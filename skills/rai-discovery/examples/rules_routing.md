# Rules Routing Examples

Discovery-to-routing walkthroughs for rules reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

Source: hero-user-journey/src/hero_user_journey/ (supply chain domain, PyRel v1)

---

## "Which suppliers are unreliable based on our business rules?"

### Ontology signals
- `Business` concept with `reliability_score` property → numeric threshold available
- `Shipment` concept with `status` and `delay_days` → aggregate metrics derivable
- Business rules exist as domain knowledge (not data-driven prediction) → rules, not predictive

### Reasoner classification: Rules (classification)
- "Based on our business rules" → explicit domain logic, not learned from data
- Threshold-based classification from known properties → deterministic rule
- NOT predictive — no training data or model fitting; thresholds come from policy
- NOT graph — no network traversal; operates on individual entity properties

### Implementation hint
```json
{"rule_type": "classification",
 "target_concept": "Business",
 "conditions": ["reliability_score < threshold", "delayed_shipment_ratio > threshold"],
 "output": "unary relationship: Business.is_unreliable()"}
```

### Modeling needs (→ rai-ontology-design)
- Computed property: `delayed_shipment_count` via `count(Shipment).where(Shipment.is_delayed()).per(Business)`
- Computed property: `total_shipment_count` via `count(Shipment).per(Business)`
- Derived ratio or direct threshold comparison on `reliability_score`
- Output: unary relationship `Business.is_unreliable()` for downstream use

### Reasoner handoff (→ rules workflow)
- `model.define(Business.is_unreliable()).where(Business.reliability_score < 0.7)`
- Or compound: `.where(Business.reliability_score < 0.7, Business.delayed_ratio > 0.3)`
- Output: boolean flag queryable via `model.where(Business.is_unreliable()).select(...)`
- Available for downstream prescriptive use (e.g., exclude unreliable suppliers from sourcing)

---

## "Flag all shipments that violate our SLA terms"

### Ontology signals
- `Shipment` concept with `delay_days`, `quantity`, `status` properties → validation inputs
- SLA terms are business rules (contractual thresholds) → deterministic, not predictive
- Multiple violation conditions possible (late delivery, quantity shortfall, damaged status)

### Reasoner classification: Rules (validation)
- "Violate SLA terms" → checking entities against known business constraints
- NOT classification — not assigning a category, but flagging violations
- NOT prescriptive — not deciding what to do about violations, just identifying them

### Implementation hint
```json
{"rule_type": "validation",
 "target_concept": "Shipment",
 "conditions": ["delay_days > sla_max_delay", "quantity < ordered_quantity * 0.95",
                 "status == 'DAMAGED'"],
 "output": "unary relationship: Shipment.violates_sla()"}
```

### Modeling needs (→ rai-ontology-design)
- Properties already on Shipment: `delay_days`, `quantity`, `status`
- Join to Order/Contract for SLA thresholds if not on Shipment directly
- Output: unary relationship `Shipment.violates_sla()` + optional `Shipment.violation_reason` property

### Reasoner handoff (→ rules workflow)
- `model.define(Shipment.violates_sla()).where(Shipment.delay_days > 5)`
- Multiple conditions via `model.union()` for OR-logic violations
- Output: flagged shipments queryable for alerting or reporting
- Pairs with prescriptive: "Given SLA violations, how should we reallocate orders?" (rules → prescriptive chain)

---

## "Derive customer value tiers from order history and account age"

### Ontology signals
- `Business` concept with `total_order_value`, `account_age_days` → segmentation inputs
- Tier definitions are business policy (not data-driven clustering) → rules, not predictive
- Output is categorical assignment → classification rule

### Reasoner classification: Rules (derivation)
- "Derive tiers" from known metrics → computed categorization
- Thresholds defined by business policy → deterministic assignment
- NOT predictive — tiers are not learned from data; they follow explicit cutoffs
- NOT graph — no network structure involved; operates on entity-level aggregates

### Implementation hint
```json
{"rule_type": "derivation",
 "target_concept": "Business",
 "conditions": ["total_order_value >= 100000 AND account_age_days >= 365 → 'PLATINUM'",
                 "total_order_value >= 50000 → 'GOLD'",
                 "total_order_value >= 10000 → 'SILVER'",
                 "otherwise → 'BRONZE'"],
 "output": "Business.value_tier property"}
```

### Modeling needs (→ rai-ontology-design)
- Computed aggregates: `total_order_value` = sum of order totals per business
- Computed property: `account_age_days` from signup date
- Enum-subconcept pattern or direct property assignment for tiers

### Reasoner handoff (→ rules workflow)
- Mutually exclusive conditions with `model.where(...).define(...)`:
  ```
  model.where(Business.total_order_value >= 100000, Business.account_age_days >= 365)
       .define(Business.value_tier(ValueTierName("PLATINUM")))
  ```
- Use enum-subconcept pattern for type-safe tier representation
- Output: `Business.value_tier` available for downstream queries and prescriptive use

### Cumulative discovery note
Customer tiers derived by rules enable prescriptive questions: "How should we allocate marketing budget across customer tiers to maximize retention?" The rules output provides the segmentation that the optimizer uses as input.
