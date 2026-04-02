<!-- TOC -->
- [Data Loading Patterns](#data-loading-patterns)
  - [Snowflake Type Mapping](#snowflake-type-mapping)
  - [Primitive Binding (Properties)](#primitive-binding-properties)
  - [Entity Reference Binding (Relationships / FKs)](#entity-reference-binding-relationships--fks)
  - [to_schema() Rules](#to_schema-rules)
  - [Boolean Columns from Source Data](#boolean-columns-from-source-data)
  - [Date and DateTime Columns](#date-and-datetime-columns)
  - [Optional vs Required Columns](#optional-vs-required-columns)
  - [Multiarity Property Loading](#multiarity-property-loading)
  - [Programmatic Entity Creation](#programmatic-entity-creation)
<!-- /TOC -->

## Data Loading Patterns

Comprehensive reference for binding source data to concepts. Covers all three data source types (`model.Table()`, `model.data(pandas.read_csv(...))`, `model.data(rows)`) and both binding targets (primitive properties and entity references).

### Snowflake Type Mapping

| Snowflake type | RAI base type |
|---|---|
| VARCHAR, TEXT | `String` |
| NUMBER(p,s) where s > 0 | `Float` |
| NUMBER, INT (no scale) | `Integer` |
| FLOAT, DOUBLE | `Float` |
| DATE | `Date` |
| TIMESTAMP_NTZ, TIMESTAMP | `DateTime` |
| BOOLEAN | `Boolean` property, or unary `Relationship` for flag-style |

---

### Primitive Binding (Properties)

Primitives are scalar values (`String`, `Integer`, `Float`, `Date`, `DateTime`) bound to a concept via `model.Property()`.

#### Explicit column mapping

Works with all data source types. Use when column names differ from property names, or when you want precise control.

```python
# model.Table()
src = model.Table("DB.SCHEMA.CUSTOMERS")
model.define(
    c := Customer.new(id=src.C_CUSTKEY),
    c.name(src.C_NAME),
    c.credit_limit(src.C_ACCTBAL),
)

# model.data(pandas.read_csv(...))
from pandas import read_csv
csv_data = model.data(read_csv("customers.csv"))
model.define(
    c := Customer.new(id=csv_data.customer_id),
    c.name(csv_data.customer_name),
    c.credit_limit(csv_data.account_balance),
)

# model.data(rows)
rows_data = model.data(customer_rows)
model.define(
    Customer.new(
        id=rows_data.id,
        name=rows_data.name,
        credit_limit=rows_data.credit_limit,
    )
)
```

#### Auto-mapping with `to_schema()`

Works with all data source types. Column/key names must match property names exactly.

```python
# model.Table()
schema = model.Table("DB.SCHEMA.PRODUCTS").to_schema(exclude=["internal_col"])
model.define(Product.new(schema))

# model.data(pandas.read_csv(...))
from pandas import read_csv
model.define(Product.new(model.data(read_csv("products.csv")).to_schema()))

# model.data(rows)
model.define(Product.new(model.data(product_rows).to_schema()))
```

#### Separate binding with `filter_by`

Bind properties independently of entity creation. Used by modeler exports and when columns are nullable (missing values won't prevent entity creation).

```python
src = model.Table("DB.SCHEMA.CUSTOMERS")
model.define(Customer.new(id=src.C_CUSTKEY))
model.define(Customer.filter_by(id=src.C_CUSTKEY).name(src.C_NAME))
model.define(Customer.filter_by(id=src.C_CUSTKEY).credit_limit(src.C_ACCTBAL))
```

---

### Entity Reference Binding (Relationships / FKs)

Entity references connect one concept to another via `model.Relationship()`. The source data contains a FK value (e.g., `REGION_ID`) that must be resolved to an existing entity.

#### Inline FK in `.new()`

Bind the FK as a keyword argument to `.new()` using `filter_by()` on the target concept.

```python
src = model.Table("DB.SCHEMA.NATIONS")
model.define(Nation.new(
    id=src.N_NATIONKEY,
    name=src.N_NAME,
    region=Region.filter_by(id=src.N_REGIONKEY),
))
```

#### `to_schema()` with FK kwargs

Auto-map scalar properties and bind FKs explicitly in the same `.new()` call. Exclude FK columns from `to_schema()` to avoid type errors.

```python
order_data = model.data(order_rows)
model.define(
    Order.new(
        order_data.to_schema(exclude=["customer_id", "product_id"]),
        customer=Customer.filter_by(id=order_data.customer_id),
        product=Product.filter_by(id=order_data.product_id),
    )
)
```

#### Chained `filter_by`

Resolve both source and target entities from the same data source. No separate `where()` needed.

```python
src = model.Table("DB.SCHEMA.ORDERS")
model.define(
    Order.filter_by(id=src.ORDER_ID)
    .ordered_by(Customer.filter_by(id=src.CUSTOMER_ID))
)
```

#### Separate `define().where()` with `filter_by`

Bind FK in a standalone statement. Useful when the relationship is optional or populated from a different source than the entity.

```python
src = model.Table("DB.SCHEMA.CUSTOMERS")
model.define(Customer.region(Region)).where(
    Customer.filter_by(id=src.C_CUSTKEY),
    Region.filter_by(id=src.C_REGIONKEY),
)
```

#### Multi-hop FK chain

Traverse multiple tables to establish a relationship between non-adjacent concepts.

```python
model.define(Demand.customer_site(Site)).where(
    Demand.id == demand_src.id,
    demand_src.customer_id == customer_src.id,
    Site.id == customer_src.site_id,
)
```

#### Self-referential relationship

Use `.ref()` to create a second variable for the same concept.

```python
task2 = Task.ref()
model.where(
    Task.id == deps_data.task_id,
    task2.id == deps_data.depends_on_id,
).define(Task.depends_on(task2))
```

---

### `to_schema()` Rules

| Behavior | Detail |
|---|---|
| **Auto-maps** | All columns/keys to concept properties with matching names |
| **Does NOT handle** | FK/Relationship columns — must be excluded and bound separately |
| **No rename** | Cannot remap column names to different property names; use explicit mapping instead |
| **`exclude` param** | `to_schema(exclude=["col1", "col2"])` skips listed columns |
| **Casing** | Snowflake normalizes unquoted identifiers to UPPERCASE; column names in schema dicts must match |
| **Combinable** | Can be mixed with explicit kwargs in the same `.new()` call |

---

### Boolean Columns from Source Data

Boolean columns map to unary Relationships or entity subtypes, not boolean Properties.

#### Unary flag from boolean source column

```python
model.where(
    Order.filter_by(id=order_src.ORDER_ID),
    order_src.IS_DRINK_ORDER == True,
).define(Order.is_drink_order())
```

#### Unary flag from string/enum comparison

```python
model.where(Part.stock_status == "CRITICAL_SHORTAGE").define(
    Part.is_critical_shortage()
)
```

#### Unary flag from expression

```python
model.where(
    Date(LineItem.commit_date) < Date(LineItem.receipt_date),
).define(LineItem.is_late())
```

#### Entity subtype from boolean column

Use when the boolean distinguishes a meaningful domain category that carries its own properties or relationships.

```python
EnterpriseCustomer = model.Concept("EnterpriseCustomer", extends=[Customer])

model.where(
    Customer.filter_by(id=customer_src.C_CUSTKEY),
    customer_src.C_IS_ENTERPRISE == True,
).define(EnterpriseCustomer(Customer))
```

---

### Date and DateTime Columns

`model.Table()` maps Snowflake `DATE` and `TIMESTAMP` columns automatically. For `model.data()`, the values must be properly typed Python objects — not strings.

#### List of dicts

Use Python `date` and `datetime` objects directly in dict values.

```python
from datetime import date, datetime

rows = [
    {"id": 1, "order_date": date(2024, 6, 10), "created_at": datetime(2024, 6, 10, 9, 30, 0)},
    {"id": 2, "order_date": date(2024, 11, 3), "created_at": datetime(2024, 11, 3, 14, 0, 0)},
]
src = model.data(rows)
model.define(
    o := Order.new(id=src.id),
    o.order_date(src.order_date),
    o.created_at(src.created_at),
)
```

#### List of tuples with `columns=`

When data is naturally columnar (e.g., parameter grids), use tuples with explicit column names:

```python
src = model.data([("Alice", 30), ("Bob", 25)], columns=["name", "age"])
model.define(c := Customer.new(name=src.name), c.age(src.age))
```

Without `columns=`, integer labels are used (`col0`, `col1`, etc.).

#### pandas DataFrame

For `DateTime` properties, use `pd.to_datetime()` to ensure columns have `datetime64` dtype. For `Date` properties, keep Python `date` objects as-is — do **not** convert with `pd.to_datetime()`, which produces `datetime64` and causes a `TyperError`.

```python
from datetime import date, datetime
import pandas as pd

df = pd.DataFrame([
    {"id": 1, "order_date": date(2024, 6, 10), "created_at": datetime(2024, 6, 10, 9, 30, 0)},
    {"id": 2, "order_date": date(2024, 11, 3), "created_at": datetime(2024, 11, 3, 14, 0, 0)},
])
# DateTime columns: convert to datetime64 with pd.to_datetime()
df["created_at"] = pd.to_datetime(df["created_at"])
# Date columns: keep as Python date objects — do NOT use pd.to_datetime()

src = model.data(df)
model.define(
    o := Order.new(id=src.id),
    o.order_date(src.order_date),
    o.created_at(src.created_at),
)
```

**Common mistakes:**
- Passing date strings (e.g., `"2024-06-10"`) without conversion causes query errors or empty result sets. Always use typed Python objects.
- Using `pd.to_datetime()` on a `Date` property column converts it to `datetime64`, which mismatches the `Date` type and causes a `TyperError`.

---

### Optional vs Required Columns

All columns passed to `.new()` in a single call are **required** — the entity is only created when ALL values are non-null.

To make columns optional, bind them separately:

```python
# Entity created even if NAME or COMMENT is null
model.define(Region.new(id=src.R_REGIONKEY))
model.define(Region.filter_by(id=src.R_REGIONKEY).name(src.R_NAME))
model.define(Region.filter_by(id=src.R_REGIONKEY).comment(src.R_COMMENT))
```

---

### Multiarity Property Loading

Load multiarity properties (e.g., nutrient content per food) by iterating over the arity dimension:

```python
for nu in nutrient_csv.name:
    model.define(food.contains(Nutrient, getattr(food_data, nu))).where(Nutrient.name == nu)
```

---

### Common Data Loading Mistakes

These produce **silent failures** — no error is raised, but data is missing or queries return empty.

**Relationships must be set in `.new()`.** Post-hoc relationship assignment silently fails:

```python
# BROKEN — post-hoc assignment
model.define(b := Business.new(id=d["ID"]), b.name(d["NAME"]))
model.where(Business.id == d["ID"]).define(Business.site(Site.filter_by(id=d["SITE_ID"])))

# CORRECT — relationship in .new()
model.define(
    b := Business.new(id=d["ID"], site=Site.filter_by(id=d["SITE_ID"])),
    b.name(d["NAME"]),
)
```

**Extra CSV columns with NaN break `model.data()`.** Pass only the columns you need:

```python
# BROKEN — VALUE_TIER and CONTACT_EMAIL columns have NaN, silently break loading
d = model.data(read_csv("business.csv"))

# CORRECT
d = model.data(read_csv("business.csv")[["ID", "NAME", "RELIABILITY_SCORE"]])
```

**`to_schema()` clobbers previously set properties.** A second `to_schema()` load of the same concept overwrites relationships and properties from the first `model.define()`:

```python
# BROKEN — second define clobbers site from first
model.define(b := Business.new(id=d["ID"], site=Site.filter_by(id=d["SITE_ID"])), ...)
model.define(Business.new(model.data(subset[["id","score"]]).to_schema()))

# CORRECT — load all properties per batch in one define
model.define(
    b := Business.new(id=d["ID"], site=Site.filter_by(id=d["SITE_ID"])),
    b.name(d["NAME"]), b.score(d["SCORE"]),
)
```

**NULL foreign keys create invisible network gaps.** Rows with NULL FK columns silently fail to create relationships. The entity is created but the relationship is empty. In network models, this creates invisible gaps (e.g., operations with no SKU, edges with no destination):

```python
# Check for NULL FKs BEFORE loading
print(df["SITE_ID"].isna().sum(), "rows with NULL SITE_ID")
# Filter or handle: df = df.dropna(subset=["SITE_ID"])
```

---

### Programmatic Entity Creation

Create entities from ranges, inline values, or derived data:

```python
model.define(Queen.new(row=std.common.range(n)))           # Range-based
model.define(sf := Factory.new(name="steel_factory"), sf.avail(40.0))  # Inline
model.define(Node.new(v=Edge.i))                            # Derived from existing data
```
