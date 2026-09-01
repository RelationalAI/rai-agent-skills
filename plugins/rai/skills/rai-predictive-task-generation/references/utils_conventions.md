# SQL Conventions

## CTE structure

Always wrap the INSERT population logic in a named CTE chain. Never use a single deeply nested SELECT. Each CTE does one thing and has a one-line comment explaining what it does.

Snowflake requires `INSERT INTO <table>` to come *before* the `WITH` clause — `WITH ... INSERT INTO ... SELECT` is a syntax error (`unexpected 'INSERT'`), even though it parses in some SQL linters. The `WITH` clause belongs to the `SELECT` that follows `INSERT INTO`, not the other way around:

```sql
INSERT INTO my_schema.task_table
WITH
-- All cutoff timestamps to generate labels for
cutoffs AS (
    SELECT DISTINCT cutoff_ts FROM my_schema.cutoff_calendar
    WHERE cutoff_ts BETWEEN '2022-01-01' AND '2023-12-01'
),
-- Active entities: at least one event in the lookback window before each cutoff
active_entities AS (
    SELECT c.cutoff_ts, e.entity_id
    FROM cutoffs c
    JOIN my_schema.events e
      ON e.event_ts <= c.cutoff_ts
     AND e.event_ts >  DATEADD('day', -90, c.cutoff_ts)
    GROUP BY 1, 2
),
-- Label: did the entity have any event in the prediction window?
labeled AS (
    SELECT
        a.cutoff_ts,
        a.entity_id,
        MAX(CASE WHEN e.event_ts > a.cutoff_ts
                  AND e.event_ts <= DATEADD('day', 90, a.cutoff_ts)
             THEN 1 ELSE 0 END)::SMALLINT AS label
    FROM active_entities a
    LEFT JOIN my_schema.events e
      ON e.entity_id = a.entity_id
    GROUP BY 1, 2
)
SELECT cutoff_ts, entity_id, label FROM labeled;
```

## Output structure — schema + staging + 3 split tables

Always generate this four-object structure. Never write a single table with a `split` column as the final output — the downstream `rai-predictive-modeling` step expects three separate Snowflake tables (one per split).

```
DATABASE/
└── TASK_SCHEMA/                  ← new schema, one per task
    ├── STAGING                   ← full dataset + split column; validate here first
    ├── TRAIN                     ← entity_id, <table>_<source_time_col>, label  (+ value if applicable)
    ├── VAL                       ← same columns as TRAIN
    └── TEST                      ← same columns as TRAIN (label kept for post-hoc eval)
```

STAGING carries two columns the final split tables never do: `cutoff_<table>_<source_time_col>` (the evaluation timestamp, used only for split assignment) and `split` itself. Both are dropped when materializing TRAIN/VAL/TEST. What survives into the final tables is `<table>_<source_time_col>` — the model's temporal anchor — which equals the cutoff in value for most tasks but is a distinct column with its own name. See the parent skill's [Downstream column naming contract](../SKILL.md#downstream-column-naming-contract) for the full naming rules, and `task_binary.md` for a fully worked example of this shape.

**Generation order in the SQL artifact:**

1. `CREATE SCHEMA IF NOT EXISTS DATABASE.TASK_SCHEMA`
2. `CREATE OR REPLACE TABLE DATABASE.TASK_SCHEMA.STAGING (... split VARCHAR(8) ...)` + INSERT
3. All validation queries (run against STAGING)
4. `CREATE OR REPLACE TABLE DATABASE.TASK_SCHEMA.TRAIN AS SELECT * EXCLUDE (cutoff_<table>_<source_time_col>, split) FROM STAGING WHERE split = 'train'`
5. Same for VAL and TEST

This way the user validates the full dataset in one place before committing to the 3 final tables, and rerunning the split tables is cheap (no recomputation — just a filter on STAGING).

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.CHURN_TASK;

-- Step 2: staging (full CTE chain + INSERT)
CREATE OR REPLACE TABLE PROD_DB.CHURN_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source event-time column's type>  NOT NULL,  -- DATE, TIMESTAMP_NTZ, etc. — match the source, don't cast; STAGING-only
    orders_order_ts         <source event-time column's type>  NOT NULL,  -- temporal anchor (has_time_column=True); same type as above; carries into TRAIN/VAL/TEST
    label                   SMALLINT       NOT NULL,
    split                   VARCHAR(8)     NOT NULL
);
-- ... INSERT INTO PROD_DB.CHURN_TASK.STAGING WITH (...) ...

-- Step 3: validate on STAGING (see Validation query template below)

-- Step 4: materialize split tables — drop the STAGING-only cutoff and split columns
CREATE OR REPLACE TABLE PROD_DB.CHURN_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CHURN_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.CHURN_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CHURN_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.CHURN_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CHURN_TASK.STAGING WHERE split = 'test';
```

The `cutoff_<table>_<source_time_col>` and `split` columns live only in STAGING. TRAIN/VAL/TEST carry `<table>_<source_time_col>` instead of either.

## Fully-qualified table names

Always use 3-part names (`DATABASE.SCHEMA.TABLE`) in every SQL statement — DDL, INSERT, SELECT, and validation queries. Never use placeholders like `<your_schema>` or `my_schema` in the final generated artifact; the user confirmed the real names in Turn 1A.

```sql
-- correct
CREATE OR REPLACE TABLE PROD_DB.SALES.churn_task (...);
SELECT * FROM PROD_DB.SALES.orders WHERE ...;

-- wrong — forces the user to find and replace
CREATE OR REPLACE TABLE my_schema.churn_task (...);
SELECT * FROM <your_schema>.orders WHERE ...;
```

## Column naming — mandatory

These names are not suggestions. The downstream `rai-predictive-modeling` step binds the task table via a `Relationship` template that uses these exact names — see the parent skill's [Downstream column naming contract](../SKILL.md#downstream-column-naming-contract) for the full table.

If the source data uses a different name (e.g., `churned`, `revenue`), alias it — do not pass the raw name through.

## Case-sensitive column identifiers

In Snowflake, unquoted identifiers are stored and matched case-insensitively (Snowflake uppercases them internally). If a column was created with double quotes — e.g. `CREATE TABLE t ("review_time" TIMESTAMP_LTZ)` — it is case-sensitive and **must** be referenced with double quotes in every query. Referencing it unquoted will produce `invalid identifier 'REVIEW_TIME'`.

**How to detect this:** when `information_schema.columns` returns a column name in lowercase (e.g. `review_time`), it was almost certainly created with double quotes and requires quoted references in SQL.

**Rule:** after running the schema discovery query in Turn 1A, check whether any column names are returned in lowercase. If they are, wrap every reference to those columns in double quotes throughout the generated SQL:

```sql
-- column created as "review_time" — must be quoted everywhere
r."review_time"
r."customer_id"
```

Unquoted references to such columns will fail at runtime even though the column clearly exists.

## Timestamps

Keep the source event-time column's native type — do not cast or normalize it. If the source is `DATE`, the cutoff/anchor columns stay `DATE`. If it's `TIMESTAMP_NTZ`, they stay `TIMESTAMP_NTZ`. The value passes straight through:

```sql
-- source order_date is whatever type it already is — pass it through unchanged
SELECT
    entity_id,
    cutoff_date AS cutoff_orders_order_ts,
    label
FROM labeled;
```

Never silently mix `TIMESTAMP_NTZ` and `TIMESTAMP_TZ` columns from different source tables within the same task table — if two source event columns disagree in type, pick one and say which, don't cast one into the other's type as a workaround.

## Deduplication

Use `QUALIFY ROW_NUMBER() OVER (...) = 1` instead of a subquery deduplication — **but only when there is already a window function in the query**. `QUALIFY` is a filter on window function results; Snowflake rejects it if there is no window function in the `SELECT` or `WHERE`.

```sql
-- correct: QUALIFY filters on a window function result
SELECT ... FROM t
QUALIFY ROW_NUMBER() OVER (PARTITION BY entity_id, cutoff_ts ORDER BY event_ts DESC) = 1

-- wrong: QUALIFY used as a plain WHERE — syntax error in Snowflake
SELECT ... FROM t
QUALIFY cutoff_date <= '2020-07-31'  -- ← no window function, this will fail

-- correct alternative for plain row filtering (e.g. date ceiling on a GENERATOR)
SELECT cutoff_date
FROM (
    SELECT DATEADD('week', seq4(), '2020-01-01'::DATE) AS cutoff_date
    FROM TABLE(GENERATOR(ROWCOUNT => 200))
)
WHERE cutoff_date <= '2022-12-31'::DATE
```

## Reserved words — avoid as column aliases

Snowflake reserves a number of common English words that look harmless. Never use these as column aliases without quoting:

`rows`, `value`, `date`, `time`, `timestamp`, `schema`, `table`, `column`, `order`, `group`, `select`, `from`, `where`, `level`, `position`, `start`, `end`, `index`, `count`, `rank`, `percent`, `prior`, `match`, `next`, `first`, `last`

Use descriptive alternatives: `row_count` instead of `rows`, `target_value` instead of `value` (in validation queries — the task table column itself must still be named `value`), `cutoff_date` instead of `date`, etc.

## Comments

One line per CTE, stating what it does. No multi-line comment blocks. No comments restating what the code already says clearly.

## Validation query template

Always append a validation query after the INSERT. It must report:

1. Row count and null counts per column
2. Class balance (classification) or target percentiles (regression)
3. Temporal sanity: no row has event data from after its `cutoff_ts`
4. Duplicate check: no duplicate `(entity_id, cutoff_ts)` rows

```sql
-- Validation
SELECT
    COUNT(*)                                          AS total_rows,
    COUNT(*) - COUNT(entity_id)                      AS null_entity,
    COUNT(*) - COUNT(cutoff_ts)                      AS null_cutoff,
    COUNT(*) - COUNT(label)                          AS null_label,
    SUM(label)                                       AS positive_count,
    ROUND(AVG(label::FLOAT), 4)                      AS positive_rate,
    COUNT(*) - COUNT(DISTINCT entity_id || '|' || cutoff_ts::VARCHAR) AS duplicates
FROM my_schema.task_table;
```
