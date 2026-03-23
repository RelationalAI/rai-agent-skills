<!-- TOC -->
- [Categorization Patterns](#categorization-patterns)
  - [Enumeration concepts for categorical data](#enumeration-concepts-for-categorical-data)
  - [Entity subtyping for derived classifications](#entity-subtyping-for-derived-classifications)
  - [Computed categorization with typed sub-concepts](#computed-categorization-with-typed-sub-concepts)
  - [Decision rule: enumeration vs. subtyping](#decision-rule-enumeration-vs-subtyping)
  - [Multiple inheritance](#multiple-inheritance)
- [Advanced Modeling Patterns](#advanced-modeling-patterns)
  - [Time-indexed properties and multi-period models](#time-indexed-properties-and-multi-period-models)
  - [Hierarchy modeling](#hierarchy-modeling)
  - [Bridge concepts via extends](#bridge-concepts-via-extends)
  - [Ternary relationships](#ternary-relationships)
  - [Tiebreaking in aggregations](#tiebreaking-in-aggregations)
  - [N-ary relationships](#n-ary-relationships)
  - [Performance: materializing computed values](#performance-materializing-computed-values)
<!-- /TOC -->

## Categorization Patterns

### Enumeration concepts for categorical data

Use for lookup tables (status codes, types, categories) instead of raw strings:

```python
LifecycleID = model.Concept("LifecycleID", extends=[String])
Lifecycle = model.Concept("Lifecycle")
Lifecycle.id = model.Property(f"{Lifecycle} has {LifecycleID:id}")
Lifecycle.name = model.Property(f"{Lifecycle} has {String:name}")
Lifecycle.sort_order = model.Property(f"{Lifecycle} has {Integer:sort_order}")

model.define(Lifecycle.new(model.data(lifecycle_df).to_schema()))

Component.lifecycle = model.Property(f"{Component} has lifecycle {Lifecycle:lifecycle}")
```

**Benefits:** Type safety, referential integrity, extensibility (enumerations can have their own properties), and cleaner queries.

**Soft-join pattern (shared enumerations across concepts):** When two concepts share categorical values (country codes, status codes, region names) but no strict FK exists between them, model the shared category as an enumeration concept and link both concepts to it:

```python
Country = model.Concept("Country", identify_by={"code": String})
Order.country = model.Relationship(f"{Order} ships to {Country}")
Customer.country = model.Relationship(f"{Customer} located in {Country}")
```

This is preferable to creating a direct Order-Customer relationship through the shared value, which would imply a business relationship that does not exist. The enumeration concept makes the shared dimension explicit without fabricating connections.

### Entity subtyping for derived classifications

Use when you need to repeatedly filter entities by the same condition:

```python
UncompletedTask = model.Concept("UncompletedTask", extends=[Task])
model.define(UncompletedTask(Task)).where(Task.status != "done")

# Use as filter everywhere
model.where(UncompletedTask(task), task.affects(Component))
```

### Computed categorization with typed sub-concepts

When deriving entity categories from computed properties, use typed sub-concepts rather than string-based segmentation:

```python
# Define segment hierarchy
CustomerValueSegment = model.Concept("CustomerValueSegment")
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentHigh = model.Concept("ValueSegmentHigh", extends=[CustomerValueSegment])
ValueSegmentMedium = model.Concept("ValueSegmentMedium", extends=[CustomerValueSegment])
ValueSegmentLow = model.Concept("ValueSegmentLow", extends=[CustomerValueSegment])

# Create named instances
CustomerValueSegmentName = model.Concept("CustomerValueSegmentName", extends=[String])
model.define(ValueSegmentVIP.new(name=CustomerValueSegmentName("VIP")))
model.define(ValueSegmentHigh.new(name=CustomerValueSegmentName("High")))

# Assign based on computed score thresholds
Customer.value_segment = model.Relationship(f"{Customer} has value segment {CustomerValueSegment}")
model.where(Customer.customer_value_score >= 300).define(Customer.value_segment(ValueSegmentVIP))
model.where(Customer.customer_value_score >= 150).define(Customer.value_segment(ValueSegmentHigh))
```

**Why typed sub-concepts over strings?** Type safety (no typos in string comparisons), extensibility (segments can have their own properties like `discount_rate`), efficient filtering (`where(Customer.value_segment(ValueSegmentVIP))` vs `where(Customer.segment == "VIP")`).

### Decision rule: enumeration vs. subtyping

| Use Case | Pattern |
|----------|---------|
| Lookup tables where categories have their own attributes | Enumeration Concepts |
| Classifying existing entities based on computed conditions | Entity Subtyping |
| Fixed categories from source data with no extra attributes | Either; prefer Enumeration if the set is closed |
| Derived categories from computed values | Entity Subtyping |

### Multiple inheritance

Concepts can extend multiple parents for cross-cutting classifications:

```python
ReturningVIPCustomer = model.Concept(
    "ReturningVIPCustomer",
    extends=[ReturningCustomer, VIPCustomer]
)
```

---

## Advanced Modeling Patterns

### Time-indexed properties and multi-period models

For data indexed by time periods or numeric sequences, prefer multiarity properties over creating a separate time-period concept:

```python
# Define property with time and value slots
FreightGroup.inv = model.Property(f"{FreightGroup} on day {Integer:t} has {Float:inv}")

# Load time-indexed data
fg_data = model.data(freight_csv)
fg = FreightGroup.new(name=fg_data.name)
model.define(fg, fg.inv(fg_data.day, fg_data.inventory_level))
```

**Decision rule for multiarity vs. cross-product:**

| Scenario | Approach | Reason |
|----------|----------|--------|
| One dimension is a numeric sequence (days, weeks) | Multiarity | Avoids entity explosion for time |
| Both dimensions are entities with relationships | Cross-product concept | Both have business meaning |

When using multi-period cross-product concepts, store time identifiers directly on the concept to avoid property-chain failures:

```python
ProductStoreWeek.week_num = model.Property(f"{ProductStoreWeek} in week {Integer:week_num}")
# Use ProductStoreWeek.week_num directly -- do NOT chain through a Week relationship
```

### Hierarchy modeling

Model hierarchies with same-type instance references and subtypes:

```python
# Same-type reference for tree structures (two independent Category instances)
Category.parent = model.Relationship(f"{Category} has parent {Category}")

# Entity subtyping for levels
RootCategory = model.Concept("RootCategory", extends=[Category])
# Define: categories with no parent are roots
```

For downstream reasoning (queries, optimization, graph analysis), materialize aggregated values at hierarchy levels rather than traversing the hierarchy at query time.

### Bridge concepts via extends

Use `extends` to create derived concepts that represent filtered subsets:

```python
Bridge = model.Concept("Bridge", extends=[Site])

site1, site2 = Site.ref(), Site.ref()
op = Operation.ref()

model.define(Bridge(site1)).where(
    Operation.source_site(op, site1),
    Operation.destination_site(op, site2),
    site1.region != site2.region
)
```

This is cleaner than maintaining a boolean flag, and it lets you query `Bridge` directly as a concept with all `Site` properties inherited.

### Ternary relationships

Use when binary decomposition would create spurious connections or lose information:

```python
Student.enrolled_with_grade = model.Relationship(
    f"{Student} enrolled in {Course} with grade {Grade}"
)
```

**Decision rule:** If removing any participant from the fact makes the remaining information incomplete or ambiguous, you need a ternary relationship. If the fact decomposes cleanly into independent binary facts, use separate binary relationships.

### Tiebreaking in aggregations

When multiple entities tie on a computed value, choose a tiebreaking strategy:

| Scenario | Recommended | Reason |
|----------|-------------|--------|
| Natural ordering exists (dates, priorities) | Attribute-based | Meaningful order |
| No meaningful ordering among ties | Entity-based (`aggs.min(Entity)`) | Stable, does not mislead |
| Multiple queries need same tiebreaker | Entity-based | Consistency across queries |

Define tiebreaker logic once in a computed layer and reuse it everywhere to prevent discrepancies.

### N-ary relationships

Relationships with more than two roles:

```python
Order.contains = model.Relationship(
    f"{Order} contains {Integer:quantity} of {Product}"
)

# Access roles
Order.contains["quantity"]      # int value
Order.contains[Product].id     # Product entity
```

Use sparingly. Name primitive roles explicitly. Consider whether a separate junction concept would be clearer.

This pattern also covers **hyper edges** — data that lives on the relationship between entities (e.g., a shipping cost on a supplier-warehouse route, a grade on a student-course enrollment). See "Properties on relationships (hyper edges)" in [SKILL.md](../SKILL.md) for the design guidance.

### Performance: materializing computed values

When an aggregation is used in three or more downstream queries, materialize it:

```python
Region.total_demand = model.Property(f"{Region} has {Float:total_demand}")
model.define(Region.total_demand(sum(Order.quantity).per(Region)))

# Downstream queries use the cached value
model.where(Region.total_demand > threshold)
```

Do not materialize values that change frequently, are used only once, or involve simple property access.
