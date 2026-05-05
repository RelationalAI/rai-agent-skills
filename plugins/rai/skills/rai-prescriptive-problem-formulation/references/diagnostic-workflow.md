# Diagnostic Workflow

Iterative debugging surface for the formulate → solve → inspect → fix → re-solve loop. Use when a solve returns something surprising (INFEASIBLE, trivial-zero OPTIMAL, OPTIMAL with values that don't match intent) or when you want to confirm a specific component grounded as expected before committing to a long solve.

The Step 5 audit (`SKILL.md`) catches static issues before solve. This reference covers the runtime diagnostic surface — what to inspect once the solve has run, plus the targeted `display(ref)` patterns that localize a problem to a specific component.

---

## The capture-ref pattern

`solve_for`, `satisfy`, `minimize`, `maximize` each return a Concept (`ProblemVariable`, `ProblemConstraint`, `ProblemObjective`). These returns are the diagnostic handles — assign them at write time so you can target them later.

```python
x_flow   = problem.solve_for(Lane.flow, where=[Lane.active], lower=0)
cap      = problem.satisfy(
    model.require(sum(Lane.flow).per(Source) <= Source.capacity),
    name=["cap", Source.id],   # name=[Entity.id] makes display rows identifiable
)
demand   = problem.satisfy(
    model.require(sum(Lane.flow).per(Sink) >= Sink.demand),
    name=["demand", Sink.id],
)
cost_obj = problem.minimize(sum(Lane.flow * Lane.unit_cost))
```

Pass `name=[Entity.id]` (or any expression that yields a unique identifier per row) at `satisfy()` time so `display(ref)` rows carry meaningful labels — without it, rows are formula text only and you can't tell *which* grouping vanished if PyRel dropped one.

The Python attributes `problem.variables`, `problem.constraints`, `problem.objectives` also hold these refs as lists in declaration order — useful when iterating over an unfamiliar Problem.

---

## Targeted display

`problem.display(part=ref)` prints just the named component's grounded form (variables expanded with bounds, constraints expanded with substituted sums, objective expanded with coefficients). `problem.display()` with no argument prints the whole formulation.

Prefer targeted display when the failure is localized — it cuts noise and makes the relevant grounding readable.

| Suspicion | Targeted call | What to check in the output |
|---|---|---|
| `where=` excluded too much (or too little) | `problem.display(var_ref)` | Per-instance bounds and entity tuples — does the variable exist for every entity it should? |
| `.per()` mis-scoped (silent OPTIMAL trap) | `problem.display(constr_ref)` | Each generated row's sum should disaggregate by the intended group; `sum(all_AB) == 1` repeated per row signals wrong scope |
| Per-entity bound silently dropped (Step 5 (d)) | `problem.display(constr_ref)` | The dropped grouping has no row; surviving rows show the expected name. Use `name=[Entity.id]` at `satisfy()` time so identifiers appear |
| Objective coefficient unbound (silent zero terms) | `problem.display(obj_ref)` | Expanded objective shows actual coefficient values per entity — zeros where data should populate indicate `model.define(...)` missing |
| Constraint redundant or contradictory | `problem.display(c)` for each suspect `c` | Same constraint twice, or two constraints whose grounded forms are mutually unsatisfiable |

### Sampling large constraints

For very-large per-grouping constraints where the full rendered table is too long to read:

```python
# Top 10 rows of one constraint, ordered by .name ascending. The summary
# header still shows true totals; only the rendered table is capped.
problem.display(cap, limit=10)

# Top 5 of every kind in the whole-problem view (counts in header stay true)
problem.display(limit=5)

# Pick a specific row by name (or any other property) — Fragment form.
# The "cap_Site_42" string is constructed by name=["cap", Site.id] above
# (sep="_"); your filter string depends on what you passed at satisfy() time.
problem.display(model.select(cap).where(cap.name == "cap_Site_42"))
```

Each `display(part)` call adds anonymous reachability rules to the model and bumps the model version (cheap per call but avoid in tight loops). The `limit` kwarg is stratification-safe for both variable and constraint paths; direct `aggregates.limit` in a Fragment's `where` only works for variables (the constraint path uses recursive AST expansion — see `display()` docstring) — use the `limit=N` kwarg instead.

To list grounded groupings without rendering the formula text — useful when even `limit` is more than you need:

```python
# All grounded names (DataFrame)
grounded = model.select(cap.name).where(cap).to_df()

# Sample
sample = model.select(cap.name).where(cap).where(cap.name == "cap_Site_42").to_df()
```

---

## Pre-solve cardinality asserts

`Problem` exposes engine-queryable counts. Use them as ICs to fail fast when registration cardinality doesn't match intent:

```python
model.require(problem.num_variables() == aggs.count(Lane).where(Lane.active))
model.require(problem.num_constraints() == 2 * aggs.count(Source))  # cap + demand per Source
```

Available counts: `num_variables()`, `num_constraints()`, `num_min_objectives()`, `num_max_objectives()`. Each returns a Relationship usable in `model.require(...)` or `model.select(...)`.

`num_constraints()` is a global check; per-constraint cardinality (Step 5 (d) in `SKILL.md`) localizes *which* constraint is short.

---

## Post-solve triage

After `problem.solve(...)` returns, branch on `solve_info`:

```python
si = problem.solve_info()
si.display()  # status, objective value, solve time, num_points, errors
```

Fields beyond `termination_status` and `objective_value`: `solve_time_sec`, `num_points`, `solver_version`, `error: tuple[str, ...]`, `printed_model` (when `solve(..., print_format=...)` was set).

**Always check `si.error` even when status looks fine** — solver-side errors don't always demote the termination status.

Branch by status:

| Status | What it means | Diagnostic move |
|---|---|---|
| `OPTIMAL` / `LOCALLY_SOLVED` | Solver claims a solution | If values look right, run `verify`. If suspicious (all-zero, concentrated, dominated), suspect a missing forcing constraint, an unbound coefficient, or a per-entity constraint that dropped silently — display each constraint and objective ref |
| `INFEASIBLE` | No feasible point | Walk `problem.constraints` with targeted display; identify the binding conflict; rebuild Problem omitting or relaxing the offender (see [fix-generation-guidelines.md](fix-generation-guidelines.md) > Infeasible Solution) |
| `TIME_LIMIT` / `ITERATION_LIMIT` | Solver gave up | Distinct from formulation bug — see `rai-prescriptive-solver-management` |
| Status unset / `error` non-empty | Solver rejected the model | Read `si.error`; common causes are unsupported expression types, type mismatches, solver-specific syntax limits. If `si.error` is also empty, the model likely failed to compile before reaching the solver — re-run with the `model.require(...)` calls active and check stderr for `ModelWarning`. |

---

## `problem.verify(*fragments)` — post-solve constraint check

`verify` re-evaluates one or more `Fragment` (the result of `model.require(...)` or `model.where(...).require(...)`) against the returned solution. Raises `ModelWarning` (`from v0.relationalai.errors import ModelWarning`) if any fragment is violated; emits `UserWarning` and returns early if `termination_status` isn't in `{"OPTIMAL", "LOCALLY_SOLVED", "SOLUTION_LIMIT"}`.

```python
demand_frag = model.require(sum(Lane.flow).per(Sink) >= Sink.demand)
problem.satisfy(demand_frag)
problem.solve("highs")
problem.verify(demand_frag)  # confirms the solution actually meets demand
```

Why this matters: solver tolerances are looser than IC checks (~1e-8 vs exact). A solution can be "OPTIMAL" by the solver and still violate the original requirement at IC strictness. Use `verify` when:

- The result is suspicious but the status looks fine
- A constraint has tight bounds where rounding could hide violations
- You're committing the solution to downstream rules / reports / customer-facing output

Pass the original fragments (the values you handed to `model.require`) — not the `ProblemConstraint` refs.

---

## INFEASIBLE: localizing the conflict

When `si.termination_status == "INFEASIBLE"`, walk the constraints and inspect their grounded forms:

```python
for c in problem.constraints:
    print(c)               # constraint name / id
    problem.display(c)     # grounded sums and bounds (limit=N to cap large ones)
```

What to look for:

- A single constraint's grounded RHS is unreachable given other constraints' grounded LHS (e.g., `sum(x) == 100` while another forces `sum(x) <= 50`)
- A `.per()` group with no rows on one side but a non-zero requirement on the other (`>= demand` for a sink with no inbound lanes)
- Two soft-looking constraints that are jointly infeasible only at a specific entity slice

After identifying the offender, rebuild the `Problem` omitting or relaxing the conflicting `satisfy(...)` — `Problem` accumulates and has no removal API. See [fix-generation-guidelines.md](fix-generation-guidelines.md) > Infeasible Solution.

---

## Trivial-OPTIMAL: localizing the missing forcing constraint

When status is OPTIMAL but values are all-zero or otherwise vacuous, the suspect is a missing forcing constraint, an unbound coefficient, or a per-entity constraint that dropped silently for the entities that mattered.

1. `problem.display(obj_ref)` — confirm the objective expanded with non-zero coefficients on the variables you expect. All-zero coefficients = `model.define(...)` populating data is missing.
2. For each forcing constraint (`>= demand`, `>= min_coverage`, etc.) call `problem.display(c)` — confirm the constraint generated rows. A `where=` predicate that matches no entities produces zero rows; the constraint exists in the formulation but is vacuous against the data.
3. For per-entity constraints, check cardinality (`len(model.select(c).to_df()) == len(model.select(Entity).to_df())`) — a sparse bound property silently drops the per-grouping body for entities missing data (Step 5 (d)).
4. Cross-check with [examples/presolve_feasibility_gate.py](../examples/presolve_feasibility_gate.py) — the same aggregation-query checks that gate solve also localize which forcing requirement is empty.

See [fix-generation-guidelines.md](fix-generation-guidelines.md) > Trivial Solution for fix priority.

---

## Quick reference

| Diagnostic | Call | Use when |
|---|---|---|
| Whole-problem snapshot | `problem.display()` | First glance at an unfamiliar Problem; sanity check after major rewrite |
| Whole-problem sample | `problem.display(limit=N)` | Large model — caps each table at top-N rows by name; counts in header stay true |
| Component grounding | `problem.display(ref)` | Localized failure; verifying `.per()` scope; confirming bounds substitution |
| Sampled component | `problem.display(ref, limit=N)` | Very-large per-grouping constraint where even one component is too long to read in full |
| Filtered component | `problem.display(model.select(ref).where(<filter>))` | Pick a specific row by name (or any other property) when you know which one to look at |
| Cardinality assertion | `model.require(problem.num_constraints() == ...)` | Catch "constraint loop never ran" before solving |
| Per-constraint cardinality | `len(model.select(constr_ref).to_df()) == len(model.select(Entity).to_df())` | Localize a per-entity constraint that dropped silently for missing-bound entities |
| Post-solve summary | `problem.solve_info().display()` | Always — first thing after `solve()` returns |
| Solver error inspection | `si.error` | Status looks fine but result is wrong; status is unset |
| Constraint re-evaluation | `problem.verify(*fragments)` | Tolerance-sensitive constraints; before committing solution downstream |
| Constraint walk | `for c in problem.constraints: problem.display(c)` | INFEASIBLE; surprising OPTIMAL where one constraint is suspect |
| Solver-format dump | `solve(..., print_format="moi"\|"latex"\|"mof"\|"lp"\|"mps"\|"nl")` then `si.printed_model` | Solver-level debugging beyond formulation |
