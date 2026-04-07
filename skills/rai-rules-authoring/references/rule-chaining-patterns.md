<!-- TOC -->
- [Rule-to-Rule Chaining](#rule-to-rule-chaining)
- [Cross-Reasoner Integration](#cross-reasoner-integration)
  - [Rules to Prescriptive](#rules--prescriptive)
  - [Graph to Rules](#graph--rules)
  - [Predictive to Rules](#predictive--rules)
  - [Rules to Rules / Rules to Predictive](#rules--rules--rules--predictive)
<!-- /TOC -->

## Rule-to-Rule Chaining

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

Graph metrics (centrality, community, component) become rule conditions. Always explore the data distribution before setting thresholds (see the [Data Exploration Before Threshold Selection](../SKILL.md#data-exploration-before-threshold-selection) section in SKILL.md).

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

- **Rules → Rules:** Layered derivations — see [Rule-to-Rule Chaining](#rule-to-rule-chaining)
- **Rules → Predictive:** Rule-derived properties (`value_segment`, `is_compliant`, `ltv`) are automatically available as features for predictive models on the same concept
