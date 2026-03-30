---
name: rai-rules-authoring
description: Converts natural language business rules into PyRel derived properties. Covers validation, classification, derivation, alerting, and reconciliation patterns with rule chaining. Use for business logic, flags, subtypes, segmentation, or compliance rules.
---

# Rules Authoring
<!-- v1-SENSITIVE -->

<!-- TOC -->
- [Summary](#summary)
- [Quick Reference](#quick-reference)
- [Rule Authoring Workflow](#rule-authoring-workflow)
- [NL-to-PyRel Translation Patterns](#nl-to-pyrel-translation-patterns)
- [Rule Design Principles](#rule-design-principles)
- [Complex Multi-Entity Rule Design](#complex-multi-entity-rule-design)
- [Rule Chaining](#rule-chaining)
- [Cross-Reasoner Integration](#cross-reasoner-integration)
- [Handling Missing Data in Rules](#handling-missing-data-in-rules)
- [Common Pitfalls (Rules-Specific)](#common-pitfalls-rules-specific)
- [Examples](#examples)
- [Reference Files](#reference-files)
<!-- /TOC -->

## Summary

**What:** Business rule authoring — translating natural language rules into PyRel derived
ontology properties and concepts. Covers validation, classification, derivation, alerting,
and reconciliation rule types.

**When to use:**
- Translating a business rule from natural language to PyRel (e.g., "flag high-value customers")
- Classifying which rule pattern to use (validation, classification, derivation, alerting, reconciliation)
- Writing `define()` + `where()` expressions that encode business logic
- Reviewing or debugging an existing rule definition
- Chaining rules with other reasoner outputs (graph metrics, predictions)
- Testing that a rule produces correct results on known data

**When NOT to use:**
- Discovering what rules a model can support (reasoner classification, feasibility) — see `rai-problem-discovery`
- PyRel syntax reference (imports, types, property patterns) — see `rai-pyrel-coding`
- Ontology modeling decisions (concept vs property, data mapping) — see `rai-ontology-design`
- Optimization formulation (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Query syntax (select, aggregation, filtering) — see `rai-querying`

**Overview (process steps):**
1. Parse the natural language rule to identify intent, entities, conditions, and output
2. Classify the rule type (validation, classification, derivation, alerting, reconciliation)
3. Map entities and conditions to existing ontology concepts and properties
4. Translate to PyRel using the appropriate `define()` + `where()` pattern
5. Validate the rule against known test cases
6. Connect to downstream consumers (queries, other rules, or reasoner chains)

---

## Quick Reference

```python
# Imports (rule authoring typically needs)
from relationalai.semantics import Model, Float, Integer, String
from relationalai.semantics.std import aggregates, math, strings
from relationalai.semantics.std.datetime import datetime
from relationalai.semantics.std import numbers

model = Model("my_model")
```

| Rule Type | Output Type | Canonical Pattern |
|-----------|------------|-------------------|
| **Validation** | `Relationship` (boolean) | `model.where(cond).define(Entity.is_valid())` |
| **Classification** | `Relationship` to segment concept | `model.where(range).define(Entity.value_segment(SegmentSubtype))` |
| **Derivation** | `Property` (computed value) | `model.define(Entity.total(aggregates.sum(Child.val).per(Entity)))` |
| **Alerting** | `Relationship` (boolean + optional severity) | `model.where(model.not_(Entity.resolved), elapsed > limit).define(Entity.is_breach())` |
| **Reconciliation** | `Property` (delta) + `Relationship` (flag) | `model.define(Match.delta(A.val - B.val))` then `model.where(math.abs(Match.delta) > tol).define(Match.has_discrepancy())` |

**Key decision rules:**
- Boolean yes/no output → `Relationship` (validation or alerting)
- Category from fixed set → typed sub-concepts with `Relationship` (classification)
- Computed number → `Property` (derivation)
- Two-source comparison → `Property` for delta + `Relationship` for flag (reconciliation)

---

## Rule Authoring Workflow

### Step 1: Parse the Natural Language Rule

Extract four components from the NL statement:

| Component | Question | Example (NL: "Flag orders exceeding their customer's credit limit") |
|-----------|----------|----------------------------------------------------------------------|
| **Subject entity** | What concept does the rule apply to? | `Order` |
| **Condition properties** | What data fields are evaluated? | `Order.amount`, `Customer.credit_limit` |
| **Threshold / logic** | What boundary or logic is applied? | `amount > credit_limit` |
| **Output** | What does the rule produce? | Boolean flag: `Order.exceeds_credit` |

Additional extraction hints:
- "for each X" → the rule applies `.per(X)` or iterates over concept X
- "across all Y" → aggregation is needed (`sum`, `count`, `avg`)
- "if ... then ..." → condition → output mapping
- "unless" / "except" → negation with `model.not_()`

### Step 2: Classify the Rule Type

| Type | NL Signals | Output Pattern | PyRel Pattern |
|------|-----------|----------------|---------------|
| **Validation** | "is valid", "complies", "within policy", "meets requirement" | Boolean flag (`Relationship`) | `model.where(cond).define(Entity.is_valid())` |
| **Classification** | "categorize", "tier", "grade", "segment", "bucket" | Subtype or Relationship to segment concept | `model.where(range).define(SegmentSubtype(Entity))` |
| **Derivation** | "total", "calculated from", "sum of", "derived", "equals" | Computed value (`Property`) | `model.define(Entity.total(expression))` |
| **Alerting** | "flag", "alert", "overdue", "exceeds", "breach", "violation" | Boolean + optional severity | `model.where(violation).define(Entity.is_flagged())` |
| **Reconciliation** | "match", "agree", "discrepancy", "difference between" | Delta value (`Property`) | `model.define(Entity.delta(A.val - B.val))` |

**Disambiguation:** If the NL rule produces a boolean yes/no answer, it is validation or alerting. If it assigns
a category from a fixed set, it is classification. If it computes a numeric value, it is derivation.

### Step 3: Map to Ontology and Explore Data

Before writing code, verify each referenced element exists in the model AND explore the actual data to inform threshold values:

| Check | How to verify | If missing |
|-------|--------------|------------|
| Concept exists | `model.concepts` or check ontology definitions | Define the concept or flag as model gap |
| Property exists on concept | Check concept's property declarations | Add property or enrich model |
| Relationship path exists | Trace join from subject to related concept | Define relationship or denormalize needed property |
| Data types match | Compare property types (`Integer`, `Float`, `String`, `Date`) | Cast with `numbers.integer()`, `floats.float()`, `date.fromisoformat()` |
| Data distribution | Query `min`, `max`, `avg` of condition properties | Set thresholds informed by actual data, not assumptions |

**Data exploration is mandatory for threshold rules.** See [Complex Multi-Entity Rule Design](#data-exploration-before-threshold-selection) for the pattern. Common scale mismatches: scores 0-10 vs 0-100, ratios > 1.0, percentages as 0-1 vs 0-100.

### Step 4: Translate to PyRel

Use the canonical pattern for each rule type. See
[pyrel-rule-patterns.md](references/pyrel-rule-patterns.md) for full examples and variants.

**Validation** — boolean flag via unary `Relationship`:

```python
Entity.is_valid = model.Relationship(f"{Entity} is valid")
model.where(condition).define(Entity.is_valid())
```

**Classification** — typed sub-concepts with mutually exclusive conditions:

Use typed sub-concepts (not string Properties) for derived classifications. This provides type
safety, extensibility, and efficient filtering. See `rai-ontology-design`
[categorization-and-advanced.md](../rai-ontology-design/references/categorization-and-advanced.md)
for full guidance on enumeration vs. subtyping.

```python
# Define segment hierarchy
CustomerValueSegment = model.Concept("CustomerValueSegment")
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentGold = model.Concept("ValueSegmentGold", extends=[CustomerValueSegment])
ValueSegmentStandard = model.Concept("ValueSegmentStandard", extends=[CustomerValueSegment])

# Create named instances
SegmentName = model.Concept("SegmentName", extends=[String])
model.define(ValueSegmentVIP.new(name=SegmentName("VIP")))
model.define(ValueSegmentGold.new(name=SegmentName("Gold")))
model.define(ValueSegmentStandard.new(name=SegmentName("Standard")))

# Assign based on score thresholds (mutually exclusive conditions)
Customer.value_segment = model.Relationship(f"{Customer} has value segment {CustomerValueSegment}")
model.where(Customer.lifetime_spend >= 50000).define(Customer.value_segment(ValueSegmentVIP))
model.where(
    Customer.lifetime_spend >= 10000,
    Customer.lifetime_spend < 50000,
).define(Customer.value_segment(ValueSegmentGold))
model.where(Customer.lifetime_spend < 10000).define(Customer.value_segment(ValueSegmentStandard))
```

**Derivation** — computed value via `Property`:

```python
Entity.total = model.Property(f"{Entity} has {Float:total}")
total = aggregates.sum(Child.amount).per(Entity).where(Child.parent(Entity))
model.define(Entity.total(total))
```

**Alerting** — violation flag, often time-based:

```python
Entity.is_breach = model.Relationship(f"{Entity} is breach")
model.where(violation_condition).define(Entity.is_breach())
```

**Reconciliation** — delta with tolerance:

```python
Match.delta = model.Property(f"{Match} has {Float:delta}")
model.define(Match.delta(Source_A.amount - Source_B.amount))
Match.has_discrepancy = model.Relationship(f"{Match} has discrepancy")
model.where(math.abs(Match.delta) > tolerance).define(Match.has_discrepancy())
```

### Step 5: Validate

Run these checks on every rule before considering it complete:

| Check | What to verify | Failure signal |
|-------|---------------|----------------|
| Output type correct | `Relationship` for boolean, `Property` for values | `FDError` if Property gets multiple values |
| Conditions exhaustive | Classification covers all entities (if intended) | Entities with no assigned value |
| Conditions exclusive | No entity matches two classification branches | `FDError` on Property |
| Join paths valid | `.where()` relationships traverse existing paths | Zero results despite matching data |
| Type alignment | Condition compares same types | Zero matches from silent type mismatch |
| Aggregation scoped | `.per()` present when aggregating across entities | Single global result instead of per-entity |

#### Exhaustiveness validation

For classification rules that should cover every entity, run an exhaustiveness check to find unclassified entities:

```python
# Find entities with no assigned classification
unclassified = model.select(
    Entity.id.alias("id"),
).where(
    model.not_(Entity.classification)
).to_df()
```

If unclassified entities exist, diagnose WHY they were missed by inspecting the condition property values:

```python
model.select(
    Entity.id.alias("id"),
    (Entity.score | "MISSING").alias("score"),
).where(
    model.not_(Entity.classification)
).to_df()
```

Common causes of incomplete coverage:
- **NaN/NULL values** — entities with missing condition properties silently fail all comparisons, so no rule branch matches
- **Boundary gaps** — e.g., conditions `>= 100` and `< 50` leave the range 50-99 uncovered
- **Type mismatches** — comparing a `String` property to an `Integer` threshold silently fails (zero matches, no error)

Fix with a catch-all rule for missing values:

```python
model.where(model.not_(Entity.score)).define(Entity.classification("unknown"))
```

### Step 6: Connect to Downstream

Rules produce derived properties that downstream consumers can query or chain:

```python
# Query rule output
violations = model.where(Order.exceeds_credit()).select(
    Order.id.alias("order_id"),
    Order.amount.alias("amount"),
).to_df()

# Chain: rule output feeds another rule
model.where(
    Customer.value_segment(ValueSegmentVIP),
    Customer.open_cases > 3,
).define(Customer.needs_escalation())
```

---

## NL-to-PyRel Translation Patterns

### Condition Mapping

| NL Phrase | PyRel Translation |
|-----------|-------------------|
| "X is Y when condition" | `model.where(condition).define(X.is_Y())` |
| "X has tier based on score" | Multiple `model.where(range).define(X.tier(value))` |
| "total X across children" | `aggregates.sum(Child.x).per(Parent).where(Child.parent(Parent))` |
| "flag X where threshold exceeded" | `model.where(X.value > X.limit).define(X.is_flagged())` |
| "X and Y agree" | `model.where(math.abs(X.v - Y.v) < epsilon).define(Match.is_reconciled())` |

### Logical Operators

| NL | PyRel | Notes |
|----|-------|-------|
| "A **and** B" | `model.where(A, B)` | Multiple args in `.where()` = conjunction |
| "A **or** B" | `model.union(branch_a, branch_b)` | Separate `.where()` calls for each branch |
| "**not** A" | `model.not_(A)` | Negates full conjunction; use parentheses for clarity |
| "**at least** N" | `>= N` | |
| "**no more than** N" | `<= N` | |
| "**exactly** N" | `== N` | |

For detailed string, numeric, date, missing-data, and aggregation syntax with examples, see
`rai-pyrel-coding` and its [standard-library.md](../rai-pyrel-coding/references/standard-library.md)
and [expression-rules.md](../rai-pyrel-coding/references/expression-rules.md).

---

## Rule Design Principles

1. **Declare the output first.** Define the `Property` or `Relationship` that the rule produces before
   writing the logic. This makes the rule's shape explicit and reviewable.

2. **Use Relationship for boolean flags, Property for values.** Boolean outputs (`is_compliant`,
   `is_overdue`) are unary Relationships. Categorical or numeric outputs (`risk_tier`, `total_cost`)
   are Properties. Mixing these up causes `FDError` or silent data loss.

3. **Conditions are conjunctive by default.** Multiple arguments in `.where()` are AND. Use
   `model.union()` for OR conditions. Never mix AND and OR in a single `.where()`.

4. **Classification rules must be mutually exclusive.** When defining multiple categories, ensure
   conditions do not overlap — otherwise the Property receives multiple values for the same entity,
   causing `FDError`. Use `<` on one boundary and `>=` on the other.

5. **Decide exhaustive vs partial.** Should every entity get a classification? If yes, include a
   default/catch-all rule. If no, document which entities will have no value.

6. **Test boundary conditions.** Rules with `>=` / `<` boundaries must handle the boundary value.
   Always verify: what happens when the value is exactly at the threshold?

7. **Prefer data-driven thresholds.** Reference properties from the ontology where possible
   (`Entity.amount > Entity.credit_limit`) rather than hardcoding values (`> 10000`).

8. **One rule per derived property.** Keep all conditions that produce the same output property
   together in one place for readability and correctness verification.

---

## Complex Multi-Entity Rule Design

### Data Exploration Before Threshold Selection

**CRITICAL:** Always explore the actual data distribution before choosing threshold values for rules. Assumptions about data scales can be wrong:

```python
# Step 1: Check the actual data range BEFORE setting thresholds
stats = model.select(
    aggregates.count(Entity).alias("total"),
    aggregates.min(Entity.score).alias("min"),
    aggregates.max(Entity.score).alias("max"),
    aggregates.avg(Entity.score).alias("avg"),
).to_df()
# Example: avg_foot_traffic_score ranges 1.2–9.7 (0-10 scale), NOT 0-100!
# Using >= 80.0 would yield zero results. Use >= 7.0 instead.
```

**Common scale mismatches:**
- Scores may be 0-10 (not 0-100)
- Ratios may be > 1.0 when numerator and denominator are on different scales
- Percentages may be stored as 0-1 (not 0-100) or vice versa

### Multi-Entity Subtype Rules (Cross-Entity Joins)

Complex rules can span multiple entities via relationship traversal in `.where()`. When PyRel joins
through relationships, it acts as an **existential check** — "there exists a related entity where
this condition is true."

```python
# Subtype spanning 3 entities: flag orders where
#   1. Order is overdue (boolean flag)
#   2. Customer is high-risk (existing subtype)
#   3. Warehouse has low stock on the ordered product
RiskyOverdueOrder = model.Concept("RiskyOverdueOrder", extends=[Order])

model.define(RiskyOverdueOrder(Order)).where(
    Order.is_overdue(),                    # boolean flag filter
    Order.customer(Customer),              # join to Customer
    HighRiskCustomer(Customer),            # existing subtype check
    Order.product(Product),                # join to Product
    Product.stocked_at(Warehouse),         # join to Warehouse
    Warehouse.stock_level < 10,            # threshold on related entity
)
```

**Key patterns in complex rules:**
- **OR conditions** → separate `model.define()` calls (never use `|` operator in subtype `where()`)
- **Existential joins** → relationship traversal in `where()` acts as "there exists"
- **Mixing subtypes** → reference existing subtypes (e.g., `HighRiskCustomer(Customer)`) as conditions
- **Boolean flags as filters** → use `Entity.is_flag()` in `where()`, not in `select()`
- **Multi-hop traversal** → chain relationships: `Entity_A → Entity_B → Entity_C` via multiple `where()` conditions

For a real-world 5-entity example with OR branches, see
[complex-rule-example.md](references/complex-rule-example.md).

### Rule Dependency Building Blocks

Build complex rules by layering simpler components:

```python
# Layer 1: Computed property
Order.fulfillment_ratio = model.Property(...)
model.define(Order.fulfillment_ratio(
    Order.shipped_qty / Order.ordered_qty
)).where(Order.ordered_qty > 0)

# Layer 2: Boolean flag (OR via multiple define calls)
Order.is_delayed = model.Relationship(...)
model.define(Order.is_delayed()).where(Order.status == "backordered")
model.define(Order.is_delayed()).where(Order.status == "on_hold")

# Layer 3: Subtype combining layers 1 + 2
CriticallyDelayedOrder = model.Concept("CriticallyDelayedOrder", extends=[Order])
model.define(CriticallyDelayedOrder(Order)).where(
    Order.is_delayed(),
    Order.fulfillment_ratio < 0.5,
)
```

---

## Rule Chaining

### Rule-to-Rule Chaining

Rules can consume other rules' output. The derived property from Rule A becomes a condition in Rule B.

```python
# Rule A: classify risk tier using subtypes
RiskTier = model.Concept("RiskTier")
HighRisk = model.Concept("HighRisk", extends=[RiskTier])
MediumRisk = model.Concept("MediumRisk", extends=[RiskTier])
LowRisk = model.Concept("LowRisk", extends=[RiskTier])

RiskTierName = model.Concept("RiskTierName", extends=[String])
model.define(HighRisk.new(name=RiskTierName("high")))
model.define(MediumRisk.new(name=RiskTierName("medium")))
model.define(LowRisk.new(name=RiskTierName("low")))

Customer.risk_tier = model.Relationship(f"{Customer} has risk tier {RiskTier}")
model.where(Customer.score < 40).define(Customer.risk_tier(HighRisk))
model.where(Customer.score >= 40, Customer.score < 80).define(Customer.risk_tier(MediumRisk))
model.where(Customer.score >= 80).define(Customer.risk_tier(LowRisk))

# Rule B: flag for review based on Rule A's output + additional condition
Customer.needs_review = model.Relationship(f"{Customer} needs review")
model.where(
    Customer.risk_tier(HighRisk),
    Customer.open_orders > 5,
).define(Customer.needs_review())
```

**Ordering guarantee:** PyRel definitions are declarative. The runtime resolves dependencies
automatically. If Rule B references Rule A's output, the engine evaluates A before B. No explicit
ordering is needed in code.

### Cross-Reasoner Chaining

| Chain | How rules participate | Example |
|-------|----------------------|---------|
| Rules → Prescriptive | Rule output constrains optimization | Compliance flag filters which entities the solver can assign |
| Predictive → Rules | Predicted score feeds rule threshold | `predicted_risk > 0.8` triggers alert rule |
| Graph → Rules | Graph metric feeds rule condition | Centrality score below threshold flags isolated nodes |
| Rules → Predictive | Rule classification becomes a feature | `risk_tier` used as feature in churn prediction |

---

## Cross-Reasoner Integration

Rule outputs (boolean flags, derived values, classifications) feed other reasoners as inputs. The key patterns:

### Rules → Prescriptive

```python
# Boolean flag as constraint filter
Order.is_compliant = model.Relationship(f"{Order} is compliant")
model.where(Order.customer(Customer), Order.amount <= Customer.credit_limit).define(Order.is_compliant())

# Decision variable scoped to compliant orders only
Order.x_assign = model.Property(f"{Order} has {Float:x_assign}")

# from relationalai.semantics.reasoners.prescriptive import Problem
p = Problem(model, Float)
p.solve_for(Order.x_assign, type="bin", where=[Order.is_compliant()])

# Derived value as objective weight
Customer.ltv = model.Property(f"{Customer} has {Float:ltv}")
model.define(Customer.ltv(aggregates.sum(Order.amount).per(Customer).where(Order.customer(Customer))))
p.maximize(aggregates.sum(Order.x_assign * Customer.ltv).where(Order.customer(Customer)))
```

### Graph → Rules

Graph metrics (centrality, community, component) become rule conditions. Always explore the data distribution before setting thresholds (see [Data Exploration Before Threshold Selection](#data-exploration-before-threshold-selection)).

```python
# Graph produced Site.centrality_score (see rai-graph-analysis)
Site.is_at_risk = model.Relationship(f"{Site} is at risk")
model.where(Site.centrality_score < 0.1).define(Site.is_at_risk())
```

### Predictive → Rules

Predicted scores feed rule thresholds:

```python
Customer.is_churn_risk = model.Relationship(f"{Customer} is churn risk")
model.where(Customer.predicted_churn_risk > 0.8).define(Customer.is_churn_risk())
```

### Rules → Rules / Rules → Predictive

- **Rules → Rules:** Layered derivations — see [Rule Chaining](#rule-chaining)
- **Rules → Predictive:** Rule-derived properties (`value_segment`, `is_compliant`, `ltv`) are automatically available as features for predictive models on the same concept

---

## Handling Missing Data in Rules

PyRel does not raise errors on missing values — conditions silently don't match. This can cause rules to skip entities unexpectedly.

```python
# Detect missing values
model.where(model.not_(Ticket.priority)).define(Ticket.needs_triage())

# Provide defaults with fallback operator
priority = Ticket.priority | "unknown"
order_count = aggregates.count(Order).per(Customer).where(Order.customer(Customer)) | 0

# Presence flags for downstream rules
Ticket.has_assignee = model.Relationship(f"{Ticket} has assignee")
model.where(Ticket.assigned_to).define(Ticket.has_assignee())
model.where(model.not_(Ticket.has_assignee), Ticket.priority == "p0").define(
    Ticket.needs_urgent_escalation()
)
```

### Aggregation in rules

```python
# Count-based classification (| 0 for zero-match groups)
order_count = aggregates.count(Order).per(Customer).where(Order.customer(Customer)) | 0
model.where(order_count >= 10).define(Customer.value_segment(ValueSegmentVIP))

# Sum-based derivation
total = aggregates.sum(Order.amount).per(Customer).where(Order.customer(Customer))
model.define(Customer.total_spend(total))
```

**Aggregation pitfalls:** Missing `.per()` = global aggregate. Zero-match groups omitted — use `| 0`. Missing property values don't contribute to `sum`/`avg`/`min`/`max`. Use `distinct()` when joins expand matches. For full guidance, see `rai-querying`.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `FDError` on classification | Overlapping conditions assign two values to same entity | Ensure mutual exclusivity: use `<` not `<=` on one boundary |
| Classification misses entities | Non-exhaustive conditions | Add a default catch-all `.where()` clause |
| Boolean flag uses `Property` | Treating boolean as value type | Use unary `Relationship` for boolean; `Property` for typed values |
| Threshold hardcoded | Not using data-driven boundaries | Reference `Entity.limit` property instead of literal value |
| Rule chaining circular dependency | Rule A depends on B which depends on A | Refactor to break cycle; rule dependencies must form a DAG |
| Rule silently skips entities | Condition property is missing for those entities | Check for missing data with `model.not_(property)`; add presence flag |
| Aggregation-based rule gives wrong counts | Missing `.per()` or wrong `.where()` scope | Validate contributing rows with `model.select()` before defining the rule |
| Classification + aggregation: `FDError` | Overlapping ranges when aggregate values land on boundary | Use strict `<` on one boundary, `>=` on the other |
| `define()` in a Python loop | Defining rules per entity in a for loop instead of declaratively | Use `model.data()` + `.where().define()`. See `rai-pyrel-coding` Common Pitfalls for before/after examples |

For general PyRel pitfalls (type mismatches, aggregation scoping, join expansion, missing data,
f-string syntax, `rai` function availability, subtype limitations, boolean negation), see
`rai-pyrel-coding` and `rai-querying`.

For subtype-specific pitfalls (OR operator crashes, aggregation chaining, dot-chain navigation,
cross-entity property access), see [pyrel-subtype-rules.md](references/pyrel-subtype-rules.md).

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Validation | Credit limit compliance with cross-entity join | [validation_rule.py](examples/validation_rule.py) |
| Classification | Multi-tier customer segmentation with mutually exclusive ranges | [classification_rule.py](examples/classification_rule.py) |
| Derivation | Order total via aggregation with property materialization | [derivation_rule.py](examples/derivation_rule.py) |
| Alerting | SLA breach detection with temporal logic and missing-data handling | [alerting_rule.py](examples/alerting_rule.py) |
| Reconciliation | Two-source delta with tolerance and severity classification | [reconciliation_rule.py](examples/reconciliation_rule.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Rule patterns | Detailed PyRel code patterns for all five rule types | [pyrel-rule-patterns.md](references/pyrel-rule-patterns.md) |
| Validation & testing | Rule validation, testing, and debugging guidance | [rule-validation-and-testing.md](references/rule-validation-and-testing.md) |
| Subtype rules | PyRel v1 subtype rules, f-string syntax, rai functions, boolean negation | [pyrel-subtype-rules.md](references/pyrel-subtype-rules.md) |
