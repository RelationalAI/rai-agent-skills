## Sensitivity Analysis

### Implementation Patterns

Sensitivity analysis uses one of two PyRel patterns (PA selects automatically):

- **Parameter variations** (budget, demand, service levels): Scenario Concept — single solve,
  results contain scenario dimension, queryable via `model.select(Scenario.name, ...)`.
  Variables are multi-argument Properties: `Property(f"{Entity} in {Scenario} is {Float:var}")`.
  Constraints use `.per(Scenario)` for per-scenario aggregation and `Scenario.param` for
  scenario-specific values. See `rai-prescriptive-solver-management/examples/portfolio_balancing_scenarios.py`.
- **Entity exclusion** (remove a supplier, disable a facility): Loop + `where=[]` filter —
  multiple solves, results collected per iteration via `variable_values().to_df()`.
  See `rai-prescriptive-solver-management/examples/factory_production_scenarios.py`.

Both produce the same output format for stakeholders: comparison tables with business language.

### What-If Framing for Stakeholders

Sensitivity analysis answers: "What happens if our assumptions change?" Present it as scenario comparison, not mathematical derivatives.

### Which Parameters to Vary

Prioritize parameters that are:
1. **Uncertain**: Demand forecasts, cost estimates, capacity projections.
2. **Controllable**: Budget limits, headcount caps, service level targets.
3. **High-impact**: Parameters where small changes cause large solution changes.

Common parameters to test:

| Category | Parameters | Why |
|----------|-----------|-----|
| Demand | Demand volumes (+/-10%, +/-25%) | Demand forecasts are inherently uncertain |
| Budget | Total budget, per-category limits | Budget is a policy lever stakeholders control |
| Capacity | Facility capacity, workforce availability | Capacity may change with investment decisions |
| Service levels | Minimum fill rate, max delivery time | Trade-off between cost and service quality |
| Costs | Unit costs, transport costs, fixed costs | Cost estimates may change with market conditions |

### Parameter Type Taxonomy

Each scenario parameter has a type that determines its required fields and how it is varied:

**Numeric parameters** — continuous values varied over a range:
- Required fields: `name`, `description`, `default`, `min`, `max`, `step`
- Example: `budget_limit` with min=50000, max=200000, step=25000
- Use for: budget limits, capacity percentages, penalty weights, service level targets

**Entity parameters** — selecting/excluding specific entities:
- Required fields: `name`, `description`, `concept`, `property`, `default`, `allow_none`
- Example: `excluded_supplier` from concept `Supplier`, property `name`, allow_none=true
- Use for: disruption scenarios ("what if Supplier X is unavailable?"), facility selection

**Categorical parameters** — discrete named options:
- Required fields: `name`, `description`, `options` (list of value/label pairs), `default`
- Example: `shipping_mode` with options ["standard", "express", "overnight"]
- Use for: policy choices, mode selection, strategy alternatives

**Selection criteria (in priority order):**
1. Parameters with clear business meaning that stakeholders understand
2. Parameters that would show interesting tradeoffs when varied
3. Parameters referenced (explicitly or implicitly) in constraints or objective
4. Parameters where small changes are likely to cause structural solution changes

### Presenting Scenario Results

Use a comparison table with business-friendly language. Describe what changes in terms stakeholders understand -- facilities, service levels, costs -- not variable values or constraint states.

| Scenario | What changes | Impact on cost | What happens differently |
|----------|-------------|---------------|--------------------------|
| Base case | Current assumptions | $1.2M total cost | 3 distribution centers active |
| High demand | Customer demand rises 20% | $1.5M (+25%) | A 4th distribution center is needed to keep up |
| Tight budget | Available budget reduced 15% | $1.35M | Service level drops from 98% to 92% |
| Lower transport rates | Shipping costs fall 10% | $1.1M (-8%) | Distribution shifts to fewer, larger hubs |

### Identifying Critical Parameters

A parameter is **critical** if small changes cause:
- Different facilities/assets selected (structural change)
- Significant objective change (>5% per 10% parameter change)
- Constraint status flips (binding becomes non-binding or vice versa)

Report critical parameters explicitly: "The solution is most sensitive to [demand at Region X] and [capacity at Site B]. A 10% increase in either changes which facilities are used."

### Strategic vs. Operational Framing

The context determines how to present scenario results:
- **Strategic decisions** (one-time planning): Show Pareto frontiers — the full tradeoff surface between competing objectives. Let stakeholders choose their preferred operating point.
- **Operational decisions** (recurring use): Show weighted objective sensitivity — how the solution changes as weights shift. Stakeholders set weights once, then run daily.

Detect context from problem characteristics: one-time capacity planning, facility location, network design → strategic. Daily scheduling, routing, allocation → operational.
