# Binary Classification — Reference

## Schema contract

Four objects are always generated — a schema, a staging table, and three split tables.

**STAGING** (full dataset — validate here):

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | e.g. `customer_id` — exact same name as the source concept |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `label` | `SMALLINT` if derived from an event window; matches the source column's type as-is if the source already has a label column | 1 = positive event occurred in window, 0 = did not — for a derived label. If the source already carries the label (e.g. `status IN ('Yes','No')`), pass its raw value straight through instead |
| `split` | `VARCHAR(8)` | `'train'` / `'val'` / `'test'` — for partitioning only |
| `<table>_<source_time_col>` (e.g. `orders_order_ts`) | same as `cutoff_<table>_<source_time_col>` — both come from the same source column | temporal tasks only (`has_time_column=True`) — the model's temporal anchor |

**TRAIN / VAL / TEST** (downstream inputs — no `split` column, no `cutoff_<table>_<source_time_col>` column):

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | |
| `label` | same as STAGING | kept in TEST for post-hoc evaluation |
| `<table>_<source_time_col>` | matches source event-time column's type | |

One row per `entity_id` in TRAIN/VAL/TEST, and per `(entity_id, cutoff_<table>_<source_time_col>)` in STAGING. No duplicates.

## Downstream binding

```python
Train = Relationship(f"{Customer} has {Any:label}")
define(Train(Customer, TrainTable.label)).where(Customer.customer_id == TrainTable.customer_id)

gnn = GNN(..., task_type="binary_classification", eval_metric="roc_auc")
# prediction attributes: .probs, .predicted_labels
```

## Label logic

A binary label answers: **"Did event E happen in `(cutoff_ts, cutoff_ts + Δ]`?"**

Common patterns:

| Framing | Label = 1 when… |
|---|---|
| Churn | NO qualifying event in the prediction window |
| Conversion | At least one purchase / sign-up in the window |
| Default / risk | At least one adverse event (late payment, claim) in the window |
| Re-engagement | At least one session after a prior gap |

Use `MAX(CASE WHEN ... THEN 1 ELSE 0 END)` rather than `COUNT(*) > 0` — the former returns 0 cleanly for entities with no match after a LEFT JOIN.

**If the source data already has a label column** (e.g. a `status` or `flag` column with values like `'Yes'`/`'No'`, `'A'`/`'B'`, `'Churned'`/`'Active'`), do not remap or re-encode its values — alias the column directly as `label`, keeping its original type and values unchanged. Only use the derived `CASE WHEN` pattern above when there is no pre-existing label column and the label must be computed from an event condition.

## Activity filter (strongly recommended)

Only include entities that were active in a lookback window ending at `cutoff_ts`. This prevents the label distribution from being dominated by long-inactive entities that trivially score 0.

```sql
-- active_entities: at least one event in (cutoff_ts - lookback, cutoff_ts]
active_entities AS (
    SELECT c.cutoff_ts, o.customer_id
    FROM cutoffs c
    JOIN orders o
      ON o.order_ts <= c.cutoff_ts
     AND o.order_ts >  DATEADD('day', -90, c.cutoff_ts)
    GROUP BY 1, 2
)
```

## SQL template — churn prediction

```sql
-- ── Step 1: schema ───────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS DB.CHURN_TASK;

-- ── Step 2: staging ──────────────────────────────────────────
CREATE OR REPLACE TABLE DB.CHURN_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches ORDERS.order_ts's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    label                   SMALLINT       NOT NULL,   -- 1 = churned, 0 = retained
    split                   VARCHAR(8)     NOT NULL    -- 'train' | 'val' | 'test'
);

INSERT INTO DB.CHURN_TASK.STAGING
WITH
-- Weekly cutoff dates over the labellable range
cutoffs AS (
    SELECT cutoff_date
    FROM (
        SELECT DATEADD('week', seq4(), '2022-01-01'::DATE) AS cutoff_date
        FROM TABLE(GENERATOR(ROWCOUNT => 200))
    )
    WHERE cutoff_date <= '2023-09-30'::DATE  -- 90 days before last event date
),
-- Customers active in the 90-day lookback before each cutoff
active AS (
    SELECT c.cutoff_date, o.customer_id
    FROM cutoffs c
    JOIN DB.SOURCE.ORDERS o
      ON o.order_ts <= c.cutoff_date
     AND o.order_ts >  DATEADD('day', -90, c.cutoff_date)
    GROUP BY 1, 2
),
-- Label: 1 if no order in prediction window (churned), 0 if they returned
labeled AS (
    SELECT
        a.cutoff_date,
        a.customer_id,
        CASE
            WHEN MAX(CASE
                         WHEN o.order_ts >  a.cutoff_date
                          AND o.order_ts <= DATEADD('day', 90, a.cutoff_date)
                         THEN 1 ELSE 0
                     END) = 0 THEN 1
            ELSE 0
        END::SMALLINT AS label
    FROM active a
    LEFT JOIN DB.SOURCE.ORDERS o ON o.customer_id = a.customer_id
    GROUP BY 1, 2
),
-- Assign train / val / test by cutoff date
split_assigned AS (
    SELECT
        customer_id,
        cutoff_date,
        label,
        CASE
            WHEN cutoff_date <= '2022-12-31'::DATE THEN 'train'
            WHEN cutoff_date <= '2023-03-31'::DATE THEN 'val'
            ELSE                                        'test'
        END AS split
    FROM labeled
)
SELECT
    customer_id,
    cutoff_date AS cutoff_orders_order_ts,
    cutoff_date AS orders_order_ts,  -- equals the cutoff in this task
    label,
    split
FROM split_assigned;

-- ── Step 3: validate on STAGING ──────────────────────────────

-- 3a. Row count, nulls, duplicates
SELECT
    COUNT(*)                                                                                  AS total_rows,
    COUNT(*) - COUNT(customer_id)                                                             AS null_entity,
    COUNT(*) - COUNT(cutoff_orders_order_ts)                                                  AS null_cutoff,
    COUNT(*) - COUNT(label)                                                                   AS null_label,
    COUNT(*) - COUNT(DISTINCT customer_id || '|' || cutoff_orders_order_ts::VARCHAR)          AS duplicates
FROM DB.CHURN_TASK.STAGING;

-- 3b. Class balance and row counts per split
SELECT
    split,
    COUNT(*)                                         AS row_count,
    SUM(label)                                       AS positive_count,
    COUNT(*) - SUM(label)                            AS negative_count,
    ROUND(SUM(label) / COUNT(*) * 100, 2)            AS pct_positive,
    COUNT(DISTINCT customer_id)                      AS distinct_entities,
    COUNT(DISTINCT cutoff_orders_order_ts)           AS num_cutoffs,
    MIN(cutoff_orders_order_ts)                      AS first_cutoff,
    MAX(cutoff_orders_order_ts)                      AS last_cutoff
FROM DB.CHURN_TASK.STAGING
GROUP BY split
ORDER BY MIN(cutoff_orders_order_ts);

-- 3c. Temporal leakage: no entity should appear before their first event (expect 0)
SELECT COUNT(*) AS leakage_rows
FROM DB.CHURN_TASK.STAGING s
JOIN (
    SELECT customer_id, MIN(order_ts) AS first_event_ts
    FROM DB.SOURCE.ORDERS
    GROUP BY customer_id
) fe ON fe.customer_id = s.customer_id
WHERE s.cutoff_orders_order_ts < fe.first_event_ts;

-- ── Step 4: materialize split tables ─────────────────────────
-- Run only after all validation checks pass

CREATE OR REPLACE TABLE DB.CHURN_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM DB.CHURN_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE DB.CHURN_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM DB.CHURN_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE DB.CHURN_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM DB.CHURN_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- The `active_entities` filter must use `order_ts <= cutoff_ts` — not `<= cutoff_ts + window`.
- The label window predicate must be strictly `> cutoff_ts` (not `>=`).
- If customers is a slowly-changing dimension (e.g., has a `status` column), join on the version as of `cutoff_ts`, not the current version.
- Never use `LAST_VALUE` or `MAX(event_ts)` without a `WHERE event_ts <= cutoff_ts` guard.

## Cutoff strategies

| Strategy | When to use | How |
|---|---|---|
| Rolling monthly | General case | `DATEADD('month', seq, start)` via `GENERATOR` |
| Fixed single cutoff | Production scoring | Literal timestamp |
| Per-entity event-relative | "N days after first order" | Join to entity's first event, then offset |

## Class balance guidance

Section 3's validation query already reports the per-split positive rate — that's sufficient. Don't proactively confirm the label definition with the user based on where that rate lands: there's no universal target range for class balance, and a heavily imbalanced task (e.g. 1% positive) can carry strong signal and produce a good model just as well as a balanced one. If the user asks whether their rate looks reasonable, or wants to discuss adjusting the window or activity filter because of it, that's the moment to engage — not before.
