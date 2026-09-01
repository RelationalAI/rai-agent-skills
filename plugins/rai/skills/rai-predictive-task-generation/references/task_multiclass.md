# Multiclass Classification — Reference

## Schema contract

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | e.g. `customer_id` |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `label` | matches the source category column's type (`VARCHAR` or `INTEGER`) | the raw class value itself — no re-encoding, no class dictionary |
| `<table>_<source_time_col>` _(optional, e.g. `orders_order_ts`)_ | same as `cutoff_<table>_<source_time_col>` — both come from the same source column | temporal tasks only (`has_time_column=True`) — the model's temporal anchor |

One row per `(entity_id, cutoff_<table>_<source_time_col>)`. Exactly one class per row — this is what distinguishes it from multilabel.

## Downstream binding

```python
Train = Relationship(f"{Customer} has {Any:label}")
define(Train(Customer, TrainTable.label)).where(Customer.customer_id == TrainTable.customer_id)

gnn = GNN(..., task_type="multiclass_classification", eval_metric="accuracy")
# prediction attributes: .probs (shape [N, K]), .predicted_labels
```

## Label logic

A multiclass label answers: **"Which one of K mutually exclusive classes does entity X fall into at cutoff T?"**

The label column takes the source category's raw value directly — never remapped or re-encoded. If the source stores categories as strings, `label` stays `VARCHAR`; if the source already stores them as integers, `label` stays `INTEGER` as-is.

Common patterns:

| Framing | Label = |
|---|---|
| Next product category | The category value itself of the first purchase after cutoff |
| Customer segment | The segment value itself with the most spend in the window |
| Primary topic | The tag value itself with the highest frequency in the window |

When multiple events occur in the window, choose one:
- **Most frequent class**: `ROW_NUMBER() OVER (PARTITION BY entity_id, cutoff_ts ORDER BY cnt DESC) = 1`
- **First class**: `ROW_NUMBER() OVER (PARTITION BY entity_id, cutoff_ts ORDER BY event_ts ASC) = 1`

Document the tiebreaker in the task spec — it affects what the model is learning.

Only include entities where at least one event occurred in the prediction window (entities with no events have no ground-truth class).

## SQL template — next product category

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.NEXT_CATEGORY_TASK;

-- Step 2: staging (full CTE chain + INSERT)
CREATE OR REPLACE TABLE PROD_DB.NEXT_CATEGORY_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    label                   VARCHAR        NOT NULL,   -- matches source category type — raw value, not re-encoded
    split                   VARCHAR(8)     NOT NULL
);

INSERT INTO PROD_DB.NEXT_CATEGORY_TASK.STAGING
WITH
-- All cutoff timestamps: one per month for 24 months
cutoffs AS (
    SELECT DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) AS cutoff_ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
-- First order in the prediction window per customer per cutoff
first_order AS (
    SELECT
        c.cutoff_ts,
        o.customer_id,
        o.category,
        ROW_NUMBER() OVER (
            PARTITION BY c.cutoff_ts, o.customer_id
            ORDER BY o.order_ts ASC
        ) AS rn
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o
      ON o.order_ts >  c.cutoff_ts
     AND o.order_ts <= DATEADD('day', 90, c.cutoff_ts)
),
-- Label: the raw category value itself, no re-encoding into an integer class ID
labeled AS (
    SELECT cutoff_ts, customer_id, category AS label
    FROM first_order
    WHERE rn = 1
),
-- Assign train/val/test split by time boundary
split_assigned AS (
    SELECT
        customer_id,
        cutoff_ts,
        label,
        CASE
            WHEN cutoff_ts <  '2023-07-01'::TIMESTAMP_NTZ THEN 'train'
            WHEN cutoff_ts <  '2023-10-01'::TIMESTAMP_NTZ THEN 'val'
            ELSE 'test'
        END AS split
    FROM labeled
)
SELECT
    customer_id,
    cutoff_ts AS cutoff_orders_order_ts,
    cutoff_ts AS orders_order_ts,  -- equals the cutoff in this task
    label,
    split
FROM split_assigned;

-- Step 3: validate on STAGING
SELECT
    COUNT(*)                                                                            AS total_rows,
    COUNT(*) - COUNT(customer_id)                                                       AS null_entity,
    COUNT(*) - COUNT(cutoff_orders_order_ts)                                            AS null_cutoff,
    COUNT(*) - COUNT(label)                                                             AS null_label,
    COUNT(DISTINCT label)                                                               AS num_classes,
    COUNT(DISTINCT customer_id)                                                         AS unique_customers,
    COUNT(*) - COUNT(DISTINCT customer_id || '|' || cutoff_orders_order_ts::VARCHAR)    AS duplicates,
    COUNT(CASE WHEN split = 'train' THEN 1 END)                                         AS train_rows,
    COUNT(CASE WHEN split = 'val'   THEN 1 END)                                         AS val_rows,
    COUNT(CASE WHEN split = 'test'  THEN 1 END)                                         AS test_rows
FROM PROD_DB.NEXT_CATEGORY_TASK.STAGING;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.NEXT_CATEGORY_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.NEXT_CATEGORY_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.NEXT_CATEGORY_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.NEXT_CATEGORY_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.NEXT_CATEGORY_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.NEXT_CATEGORY_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- The `first_order` filter must use strictly `> cutoff_ts`.
- `ROW_NUMBER()` tiebreaking must use only data within the prediction window.
- Since labels are passed through as their raw source values, there is no class-dictionary alignment to keep leakage-safe across splits. Categories that appear only in val/test (never in train) are a modeling-time concern for the downstream training step, not something the task table needs to handle.

## Guidance

- Confirm the number of classes (K) with the user before generating code — run `SELECT COUNT(DISTINCT category) FROM ...` to get it directly, since there's no dictionary table to read it from. K drives the model's output dimension.
- If K is large (> 100), discuss whether multiclass is appropriate — link prediction may be a better fit.
- Classes with very few examples (< ~30 training instances) degrade model quality; consider merging rare classes into an "other" bin.
