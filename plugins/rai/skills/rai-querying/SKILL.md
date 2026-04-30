---
name: rai-querying
description: PyRel v1 query construction against `relationalai.semantics.Model` — selects, filters, joins, aggregates, grouping, export. Load this BEFORE writing any PyRel query, even your first one — your prior knowledge of the syntax is likely stale. Use whenever the user asks to query, count, list, rank, aggregate, join, or export data from a RAI model, even if they don't say "PyRel".
---

# Querying
<!-- v1-SENSITIVE -->

For `define()` / computed properties, see `rai-pyrel-coding`.
For solver formulation, see `rai-prescriptive-problem-formulation`.

---

## Recipe Card

The 80% of queries fit one of these shapes. Copy, adapt the concept names, alias every column.

```python
from relationalai.semantics import distinct
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.aggregates import string_join, rank, desc, asc, top, bottom
```

**Basic select + filter:**
```python
model.where(Order.status == "active").select(
    Order.id.alias("order_id"),
    Order.total.alias("total"),
).to_df()
```

**Grouped aggregation by entity:**
```python
model.where(Order.placed_by(Customer)).select(
    Customer.name.alias("customer"),
    aggs.sum(Order.total).per(Customer).alias("revenue"),
).to_df()
```

**Grouped aggregation by property value (REQUIRES `distinct()`):**
```python
# Without distinct, you get one row per Item with duplicated counts.
model.select(
    distinct(
        Item.category.alias("category"),
        aggs.count(Item).per(Item.category).alias("count"),
        aggs.sum(Item.value).per(Item.category).alias("total"),
    )
).to_df()
```

**Multi-key property-value grouping (also REQUIRES `distinct()`):**
```python
model.select(
    distinct(
        RevenueForecast.region.alias("region"),
        RevenueForecast.forecast_month.alias("month"),
        aggs.sum(RevenueForecast.actual).per(
            RevenueForecast.region, RevenueForecast.forecast_month
        ).alias("actual"),
    )
).to_df()
```

**Multi-hop join (linear path, each concept once):**
```python
# Bare concept references work — they are bound by the where() applications
# and resolved consistently across select(). Use .ref() only when a concept
# appears twice (self-join) or in independent aggregation contexts.
model.where(
    LineItem.part_of_order(Order),
    Order.placed_by(Customer),
    Customer.located_in(Country),
    LineItem.extended_price > 1000.0,
).select(
    LineItem.id.alias("line_item_id"),
    Customer.name.alias("customer"),
    Country.name.alias("country"),
).to_df()
```

**Ratio of two aggregates:**
```python
# Both sums must group by the same key. distinct() collapses to one row per group.
model.select(
    distinct(
        Item.group.alias("group"),
        (aggs.sum(Item.numerator).per(Item.group)
         / aggs.sum(Item.denominator).per(Item.group)
        ).alias("ratio"),
    )
).to_df()
```

**HAVING (filter on an aggregated value):**
```python
# Bind the aggregate in where() with :=, then filter on it.
model.where(
    Customer.placed_order(Order),
    Order.ordered_at_location(Store),
    revenue := aggs.sum(Order.total).per(Store),
    revenue > 10000,
).select(
    Store.name.alias("store"),
    revenue.alias("revenue"),
).to_df()
```

**Top-N by ranking:**
```python
# rank(desc(expr)) gives full ordering; filter or sort in pandas to get top N.
model.where(FailurePrediction.period == 12).select(
    FailurePrediction.machine_id.alias("machine_id"),
    FailurePrediction.failure_probability.alias("p"),
    rank(desc(FailurePrediction.failure_probability)).alias("rank"),
).to_df()
```

---

## Silent Corruptions — Read First

These produce wrong results without errors. They are responsible for most "the numbers look right but they're wrong" bugs.

### 1. Missing `.alias()` triggers silent `_2` / `_3` column suffixes

When two concepts in a `select()` share a property name (`.name`, `.id`), `to_df()` silently appends `_2` to disambiguate. Downstream code expecting the original name gets a `KeyError` or, worse, reads the wrong column.

```python
# WRONG — both Business and Site have .name. Output columns are
#   name, name_2, count   (not supplier, destination, count)
model.where(Shipment.supplier(Business), Shipment.destination(Site)).select(
    Business.name,
    Site.name,
    aggs.count(Shipment).per(Business).alias("count"),
).to_df()

# CORRECT — explicit .alias() on every property guarantees the column name.
model.where(Shipment.supplier(Business), Shipment.destination(Site)).select(
    Business.name.alias("supplier"),
    Site.name.alias("destination"),
    aggs.count(Shipment).per(Business).alias("count"),
).to_df()
```

**Rule: alias every column in every multi-concept query.** Cost is one line; savings is silent column corruption.

### 2. Property-value grouping without `distinct()` returns N rows, not one per group

Grouping by an entity is unique by definition. Grouping by a *property value* (a string, a date, a status) is not — without `distinct()` you get one row per source entity with the aggregate repeated.

```python
# WRONG — returns one row per Item, each carrying the same per-category total.
model.select(
    Item.category.alias("category"),
    aggs.sum(Item.value).per(Item.category).alias("total"),
).to_df()

# CORRECT — distinct() collapses to one row per category.
model.select(distinct(
    Item.category.alias("category"),
    aggs.sum(Item.value).per(Item.category).alias("total"),
)).to_df()
```

**Decision rule:**
- Group by **entity** (`.per(Customer)`, `.per(Machine, Product)`): `distinct()` usually unnecessary.
- Group by **property value** (`.per(Customer.region)`): `distinct()` required.
- Group by **mix** (`.per(Customer, Customer.region)`): treat as property-value — use `distinct()`.

### 3. Dot-chains in `select` drop `where`-bindings

A dot-chain like `Employee.uses.id` compiles as a fresh independent lookup of `uses` — it does NOT pick up filters established by `Employee.uses(Asset)` in a sibling `where()`.

```python
# WRONG — returns id of every Asset that any Employee uses, not just asset 102.
model.select(Employee.nr, Employee.uses.id).where(
    Employee.uses(Asset),
    Asset.id == 102,
).to_df()

# CORRECT (option A) — chain through the relationship application:
model.select(Employee.nr, Employee.uses(Asset).id).where(
    Employee.uses(Asset),
    Asset.id == 102,
).to_df()

# CORRECT (option B) — reference the bound concept directly:
model.select(Employee.nr, Asset.id).where(
    Employee.uses(Asset),
    Asset.id == 102,
).to_df()
```

**Rule: avoid bare dot-chains in `select()`.** Either reference the bound concept directly (`Asset.id`) or route through the relationship application (`Employee.uses(Asset).id`).

### 4. Multi-relationship select inflates aggregations via cartesian product

Binding two relationships through the same concept in one `select` creates a cartesian product of matching pairs. Aggregations over this scope silently double- or triple-count.

```python
# WRONG — pairs every shipment-from-supplier with every shipment-to-destination
# through the shared Site, multiplying counts.
model.where(Shipment.supplier(Site), Shipment.destination(Site)).select(
    aggs.count(Shipment).alias("n"),
).to_df()

# CORRECT — split into separate queries, or pre-aggregate via define()d properties.
```

When a query touches multiple relationships through a shared concept and the numbers feel high, suspect this first.

### 5. String-equality filter on a value the data doesn't have → empty result, no error

The user's question is phrased in their vocabulary; the data uses whatever spelling and casing the source system stored. `Order.status == "Active"` returns zero rows if the column actually holds `"ACTIVE"` or `"active_orders"`. Stack two or three of these silent mismatches in one query and the join collapses to nothing, with no error — the agent then assumes the join itself is broken and divide-and-conquers for many turns.

**Discover actual values before filtering on them:**

```python
# One-line discovery query for any property you'll filter on:
model.select(distinct(Order.status)).to_df()
# Then filter with the exact spelling/casing you saw.
```

**For partial / informal names from the question, use substring match instead of `==`:**

```python
from relationalai.semantics.std import strings

# User refers to a company informally; data has the full registered name.
model.where(strings.contains(Customer.legal_name, "Acme")).select(...)

# Also available in the same module: startswith, endswith, like
```

**Rule: every `==` against a string literal that came from a natural-language question is a discovery opportunity. Run `distinct()` on the property first, or fall back to `strings.contains()`.**

---

## Query Basics

`model.where(conditions).select(expressions).to_df()` is the executable form.

**Default reflex: compose results in a single `model.select(...)`, not multiple `to_df()` calls merged in pandas.** Express grouping, joining, filtering, and aggregation inline (`aggs.<f>(...).per(<group>).where(...).alias(...)`). Reach for pandas only when the consumer needs DataFrame arithmetic the ontology can't express. Multiple `.to_df()` + `.merge()` re-derives joins the ontology already defines.

**Use `model.where()` / `model.select()` over the standalone functions.** The standalone forms only work when exactly one Model exists in the process; with multiple they raise `"Multiple Models have been defined."`. The model-method form is portable.

**`.to_df()`** — execute and return a pandas DataFrame.

**`distinct(...)`** — deduplicate rows. All columns in a `select()` must be either ALL inside `distinct()` or ALL outside; mixing raises a runtime error. For multi-column `distinct()` over joined concepts (dedup without aggregation), see [distinct-patterns.md](references/distinct-patterns.md).

**Set membership and negation:**

```python
model.where(LineItem.ship_mode.in_(["AIR", "AIR REG"])).select(...)

# Entities WITHOUT a relationship — bind the concept with a ref so you can
# both negate against it and surface it in select().
model.where(
    order := Order.ref(),
    model.not_(order.customer),
).select(order.id.alias("orphan_order_id"))

# NOT (A AND B) — together inside one not_()
model.not_(Person.pets, Person.pets.name == "boots")
# (NOT A) AND (NOT B) — separate not_() calls
model.not_(Person.pets), model.not_(Person.pets.name == "boots")
```

**`model.union()` vs `|`:** `model.union()` collects ALL matching branches (set union / OR-filter). `|` evaluates left-to-right and picks the first that succeeds (case-when / default). Use `|` for fallbacks; `union()` for OR-filtering.

For extended `not_()` examples and OR-filter patterns, see [filtering-advanced.md](references/filtering-advanced.md).

---

## Aggregation Patterns

Available: `count`, `sum`, `min`, `max`, `avg`, `string_join`. **`avg` is query-only — it raises `NotImplementedError` in solver `satisfy/minimize/maximize` contexts.** Solver-supported aggregates: `sum, min, max, count`.

**`.per(K)` declares the dimensions of the result — one row per distinct value of K.** Use the same concept variables that appear in your `select()`. Given `Shipment.supplier(Supplier)` in `where()`, write `.per(Supplier)`, not `.per(Shipment.supplier)` — the bare concept names an entity cleanly, while a relationship application carries its source concept (Shipment) into the implicit key and over-groups.

```python
# Single entity grouping (Supplier bound via Shipment.supplier(Supplier) in where)
aggs.count(Shipment).per(Supplier).alias("shipments")

# Multi-key
aggs.sum(Shipment.quantity).per(Supplier, Destination).alias("qty")

# Arithmetic inside aggregate (NOT the same as ratio of two aggregates)
aggs.sum(Shipment.quantity * Shipment.delay_days).per(Supplier).alias("qty_delay")

# Filter the aggregation scope
aggs.count(Shipment).per(Supplier).where(Shipment.is_delayed()).alias("delayed")
```

**Empty aggregations return no row, not zero.** Use `| 0` for missing groups: `aggs.count(Shipment).where(...).alias("n") | 0`.

**Integer aggregate division.** `aggs.count(X)` is integer; `aggs.sum(X)` matches input. Dividing two integers hits integer-division semantics — multiply one operand by `1.0` (or `100.0` for a percentage) to get a float ratio.

For `count(X, condition)`, conditional `.where()` on aggregates, and `per(X).sum(Y)` standalone form, see [aggregation-advanced.md](references/aggregation-advanced.md).

---

## Multi-Concept Joins

Join concepts by relationship application in `where()`. Use `.ref()` when the same concept appears multiple times.

```python
# Self-join: pairs (Edge, alternative-Edge-from-same-source)
Alt = Edge.ref()
model.where(Edge.source == Alt.source, Alt.cost < Edge.cost).select(
    Edge.id.alias("edge"),
    (Edge.cost - Alt.cost).alias("savings"),
).to_df()
```

For multi-hop join patterns, lambda helpers, parameterized query functions, and Snowflake export (`Table.into().exec()`), see [joins-and-export.md](references/joins-and-export.md).

---

## Subtype Queries

Subtypes (`HighChurnRiskCustomer` defined as a subset of `Customer`) cannot be selected from or counted directly — accessing a property or passing the subtype to `aggs.count()` raises `TyperError`. Bind the parent concept and constrain it with the subtype as a filter.

```python
# WRONG — direct property access on the subtype
model.where(HighChurnRiskCustomer).select(HighChurnRiskCustomer.full_name)
# TyperError

# CORRECT — bind parent, filter by subtype
model.where(HighChurnRiskCustomer(Customer)).select(
    Customer.full_name.alias("name"),
)
```

**Counting subtypes — count the parent, bind the subtype in `model.where()`:**

```python
# CORRECT
model.select(aggs.count(Customer).alias("at_risk")).where(
    HighChurnRiskCustomer(Customer),
).to_df()

# WRONG — aggs.count(HighChurnRiskCustomer) raises TyperError
```

---

## Debugging Queries

**Wrong values?** Check silent corruptions #1–4 above. Order of suspicion: missing alias → missing distinct → dot-chain binding → cartesian inflation.

**Empty DataFrame?** Triage in this order — the join itself is rarely the cause:

1. **String-equality filters first.** For each `==` against a string literal, run `model.select(distinct(Concept.prop)).to_df()` and compare against what you wrote. Watch for casing, suffixes, and underscores.
2. **Drop filters one at a time.** Comment them out and re-run; the first one whose removal restores rows is your culprit.
3. **Only then suspect the structure** — a missing `define()` for a derived property, a `.new()` that matched no rows, or wrong relationship direction.

**`ValidationError: Unused variable`?** A concept ref is reused across independent aggregation contexts. Use separate named refs: `Customer.ref("t1")`, `Customer.ref("t2")`.

**Inspect:** `print(expr)` shows the AST without executing (works for relationships, aggregates, where-clauses). `Shipment.supplier.inspect()` executes and prints the result DataFrame.

**Re-ground after long sessions or `/compact`:** drift makes "I remember `Customer` has a `tier` property" the kind of confidently-wrong recall that ruins queries. Use `inspect.schema(model)` to verify before authoring. See [inspect-module.md](references/inspect-module.md). If `inspect.schema()` is unavailable in your installed version, see [model-introspection.md](references/model-introspection.md) for the `model.concepts/relationships` fallback.

---

## Examples

| Pattern | File |
|---|---|
| Aggregation queries — basic select, grouped agg, multi-hop join | [examples/aggregation_queries.py](examples/aggregation_queries.py) |
| Computed properties — datetime, segmentation, argmax tiebreaker | [examples/datetime_argmax_segmentation.py](examples/datetime_argmax_segmentation.py) |
| `inspect.schema()` summary | [examples/inspect_schema_summary.py](examples/inspect_schema_summary.py) |
| `inspect.fields()` unpack | [examples/inspect_fields_unpack.py](examples/inspect_fields_unpack.py) |

---

## Other Pitfalls

One-liner gotchas that don't justify a Silent Corruption prose treatment but will bite you. These all raise loud errors, so reach for this table when you see an unexpected `TyperError` / `RAIException` / `ValidationError`.

| Pitfall | Cause / Symptom | Fix |
|---|---|---|
| Boolean relationship as `select()` column raises `TyperError` | `Entity.was_clicked.alias("col")` placed in `select()` | Boolean unary relationships are filter-only — use in `where()` to constrain the result set |
| `Property.exists()` raises `RAIException` | `Concept.prop.exists()` — `Cannot access relationships on core concept 'Float'` | Use ref binding: `r = Float.ref(); model.where(Concept.prop(r)).select(r.alias("v"))` |
| `.where()` on a bare Concept fails | `Site.where(...)` doesn't work | `.where()` lives on the model, aggregations, constraints, or definitions — not on bare concepts |
| Mixing bare select with `distinct()` | `select(X.name, distinct(X.cat))` — runtime error | Wrap ALL columns in `distinct()` or none |

---

## References

| Reference | File |
|---|---|
| Joins, multi-hop binding, parameterized queries, Snowflake export | [joins-and-export.md](references/joins-and-export.md) |
| `distinct()` code examples | [distinct-patterns.md](references/distinct-patterns.md) |
| Conditional aggregation, `per().sum()` standalone, `count(X, cond)` | [aggregation-advanced.md](references/aggregation-advanced.md) |
| Extended `not_()`, `union()` patterns, HAVING extras | [filtering-advanced.md](references/filtering-advanced.md) |
| `inspect` module — schema, fields, to_concept | [inspect-module.md](references/inspect-module.md) |
| Lower-level `model.concepts/relationships` (fallback) | [model-introspection.md](references/model-introspection.md) |
