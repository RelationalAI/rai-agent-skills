# Distinct Patterns — Code Examples

Examples of `distinct()` usage in `select()` queries.

**Multi-column distinct with joins:**

```python
from relationalai.semantics import distinct

# CORRECT: all columns inside distinct()
model.where(
    reachable(target_supplier, customer),
).select(
    distinct(
        customer.name.alias("customer_name"),
        customer.type.alias("customer_type"),
        customer.ships_to.name.alias("immediate_customer"),
    )
)
```

**Grouped aggregation with distinct — one row per group:**

```python
# CORRECT: distinct with grouped aggregation — one row per group
model.where(
    BadWeatherMoneyLoser(DailyDeployment),
).select(
    distinct(
        DailyDeployment.weather_condition.alias("weather"),
        aggs.count(DailyDeployment).per(DailyDeployment.weather_condition).alias("count"),
        aggs.avg(DailyDeployment.demand_fulfillment_ratio).per(DailyDeployment.weather_condition).alias("avg_ratio"),
    )
)
```

**Common mistakes:**

```python
# WRONG — without distinct(), returns one row per entity (duplicated aggregations)
# model.select(
#     DailyDeployment.weather_condition.alias("weather"),
#     aggs.count(DailyDeployment).per(DailyDeployment.weather_condition).alias("count"),
# ).where(...).to_df()  # Returns N rows instead of grouped rows!

# WRONG: mixing bare select with distinct field — will error
# model.select(Product.name, distinct(Product.category))  # ← DO NOT DO THIS
```

**Standalone select with distinct:**

```python
query = model.select(distinct(
    Bridge.id.alias("bridge_site_id"),
    Bridge.name.alias("bridge_site_name"),
    Bridge.region.id.alias("bridge_region"),
    Bridge.connects_region.id.alias("connects_to_region")
))
```
