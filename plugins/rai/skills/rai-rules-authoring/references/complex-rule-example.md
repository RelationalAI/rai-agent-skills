# Complex Multi-Entity Rule Example

Real-world example of a 5-entity subtype rule with OR branches and layered dependencies.
Domain: food truck fleet operations.

---

## CannibalizationRiskHotspot (5-entity subtype)

Identifies locations where two food trucks compete for the same customers, the location
has high foot traffic, and at least one truck is wasting inventory.

```python
# Subtype of LocationCooccurrence where:
#   1. High cannibalization score (boolean flag)
#   2. Location is a HighTrafficLocation (existing subtype)
#   3. At least one of the two trucks has high inventory waste
CannibalizationRiskHotspot = model.Concept(
    "CannibalizationRiskHotspot", extends=[LocationCooccurrence]
)

# Path 1: truck_a has high waste (OR branch 1)
model.define(CannibalizationRiskHotspot(LocationCooccurrence)).where(
    LocationCooccurrence.is_high_cannibalization(),   # boolean flag filter
    LocationCooccurrence.at_location(Location),        # join to Location
    HighTrafficLocation(Location),                     # existing subtype check
    LocationCooccurrence.truck_a(FoodTruck),           # join to FoodTruck via truck_a
    FoodTruck.has_inventory_log(InventoryLog),         # join to InventoryLog
    InventoryLog.is_high_waste(),                      # boolean flag filter
)

# Path 2: truck_b has high waste (OR branch 2)
model.define(CannibalizationRiskHotspot(LocationCooccurrence)).where(
    LocationCooccurrence.is_high_cannibalization(),
    LocationCooccurrence.at_location(Location),
    HighTrafficLocation(Location),
    LocationCooccurrence.truck_b(FoodTruck),           # different FK path
    FoodTruck.has_inventory_log(InventoryLog),
    InventoryLog.is_high_waste(),
)
```

**Patterns demonstrated:**
- **OR conditions** → separate `model.define()` calls (never use `|` operator in subtype `where()`)
- **Existential joins** → relationship traversal in `where()` acts as "there exists"
- **Mixing subtypes** → reference existing subtypes (e.g., `HighTrafficLocation(Location)`) as conditions
- **Boolean flags as filters** → use `Entity.is_flag()` in `where()`, not in `select()`
- **Multi-hop traversal** → chain relationships: `Entity_A → Entity_B → Entity_C` via multiple `where()` conditions

---

## Layered Rule Dependencies (DailyDeployment)

Building a complex subtype by layering computed property → boolean flag → subtype.

```python
# Layer 1: Computed property
DailyDeployment.demand_fulfillment_ratio = model.Property(...)
model.define(DailyDeployment.demand_fulfillment_ratio(
    DailyDeployment.actual_orders_count / DailyDeployment.predicted_demand_score
)).where(DailyDeployment.predicted_demand_score > 0)

# Layer 2: Boolean flag (OR via multiple define calls)
DailyDeployment.is_bad_weather = model.Relationship(...)
model.define(DailyDeployment.is_bad_weather()).where(DailyDeployment.weather_condition == "rainy")
model.define(DailyDeployment.is_bad_weather()).where(DailyDeployment.weather_condition == "stormy")
model.define(DailyDeployment.is_bad_weather()).where(DailyDeployment.weather_condition == "cold")

# Layer 3: Subtype combining layers 1 + 2
BadWeatherMoneyLoser = model.Concept("BadWeatherMoneyLoser", extends=[DailyDeployment])
model.define(BadWeatherMoneyLoser(DailyDeployment)).where(
    DailyDeployment.is_bad_weather(),
    DailyDeployment.demand_fulfillment_ratio < 5.0,
)
```
