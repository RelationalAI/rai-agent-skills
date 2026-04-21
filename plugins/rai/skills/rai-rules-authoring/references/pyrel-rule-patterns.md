<!-- TOC -->
- [Validation Rules](#validation-rules)
- [Classification Rules](#classification-rules)
- [Derivation Rules](#derivation-rules)
- [Alerting Rules](#alerting-rules)
- [Reconciliation Rules](#reconciliation-rules)
- [Subtype Patterns](#subtype-patterns)
- [Advanced Patterns](#advanced-patterns)
<!-- /TOC -->

## Validation Rules

Boolean flag on an entity indicating whether a condition holds. Output is a unary `Relationship`.

**Simple threshold:**

```python
Order.within_budget = model.Relationship(f"{Order} within budget")
model.where(Order.amount <= Order.budget).define(Order.within_budget())
```

**Cross-entity validation (join required):**

```python
Order.exceeds_credit = model.Relationship(f"{Order} exceeds credit limit")
model.where(
    Order.customer(Customer),
    Order.amount > Customer.credit_limit,
).define(Order.exceeds_credit())
```

**Text-based validation:**

```python
from relationalai.semantics.std import strings

Ticket.is_urgent = model.Relationship(f"{Ticket} is urgent")
model.where(
    strings.like(strings.lower(Ticket.subject), "%outage%"),
).define(Ticket.is_urgent())
```

**Negative validation (flag violators):**

```python
Account.missing_contact = model.Relationship(f"{Account} missing contact")
model.where(model.not_(Account.email)).define(Account.missing_contact())
```

---

## Classification Rules

Assign a category from a fixed set using typed sub-concepts. Use `Relationship` to link entities to
their segment concept. Conditions must be mutually exclusive. See `rai-ontology-design`
[categorization-and-advanced.md](../../rai-ontology-design/references/categorization-and-advanced.md)
for enumeration vs. subtyping guidance.

**Range-based tiers (typed sub-concepts):**

```python
# Define segment hierarchy
CustomerValueSegment = model.Concept("CustomerValueSegment")
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentGold = model.Concept("ValueSegmentGold", extends=[CustomerValueSegment])
ValueSegmentSilver = model.Concept("ValueSegmentSilver", extends=[CustomerValueSegment])
ValueSegmentBronze = model.Concept("ValueSegmentBronze", extends=[CustomerValueSegment])

# Create named instances
SegmentName = model.Concept("SegmentName", extends=[String])
model.define(ValueSegmentVIP.new(name=SegmentName("VIP")))
model.define(ValueSegmentGold.new(name=SegmentName("Gold")))
model.define(ValueSegmentSilver.new(name=SegmentName("Silver")))
model.define(ValueSegmentBronze.new(name=SegmentName("Bronze")))

# Assign based on score thresholds
Customer.value_segment = model.Relationship(f"{Customer} has value segment {CustomerValueSegment}")
model.where(Customer.lifetime_spend >= 50000).define(Customer.value_segment(ValueSegmentVIP))
model.where(
    Customer.lifetime_spend >= 10000,
    Customer.lifetime_spend < 50000,
).define(Customer.value_segment(ValueSegmentGold))
model.where(
    Customer.lifetime_spend >= 1000,
    Customer.lifetime_spend < 10000,
).define(Customer.value_segment(ValueSegmentSilver))
model.where(Customer.lifetime_spend < 1000).define(Customer.value_segment(ValueSegmentBronze))
```

> Boundary rule: use `>=` on lower bound and `<` on upper bound consistently to prevent overlap.

**Text-based classification:**

```python
from relationalai.semantics.std import strings

# Define category hierarchy
TicketCategory = model.Concept("TicketCategory")
BillingCategory = model.Concept("BillingCategory", extends=[TicketCategory])
SupportCategory = model.Concept("SupportCategory", extends=[TicketCategory])
FeatureCategory = model.Concept("FeatureCategory", extends=[TicketCategory])

CategoryName = model.Concept("CategoryName", extends=[String])
model.define(BillingCategory.new(name=CategoryName("billing")))
model.define(SupportCategory.new(name=CategoryName("support")))
model.define(FeatureCategory.new(name=CategoryName("feature")))

Ticket.category = model.Relationship(f"{Ticket} has category {TicketCategory}")
subject = strings.lower(strings.strip(Ticket.subject))

model.where(strings.startswith(subject, "[billing]")).define(Ticket.category(BillingCategory))
model.where(strings.startswith(subject, "[support]")).define(Ticket.category(SupportCategory))
model.where(strings.startswith(subject, "[feature]")).define(Ticket.category(FeatureCategory))
```

**Default catch-all (when exhaustive classification is needed):**

```python
# Define an unclassified segment
ValueSegmentUnclassified = model.Concept("ValueSegmentUnclassified", extends=[CustomerValueSegment])
model.define(ValueSegmentUnclassified.new(name=SegmentName("Unclassified")))

# After all specific tiers are defined, assign remaining entities
model.where(
    Customer,
    model.not_(Customer.value_segment),
).define(Customer.value_segment(ValueSegmentUnclassified))
```

---

## Derivation Rules

Compute a value from existing properties or aggregations. Output is a `Property`.

**Simple computation:**

```python
LineItem.line_total = model.Property(f"{LineItem} has {Float:line_total}")
model.define(LineItem.line_total(LineItem.quantity * LineItem.unit_price))
```

**Aggregation with `.per()` grouping:**

```python
from relationalai.semantics.std import aggregates

Order.total_value = model.Property(f"{Order} has {Float:total_value}")
total = aggregates.sum(LineItem.line_total).per(Order).where(LineItem.order(Order))
model.define(Order.total_value(total))
```

**Count with deduplication:**

```python
from relationalai.semantics import distinct

Account.unique_contacts = model.Property(f"{Account} has {Integer:unique_contacts}")
contact_count = aggregates.count(distinct(Contact)).per(Account).where(
    Contact.account(Account)
)
model.define(Account.unique_contacts(contact_count))
```

**Aggregation with fallback for missing groups:**

```python
Account.open_ticket_count = model.Property(f"{Account} has {Integer:open_ticket_count}")
open_count = aggregates.count(Ticket).per(Account).where(
    Ticket.account(Account), Ticket.status == "open"
) | 0
model.define(Account.open_ticket_count(open_count))
```

---

## Alerting Rules

Flag entities that violate a condition, often time-based. Output is a `Relationship`, optionally
paired with a severity classification `Property`.

**Temporal SLA breach:**

```python
from relationalai.semantics.std.datetime import datetime
from relationalai.semantics.std import numbers

Ticket.is_sla_breach = model.Relationship(f"{Ticket} is SLA breach")
elapsed_ms = datetime.period_milliseconds(Ticket.created_at, datetime.now())
sla_ms = numbers.integer(Ticket.sla_hours * 3600000)

model.where(
    model.not_(Ticket.resolved_at),
    elapsed_ms > sla_ms,
).define(Ticket.is_sla_breach())
```

**Severity classification on alerts:**

```python
Ticket.breach_severity = model.Property(f"{Ticket} has {String:breach_severity}")
model.where(Ticket.is_sla_breach(), Ticket.priority == "critical").define(
    Ticket.breach_severity("urgent")
)
model.where(Ticket.is_sla_breach(), Ticket.priority != "critical").define(
    Ticket.breach_severity("warning")
)
```

**Threshold alerting with data-driven limit:**

```python
Account.over_quota = model.Relationship(f"{Account} over quota")
model.where(Account.usage > Account.quota_limit).define(Account.over_quota())
```

---

## Reconciliation Rules

Compare values from two sources and flag discrepancies. Output is a delta `Property` and a
boolean `Relationship`.

```python
from relationalai.semantics.std import math

# Compute delta between two sources
Match.delta = model.Property(f"{Match} has {Float:delta}")
model.define(Match.delta(Match.source_a_amount - Match.source_b_amount))

# Flag discrepancies exceeding tolerance
Match.has_discrepancy = model.Relationship(f"{Match} has discrepancy")
model.where(math.abs(Match.delta) > 0.01).define(Match.has_discrepancy())
```

> Never use `==` for float comparison. Always use `math.abs(a - b) < epsilon` with a tolerance.

---

## Subtype Patterns

For subtype rules (`extends=[model.Parent]`), including OR operator limitations, aggregation chaining
restrictions, arithmetic property chaining, cross-entity property access, and nested computed
properties, see [pyrel-subtype-rules.md](pyrel-subtype-rules.md).

---

## Advanced Patterns

**Negation — flag absence of a property:**

```python
Customer.inactive = model.Relationship(f"{Customer} inactive")
model.where(
    Customer,
    model.not_(Customer.last_order_date),
).define(Customer.inactive())
```

**CRITICAL: Negation of boolean relationships in QUERIES:**

The `~` (bitwise NOT) operator does NOT work on boolean relationships. It raises
`bad operand type for unary ~: 'Chain'`. There is no direct negation operator for boolean
relationships in PyRel v1.

```python
# FAILS — ~ operator on boolean relationship
results = model.where(
    model.RecommendationLog.was_watched,
    ~model.RecommendationLog.was_clicked,   # TypeError: bad operand type for unary ~
).select(...).to_df()

# FAILS — not operator on boolean relationship
results = model.where(
    model.RecommendationLog.was_watched,
    not model.RecommendationLog.was_clicked,  # Python not converts to bool, wrong semantics
).select(...).to_df()
```

**Workaround — two-query pandas subtraction:**

Query the positive set and the intersection, then subtract with pandas:

```python
# Step 1: Get all entities with flag A
all_watched = model.where(
    model.RecommendationLog.was_watched,
).select(
    model.RecommendationLog.id.alias("id"),
    model.RecommendationLog.recommendation_date.alias("date"),
).to_df()

# Step 2: Get entities with BOTH flag A AND flag B
watched_and_clicked = model.where(
    model.RecommendationLog.was_watched,
    model.RecommendationLog.was_clicked,
).select(
    model.RecommendationLog.id.alias("id"),
).to_df()

# Step 3: Subtract — entities with A but NOT B
results = all_watched[~all_watched["id"].isin(watched_and_clicked["id"])]
```

> **Note:** `model.not_()` works for negating **property existence** (e.g., `model.not_(Entity.email)`)
> and **relationship applications** in `define()` contexts. But for **boolean flag relationships**
> (unary relationships like `Entity.is_active`) in query `model.where()` contexts, use the two-query
> pandas subtraction pattern above.

**Aggregation-based rule — flag groups exceeding threshold:**

```python
Account.high_volume = model.Relationship(f"{Account} high volume")
ticket_count = aggregates.count(Ticket).per(Account).where(Ticket.account(Account))
model.where(ticket_count > 100).define(Account.high_volume())
```

**Rule consuming another rule's output (chaining):**

For full rule chaining patterns (rule-to-rule and cross-reasoner), see the Rule Chaining section in [SKILL.md](../SKILL.md#rule-chaining).

```python
# Assumes Customer.risk_tier and HighRisk already defined by a classification rule
Customer.needs_review = model.Relationship(f"{Customer} needs review")
model.where(
    Customer.risk_tier(HighRisk),
    Customer.open_orders > 5,
).define(Customer.needs_review())
```

**CRITICAL: Querying subtype entities — bind to parent, access properties via parent:**

```python
# CORRECT — bind subtype to parent, access properties through parent concept
results = model.where(
    model.FlopMovie(model.Movie),
).select(
    model.Movie.title.alias("title"),
    model.Movie.profit_millions.alias("profit"),
    model.Movie.roi_pct.alias("roi_pct"),
).to_df()

# WRONG — accessing properties directly on subtype causes TyperError
results = model.where(model.FlopMovie).select(
    model.FlopMovie.title.alias("title"),  # FAILS: Type errors detected during type inference
).to_df()

# Counting subtypes — also use parent binding
results = model.select(
    rai.count(model.Movie).alias("count"),
).where(
    model.FlopMovie(model.Movie),
).to_df()
```

**Union for OR conditions:**

```python
Ticket.escalate = model.Relationship(f"{Ticket} needs escalation")
# Escalate if priority is critical OR if SLA is breached
# Multiple define() calls give OR semantics — either condition triggers the definition
model.where(Ticket.priority == "critical").define(Ticket.escalate())
model.where(Ticket.is_sla_breach()).define(Ticket.escalate())
```
