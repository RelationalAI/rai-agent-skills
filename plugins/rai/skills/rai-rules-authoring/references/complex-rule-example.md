# Complex Multi-Entity Rule Example

Pattern: 5-entity subtype rule with OR branches and layered dependencies on existing boolean flags and subtypes. The concept names below illustrate the pattern generically; the structure applies to any overlap/risk classification across entities that share a location or context.

---

## OverlapRiskHotspot (5-entity subtype)

Identifies locations where two entities overlap at the same location, the location
has high foot traffic, and at least one entity is wasting inventory.

```python
# Subtype of LocationCooccurrence where:
#   1. High overlap score (boolean flag)
#   2. Location is a HighTrafficLocation (existing subtype)
#   3. At least one of the two entities has high inventory waste
OverlapRiskHotspot = model.Concept(
    "OverlapRiskHotspot", extends=[LocationCooccurrence]
)

# Path 1: entity_a has high waste (OR branch 1)
model.define(OverlapRiskHotspot(LocationCooccurrence)).where(
    LocationCooccurrence.is_high_overlap(),            # boolean flag filter
    LocationCooccurrence.at_location(Location),        # join to Location
    HighTrafficLocation(Location),                     # existing subtype check
    LocationCooccurrence.entity_a(Asset),              # join to Asset via entity_a
    Asset.has_inventory_log(InventoryLog),             # join to InventoryLog
    InventoryLog.is_high_waste(),                      # boolean flag filter
)

# Path 2: entity_b has high waste (OR branch 2)
model.define(OverlapRiskHotspot(LocationCooccurrence)).where(
    LocationCooccurrence.is_high_overlap(),
    LocationCooccurrence.at_location(Location),
    HighTrafficLocation(Location),
    LocationCooccurrence.entity_b(Asset),              # different FK path
    Asset.has_inventory_log(InventoryLog),
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
