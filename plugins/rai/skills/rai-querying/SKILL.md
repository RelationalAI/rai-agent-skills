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

**`print(expr)`** — shows the PyRel structure of an expression, concept, or relationship without executing a query. Use to verify expression composition before running:

```python
print(Order.customer)                          # → Order.customer
print(aggs.sum(Order.total).per(Customer))     # → (sum Order.total (per Customer))
print(model.where(Order.status == "active"))   # → (where Order.status == 'active')
```

**`.inspect()`** — convenience for debugging; executes the query and prints the DataFrame to stdout. Equivalent to `print(rel.to_df())`.

```python
Shipment.supplier.inspect()  # Quick check of a relationship's contents
```

**`distinct(...)`** — deduplicate result rows. Frequently needed with aggregations to prevent validation errors.

All columns in a `select()` must be either all inside `distinct()` or all outside — mixing causes a runtime error. Grouped aggregation queries (grouping by a property value, not an entity) require `distinct()` to get one row per group; without it, PyRel returns one row per entity with duplicated aggregation values.

**When to use `distinct()`:**
- Grouping by a **property value** (e.g., `weather_condition`, `category`): use `distinct()` — without it you get duplicated rows
- Grouping by an **entity concept** (e.g., `.per(Customer)`): usually not needed, since each entity is already unique
- Grouping by a **mix of entity and property value** (e.g., `.per(Supplier, Dest.region)`): treat as property-value grouping — use `distinct()`
- Deduplicating rows from multi-hop joins: use `distinct()`

For detailed `distinct()` code examples (multi-column, grouped aggregation, common mistakes), see [distinct-patterns.md](references/distinct-patterns.md).

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

# WILL RAISE NotImplementedError if used in problem.satisfy() or problem.minimize/maximize
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

**Advanced aggregation:** Conditional `.where()` on aggregates (subquery filters), `per(group).sum(expr)` standalone form, and conditional `count(X, condition)`.
See [aggregation-advanced.md](references/aggregation-advanced.md) for examples.

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
    aggs.count(Asset).alias("count"),
).where(
    UnderutilizedAsset(Asset),
).to_df()

# WRONG — counting subtype directly causes TyperError
# results = model.select(aggs.count(UnderutilizedAsset).alias("count")).to_df()
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

**`not_()` — grouped vs. separate negation:**

```python
# NOT (A AND B):
model.not_(Person.pets, Person.pets.name == "boots")
# (NOT A) AND (NOT B):
model.not_(Person.pets), model.not_(Person.pets.name == "boots")
```

**`model.union()` vs `|`:** `model.union()` collects ALL matching branches (set union / OR-filter). `|` evaluates left-to-right and picks the first that succeeds (ordered fallback / if-then-else). Use `|` for defaults and case-when chains; use `model.union()` for OR-filtering. For full semantics, see `rai-pyrel-coding/expression-rules.md`.

For extended `not_()` examples, `union()` patterns, and the HAVING equivalent, see [filtering-advanced.md](references/filtering-advanced.md).

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

**In solver context:** `problem.satisfy(model.require(expr))` promotes the requirement to a solver constraint:

```python
problem.satisfy(model.require(supply >= demand))  # hard constraint in the solver
```

---

## Model Introspection

`relationalai.semantics.inspect` (v1.0.14+) is the recommended public API for discovering model structure at runtime:

- `inspect.schema(model)` — full frozen `ModelSchema` with concepts, properties (including inherited), relationships, tables, inline data sources, enums, and rules. Supports `ms["Person"]` dict-style access and `ms.to_dict()` for JSON-safe serialization.
- `inspect.fields(rel)` — `tuple[FieldRef, ...]` usable directly in `select(*inspect.fields(rel))`; handles inheritance and alt readings.
- `inspect.to_concept(obj)` — resolve any DSL handle (Chain, Ref, FieldRef, Expression) to its underlying `Concept`.

Use inspect-before-authoring to catch duplicate/hallucinated properties, inspect-after-scaffolding to verify what actually registered, and re-inspect after long sessions or `/compact` to avoid acting on stale mental models. See [inspect-module.md](references/inspect-module.md).

Lower-level `model.concepts` / `model.relationships` / `model.tables` / `model.data_items` remain available as a fallback — see [model-introspection.md](references/model-introspection.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Dot-chain returns ALL related entities, not filtered ones | `.uses.id` in `select` creates independent lookup, ignoring `where` bindings | Use bound concept in select (`Asset.id`) or chain through application (`Employee.uses(Asset).id`) |
| Empty DataFrame from query | Missing `define()` for computed values, or `.new()` matched no rows | Verify entities exist and derived values are `define()`d before querying |
| `ValidationError: Unused variable` | Same concept ref reused in independent aggregation contexts | Use separate named refs (`Customer.ref("t1")`, `Customer.ref("t2")`) |
| Duplicate rows in aggregation results | Missing `distinct()` wrapper | Wrap `select(distinct(...))` — ALL columns must be inside `distinct()` |
| Grouped aggregation returns N rows instead of grouped rows | Grouping by a property value without `distinct()` | Use `select(distinct(property.alias(...), agg.per(property).alias(...)))` — see Grouped Aggregation pattern above |
| Subtype query returns TypeError | Accessing properties directly on subtype (`model.Subtype.prop`) | Bind subtype to parent: `model.where(model.Subtype(model.Parent)).select(model.Parent.prop.alias(...))` |
| `aggs.count(model.SubtypeName)` in bare select fails | Counting subtype directly without parent binding | Use `model.select(aggs.count(model.Parent).alias("n")).where(model.Subtype(model.Parent))` |
| Mixing bare select with distinct | `select(X.name, distinct(X.cat))` — can't mix | Either wrap ALL columns in `distinct()` or none |
| `.where()` on wrong target | Calling `.where()` directly on a Concept (`Site.where(...)`) | `.where()` goes on aggregations, constraints, definitions, or queries — not on bare concepts |
| Using standalone `where()`/`select()` with multiple models | `"Multiple Models have been defined."` error | Use `model.where()`/`model.select()` instead of standalone imports |
| Aggregation returns empty DataFrame instead of zero | `aggs.count(X).where(no_match)` returns no rows, not a row with 0 | Use `\| 0` default: `aggs.count(Shipment).where(Shipment.supplier.name == "foo") \| 0` |
| `.exists()` on Properties raises error | `Concept.prop.exists()` — `RAIException: Cannot access relationships on core concept 'Float'.` | Use ref binding: `r = Float.ref(); model.where(Concept.prop(r)).select(r.alias("val"))` |
| Inflated aggregation from multi-relationship select | Binding two relationships through the same concept in one `select` (e.g., `A.r1(C)` and `B.r2(C)`) creates a cartesian product of matching pairs — aggregation counts silently wrong | Split into separate queries per relationship, or pre-aggregate with derived properties. This is distinct from prescriptive cross-product concepts — it applies to any `select` with multiple join paths through a shared concept |
| Silent column renaming (`_2`, `_3` suffixes) | Two concepts in a query share a property name (e.g., both have `.name`) — `to_df()` silently appends `_2` to disambiguate | Always apply `.alias()` to every selected property. Without explicit aliases, downstream code referencing the original column name gets wrong data or `KeyError` |

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Aggregation queries | `model.select()`, `.alias()`, `sum/count` with `.per()`, multi-hop joins, `.to_df()` | [examples/aggregation_queries.py](examples/aggregation_queries.py) |
| Computed properties | `std.datetime` arithmetic, enum-subconcept segmentation, argmax with tiebreaker | [examples/datetime_argmax_segmentation.py](examples/datetime_argmax_segmentation.py) |
| `inspect.schema()` summary | Dump registered concepts/properties, dict-style access, does-property-exist check, JSON-safe `to_dict()` | [examples/inspect_schema_summary.py](examples/inspect_schema_summary.py) |
| `inspect.fields()` unpack | `select(*inspect.fields(rel))` canonical idiom + `include_owner=True` variant | [examples/inspect_fields_unpack.py](examples/inspect_fields_unpack.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Joins & export | Multi-concept joins, reusable query fragments, Snowflake write-back | [joins-and-export.md](references/joins-and-export.md) |
| Distinct patterns | Code examples for `distinct()` usage in select queries | [distinct-patterns.md](references/distinct-patterns.md) |
| Advanced aggregation | Conditional `.where()` on aggregates, `per().sum()` standalone, conditional count | [aggregation-advanced.md](references/aggregation-advanced.md) |
| Advanced filtering | Extended `not_()` examples, `union()` patterns, HAVING equivalent | [filtering-advanced.md](references/filtering-advanced.md) |
| `inspect` module | Public model-introspection API: `inspect.schema`, `inspect.fields`, `inspect.to_concept` | [inspect-module.md](references/inspect-module.md) |
| Model introspection (lower level) | `model.concepts`/`relationships`/`tables`/`data_items` fallback API | [model-introspection.md](references/model-introspection.md) |
