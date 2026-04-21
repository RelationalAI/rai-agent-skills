<!-- TOC -->
- [Multi-Concept Joins](#multi-concept-joins)
- [Reusable Query Fragments](#reusable-query-fragments)
  - [Lambda helpers](#lambda-helpers)
  - [Named refs for independent aggregation contexts](#named-refs-for-independent-aggregation-contexts)
  - [Parameterized query functions](#parameterized-query-functions)
- [Data Export](#data-export)
  - [Table Reference](#table-reference)
  - [Export Pattern: .into(table).exec()](#export-pattern-intotableexec)
  - [Full Export Examples](#full-export-examples)
  - [Table Column Access](#table-column-access)
  - [Table as Row Source](#table-as-row-source)
<!-- /TOC -->

## Multi-Concept Joins

Join concepts by equating properties in a `where()` clause. Use `.ref()` when joining a concept to itself.

```python
# Cross-entity join: orders with their supplier info
model.where(
    Order.supplier_id == Supplier.id
).select(
    Order.id.alias("order_id"),
    Supplier.name.alias("supplier_name"),
    (Order.cost - Supplier.base_cost).alias("markup")  # Inline computation
)

# Self-join via .ref()
Alt = Edge.ref()
model.where(Edge.source == Alt.source, Alt.cost < Edge.cost).select(
    Edge.id.alias("edge"), (Edge.cost - Alt.cost).alias("savings")
)
```

**Relationship traversal** -- chain properties for multi-hop navigation in select, where, and result extraction:

```python
# Multi-hop: EdgeTransportMode -> edge -> source -> id
model.select(EdgeTransportMode.edge.source.id.alias("origin"))

# FK traversal: follow property to related entity, then access its properties
Order.ordered_by.name.alias("customer_name")      # Order -> Customer -> name
Order.ordered_at_location.name.alias("store_name") # Order -> Location -> name
Nation.region.r_name                                # Nation -> Region -> r_name
CalendarDay.calendar_year.nr                        # CalendarDay -> Year -> nr
```

**Multi-hop join inference (4+ relationships):** When the question requires tracing a path through many concepts, chain relationship applications in `.where()` to join them, then select from any concept in the chain:

```python
# Trace: LineItem -> Order -> Customer -> Region -> Country
# "What countries do our high-value line items ship to?"
li = LineItem.ref()
order = Order.ref()
customer = Customer.ref()
region = Region.ref()
country = Country.ref()

model.where(
    li.part_of_order(order),
    order.placed_by(customer),
    customer.located_in(region),
    region.belongs_to(country),
    li.extended_price > 1000.0,
).select(
    li.id.alias("line_item"),
    customer.name.alias("customer"),
    country.name.alias("country"),
).to_df()
```

Each `.where()` condition joins the next hop. Use explicit concept refs and relationship applications — not dot-chains — so bindings carry across all hops.

**Dot-chain binding gotcha:** A dot-chain in `select` creates its own independent lookup — it does NOT carry bindings established by relationship applications in `where`. This is a common source of incorrect results:

```python
# WRONG — .uses.id does NOT pick up the Asset filter from .where()
# Returns ALL asset ids, not just asset 102
model.select(Employee.nr, Employee.uses.id).where(
    Employee.uses(Asset),
    Asset.id == 102
).to_df()

# CORRECT option A: dot-chain through the relationship application
model.select(Employee.nr, Employee.uses(Asset).id).where(
    Employee.uses(Asset),
    Asset.id == 102
).to_df()

# CORRECT option B: use the bound concept directly in select
model.select(Employee.nr, Asset.id).where(
    Employee.uses(Asset),
    Asset.id == 102
).to_df()
```

**Why:** `Employee.uses.id` is compiled as a `Chain` that creates a fresh lookup for `uses`, independent of the `Employee.uses(Asset)` application in `where`. To get the filtered entity's properties, reference the bound concept variable (`Asset.id`) or chain through the application (`Employee.uses(Asset).id`).

---

## Reusable Query Fragments

### Lambda helpers

Encapsulate repeated join patterns as lambdas for reuse within a query:

```python
# Define reusable join pattern
# Note: lambdas use model.where() — pass model as a parameter in multi-model code.
order_has_product = lambda o, oi, p: model.where(
    oi.composes_order(o),
    oi.contains_product(p),
)

# Use multiple times with different refs
orders_with_both = aggs.count(order).per(product_a, product_b).where(
    order_has_product(order, oi_a, product_a),
    order_has_product(order, oi_b, product_b),
)
```

**Promotion rule:** If multiple app functions share the same helper, evaluate whether it represents business logic (promote to computed layer) or utility logic (keep as shared helper).

### Named refs for independent aggregation contexts

When a complex query needs the same concept in multiple independent aggregation contexts, use separate named refs to avoid `ValidationError: Unused variable declared`:

```python
customer = Customer.ref()
product = Product.ref()
order = Order.ref()
orderitem = OrderItem.ref()

# Aggregation 1: count per customer-product pair
order_count = aggs.count(orderitem).per(customer, product).where(
    orderitem.composes_order(order),
    order.ordered_by(customer),
    orderitem.contains_product(product),
)

# Aggregation 2: max across products per customer
max_count = aggs.max(order_count).per(customer)

# Aggregation 3: tiebreaker using entity comparison
min_entity = aggs.min(product).per(customer).where(order_count == max_count)

# Final define
model.define(customer.favorite_product(product)).where(product == min_entity)
```

### Parameterized query functions

App-layer queries accept parameters and return `rai.Fragment` for composability and testing:

```python
def revenue_by_location(model, location_name: str = "Brooklyn") -> rai.Fragment:
    return model.where(
        model.StoreLocation.name == location_name,
        model.Order.ordered_at_location(model.StoreLocation),
    ).select(
        aggs.sum(model.Order.total).per(model.StoreLocation).alias("total_revenue"),
    )

# Execute
result = revenue_by_location(jaffle, "Manhattan").to_df()
```

---

## Data Export

Export query results to external tables using `Model.Table()` + `.into()` + `.exec()`.

### Table Reference

`Model.Table(name, schema={})` creates a lightweight handle for an external table (e.g., a Snowflake table or view). Two uses:
1. **As row source** — load data into concepts via `Table.to_schema()` (see `rai-ontology-design`)
2. **As export target** — write query results via `Fragment.into(table).exec()`

```python
# Create table reference (no schema needed for export)
out = model.Table("DB.SCHEMA.RESULTS_EXPORT")
```

With explicit schema (types checked on export):

```python
out = model.Table("DB.SCHEMA.RESULTS_EXPORT", schema={"id": Integer, "name": String})
```

### Export Pattern: `.into(table).exec()`

**`Fragment.into(table, update=False)`** — set export destination. Returns a new Fragment.
- `update=False` (default): **Replace** the destination table
- `update=True`: **Merge/upsert** into existing table

**`Fragment.exec()`** — execute the query and export results. Returns DataFrame or None. Idempotent: subsequent `.exec()` calls are no-ops.

```python
# Replace mode (default) — overwrites destination table
out = model.Table("DB.SCHEMA.RESULTS_EXPORT")
model.select(Person.id, Person.name).into(out).exec()
```

```python
# Update mode — merge into existing table
out = model.Table("DB.SCHEMA.RESULTS_EXPORT")
model.select(Person.id, Person.name).into(out, update=True).exec()
```

### Full Export Examples

**Export query results with aliased columns:**

```python
out = model.Table("DB.SCHEMA.SUPPLIER_REPORT")
model.where(
    Business.is_high_value_customer(),
    Business.receives_shipment(Shipment),
).select(
    Business.name.alias("CUSTOMER_NAME"),
    aggs.count(Shipment).per(Business).alias("SHIPMENT_COUNT"),
).into(out).exec()
```

**Export solution results after a solve:**

```python
results_table = model.Table("DB.SCHEMA.OPTIMIZATION_RESULTS")
model.select(
    Route.origin.name.alias("FROM_SITE"),
    Route.dest.name.alias("TO_SITE"),
    Route.x_flow.alias("OPTIMAL_FLOW"),
).where(Route.x_flow > 1e-6).into(results_table).exec()
```

### Table Column Access

Tables behave like concepts with column relationships:

```python
t = model.Table("DB.SCHEMA.CUSTOMERS", schema={"id": Integer, "name": String})

# Access by name or index
model.select(t["name"], t[0]).to_df()

# Select all columns
model.select(*t).to_df()
```

### Table as Row Source

Use `Table.to_schema()` to load external data into concepts:

```python
source = model.Table("DB.SCHEMA.CUSTOMERS", schema={"id": Integer, "name": String})
Customer = model.Concept("Customer", identify_by={"id": Integer})
model.define(Customer.new(source.to_schema()))

# Exclude FK columns and map them to concept references
orders_table = model.Table("DB.SCHEMA.ORDERS")
model.define(
    Order.new(
        orders_table.to_schema(exclude=["customer_id"]),
        customer=Customer.new(id=orders_table.customer_id),
    )
)
```

---

## Schema Introspection Reference

Detailed reference for discovering model structure at runtime.

**Prefer `inspect.schema(model)` from `relationalai.semantics.inspect` (v1.0.14+) for all of the patterns in this section.** It returns a frozen `ModelSchema` covering concepts, inherited properties with real types, relationships, tables, inline data sources, and enums in a single call. The lower-level `model.concepts` / `model.relationships` / `model.tables` patterns below remain valid and are kept as a fallback.

See [inspect-module.md](inspect-module.md) for the recommended API. The rest of this section documents the lower-level surface.

### Concept Discovery

```python
# List all concept names (concepts is a list in v1, not a dict)
for concept in model.concepts:
    print(concept)

# Lookup by name via index
Order = model.concept_index["Order"]

# Check if a concept exists
if "Order" in model.concept_index:
    Order = model.concept_index["Order"]
```

### Relationship Discovery

```python
# List all relationships
for rel in model.relationships:
    fields = list(rel)
    field_desc = ", ".join(f"{f.name}:{f.type}" for f in fields)
    print(f"({field_desc})")

# Lookup relationship by short name
if "customer" in model.relationship_index:
    customer_rel = model.relationship_index["customer"]

# Find relationships involving a specific concept
def relationships_for(model, concept_name: str):
    results = []
    for rel in model.relationships:
        if any(str(f.type) == concept_name for f in rel):
            results.append(rel)
    return results
```

### Field Classification

Fields in v1 always have a resolved `type` (never None). Use `field.is_input` and `field.is_list` for additional classification.

```python
for rel in model.relationships:
    for field in rel:
        print(f"  name={field.name}, type={field.type}, input={field.is_input}, list={field.is_list}")
```

**Build a property map for a concept:**

```python
def get_concept_properties(model, concept_name: str):
    """Return {property_name: type} for all properties of a concept."""
    SCALAR_TYPES = {"String", "Integer", "Float", "Boolean", "Date"}
    props = {}
    for rel in model.relationships:
        fields = list(rel)
        if len(fields) == 2 and str(fields[0].type) == concept_name:
            target = fields[1]
            kind = "scalar" if str(target.type) in SCALAR_TYPES else "entity"
            props[target.name] = {"type": str(target.type), "kind": kind}
    return props
```

### Table Discovery

```python
# List all loaded tables
for table in model.tables:
    print(table)

# Lookup by path
if "DB.SCHEMA.ORDERS" in model.table_index:
    orders_table = model.table_index["DB.SCHEMA.ORDERS"]

# Inline model.data(...) sources — tracked separately
for data in model.data_items:
    print(data)
```

**Note:** `model.tables` does not include inline `model.data(pd.DataFrame(...))` sources. Use `model.data_items` or `inspect.schema(model)` (which covers both) when listing every data source feeding the model.

### Rule Inspection

```python
# List all define() fragments
for fragment in model.defines:
    print(fragment)

# List all require() fragments
for fragment in model.requires:
    print(fragment)

# List all enum types
for enum_type in model.enums:
    print(enum_type)
```

### Data Inspection

```python
# Materialize relationship data as DataFrame
df = Order.customer.to_df()
print(f"{len(df)} Order-Customer links")

# Quick debug print
Order.customer.inspect()
```
