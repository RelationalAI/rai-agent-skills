<!-- TOC -->
- [Multi-Concept Joins](#multi-concept-joins)
- [Multi-Argument Relationships](#multi-argument-relationships)
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

## Multi-Argument Relationships

A single `model.Relationship` can pack several positional typed fields, not just one. These are common in ontologies generated from wide source tables (modeler / PyrelQB exports), where many columns of one row land on one relationship:

```python
# Value fields, each given an explicit name with {Type:label}
Shipment.lifecycle = model.Relationship(
    f"{Shipment} has {Float:delay_days} in {String:fiscal_quarter}"
)
# Entity fields with NO explicit label — the prose words are not names
Shipment.trading_parties = model.Relationship(
    f"{Shipment} has supplier {Business} and customer {Business}"
)
```

**Always run `inspect.fields()` first — the reading-string prose words are NOT field names.** A field is named only when the f-string gives it an explicit `{Type:label}`. `{Business}` with the word "supplier" nearby has *no* name; its field is auto-named from the type:

```python
from relationalai.semantics import inspect
inspect.fields(Shipment.lifecycle)          # (Shipment.lifecycle[delay_days], Shipment.lifecycle[fiscal_quarter])
inspect.fields(Shipment.trading_parties)    # ([shipment], [business], [business_2])  — NOT supplier/customer
```

Access depends on whether the field is **labeled** and whether it holds a **value** or an **entity**.

**Labeled value fields → index by name (works in `select()` AND `where()`):**

```python
model.where(
    Shipment.lifecycle["fiscal_quarter"] == "Q4-2024",   # name-index filters fine
    Shipment.lifecycle["delay_days"] > 0.0,
).select(
    Shipment.id.alias("shipment_id"),
    Shipment.lifecycle["delay_days"].alias("delay_days"),
).to_df()
```

A wrong name fails loudly (`KeyError` listing the valid field names), so this is self-correcting. Positional ref-binding (`Shipment.lifecycle(D, Q)` with `D=Float.ref()`, `Q=String.ref()`) is an equivalent path for value fields.

**Unlabeled fields → index by integer position** (the engine directs you here: *"access it by concept type or index"*). Read the right index from `inspect.fields()` — guessing is what makes `[6]` bind the wrong field:

```python
# fields: [0] shipment(owner)  [1] business(supplier)  [2] business_2(customer)
Shipment.trading_parties[1]   # the supplier-side Business
```

**Entity fields → bind via raw source columns, not the relationship.** This is the load-bearing rule for modeler-generated ontologies. For a field that holds an *entity* (a `{Business}`, `{Site}`, …), the relationship API is unreliable: positional ref-binding silently returns **0 rows**, and an index chain like `rel[1].id` returns **NaN** once combined with other filters. Bind the entity from the backing table's foreign-key column instead — the same fallback used for graph edges in `rai-graph-analysis`:

```python
ship = Sources.<schema>.shipment            # the backing Table
supplier = Business.ref()
model.where(
    supplier.id == ship.supplier_business_id,        # entity link via raw FK column
    ship.fiscal_quarter == "Q4-2024",                # filter raw columns directly
    ship.delay_days > 0.0,
).select(
    supplier.id.alias("supplier_id"),
    aggs.count(ship.id).per(supplier).alias("delayed_shipments"),  # group by the bound concept
).to_df()
```

**Keyword binding never works** — `Shipment.lifecycle(delay_days=D)` raises `RAIException [Too few args]`; field names are not keyword arguments.

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

## Model Introspection

For runtime discovery of concepts, relationships, tables, fields, and rules, see [inspect-module.md](inspect-module.md) (recommended API) and [model-introspection.md](model-introspection.md) (lower-level fallback and field-attribute details).
