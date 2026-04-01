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

- **Request multiple solutions:** `p.solve("minizinc", solution_limit=10)` — `solution_limit` is a first-class parameter
- **Check count:** `p.num_points()` (Relationship) or `p.solve_info().num_points` (Python)
- **Extract all solutions:** `p.variable_values(multiple=True).to_df()` returns a DataFrame with `sol_index` (0-based), `name`, `value`
- **Switch active solution:** `p.load_point(index)` loads solution at 0-based index (0 = first, up to `num_points - 1`). After loading, `model.select()` on populated properties reflects the selected solution. `load_point()` can also be used with `populate=False` to manually control when solution values are written to model properties.

```python
# Solve with multiple solutions
p.solve("minizinc", solution_limit=5)
si = p.solve_info()
print(f"Found {si.num_points} solutions")

# View all solutions
all_df = p.variable_values(multiple=True).to_df()

# Switch to solution 2 (0-based) and query
p.load_point(2)
sol2_df = model.select(Food.name, Food.amount).to_df()
```

**How many solutions to request:**

Keep `solution_limit` small (typically 3-10). The primary use case for multiple solutions is enabling human evaluation — like Google Maps showing a few route options — but humans are not effective at comparing hundreds of alternatives. If there is an analytical way to compare solutions, that comparison criterion belongs in the objective function, not in post-hoc filtering of a large solution set.

Requesting very large solution counts (e.g., 100,000) is almost never appropriate. The few specialized cases where large solution sets make sense include running downstream simulations over candidate solutions or feeding alternatives into a separate evaluation pipeline. For standard decision-support problems, a handful of near-optimal alternatives is far more useful than an exhaustive enumeration.

## Iterative Solving

Constraints defined over concepts automatically apply to new data added between solves. Pattern:
1. Solve relaxed problem
2. Inspect solution (e.g., find subtours)
3. Add violated constraints as new data
4. Re-solve — existing `p.satisfy()` picks up new data

## Scenario / Parametric Solving

**Scenario Concept (parameter variations) — preferred when applicable:** Results from a single solve are incorporated into the ontology — queryable via `model.select(Scenario.name, ...).where(Entity.x_var(Scenario, x_ref), x_ref > threshold)`, composable with other model queries, and available for downstream derived properties. Group by `Scenario.name` for comparison tables. Variables are multi-argument Properties indexed by (Entity, Scenario) — the scenario column is part of the variable identity. Use when only parameter values change between scenarios (budget, demand, thresholds). See [examples/portfolio_scenario_concept_results.py](../examples/portfolio_scenario_concept_results.py).

**Loop + where= (entity exclusion):** Each iteration produces a separate `variable_values().to_df()` — results live in Python DataFrames, outside the model. Collect per-iteration results in a list, label by scenario. Use `populate=False` to prevent cross-iteration contamination. Required when the problem *structure* changes between scenarios (entities added/removed, constraint graph differs). See [examples/portfolio_results.py](../examples/portfolio_results.py).
