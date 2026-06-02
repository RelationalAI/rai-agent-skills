# Diagnostic Workflow

Iterative debugging surface for the formulate → solve → inspect → fix → re-solve loop. Use when a solve returns something surprising (INFEASIBLE, trivial-zero OPTIMAL, OPTIMAL with values that don't match intent) or when you want to confirm a specific component grounded as expected before committing to a long solve.

The Step 5 audit (`SKILL.md`) catches static issues before solve. This reference covers the diagnostic surface around solve: pre-solve handles (capture-ref pattern, cardinality assertions) and post-solve triage (status branching, targeted `display(ref)`, `verify`).

---

## The capture-ref pattern

`solve_for`, `satisfy`, `minimize`, `maximize` each return a Concept (`ProblemVariable`, `ProblemConstraint`, `ProblemObjective`) — the diagnostic handle. Pass `name=[Entity.id]` at `satisfy()` time so `display(ref)` rows carry identifiable labels; without it, rows are formula text only and you can't tell *which* entity didn't ground. The Python attributes `problem.variables`, `problem.constraints`, `problem.objectives` hold these refs as lists in declaration order — useful when iterating over an unfamiliar Problem. See [SKILL.md](../SKILL.md) for the full setup pattern.

---

## Targeted display

`problem.display(ref)` prints just the named component's grounded form for a constraint (substituted sums) or objective (expanded coefficients). `problem.display()` with no argument prints the whole formulation, including the variable table. For per-variable inspection, query rows via the DSL — `model.select(var_ref.name, var_ref.lower, var_ref.upper).to_df()` — since `display(part)` is reserved for constraints and objectives.

Prefer targeted display when the failure is localized — it cuts noise and makes the relevant grounding readable.

| Suspicion | Targeted call | What to check in the output |
|---|---|---|
| `where=` excluded too much (or too little) | `model.select(var_ref.name, var_ref.lower, var_ref.upper).to_df()` | Per-instance bounds and entity tuples — does the variable exist for every entity it should? Variable rows are queried via the DSL; `display(part)` itself is for constraints and objectives. |
| `.per()` mis-scoped (silent OPTIMAL trap) | `problem.display(constr_ref)` | Each generated row's sum should disaggregate by the intended group; `sum(all_AB) == 1` repeated per row signals wrong scope |
| Per-entity bound missing for some entities (Step 5 (d)) | `problem.display(constr_ref)` | A grouping whose body has no tuples grounds no row; rows that did ground show the expected name. Use `name=[Entity.id]` at `satisfy()` time so identifiers appear |
| Objective coefficient property has no tuples for some entities | `problem.display(obj_ref)` | Expanded objective shows the terms that ground; entities missing from the rendered sum have no tuple for the coefficient property (under PyRel relational semantics, no tuple = no row in the join) — typically `model.define(...)` missing |
| Constraint redundant or contradictory | `problem.display(c)` for each suspect `c` | Same constraint twice, or two constraints whose grounded forms are mutually unsatisfiable |

### Sampling large constraints

For very-large per-grouping constraints where the full rendered table is too long to read, use `problem.display(ref, limit=N)`, the whole-problem `display(limit=N)`, or the `where=` filter form `display(ref, where=ref.name == "...")`. The `name=["cap", Entity.id]` you passed at `satisfy()` time is what makes the filter strings predictable (joined with `_`, e.g. `name=["cap", Site.id]` → `"cap_42"` for the Site whose `id` is 42).

For the sampling API, stratification caveats, and when to drop into `model.select(ref.name)` instead, see [rai-prescriptive-solver-management/references/formulation-display.md](../../rai-prescriptive-solver-management/references/formulation-display.md) > Targeted Inspection.

---

## Pre-solve cardinality asserts

`Problem` exposes engine-queryable counts. Use them as ICs to fail fast when registration cardinality doesn't match intent:

```python
model.require(problem.num_variables() == aggs.count(Lane).where(Lane.active))
model.require(problem.num_constraints() == aggs.count(Source) + aggs.count(Sink))  # cap per Source + demand per Sink
```

Available counts: `num_variables()`, `num_constraints()`, `num_min_objectives()`, `num_max_objectives()`. Each returns a Relationship usable in `model.require(...)` or `model.select(...)`.

`num_constraints()` is a global check; per-constraint cardinality (Step 5 (d) in `SKILL.md`) localizes *which* constraint is short.

These ICs persist for the lifetime of the model — use them in single-shot validation, not in iterative solve loops where constraint counts change between solves. For iterative workflows, use `len(model.select(ref).to_df())` instead.

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
| `OPTIMAL` / `LOCALLY_SOLVED` | Solver claims a solution | If values look right, run `verify`. If suspicious (all-zero, concentrated, dominated), suspect a missing forcing constraint, an unbound coefficient, or a per-entity constraint that grounded for fewer entities than expected — display each constraint and objective ref |
| `INFEASIBLE` | No feasible point | Localize with `solve(conflict=True)` (IIS) — one solve returns the minimal conflicting subset of constraints / bounds; then rebuild the Problem omitting or relaxing a member (see below and [fix-generation-guidelines.md](fix-generation-guidelines.md) > Infeasible Solution). Manual constraint-walking is the fallback when the solver reports `NOT_SUPPORTED` |
| `TIME_LIMIT` / `ITERATION_LIMIT` | Solver gave up | Distinct from formulation bug — see `rai-prescriptive-solver-management` |
| Status unset / `error` non-empty | Solver rejected the model | Read `si.error`; common causes are unsupported expression types, type mismatches, solver-specific syntax limits. If `si.error` is also empty, the formulation failed before the solver received it — check stderr for `ModelWarning` or `RAIException`. |

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

When `si.termination_status == "INFEASIBLE"`, the first move is `solve(conflict=True)` — one solve returns the **conflict (IIS)**: a minimal subset of constraints and variable bounds that cannot all hold. It needs no objective and works on MIP. Read the members joined to their entity by key:

```python
problem.solve("highs", conflict=True)
si = problem.solve_info()
if si.conflict_status == "CONFLICT_FOUND":
    model.select(floor.region.name, floor.region.demand).where(floor.in_conflict).inspect()
```

The IIS is a subset to inspect or relax — **not necessarily a single offending `satisfy()`**. Relaxing one member restores feasibility for *that* conflict; if other independent conflicts remain the model is still infeasible, so **re-solve to confirm**. For the full membership / `conflict_status` reading, see `rai-prescriptive-results-interpretation/references/conflict-analysis.md`.

**Fallback — manual constraint-walking** (when `conflict_status` is `NOT_SUPPORTED` on the chosen solver, or `FAILED`): walk the constraints and inspect their grounded forms:

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

When status is OPTIMAL but values are all-zero or otherwise vacuous, the suspect is a missing forcing constraint, an unbound coefficient, or a per-entity constraint whose body didn't ground for the entities that mattered.

1. `problem.display(obj_ref)` — confirm the objective expanded with non-zero coefficients on the variables you expect. All-zero coefficients = `model.define(...)` populating data is missing.
2. For each forcing constraint (`>= demand`, `>= min_coverage`, etc.) call `problem.display(c)` — confirm the constraint generated rows. If the constraint body's own `.where(...)` filter matches no entities, the constraint grounds zero rows; it exists in the formulation but is vacuous against the data.
3. For per-entity constraints, check cardinality (`len(model.select(c).to_df()) == len(model.select(Entity).to_df())`) — a sparse bound property leaves the per-grouping body empty for entities missing data, so under PyRel relational semantics no row grounds for them (Step 5 (d)).
4. Cross-check with [examples/presolve_feasibility_gate.py](../examples/presolve_feasibility_gate.py) — the same aggregation-query checks that gate solve also localize which forcing requirement is empty.

See [fix-generation-guidelines.md](fix-generation-guidelines.md) > Trivial Solution for fix priority.

---

## Quick reference

| Diagnostic | Call | Use when |
|---|---|---|
| Whole-problem snapshot | `problem.display()` | First glance at an unfamiliar Problem; verify formulation shape after major rewrite |
| Whole-problem sample | `problem.display(limit=N)` | Large model — caps each table at top-N rows by name; counts in header stay true |
| Component grounding | `problem.display(ref)` | Localized failure; verifying `.per()` scope; confirming bounds substitution |
| Sampled component | `problem.display(ref, limit=N)` | Very-large per-grouping constraint where even one component is too long to read in full |
| Filtered component | `problem.display(ref, where=<predicate>)` | Pick a specific row by name (or any other property) when you know which one to look at — `where=` requires `part`. |
| Cardinality assertion | `model.require(problem.num_constraints() == ...)` | Catch "constraint loop never ran" before solving |
| Per-constraint cardinality | `len(model.select(constr_ref).to_df()) == len(model.select(Entity).to_df())` | Localize a per-entity constraint that didn't ground for missing-bound entities |
| Post-solve summary | `problem.solve_info().display()` | Always — first thing after `solve()` returns |
| Solver error inspection | `si.error` | Status looks fine but result is wrong; status is unset |
| Constraint re-evaluation | `problem.verify(*fragments)` | Tolerance-sensitive constraints; before committing solution downstream |
| Constraint walk | `for c in problem.constraints: problem.display(c)` | INFEASIBLE; surprising OPTIMAL where one constraint is suspect |
| Solver-format dump | `solve(..., print_format="moi"\|"latex"\|"mof"\|"lp"\|"mps"\|"nl")` then `si.printed_model` | Solver-level debugging beyond formulation |
