# Solution Extraction Details

## Engine-Side Result Attributes (Relationships)

After `problem.solve()`, these accessors return Relationships usable in `model.require()`, `model.select()`, and solver expressions (the Python-side `solve_info()` counterparts live in SKILL.md > Solution Extraction):

| Method | Return type | Description |
|--------|-------------|-------------|
| `problem.termination_status()` | Relationship | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `problem.objective_value()` | Relationship | Optimal objective value |
| `problem.num_points()` | Relationship | Number of solutions returned |
| `problem.error()` | Relationship | Error message tuple (if solve failed) |
| `problem.printed_model()` | Relationship | Text representation (with `print_format=`) |
| `problem.num_variables()` | Relationship | Total registered variables |
| `problem.num_constraints()` | Relationship | Total constraints |
| `problem.num_min_objectives()` | Relationship | Number of minimize objectives |
| `problem.num_max_objectives()` | Relationship | Number of maximize objectives |

```python
# Engine-side: integrity constraint on status (reports only with compiler.require_mode: report)
model.require(problem.termination_status() == "OPTIMAL")
```

---

## Querying Solution Values

The canonical `populate=True` and `populate=False` queries are in SKILL.md > Solution Extraction. The rules behind them:

- Use `model.select()` by default: with `populate=True`, solved values are written back as property values and query like any other model data, with entity context. `.inspect()` prints; `.to_df()` returns the DataFrame.
- Use `populate=False` + `var.values(sol_index, value_ref)` for loop-based exclusion/partition scenarios, where several Problems share decision variables and one solve would overwrite another's results. Scenario Concept workflows keep `model.select()`: the scenario is part of the variable's identity.
- `solve_for()` returns a `ProblemVariable`, `satisfy()` a `ProblemConstraint`, `minimize()`/`maximize()` a `ProblemObjective`. All three are Concepts usable in `model.define()`, `model.select()` and `.ref()`. For entity context, traverse a variable's back-pointers or the ones a constraint declared with `keyed_by=`; an objective has none.

---

## Variable.values() Back-Pointer Naming Rule

Each **non-value** field in the Property's format string becomes a back-pointer attribute on the `ProblemVariable`. The **last** field is the value field — you read it via `var.values(sol_idx, val_ref)` and it is NOT a back-pointer. For each non-value field, the back-pointer attribute name is the **explicit `:name` from the format string if present**, otherwise the **lowercased type name**. Examples:

| Property definition | Back-pointers on the returned var | Value field |
|---|---|---|
| `f"{Assignment} has {Float:x}"` | `var.assignment` (lowercased type) | `x` |
| `f"{Edge:e} has {Float:flow}"` | `var.e` (explicit `:e` overrides `edge`) | `flow` |
| `f"{Queen} is in {Integer:column}"` | `var.queen` | `column` |
| `f"{Player} in {Integer:week} is in {Integer:group}"` | `var.player`, `var.week` | `group` |
| `f"cell {Integer:i} {Integer:j} is {Integer:x}"` | `var.i`, `var.j` (no entity concept) | `x` |
| `f"{MachinePeriod} has {Float:x}"` | `var.machineperiod` (lowercased as-is, NOT `machine_period`) | `x` |
| `f"{Float:x}"` | none — call `var.values(sol_idx, val)` directly | `x` |

The lowercased type name is the type name converted to lowercase **as-is** — no underscores or snake_case conversion. `MachinePeriod` becomes `machineperiod`, not `machine_period`.

---

## Constraint Back-Pointer Access (marginals & conflict membership)

A `ProblemConstraint` carries one entity back-pointer per grounding key declared with `keyed_by=` at `satisfy()` time, named by the **dict key you chose** (`keyed_by={"resource": Resource}` reads back as `cap.resource`), never by the `name=` display label. There is no automatic constraint back-pointer. A family grounded over several entities takes several keys; a scalar grounding takes a value reference (`keyed_by={"i": X.i}`). Reading marginals and conflict flags through it: SKILL.md > Sensitivity & conflict attributes; the formulation idiom and key-uniqueness rule: `rai-prescriptive-problem/references/constraint-formulation.md` > Declaring constraint keys.

---

## Silent-Failure Warnings

`ProblemVariable` is a Concept subclass, and Concepts return a `Chain` from `__getattr__` for unknown attribute names instead of raising. Three common mistakes all silently return a `Chain` and produce empty or garbage results (not an `AttributeError`):

1. Writing `var.edge` when the format string said `{Edge:e}` (explicit `:name` was `:e`).
2. Writing `var.column` or `var.group` when the name is a **value** field — those are not back-pointers; read them through `var.values(sol_idx, val_ref)`.
3. Writing `var.machine_period` when the concept is `MachinePeriod` — the correct name is `var.machineperiod` (lowercased, no underscores).

Always match the attribute name to a non-value field name in the format string.

---

## Exporting Solution Results to Tables

After extracting solution values, export them to a Snowflake table using `.into().exec()`:

```python
# Export optimal allocations to a results table
results_table = model.Table("DB.SCHEMA.OPTIMIZATION_RESULTS")
model.select(
    Route.origin.name.alias("FROM_SITE"),
    Route.dest.name.alias("TO_SITE"),
    Route.x_flow.alias("OPTIMAL_FLOW"),
).where(Route.x_flow > 1e-6).into(results_table).exec()
```

**Replace vs update:** Use `update=True` to merge into an existing table (e.g., appending scenario results):

```python
results_table = model.Table("DB.SCHEMA.SCENARIO_RESULTS")
model.select(
    Food.name.alias("FOOD"), Food.amount.alias("AMOUNT"),
).into(results_table, update=True).exec()
```

## Multiple Solutions

MiniZinc on a `Problem(model, Integer)` returns up to K distinct feasible points for `solve(..., solution_limit=K)`; what the limit does on other solvers, and how to size K: [solver-parameters.md](solver-parameters.md) > `solution_limit` semantics. Count points with `si.num_points` (or `problem.num_points()`), read point k with `var.values(k, ref)` (0-based), and gate the loop on status:

```python
problem = Problem(model, Integer)
pick = problem.solve_for(Item.x_pick, type="bin", name=["pick", Item.name], populate=False)
problem.satisfy(model.require(sum(Item.x_pick) == 2))
problem.solve("minizinc", solution_limit=5)
si = problem.solve_info()
if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):   # OPTIMAL = fewer than K found (complete unless the time limit hit)
    v = Integer.ref()
    for k in range(si.num_points or 0):
        model.select(pick.item.name).where(pick.values(k, v), v > 0.5).inspect()
```

Zero points under `TIME_LIMIT` or an error does not mean the feasible set is empty: the search did not finish (SKILL.md > Audit / witness mode). For people comparing alternatives, a handful of points (3-10) is enough; if one criterion should decide between them, it belongs in the objective.

## Iterative Solving

Constraints defined over concepts automatically apply to new data added between solves. Pattern:
1. Solve relaxed problem
2. Inspect solution (e.g., find subtours)
3. Add violated constraints as new data
4. Re-solve — existing `problem.satisfy()` picks up new data

## Scenario / Parametric Solving

**Scenario Concept** (only parameter values change): one solve; results stay in the ontology for the rest of the solving process, queryable with `model.select(Scenario.name, ...).where(Entity.x_var(Scenario, x_ref), x_ref > threshold)` and grouped by `Scenario.name`. [examples/scenario_concept_extraction.py](../examples/scenario_concept_extraction.py).

**Loop + `where=`** (the problem's structure changes: entities added or removed): one Problem per iteration with `populate=False`; results come back through `Variable.values()` into Python DataFrames labelled by scenario. [examples/loop_based_extraction.py](../examples/loop_based_extraction.py). Choosing between them: `rai-prescriptive-problem/references/scenario-analysis.md`.
