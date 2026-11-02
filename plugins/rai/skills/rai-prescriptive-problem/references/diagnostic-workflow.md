# Diagnostic Workflow

Iterative debugging surface for the formulate → solve → inspect → fix → re-solve loop. Use when a solve returns something surprising (INFEASIBLE, trivial-zero OPTIMAL, OPTIMAL with values that don't match intent) or when you want to confirm a specific component grounded as expected before committing to a long solve.

The Step 5 audit (`SKILL.md`) catches static issues before solve. This reference covers the diagnostic surface around solve: the capture-ref pattern and post-solve triage (status branching, targeted `display_string` reads, `verify`).

---

## The capture-ref pattern

`solve_for`, `satisfy`, `minimize`, `maximize` each return a Concept (`ProblemVariable`, `ProblemConstraint`, `ProblemObjective`) — the diagnostic handle. Pass `name=[Entity.id]` at `satisfy()` time so the rendered rows carry identifiable labels; without it, rows are formula text only and you can't tell *which* entity didn't ground. The Python attributes `problem.variables`, `problem.constraints`, `problem.objectives` hold these refs as lists in declaration order — useful when iterating over an unfamiliar Problem. See [SKILL.md](../SKILL.md) for the full setup pattern.

---

## Targeted display

*The `display_string` surface below requires relationalai>=1.29. `problem.display()` takes no positional arguments there: whole-problem output is `display(limit=N)`, and targeted reads go through `display_string`.*

Every constraint and objective carries a `display_string` property holding the text rendered from its expression tree. Selecting it on a captured ref reads just that component's grounded form — substituted sums for a constraint, expanded coefficients for an objective.

Install the rendering rules once, after the model is fully declared, then select:

```python
problem.install_display_strings()
model.select(constr_ref.name, constr_ref.display_string).inspect()
```

A null `display_string` never comes with an error. The first two checks are a missing install (a direct select does not install on demand) and a decision variable declared without `name=`, which stays null after a correct install. Full list, the install's cost, and sampling very large constraints: [formulation-display.md](formulation-display.md) > Targeted Inspection with `display_string`.

Variables have no `display_string`; query their rows via the DSL — `model.select(var_ref.name, var_ref.lower, var_ref.upper).to_df()`.

Prefer a targeted read when the failure is localized — it cuts noise and makes the relevant grounding readable.

| Suspicion | Targeted call | What to check in the output |
|---|---|---|
| `where=` excluded too much (or too little) | `model.select(var_ref.name, var_ref.lower, var_ref.upper).to_df()` | Per-instance bounds and entity tuples — does the variable exist for every entity it should? |
| `.per()` mis-scoped (silent OPTIMAL trap) | `model.select(constr_ref.name, constr_ref.display_string).to_df()` | Each generated row's sum should disaggregate by the intended group; `sum(all_AB) == 1` repeated per row signals wrong scope |
| Per-entity bound missing for some entities (Step 5 (d)) | `model.select(constr_ref.name, constr_ref.display_string).to_df()` | A grouping whose body has no tuples grounds no row; rows that did ground show the expected name. Use `name=[Entity.id]` at `satisfy()` time so identifiers appear |
| Objective coefficient property has no tuples for some entities | `model.select(obj_ref.name, obj_ref.display_string).to_df()` | Expanded objective shows the terms that ground; entities missing from the rendered sum have no tuple for the coefficient property (under PyRel relational semantics, no tuple = no row in the join) — typically `model.define(...)` missing |
| Constraint redundant or contradictory | `model.select(c.name, c.display_string).to_df()` for each suspect `c` | Same constraint twice, or two constraints whose grounded forms are mutually unsatisfiable |

---

## Pre-solve cardinality asserts

Entity, binding, grounding and engine-side counts before solving: [pre-solve-validation.md](pre-solve-validation.md) > Cardinality checks.

---

## Post-solve triage

After `problem.solve(...)` returns, branch on `solve_info`:

```python
si = problem.solve_info()
si.display()  # status, objective value, solve time, num_points, errors
```

Fields beyond `termination_status` and `objective_value`: `solve_time_sec`, `num_points`, `primal_status`, `solver_version`, `error: tuple[str, ...]`, `printed_model` (when `solve(..., print_format=...)` was set; formats: [formulation-display.md](formulation-display.md) > `problem.printed_model()`).

**Always check `si.error` even when status looks fine** — solver-side errors don't always demote the termination status. If `solve()` raised, read the exception instead: `solve_info()` still describes the last solve that didn't raise.

Branch by status:

| Status | What it means | Diagnostic move |
|---|---|---|
| `OPTIMAL` / `LOCALLY_SOLVED` | Solver claims a solution | If values look right, run `verify`. If suspicious (all-zero, concentrated, dominated), suspect a missing forcing constraint, an unbound coefficient, or a per-entity constraint that grounded for fewer entities than expected — install the rendering rules and read each constraint and objective ref's `display_string` |
| `INFEASIBLE` | No feasible point | Localize with `solve(conflict=True)` (IIS), then rebuild the Problem omitting or relaxing a flagged member — see INFEASIBLE: localizing the conflict below |
| `TIME_LIMIT` / `ITERATION_LIMIT` | Stopped at a limit; holds a solution only if `si.primal_status == "FEASIBLE_POINT"` (before relationalai 1.26, for a MIP: `if si.num_points:`) | Distinct from formulation bug — see `rai-prescriptive-results` |
| Error status (`OTHER_ERROR`, …) or unset; `error` non-empty | Solver or service rejected the request | Read `si.error`: common causes are an unsupported solver option, unsupported expression types, type mismatches, solver-specific syntax limits. If `si.error` is also empty, the formulation failed before the solver received it — check stderr for `ModelWarning` or `RAIException`. |

---

## `problem.verify(*fragments)` — post-solve constraint check

`verify` re-evaluates one or more `Fragment` (the result of `model.require(...)` or `model.where(...).require(...)`) against the returned solution. Emits a `ModelWarning` (`from v0.relationalai.errors import ModelWarning`) if any fragment is violated, but only when the config sets `compiler: require_mode: report` (default `ignore`: silent; `rai-prescriptive-results` > Post-solve constraint verification); emits `UserWarning` and returns early if `termination_status` isn't in `{"OPTIMAL", "LOCALLY_SOLVED", "SOLUTION_LIMIT"}`.

```python
demand_frag = model.require(sum(Lane.flow).per(Sink) >= Sink.demand)
problem.satisfy(demand_frag)
problem.solve("highs")
problem.verify(demand_frag)  # confirms the solution actually meets demand
```

It checks at IC strictness, not solver tolerance (~1e-8), so on a continuous constraint like this one it can warn about a point the solver returned correctly; PyRel's docstring recommends a tolerant post-solve `model.require(x <= bound + 1e-6)` there. A pass is not a certificate either: it skips solver-only IC bodies ([csp-formulation.md](csp-formulation.md) § 6), and the SQL backend does not report ICs, so there it cannot warn.

Pass the original fragments (the values you handed to `model.require`) — not the `ProblemConstraint` refs.

---

## INFEASIBLE: localizing the conflict

When `si.termination_status == "INFEASIBLE"`, the first move is `solve(conflict=True)` — when the solver supports it, one solve returns the **conflict (IIS)**: a minimal subset of constraints and variable bounds that cannot all hold. It needs no objective and works on MIP. Read the members joined to their entity by key:

```python
# floor = a per-Region satisfy(..., keyed_by={"region": Region}) family
# Upfront, or as a re-solve after the INFEASIBLE plain solve (relationalai>=1.26)
problem.solve("highs", conflict=True)
si = problem.solve_info()
if si.conflict_status == "CONFLICT_FOUND":
    model.select(floor.region.name, floor.region.demand).where(floor.in_conflict).inspect()
```

The IIS is a subset to inspect or relax — **not necessarily a single offending `satisfy()`**. Each flagged member is a *candidate* (the flags are leads), so relax one and **re-solve to confirm** — relaxing a true member restores feasibility for *that* conflict, but other independent conflicts may remain. For the full membership / `conflict_status` reading, see `rai-prescriptive-results/references/conflict-analysis.md`.

**Fallback — manual constraint-walking** (when `conflict_status` is `NOT_SUPPORTED` on the chosen solver, or `FAILED`): walk the constraints and inspect their grounded forms:

```python
problem.install_display_strings()
c = problem.Constraint
# grounded sums and bounds for every constraint, in one read
model.select(c.name, c.display_string).inspect()
```

What to look for:

- A single constraint's grounded RHS is unreachable given other constraints' grounded LHS (e.g., `sum(Decision.x) == 100` while another forces `sum(Decision.x) <= 50`)
- A `.per()` group with no rows on one side but a non-zero requirement on the other (`>= demand` for a sink with no inbound lanes)
- Two soft-looking constraints that are jointly infeasible only at a specific entity slice

After identifying the offender, rebuild the `Problem` omitting or relaxing the conflicting `satisfy(...)` (or widen a flagged variable bound/type if `var.*_in_conflict` is the member) — `Problem` accumulates and has no removal API. See [fix-generation-guidelines.md](fix-generation-guidelines.md) > Infeasible Solution.

---

## Trivial-OPTIMAL: localizing the missing forcing constraint

When status is OPTIMAL but values are all-zero or otherwise vacuous, the suspect is a missing forcing constraint, an unbound coefficient, or a per-entity constraint whose body didn't ground for the entities that mattered.

1. `problem.install_display_strings()` first — without it every `display_string` below is null, which reads exactly like an objective that expanded to nothing.
2. `model.select(obj_ref.name, obj_ref.display_string).inspect()` — confirm the objective expanded with non-zero coefficients on the variables you expect. A term missing for some entities = the coefficient property has no tuple for them (typically a `model.define(...)` is missing).
3. Read every constraint in one go — `c = problem.Constraint; model.select(c.name, c.display_string).inspect()` — and confirm each forcing constraint (`>= demand`, `>= min_coverage`, etc.) generated rows. If the constraint body's own `.where(...)` filter matches no entities, the constraint grounds zero rows; it exists in the formulation but is vacuous against the data.
4. For a per-entity constraint, compare its grounded row count with the entity count — a sparse bound property grounds no row for the entities missing data: [pre-solve-validation.md](pre-solve-validation.md) > Cardinality checks.
5. Cross-check with [examples/presolve_feasibility_gate.py](../examples/presolve_feasibility_gate.py) — the same aggregation-query checks that gate solve also localize which forcing requirement is empty.

See [fix-generation-guidelines.md](fix-generation-guidelines.md) > Trivial Solution for fix priority.
