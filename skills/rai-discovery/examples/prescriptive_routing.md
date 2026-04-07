# Prescriptive Routing Examples

Discovery-to-routing walkthroughs for prescriptive reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "How should we re-source components if a supplier goes offline?"

### Ontology signals
- `Operation` concept with `source_site`, `output_site`, `cost_per_unit`, `capacity_per_day` → flow network with costs and capacity
- `BillOfMaterials` with `input_sku`, `output_sku`, `input_quantity` → component requirements per product
- `Demand` with `quantity` per `business_id` and `sku_id` → forcing requirement (demand must be met)
- Binary scenario: exclude one supplier entirely → contingency planning

### Reasoner classification: Prescriptive (network flow LP)
- "How should we re-source" → optimization decision
- Network structure (supplier → manufacturer → warehouse) → network flow type
- Capacity constraints + cost minimization → linear program
- NOT graph — question is "what should we do?", not "what's the structure?"

### Implementation hint
```json
{"problem_type": "network_flow",
 "decision_scope": "ComponentFlow through Operation — quantity to ship per operation route",
 "forcing_requirement": "BOM component demand satisfaction per (SKU, Site)",
 "objective_property": "total_cost (flow * cost_per_unit) + unmet_penalty",
 "scenario_parameter": "excluded_supplier (binary: force flow=0 for that supplier's operations)"}
```

### Modeling needs (→ rai-ontology-design, rai-prescriptive-problem-formulation)
- Decision concept: `ComponentFlow` defined on `Operation` with `quantity` variable
- Slack concept: `UnmetComponent` per (SKU, Site) for infeasibility handling
- Variables: `ComponentFlow.quantity` (continuous, 0 to capacity), `UnmetComponent.quantity` (continuous, >= 0)
- Constraints: per (SKU, Site): sum(inflow) + unmet >= BOM requirement
- Constraint: if excluded supplier, force `ComponentFlow.quantity == 0` for that supplier's operations

### Reasoner handoff (→ prescriptive workflow)
- Define variables → define constraints → define objective → validate formulation → solve
- Solver: HiGHS (LP/MIP)
- Scenario comparison: baseline (all suppliers) vs offline (excluded supplier)

### Reference
`hero-user-journey/src/hero_user_journey/queries/q7_component_sourcing.py`

---

## "Minimize transportation costs while meeting demand given supplier reliability"

### Ontology signals
- Same `Operation` network as Q7 with costs and capacity
- `Demand` concept with quantity per customer and SKU → forcing requirement
- `Business.reliability_score` → supplier quality metric
- `DelayPrediction.predicted_delay_prob` → predicted reliability from predictive stage

### Reasoner classification: Prescriptive (network flow LP with predictive input)
- "Minimize costs" + "meeting demand" + "given reliability" → constrained optimization
- Reliability as a parameter/constraint → uses predictive output (cumulative discovery)
- Multiple scenario variants: pure cost, reliability-weighted, minimum reliability threshold

### Implementation hint
```json
{"problem_type": "network_flow",
 "decision_scope": "SupplyFlow through Operation — quantity to ship per route",
 "forcing_requirement": "demand satisfaction per SKU (sum of inflow + unmet >= demand)",
 "objective_property": "transport_cost + unmet_penalty + reliability_penalty",
 "scenario_parameters": ["reliability_weight (soft penalty multiplier)",
                         "min_reliability (hard threshold, exclude suppliers below)"]}
```

### Modeling needs (→ rai-ontology-design, rai-prescriptive-problem-formulation)
- Decision concept: `SupplyFlow` defined on `Operation` with `quantity` variable
- Slack concept: `UnmetDemand` per SKU
- Reliability integration: `Business.reliability_score` as constraint parameter
- Three scenario framings:
  1. Pure cost: minimize `sum(flow * cost_per_unit) + unmet_penalty`
  2. Reliability-weighted: add `reliability_weight * sum(flow * (1 - reliability_score))`
  3. Hard threshold: force `SupplyFlow.quantity == 0` where `source.reliability_score < min_reliability`

### Reasoner handoff (→ prescriptive workflow)
- Same prescriptive workflow as Q7
- `configure_scenarios` to set up reliability parameter sweeps before solving
- Output: cost-vs-reliability tradeoff frontier across scenarios

### Cumulative discovery note
This problem uses predictive output (DelayPrediction) as a prescriptive parameter — a key predictive → prescriptive chain. Discovery should suggest: "Given predicted supplier delays (from the prediction stage), optimize sourcing to minimize cost while maintaining reliability."

### Reference
`hero-user-journey/src/hero_user_journey/queries/q8_supplier_reliability_transport.py`
