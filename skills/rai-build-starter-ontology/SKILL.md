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
7. Validate with queries, then emit `inspect.schema()` summary so the user sees what actually registered


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

**Data loading decision:** Use `model.Table()` for Snowflake-backed data (any size, production-ready). Use `model.data()` for prototyping with DataFrames only (≤ hundreds of rows) or inline scenario data not in Snowflake.

#### 2a — Snowflake tables (recommended)

For connection setup, see `rai-onboarding`. Run discovery queries via the `snow` CLI or a Snowpark session:

```python
from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

session: snowpark.Session = create_config().get_session(SnowflakeConnection)
session.sql("""
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
           NUMERIC_PRECISION, NUMERIC_SCALE
    FROM <database>.INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = '<schema>'
    ORDER BY TABLE_NAME, ORDINAL_POSITION
""").show()
```

> **Keep this result available throughout the workflow.** The `DATA_TYPE` and `NUMERIC_SCALE` columns are the authoritative source for deriving RAI property types in Step 6. When declaring each property, look up its source column in this result and use the type mapping table (Step 5) to pick the correct RAI type. Do not infer types from column names, CSV samples, or example ontologies.

#### 2b — Local CSV / DataFrame (prototyping only)

`model.data()` is for prototyping only (hundreds of rows). For production, load into Snowflake and use `model.Table()`.

#### Analysis

**Identify data shape first.** Source tables typically arrive in one of two shapes, and the distinction drives whether downstream steps derive metrics or bind them directly:

- **Raw events / measurements** — one row per occurrence; metrics of interest must be *derived* in a downstream computed layer from the raw rows.
- **Pre-aggregated statistics** — one row per entity, per pair, or per time bucket carrying already-computed values (including long-form `(entity_i, entity_j, value)` matrices). Metrics arrive ready-to-bind; do not re-aggregate already-aggregated values.

Two tables in the same schema can be different shapes — classify each independently. For long-form pairwise data specifically, see the pairwise value matrix example in [examples.md](references/examples.md).

Analyze source data per `rai-ontology-design` § Design Decision Sequence, step 1 (Analyze sources). Note:
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

**For graph/network models — trace the topology before modeling:**

When your data describes a network (nodes connected by edges via FK chains), trace the full path before Step 3:

```sql
-- What node types connect to what? Reveals tiers and layers.
SELECT source.TYPE AS from_type, dest.TYPE AS to_type, COUNT(*) AS edges
FROM <edge_table> e
JOIN <node_table> source ON e.SOURCE_ID = source.ID
JOIN <node_table> dest ON e.DEST_ID = dest.ID
GROUP BY from_type, to_type ORDER BY edges DESC;

-- Check for NULL FKs that create invisible network gaps
SELECT COUNT(*) AS broken_edges FROM <edge_table> WHERE DEST_ID IS NULL OR SOURCE_ID IS NULL;
```

This reveals hidden layers, missing connections, and whether you need intermediate concepts to bridge tiers.

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

Always run this query before writing property declarations. A single type mismatch between any RAI property and its Snowflake column causes a `TyperError` that blocks ALL queries on the entire model — not just the mismatched property — with no indication of which property failed.

**Common mismatches to check:**
- **DATE vs TEXT** — Columns with date-like names (`signup_date`, `created_at`) may be stored as TEXT in Snowflake, especially when loaded from CSV. Check the actual type; use `String` if the column is TEXT.
- **NUMBER precision** — A column typed `NUMBER(38,0)` maps to `Integer`, but `NUMBER(18,4)` maps to `Float`. Always check `NUMERIC_SCALE`; if scale > 0, use `Float`. If a `NUMBER(38,0)` column holds values that are conceptually continuous (e.g., `CAPACITY_MW`, `COST_MILLION`), flag this to the user — the DDL may need `FLOAT` or `NUMBER(18,2)` instead.
- **BOOLEAN** — Model as `Boolean` property or unary `Relationship(f"... is <flag>")`. Both work; prefer `Relationship` when the flag semantics read naturally (e.g., "Order is urgent").
- **Numeric IDs** — A column named `CREDIT_CARD_NUMBER` or `PHONE` may be NUMBER, not TEXT. Let the schema dictate the type, not the name.

---

### Step 6 — Generate code

> **GATE: Do not proceed until Step 5 type validation is complete.**

Use the type mapping table and `INFORMATION_SCHEMA.COLUMNS` output from Step 5 to derive every property type.

Follow conventions in `rai-pyrel-coding` and `rai-ontology-design`. Put everything in a single file named after the domain:

```
<domain>.py     # e.g., supply_chain.py, fraud.py, inventory.py
```

A single file is easiest to iterate on. When the model grows (multiple reasoners, derived layers, shared computed logic), split into a package — see `rai-ontology-design` § Layering Principles.

> **If you do split into a package:** Never name the directory `model/` if your `Model` variable is also called `model`. Python resolves `import model.xxx` to the directory, shadowing the variable. Use a domain-specific name (e.g., `sc_model/`, `fraud_model/`).

---

### Step 7 — Validate with queries

Add validation queries to the bottom of your `<domain>.py` file to confirm data loaded correctly before answering scoped questions. Fix any import errors or empty results before considering the starter ontology complete. For query syntax, see `rai-querying`.

> **Note:** Import aggregates with `from relationalai.semantics.std import aggregates`.

**7a — Spot-check property types against schema** before running any queries. For each `BOOLEAN`, `DATE`, and `NUMBER` column in the Step 2 schema output, confirm the corresponding property declaration uses the correct RAI type. These three are the most common sources of silent type mismatches (`TyperError` at query time with no indication of which property failed). Fix any mismatch before proceeding.

**7b — Count instances per concept** to confirm data binding loaded rows:

```python
from relationalai.semantics.std import aggregates

df = model.select(aggregates.count(MyConcept).alias("count")).to_df()
print(df)
# Expect: count matches source table row count. Zero means data binding failed.
```

> **Note:** `aggregates.count(C)` on a concept with zero instances returns an empty DataFrame (no rows), not a DataFrame with `count=0` — the underlying relation is empty so the aggregation has no rows to reduce over. For chained workflows where a placeholder concept is populated by a downstream step, use `inspect.schema()` membership to verify the concept is declared rather than `count()` to verify data.

**7c — Verify relationships** to confirm FK joins resolved:

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

**7d — Answer scoped questions** from Step 1:

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

**7e — Report what actually registered.** After the model runs cleanly, emit an `inspect.schema()` summary for the user. This is the canonical "here's what got built" artifact — distinct from "here's what I intended to build."

```python
from relationalai.semantics import inspect

schema = inspect.schema(model)

# Full dump for small models
print(schema)

# Targeted per-concept inspection for larger models
for concept_name in scoped_concepts:
    c = schema[concept_name]
    idents = ", ".join(f"{f.name}:{f.type_name}" for f in c.identify_by)
    print(f"{concept_name} [id: {idents}], extends={c.extends}")
    for prop in c.properties:
        print(f"  .{prop.name}: {prop.type_name}")
    for rel in c.relationships:
        print(f"  ~{rel.name}: {rel.reading}")

# Data sources — tables and inline data (schema.tables includes both model.Table() and model.data())
print(f"Tables: {[t.name for t in schema.tables]}")
```

This is the trust-building step. `inspect.schema()` *enriches* the summary with table-backed type information — for properties created via `Concept.new(table.to_schema())`, it infers and reports concrete types (`Integer`, `String`, `Date`) from the backing table even when the frontend model still types them as `Any`. The engine produces correctly-typed output regardless (it reads the backing data), but the `inspect` summary gives you a human-readable view of what the data actually carries. See `rai-querying/references/inspect-module.md`.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Schema-driven names (`CUST_TABLE`, `ORD_AMT`) | Copying column/table names from schema | Use business domain names (`Customer`, `amount`) |
| Boolean columns as `String` | Guessing types from column names or example ontologies instead of Snowflake schema | Always derive types from `INFORMATION_SCHEMA.COLUMNS` `DATA_TYPE`; BOOLEAN → `Boolean` property or unary `Relationship` |
| Boolean columns as `Boolean` property | Using a scalar property when the column represents a semantic flag | Prefer unary `Relationship(f"... is active")` for flag-style booleans |
| Modeling every column | No scoping step | Only model columns relevant to scoped questions |
| `model.data()` for large datasets | Treating CSV/DataFrame as production-ready | Prototyping only (≤ hundreds of rows). Use `model.Table()` |
| Wrong Snowflake table path | Incorrect database, schema, or table name | Verify with `SHOW TABLES IN SCHEMA <db>.<schema>` |
| "Object does not exist" on valid table | Snowflake role lacks access | Check `SELECT CURRENT_ROLE()` and `SHOW GRANTS ON <object>` |
| Model won't load or sync | Engine not running or misconfigured connection | See `rai-configuration` and `rai-health-skill` |
| `SnowflakeChangeTrackingNotEnabledException` on first query | `model.Table()` requires change tracking on each source table | Add `ensure_change_tracking=True` to `Model()` constructor, or run `ALTER TABLE <db>.<schema>.<table> SET CHANGE_TRACKING = TRUE` on each source table |
| Stale data source cleanup takes minutes on re-run | Re-using a model name after changing data bindings triggers stale source removal | Use a fresh model name during rapid iteration, or wait for cleanup to complete |
| Skipping scope | Starting from tables instead of questions | Complete Step 1 before Step 2 |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Starter ontology examples | Build patterns: Snowflake tables, CSV, derived concepts, junction concepts, self-referential hierarchies, pairwise matrices, portable source paths | [examples.md](references/examples.md) |

---

## What's Next

After your starter ontology validates and queries correctly, the typical next steps are:

**Build starter ontology → Discover problems (`rai-discovery`) → Enrich model (`rai-ontology-design`) → Formulate (`rai-prescriptive-problem-formulation` or `rai-graph-analysis`)**

| Step | Skill | What it does |
|------|-------|-------------|
| 1. Discover what problems your model can answer | `rai-discovery` | Surfaces questions by reasoner type (prescriptive, graph, rules, predictive) and assesses data readiness |
| 2. Enrich the model for a selected problem | `rai-ontology-design` § Enrichment Workflow | Adds properties and relationships from unmapped source columns needed by the problem |
| 3. Identify and fill model gaps | `rai-ontology-design` § Model Gap Identification | Classifies gaps as READY / MODEL_GAP / DATA_GAP and prescribes fixes |
| 4. Add advanced patterns (as needed) | `rai-ontology-design` § reference files | Subtypes, enums, time-indexed properties, hierarchies, cross-product concepts, model composition |
