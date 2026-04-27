<!-- TOC -->
- [Categorization Patterns](#categorization-patterns)
  - [Enumeration concepts for categorical data](#enumeration-concepts-for-categorical-data)
  - [Entity subtyping for derived classifications](#entity-subtyping-for-derived-classifications)
  - [Computed categorization with typed sub-concepts](#computed-categorization-with-typed-sub-concepts)
  - [Decision rule: enumeration vs. subtyping](#decision-rule-enumeration-vs-subtyping)
  - [Subtype constraint completeness](#subtype-constraint-completeness)
  - [Subtyping vs. subset constraint trade-off](#subtyping-vs-subset-constraint-trade-off)
  - [Multiple inheritance](#multiple-inheritance)
- [Advanced Modeling Patterns](#advanced-modeling-patterns)
  - [Derived vs. asserted vs. partially computed properties](#derived-vs-asserted-vs-partially-computed-properties)
  - [Lazy vs. eager materialization](#lazy-vs-eager-materialization)
  - [Semantic stability](#semantic-stability)
  - [Historical properties (temporal tracking)](#historical-properties-temporal-tracking)
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

### Subtype constraint completeness

When defining subtypes, explicitly declare whether the set of subtypes is **exhaustive** (every supertype instance is in some subtype), **exclusive** (no instance is in two subtypes), or a **partition** (both).

| Constraint | Meaning | Validation |
|------------|---------|------------|
| **Exhaustive** | Every supertype instance belongs to at least one subtype | Check for uncategorized entities |
| **Exclusive** | No instance belongs to two subtypes simultaneously | Check for overlap between subtypes |
| **Partition** | Both exhaustive and exclusive | Both checks |

```python
# Define exclusive subtypes
InternalOrder = model.Concept("InternalOrder", extends=[Order])
ExternalOrder = model.Concept("ExternalOrder", extends=[Order])

# Validate exclusion: no order should be both internal and external
Order.in_both = model.Relationship(f"{Order} is both internal and external")
model.where(InternalOrder(Order), ExternalOrder(Order)).define(Order.in_both())

# Validate exhaustiveness: every order should be in some subtype
Order.uncategorized = model.Relationship(f"{Order} is uncategorized")
model.where(Order, model.not_(InternalOrder(Order)), model.not_(ExternalOrder(Order))).define(Order.uncategorized())
```

**Decision rule:** Always declare the intended constraint. For derived subtypes (computed from a property like `status`), the partition constraint is often implied by the derivation rules + value constraint -- don't redundantly assert what the derivation already guarantees. For asserted subtypes (loaded from data), validate explicitly.

### Subtyping vs. subset constraint trade-off

Subtyping and subset constraints can often model the same situation. Choose based on whether the filtered set has its own specific properties or relationships.

| Situation | Preferred pattern | Reason |
|-----------|------------------|--------|
| Filtered set has own properties/relationships | **Subtype** (`extends`) | Subtypes inherit parent properties and can add their own |
| Filtered set is just a condition with no specific roles | **`.where()` filter** or validation rule | Avoids concept proliferation; a filter suffices |
| Filtered set is reused across 3+ queries | **Subtype** | Named reusability justifies the concept |

```python
# Subtype: VIPCustomers have their own discount rate
VIPCustomer = model.Concept("VIPCustomer", extends=[Customer])
VIPCustomer.discount_rate = model.Property(f"{VIPCustomer} has {Float:discount_rate}")

# Filter only: "active orders" is just a condition, no specific properties
# Prefer .where() unless used in 3+ places
model.where(Order.status != "cancelled")  # inline filter
# OR promote to subtype if reused:
ActiveOrder = model.Concept("ActiveOrder", extends=[Order])
model.define(ActiveOrder(Order)).where(Order.status != "cancelled")
```

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

### Derived vs. asserted vs. partially computed properties

Every property in the model falls into one of three modes. Naming the mode explicitly helps the agent decide how to implement and maintain each property.

| Mode | Definition | PyRel pattern | Example |
|------|-----------|---------------|---------|
| **Asserted** | Loaded from data, taken as ground truth | `model.define(C.prop(TABLE.col)).where(...)` | Customer.name from CUSTOMERS table |
| **Derived** | Computed on demand from other properties | `model.define(C.prop(expression))` | Customer.total_spend = sum(Order.amount) |
| **Partially computed** | Some instances loaded from data, others computed | Both patterns on the same property | Product.price: loaded for most, computed for bundles |

```python
# Asserted: loaded directly from source
Customer.credit_score = model.Property(f"{Customer} has {Float:credit_score}")
model.define(Customer.credit_score(TABLE.credit_score)).where(Customer.id == TABLE.id)

# Derived: computed from base facts
Customer.total_spend = model.Property(f"{Customer} has {Float:total_spend}")
model.define(Customer.total_spend(aggs.sum(Order.amount).per(Customer)))

# Partially computed: some products have listed prices, bundles are computed
Product.price = model.Property(f"{Product} has {Float:price}")
model.define(Product.price(TABLE.price)).where(Product.id == TABLE.id)  # asserted
model.define(Product.price(aggs.sum(BundleItem.price).per(Product))).where(
    Bundle(Product)  # derived for bundles only
)
```

**Decision rule:** Prefer derived when base properties exist and the computation is straightforward -- this keeps the model authoritative and auditable. Use asserted for opaque externally-computed values. Partially computed is appropriate when most instances are loaded but a subset needs computation (e.g., default values, bundle pricing).

### Lazy vs. eager materialization

Derived properties can be evaluated lazily (computed at query time) or eagerly (materialized as stored values). This choice affects performance and freshness.

| Strategy | When to use | PyRel pattern |
|----------|-------------|---------------|
| **Lazy** (default) | Infrequently queried, cheap to compute, or base facts change often | Standard `model.define(C.prop(expression))` |
| **Eager** (materialized) | Queried in 3+ downstream rules/queries, expensive to compute | `model.Property()` + `model.define()` with explicit storage |

RAI's default behavior is lazy evaluation -- derived properties are computed when accessed. Materialize (see [Performance: materializing computed values](#performance-materializing-computed-values)) only when an aggregation is used in 3+ downstream contexts or computation cost is significant.

**Decision rule:** Start lazy. Materialize when you observe performance issues or when the same expensive aggregation appears in multiple downstream definitions. Don't materialize values that change frequently or are used only once.

### Semantic stability

Property-per-attribute modeling (where each property is an independent declaration) provides a key advantage: **when the domain changes, you add new properties rather than restructure existing concepts.** This is why RAI properties are declared independently rather than bundled into compound structures.

**Implication for the agent:** Resist the temptation to create compound structures (wide junction concepts with many properties, nested property groups) prematurely. Each property should be independently meaningful. When the domain evolves, you add new properties or relationships without restructuring existing ones.

```python
# Good: independent properties -- adding email doesn't change anything about name
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.email = model.Property(f"{Customer} has {String:email}")  # added later

# Avoid: compound structure that must be restructured when domain changes
Customer.contact_info = model.Relationship(
    f"{Customer} has {String:name} and {String:email} and {String:phone}"
)  # Adding a new field requires changing the reading string and all bindings
```

### Historical properties (temporal tracking)

When a property changes over time and you need to track its history (not just the current value), create a time-indexed property.

```python
# Current value only (default): one price per product
Product.price = model.Property(f"{Product} has {Float:price}")

# Historical tracking: price per product per effective date
Product.price_history = model.Property(
    f"{Product} has {Float:price} effective {Date:effective_date}"
)
# FD: (Product, Date) -> price -- each product has one price per date

# Query current price: filter to max effective_date
Product.current_price = model.Property(f"{Product} has {Float:current_price}")
product_ref, price_ref, date_ref = Product.ref(), Float.ref(), Date.ref()
model.where(
    Product.price_history(product_ref, price_ref, date_ref),
    date_ref == aggs.max(date_ref).per(product_ref)
).define(product_ref.current_price(price_ref))
```

**Decision rule:** Use time-indexed facts when:
- The domain requires knowing what a value WAS at a point in time (audit, compliance)
- Predictive reasoning needs historical patterns (demand forecasting, trend analysis)
- Multi-period optimization needs time-varying parameters (see multi-period models below)

For current-value-only properties (most common), a simple Property suffices.

### Time-indexed properties and multi-period models

For data indexed by time periods or numeric sequences, prefer multiarity properties over creating a separate time-period concept:

```python
# Define property with time and value slots
ResourceGroup.inv = model.Property(f"{ResourceGroup} on day {Integer:t} has {Float:inv}")

# Load time-indexed data
rg_data = model.data(resource_csv)
rg = ResourceGroup.new(name=rg_data.name)
model.define(rg, rg.inv(rg_data.day, rg_data.inventory_level))
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
