# Examples Index

| Problem Type | Pattern Demonstrated | File |
|---|---|---|
| Continuous + ternary join | Continuous vars + ternary property join for per-attribute constraint | [examples/continuous_ternary_join.py](../examples/continuous_ternary_join.py) |
| Flow conservation | Flow conservation per node using two independent Edge refs | [examples/flow_conservation.py](../examples/flow_conservation.py) |
| Binary coverage (scoped) | Binary vars scoped to availability + per-entity coverage constraints | [examples/binary_coverage_scoped.py](../examples/binary_coverage_scoped.py) |
| Quadratic pairwise ref | Pairwise quadratic term via Concept.ref() + Float.ref() binding | [examples/quadratic_pairwise_ref.py](../examples/quadratic_pairwise_ref.py) |
| Multi-concept union objective | Multi-concept coordination: cross-concept conservation + binary selection + model.union() objective | [examples/multi_concept_union_objective.py](../examples/multi_concept_union_objective.py) |
| One-hot temporal recurrence | One-hot selection, stepped-value constraint, cumulative tracking with temporal recurrence | [examples/one_hot_temporal_recurrence.py](../examples/one_hot_temporal_recurrence.py) |
| Partitioned subproblem | Partitioned sub-problem solving with `populate=False` and `where=[filter]` | [examples/partitioned_subproblem.py](../examples/partitioned_subproblem.py) |
| Subtour elimination (MTZ) | Derived scalar bounds, MTZ subtour elimination, degree constraints, walrus aliasing | [examples/subtour_elimination_mtz.py](../examples/subtour_elimination_mtz.py) |
| Conflict graph exclusion | Conflict-graph mutual exclusion via Conflict concept + dual `.ref()` | [examples/conflict_graph_exclusion.py](../examples/conflict_graph_exclusion.py) |
| Fixed-charge facility | Fixed-charge facility location: tracking concept + binary linking constraint | [examples/fixed_charge_facility.py](../examples/fixed_charge_facility.py) |
| Hinge variable penalty | Hinge variable + attribute-filtered aggregation + unmet-requirement penalty | [examples/hinge_variable_penalty.py](../examples/hinge_variable_penalty.py) |
| Epoch filter assignment | Epoch filtering pipeline + attribute-constrained assignment domain + weighted completion | [examples/epoch_filter_assignment.py](../examples/epoch_filter_assignment.py) |
| Multi-period flow conservation | Multi-period flow conservation with time-indexed multiarity variables + model.union() objective | [examples/multi_period_flow_conservation.py](../examples/multi_period_flow_conservation.py) |
| Coupled binary knapsack | Two coupled binary decision sets sharing a resource constraint + budget knapsack (illustrated with capacity expansion) | [examples/coupled_binary_knapsack.py](../examples/coupled_binary_knapsack.py) |
| Semi-continuous activation | Semi-continuous variables via binary activation indicator + per-entity and global budget | [examples/semi_continuous_activation.py](../examples/semi_continuous_activation.py) |
| N-queens (Integer) | Pairwise inequality constraints with `.ref()`, `Problem(model, Integer)`, MiniZinc | [examples/n_queens.py](../examples/n_queens.py) |
| Sudoku (Integer) | `all_different` global constraint with `.per()` grouping, standalone property variables | [examples/sudoku.py](../examples/sudoku.py) |
| Epsilon constraint Pareto | Epsilon constraint loop + Scenario Concept inside, quadratic objective, anchor solves + sweep | [examples/epsilon_constraint_pareto.py](../examples/epsilon_constraint_pareto.py) |
| Chained graph → prescriptive | Graph centrality enrichment feeding prescriptive objective weight | [examples/chained_graph_prescriptive.py](../examples/chained_graph_prescriptive.py) |
| Chained graph → constraint | Graph centrality as prescriptive constraint lower bound (proportional allocation) | [examples/chained_graph_constraint.py](../examples/chained_graph_constraint.py) |
| Chained rules → prescriptive | Rules-derived boolean flags as hard constraints + cost surcharges in optimizer | [examples/chained_rules_prescriptive.py](../examples/chained_rules_prescriptive.py) |
| Union heterogeneous objective | `model.union()` combining costs from different concept scopes into single objective | [examples/union_heterogeneous_objective.py](../examples/union_heterogeneous_objective.py) |
| Slack variables penalty | Slack variables absorbing shortfall + penalty term for soft constraints | [examples/slack_variables_penalty.py](../examples/slack_variables_penalty.py) |
