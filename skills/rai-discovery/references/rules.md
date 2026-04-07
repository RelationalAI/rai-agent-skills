<!-- TOC -->
- [Rules Question Types](#rules-question-types)
- [Rules Implementation Hints](#rules-implementation-hints)
- [When Rules vs Other Reasoners](#when-rules-vs-other-reasoners)
- [Implementation Approach](#implementation-approach)
- [Rule Pattern Signals](#rule-pattern-signals)
- [Rules-Specific Feasibility Criteria](#rules-specific-feasibility-criteria)
- [Variety Heuristics for Rules](#variety-heuristics-for-rules)
- [Cross-Reasoner Chains Involving Rules](#cross-reasoner-chains-involving-rules)
- [Execution Skill Handoff](#execution-skill-handoff)
<!-- /TOC -->

## Rules Question Types

Rules reasoning enforces business logic, validates compliance, and derives classifications from known facts.

Business rules are expressed as **derived ontology properties and concepts** — e.g., `Business.is_high_value_customer` defined as `TYPE='BUYER' AND value_tier='HIGH'`. Complex conditional logic, threshold checks, and derived classifications are modeled directly in PyRel as ontology-layer definitions.

| Type | Question Pattern | Ontology Signal |
|------|-----------------|-----------------|
| **Validation** | "Is this compliant / valid / within policy?" | Concepts with threshold/limit properties, regulatory categories, approval status fields |
| **Classification** | "What category based on business rules?" | Hierarchical categories, conditional membership criteria, tier/grade definitions |
| **Derivation** | "What follows from these facts?" | Transitive relationships (A manages B, B manages C → A indirectly manages C), inheritance patterns |
| **Alerting** | "What violates policy / needs attention?" | Concepts with limit/threshold properties, SLA definitions, overdue/expired status fields |
| **Reconciliation** | "Do these two sources agree?" | Multiple concepts representing overlapping data (orders vs invoices, planned vs actual) |

---

## Rules Implementation Hints

For each rules suggestion, provide an implementation hint with these fields:

```json
{
  "rule_type": "validation|classification|derivation|alerting|reconciliation",
  "source_concept": "Order",
  "condition_properties": ["Order.amount", "Customer.credit_limit"],
  "join_path": "Order.customer(Customer)",
  "threshold": "amount > credit_limit",
  "output_type": "relationship|property",
  "output_property": "Order.exceeds_credit",
  "downstream_use": "prescriptive constraint filter|predictive feature|rule chain input|standalone query"
}
```

| Field | Description | Required |
|-------|-------------|----------|
| `rule_type` | Which of the 5 rule types (validation, classification, derivation, alerting, reconciliation) | Yes |
| `source_concept` | Primary concept the rule applies to | Yes |
| `condition_properties` | Properties evaluated in the rule condition | Yes |
| `join_path` | Relationship traversal needed to reach cross-entity properties (e.g., `Order.customer(Customer)`) | If cross-entity |
| `threshold` | The business rule logic/boundary | Yes |
| `output_type` | `relationship` for boolean flags, `property` for computed values | Yes |
| `output_property` | Name of the derived property/relationship the rule creates | Yes |
| `downstream_use` | How the rule output will be consumed | Recommended |

---

## When Rules vs Other Reasoners

- Deterministic logic over known facts → **rules** (derived ontology properties)
- "Predict whether it will violate" (uncertain outcome) → **predictive** (or predictive → rules chain)
- "Optimize to minimize violations" (decision-making) → **prescriptive**
- "Find all connected violations in the network" → **graph** (or graph → rules chain)
- Simple threshold classification (e.g., "high-value if spend > $10K") → derived property in ontology, not a separate reasoner

---

## Implementation Approach

After selecting a rules suggestion, use `rai-rules-authoring` for the full authoring workflow (NL parsing → rule type classification → ontology mapping → PyRel translation → validation). The implementation hint fields above map directly to the authoring workflow's inputs.

---

## Rule Pattern Signals

What ontology patterns indicate rules reasoning potential:

- **Threshold/limit properties**: max_capacity, min_balance, credit_limit, sla_hours — natural rule boundaries
- **Status/category fields**: approval_status, risk_tier, compliance_grade — rule-driven classifications
- **Hierarchical concepts**: Category → Subcategory → Item with inheritance of rules down the hierarchy
- **Cross-entity comparisons**: Order.amount vs Customer.credit_limit, Actual.hours vs Plan.hours
- **Temporal compliance**: Due dates, SLA deadlines, review periods — time-based rule triggers

**Minimum viable ontology for rules:** At least one concept with properties that define a business rule boundary (threshold, category, status) and entities to evaluate against it.

---

## Rules-Specific Feasibility Criteria

Beyond the standard READY / MODEL_GAP / DATA_GAP classification, rules suggestions require additional checks:

| Criterion | Check | Impact |
|-----------|-------|--------|
| **Condition properties populated** | Are the properties used in the rule condition non-null for enough entities? | If most entities have null values for the condition property, the rule will match few/no entities |
| **Threshold deterministic vs user-input** | Can the threshold be derived from data, or does it require user specification? | Data-driven thresholds (e.g., `> Entity.limit`) are READY; hardcoded thresholds (e.g., `> 10000`) need parameter confirmation |
| **Join path exists** | For cross-entity rules: does the relationship traversal path exist in the model? | Missing join path = MODEL_GAP (need to add relationship) |
| **Output type feasibility** | Does the rule produce a boolean (Relationship) or value (Property)? | Mismatching output type causes `FDError` or silent data loss |
| **Classification exhaustiveness** | For classification rules: do conditions cover all entities? | Non-exhaustive classification leaves entities unclassified — acceptable if intentional, flag if not |

---

## Variety Heuristics for Rules

When suggesting rules, explore different aspects of what the data can validate:

- **Different rule types** — don't suggest only validation; include classification, derivation, alerting, and reconciliation where the data supports it
- **Different concepts** — spread rules across multiple entities rather than clustering on one concept
- **Cross-entity rules** — include at least one rule that spans multiple concepts via relationship joins (not just single-concept threshold checks)
- **Different downstream uses** — suggest rules that feed different consumers: some as standalone queries, some as constraint filters for optimization, some as chain inputs for other rules

---

## Cross-Reasoner Chains Involving Rules

Rules participate in chains both as producers (rule output feeds another reasoner) and consumers (another reasoner's output feeds a rule condition).

| Chain | Direction | Example |
|-------|-----------|---------|
| **Rules → Prescriptive** | Rule output constrains optimization | Compliance flag filters which entities the solver can assign; derived LTV weights the objective |
| **Rules → Predictive** | Rule classification becomes a predictive feature | `risk_tier` used as feature in churn prediction model |
| **Graph → Rules** | Graph metric feeds rule threshold | Centrality score below threshold flags structurally isolated nodes |
| **Predictive → Rules** | Predicted score feeds rule condition | `predicted_risk > 0.8` triggers alert rule |
| **Rules → Rules** | Layered derivations | Classification rule → alerting rule based on classification + additional condition |
| **Graph → Rules → Prescriptive** | Three-stage chain | Centrality → flag at-risk nodes → optimize allocation avoiding at-risk nodes |

For each chained suggestion, the implementation hint should include `downstream_use` indicating what consumes the rule output.

---

## Execution Skill Handoff

After selecting a rules suggestion from discovery, the execution workflow uses the `rai-rules-authoring` skill for NL-to-PyRel translation, rule type classification, pattern selection, and validation.

**Question discovery** (`rai-discovery` + this reference file) answers: "What rules can this data support?"
**Execution** (`rai-rules-authoring`) answers: "How do I translate the rule to PyRel and validate it?"

The implementation hint from discovery provides the starting point for execution:
- `rule_type` → maps to `rai-rules-authoring` canonical pattern for that type
- `source_concept` + `condition_properties` → maps to `rai-rules-authoring` ontology mapping step
- `output_type` + `output_property` → maps to `rai-rules-authoring` output declaration pattern
- `join_path` → maps to `rai-rules-authoring` cross-entity rule design
