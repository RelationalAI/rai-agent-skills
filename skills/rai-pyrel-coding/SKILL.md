---
name: rai-pyrel-coding
description: Covers PyRel v1 language syntax including imports, type system, concepts, properties, relationships, data loading, references, and code structure. Use when writing or reviewing PyRel code.
---

# PyRel Coding
<!-- v1-SENSITIVE -->

## Summary

**What:** PyRel v1 language syntax — imports, types, concepts, properties, expressions, data loading, and standard library.

**When to use:**
- Writing or reviewing PyRel model code
- Need the correct import path, type syntax, or property declaration pattern
- Debugging a syntax error, `UninitializedPropertyException`, or empty/unexpected query results
- Checking what standard library functions are available (math, strings, dates)
- Looking up data loading patterns (CSV, Snowflake, FK resolution)
- Understanding expression rules (`.where()` targets, `.per()` grouping, operators)

**When NOT to use:**
- Ontology modeling decisions (when to create a concept vs property, gap classification) — see `rai-ontology-design`
- Query construction (select, aggregation, filtering, joins) — see `rai-querying`
- Solver formulation (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Connection and config setup — see `rai-configuration`

**Overview:** Reference skill. Key lookup areas: Imports, Model Patterns, Type System, Concepts/Properties/Relationships, Data Loading, References and Aliasing, Standard Library (math/strings/dates), Expression Rules.

---

## Quick Reference

```python
# Imports
from relationalai.semantics import (
    Model, Float, Integer, String, Date, DateTime,
    count, sum, min, max, avg, per, distinct,
)
from relationalai.semantics import Number  # Always use Number.size(p,s) — bare Number causes inference issues
from relationalai.semantics.reasoners.prescriptive import Problem

# Model + concepts
model = Model("my_model")
Product = model.Concept("Product", identify_by={"id": Integer})

# Properties (concept → value) and Relationships (concept → concept)
Product.cost = model.Property(f"{Product} has {Float:cost}")
Product.supplier = model.Relationship(f"{Product} supplied by {Supplier:supplier}")

# Data loading
model.define(Product.new(model.data(df).to_schema()))

# Query — prefer model.where/model.select for multi-model safety
result = model.where(Product.cost > 10).select(Product.id, Product.cost).to_df()

# Debugging — inspect prints data to stdout
Product.cost.inspect()

# Solver
p = Problem(model, Float)
p.solve_for(Product.x_qty, type="cont", lower=0, name=["qty", Product.id])
p.satisfy(model.require(sum(Product.x_qty) <= 100))
p.minimize(sum(Product.cost * Product.x_qty))
p.solve("highs")
```

---

## Imports

All v1 import paths:

```python
# Module alias (preferred in reference KGs for conciseness)
import relationalai.semantics as rai
# Then use: rai.Model, rai.Concept, rai.Property; model.where(), model.select(), model.define(), etc.

# Explicit imports (preferred in standalone scripts / solver code)
from relationalai.semantics import (
    Model,                              # Model creation
    Float, Integer, String, Date,       # Type references
    DateTime, Number,                   # DateTime for timestamps, Number.size(p,s) for decimals
    sum, count, max, min, avg,          # Aggregation — shadows Python builtins (see note below)
    per, where, select, define,         # Query/definition functions
    require,                            # Constraint creation (also model.require)
    data, distinct,                     # Data loading, dedup
)

# Reasoner-specific imports
from relationalai.semantics.reasoners.prescriptive import (
    Problem,
    all_different, implies, special_ordered_set_type_1, special_ordered_set_type_2,
)
from relationalai.semantics.reasoners.graph import Graph

# Standard library
from relationalai.semantics import std
from relationalai.semantics.std.datetime import datetime       # datetime.year(), .month(), etc. — shadows Python datetime
from relationalai.semantics.std import datetime as dt           # dt.date.period_days(), dt.datetime.to_date()
from relationalai.semantics.std import math                     # math.abs()
from relationalai.semantics.std.strings import string, concat   # string conversion, concatenation
from relationalai.semantics.std import strings                  # full string library
from relationalai.semantics.std import re                       # regex module (v1)

# Builtin shadowing — when you need both RAI and Python builtins, use a module alias:
from relationalai.semantics.std import aggregates as aggs       # aggs.sum, aggs.count, aggs.max, aggs.min
import datetime as py_datetime                                  # Python stdlib datetime
```

**Long import lines:** Split across multiple lines with `()` or use `import relationalai.semantics as rai` to keep lines manageable.

---

## Model Patterns

```python
model = Model("my_model")
```

**Accepted parameters:** `name` (str), `config` (Config), `exclude_core` (bool), `is_library` (bool). Without `config`, auto-discovers `raiconfig.yaml`. Use `time_ns()` suffix only for throwaway models in automated pipelines. Shorthand: `Concept, Property = model.Concept, model.Property`.

**Always use `model.define()`/`model.where()`/`model.select()`** — standalone `define()`, `where()`, `select()` fail when multiple Models exist (`"Multiple Models have been defined."`). Generated code should always use the model method form.

---

## Type System

Types are imported objects, not strings. Used in Property f-strings and as type arguments to reasoner APIs.

| Type | Usage in Property | Python equivalent |
|------|-------------------|-------------------|
| `Float` | `{Float:cost}` | `float` |
| `Integer` | `{Integer:count}` | `int` |
| `String` | `{String:name}` | `str` |
| `Number.size(p,s)` | `{Number.size(38,4):price}` | `decimal(p,s)` |
| `Date` | `{Date:due_date}` | date |
| `DateTime` | `{DateTime:timestamp}` | datetime |
| `Boolean` | `{Boolean:active}` | `bool` |

**`Number.size(precision, scale)`** — always use with explicit parameters. `Number` alone (unparameterized) causes type inference issues and should be avoided. Always specify `Number.size(p, s)` (e.g., `Number.size(38, 4)` for Snowflake NUMBER columns). Do NOT call `Number(38, 4)` directly (that's concept invocation, not type construction).

**Deprecated alias:** `decimal` is a deprecated alias for `Number` — do not use it. Use `Number.size(p, s)` instead.

---

## Properties and Relationships — When to Use Which

The choice is about **multiplicity** — whether the association is many-to-one or many-to-many. Both support any arity (unary, binary, ternary+).

**Property** — functional dependency (uniqueness constraint). Inputs uniquely determine the output (at most one value). Use for **many-to-one**. Provides performance benefits and enforces the constraint.

**Relationship** — no uniqueness constraint (zero, one, or many outputs per input). Use for **many-to-many**. More flexible when cardinality is uncertain, but prefer establishing multiplicity.

| Pattern | Use Property | Use Relationship |
|---------|-------------|-----------------|
| Single-valued attribute | `Food` has one `Float:cost` | — |
| Concept → Concept (functional, e.g. FK) | `Order` placed by exactly one `Customer` | — |
| Concept → Concept (multi-valued) | — | `Parent` has many `Child` |
| Availability/membership (many-to-many) | — | `Worker` available for `Shift` |
| Unary flag (functional) | `Order` is rush order | — |
| Ternary with FD | `Food` contains `Nutrient` in `Float:qty` | — |
| Ternary without FD | — | `Food` contains `Nutrient` (many-to-many) |
| Association where cardinality is uncertain | — | Use Relationship — but prefer establishing multiplicity |

---

## Concepts

```python
# Identified concept (typed key — PREFERRED, use whenever possible)
Food = model.Concept("Food", identify_by={"name": String})
Stock = model.Concept("Stock", identify_by={"index": Integer})
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})

# Basic concept (no identify_by — avoid unless extending primitives)
Product = model.Concept("Product")

# Subtype (inherits parent properties)
ActiveOrder = model.Concept("ActiveOrder", extends=[Order])
# Populate subtype membership with model.define():
model.define(ActiveOrder(Order)).where(Order.total > 75)
# Query through parent properties:
model.select(ActiveOrder.id, ActiveOrder.total)

# Extending a primitive type (no identify_by needed — identity comes from the primitive)
PositiveInt = model.Concept("PositiveInt", extends=[Integer])
```

- **Always include `identify_by` whenever possible.** It defines the natural key — entities with the same key values are the same instance. This prevents duplicate entities and makes identity explicit.
- Without `identify_by`, ALL parameters passed to `.new()` are used for the identity hash. This is fragile — adding or removing a `.new()` parameter changes entity identity.
- Composite keys use multiple entries: `identify_by={"i": Integer, "j": Integer}`.
- **`identify_by` auto-creates properties.** `Concept("Customer", identify_by={"customer_id": Integer})` automatically creates `Customer.customer_id` as a `Property(Integer)`. Do not declare a separate `model.Property()` for identity fields — it will create a duplicate.
- **`identify_by` supports concept types** — use for composite keys involving other concepts: `OrderItem = model.Concept("OrderItem", identify_by={"order": Order, "item": Item})`. This is standard for association/junction concepts.
- **Exception where `identify_by` is not used:** Extending primitive types (`extends=[Integer]`) — identity comes from the primitive value.
- **Introspection:** `model.concepts` — list of all declared concepts; `model.concept_index["Name"]` — look up concept by name.

---

## Properties

Properties use f-strings with type references. The type comes BEFORE the field name: `{Type:field}`. Use Property for **many-to-one (functional) associations** — scalar attributes, functional concept-to-concept FKs, and N-ary associations with a functional dependency.

```python
# Scalar value properties (concept → primitive)
Food.cost = model.Property(f"{Food} has {Float:cost}")
Worker.name = model.Property(f"{Worker} has {String:name}")

# Functional FK property (concept → concept, many-to-one)
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")

# Multiarity property with value output (inputs uniquely determine the Float output)
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")
```

**Canonical syntax (v1):** `model.Property(f"{Food} has {Float:cost}")` — f-string with type objects interpolated. Always use this form.

**Property name vs madlib verb:** The property name is the f-string field name (e.g., `qty` in `{Float:qty}`), not the verb (`contains`, `in`).

**Multi-argument (multiarity) properties:** Field names required when the same type appears multiple times to disambiguate inputs.

```python
Stock.covar = model.Property(f"{Stock:stock1} and {Stock:stock2} have {Float:covar}")       # Binary (same-type disambiguation)
FreightGroup.inv = model.Property(f"{FreightGroup} on day {Integer:t} has {Float:inv}")      # Time-indexed
Worker.assignment = model.Property(f"{Worker} has {Shift} if {Integer:assigned}")             # Multi-concept
```

**Scalar / standalone properties** (primitives only, no user-defined concepts): `bin_tl = model.Property(f"departure day {Integer:t} has {Float:bin_tl}")`

---

## Relationships

Relationships are **multi-valued** associations — zero, one, or many outputs per input. No uniqueness constraint. Use for concept-to-concept links where one entity can relate to many others.

```python
# Concept-to-concept links — ALL concept-to-concept associations use Relationship
Parent.has_child = model.Relationship(f"{Parent} has {Child}")
Order.placed_by = model.Relationship(f"{Order} placed by {Customer}")

# Availability / membership
Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")
```

**Scalar variables** (standalone floats/ints without a parent concept). Use for optimization variables not attached to any concept (e.g., NLP problems with just a few free variables):

```python
x = model.Relationship(f"{Float:x}")
y = model.Relationship(f"{Float:y}")

# Use in solver:
p = Problem(model, Float)
p.solve_for(x, name="x", lower=-100.0, upper=5.0, start=0.0)
p.solve_for(y, name="y", lower=-100.0, upper=5.0, start=0.0)
p.minimize((1 - x) ** 2 + 100 * (y - x**2) ** 2)
```

**Global counts/values:** Assign to a Python variable (`NODE_COUNT = count(Node)`). Use a model Relationship only when the value must be available in downstream `define()` rules or solver expressions: `model.define(node_count(count(Node)))`.

**Bracket access:** Use `rel["field"]` to access named roles. See References and Aliasing section below.

**`Chain.ref()` and `.alt()`:** For independent chain traversals and inverse relationships, see [expression-rules.md](references/expression-rules.md#chain-ref-and-alt).

---

## Definitions

Definitions are the core of PyRel coding. They let you bake business logic and domain knowledge into the model so that every query and solver formulation can leverage it. Prefer putting logic in definitions over writing complex queries.

**`model.define()`** — declare facts, computed properties, derived relationships, and entity creation rules:

```python
# Computed property — derived from existing data
model.define(Order.total(Order.quantity * Order.unit_price))

# Boolean flag as unary relationship
model.define(Shipment.is_delayed()).where(Shipment.delay_days > 0)

# Derived relationship — named subset
# NOTE: aggregation needs an explicit join through the relationship
high_value = model.Relationship(f"High Value: {Customer}")
model.define(high_value(Customer)).where(
    aggs.sum(Order.total).where(Order.customer(Customer)).per(Customer) > 10000
)

# Entity creation from relationships
model.define(
    OrderItem.new(order=Order, item=Item)
).where(Order.contains(Item))

# Conditional / multi-branch definitions
model.define(Order.priority_label("high")).where(Order.total > 1000)
model.define(Order.priority_label("low")).where(Order.total <= 1000)
```

**`model.where(...).define(...)` and `model.define(...).where(...)`** — both directions are valid. Use whichever reads more naturally for the logic.

**Key principle:** Most logic should live in definitions. Queries (`select().to_df()`) should be simple — selecting and aggregating values that definitions have already computed. If you find yourself writing complex logic inside a query, consider extracting it into a definition instead.

---

## Enums

`model.Enum` creates a concept-backed Python enum whose members are usable as concept literals in `where()` and `define()`. Use instead of bare string comparisons when values are a fixed controlled vocabulary.

```python
# Class-style:
class Priority(model.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

# Functional form:
Priority = model.Enum("Priority", ["low", "medium", "high"])
```

Note: `Enum` is accessed via `model.Enum`, not imported standalone. See [expression-rules.md](references/expression-rules.md#enums) for full syntax and examples.

---

## Data Loading Patterns

API reference for loading data into models. For strategy guidance (authoritative vs joinable sources, schema-to-ontology workflow), see `rai-ontology-design`.

### Core APIs

| API | Purpose | Key params |
|-----|---------|------------|
| `model.data(df)` | Wrap a pandas DataFrame for loading | — |
| `.to_schema()` | Auto-map columns to matching Property names | `exclude=[]` |
| `model.Table("DB.SCHEMA.TABLE")` | Reference a Snowflake table | Optional column schema dict |
| `Concept.filter_by(prop=value)` | FK resolution — look up entity by property value; no match → no row | Returns matching entity or nothing |
| `Concept.to_identity(key=value)` | Strict identity lookup — exactly one match guaranteed; raises if not found | Use for lookups where missing is an error |
| `Concept.new(key=value)` | Create entity instances | Identity properties as kwargs |
| `std.common.range(n)` | Generate integer range 0..n-1 | Also `range(start, end)` |

### CSV loading

```python
# Auto-map: column names must match Property names exactly
model.define(Food.new(model.data(csv).to_schema()))

# Explicit mapping: when column names differ from Properties
food_data = model.data(read_csv("foods.csv"))
model.define(food := Food.new(name=food_data.name), food.cost(food_data.cost))
```

### Snowflake tables

```python
schema = model.Table("DB.SCHEMA.TABLE").to_schema(exclude=["internal_col"])
model.define(Concept.new(schema))
```

**Column renaming:** `to_schema()` does not support `rename`. Use explicit property assignment:

```python
src = model.Table("DB.SCHEMA.TABLE")
model.define(concept := Concept.new(key=src.SRC_COL), concept.target_prop(src.OTHER_COL))
```

**Column name casing:** Snowflake normalizes unquoted identifiers to UPPERCASE. Column schema dicts must use UPPERCASE names to match.

### FK resolution with `filter_by`

```python
# Preferred: filter_by in model.define() — no separate where() needed
model.define(
    Order.filter_by(id=source.ORDER_ID)
    .ordered_by(Customer.filter_by(id=source.CUSTOMER_ID))
)

# Alternative: model.where() + define()
order = model.where(Order.id == source.ORDER_ID)
order.define(Order.ordered_by(Customer.filter_by(id=source.CUSTOMER_ID)))
```

`filter_by` returns the entity matching the given property value. If no match exists, the relationship is not defined (no error). The `model.define(Concept.filter_by(...).prop(...))` pattern is used by modeler exports and avoids separate `where()` calls.

### Multiarity property loading

```python
for nu in nutrient_csv.name:
    model.define(food.contains(Nutrient, getattr(food_data, nu))).where(Nutrient.name == nu)
```

### Programmatic entity creation

```python
model.define(Queen.new(row=std.common.range(n)))           # Range-based
model.define(sf := Factory.new(name="steel_factory"), sf.avail(40.0))  # Inline
model.define(Node.new(v=Edge.i))                            # Derived from existing data
```

---

## References and Aliasing

Use `.ref()` to create independent variables of the same concept or type for pairwise expressions, multiarity value binding, and complex aggregation contexts. Use `.alias("name")` for readable debug output. The walrus operator `:=` creates inline refs inside `where()`. See [expression-rules.md](references/expression-rules.md#references-and-aliasing) for full patterns including named refs, `Float.ref()` value binding, and bracket notation.

---

## Code Structure

**Define models at module level** — not inside functions. This is the standard pattern because tooling and introspection need access to the model objects at import time. Scoping a model inside a function hides it from these tools.

```python
"""Model Name - Brief description."""

from pathlib import Path

from pandas import read_csv
from relationalai.semantics import Float, Integer, Model, String, sum

# --- Model (module level) ---
model = Model("my_model")

# --- Concepts ---
Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")

# --- Data Loading ---
csv = read_csv(Path(__file__).parent / "data" / "foods.csv")
model.define(Food.new(model.data(csv).to_schema()))
```

Reasoner-specific code (solver formulation, graph analysis) goes in separate functions that receive the model:

```python
def solve(model):
    """Define solver variables/constraints/objectives, solve, return results."""
    ...
```

**Template examples:** See `rai-prescriptive-problem-formulation` examples: `diet.py` (linear optimization), `shift_assignment.py` (binary assignment), `portfolio_balancing.py` (pairwise expressions).

---
## RAI Expression Syntax

### Boolean Logic in Expressions

RAI expressions do not support Python's boolean keywords (`and`, `or`, `not`, `if/else`). These trigger `[Invalid operator] Cannot use python's 'bool check'` at compile time. Use the operator overloads or library functions instead:

| Python (wrong) | PyRel (correct) |
|----------------|-----------------|
| `(x >= 1) and (y >= 1)` | `(x >= 1) & (y >= 1)` |
| `(x >= 1) or (y >= 1)` | `(x >= 1) \| (y >= 1)` |
| `not x_assigned` | `not_(x_assigned)` |
| `if condition else fallback` | `value \| fallback` (ordered fallback), or `.where(condition)` on the constraint |

**`|` vs `model.union()`:** The `|` operator is an ordered fallback (picks the first branch that succeeds — if-then-else semantics). `model.union()` is set OR (collects ALL matching branches). Use `|` for defaults and case-when chains; use `model.union()` for multi-term objectives or OR-filtering. The `|` operator creates a `Match` object (importable from `relationalai.semantics`) — nested matches are flattened: `(a | b) | c` == `a | b | c`.

### Property Definition F-Strings

Property definitions use Python f-strings where the braces invoke `__format__()` on concept/type objects to resolve internal IDs.

```python
# Correct — braces call Float.__format__("x_flow"), resolving the concept ID
Shipment.x_flow = model.Property(f'{Shipment} has {Float:x_flow}')

# Wrong — escaped braces produce a plain string, causing [Unknown Concept] at solve
Shipment.x_flow = model.Property(f'{{Shipment}} has {{Float:x_flow}}')

# Also wrong for decision variables — {{name:type}} shorthand creates Number(38,14),
# which solve_for() rejects. Always use {Type:name} for properties passed to solve_for().
Shipment.x_flow = model.Property(f'{Shipment} has {{x_flow:float}}')  # Number(38,14), not Float
```

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Using `with model.rule():` context manager | Not supported; no context managers | Use direct calls: `model.define(...)`, `model.require(...)` |
| `model.define()` or `model.require()` in a Python loop | Creates separate rules per iteration instead of one declarative rule. PyRel detects this (same call site threshold >50) and warns. | Use declarative patterns: `model.data(df)` + `.to_schema()` for data, vectorized `.where().define()` for constraints. See examples below. |
| Division by zero in expressions | Not caught at definition time | Guard with `.where(Entity.input > 0)` |
| `UninitializedPropertyException` on property chain | Property chain through cross-product concept (e.g., `ProductStoreWeek.week.week_num`) | Store values directly as properties on the cross-product concept |
| "Uninitialized properties" on `where().define()` | Declarative filtering by relationship equality on cross-products | Use loop pattern for relationship-based filtering; use declarative for primitive equality |
| Redundant `model.Property()` for identity field | `identify_by` already auto-creates the property | Remove the duplicate `model.Property()` declaration |
| `FDError: Found non-unique values` | Property received two different values for same key set | Establish actual multiplicity — switch to `Relationship` if truly many-to-many, fix overlapping rules, or fix data quality if it should be many-to-one |
| Empty DataFrame from queries | Missing `define()` call, wrong concept type, or missing data | Verify entities exist and computed values are `define()`d before querying |
| `TypeMismatch` error | Comparing concepts of different types via `==` | Ensure both sides are the same concept type; value types prevent cross-type joins |
| Duplicate column name on Snowflake export | Case-insensitive column name collision (`LongShort` vs `longshort`) | Use distinct uppercase names for all `.alias()` values |
| Using Python builtins on RAI expressions | `abs()`, `min()`, `max()`, `round()` don't work on symbolic expressions | Use `math.abs()`, RAI aggregation imports, or algebraic equivalents |
| `//` on two decision variables | Floor division fails when both operands are decision variables | Works fine on property // constant (e.g., `Player.p // group_size`). Only fails with two solver variables — use algebraic reformulation |
| `count(X, condition)` not working | Using wrong syntax for conditional counting | Use `count(Player, x == group)` — second arg is a condition expression, works in both query and solver contexts |
| Long import lines breaking linters | LLMs generate 100+ char single-line imports | Split across multiple lines with `()` or use module alias (`import relationalai.semantics as rai`) |
| Using bare `Number` without `.size()` | Causes type inference issues at runtime | Always use `Number.size(p, s)` (e.g., `Number.size(38, 4)`) |
| Relationship declared but has no data | `model.Relationship(...)` without a corresponding `model.define()` data binding | Relationship has NO DATA at runtime — any `.where()` join on it returns zero matches. Add `model.define(From.rel(To)).where(...)` to populate it from data. |
| Using `~` for negations | Causes `TypeError: bad operand type for unary ~: 'Expression'` | Always use `model.not_(expr)`
| Using aggregates without model.distinct() | Causes duplicate rows in output | use `model.select(model.distinct(expr))` around all columns |
| Incorrect datetimes for inline data | Causes query errors or empty result sets | use eg `df["date"] = pd.to_datetime(df["date"]).dt.date` |
| Entity-valued Property for concept-to-concept FK | Some model files use `model.Property(f"{Order} placed by {Customer:customer}")` for FKs | Recommended when the FK is many-to-one (each Order has exactly one Customer) — provides performance benefits and enforces the functional constraint. Use `model.Relationship()` only if the association is truly many-to-many or cardinality is uncertain |
| Dynamic model loading loses module-level concepts | Using `importlib.util` to load a model file — concepts defined as module variables aren't on the model object | After loading, iterate module attributes and `setattr(model, name, obj)` for each `rai.Concept` instance |
| Typo creates silent empty property | `Customer.nmae` (typo) silently creates an empty property via implicit property creation — no error | `create_config(model={"implicit_properties": False})` or set `implicit_properties: false` under `model:` in raiconfig.yaml |

### Avoid Python loops around `model.define()` / `model.require()`

PyRel is declarative — one `define()` call handles all matching entities. Python loops that call `define()` per row create separate rules per iteration, which is slow and triggers a PyRel warning (threshold: 50 calls from the same call site).

```python
# BAD: Python loop creates N separate rules
for _, row in df.iterrows():
    model.define(Product.new(name=row["name"], cost=row["cost"]))

# GOOD: One declarative call handles all rows
product_data = model.data(df)
model.define(Product.new(product_data.to_schema()))

# BAD: Loop to add constraints per entity
for limit in capacity_limits:
    model.where(Site.id == limit["id"]).define(Site.max_capacity(limit["cap"]))

# GOOD: Load limits as data, join declaratively
limits = model.data(capacity_limits_df)
model.define(Site.filter_by(id=limits.id).max_capacity(limits.cap))
```

For detailed `.where()` targets, `.per()` scoping, and operator precedence rules, see [expression-rules.md](references/expression-rules.md).

---

## Debugging Empty or Unexpected Results

When a query returns an empty DataFrame or wrong values, work through these checks in order (cheapest/highest-yield first):

1. **Check for typos (implicit properties):**
   Typos silently create empty properties (see pitfall table above). Quick test:
   set `implicit_properties: false` in raiconfig.yaml and re-run — any typo will error.

2. **Check type alignment:**
   `.where(Order.id == "123")` returns empty when `id` is Integer — no error.
   Fix: use matching type (`.where(Order.id == 123)`).
   Use `.inspect()` to see actual values and infer types.
   Also check datetime columns: pandas Timestamps don't match Date properties —
   convert with `df["col"] = pd.to_datetime(df["col"]).dt.date`.

3. **Check join paths:**
   Does the relationship used in `.where()` have a `model.define()` populating it?
   Test: `Concept.rel.inspect()` — if empty, add a `model.define()` rule to populate it.

4. **Check entity counts:**
   ```python
   model.select(count(Customer)).to_df()
   ```
   If 0: data not loaded. Check table path and `model.define()` rules.

5. **Isolate where conditions:**
   ```python
   model.where(A).select(X).to_df()            # works?
   model.where(A, B).select(X).to_df()         # still works?
   model.where(A, B, C).select(X).to_df()      # empty? → C is the culprit
   ```

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Multiarity properties + refs | Binding multiple Float.ref() in `.where()`, pairwise week comparison | [examples/retail_markdown_code.py](examples/retail_markdown_code.py) |
| Standalone Property + union | Property not attached to concept, `model.union()` for multi-component objective, segment self-join | [examples/supply_chain_transport_code.py](examples/supply_chain_transport_code.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Expression rules | `.where()`, `.per()`, aggregation targets, scoping rules, operator precedence | [expression-rules.md](references/expression-rules.md) |
| Data loading | Primitive binding, FK/entity reference binding, `to_schema()` rules, unary flags, optional vs required columns | [data-loading.md](references/data-loading.md) |
| Standard library | `rai_abs()`, string functions, date arithmetic, complete function reference | [standard-library.md](references/standard-library.md) |
