# Probing Strategies

SQL queries and procedures used in SRP **Step 1 (Inventory)** and **Step 5 (Probe samples)**. Per-dialect introspection plus per-probe sample queries, with sample-size caps, timeouts, and confidence thresholds.

Load at SRP Steps 1 and 5.

Cross-references:
- Output shape (where probe results land in the YAML) → [representation-format.md](representation-format.md), per-source provenance section.
- Antipattern detection (Step 7 builds on probe results) → [antipattern-catalog.md](antipattern-catalog.md).

## Defaults (configurable)

| Knob | Default | Rationale |
|---|---|---|
| Sample size cap | 10,000 rows | Trades probe accuracy for runtime; 10k saturates most enums and gives stable percentiles. |
| Sample size minimum for `confirmed` promotion | 1,000 rows | Below this, `proposed` only. Prevents tiny tables from over-influencing the model. |
| Query timeout | 60 s per probe | Aborted probes degrade to `proposed`, never block the SRP. |
| Enum-detection cardinality threshold | < 20 distinct values | Above this, treat as free-text rather than enumeration. |
| NULL-rate threshold for mandatory inference | < 0.1% | Reinforces explicit NOT NULL; doesn't override schema where NULL is allowed. |
| Distinct-count saturation | distinct count unchanged across last 1000 rows of sample | Probe is "saturated" — `confirmed` promotion eligible. |

These defaults are recorded in `source.scope.probe_defaults` of the YAML when overrides are applied. Phase 3 might tighten them after the first full eval run; v0.1 is conservative.

## Step 1 — Inventory (per-dialect introspection)

Targeting: tables, columns (name, type, nullability, default, comment), PKs, FKs, UNIQUE indexes, CHECK constraints, table-level comments.

### Snowflake

```sql
-- Tables
SELECT TABLE_SCHEMA, TABLE_NAME, COMMENT
FROM <database>.INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = '<schema>' AND TABLE_TYPE = 'BASE TABLE';

-- Columns
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE,
       IS_NULLABLE, COLUMN_DEFAULT, NUMERIC_PRECISION, NUMERIC_SCALE,
       COMMENT
FROM <database>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- Primary keys
SHOW PRIMARY KEYS IN SCHEMA <database>.<schema>;

-- Foreign keys
SHOW IMPORTED KEYS IN SCHEMA <database>.<schema>;

-- Unique constraints
SHOW UNIQUE KEYS IN SCHEMA <database>.<schema>;

-- Check constraints (limited — Snowflake stores CHECKs but exposes them via INFORMATION_SCHEMA inconsistently)
SELECT *
FROM <database>.INFORMATION_SCHEMA.CHECK_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = '<schema>';
```

`SHOW`-result rows must be flattened into a uniform schema-description structure before they're handed to Step 2.

### Postgres

```sql
-- Tables
SELECT n.nspname AS schema, c.relname AS table_name,
       obj_description(c.oid, 'pg_class') AS comment
FROM pg_class c
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE n.nspname = '<schema>' AND c.relkind = 'r';

-- Columns
SELECT table_name, column_name, ordinal_position, data_type,
       is_nullable, column_default, numeric_precision, numeric_scale,
       col_description((table_schema || '.' || table_name)::regclass::oid, ordinal_position) AS comment
FROM information_schema.columns
WHERE table_schema = '<schema>'
ORDER BY table_name, ordinal_position;

-- Primary keys
SELECT tc.table_name, kcu.column_name, kcu.ordinal_position
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema)
WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = '<schema>'
ORDER BY tc.table_name, kcu.ordinal_position;

-- Foreign keys
SELECT tc.table_name, kcu.column_name, ccu.table_name AS references_table, ccu.column_name AS references_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema)
JOIN information_schema.constraint_column_usage ccu USING (constraint_name, table_schema)
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = '<schema>';

-- Unique constraints
SELECT tc.table_name, tc.constraint_name, kcu.column_name, kcu.ordinal_position
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema)
WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = '<schema>';

-- Check constraints
SELECT tc.table_name, tc.constraint_name, cc.check_clause
FROM information_schema.table_constraints tc
JOIN information_schema.check_constraints cc USING (constraint_name, constraint_schema)
WHERE tc.constraint_type = 'CHECK' AND tc.table_schema = '<schema>';
```

### MySQL

```sql
-- Tables
SELECT TABLE_NAME, TABLE_COMMENT
FROM information_schema.tables
WHERE TABLE_SCHEMA = '<schema>' AND TABLE_TYPE = 'BASE TABLE';

-- Columns
SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, DATA_TYPE,
       IS_NULLABLE, COLUMN_DEFAULT, NUMERIC_PRECISION, NUMERIC_SCALE,
       COLUMN_COMMENT
FROM information_schema.columns
WHERE TABLE_SCHEMA = '<schema>'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- Primary keys, foreign keys, unique constraints
SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.key_column_usage
WHERE TABLE_SCHEMA = '<schema>'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

-- (Constraint type — PK, UNIQUE, FK — joined from information_schema.table_constraints)
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE
FROM information_schema.table_constraints
WHERE TABLE_SCHEMA = '<schema>';

-- Check constraints (MySQL 8.0.16+)
SELECT TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE
FROM information_schema.check_constraints
WHERE CONSTRAINT_SCHEMA = '<schema>';
```

### Oracle

Use `ALL_*` views (or `USER_*` if scoped to current user; `DBA_*` requires DBA privileges).

```sql
-- Tables
SELECT OWNER, TABLE_NAME, COMMENTS
FROM ALL_TAB_COMMENTS
WHERE OWNER = '<schema>' AND TABLE_TYPE = 'TABLE';

-- Columns
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_ID AS ORDINAL_POSITION, DATA_TYPE,
       NULLABLE, DATA_DEFAULT, DATA_PRECISION, DATA_SCALE
FROM ALL_TAB_COLUMNS
WHERE OWNER = '<schema>'
ORDER BY TABLE_NAME, COLUMN_ID;

-- Constraints (PK, UNIQUE, FK, CHECK all in one view)
SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE,    -- P, U, R (FK), C (CHECK)
       SEARCH_CONDITION,                                 -- CHECK clause when CONSTRAINT_TYPE = 'C'
       R_OWNER, R_CONSTRAINT_NAME                        -- referenced constraint when FK
FROM ALL_CONSTRAINTS
WHERE OWNER = '<schema>';

-- Constraint columns
SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, POSITION
FROM ALL_CONS_COLUMNS
WHERE OWNER = '<schema>'
ORDER BY TABLE_NAME, CONSTRAINT_NAME, POSITION;
```

Oracle's `NULLABLE` is `'Y'`/`'N'`, not `YES`/`NO` — normalise on the way in. `DATA_TYPE` for `NUMBER` columns requires reading `DATA_PRECISION` and `DATA_SCALE` (scale > 0 → `Number.size(p,s)`; scale 0 → `Integer`).

### SQLite

SQLite doesn't have a standard `INFORMATION_SCHEMA`. Use the `pragma_*` virtual tables.

```sql
-- Tables
SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%';

-- Columns (per table)
SELECT * FROM pragma_table_info('<table>');
-- Columns: cid, name, type, notnull, dflt_value, pk

-- Foreign keys (per table)
SELECT * FROM pragma_foreign_key_list('<table>');
-- Columns: id, seq, table, from, to, on_update, on_delete, match

-- Indexes (per table) — UNIQUE indexes can be detected from this
SELECT * FROM pragma_index_list('<table>');
-- Columns: seq, name, unique, origin, partial

SELECT * FROM pragma_index_info('<index_name>');
-- Columns: seqno, cid, name
```

SQLite has limited CHECK constraint introspection — they live in the `CREATE TABLE` SQL text accessible via `sqlite_master.sql`. Parsing that DDL is the only way to recover them.

### DDL-file input

Parse with a dialect-aware SQL parser. Same target structure as live introspection:
- `CREATE TABLE` → tables + columns + inline constraints (PK, UNIQUE, NOT NULL, CHECK, FK)
- `ALTER TABLE … ADD CONSTRAINT` → constraints not declared inline
- `CREATE [UNIQUE] INDEX` → indexes (UNIQUE indexes are equivalent to UNIQUE constraints)
- `COMMENT ON …` (Postgres / Oracle / Snowflake) → comments

Phase 4 picks the parser library; sqlglot or sqlparse are both reasonable starting points. v0.1's CSV path doesn't need DDL parsing.

### CSV input

CSV inputs have no DDL. Step 1 produces:
- Tables = filenames (one CSV per table).
- Columns = CSV headers, with types inferred from sampled rows.
- No PKs / FKs / NOT NULLs / UNIQUEs / CHECKs.

Type inference rules (per column):
- All values parse as integers → `Integer`.
- All values parse as decimals → `Float` (default) or `Number.size(p,s)` if all values fit one precision/scale.
- All values parse as ISO-8601 dates → `Date`. ISO-8601 datetimes → `DateTime`.
- Values restricted to {`true`/`false`/`0`/`1`/`Y`/`N`} → flag for `Boolean` candidate (Step 7 antipattern catalog).
- All values match `^[0-9]+$` and the column name ends in `_id` → flag as PK candidate (Step 7 missing-PK).
- Otherwise `String`.

CSV input forces `source.confidence: low` and disables Step 5 confirmation promotion (everything stays `proposed`).

## Step 5 — Sample probes

For each probe type below: the SQL pattern, when to run it, what constraint it produces, and the saturation/promotion rule.

### Distinct-value enumeration

**When:** column has `data_type IN ('VARCHAR', 'TEXT', 'CHAR')` and either (a) name ends in `STATUS`, `TYPE`, `KIND`, `CATEGORY`, `STATE`, `LEVEL`, `CLASS`, or (b) explicit user request to probe.

**Query:**
```sql
SELECT DISTINCT <column>
FROM <table>
WHERE <column> IS NOT NULL
LIMIT <enum-detection cardinality threshold + 1>;
```

The `+1` lets us detect "more than threshold" without scanning the full table.

**Decision:**
- Distinct-count ≤ threshold → propose `value` constraint with `allowed: [<distinct values>]`. `source: sample`.
- Distinct-count > threshold → not enum; treat as free-text.

**Saturation:** with the `LIMIT threshold+1` query, distinct-count saturation is automatic. If the result has ≤ threshold rows, the enum is fully observed.

**Provenance recorded:**
```yaml
provenance:
  sample_query: "SELECT DISTINCT STATUS FROM PUBLIC.ORDERS WHERE STATUS IS NOT NULL LIMIT 21"
  sample_size: 5                                # actual distinct count
  saturation: true
  observed_values: ['PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED']
```

### Numeric range

**When:** column has numeric type AND name matches `(AGE|PRICE|AMOUNT|QUANTITY|COUNT|PERCENT|RATE|SCORE|TEMPERATURE|WEIGHT|HEIGHT|LENGTH|WIDTH|DURATION|SECONDS|MINUTES|HOURS|DAYS)` (case-insensitive). For arbitrary numeric columns, `source: sample` with `confidence: low`.

**Query:**
```sql
SELECT MIN(<column>) AS min_v, MAX(<column>) AS max_v, COUNT(*) AS n
FROM <table>
WHERE <column> IS NOT NULL;
```

**Decision:**
- If the observed min and max look meaningful for the named domain (e.g., `AGE → [0, 120]`), propose `value` constraint with `range: { min, max }` widened slightly to express the constraint as a hypothesis rather than a tight fit (e.g., `[0, 150]` for AGE rather than `[0, 120]`).
- For arbitrary numeric columns, propose only a hypothesis range with rationale "observed min/max in sample".

**Provenance:**
```yaml
provenance:
  sample_query: "SELECT MIN(AGE), MAX(AGE), COUNT(*) FROM PUBLIC.PEOPLE WHERE AGE IS NOT NULL"
  sample_size: 5234
  observed_range: { min: 0, max: 119 }
```

### Mandatory bound (NULL rate)

**When:** column does NOT have explicit NOT NULL constraint.

**Query:**
```sql
SELECT
  COUNT(*) AS total,
  COUNT(<column>) AS non_null,
  ROUND(1 - COUNT(<column>)::float / NULLIF(COUNT(*), 0), 6) AS null_rate
FROM <table>;
```

**Decision:**
- `null_rate < threshold` (default 0.001) → propose mandatory on the corresponding role. `source: sample`.
- `null_rate >= threshold` → don't propose mandatory; the column is genuinely optional.

The threshold default (0.1%) is conservative — it accepts mandatoriness only when violations are rare enough to be data-quality noise. Tighten in Phase 3 if false positives surface.

**Provenance:**
```yaml
provenance:
  sample_query: "SELECT COUNT(*), COUNT(EMAIL), null_rate FROM PUBLIC.CUSTOMERS"
  sample_size: 12345
  null_rate: 0.0
```

### Frequency bounds (counted)

**When:** binary fact type with a sound interpretation of "many B per A" — typically header-detail relationships (Order → OrderItem; Invoice → InvoiceLine). Propose only when the relationship name strongly suggests counting (column name ending in `_id` and the parent table name appearing as a prefix).

**Query:**
```sql
SELECT MIN(c) AS min_count, MAX(c) AS max_count,
       AVG(c) AS avg_count, COUNT(*) AS n_groups
FROM (
  SELECT <fk_column>, COUNT(*) AS c
  FROM <child_table>
  GROUP BY <fk_column>
) g;
```

**Decision:**
- Tight bounds (max < 20, min > 0) → propose internal frequency constraint with the observed min/max (widened slightly).
- Wide bounds → don't propose; the cardinality is genuinely unbounded.

**Provenance:**
```yaml
provenance:
  sample_query: "SELECT MIN(c), MAX(c), AVG(c) FROM (SELECT order_id, COUNT(*) c FROM PUBLIC.ORDER_ITEM GROUP BY order_id) g"
  sample_size: 542
  observed_range: { min: 1, max: 5 }
```

### Functional dependency (sample-only uniqueness)

**When:** non-PK column suspected unique by sample (columns ending in `_CODE`, `_KEY`, `_NUMBER` without DDL UNIQUE).

**Query:**
```sql
SELECT COUNT(*) AS total, COUNT(DISTINCT <column>) AS distinct_count
FROM <table>
WHERE <column> IS NOT NULL;
```

**Decision:**
- `total = distinct_count` AND total ≥ minimum-size threshold → **flag as Step 7 antipattern candidate** (missing UNIQUE constraint). Do **NOT** auto-propose a UC. The schema author may have allowed duplicates intentionally.
- Otherwise → no flag.

The discipline here is firm: data being unique today does not mean uniqueness is required. Step 7 surfaces the candidate for user confirmation in Step 9c; only then does it become a UC.

### Subset / inclusion (cross-fact-type sample)

**When:** explicit user request, or a strong hypothesis from common-sense library (e.g., "smokers are cancer-prone"). Don't auto-probe — too combinatorial.

**Query:**
```sql
SELECT
  (SELECT COUNT(*) FROM <subset_table> WHERE <subset_predicate>) AS subset_count,
  (SELECT COUNT(*) FROM <subset_table> sb
     LEFT JOIN <super_table> su ON <join_condition>
     WHERE <subset_predicate> AND <super_predicate> IS NULL) AS subset_minus_super_count;
```

**Decision:**
- `subset_minus_super_count = 0` → subset constraint holds in the sample. Propose with `source: sample`.
- Otherwise → don't propose.

Subset/exclusion sample probes are bounded — only run when the proposer asks for them.

## Probing budget

Per SRP run, the cumulative probe budget is bounded:
- Wall-clock cap: 5 minutes total across all probes (Phase 3 default; tunable).
- Probe count cap: 100 probes (one per column for enum/range/mandatory; one per FK for frequency).

When the budget exhausts, remaining probes are skipped and their target constraints stay `proposed` without sample provenance. This prevents the SRP from stalling on giant schemas.

The budget tracker writes a one-line summary to `source.scope.probe_summary`:
```yaml
probe_summary:
  ran: 87
  skipped_budget: 13
  total_seconds: 142
```

## Failure handling

Probes can fail for many reasons (permissions, dialect quirks, query timeouts, transient connectivity). Failure handling:

- A probe that errors → don't crash; skip the probe, leave the target constraint at `proposed` (or omit if the probe was the only signal), and record the error code in `source.scope.probe_errors`.
- A probe that times out → same as error; record `timeout` as the error code.
- A dialect missing one of the introspection paths above → degrade gracefully; emit `source.confidence: low` if a critical path is missing (e.g., no FK introspection on a non-standard dialect).

The SRP **never** fails because of a probe failure. Probes are best-effort enrichment, not blocking.

## Live vs DDL-only vs CSV — promotion summary

| Input kind | Step 4 (explicit) | Step 5 sample probes | Promotion rule |
|---|---|---|---|
| Live SQL | DDL → `confirmed` | Run, save provenance | Saturation + sample ≥ 1000 → `confirmed`; else `proposed` |
| DDL file | DDL → `confirmed` | Skipped | All Step 5 outputs absent; antipatterns still detected from DDL alone |
| CSV | (no DDL) | Run, save provenance | Always `proposed` — no schema authority to corroborate against |

The promotion rule is the single point where input kind influences the YAML's status field. Everything else (constraint shape, provenance fields, antipattern detection) is uniform across input kinds.
