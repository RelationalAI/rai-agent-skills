# Link Prediction — Reference

## Schema contract

| Column | Type | Notes |
|---|---|---|
| `src_id` | matches source concept PK | e.g. `customer_id` |
| `dst_id` | `ARRAY` | list of positive destination entity PKs in the prediction window |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `<table>_<source_time_col>` _(optional, e.g. `orders_order_ts`)_ | same as `cutoff_<table>_<source_time_col>` — both come from the same source column | temporal tasks only (`has_time_column=True`) — the model's temporal anchor |

One row per `(src_id, cutoff_<table>_<source_time_col>)`. No duplicates.

Column names `src_id` and `dst_id` should be replaced with actual concept PK names (e.g., `customer_id`, `product_id`). The `dst_id` column holds an `ARRAY` of those PKs — not a scalar.

The task table contains **only ground-truth positive lists**. Negatives are sampled by the framework internally at training and evaluation time — do not add explicit negative rows.

## Downstream binding

```python
Train = Relationship(f"{Customer} has {Product}")
define(Train(Customer, Product)).where(
    Customer.customer_id == TrainTable.customer_id,
    Product.product_id   == TrainTable.product_id,
)

gnn = GNN(..., task_type="link_prediction", eval_metric="link_prediction_precision@10")
# prediction attributes: .rank, .scores, .predicted_product (for each customer)
# other eval_k options: @5, @20
# also consider: link_prediction_recall@K, link_prediction_map@K
```

## Label logic

A positive list for `src` at `cutoff_ts` contains every distinct `dst` entity that `src` interacted with in `(cutoff_ts, cutoff_ts + Δ]`.

The framework ranks the full candidate pool at evaluation time and scores Precision@K, Recall@K, and MAP@K against this list.

## Negatives — framework handles these

Do not sample or add negative rows to the task table. The framework samples negatives internally during training and ranks the full candidate pool during evaluation. Adding explicit negatives would double-count the negative signal and break the framework's internal sampling logic.

If you need to score specific `(src, dst)` pairs with a binary yes/no label and explicit negatives (AUC evaluation), use `TaskType.BINARY_CLASSIFICATION` on the source entity with the target encoded as a feature instead.

## Activity filter — explicit decision required

Confirm with the user whether the task table should be restricted to active source entities (those with at least one event in the Δ-day lookback window before `cutoff_ts`). This is not a silent default:

- **With activity filter**: model trains on recently-active entities only; more focused but excludes infrequent users.
- **Without activity filter**: includes all entities with any interaction in the prediction window; broader coverage, consistent with many reference implementations that omit this filter.

Default: **no activity filter** unless the user explicitly requests one.

## SQL template — list of purchased products per customer

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.PURCHASE_LINK_TASK;

-- Step 2: staging (full CTE chain + INSERT)
CREATE OR REPLACE TABLE PROD_DB.PURCHASE_LINK_TASK.STAGING (
    customer_id             NUMBER         NOT NULL,
    product_id              ARRAY          NOT NULL,  -- list of distinct purchased products
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    split                   VARCHAR(8)     NOT NULL
);

INSERT INTO PROD_DB.PURCHASE_LINK_TASK.STAGING
WITH
cutoffs AS (
    SELECT '2014-10-02'::TIMESTAMP_NTZ AS cutoff_ts, 'train' AS split
    UNION ALL
    SELECT '2015-01-01'::TIMESTAMP_NTZ, 'val'
    UNION ALL
    SELECT '2016-01-01'::TIMESTAMP_NTZ, 'test'
),
-- Positive lists: distinct products purchased by each customer in the prediction window
positives AS (
    SELECT
        c.cutoff_ts,
        c.split,
        o.customer_id,
        ARRAY_AGG(DISTINCT o.product_id) AS product_id
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o
      ON o.order_ts >  c.cutoff_ts
     AND o.order_ts <= DATEADD('day', 91, c.cutoff_ts)
    GROUP BY c.cutoff_ts, c.split, o.customer_id
)
SELECT
    customer_id,
    product_id,
    cutoff_ts AS cutoff_orders_order_ts,
    cutoff_ts AS orders_order_ts,  -- equals the cutoff in this task
    split
FROM positives;

-- Step 3: validate on STAGING
SELECT
    split,
    COUNT(*)                                                                                        AS total_rows,
    COUNT(*) - COUNT(customer_id)                                                                   AS null_src,
    COUNT(*) - COUNT(product_id)                                                                    AS null_dst_list,
    COUNT(*) - COUNT(cutoff_orders_order_ts)                                                        AS null_cutoff,
    MIN(ARRAY_SIZE(product_id))                                                                     AS min_list_length,
    MEDIAN(ARRAY_SIZE(product_id))                                                                  AS median_list_length,
    MAX(ARRAY_SIZE(product_id))                                                                     AS max_list_length,
    COUNT(*) - COUNT(DISTINCT customer_id::VARCHAR || '|' || cutoff_orders_order_ts::VARCHAR)        AS duplicates
FROM PROD_DB.PURCHASE_LINK_TASK.STAGING
GROUP BY split
ORDER BY split;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.PURCHASE_LINK_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.PURCHASE_LINK_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.PURCHASE_LINK_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.PURCHASE_LINK_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.PURCHASE_LINK_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.PURCHASE_LINK_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- Positive lists: the JOIN window must be strictly `> cutoff_ts` — events at or before the cutoff must not contribute to the list.
- Candidate pool used by the framework at eval time: the framework builds this from entities known as of `cutoff_ts`; no action required in the task table itself.
- If an activity filter is applied, its lookback predicate must use `<= cutoff_ts`.

## Validation extras for link prediction

Beyond the standard checks, report:
- `min/median/max_list_length` — very short median lists (< 2) suggest the window may be too short; very long lists suggest it may be too long.
- `duplicates` — any duplicate `(src_id, cutoff_ts)` pair is a schema violation.
- Spot-check that every `product_id` in the list has at least one review/event strictly after `cutoff_ts` — nothing from before the cutoff should appear as a label.
