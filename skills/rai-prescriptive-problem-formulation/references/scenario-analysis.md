# Scenario Analysis (What-If)

Two patterns for exploring how solutions change under different assumptions.

## Pattern 1: Scenario Concept — parameter variations (preferred)

When the same problem structure is solved with different parameter values (budget, demand,
service levels), model scenarios as a first-class Concept. One solve handles all scenarios:

```python
# Assumes: Stock = model.Concept("Stock", identify_by={"index": Integer})
# with Stock.returns (Float) and Stock data already loaded.

# Scenario with parameter data
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_return = model.Property(f"{Scenario} has {Float:min_return}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_return"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable indexed by Scenario
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()

# Constraint references Scenario property
return_ok = model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(
    sum(x_qty * Stock.returns).per(Scenario) >= Scenario.min_return
)

# Single solve — all scenarios simultaneously
problem = Problem(model, Float)
problem.solve_for(Stock.x_quantity(Scenario, x_qty), name=[Scenario.name, "qty", Stock.index])
problem.satisfy(return_ok)
problem.minimize(sum(Stock.x_quantity))
problem.solve(solver, time_limit_sec=60)

# Results: query with scenario filter
model.select(Scenario.name, Stock.index, Stock.x_quantity).where(
    Stock.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()
```

## Pattern 2: Loop + where= filter — entity selection/exclusion

When different entity subsets are tested (exclude a supplier, solve per region),
loop with `where=[]` scoping. Each iteration is an independent sub-problem:

```python
for excluded in [None, "SupplierC", "SupplierB"]:
    problem = Problem(model, Float)
    if excluded:
        active = Order.supplier.name != excluded
        problem.solve_for(Order.x_qty, where=[active], populate=False)
    else:
        problem.solve_for(Order.x_qty, populate=False)
    problem.maximize(...)
    problem.solve(solver, time_limit_sec=60)
    # Use Variable.values() or variable_values().to_df() for per-iteration results
```

## When to use which

| Criterion | Scenario Concept | Loop + where= |
|-----------|-----------------|---------------|
| What varies | Parameter values (budget, demand, thresholds) | Which entities participate (exclude supplier, solve per factory) |
| Problem structure | Same constraints, same entities, different parameter values | Constraints or entity sets change between scenarios |
| Number of solves | One (all scenarios simultaneously) | One per scenario |
| Where results live | **In the ontology** — queryable via `model.select()`, composable with other model queries, available for downstream derived properties | In Python DataFrames via `Variable.values()` or `variable_values().to_df()` — outside the model |
| Problem size | Cross-product of entities x scenarios (can be large) | Each sub-problem is small and independent |

**Decision rule:**
- Only parameter values change -> **Scenario Concept**. Results are part of the ontology, which is the key advantage — they can be queried, joined, and composed like any other model data.
- Entities are added/removed or constraint structure changes -> **Loop + where=**. Required when the problem graph itself differs between scenarios (e.g., removing a supplier changes which entities exist).
- Independent partitions (per-factory, per-region) -> **Loop + where=**. Each partition is a separate problem with no cross-partition coupling.

## Pattern 3: Epsilon Constraint Loop (Bi-Objective)

When two objectives compete, the epsilon constraint loop sweeps the secondary objective's bound across the feasible range. Each iteration is a standard single-objective problem with one extra constraint — same Loop + `populate=False` infrastructure as Pattern 2.

Can combine with Scenario Concept: place Scenario Concept inside the epsilon loop so each epsilon solve handles all parameter scenarios simultaneously (N solves, not N x M).

| Criterion | Scenario Concept (Pattern 1) | Loop + where= (Pattern 2) | Epsilon Constraint (Pattern 3) |
|-----------|-----------------|---------------|------|
| What varies | Parameter values | Entity subsets | Secondary objective bound |
| Number of solves | One | One per scenario | One per epsilon point |
| Use case | What-if on parameters | Entity exclusion/partition | Tradeoff frontier between competing objectives |

For the full epsilon constraint method (anchor solves, direction handling, loop pattern, pitfalls), see [multi-objective-formulation.md](multi-objective-formulation.md).
