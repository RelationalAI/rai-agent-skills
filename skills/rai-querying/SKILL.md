---
name: rai-querying
description: Covers query construction in PyRel v1 including aggregation, derived concepts, filtering, ordering, multi-concept joins, and data export. Use when building queries or extracting data from RAI models.
---

# Querying
<!-- v1-SENSITIVE -->

## Summary

**What:** Query construction — producing actual table output via `select().to_df()`. Covers aggregation, filtering, joins, ordering, and data export in PyRel v1.

**Scope boundary:** A "query" in this skill means code that produces a DataFrame output via `select().to_df()`. Model logic (definitions, computed properties, derived relationships, entity creation) belongs in `rai-pyrel-coding` — see its Definitions section. **Queries should be simple.** Most logic should live in definitions; queries should primarily select and aggregate values that definitions have already computed. If a query has complex logic, consider extracting it into a definition instead.

**When to use:**
- Writing queries to extract data from a model (`select`, `where`, `to_df`)
- Building aggregations for output (`count`, `sum`, `min`, `max`, `avg` with `per`/`where`)
- Filtering and ordering query results (`in_`, `not_`, `union`, `rank`/`top`/`bottom`)
- Joining across concepts or self-joining with `.ref()` in select contexts
- Exporting results to Snowflake tables
- Extracting solution values after a solve (used alongside `rai-prescriptive-results-interpretation`)

**When NOT to use:**
- Defining model logic (concepts, properties, relationships, derived properties via define/where) — see `rai-pyrel-coding`
- Solver formulation patterns (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Post-solve interpretation logic (quality assessment, explanation, sensitivity) — see `rai-prescriptive-results-interpretation`

**Overview:** Reference skill. Key lookup areas: Query Basics (where/select/to_df), Aggregation (sum/count/per), Filtering (in_/not_/union), Multi-Concept Joins, Data Export.

---

## Quick Reference

```python
from relationalai.semantics.std import aggregates as aggs

# Basic query — prefer model.where/model.select for multi-model safety
result = model.where(Order.status == "active").select(Order.id, Order.total).to_df()

# Grouped aggregation
revenue = model.where(Order).select(
    aggs.sum(Order.total).per(Order.customer).alias("revenue"),
    Order.customer.name.alias("customer")
).to_df()

# Conditional aggregation
delayed = aggs.count(Shipment).per(Supplier).where(Shipment.is_delayed())

# Distinct wrapper — everything inside distinct()
unique = model.select(distinct(Product.category.alias("cat"))).to_df()
```

---

## Query Basics

Core pattern: `model.where(conditions).select(expressions)` chained with `.to_df()` for execution.

**Best practice: Use `model.where()` / `model.select()` instead of standalone `where()` / `select()`.** The standalone forms are convenience wrappers that only work when exactly one Model exists in the process. With two or more models, they raise `"Multiple Models have been defined."` Using `model.where()`/`model.select()` guarantees compatibility in multi-model scenarios, makes code portable when copying between scripts, and reduces import requirements.

```python
# Preferred: model method form
result = model.where(
    Business.is_high_value_customer(),
    Business.receives_shipment(Shipment),
    Shipment.is_delayed()
).select(
    Business.name.alias("customer_name"),
    Shipment.delay_days.alias("delay_days")
).to_df()
```

**`.alias("name")`** — rename output columns for clean DataFrames:

```python
model.where(
    Shipment.supplier(Shipment, Supplier)
).select(
    Supplier.name.alias("supplier_name"),
    Supplier.id.alias("supplier_id"),
)
```

**`.to_df()`** — execute query and return a pandas DataFrame.

**`.inspect()`** — convenience for debugging; prints the DataFrame to stdout. Equivalent to `print(rel.to_df())`.

```python
Shipment.supplier.inspect()  # Quick check of a relationship's contents
```

**`distinct(...)`** — deduplicate result rows. Frequently needed with aggregations to prevent validation errors.

All columns in a `select()` must be either all inside `distinct()` or all outside — mixing causes a runtime error. Grouped aggregation queries (grouping by a property value, not an entity) require `distinct()` to get one row per group; without it, PyRel returns one row per entity with duplicated aggregation values.

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

# WRONG — without distinct(), returns one row per entity (duplicated aggregations)
# model.select(
#     DailyDeployment.weather_condition.alias("weather"),
#     aggs.count(DailyDeployment).per(DailyDeployment.weather_condition).alias("count"),
# ).where(...).to_df()  # Returns N rows instead of grouped rows!

# WRONG: mixing bare select with distinct field — will error
# model.select(Product.name, distinct(Product.category))  # ← DO NOT DO THIS
```

**When to use `distinct()`:**
- Grouping by a **property value** (e.g., `weather_condition`, `category`): use `distinct()` — without it you get duplicated rows
- Grouping by an **entity concept** (e.g., `.per(Customer)`): usually not needed, since each entity is already unique
- Grouping by a **mix of entity and property value** (e.g., `.per(Supplier, Dest.region)`): treat as property-value grouping — use `distinct()`
- Deduplicating rows from multi-hop joins: use `distinct()`

**`model.select(...)` standalone** — query without conditions:

```python
query = model.select(distinct(
    Bridge.id.alias("bridge_site_id"),
    Bridge.name.alias("bridge_site_name"),
    Bridge.region.id.alias("bridge_region"),
    Bridge.connects_region.id.alias("connects_to_region")
))
```

---

## Aggregation Patterns

Import aggregates via module alias to avoid shadowing Python builtins:

```python
from relationalai.semantics.std import aggregates as aggs
# Use aggs.count, aggs.sum, aggs.max, aggs.min, aggs.avg

from relationalai.semantics.std.aggregates import string_join, rank, desc, asc
```

**Available aggregates:** `count`, `sum`, `min`, `max`, `avg`, `string_join`.

**`avg` — available in queries, NOT in solver contexts:**

```python
# Query: average order value per customer
aggs.avg(Order.total).per(Customer).alias("avg_order_value")

# WILL RAISE NotImplementedError if used in p.satisfy() or p.minimize/maximize
# Solver-supported aggregates: sum, min, max, count only
```

**`.per(group)` for group-by semantics:**

```python
# Count shipments per supplier
aggs.count(Shipment).per(Shipment.supplier).alias("total_shipments")

# Sum with arithmetic in aggregate
aggs.sum(Shipment.quantity * Shipment.delay_days).per(Shipment.supplier).alias("qty_delay_impact")

# Sum per entity
aggs.sum(Shipment.delay_days).per(Shipment.supplier).alias("total_delay_days")
```

**Multi-key grouping:**

```python
aggs.sum(customer.receives_shipment.quantity).per(customer, SKU).alias("quantity_at_risk")
```

**Aggregation with unary relationship filter:**

```python
# Count only delayed shipments (where is_delayed is a unary relationship)
aggs.count(Shipment.is_delayed()).per(Shipment.supplier).alias("delayed_shipments")
```

**Full query with mixed aggregations:**

```python
return model.where(
    Business.is_high_value_customer(),
    Business.receives_shipment(Shipment),
    Shipment.is_delayed()
).select(
    aggs.count(Business).alias("high_value_customers"),
    aggs.count(Shipment).alias("total_shipments"),
    aggs.sum(Shipment.quantity).alias("delayed_quantity")
)
```

**Conditional aggregation with `.where()` on the aggregate** (acts as a subquery filter):

```python
# Count only orders where customer exists (loyalty orders)
total_loyalty = aggs.count(order).per(Truck).where(order.customer)

# Count only orders where customer does NOT exist
total_unknown = aggs.count(order).per(Truck).where(model.not_(order.customer))

# Count with boolean flag filter
high_priority = aggs.count(line_item).per(line_item.ship_mode).where(
    line_item.order(order),
    (order.priority == "1-URGENT") | (order.priority == "2-HIGH")
)

# Sum with time-window filter
from dateutil.relativedelta import relativedelta
import datetime as org_dt
target = org_dt.datetime(2025, 11, 1)
recent = model.where(Order.order_ts >= target - relativedelta(months=3), Order.order_ts < target)
aggs.sum(Order.total).per(Product).where(recent)
```

**`per(group).sum(expr)` standalone form:**

```python
from relationalai.semantics import per

flow_out = per(Edge.source).sum(Edge.flow)
# Equivalent to: sum(Edge.flow).per(Edge.source)
```

`per()` is a standalone function import (`from relationalai.semantics import per`) that provides an alternative grouping syntax. Both `per(X).sum(Y)` and `sum(Y).per(X)` are valid and equivalent.

**Conditional counting with `count(X, condition)`:**

`count()` accepts a second argument as a condition expression. This works in both query and solver contexts:

```python
# Count how many players are assigned to each group
count(Player, x == group)  # counts players where x_group equals the target group
```

In query contexts, you can also use `.where()` on the aggregate for the same effect (see examples above).

---

## Derived Concepts and Relationships

> **Note:** These `define()`/`where()` patterns are model logic, not queries. They are included here as a quick reference because they often precede query construction. For the full treatment of definitions — the core of PyRel coding — see `rai-pyrel-coding` § Definitions.

**`model.define(...).where(...)` — derive from conditions:**

```python
# Unary relationship as boolean flag
model.define(Shipment.is_delayed()).where(Shipment.delay_days > 0)

# Named intermediate relationship for staged computation
relevant_shipment = model.Relationship(f"Delayed Shipment in Last Quarter: {Shipment}")
model.define(relevant_shipment(Shipment)).where(
    Shipment.fiscal_quarter == aggs.max(Shipment.fiscal_quarter)
)
```

**`model.where(...).define(...)` — both directions are valid:**

```python
# Define a target subset
target_supplier = model.Relationship(f"Target Supplier: {Business}")
model.define(target_supplier(Business)).where(
    Business.name == supplier_name
)

# Define a subset from a unary relationship
target_customer = model.Relationship(f"Target Customer: {Business}")
model.define(target_customer(Business)).where(
    Business.is_high_value_customer()
)
```

**Computed properties from aggregation:**

```python
# Computed metric: count of operations per site
model.where(
    Operation.destination_site(op, site),
    Operation.type(op, "SHIP")
).define(Site.count_is_destination(site, aggs.count(op).per(site)))
```

For multi-concept joins, reusable query fragments, and Snowflake export patterns, see [joins-and-export.md](references/joins-and-export.md).

---

## Subtype Query Patterns

Subtypes inherit parent properties, but you MUST bind the subtype to its parent and access properties through the PARENT concept. Accessing properties directly on the subtype causes `TyperError`.

```python
# CORRECT — bind subtype to parent, access properties via parent
results = model.where(
    HighChurnRiskCustomer(Customer),
).select(
    Customer.full_name.alias("name"),
    Customer.churn_score.alias("churn_score"),
).to_df()

# WRONG — accessing properties on subtype causes TyperError
# results = model.where(HighChurnRiskCustomer).select(
#     HighChurnRiskCustomer.full_name.alias("name"),  # FAILS!
# ).to_df()
```

**Counting subtypes:**

```python
# CORRECT — count parent concept, filter by subtype binding
results = model.select(
    aggs.count(FoodTruck).alias("count"),
).where(
    UnderutilizedFoodTruck(FoodTruck),
).to_df()

# WRONG — counting subtype directly causes TyperError
# results = model.select(rai.count(UnderutilizedFoodTruck).alias("count")).to_df()
```

**Boolean relationships as filters (not selectable):**

Boolean relationships (unary flags like `is_event_day`, `is_active`) can ONLY be used as filters in `.where()`. They CANNOT be placed in `select()` with `.alias()`.

```python
# CORRECT — boolean flag as filter in where()
results = model.where(
    DailyDeployment.is_event_day(),
).select(
    DailyDeployment.deployment_date.alias("date"),
).to_df()

# WRONG — boolean relationship in select() causes TyperError
# results = model.select(DailyDeployment.is_event_day.alias("flag")).to_df()
```

To project a boolean flag as a column, use the **two-query pandas pattern**: query all entities, query the flagged subset, then merge with `df["flag"] = df["id"].isin(flagged_ids)`.

---

## Filtering and Ordering

Chain `.where()` conditions to filter results. Each `.where()` adds an AND condition and can introduce new concept refs.

```python
# Numeric and string filtering
model.where(Product.price > 100, Product.category("electronics")).select(Product.name)

# Sorting: order_by() is NOT yet available in v1.
# Use std.aggregates for ranking/ordering:
from relationalai.semantics.std.aggregates import rank, rank_asc, rank_desc, desc, asc, top, bottom, limit

# Rank by descending value
model.where(Order.status("open")).select(
    rank(desc(Order.value)).alias("rank"),
    Order.id, Order.value
)

# Top-N / Bottom-N
top(3, Order.value)       # Top 3 by value
bottom(5, Product.price)  # Bottom 5 by price
```

**Set membership with `.in_()`:**

```python
model.where(LineItem.ship_mode.in_(["AIR", "AIR REG"])).select(...)
model.where(Part.container.in_(["SM CASE", "SM BOX", "SM PACK"])).select(...)
```

**Negation with `model.not_()`:**

```python
# Entities that DON'T have a relationship
model.where(
    order := Order.ref(),
    model.not_(order.customer),          # orders without a customer
).select(order.id.alias("orphan_order_id"))

# Negated condition in aggregation
avg_without = aggs.avg(order.total).per(product).where(
    model.not_(order_has_product(order, orderitem, product))
)
```

**`not_()` patterns:**

```python
# Negate a comparison
model.not_(Person.age > 40)

# Negate a union (NOT OR) — people aged 20-30
model.where(model.not_(model.union(Person.age > 30, Person.age < 20)))

# Negate relationship existence (no siblings)
model.select(aggs.count(Person.name)).where(model.not_(Person.brother))

# Grouped vs separate negation:
# NOT (A AND B):
model.not_(Person.pets, Person.pets.name == "boots")
# (NOT A) AND (NOT B):
model.not_(Person.pets), model.not_(Person.pets.name == "boots")
```

**OR-filtering with `model.union()`:**

```python
# Match entities satisfying ANY condition (set union, not first-match)
model.where(model.union(
    Person.age < 18,
    Person.age >= 65,
)).select(Person.name).to_df()

# Combine NOT with union
model.where(
    model.not_(model.union(Person.age > 30, Person.age < 20)) | (Person.name == "Cleve")
).select(Person.name, Person.age).to_df()
```

The `|` operator evaluates branches left-to-right and picks the first that succeeds (ordered fallback / if-then-else), while `model.union()` collects ALL matching branches (set union). Use `|` for defaults (`status | "missing"`) and case-when chains; use `model.union()` for multi-term objectives or OR-filtering. For full semantics, CASE-WHEN patterns, and multi-component objective use, see `rai-pyrel-coding/expression-rules.md`.

**HAVING equivalent** -- filter on aggregated values by binding the aggregate in `where()`:

```python
model.where(
    Customer.placed_order(Order),
    Order.ordered_at_location(StoreLocation),
    total_per_store := aggs.sum(Order.total).per(StoreLocation),
    customer_count := aggs.count(Customer).per(StoreLocation),
    total_per_store / customer_count < 500  # HAVING clause equivalent
).select(
    StoreLocation.name.alias("store"),
    total_per_store.alias("total_revenue"),
)
```

**Dynamic query construction:** Build a base query and conditionally append `.where()` clauses. Each additional `.where()` narrows the result set without modifying prior conditions. This is useful when filter criteria come from user input or runtime parameters.

---

## Requirements (Semantic Data Validation)

Requirements are reusable checks that express what must be true in your domain. They fire at materialization time (`to_df()` or `exec()`). A failing requirement makes **all** queries on that model fail.

Three forms with distinct semantics:

```python
# 1. Global — passes if AT LEAST ONE entity satisfies expr
model.require(Order.status == "pending")

# 2. Per-entity — EVERY instance must satisfy; fails if any violates
Order.require(Order.amount >= 0)
# Equivalent to:
model.where(Order).require(Order.amount >= 0)

# 3. Scoped — every match in the where scope must satisfy
model.where(Order.amount > 0).require(Order.customer)
```

**Key distinction:** `model.require(expr)` is an existence check ("at least one"); `Concept.require(expr)` is a universal check ("all of them"). Choose based on your invariant.

**Requirements fire at `to_df()` / `exec()` time** — not at definition time. There is no `.check()` or `.validate()` method.

**In solver context:** `p.satisfy(model.require(expr))` promotes the requirement to a solver constraint:

```python
p.satisfy(model.require(supply >= demand))  # hard constraint in the solver
```

---

## Model Introspection

Public API for discovering model structure at runtime. Useful for dynamic code generation, model validation, and exploring unfamiliar models.

### Core Collections

| API | Type | Description |
|-----|------|-------------|
| `model.concepts` | `list[Concept]` | All concepts in creation order |
| `model.concept_index` | `dict[str, Concept]` | Lookup concept by name |
| `model.relationships` | `list[Relationship]` | All relationships/properties |
| `model.relationship_index` | `dict[str, Relationship]` | Lookup by short name |
| `model.tables` | `list[Table]` | All table references |
| `model.table_index` | `dict[str, Table]` | Lookup table by path |
| `model.defines` | `KeyedSet[Fragment]` | All define() fragments |
| `model.requires` | `KeyedSet[Fragment]` | All require() fragments |
| `model.enums` | `list[type[ModelEnum]]` | Enum types |

### Relationship / Property Inspection

| API | Type | Description |
|-----|------|-------------|
| `rel.to_df()` | method | Materialize relationship tuples as DataFrame |
| `rel.inspect()` | method | Print relationship data to stdout |

### Field Attributes

| API | Type | Description |
|-----|------|-------------|
| `field.name` | `str` | Field role name (e.g., "customer", "cost") |
| `field.type` | `Concept` | Field type (always resolved in v1) |
| `field.is_input` | `bool` | Whether field is an input field |
| `field.is_list` | `bool` | Whether field is list-valued |

### Quick Examples

```python
# List all concept names
for concept in model.concepts:
    print(concept)

# Lookup by name
Order = model.concept_index["Order"]

# Find all properties/relationships on a concept
order_rels = [r for r in model.relationships if any(
    str(f.type) == "Order" for f in r
)]

# Check what tables are loaded
for table in model.tables:
    print(table)
```

For detailed introspection patterns (classification, property maps, data inspection), see [joins-and-export.md](references/joins-and-export.md) § Schema Introspection Reference.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Dot-chain returns ALL related entities, not filtered ones | `.uses.id` in `select` creates independent lookup, ignoring `where` bindings | Use bound concept in select (`Asset.id`) or chain through application (`Employee.uses(Asset).id`) |
| Empty DataFrame from query | Missing `define()` for computed values, or `.new()` matched no rows | Verify entities exist and derived values are `define()`d before querying |
| `ValidationError: Unused variable` | Same concept ref reused in independent aggregation contexts | Use separate named refs (`Customer.ref("t1")`, `Customer.ref("t2")`) |
| Duplicate rows in aggregation results | Missing `distinct()` wrapper | Wrap `select(distinct(...))` — ALL columns must be inside `distinct()` |
| Grouped aggregation returns N rows instead of grouped rows | Grouping by a property value without `distinct()` | Use `select(distinct(property.alias(...), agg.per(property).alias(...)))` — see Grouped Aggregation pattern above |
| Subtype query returns TyperError | Accessing properties directly on subtype (`m.Subtype.prop`) | Bind subtype to parent: `m.where(m.Subtype(m.Parent)).select(m.Parent.prop.alias(...))` |
| `rai.count(m.SubtypeName)` in bare select fails | Counting subtype directly without parent binding | Use `m.select(rai.count(m.Parent).alias("n")).where(m.Subtype(m.Parent))` |
| Mixing bare select with distinct | `select(X.name, distinct(X.cat))` — can't mix | Either wrap ALL columns in `distinct()` or none |
| `.where()` on wrong target | Calling `.where()` directly on a Concept (`Site.where(...)`) | `.where()` goes on aggregations, constraints, definitions, or queries — not on bare concepts |
| Using standalone `where()`/`select()` with multiple models | `"Multiple Models have been defined."` error | Use `model.where()`/`model.select()` instead of standalone imports |
| Aggregation returns empty DataFrame instead of zero | `aggs.count(X).where(no_match)` returns no rows, not a row with 0 | Use `\| 0` default: `aggs.count(Shipment).where(Shipment.supplier.name == "foo") \| 0` |

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Aggregation queries | `model.select()`, `.alias()`, `sum/count` with `.per()`, multi-hop joins, `.to_df()` | [examples/aggregation_queries.py](examples/aggregation_queries.py) |
| Computed properties | `std.datetime` arithmetic, enum-subconcept segmentation, argmax with tiebreaker | [examples/jaffle_computed.py](examples/jaffle_computed.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Joins & export | Multi-concept joins, reusable query fragments, Snowflake write-back | [joins-and-export.md](references/joins-and-export.md) |
