# Examples Index

| Problem Type | Pattern Demonstrated | File |
|---|---|---|
| Diet optimization | Continuous vars + ternary property join for per-nutrient constraint | [examples/diet.py](../examples/diet.py) |
| Network flow | Flow conservation per node using two independent Edge refs | [examples/network_flow.py](../examples/network_flow.py) |
| Shift assignment | Binary vars scoped to availability + per-entity coverage constraints | [examples/shift_assignment.py](../examples/shift_assignment.py) |
| Portfolio balancing | Pairwise quadratic risk via Stock.ref() + Float.ref() covariance binding | [examples/portfolio_balancing.py](../examples/portfolio_balancing.py) |
| Supply chain transport | Multi-concept coordination: inventory conservation + mode selection + model.union() objective | [examples/supply_chain_transport.py](../examples/supply_chain_transport.py) |
| Retail markdown | One-hot selection, price ladder constraint, cumulative tracking with temporal recurrence | [examples/retail_markdown.py](../examples/retail_markdown.py) |
| Factory production | Partitioned sub-problem solving with `populate=False` and `where=[filter]` | [examples/factory_production.py](../examples/factory_production.py) |
| Traveling salesman | Derived scalar bounds, MTZ subtour elimination, degree constraints, walrus aliasing | [examples/traveling_salesman.py](../examples/traveling_salesman.py) |
| Machine maintenance | Conflict-graph mutual exclusion via Conflict concept + dual `.ref()` | [examples/machine_maintenance.py](../examples/machine_maintenance.py) |
| Order fulfillment | Fixed-charge facility location: FCUsage tracking concept + linking constraint | [examples/order_fulfillment.py](../examples/order_fulfillment.py) |
| Hospital staffing | Overtime hinge variable + skill-filtered aggregation + unmet demand penalty | [examples/hospital_staffing.py](../examples/hospital_staffing.py) |
| Sprint scheduling | Epoch filtering pipeline + skill-constrained assignment domain + weighted completion | [examples/sprint_scheduling.py](../examples/sprint_scheduling.py) |
| Demand planning (temporal) | Multi-period flow conservation with time-indexed multiarity variables + model.union() objective | [examples/demand_planning_temporal.py](../examples/demand_planning_temporal.py) |
| Vehicle scheduling | Fixed-charge vehicle usage with big-M linking to binary assignments | [examples/vehicle_scheduling.py](../examples/vehicle_scheduling.py) |
| Grid interconnection | Capacity expansion — two coupled binary decision sets sharing a resource constraint + budget knapsack | [examples/grid_interconnection.py](../examples/grid_interconnection.py) |
| Ad spend allocation | Semi-continuous variables via binary activation indicator + per-campaign and global budget | [examples/ad_spend_allocation.py](../examples/ad_spend_allocation.py) |
| N-queens (Integer) | Pairwise inequality constraints with `.ref()`, `Problem(model, Integer)`, MiniZinc | [examples/n_queens.py](../examples/n_queens.py) |
| Sudoku (Integer) | `all_different` global constraint with `.per()` grouping, standalone property variables | [examples/sudoku.py](../examples/sudoku.py) |
