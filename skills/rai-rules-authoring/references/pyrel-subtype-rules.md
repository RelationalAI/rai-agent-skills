# PyRel v1 Subtype Rules Reference

> **Convention note:** This file uses `m` as the model variable and `rai.*` for base types
> (e.g., `rai.Float`, `rai.avg`). In SKILL.md, the same patterns appear as `model.*` and
> direct imports (`Float`, `aggregates.avg`). The mapping: `m` → `model`,
> `rai.Float` → `Float`, `rai.avg(...)` → `aggregates.avg(...)`.

Reference for subtype rule limitations (`extends=[model.Parent]`). For PyRel syntax, f-string format,
and available functions, see `rai-pyrel-coding`. For boolean negation patterns, see
[pyrel-rule-patterns.md — Advanced Patterns](pyrel-rule-patterns.md#advanced-patterns).

**Important:** Classification rules now use typed sub-concepts (`extends=[]`), so these subtype
limitations directly apply to classification rule authoring. See
[pyrel-rule-patterns.md — Classification Rules](pyrel-rule-patterns.md#classification-rules) for
the aligned patterns.

---

## PyRel v1 Subtype Rules (extends=[m.Parent])

### Working Pattern — Subtype with Direct or Arithmetic-Computed Properties

Subtypes defined with `extends=[m.ParentEntity]` can only use **direct properties** (loaded from
data source) or **arithmetic-computed properties** (defined using `+`, `-`, `*`, `/` on direct
properties) in their `where()` conditions.

```python
# WORKS: subtype using direct property
m.HighChurnRiskCustomer = m.Concept("HighChurnRiskCustomer", extends=[m.Customer])
m.define(m.HighChurnRiskCustomer(m.Customer)).where(
    m.Customer.churn_score >= 0.7,  # churn_score is loaded from data source
)

# WORKS: subtype using arithmetic-computed property
m.ProfitMarginPct = m.Concept("ProfitMarginPct", extends=[rai.Float])
m.MenuItem.profit_margin_pct = m.Property(f"{m.MenuItem} has profit_margin_pct {m.ProfitMarginPct}")
m.define(
    m.MenuItem.profit_margin_pct(
        m.ProfitMarginPct(((m.MenuItem.unit_price - m.MenuItem.food_cost) / m.MenuItem.unit_price) * 100)
    )
)

m.HighMarginMenuItem = m.Concept("HighMarginMenuItem", extends=[m.MenuItem])
m.define(m.HighMarginMenuItem(m.MenuItem)).where(
    m.MenuItem.profit_margin_pct >= 60.0,  # arithmetic-computed — OK
)
```

### CRITICAL LIMITATION: OR Operator (`|`) in Subtype Conditions

**Subtypes CANNOT use `|` (OR) operator** in their `where()` conditions. This causes `Query error`
and **poisons ALL queries on the parent entity** — not just the subtype.

**Note:** The `&` (AND) operator DOES work in `where()` conditions — e.g.,
`(m.Entity.score >= 1.0) & (m.Entity.score < 2.0)` is valid for range checks in classification.
Only `|` (OR) crashes.

**Impact on classification rules:** Since classification rules use typed sub-concepts, any
classification that needs OR logic in its conditions must use multiple `m.define()` calls.

```python
# FAILS — OR operator in subtype where() poisons all Customer queries
m.LoyalCustomer = m.Concept("LoyalCustomer", extends=[m.Customer])
m.define(m.LoyalCustomer(m.Customer)).where(
    m.Customer.value_segment(ValueSegmentGold) | m.Customer.value_segment(ValueSegmentPlatinum),
)

# FIX — split into multiple m.define() calls (one per OR branch)
m.LoyalCustomer = m.Concept("LoyalCustomer", extends=[m.Customer])
m.define(m.LoyalCustomer(m.Customer)).where(
    m.Customer.value_segment(ValueSegmentGold),
)
m.define(m.LoyalCustomer(m.Customer)).where(
    m.Customer.value_segment(ValueSegmentPlatinum),
)
```

### CRITICAL LIMITATION: m.define() Cannot Chain on Aggregation-Computed Properties

**`m.define()` CANNOT reference aggregation-computed properties in arithmetic** — not just subtypes,
but ANY downstream `m.define()`. This causes "Unreachable" error and **poisons the entire model**.

This includes:
- Properties defined with `rai.avg`, `rai.sum`, `rai.count` + `.per()` (direct aggregation)
- Properties computed via arithmetic on aggregation-computed inputs (transitive aggregation)
  e.g., `total_revenue / employee_count` where both are aggregation-computed
- ANY `m.define(Entity.new_prop(Entity.agg_prop * something))` where `agg_prop` is tainted

**Impact on classification rules:** You CANNOT define classification subtypes based on
aggregation-computed thresholds (e.g., "classify customers by average order value"). The
aggregation property works for queries, but subtype membership or downstream `m.define()`
chains on it will crash. Use query-time filtering with pandas instead.

Aggregation properties CAN be queried (`m.where(Entity.agg_prop > X).select(...)`) — only
further `m.define()` chains on them fail.

```python
# FAILS: subtype referencing aggregation-computed property
m.FoodTruckAvgOrders = m.Concept("FoodTruckAvgOrders", extends=[rai.Float])
m.FoodTruck.avg_daily_orders = m.Property(f"{m.FoodTruck} has avg_daily_orders {m.FoodTruckAvgOrders}")
m.define(
    m.FoodTruck.avg_daily_orders(
        m.FoodTruckAvgOrders(rai.avg(m.DailyDeployment.actual_orders_count).per(m.FoodTruck))
    )
).where(m.FoodTruck.has_deployment(m.DailyDeployment))

# THIS WILL CRASH — avg_daily_orders is aggregation-computed
m.UnderutilizedFoodTruck = m.Concept("UnderutilizedFoodTruck", extends=[m.FoodTruck])
m.define(m.UnderutilizedFoodTruck(m.FoodTruck)).where(
    m.FoodTruck.avg_daily_orders < 50,  # FAILS: Query error
)

# ALSO FAILS — inline aggregation in subtype condition
m.define(m.UnderutilizedFoodTruck(m.FoodTruck)).where(
    m.FoodTruck.has_deployment(m.DailyDeployment),
    rai.avg(m.DailyDeployment.actual_orders_count).per(m.FoodTruck) < 50,  # FAILS
)
```

**Workaround:** Keep the aggregation as a computed property (it works for queries), but filter
at query time instead of defining a subtype:

```python
# Define the property — this works
m.define(
    m.FoodTruck.avg_daily_orders(
        m.FoodTruckAvgOrders(rai.avg(m.DailyDeployment.actual_orders_count).per(m.FoodTruck))
    )
).where(m.FoodTruck.has_deployment(m.DailyDeployment))

# Query-time filter instead of subtype — this works
results = m.where(
    m.FoodTruck.avg_daily_orders < m.FoodTruck.max_daily_capacity * 0.5,
).select(
    m.FoodTruck.truck_name.alias("name"),
    m.FoodTruck.avg_daily_orders.alias("avg_orders"),
).to_df()
```

### CRITICAL LIMITATION: Cross-Entity Property Access in m.define()

Dot-chain navigation (`m.EntityA.relationship.property`) in `m.define()` arithmetic causes
"Unreachable" error. You MUST use explicit joins instead.

**Impact on classification rules:** When a classification rule computes a threshold from a
related entity's property (e.g., "classify orders by their customer's credit tier"), use
explicit `.where()` joins — not dot-chain navigation.

```python
# WRONG — dot-chain causes "Unreachable"
m.define(
    m.MovieCast.salary_pct(
        m.PctType(m.MovieCast.salary_millions / m.MovieCast.movie.box_office_revenue_millions)
    )
).where(m.MovieCast.movie.box_office_revenue_millions > 0)

# CORRECT — explicit join via .where()
m.define(
    m.MovieCast.salary_pct(
        m.PctType(m.MovieCast.salary_millions / m.Movie.box_office_revenue_millions)
    )
).where(
    m.MovieCast.movie(m.Movie),
    m.Movie.box_office_revenue_millions > 0,
)
```

**Pattern:** Access the related entity's properties directly (`m.EntityB.property`) and add the
relationship navigation in `.where()` (`m.EntityA.relationship(m.EntityB)`).

### Nested/Chained Computed Properties for Subtypes

When building complex rules (including classification rules that use typed sub-concepts), chain
arithmetic-computed properties. Each step must use only basic arithmetic on direct or
previously-defined arithmetic properties. NO aggregation anywhere in the chain.

```python
# Step 1: Compute spend_per_order (arithmetic on direct properties)
m.SpendPerOrderType = m.Concept("SpendPerOrderType", extends=[rai.Float])
m.Customer.spend_per_order = m.Property(f"{m.Customer} has spend_per_order {m.SpendPerOrderType}")
m.define(
    m.Customer.spend_per_order(
        m.SpendPerOrderType(m.Customer.lifetime_spend / m.Customer.total_orders)
    )
).where(m.Customer.total_orders > 0)

# Step 2: Compute engagement_score (arithmetic on step 1 + direct property)
m.EngagementScoreType = m.Concept("EngagementScoreType", extends=[rai.Float])
m.Customer.engagement_score = m.Property(f"{m.Customer} has engagement_score {m.EngagementScoreType}")
m.define(
    m.Customer.engagement_score(
        m.EngagementScoreType(m.Customer.spend_per_order * m.Customer.satisfaction_avg / 5)
    )
)

# Step 3: Subtype using chained arithmetic properties — WORKS
m.HighEngagementCustomer = m.Concept("HighEngagementCustomer", extends=[m.Customer])
m.define(m.HighEngagementCustomer(m.Customer)).where(
    m.Customer.engagement_score > 15,
    m.Customer.churn_score < 0.4,
)
```

> **Reminder:** Always use single braces `{m.Entity}` in f-strings — double braces `{{m.Entity}}`
> output literal text and cause `[Unknown Concept]` errors. See `rai-pyrel-coding` for full syntax.
