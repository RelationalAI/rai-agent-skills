# Advanced Modeling Patterns

Detailed patterns extracted from the Concept Design, Relationship Principles, and Data Mapping sections of SKILL.md. Refer to these when working with advanced PyRel modeling scenarios.

<!-- TOC -->
- [Value Type Concepts for Type Safety](#value-type-concepts-for-type-safety)
- [Concept Creation with identify_by](#concept-creation-with-identify_by)
  - [Identity pattern taxonomy](#identity-pattern-taxonomy)
  - [Composite keys and preferred identification](#composite-keys-and-preferred-identification)
- [Ternary Property: Implicit Key Ordering](#ternary-property-implicit-key-ordering)
- [Property and Relationship String Quality](#property-and-relationship-string-quality)
- [Property Grouping Guidance](#property-grouping-guidance)
- [Inverse Relationships for Bidirectional Navigation](#inverse-relationships-for-bidirectional-navigation)
- [Role Naming for Disambiguation](#role-naming-for-disambiguation)
- [Same-Type Instance References](#same-type-instance-references)
- [Multi-argument Properties (Scenario Modeling)](#multi-argument-properties-scenario-modeling)
<!-- /TOC -->

---

## Value Type Concepts for Type Safety

In reference knowledge graphs, every attribute gets its own typed concept extending a base type. This provides type safety, self-documenting properties, and prevents accidentally assigning incompatible values.

```python
# Define value types
CustomerID = model.Concept("CustomerID", extends=[String])
CustomerName = model.Concept("CustomerName", extends=[String])
CustomerLifetimeSpend = model.Concept("CustomerLifetimeSpend", extends=[Float])
OrderTimestamp = model.Concept("OrderTimestamp", extends=[DateTime])

# Use in identify_by
Customer = model.Concept("Customer", identify_by={"id": CustomerID})

# Use in Property definitions
Customer.name = model.Property(f"{Customer} has name {CustomerName}")
Customer.lifetime_spend = model.Property(f"{Customer} has lifetime spend {CustomerLifetimeSpend}")

# Wrap computed values in value type when defining
model.define(
    Product.cost(ProductCost(aggs.sum(SupplyItem.cost).per(Product)))
)
```

**Naming convention:** `{ConceptName}{AttributeName}` (e.g., `CustomerName`, `ProductPrice`, `OrderTotal`).

**When to use:** Reference knowledge graphs use value types for every property. For our optimization models, use value types for entity IDs and key business quantities. For quick prototyping, raw types (`String`, `Float`) are acceptable.

---

## Concept Creation with identify_by

In v1, concepts can declare their identity key and type at creation:

```python
# Typed identifier
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Stock = model.Concept("Stock", identify_by={"index": Integer})

# With value type concept
ProductID = model.Concept("ProductID", extends=[String])
Product = model.Concept("Product", identify_by={"id": ProductID})

# Compound identity (composite key)
LineItem = model.Concept("LineItem", identify_by={
    "order_id": OrderId,
    "line_number": Integer,
})

# No identify_by (identity set via Property + .new())
_Site = Concept("Site")
_Site.id = Property(f"{_Site} has id {String:id}")
model.define(_Site.new(id=TABLE__SITE.id))
```

Both patterns are valid. Use `identify_by` when the identity key and type are known upfront. Use the Property + `.new()` pattern in modeler exports where identity is established during data loading.

### Identity pattern taxonomy

Identity patterns follow three naming conventions for value type concepts. Choosing the right one produces self-documenting, semantically clear models:

| Mode | Pattern | Example | When to use |
|------|---------|---------|-------------|
| **Popular** | Value type = ConceptName + RefMode | `CustomerName`, `ProductCode` | Most common; the value type name combines the concept with a standard suffix (.Name, .Code, .Nr) |
| **General** | Value type has its own name | `TaxFileNumber`, `ISBN` | When the reference scheme has a well-known independent name |
| **Unit-based** | Value type is a measurement unit | `kg`, `USD`, `meters` | For measured quantities where the unit IS the identity (rare for entity IDs; common for value types) |

```python
# Popular mode: CustomerID combines "Customer" + "ID"
CustomerID = model.Concept("CustomerID", extends=[String])
Customer = model.Concept("Customer", identify_by={"id": CustomerID})

# General mode: ISBN is a well-known independent identifier
ISBN = model.Concept("ISBN", extends=[String])
Book = model.Concept("Book", identify_by={"isbn": ISBN})

# Simple mode (prototyping): raw type, no value type concept
Order = model.Concept("Order", identify_by={"id": Integer})
```

### Composite keys and preferred identification

When an entity has multiple candidate keys (e.g., employee number AND name+department), declare which is the **preferred** key (used in `identify_by`) and which is secondary (modeled as a uniqueness-constrained Property).

```python
# Preferred: employee number (system-assigned, stable)
Employee = model.Concept("Employee", identify_by={"emp_number": Integer})

# Secondary: name + department (business-meaningful but not guaranteed unique)
# Model as properties -- the identify_by declares the preferred key
Employee.name = model.Property(f"{Employee} has {String:name}")
Employee.department = model.Property(f"{Employee} in {Department:department}")
```

**Decision rule:** Prefer surrogate/system IDs for `identify_by` (stable, guaranteed unique). Use natural keys (name, code) as secondary properties. For compound identity where both keys are truly needed, use `identify_by` with multiple fields.

**Third pattern — `Concept.identify_by(existing_prop)`:** Attach identity to a pre-declared property. Use when you need a custom reading string on the identity property (the default `identify_by={"field": Type}` uses an auto-generated reading):

```python
Customer = model.Concept("Customer")
Customer.customer_id = model.Property(f"{Customer} is identified by {String:customer_id}")
Customer.identify_by(Customer.customer_id)  # promote to identity key after declaration
```

Use this pattern when the identity property's natural language reading matters (e.g., for LLM-readable models).

---

## Ternary Property: Implicit Key Ordering

For Properties with 3+ fields, the FD is always: **all fields except the last are keys → last field is the value.** Be careful that this matches your intent:

```python
# This creates FD: (Supplier, Quantity) → Part
# i.e., for each (Supplier, Quantity) pair, there is exactly one Part
# This may NOT be what you intended!
model.Property(f"{Supplier} has available {Quantity} of {Part}")

# If you intended (Supplier, Part) → Quantity, reorder the fields:
model.Property(f"{Supplier} supplies {Part} in {Float:quantity}")
```

**Rule:** Place the dependent value (the "column" you'd look up) as the LAST field. Place identifying keys first.

**Before committing a ternary:** Verify it passes the irreducibility and minimum key span checks in [fact-decomposition-and-validation.md](fact-decomposition-and-validation.md). A ternary that decomposes into independent binaries should be split.

---

## Property and Relationship String Quality

Reading strings (the `f"{Concept} has {Type:property}"` patterns) are used by the LLM for reasoning and by reasoners for naming. Quality matters.

**Rules:**
- **Brevity**: Static text (words outside `{...}` patterns) should be 8 words or fewer
- **No redundancy**: Static text must not repeat words from field names. Bad: `f"{Order} is registered as vehicle {String:Type}"` (repeats context). Good: `f"{Order} has {String:Type}"`
- **Field limit**: Maximum 3 field references per reading. If you need more, the relationship should be decomposed
- **Verb choice**: Use precise verbs that describe the relationship's purpose -- `placed by`, `assigned to`, `contains`, `supplies` -- not generic connectors like `is associated with` or `is related to`
- **No owner echo**: Do not include the owner concept redundantly. Bad: `f"{Customer} is a customer with {String:name}"`. Good: `f"{Customer} has {String:name}"`

```python
# GOOD: concise, precise verb, no redundancy
Order.placed_by = model.Property(f"{Order} placed by {Customer:placed_by}")
Site.capacity = model.Property(f"{Site} has {Float:capacity}")
Operation.source = model.Relationship(f"{Operation} from {Site:source}")

# BAD: verbose, generic verb, redundant
Order.customer_relationship = model.Relationship(f"{Order} is associated with customer {Customer}")
Site.site_capacity = model.Property(f"{Site} is a site that has capacity {Float:site_capacity}")
```

---

## Property Grouping Guidance

When a concept has many properties, group them by topic for readability and targeted enrichment.

**Individual Properties (hand-written models):**

```python
# Location properties
Site.city = model.Property(f"{Site} has {String:city}")
Site.region = model.Property(f"{Site} has {String:region}")
Site.country = model.Relationship(f"{Site} located in {Country}")

# Capacity properties
Site.capacity = model.Property(f"{Site} has {Float:capacity}")
Site.max_throughput = model.Property(f"{Site} has {Float:max_throughput}")
```

**Multi-field Relationships with short_name (modeler exports):**

The modeler groups related fields into a single Relationship:

```python
Site.location_details = model.Relationship(
    f"{Site} is in {String:city}, {String:region}, {String:country}",
    short_name="site_location_details"
)
Site.capacity_info = model.Relationship(
    f"{Site} has {Float:capacity} capacity and {Float:max_throughput} throughput",
    short_name="site_capacity_info"
)
```

Both patterns are valid. Individual Properties give FD enforcement per attribute. Multi-field Relationships are more concise and self-documenting but lose per-field uniqueness guarantees.

**Guidelines:**
- Each property group should ideally draw from the same source table
- If topically related columns span multiple tables, create separate groups per source and document the join path in comments
- If a "property group" starts developing its own identity (shared across parent entities, referenced independently), it should be promoted to a concept (see Concept Orthogonality in SKILL.md)

---

## Inverse Relationships for Bidirectional Navigation

Define both directions when queries need both:

```python
# Forward (from FK in data)
Order.ordered_by = model.Relationship(f"{Order} ordered by {Customer}")

# Inverse using .alt()
Customer.placed_order = Order.ordered_by.alt(f"{Customer} placed {Order}")
```

Or define and bind explicitly:

```python
Customer.placed_order = model.Relationship(f"{Customer} placed order {Order}")
model.define(Customer.placed_order(Customer, Order)).where(Order.ordered_by == Customer)
```

The `.alt()` pattern is preferred for conciseness when the inverse is a simple flip.

---

## Role Naming for Disambiguation

When the same concept type appears multiple times in a relationship, use named roles:

```python
# WRONG: ambiguous
Transfer.parties = model.Relationship(f"{Person} pays {Person}")

# RIGHT: named roles
Transfer.parties = model.Relationship(f"{Person:payer} pays {Person:payee}")
Transfer.parties["payer"].name   # access specific role
```

---

## Same-Type Instance References

Use `.ref()` to create a second reference to the same concept type, for relating two independent instances (dependencies, comparisons, hierarchies):

```python
Task.depends_on = model.Relationship(f"{Task} depends on {Task}")

task2 = Task.ref()
model.where(
    Task.id == deps_data.task_id,
    task2.id == deps_data.depends_on_id
).define(Task.depends_on(task2))
```

---

## Multi-argument Properties (Scenario Modeling)

Decision variables that vary across scenarios use multi-argument Properties. The additional
Concept argument creates a dimension — each (Entity, Scenario) pair maps to exactly one value:

```python
# Single-argument (no scenarios): one value per entity
Project.x_approved = Property(f"{Project} is {Float:approved}")

# Multi-argument (with scenarios): one value per entity per scenario
Project.x_approved = Property(f"{Project} in {Scenario} is {Float:approved}")
```

Access requires binding with `ref()`:
```python
x_approved = Float.ref()

# In constraints/objectives — bind Scenario dimension via model.where():
model.where(Project.x_approved(Scenario, x_approved)).require(
    sum(x_approved * Project.cost).per(Scenario) <= Scenario.budget
)

# In solve_for — pass the binding, include Scenario.name for labeling:
problem.solve_for(Project.x_approved(Scenario, x_approved),
            name=[Scenario.name, Project.name])

# In result queries — filter on the bound reference:
model.select(Scenario.name, Project.name).where(
    Project.x_approved(Scenario, x_approved), x_approved > 0.5
)
```

**Key rules:**
- Variable Property uses `f"{Entity} in {Scenario} is {Float:var}"` pattern
- ALL constraints/objectives referencing the variable must bind Scenario via `model.where(Entity.x_var(Scenario, ref))`
- Use `.per(Scenario)` for aggregations that should be per-scenario
- Reference `Scenario.param` instead of literal values in constraints
- Single solve — no loop needed

**Implementation detail:** The argument structure is exposed via `Property._fields` — a list of
`Field` objects with `.name`, `.type`, and `.is_input`. Multi-arg Properties have 2+ input fields
(the subject + the scenario dimension). This structure identifies scenario dimensions programmatically.
