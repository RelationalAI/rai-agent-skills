---
name: rai-build-starter-ontology
description: Walks through building a first RAI ontology from Snowflake tables or local data samples. Use when creating a new RAI model, starting a proof of concept, or onboarding a new dataset.
---

# Build Starter Ontology
<!-- v1-STABLE -->

## Summary

**What:** Workflow for building a minimal working RAI ontology from raw data.

**When to use:**
- Starting a new RAI project from Snowflake tables or local CSV files
- User has raw data and wants a base model to query or build on
- Bootstrapping an ontology before optimization or graph analysis

**When NOT to use:**
- Enriching an existing model — see `rai-ontology-design`
- Exported model — see `rai-ontology-design`
- PyRel syntax — see `rai-pyrel-coding`
- Query construction — see `rai-querying`

**Overview:**
1. Scope — what questions must the model answer?
2. Discover source data and run basic EDA
3. Identify concepts (domain-first)
4. Identify relationships and properties
5. Validate design against schema
6. Generate code
7. Validate with queries


---

## Instructions

**Required dependency:** `rai-ontology-design` is the authority for all design decisions. This skill is the workflow. Use `rai-pyrel-coding` for syntax and [data-loading.md](../rai-pyrel-coding/references/data-loading.md) for data binding patterns.

Start from the business domain — what concepts exist, what questions must the model answer — then find data mappings. Domain-first modeling produces better models than table-to-concept mapping.

Write and maintain a document to help people onboard and understand the decisionmaking process. Document your findings and decisions for each step.

**Interaction mode:** Before starting, ask the user which mode they prefer:
- **Guided** — present your proposed design at each step and confirm before proceeding. Best when the user has domain context or nuances to share along the way.
- **One-shot** — produce the best result you can in a single pass. Best when the user wants speed and will review/iterate after.

The user knows their domain better than the data does — guided mode lets them steer you through subtleties that aren't obvious from the schema alone.

### Step 1 — Scope

Before looking at any data, define:
- **1-3 concrete questions** the model must answer
- **What is out of scope** — explicitly exclude tables/domains not needed yet

Keep the first version to ~10-15 must-have properties.

| Goal | In scope | Out of scope |
|---|---|---|
| Identify delayed orders | Orders, shipments, delay timestamps | Returns, carrier contracts, inventory |

---

### Step 2 — Discover source data

#### 2a — Snowflake tables (recommended)

For connection setup, see `rai-onboarding`. Run discovery queries via the `snow` CLI or a Snowpark session:

```python
from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

session: snowpark.Session = create_config().get_session(SnowflakeConnection)
session.sql("""
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE
    FROM <database>.INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = '<schema>'
    ORDER BY TABLE_NAME, ORDINAL_POSITION
""").show()
```

#### 2b — Local CSV / DataFrame (prototyping only)

`model.data()` is for prototyping only (hundreds of rows). For production, load into Snowflake and use `model.Table()`.

#### Analysis

Analyze source data per `rai-ontology-design` § Source Table Analysis. Note:
- `_ID` suffixes (likely PKs), columns matching other tables' PKs (likely FKs)
- `IS_`/`HAS_` prefixes (boolean flags), repeated string categories (enums)
- Soft-joins (shared codes or categories across tables)

**Basic EDA:**

```sql
-- Row count and PK uniqueness
SELECT COUNT(*), COUNT(DISTINCT <pk_col>) FROM <database>.<schema>.<table>;

-- FK cardinality
SELECT COUNT(DISTINCT <fk_col>), COUNT(*) FROM <database>.<schema>.<table>;

-- Null rate
SELECT COUNT(*) AS total, COUNT(<col>) AS non_null,
    ROUND(1 - COUNT(<col>) / COUNT(*), 2) AS null_rate
FROM <database>.<schema>.<table>;

-- Value distribution for enum/category columns
SELECT <col>, COUNT(*) AS cnt FROM <database>.<schema>.<table>
GROUP BY <col> ORDER BY cnt DESC LIMIT 20;

-- Subtype discovery: look for TYPE/CATEGORY/CLASS columns with few values
-- that partition entities into fundamentally different kinds
-- e.g., BUSINESS_TYPE with values 'Supplier','Customer' → subtypes of Business
SELECT <type_col>, COUNT(*) AS cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM <database>.<schema>.<table>
GROUP BY <type_col> ORDER BY cnt DESC;

-- Relationship multiplicity: determine 1:1, 1:N, or M:N
-- Run for each FK to understand the join shape
SELECT
    ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT <fk_col>), 0), 2) AS avg_rows_per_fk,
    MAX(cnt) AS max_rows_per_fk
FROM (
    SELECT <fk_col>, COUNT(*) AS cnt
    FROM <database>.<schema>.<table>
    GROUP BY <fk_col>
);
```

---

### Step 3 — Identify concepts

Work domain-first: brainstorm business entities, then map to tables. Each concept must map to an authoritative source with a clear identity. Refer to `rai-ontology-design` § Concept Design Principles.

**Check for subtypes:** If Step 2 EDA found TYPE/CATEGORY columns that partition a concept into fundamentally different kinds (e.g., a `BUSINESS_TYPE` column with values `Supplier` and `Customer`), model these as subtypes using `extends`. Use subtypes when each kind carries its own properties or relationships — not for every enum column.

**Validate:**
- Each concept maps to at least one authoritative source
- Each concept has a clear identity
- Concepts are orthogonal (no two with identical entity sets)

---

### Step 4 — Identify relationships and properties

**Relationships** — FK columns, shared keys, business associations. Each link connects independently meaningful concepts. Use the multiplicity results from Step 2 EDA to determine whether each relationship is 1:1, 1:N, or M:N (junction concept).

**Properties** — remaining columns as attributes. Omit columns with no business meaning for the scoped questions.

Refer to `rai-ontology-design` § Relationship Principles.

---

### Step 5 — Validate design

Validate the proposed design against source data before coding:

| Check | What to confirm |
|-------|-----------------|
| Identity columns | Exist in source and uniquely identify rows |
| Relationships | Valid FK or join key exists |
| Properties | Source column exists with compatible data type |
| Concept grounding | Every concept maps to an authoritative source |
| Orthogonality | No two concepts represent the same entity set |

#### Type validation against Snowflake schema

Verify that every property's RAI type matches its Snowflake source column. Use this mapping:

| Snowflake type | RAI type | Notes |
|---|---|---|
| VARCHAR, TEXT, STRING | `String` | |
| NUMBER with scale > 0 (e.g., NUMBER(18,2)) | `Float` | Check `NUMERIC_SCALE` in INFORMATION_SCHEMA |
| NUMBER, INT, INTEGER (scale = 0) | `Integer` | |
| FLOAT, DOUBLE, REAL | `Float` | |
| DATE | `Date` | |
| TIMESTAMP_NTZ, TIMESTAMP_LTZ, TIMESTAMP | `DateTime` | |
| BOOLEAN | `Boolean` property, or unary `Relationship` for flag-style patterns | |

Run this query to pull actual column types for comparison:

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NUMERIC_PRECISION, NUMERIC_SCALE
FROM <database>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
  AND TABLE_NAME IN ('<table1>', '<table2>')
ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

Always run this query before writing property declarations. A type mismatch between the RAI property and the Snowflake column causes a `TyperError` at query time with no indication of which property failed.

**Common mismatches to check:**
- **DATE vs TEXT** — Columns with date-like names (`signup_date`, `created_at`) may be stored as TEXT in Snowflake, especially when loaded from CSV. Check the actual type; use `String` if the column is TEXT.
- **NUMBER precision** — A column typed `NUMBER(38,0)` is an integer, but `NUMBER(18,4)` is a float. Always check `NUMERIC_SCALE`; if scale > 0, use `Float`.
- **BOOLEAN** — Model as `Boolean` property or unary `Relationship(f"... is <flag>")`. Both work; prefer `Relationship` when the flag semantics read naturally (e.g., "Order is urgent").
- **Numeric IDs** — A column named `CREDIT_CARD_NUMBER` or `PHONE` may be NUMBER, not TEXT. Let the schema dictate the type, not the name.

---

### Step 6 — Generate code

Follow conventions in `rai-pyrel-coding` and `rai-ontology-design`. Organize the model as a package:

```
model/
├── __init__.py      # imports all submodules in dependency order
├── core.py          # model, source tables, concepts, properties, relationships, data binding
├── computed.py      # derived metrics, computed properties, subtypes (optional)
```

- `core.py` — `Model`, source table references, concepts, properties, relationships, and data bindings.
- `computed.py` — imports from `core.py`, adds derived metrics and subtypes. Only needed when scoped questions require values not directly in source data. See `rai-ontology-design` § Layering Principles.
- `__init__.py` — imports submodules in dependency order.

---

### Step 7 — Validate with queries

Create a `main.py` that imports the model and validates data loaded correctly before answering scoped questions. Fix any import errors or empty results before considering the starter ontology complete. For query syntax, see `rai-querying`.

> **Note:** Import aggregates with `from relationalai.semantics.std import aggregates`.

**7a — Count instances per concept** to confirm data binding loaded rows:

```python
from relationalai.semantics.std import aggregates

df = model.select(aggregates.count(MyConcept).alias("count")).to_df()
print(df)
# Expect: count matches source table row count. Zero means data binding failed.
```

**7b — Verify relationships** to confirm FK joins resolved:

```python
df = model.select(
    ConceptA.id.alias("a_id"),
    ConceptB.id.alias("b_id"),
).where(
    ConceptA.my_relationship(ConceptB)
).to_df()
print(f"Linked pairs: {len(df)}")
# Expect: non-empty results. Empty means the FK join didn't match.
```

**7c — Answer scoped questions** from Step 1:

```python
df = model.select(
    MyConcept.id.alias("id"),
    MyConcept.some_property.alias("value"),
).where(
    MyConcept.some_property > threshold
).to_df()
print(df)
# Each scoped question from Step 1 should be answerable with a query like this.
```

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Schema-driven names (`CUST_TABLE`, `ORD_AMT`) | Copying column/table names from schema | Use business domain names (`Customer`, `amount`) |
| Boolean columns as `Property` | Treating booleans as data values | Use unary `Relationship(f"... is active")` |
| Modeling every column | No scoping step | Only model columns relevant to scoped questions |
| `model.data()` for large datasets | Treating CSV/DataFrame as production-ready | Prototyping only (≤ hundreds of rows). Use `model.Table()` |
| Wrong Snowflake table path | Incorrect database, schema, or table name | Verify with `SHOW TABLES IN SCHEMA <db>.<schema>` |
| "Object does not exist" on valid table | Snowflake role lacks access | Check `SELECT CURRENT_ROLE()` and `SHOW GRANTS ON <object>` |
| Model won't load or sync | Engine not running or misconfigured connection | See `rai-configuration` and `rai-health-skill` |
| Skipping scope | Starting from tables instead of questions | Complete Step 1 before Step 2 |
