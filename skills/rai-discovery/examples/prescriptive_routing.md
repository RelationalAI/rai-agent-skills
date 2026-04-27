# Prescriptive Routing Examples

Discovery-to-routing walkthroughs for prescriptive reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "How should we re-allocate components if an entity goes offline?"

### Ontology signals
- `Activity` concept with `source_node`, `target_node`, `cost_per_unit`, `capacity_per_period` → flow network with costs and capacity
- `Dependency` with `input_resource`, `output_resource`, `input_quantity` → component requirements per output
- `Demand` with `quantity` per `entity_id` and `resource_id` → forcing requirement (demand must be met)
- Binary scenario: exclude one entity entirely → contingency planning

### Reasoner classification: Prescriptive (network flow LP)
- "How should we re-allocate" → optimization decision
- Network structure (entity → intermediary → hub) → network flow type
- Capacity constraints + cost minimization → linear program
- NOT graph — question is "what should we do?", not "what's the structure?"

### Implementation hint
```json
{"problem_type": "network_flow",
 "decision_scope": "ComponentFlow through Activity — quantity to move per activity route",
 "forcing_requirement": "Dependency component demand satisfaction per (Resource, Entity)",
 "objective_property": "total_cost (flow * cost_per_unit) + unmet_penalty",
 "scenario_parameter": "excluded_entity (binary: force flow=0 for that entity's activities)"}
```

### Modeling needs (→ rai-ontology-design, rai-prescriptive-problem-formulation)
- Decision concept: `ComponentFlow` defined on `Activity` with `quantity` variable
- Slack concept: `UnmetComponent` per (Resource, Entity) for infeasibility handling
- Variables: `ComponentFlow.quantity` (continuous, 0 to capacity), `UnmetComponent.quantity` (continuous, >= 0)
- Constraints: per (Resource, Entity): sum(inflow) + unmet >= Dependency requirement
- Constraint: if excluded entity, force `ComponentFlow.quantity == 0` for that entity's activities

### Reasoner handoff (→ prescriptive workflow)
- Define variables → define constraints → define objective → validate formulation → solve
- Solver: HiGHS (LP/MIP)
- Scenario comparison: baseline (all entities) vs offline (excluded entity)

---

## "Minimize total flow cost while meeting demand given entity reliability"

### Ontology signals
- Same `Activity` network as the previous example with costs and capacity
- `Demand` concept with quantity per target and resource → forcing requirement
- `Entity.reliability_score` → entity quality metric
- `RiskPrediction.predicted_risk_prob` → predicted reliability from predictive stage

### Reasoner classification: Prescriptive (network flow LP with predictive input)
- "Minimize costs" + "meeting demand" + "given reliability" → constrained optimization
- Reliability as a parameter/constraint → uses predictive output (cumulative discovery)
- Multiple scenario variants: pure cost, reliability-weighted, minimum reliability threshold

### Implementation hint
```json
{"problem_type": "network_flow",
 "decision_scope": "AllocationFlow through Activity — quantity to move per route",
 "forcing_requirement": "demand satisfaction per Resource (sum of inflow + unmet >= demand)",
 "objective_property": "flow_cost + unmet_penalty + reliability_penalty",
 "scenario_parameters": ["reliability_weight (soft penalty multiplier)",
                         "min_reliability (hard threshold, exclude entities below)"]}
```

### Modeling needs (→ rai-ontology-design, rai-prescriptive-problem-formulation)
- Decision concept: `AllocationFlow` defined on `Activity` with `quantity` variable
- Slack concept: `UnmetDemand` per Resource
- Reliability integration: `Entity.reliability_score` as constraint parameter
- Three scenario framings:
  1. Pure cost: minimize `sum(flow * cost_per_unit) + unmet_penalty`
  2. Reliability-weighted: add `reliability_weight * sum(flow * (1 - reliability_score))`
  3. Hard threshold: force `AllocationFlow.quantity == 0` where `source.reliability_score < min_reliability`

### Reasoner handoff (→ prescriptive workflow)
- Same prescriptive workflow as the previous example
- `configure_scenarios` to set up reliability parameter sweeps before solving
- Output: cost-vs-reliability tradeoff frontier across scenarios

### Cumulative discovery note
This problem uses predictive output (RiskPrediction) as a prescriptive parameter — a key predictive → prescriptive chain. Discovery should suggest: "Given predicted entity risks (from the prediction stage), optimize allocation to minimize cost while maintaining reliability."
