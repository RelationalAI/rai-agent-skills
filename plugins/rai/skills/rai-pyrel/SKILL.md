---
name: rai-pyrel
description: PyRel v1 language — modeling syntax (concepts, properties, relationships, data loading), business rules as derived properties (validation, classification, tiers, flags), and query construction against `relationalai.semantics.Model` (selects, filters, joins, aggregates, export). Load BEFORE writing any PyRel code, even your first line — prior knowledge of the syntax is likely stale. Use whenever the user asks to model, load, derive, classify, flag, query, count, rank, aggregate, join, or export data from a RAI model, even if they don't say PyRel. Not for ontology design decisions (see rai-ontology), optimization formulation (see rai-prescriptive-problem), graph algorithms (see rai-graph-analysis), or GNN work (see rai-predictive-modeling).
---

# PyRel
<!-- v1-SENSITIVE -->

## Summary

**What:** The PyRel v1 language surface — types, concepts, properties, relationships, data loading, expressions, derived-property business rules, and query construction.

**When to use:**
- Writing or reviewing any PyRel model code; looking up imports, types, or declaration patterns
- Translating a business rule to PyRel ("flag high-value customers", tiers, segments, scores) — see [Rules Authoring](#rules-authoring)
- Querying: select, filter, join, aggregate, rank, export — see [Querying](#querying)
- Debugging syntax errors, `FDError`, `Unground Variables`, or empty/unexpected results

**When NOT to use:** reasoner-specific tasks route to their reasoner skill — it owns the patterns and pitfalls:
- Ontology design decisions (concept vs property, identity, data mapping, enrichment) — see `rai-ontology`
- Optimization formulation (decision variables, constraints, objectives) — see `rai-prescriptive-problem`
- Graph analysis (centrality, community, reachability, paths) — see `rai-graph-analysis`
- GNN modeling and training — see `rai-predictive-modeling`, `rai-predictive-training`
- Reasoner routing and question discovery — see `rai-discovery`; connection/config — see `rai-setup`

**Overview:** Modeling declares the surface (concepts, properties, relationships); [Definitions](#definitions) bake business logic into the model; [Rules Authoring](#rules-authoring) is the workflow for deriving new properties from natural-language rules; [Querying](#querying) reads it all back. Most logic belongs in definitions — queries should be simple reads over what definitions computed.

---

## Quick Reference

```python
from relationalai.semantics import (
    Model, Float, Integer, String, Date, DateTime, distinct,
)
from relationalai.semantics import Number            # always Number.size(p,s), never bare
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.std.aggregates import rank, desc, asc, top, bottom
from relationalai.semantics.std import strings, math, numbers

model = Model("my_model")
Product = model.Concept("Product", identify_by={"id": Integer})
Product.cost = model.Property(f"{Product} has {Float:cost}")            # many-to-one
Product.supplier = model.Property(f"{Product} supplied by {Supplier:supplier}")  # functional FK
model.define(Product.new(model.data(df).to_schema()))                   # load data
result = model.where(Product.cost > 10).select(Product.id, Product.cost).to_df()
print(Product.cost > 10)      # readable repr — verify structure before querying
Product.cost.inspect()        # executes, prints DataFrame
```

| Rule type | Output | Canonical pattern |
|-----------|--------|-------------------|
| **Validation** | unary `Relationship` | `model.where(cond).define(Entity.is_valid())` |
| **Classification** | subtype via `extends` | `model.define(HighValue(Entity)).where(Entity.score > t)` |
| **Derivation** | `Property` | `model.define(Entity.total(aggs.sum(Child.val).per(Entity)))` |
| **Alerting** | unary `Relationship` | `model.where(model.not_(E.resolved), elapsed > limit).define(E.is_breach())` |
| **Reconciliation** | `Property` delta + flag | `define(M.delta(A.v - B.v))`, then `where(math.abs(M.delta) > tol).define(M.has_discrepancy())` |

For solver formulation (`Problem`, `solve_for`, `satisfy`, minimize/maximize) see `rai-prescriptive-problem`; for CSP-style formulation see its `references/csp-formulation.md`.

---

## Modeling

### Model patterns

`model = Model("my_model")` — params: `name`, `config` (auto-discovers `raiconfig.yaml`), `exclude_core`, `is_library`. **Always use the model-method forms** `model.define()/where()/select()` — standalone `define()`/`where()`/`select()` fail when multiple Models exist. Define models at module level (tooling needs them at import time); reasoner-specific code goes in functions that receive the model. For imports beyond Quick Reference (reasoners, `std`, builtin shadowing), see [imports.md](references/imports.md).

### Type system

Types are imported objects used in Property f-strings: `{Type:field}` — type BEFORE the field name.

| Type | Usage | Python |
|------|-------|--------|
| `Float` / `Integer` / `String` / `Boolean` | `{Float:cost}` | float / int / str / bool |
| `Number.size(p,s)` | `{Number.size(38,4):price}` | decimal(p,s) |
| `Date` / `DateTime` | `{Date:due}` / `{DateTime:ts}` | date / datetime |

Bare `Number` (unparameterized) causes type-inference issues — always `Number.size(p, s)`; never call `Number(38, 4)` directly and never use the deprecated `decimal` alias. When loading from Snowflake, the property type must match the column's actual type — see `rai-ontology` § Data Mapping Guidance for the mapping table; a mismatch raises `TyperError` at query time that blocks all queries on the model.

### Properties and Relationships

The choice is about **multiplicity**; both support any arity. **Property** enforces a functional dependency — all fields except the last are keys, the last is the unique value. Use for **many-to-one**: scalar attributes, functional concept-to-concept FKs, unary flags, N-ary with FD. **Relationship** has no uniqueness constraint. Use for **many-to-many**. Full design treatment (FD semantics, junction concepts, hyper edges, solver safety): `rai-ontology` § Relationship Principles.

```python
Food.cost = model.Property(f"{Food} has {Float:cost}")                        # scalar
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")     # functional FK
Order.is_rush = model.Property(f"{Order} is rush order")                      # unary flag
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")  # ternary w/ FD
Stock.covar = model.Property(f"{Stock:stock1} and {Stock:stock2} have {Float:covar}")  # same-type slots need names
Parent.has_child = model.Relationship(f"{Parent} has {Child}")                # one-to-many
Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")  # many-to-many
x = model.Relationship(f"{Float:x}")                                          # standalone scalar variable
```

- The property name is the f-string **field name** (`qty` in `{Float:qty}`), not the verb.
- **Never pass `short_name=`** — PyRel derives it from the LHS attribute; a mismatched one fails with `[Invalid short name]`, and invoking via an alternate name silently creates a parallel implicit Property (NaN reads, `TyperError` joins). Needed only for `relationship_index` lookup and same-type-slot disambiguation. See [common-pitfalls.md](references/common-pitfalls.md).
- **Reserved attribute names** (`ref`, `new`, `select`, `where`, `define`, `filter_by`, `identify_by`, …) raise `[Reserved relationship name]` — rename the attribute (`deploy_ref`), the source column can stay. Full list in [common-pitfalls.md](references/common-pitfalls.md).
- **Dynamic Property names need `setattr`**: `getattr(Concept, attr)` may surface as `Any` in `solve_for(...)` — bind explicitly with `setattr(Concept, attr, prop)`.
- Global counts: assign to a Python variable (`NODE_COUNT = count(Node)`); use a model Relationship only when downstream `define()` rules or solver expressions need the value.

### Concepts

```python
Food = model.Concept("Food", identify_by={"name": String})       # PREFERRED: typed natural key
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})   # composite key
OrderItem = model.Concept("OrderItem", identify_by={"order": Order, "item": Item})  # junction
ActiveOrder = model.Concept("ActiveOrder", extends=[Order])      # subtype — inherits parent properties
model.define(ActiveOrder(Order)).where(Order.total > 75)         # populate membership
PositiveInt = model.Concept("PositiveInt", extends=[Integer])    # extending a primitive: no identify_by
```

- **Always include `identify_by` whenever possible** — entities with the same key values are the same instance. Without it, ALL `.new()` parameters hash into identity, so adding/removing a parameter silently changes identity.
- **`identify_by` auto-creates the identity properties** — do not also declare `model.Property()` for them (duplicate).
- `model.Concept(name, extends=[Parent])` takes a plain name — a reading f-string here creates an *unrelated* concept and `define(Sub(Entity))` raises `[TypeMismatch]`. Reading f-strings belong to Property/Relationship only.
- **Introspection:** `inspect.schema(model)` (v1.0.14+) returns concepts, inherited properties, types, and data sources; `inspect.to_concept(obj)` accepts any DSL handle. See [inspect-module.md](references/inspect-module.md); older-version fallback in [model-introspection.md](references/model-introspection.md).

### Enums

`model.Enum` creates a concept-backed enum whose members work as literals in `where()`/`define()` and (relationalai>=1.12) in every value position: kwargs, enum-typed property values, and `solve_for()`/`satisfy()` expressions. Use for fixed, closed vocabularies; leave open-ended data-driven strings as `String`.

```python
class Priority(model.Enum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"
Priority = model.Enum("Priority", ["low", "medium", "high"])   # functional form
```

Access via `model.Enum` (not a standalone import). Integer members, CSV-to-member `lookup()` caveats, member-name readback, and the class-vs-member `TypeError`: [expression-rules.md](references/expression-rules.md#enums).

### Data loading

| API | Purpose |
|-----|---------|
| `model.data(df)` + `.to_schema()` | Wrap a DataFrame; auto-map columns to matching Property names (`exclude=[]`) |
| `model.Table("DB.SCHEMA.TABLE")` | Reference a Snowflake table (production path) |
| `Concept.lookup(prop=value)` | FK resolution — fresh reference to the matching entity; no match → no row (replaces deprecated `filter_by`) |
| `Concept.to_identity(key=value)` | Strict lookup — raises if not exactly one match |
| `Concept.new(key=value)` | Create entities (identity properties as kwargs) |
| `std.common.range(n)` | Integer range 0..n-1 |

```python
model.define(Food.new(model.data(csv).to_schema()))                       # auto-map
food_data = model.data(read_csv("foods.csv"))                             # explicit map
model.define(food := Food.new(name=food_data.name), food.cost(food_data.cost))
```

Snowflake tables follow the same `model.Table(...)` + `lookup`/`define` pattern. FK binding, column casing/renaming, `to_schema()` rules, unary flags, optional vs required columns: [data-loading.md](references/data-loading.md). Strategy (authoritative vs joinable sources): `rai-ontology`. Auth: `rai-setup`.

---

## Definitions

Definitions are the core of PyRel: bake business logic into the model so every query and solver formulation can leverage it. **Most logic should live in definitions; queries should be simple reads.**

```python
model.define(Order.total(Order.quantity * Order.unit_price))          # computed property
model.define(Shipment.is_delayed()).where(Shipment.delay_days > 0)    # boolean flag
model.define(OrderItem.new(order=Order, item=Item)).where(Order.contains(Item))  # entity creation
model.define(Order.priority_label("high")).where(Order.total > 1000)  # multi-branch
model.define(Order.priority_label("low")).where(Order.total <= 1000)

# Aggregated metric materialized onto entities — .per() inside define()
model.where(
    Operation.destination_site(op, site), Operation.type(op, "SHIP")
).define(Site.count_is_destination(site, aggs.count(op).per(site)))
```

`model.where(...).define(...)` and `model.define(...).where(...)` are both valid — use whichever reads naturally.

**The model is append-only.** Every `define()`/`Property()`/`Concept()`/`Relationship()` call ADDS; nothing removes or replaces. A "corrected" rule does not supersede the original — both stay active. To change an element, define a fresh model. Reasoner stacks (e.g. `Problem`) inherit this.

**Never loop `define()`/`require()` over rows.** One declarative call handles all matching entities; per-row loops create a rule per iteration (PyRel warns past 50 calls from one site):

```python
# BAD: for _, row in df.iterrows(): model.define(Product.new(name=row["name"]))
product_data = model.data(df)
model.define(Product.new(product_data.to_schema()))          # GOOD: one declarative call
limits = model.data(capacity_limits_df)
model.define(Site.lookup(id=limits.id).max_capacity(limits.cap))   # GOOD: join declaratively
```

---

## Expressions

### Boolean logic

Python's `and`/`or`/`not`/`if-else` raise `[Invalid operator]` in RAI expressions. Use `&`, `|`, `not_`:

| Python (wrong) | PyRel (correct) |
|----------------|-----------------|
| `a and b` | `(a) & (b)` — or multiple args in `.where()` (conjunction) |
| `a or b` | `(a) \| (b)` or `model.union(...)` — see below |
| `not x` | `model.not_(x)` — Python `~` raises `TypeError` |
| `if c else d` | `value \| fallback` (ordered fallback) or `.where(c)` |

**`|` vs `model.union()`** — the one distinction that silently changes results: `|` is an ordered fallback (first branch that succeeds — if-then-else; creates a flattenable `Match`); `model.union()` is set OR (collects ALL matching branches). Use `|` for defaults and case-when; `union()` for OR-filters and multi-term objectives. **All `union()` branches must return the same number of values** — a bare relation call returns 1, `where(...)` without `select()` returns 0; mixing raises `[Inconsistent branches]`.

### Property f-strings

Braces invoke `__format__()` on concept/type objects to resolve IDs. Escaped braces (`{{Shipment}}`) produce a plain string → `[Unknown Concept]` at solve. The `{{name:type}}` shorthand creates `Number(38,14)`, which `solve_for()` rejects — always `{Type:name}`.

### Free-Variable Scoping

**A PyRel statement is one logical rule: its head (`define`/`select`/`require`) and body (`where`) share logic variables by identity.** A bare `Concept` symbol is ONE free variable everywhere it appears in the chain — head, `.per(...)` key, inner `.where(...)`. Each `Concept.ref()` (and each `Concept.lookup(...)`) is a DIFFERENT variable of the same type; two variables unify only through explicit equality. A Concept-typed FK property (`Item.bin`) introduces its own anonymous variable over the linked concept.

A head variable the body leaves free cross-products over the whole concept → `FDError` or `Unground Variable`.

```python
# WRONG — Item.bin (anon var) and Bin (var over all bins) are independent: cartesian.
model.require(sum(Item.x_assigned).per(Item.bin) <= Bin.cap)
# RIGHT — outer where binds the FK to the Concept; bare references unify.
model.where(Item.bin == Bin).require(sum(Item.x_assigned).per(Bin) <= Bin.cap)

# Relationship-linked aggregation: inner .where ties rows to the SAME bare variable.
model.where(IL.demand > 0).require(
    sum(SM.alloc).per(IL).where(SM.dest_il(IL)) + IL.unmet == IL.demand)

# define(): bind the entity by keys with lookup under a walrus; reuse that ONE variable.
model.where(p := Period.lookup(region=src.REGION, month=src.MONTH)).define(
    p.metric_sum(aggs.sum(src.AMOUNT).per(p)))
```

**When `.ref()` is genuinely needed:** pairwise/quadratic constraints, self-joins inside aggregates, value binding from multiarity properties (`qty = Float.ref()`), and disambiguating independent aggregation contexts. Bare references already unify in single-clause `.per(Concept)` aggregates and cross-concept dimension joins. Use `.alias("name")` for readable output columns; walrus `:=` creates inline refs. Full patterns (named refs, `Float.ref()` binding, bracket notation, `Chain.ref()`/`.alt()`): [expression-rules.md](references/expression-rules.md#references-and-aliasing).

**Aggregates of decision variables can't be materialized as Properties** — `define(C.total(aggs.sum(DecisionVar).per(C)))` decouples the aggregate from the solver's symbolic graph (`ValueError: no decision variables`). Keep them INLINE in `.require(...)`; data-derived aggregates materialize fine.

---

## Querying

**Ground before writing any query:** (1) match the task to a [Recipe](#recipe-card) shape; (2) verify concept/property names with `inspect.schema(model)` — recall drifts, especially after long sessions or `/compact`; (3) for a relationship packing several fields, run `inspect.fields(Concept.rel)` first — reading-string prose words are NOT field names. Then write and execute; don't guess syntax from memory.

### Recipe Card

The 80% of queries fit these shapes. Copy, adapt names, **alias every column**.

```python
# Basic select + filter
model.where(Order.status == "active").select(
    Order.id.alias("order_id"), Order.total.alias("total")).to_df()

# Grouped aggregation by ENTITY
model.where(Order.placed_by(Customer)).select(
    Customer.name.alias("customer"),
    aggs.sum(Order.total).per(Customer).alias("revenue")).to_df()

# Grouped aggregation by PROPERTY VALUE — REQUIRES distinct()
model.select(distinct(
    Item.category.alias("category"),
    aggs.count(Item).per(Item.category).alias("count"),
    aggs.sum(Item.value).per(Item.category).alias("total"))).to_df()

# Multi-key property-value grouping — also REQUIRES distinct()
model.select(distinct(
    RF.region.alias("region"), RF.forecast_month.alias("month"),
    aggs.sum(RF.actual).per(RF.region, RF.forecast_month).alias("actual"))).to_df()

# Multi-hop join (linear path, each concept once — bare references bind via where)
model.where(
    LineItem.part_of_order(Order), Order.placed_by(Customer),
    Customer.located_in(Country), LineItem.extended_price > 1000.0,
).select(LineItem.id.alias("li"), Customer.name.alias("customer"),
         Country.name.alias("country")).to_df()

# Ratio of two aggregates (same group key; distinct collapses to one row per group)
model.select(distinct(
    Item.group.alias("group"),
    (aggs.sum(Item.num).per(Item.group) / aggs.sum(Item.den).per(Item.group)).alias("ratio"))).to_df()

# HAVING — bind the aggregate with :=, filter on it
model.where(
    Customer.placed_order(Order), Order.ordered_at_location(Store),
    revenue := aggs.sum(Order.total).per(Store), revenue > 10000,
).select(Store.name.alias("store"), revenue.alias("revenue")).to_df()

# Top-N (native, no pandas); rank value / inverse: rank(desc(e)) / bottom(N, e)
model.where(FailurePrediction.period == 12,
            top(5, FailurePrediction.failure_probability),
).select(FailurePrediction.machine_id.alias("m"),
         FailurePrediction.failure_probability.alias("p")).to_df()
```

### Silent Corruptions — Read First

These produce wrong results **without errors** — most "numbers look right but they're wrong" bugs.

1. **Missing `.alias()` → silent `_2`/`_3` suffixes.** Two concepts sharing a property name (`.name`, `.id`) in one `select()` get auto-suffixed columns; downstream code reads the wrong one. *Alias every column in every multi-concept query.*
2. **Property-value grouping without `distinct()` → N rows, not one per group.** Entity grouping (`.per(Customer)`) is unique by definition; property-value grouping (`.per(Customer.region)`) repeats the aggregate per source entity. Mixed keys (`.per(Customer, Customer.region)`) count as property-value. *distinct() required.*
3. **Dot-chains in `select` drop `where`-bindings.** `Employee.uses.id` compiles as a fresh independent lookup, ignoring `Employee.uses(Asset)` + `Asset.id == 102` in `where()`. *Reference the bound concept directly (`Asset.id`) or route through the application (`Employee.uses(Asset).id`).*
4. **Multi-relationship select cartesian-inflates aggregations.** Binding two relationships through one shared concept in a single select pairs every match with every match — counts double/triple. *Split into separate queries or pre-aggregate via `define()`d properties. When numbers feel high, suspect this first.*
5. **`.per(FK_property)` doesn't unify with the bound Concept.** `Order.customer` is an anonymous iterator, separate from `Customer` bound in `where(Order.customer(Customer))` — aggregating `.per(Order.customer)` while selecting `Customer.name` cartesian-multiplies. Looks like #2 but `distinct()` won't fix it. *Use the bare Concept as both select and `.per()` key.* (This is [Free-Variable Scoping](#free-variable-scoping) at query time.)
6. **String-equality on a value the data doesn't have → empty result, no error.** `Order.status == "Active"` returns zero rows when the data holds `"ACTIVE"`. Stacked mismatches collapse joins to nothing and send you debugging the join. *Every `==` against a string from a natural-language question is a discovery opportunity:* `model.select(distinct(Order.status)).to_df()` first, or `strings.contains(Customer.legal_name, "Acme")` (also `startswith`, `endswith`, `like`; full string/number/date helper list: [standard-library.md](references/standard-library.md)).
7. **One-to-many joins fan out — fix the grain before ranking.** An entity linked to many rows (per period, per version) multiplies across matches; rank/`limit` over the fanned scope repeats entities and computes per-entity metrics on the wrong row. *Decide the grain — filter to the intended row (`F.period == latest`) or aggregate the many side — before ranking. Expecting one row per entity? Verify `row_count == entity_count`.*

```python
# Corruption #5 in one line — WRONG then RIGHT:
aggs.sum(Order.amount).per(Order.customer)   # anon var: cartesian with selected Customer
aggs.sum(Order.amount).per(Customer)         # bare Concept unifies with where() binding
```

### Query basics

`model.where(conditions).select(expressions).to_df()`. **Default reflex: compose one `model.select(...)`** — grouping, joining, filtering, aggregation inline — not multiple `to_df()` calls merged in pandas (that re-derives joins the ontology already defines). Reach for pandas only when the consumer needs DataFrame arithmetic the ontology can't express.

- `distinct(...)`: ALL select columns inside it or ALL outside — mixing raises. Multi-column dedup: [distinct-patterns.md](references/distinct-patterns.md).
- Set membership: `LineItem.ship_mode.in_(["AIR", "AIR REG"])`. Negation: `model.not_(...)` — entities WITHOUT a relationship need a ref: `order := Order.ref(), model.not_(order.customer)`. `not_(A, B)` = NOT(A AND B); separate calls = (NOT A) AND (NOT B). Extended patterns: [filtering-advanced.md](references/filtering-advanced.md).

### Aggregation

Value aggregates: `count, sum, min, max, avg, product, stddev_samp, string_join`. **`avg`, `product`, `stddev_samp` are query-only** (raise `NotImplementedError` under `satisfy`/`minimize`/`maximize`; solver supports `sum, min, max, count`). `product`/`stddev_samp` need relationalai>=1.12, return Float; `product` is an exp-log approximation — see [aggregation-advanced.md](references/aggregation-advanced.md).

**`.per(K)` declares the result dimensions — one row per distinct K.** Use the same concept variables that appear in `select()`: given `Shipment.supplier(Supplier)` in `where()`, write `.per(Supplier)`, not `.per(Shipment.supplier)` (carries Shipment into the key and over-groups; see Silent Corruption #5).

```python
aggs.count(Shipment).per(Supplier).alias("shipments")                     # entity group
aggs.sum(Shipment.qty).per(Supplier, Destination).alias("qty")            # multi-key
aggs.sum(Shipment.qty * Shipment.delay_days).per(Supplier).alias("qd")    # arithmetic inside
aggs.count(Shipment).per(Supplier).where(Shipment.is_delayed()).alias("delayed")  # scoped
```

- **Empty aggregations return no row, not zero** — coalesce with `| 0` for missing groups.
- **Integer division**: `count` is integer — multiply one operand by `1.0` (or `100.0`) for float ratios.
- `count(X, condition)`, conditional `.where()` on aggregates, standalone `per(X).sum(Y)`: [aggregation-advanced.md](references/aggregation-advanced.md).

### Joins and subtypes

Join by relationship application in `where()`; `.ref()` only for self-joins (`Alt = Edge.ref()`) or independent aggregation contexts. Multi-hop patterns, parameterized query functions, and Snowflake export (`Table.into().exec()`): [joins-and-export.md](references/joins-and-export.md). Multi-argument relationships: `inspect.fields(rel)` first — labeled value fields by name `rel["field"]`, unlabeled by integer position, entity-typed fields via raw source columns (the relationship API silently returns 0 rows / NaN); keyword binding never works.

**Subtypes are filter-only in queries**: selecting or counting a subtype directly raises `TyperError` — bind the parent and constrain:

```python
model.where(HighChurnRiskCustomer(Customer)).select(Customer.full_name.alias("name"))
model.select(aggs.count(Customer).alias("n")).where(HighChurnRiskCustomer(Customer)).to_df()
```

---

## Rules Authoring

Translating a natural-language business rule into derived model surface. **Never compute rule output in pandas** — every tier, flag, score, or segment is a `Concept`/`Relationship`/`Property` with `define()`; pandas only formats final query results.

1. **Parse the rule**: subject entity, condition properties, threshold/logic, output. Hints: "for each X" → `.per(X)`; "across all Y" → aggregation; "unless/except" → `model.not_()`.
2. **Classify the type** (table in [Quick Reference](#quick-reference)): boolean yes/no → validation or alerting (unary Relationship); category from a fixed set → classification (subtype); computed number → derivation (Property); two-source comparison → reconciliation. Classification yields *every* qualifying entity — "top 5 by spend" is a ranking query AFTER the rule, not part of it.
3. **Ground in the model first** — `inspect.schema(model)[concept]` catches the three silent failure modes: duplicate authoring (property already exists, possibly inherited or near-synonym), hallucinated surface (`Customer.tier` vs actual `Customer.category`), and wrong-type inference (read the enriched `type_name` from inspect, don't guess from column names). Skip only on greenfield/empty models. **Data exploration is mandatory for threshold rules**: query `min`/`max`/`avg` of the condition property first — scores may be 0-10 not 0-100, ratios > 1.0, percentages 0-1 vs 0-100.
4. **Translate** using the canonical patterns ([Quick Reference](#quick-reference) table; full variants in [pyrel-rule-patterns.md](references/pyrel-rule-patterns.md)). Design rules that prevent rework: declare the output surface first; Relationship for booleans, Property for values; conditions in one `where()` are AND, `model.union()` for OR; classification conditions mutually exclusive (`<` one boundary, `>=` the other) or `FDError`; decide exhaustive vs partial (catch-all rule?); prefer data-driven thresholds (`Entity.amount > Entity.credit_limit`) over literals; one rule per derived property; reuse an existing classification rather than re-deriving it from a composite metric. Full principles and NL-to-PyRel translation tables: [rule-design.md](references/rule-design.md).
5. **Validate**: output type right? properties exist? join path traverses? types align (silent zero matches on Integer-vs-Float)? classifications exclusive? `.per()` present on aggregations? no circular deps? Then `model.where(Entity.is_flagged()).select(Entity.id).to_df()` and assert non-empty. Testing approaches and exhaustiveness checks: [rule-validation-and-testing.md](references/rule-validation-and-testing.md).
6. **Connect downstream**: query the output, chain it into other rules (the runtime resolves rule dependencies declaratively — no explicit ordering), or feed other reasoners: rules → prescriptive (flag constrains assignment), predictive → rules (`predicted_risk > 0.8` alert), graph → rules (centrality threshold), rules → predictive (tier as feature). Code examples: [rule-chaining-patterns.md](references/rule-chaining-patterns.md).

**Missing data:** PyRel doesn't raise on missing values — conditions silently don't match. Detect with `model.not_(Ticket.priority)`; default with the fallback operator (`Ticket.priority | "unknown"`, `aggs.count(...).per(C).where(...) | 0`); add presence flags for downstream rules. A sparse aggregation-derived Property un-grounds downstream rules and solver constraints silently — coalesce with `| <default>`.

Multi-entity subtype rules, cross-entity joins, OR-condition flags: [complex-multi-entity-rules.md](references/complex-multi-entity-rules.md) and the worked [complex-rule-example.md](references/complex-rule-example.md). Subtype-specific pitfalls: [pyrel-subtype-rules.md](references/pyrel-subtype-rules.md).

---

## Debugging

**Step 0: print the expression.** Every PyRel object has a readable `repr` — `print(aggs.sum(Order.total).per(Customer))` confirms structure before querying (wrong concept in `.per()`, wrong property) — distinct from `.inspect()`, which executes.

**Wrong values?** Check Silent Corruptions #1-5 in order: missing alias → missing distinct → dot-chain binding → cartesian inflation → `.per(FK_property)`.

**Empty DataFrame?** The join itself is rarely the cause. (1) String-equality filters first — run `distinct()` on each filtered property, watch casing/suffixes/underscores. (2) Drop filters one at a time until rows return. (3) Only then suspect structure — missing `define()`, a `.new()` that matched nothing, wrong relationship direction.

**`Unground Variables`?** A body variable can't bind — usually type mismatch (Float vs Integer: cast with `floats.float()` / `numbers.integer()`), a non-existent property, or a join path with no bindings; isolate the call, check comparison types, comment out clauses incrementally. Spinner can swallow the detail — set `TERM=dumb`. Head-variable-vs-ref cases: see [Free-Variable Scoping](#free-variable-scoping). Full checklist: [common-pitfalls.md](references/common-pitfalls.md#debugging-empty-or-unexpected-results).

**`ValidationError: Unused variable`?** A ref reused across independent aggregation contexts — use named refs (`Customer.ref("t1")`).

---

## Common Pitfalls

| Mistake | Cause / Symptom | Fix |
|---------|-----------------|-----|
| `with model.rule():` | Context managers not supported | Direct calls: `model.define(...)`, `model.require(...)` |
| `define()`/`require()` in a Python loop | One rule per iteration; slow; PyRel warns >50 | Declarative: `model.data(df)` + `to_schema()`; `lookup` joins (see [Definitions](#definitions)) |
| `FDError: Found non-unique values` | Property got two values per key — overlapping rules, boundary overlap, or truly M:N | Mutually exclusive conditions (`<` / `>=`), fix data, or switch to Relationship |
| `Unground Variables` | Type mismatch, missing property, unbound head variable | See [Debugging](#debugging); scoping cases in [Free-Variable Scoping](#free-variable-scoping) |
| `~` for negation | `TypeError: bad operand type for unary ~` | `model.not_(expr)`; set-difference: nested `not_()` or subtract in pandas |
| Bare `Number` without `.size()` | Type-inference issues at runtime | `Number.size(p, s)` |
| Redundant `Property()` for identity field | `identify_by` auto-creates it | Remove the duplicate |
| `UninitializedPropertyException` on chain | Property chain through a cross-product concept | Store values directly on the cross-product concept |
| "Uninitialized properties" on `where().define()` | Declarative filtering by relationship equality on cross-products | Loop pattern for relationship-based filtering; declarative for primitive equality |
| Division by zero | Not caught at definition time | Guard with `.where(Entity.input > 0)` |
| Every query fails after one bad `define()` | A raising `define()` isn't rolled back — the poisoned rule re-raises on every later query | Restart the process / rebuild the model; don't debug unrelated queries in a poisoned session |
| Boolean flag as `select()` column | `TyperError` — unary Relationships are filter-only | Filter in `where()`; to project flags into a table, query each flag's IDs and merge (pattern in [rule-design.md](references/rule-design.md)) — but derived values still come from `define()`, never pandas |
| `Property.exists()` | `RAIException: Cannot access relationships on core concept` | Ref binding: `r = Float.ref(); model.where(Concept.prop(r)).select(r.alias("v"))` |
| `.where()` on a bare Concept | `Site.where(...)` doesn't exist | `.where()` lives on model, aggregations, constraints, definitions |
| Mixing bare select with `distinct()` | Runtime error | ALL columns inside `distinct()` or none |
| Integer column returns `Int128Array` | Reductions raise `TypeError`; `df[df.n == 6]` silently empty | Compose in-model instead of pandas; if pandas is final consumer, `df["n"] = df["n"].astype(int)` immediately |
| Multi-arg relationship wrong/zero rows | Guessed field access (keyword args never work; entity fields silently 0 rows) | `inspect.fields(rel)` first; name / position / raw-column per [joins-and-export.md](references/joins-and-export.md#multi-argument-relationships) |
| Rule silently skips entities | Condition property missing on them | `model.not_(prop)` detection, presence flags, `\| default` |
| Rule chaining cycle | A depends on B depends on A | Dependencies must form a DAG |
| Hardcoded threshold | Literal instead of data-driven bound | Reference `Entity.limit`; explore `min`/`max`/`avg` first |

Lower-frequency pitfalls (Snowflake export casing, Python builtins on RAI expressions, implicit-property typos): [common-pitfalls.md](references/common-pitfalls.md).

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Aggregation queries | Basic select, grouped agg, multi-hop join, multi-arg relationship binding | [examples/aggregation_queries.py](examples/aggregation_queries.py) |
| Computed properties | Datetime, segmentation, argmax tiebreaker | [examples/datetime_argmax_segmentation.py](examples/datetime_argmax_segmentation.py) |
| Validation rule | Threshold compliance with cross-entity join | [examples/validation_rule.py](examples/validation_rule.py) |
| Classification rule | Multi-tier classification, mutually exclusive ranges | [examples/classification_rule.py](examples/classification_rule.py) |
| Derivation rule | Computed total via aggregation | [examples/derivation_rule.py](examples/derivation_rule.py) |
| Alerting rule | Temporal breach detection with missing-data handling | [examples/alerting_rule.py](examples/alerting_rule.py) |
| Reconciliation rule | Two-source delta with tolerance and severity | [examples/reconciliation_rule.py](examples/reconciliation_rule.py) |
| Cross-entity alerting | Disjunctive OR flags via multiple `define()` calls | [examples/cross_entity_alerting.py](examples/cross_entity_alerting.py) |
| Multiarity properties + refs | Multiple `Float.ref()` binding, pairwise multi-arity joins | [examples/multiarity_property_refs.py](examples/multiarity_property_refs.py) |
| Standalone Property + union | Unattached Property, `model.union()` multi-component objective | [examples/standalone_property_union_objective.py](examples/standalone_property_union_objective.py) |
| print() debugging | Readable repr before query execution | [examples/pprint_debugging.py](examples/pprint_debugging.py) |
| End-to-end walkthrough | Ontology + graph + aggregation + query in one script | [examples/graph_derived_subtypes.py](examples/graph_derived_subtypes.py) |
| `inspect.to_concept()` helper | Defensive helper for any DSL handle | [examples/inspect_to_concept_helper.py](examples/inspect_to_concept_helper.py) |
| `inspect.schema()` summary | Canonical model-summary emit | [examples/inspect_schema_summary.py](examples/inspect_schema_summary.py) |
| `inspect.fields()` unpack | Multi-argument relationship field discovery | [examples/inspect_fields_unpack.py](examples/inspect_fields_unpack.py) |

---

## Reference files

| Reference | When to load | File |
|-----------|--------------|------|
| Expression rules | `.where()` targets, `.per()` scoping, operator precedence, refs/aliasing, enums detail | [expression-rules.md](references/expression-rules.md) |
| Data loading | FK binding, `to_schema()` rules, unary flags, optional vs required columns | [data-loading.md](references/data-loading.md) |
| Standard library | `math.abs()`, string functions, date arithmetic — full catalog | [standard-library.md](references/standard-library.md) |
| Imports | Module aliases, reasoner imports, builtin shadowing | [imports.md](references/imports.md) |
| Common pitfalls | Lower-frequency pitfalls + step-by-step empty-results debugging | [common-pitfalls.md](references/common-pitfalls.md) |
| Joins and export | Multi-hop binding, multi-argument relationships, parameterized queries, Snowflake export | [joins-and-export.md](references/joins-and-export.md) |
| Distinct patterns | Multi-column dedup without aggregation | [distinct-patterns.md](references/distinct-patterns.md) |
| Aggregation advanced | Ranking (`top`/`bottom`/`rank`), `count(X, cond)`, conditional aggregates, `product`/`stddev_samp` | [aggregation-advanced.md](references/aggregation-advanced.md) |
| Filtering advanced | Extended `not_()`, `union()` OR-filters, HAVING extras | [filtering-advanced.md](references/filtering-advanced.md) |
| Inspect module | `inspect.schema` / `fields` / `to_concept` API | [inspect-module.md](references/inspect-module.md) |
| Model introspection (fallback) | `model.concepts/relationships` for pre-1.0.14 versions | [model-introspection.md](references/model-introspection.md) |
| Rule design | NL-to-PyRel translation tables, the nine design principles, boolean-flag projection | [rule-design.md](references/rule-design.md) |
| Rule patterns | Full code patterns for all five rule types | [pyrel-rule-patterns.md](references/pyrel-rule-patterns.md) |
| Rule validation & testing | Known-data/boundary/coverage testing, exhaustiveness checks | [rule-validation-and-testing.md](references/rule-validation-and-testing.md) |
| Subtype rules | Subtype rule syntax, OR crashes, dot-chain limits | [pyrel-subtype-rules.md](references/pyrel-subtype-rules.md) |
| Complex multi-entity rules | Cross-entity joins, existential checks, layered derivations | [complex-multi-entity-rules.md](references/complex-multi-entity-rules.md) |
| Rule chaining | Rule-to-rule and cross-reasoner integration examples | [rule-chaining-patterns.md](references/rule-chaining-patterns.md) |
| Complex rule example | Worked 5-entity subtype rule with OR branches | [complex-rule-example.md](references/complex-rule-example.md) |
