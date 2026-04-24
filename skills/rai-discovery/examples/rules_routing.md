# Rules Routing Examples

Discovery-to-routing walkthroughs for rules reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "Which entities are unreliable based on our business rules?"

### Ontology signals
- `Entity` concept with `reliability_score` property → numeric threshold available
- `Activity` concept with `status` and `risk_value` → aggregate metrics derivable
- Business rules exist as domain knowledge (not data-driven prediction) → rules, not predictive

### Reasoner classification: Rules (classification)
- "Based on our business rules" → explicit domain logic, not learned from data
- Threshold-based classification from known properties → deterministic rule
- NOT predictive — no training data or model fitting; thresholds come from policy
- NOT graph — no network traversal; operates on individual entity properties

### Implementation hint
```json
{"rule_type": "classification",
 "target_concept": "Entity",
 "conditions": ["reliability_score < threshold", "at_risk_activity_ratio > threshold"],
 "output": "unary relationship: Entity.is_unreliable()"}
```

### Modeling needs (→ rai-ontology-design)
- Computed property: `at_risk_activity_count` via `count(Activity).where(Activity.is_at_risk()).per(Entity)`
- Computed property: `total_activity_count` via `count(Activity).per(Entity)`
- Derived ratio or direct threshold comparison on `reliability_score`
- Output: unary relationship `Entity.is_unreliable()` for downstream use

### Reasoner handoff (→ rules workflow)
- `model.define(Entity.is_unreliable()).where(Entity.reliability_score < 0.7)`
- Or compound: `.where(Entity.reliability_score < 0.7, Entity.at_risk_ratio > 0.3)`
- Output: boolean flag queryable via `model.where(Entity.is_unreliable()).select(...)`
- Available for downstream prescriptive use (e.g., exclude unreliable providers from allocation)

---

## "Flag all activities that violate our SLA terms"

### Ontology signals
- `Activity` concept with `risk_value`, `quantity`, `status` properties → validation inputs
- SLA terms are business rules (contractual thresholds) → deterministic, not predictive
- Multiple violation conditions possible (e.g., threshold breach, quantity shortfall, abnormal status)

### Reasoner classification: Rules (validation)
- "Violate SLA terms" → checking entities against known business constraints
- NOT classification — not assigning a category, but flagging violations
- NOT prescriptive — not deciding what to do about violations, just identifying them

### Implementation hint
```json
{"rule_type": "validation",
 "target_concept": "Activity",
 "conditions": ["risk_value > sla_max_risk", "quantity < requested_quantity * 0.95",
                 "status == 'ABNORMAL'"],
 "output": "unary relationship: Activity.violates_sla()"}
```

### Modeling needs (→ rai-ontology-design)
- Properties already on Activity: `risk_value`, `quantity`, `status`
- Join to Agreement/Contract for SLA thresholds if not on Activity directly
- Output: unary relationship `Activity.violates_sla()` + optional `Activity.violation_reason` property

### Reasoner handoff (→ rules workflow)
- `model.define(Activity.violates_sla()).where(Activity.risk_value > 5)`
- Multiple conditions via `model.union()` for OR-logic violations
- Output: flagged activities queryable for alerting or reporting
- Pairs with prescriptive: "Given SLA violations, how should we reallocate?" (rules → prescriptive chain)

---

## "Derive entity value tiers from activity history and account age"

### Ontology signals
- `Entity` concept with `total_activity_value`, `account_age_days` → segmentation inputs
- Tier definitions are business policy (not data-driven clustering) → rules, not predictive
- Output is categorical assignment → derivation rule (computed property from known metrics)

### Reasoner classification: Rules (derivation)
- "Derive tiers" from known metrics → computed categorization
- Thresholds defined by business policy → deterministic assignment
- NOT predictive — tiers are not learned from data; they follow explicit cutoffs
- NOT graph — no network structure involved; operates on entity-level aggregates

### Implementation hint
```json
{"rule_type": "derivation",
 "target_concept": "Entity",
 "conditions": ["total_activity_value >= 100000 AND account_age_days >= 365 → 'PLATINUM'",
                 "total_activity_value >= 50000 → 'GOLD'",
                 "total_activity_value >= 10000 → 'SILVER'",
                 "otherwise → 'BRONZE'"],
 "output": "Entity.value_tier property"}
```

### Modeling needs (→ rai-ontology-design)
- Computed aggregates: `total_activity_value` = sum of activity totals per entity
- Computed property: `account_age_days` from signup date
- Enum-subconcept pattern or direct property assignment for tiers

### Reasoner handoff (→ rules workflow)
- Mutually exclusive conditions with `model.where(...).define(...)`:
  ```
  model.where(Entity.total_activity_value >= 100000, Entity.account_age_days >= 365)
       .define(Entity.value_tier(ValueTierName("PLATINUM")))
  ```
- Use enum-subconcept pattern for type-safe tier representation
- Output: `Entity.value_tier` available for downstream queries and prescriptive use

### Cumulative discovery note
Tiers derived by rules enable prescriptive questions: "How should we allocate budget across entity tiers to maximize a target metric?" The rules output provides the segmentation that the optimizer uses as input.
