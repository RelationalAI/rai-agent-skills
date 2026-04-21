# PyRel v1 Subtype Rules Reference

Reference for subtype rule limitations (`extends=[model.Parent]`). For PyRel syntax, f-string format,
and available functions, see `rai-pyrel-coding`. For boolean negation patterns, see
[pyrel-rule-patterns.md — Advanced Patterns](pyrel-rule-patterns.md#advanced-patterns).

**Important:** Classification rules now use typed sub-concepts (`extends=[]`), so these subtype
limitations directly apply to classification rule authoring. See
[pyrel-rule-patterns.md — Classification Rules](pyrel-rule-patterns.md#classification-rules) for
the aligned patterns.

---

## PyRel v1 Subtype Rules (extends=[model.Parent])

### Working Pattern — Subtype with Direct or Arithmetic-Computed Properties

Subtypes defined with `extends=[model.ParentEntity]` can only use **direct properties** (loaded from
data source) or **arithmetic-computed properties** (defined using `+`, `-`, `*`, `/` on direct
properties) in their `where()` conditions.

```python
# WORKS: subtype using direct property
model.HighChurnRiskCustomer = model.Concept("HighChurnRiskCustomer", extends=[model.Customer])
model.define(model.HighChurnRiskCustomer(model.Customer)).where(
    model.Customer.churn_score >= 0.7,  # churn_score is loaded from data source
)

# WORKS: subtype using arithmetic-computed property
model.ProfitMarginPct = model.Concept("ProfitMarginPct", extends=[Float])
model.MenuItem.profit_margin_pct = model.Property(f"{model.MenuItem} has profit_margin_pct {model.ProfitMarginPct}")
model.define(
    model.MenuItem.profit_margin_pct(
        model.ProfitMarginPct(((model.MenuItem.unit_price - model.MenuItem.food_cost) / model.MenuItem.unit_price) * 100)
    )
)

model.HighMarginMenuItem = model.Concept("HighMarginMenuItem", extends=[model.MenuItem])
model.define(model.HighMarginMenuItem(model.MenuItem)).where(
    model.MenuItem.profit_margin_pct >= 60.0,  # arithmetic-computed — OK
)
```

### CRITICAL LIMITATION: OR Operator (`|`) in Subtype Conditions

**Subtypes CANNOT use `|` (OR) operator** in their `where()` conditions. This causes `Query error`
and **poisons ALL queries on the parent entity** — not just the subtype.

**Note:** The `&` (AND) operator DOES work in `where()` conditions — e.g.,
`(model.Entity.score >= 1.0) & (model.Entity.score < 2.0)` is valid for range checks in classification.
Only `|` (OR) crashes.

**Impact on classification rules:** Since classification rules use typed sub-concepts, any
classification that needs OR logic in its conditions must use multiple `model.define()` calls.

```python
# FAILS — OR operator in subtype where() poisons all Customer queries
model.LoyalCustomer = model.Concept("LoyalCustomer", extends=[model.Customer])
model.define(model.LoyalCustomer(model.Customer)).where(
    model.Customer.value_segment(ValueSegmentGold) | model.Customer.value_segment(ValueSegmentPlatinum),
)

# FIX — split into multiple model.define() calls (one per OR branch)
model.LoyalCustomer = model.Concept("LoyalCustomer", extends=[model.Customer])
model.define(model.LoyalCustomer(model.Customer)).where(
    model.Customer.value_segment(ValueSegmentGold),
)
model.define(model.LoyalCustomer(model.Customer)).where(
    model.Customer.value_segment(ValueSegmentPlatinum),
)
```

### CRITICAL LIMITATION: model.define() Cannot Chain on Aggregation-Computed Properties

**`model.define()` CANNOT reference aggregation-computed properties in arithmetic** — not just subtypes,
but ANY downstream `model.define()`. This causes "Unreachable" error and **poisons the entire model**.

This includes:
- Properties defined with `aggregates.avg`, `aggregates.sum`, `aggregates.count` + `.per()` (direct aggregation)
- Properties computed via arithmetic on aggregation-computed inputs (transitive aggregation)
  e.g., `total_revenue / employee_count` where both are aggregation-computed
- ANY `model.define(Entity.new_prop(Entity.agg_prop * something))` where `agg_prop` is tainted

**Impact on classification rules:** You CANNOT define classification subtypes based on
aggregation-computed thresholds (e.g., "classify customers by average order value"). The
aggregation property works for queries, but subtype membership or downstream `model.define()`
chains on it will crash. Use query-time filtering with pandas instead.

Aggregation properties CAN be queried (`model.where(Entity.agg_prop > X).select(...)`) — only
further `model.define()` chains on them fail.

```python
# FAILS: subtype referencing aggregation-computed property
model.FoodTruckAvgOrders = model.Concept("FoodTruckAvgOrders", extends=[Float])
model.FoodTruck.avg_daily_orders = model.Property(f"{model.FoodTruck} has avg_daily_orders {model.FoodTruckAvgOrders}")
model.define(
    model.FoodTruck.avg_daily_orders(
        model.FoodTruckAvgOrders(aggregates.avg(model.DailyDeployment.actual_orders_count).per(model.FoodTruck))
    )
).where(model.FoodTruck.has_deployment(model.DailyDeployment))

# THIS WILL CRASH — avg_daily_orders is aggregation-computed
model.UnderutilizedFoodTruck = model.Concept("UnderutilizedFoodTruck", extends=[model.FoodTruck])
model.define(model.UnderutilizedFoodTruck(model.FoodTruck)).where(
    model.FoodTruck.avg_daily_orders < 50,  # FAILS: Query error
)

# ALSO FAILS — inline aggregation in subtype condition
model.define(model.UnderutilizedFoodTruck(model.FoodTruck)).where(
    model.FoodTruck.has_deployment(model.DailyDeployment),
    aggregates.avg(model.DailyDeployment.actual_orders_count).per(model.FoodTruck) < 50,  # FAILS
)
```

**Workaround:** Keep the aggregation as a computed property (it works for queries), but filter
at query time instead of defining a subtype:

```python
# Define the property — this works
model.define(
    model.FoodTruck.avg_daily_orders(
        model.FoodTruckAvgOrders(aggregates.avg(model.DailyDeployment.actual_orders_count).per(model.FoodTruck))
    )
).where(model.FoodTruck.has_deployment(model.DailyDeployment))

# Query-time filter instead of subtype — this works
results = model.where(
    model.FoodTruck.avg_daily_orders < model.FoodTruck.max_daily_capacity * 0.5,
).select(
    model.FoodTruck.truck_name.alias("name"),
    model.FoodTruck.avg_daily_orders.alias("avg_orders"),
).to_df()
```

### CRITICAL LIMITATION: Cross-Entity Property Access in model.define()

Dot-chain navigation (`model.EntityA.relationship.property`) in `model.define()` arithmetic causes
"Unreachable" error. You MUST use explicit joins instead.

**Impact on classification rules:** When a classification rule computes a threshold from a
related entity's property (e.g., "classify orders by their customer's credit tier"), use
explicit `.where()` joins — not dot-chain navigation.

```python
# WRONG — dot-chain causes "Unreachable"
model.define(
    model.MovieCast.salary_pct(
        model.PctType(model.MovieCast.salary_millions / model.MovieCast.movie.box_office_revenue_millions)
    )
).where(model.MovieCast.movie.box_office_revenue_millions > 0)

# CORRECT — explicit join via .where()
model.define(
    model.MovieCast.salary_pct(
        model.PctType(model.MovieCast.salary_millions / model.Movie.box_office_revenue_millions)
    )
).where(
    model.MovieCast.movie(model.Movie),
    model.Movie.box_office_revenue_millions > 0,
)
```

**Pattern:** Access the related entity's properties directly (`model.EntityB.property`) and add the
relationship navigation in `.where()` (`model.EntityA.relationship(model.EntityB)`).

### Nested/Chained Computed Properties for Subtypes

When building complex rules (including classification rules that use typed sub-concepts), chain
arithmetic-computed properties. Each step must use only basic arithmetic on direct or
previously-defined arithmetic properties. NO aggregation anywhere in the chain.

```python
# Step 1: Compute spend_per_order (arithmetic on direct properties)
model.SpendPerOrderType = model.Concept("SpendPerOrderType", extends=[Float])
model.Customer.spend_per_order = model.Property(f"{model.Customer} has spend_per_order {model.SpendPerOrderType}")
model.define(
    model.Customer.spend_per_order(
        model.SpendPerOrderType(model.Customer.lifetime_spend / model.Customer.total_orders)
    )
).where(model.Customer.total_orders > 0)

# Step 2: Compute engagement_score (arithmetic on step 1 + direct property)
model.EngagementScoreType = model.Concept("EngagementScoreType", extends=[Float])
model.Customer.engagement_score = model.Property(f"{model.Customer} has engagement_score {model.EngagementScoreType}")
model.define(
    model.Customer.engagement_score(
        model.EngagementScoreType(model.Customer.spend_per_order * model.Customer.satisfaction_avg / 5)
    )
)

# Step 3: Subtype using chained arithmetic properties — WORKS
model.HighEngagementCustomer = model.Concept("HighEngagementCustomer", extends=[model.Customer])
model.define(model.HighEngagementCustomer(model.Customer)).where(
    model.Customer.engagement_score > 15,
    model.Customer.churn_score < 0.4,
)
```

> **Reminder:** Always use single braces `{model.Entity}` in f-strings — double braces `{{model.Entity}}`
> output literal text and cause `[Unknown Concept]` errors. See `rai-pyrel-coding` for full syntax.
