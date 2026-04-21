# Solution Extraction Details

## Table of Contents
- [Exporting Solution Results to Tables](#exporting-solution-results-to-tables)
- [Multiple Solutions](#multiple-solutions)
- [Iterative Solving](#iterative-solving)
- [Scenario / Parametric Solving](#scenario--parametric-solving)

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

The `.into(table)` call writes query results to the specified Snowflake table. Use `update=True` to merge into an existing table rather than replacing it.

## Multiple Solutions

v1 supports multiple solutions natively:

- **Request multiple solutions:** `problem.solve("minizinc", solution_limit=10)` — `solution_limit` is a first-class parameter
- **Check count:** `problem.num_points()` (Relationship) or `problem.solve_info().num_points` (Python)
- **Extract solution values:** Use `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for()` for structured access via back-pointers. For multi-solution access, use different `sol_index` values.

```python
# Solve with multiple solutions
problem = Problem(model, Float)
amount_var = problem.solve_for(Food.x_amount, lower=0)
problem.minimize(sum(Food.cost * Food.x_amount))
problem.solve("minizinc", solution_limit=5)
si = problem.solve_info()
print(f"Found {si.num_points} solutions")

# Extract solution at index 0 (preferred: Variable.values())
value_ref = Float.ref()
sol0_df = model.select(
    amount_var.food.name.alias("food"),
    value_ref.alias("amount"),
).where(amount_var.values(0, value_ref), value_ref > 0.001).to_df()

# Extract solution at index 2
sol2_df = model.select(
    amount_var.food.name.alias("food"),
    value_ref.alias("amount"),
).where(amount_var.values(2, value_ref), value_ref > 0.001).to_df()

```

**How many solutions to request:**

Keep `solution_limit` small (typically 3-10). The primary use case for multiple solutions is enabling human evaluation — like Google Maps showing a few route options — but humans are not effective at comparing hundreds of alternatives. If there is an analytical way to compare solutions, that comparison criterion belongs in the objective function, not in post-hoc filtering of a large solution set.

Requesting very large solution counts (e.g., 100,000) is almost never appropriate. The few specialized cases where large solution sets make sense include running downstream simulations over candidate solutions or feeding alternatives into a separate evaluation pipeline. For standard decision-support problems, a handful of near-optimal alternatives is far more useful than an exhaustive enumeration.

## Iterative Solving

Constraints defined over concepts automatically apply to new data added between solves. Pattern:
1. Solve relaxed problem
2. Inspect solution (e.g., find subtours)
3. Add violated constraints as new data
4. Re-solve — existing `problem.satisfy()` picks up new data

## Scenario / Parametric Solving

**Scenario Concept (parameter variations) — preferred when applicable:** Results from a single solve are incorporated into the ontology — queryable via `model.select(Scenario.name, ...).where(Entity.x_var(Scenario, x_ref), x_ref > threshold)`, composable with other model queries, and available for downstream derived properties. Group by `Scenario.name` for comparison tables. Variables are multi-argument Properties indexed by (Entity, Scenario) — the scenario column is part of the variable identity. Use when only parameter values change between scenarios (budget, demand, thresholds). See [examples/scenario_concept_extraction.py](../examples/scenario_concept_extraction.py).

**Loop + where= (entity exclusion):** Each iteration produces results via `Variable.values()` — results live in Python DataFrames, outside the model. Collect per-iteration results in a list, label by scenario. Use `populate=False` to prevent cross-iteration contamination. Required when the problem *structure* changes between scenarios (entities added/removed, constraint graph differs). See [examples/loop_based_extraction.py](../examples/loop_based_extraction.py).
