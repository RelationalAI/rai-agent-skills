# Regression — Reference

## Schema contract

Four objects are always generated — a schema, a staging table, and three split tables.

**STAGING** (full dataset — validate here):

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | e.g. `customer_id` |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `value` | `FLOAT` | the continuous target; column must be named `value` |
| `split` | `VARCHAR(8)` | `'train'` / `'val'` / `'test'` — for partitioning only |
| `<table>_<source_time_col>` (e.g. `orders_order_ts`) | same as `cutoff_<table>_<source_time_col>` — both come from the same source column | temporal tasks only (`has_time_column=True`) — the model's temporal anchor |

**TRAIN / VAL / TEST** (downstream inputs — no `split` column, no `cutoff_<table>_<source_time_col>` column):

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | |
| `value` | same as STAGING | kept in TEST for post-hoc evaluation |
| `<table>_<source_time_col>` | matches source event-time column's type | |

One row per `entity_id` in TRAIN/VAL/TEST, and per `(entity_id, cutoff_<table>_<source_time_col>)` in STAGING. No duplicates.

## Downstream binding

```python
Train = Relationship(f"{Customer} has {Any:value}")
define(Train(Customer, TrainTable.value)).where(Customer.customer_id == TrainTable.customer_id)

gnn = GNN(..., task_type="regression", eval_metric="rmse")
# prediction attributes: .predicted_value
# other available metrics: r2, mae
```

## Label logic

A regression target answers: **"What continuous value will entity X produce in `(cutoff_ts, cutoff_ts + Δ]`?"**

Common patterns:

| Framing | `value` = |
|---|---|
| 90-day revenue (LTV) | `SUM(order_amount)` in window; `0.0` if no orders |
| Next-period order count | `COUNT(*)` of orders in window; `0` if none |
| Average rating | `AVG(rating)` of reviews in window; only include entities with ≥ 1 review |
| Days until next event | `DATEDIFF('day', cutoff_ts, MIN(event_ts))` in window; NULL if no event |

**Always use `COALESCE(..., 0.0)`** for aggregation-based targets (sum, count) so that entities with no events in the window get a target of 0.0 rather than NULL. NULLs in the `value` column are dropped by the training step and silently reduce dataset size.

Exception: if 0.0 is not a meaningful target for entities with no events (e.g., "average rating" where no rating was given), filter those entities out rather than imputing 0.

## SQL template — 90-day revenue

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.LTV_TASK;

-- Step 2: staging (full CTE chain + INSERT)
CREATE OR REPLACE TABLE PROD_DB.LTV_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    value                   FLOAT          NOT NULL,
    split                   VARCHAR(8)     NOT NULL
);

INSERT INTO PROD_DB.LTV_TASK.STAGING
WITH
-- Monthly cutoff timestamps spanning the study period
cutoffs AS (
    SELECT DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) AS cutoff_ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
-- Customers active in the 90-day lookback
active AS (
    SELECT c.cutoff_ts, o.customer_id
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o
      ON o.order_ts <= c.cutoff_ts
     AND o.order_ts >  DATEADD('day', -90, c.cutoff_ts)
    GROUP BY 1, 2
),
-- Revenue sum in the 90-day prediction window; 0 if no orders
labeled AS (
    SELECT
        a.cutoff_ts,
        a.customer_id,
        COALESCE(SUM(o.order_amount), 0.0)::FLOAT AS value
    FROM active a
    LEFT JOIN PROD_DB.SALES.orders o
      ON o.customer_id = a.customer_id
     AND o.order_ts >  a.cutoff_ts
     AND o.order_ts <= DATEADD('day', 90, a.cutoff_ts)
    GROUP BY 1, 2
),
-- Assign train / val / test split by cutoff date
split_assigned AS (
    SELECT
        customer_id,
        cutoff_ts,
        value,
        CASE
            WHEN cutoff_ts < '2023-07-01'::TIMESTAMP_NTZ THEN 'train'
            WHEN cutoff_ts < '2023-10-01'::TIMESTAMP_NTZ THEN 'val'
            ELSE 'test'
        END AS split
    FROM labeled
)
SELECT
    customer_id,
    cutoff_ts AS cutoff_orders_order_ts,
    cutoff_ts AS orders_order_ts,  -- equals the cutoff in this task
    value,
    split
FROM split_assigned;

-- Step 3: validate on STAGING
SELECT
    COUNT(*)                                                            AS total_rows,
    COUNT(*) - COUNT(value)                                             AS null_value,
    ROUND(AVG(value), 2)                                                AS mean_value,
    ROUND(MEDIAN(value), 2)                                             AS median_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value)                 AS p95_value,
    MAX(value)                                                          AS max_value,
    SUM(CASE WHEN value = 0 THEN 1 END)                                 AS zero_count,
    ROUND(SUM(CASE WHEN value = 0 THEN 1 END) / COUNT(*)::FLOAT, 4)     AS zero_rate,
    SUM(CASE WHEN split = 'train' THEN 1 ELSE 0 END)                    AS train_rows,
    SUM(CASE WHEN split = 'val'   THEN 1 ELSE 0 END)                    AS val_rows,
    SUM(CASE WHEN split = 'test'  THEN 1 ELSE 0 END)                    AS test_rows
FROM PROD_DB.LTV_TASK.STAGING;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.LTV_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.LTV_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.LTV_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.LTV_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.LTV_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.LTV_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- The `active` filter lookback must use `order_ts <= cutoff_ts`.
- The label window must be strictly `> cutoff_ts`.
- If joining to a price or product table for the amount, ensure you use the price **as of** the order date, not the current price (if prices are slowly changing).

## Target distribution guidance

Revenue and count targets are almost always right-skewed. Check the validation output:

- If `p95_value / median_value > 100`, consider log1p-transforming the target — ask the user whether the model should predict raw revenue or log-revenue.
- If `zero_rate > 0.8`, the task may be better framed as binary classification (will spend or not) followed by a conditional regression.
- Report both of these in chat before writing the final code; they are decisions for the user, not defaults.
