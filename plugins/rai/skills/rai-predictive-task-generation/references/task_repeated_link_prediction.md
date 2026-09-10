# Repeated Link Prediction — Reference

## Schema contract

| Column | Type | Notes |
|---|---|---|
| `src_id` | matches source concept PK | e.g. `customer_id` |
| `dst_id` | `ARRAY` | list of dst entity PKs from prior-history pairs that were interacted with again in the window |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `<table>_<source_time_col>` _(optional, e.g. `orders_order_ts`)_ | same as `cutoff_<table>_<source_time_col>` — both come from the same source column | temporal tasks only (`has_time_column=True`) — the model's temporal anchor; named by prepending the source table name to the source event time column |

One row per `(src_id, cutoff_<table>_<source_time_col>)`. No duplicates.

Targets are formatted as a list of destination entity PKs — matching the framework's list convention for link tasks. The distinction from `LINK_PREDICTION` is that the candidate pool is restricted to `(src, dst)` pairs with **prior history** as of `cutoff_ts` — the model predicts re-interaction, not discovery.

Column names (`src_id`, `dst_id`) should be replaced with actual concept PK names. The framework samples negatives (prior-history pairs not re-interacted with) internally.

**Semantic variants** (for reference — both use the list format above):
- *Will they interact again?* — list contains dst entities with ≥1 re-interaction in the window
- *How many times?* — the framework infers frequency from the list length or a separate count column if the task requires it; confirm with user

## Downstream binding

```python
# Count variant
Train = Relationship(f"{Customer} has {Product}")
define(Train(Customer, Product)).where(
    Customer.customer_id == TrainTable.customer_id,
    Product.product_id   == TrainTable.product_id,
)

gnn = GNN(..., task_type="repeated_link_prediction", eval_metric="link_prediction_precision@5")
# prediction attributes: .rank, .scores, .predicted_product
```

## Difference from link prediction

| | Link prediction | Repeated link prediction |
|---|---|---|
| Target | List of positive dst PKs in `(T, T+Δ]` — any interaction, including first-time | List of positive dst PKs in `(T, T+Δ]` — restricted to prior-history pairs only |
| Candidate pool | All dst entities known as of `cutoff_ts` | Only `(src, dst)` pairs with prior history as of `cutoff_ts` |
| Use case | Recommendation / discovery | Reorder / retention / reengagement |

Entities with no positives in the window are excluded — no list means no row — the same as `LINK_PREDICTION`. The framework does not read empty rows from the task table as a negative signal; negatives are sampled internally at training and evaluation time (from prior-history pairs not re-interacted with), never from the task table itself.

## Prerequisite check

Before generating code, verify the source table supports this task:
- The event table must record **each interaction as a separate row** (not the most-recent-only).
- If the table only stores the latest interaction or a running count, flag this to the user — the data does not support a repeated link prediction task.

## Pair selection strategies

Unlike link prediction, you typically restrict to pairs that have **prior history** as of `cutoff_ts`. Including all-new pairs makes the zero counts dominate and dilutes signal.

| Strategy | Pairs included |
|---|---|
| Prior-interaction pairs only (default) | `(src, dst)` pairs with at least one interaction before `cutoff_ts` |
| Recent-interaction pairs | `(src, dst)` pairs with at least one interaction in the lookback window |
| All pairs (use with caution) | All `(src, dst)` combinations that existed as of `cutoff_ts`; needs large negative sampling budget |

## SQL template — customer reorder list (list variant)

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.REORDER_TASK;

-- Step 2: staging — one row per (customer_id, cutoff_ts); product_id is ARRAY of re-ordered product PKs
-- (column names here are already replaced with the actual concept PK names, per the
-- schema contract above — src_id -> customer_id, dst_id -> product_id)
CREATE OR REPLACE TABLE PROD_DB.REORDER_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    product_id              ARRAY          NOT NULL,  -- ARRAY_AGG of product_ids re-ordered in the window
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    split                   VARCHAR(8)     NOT NULL
);

INSERT INTO PROD_DB.REORDER_TASK.STAGING
WITH
-- Monthly evaluation cutoffs
cutoffs AS (
    SELECT DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) AS cutoff_ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
    WHERE DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) <= '2023-12-01'::TIMESTAMP_NTZ
),
-- Prior-history pairs: (customer, product) with at least one order before cutoff
prior_pairs AS (
    SELECT DISTINCT c.cutoff_ts, o.customer_id, o.product_id
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o ON o.order_ts <= c.cutoff_ts
),
-- Products re-ordered in the 90-day prediction window, restricted to prior-history pairs
reordered AS (
    SELECT
        p.cutoff_ts,
        p.customer_id,
        p.product_id
    FROM prior_pairs p
    JOIN PROD_DB.SALES.orders o
      ON o.customer_id = p.customer_id
     AND o.product_id  = p.product_id
     AND o.order_ts >   p.cutoff_ts
     AND o.order_ts <=  DATEADD('day', 90, p.cutoff_ts)
),
-- Aggregate re-ordered products into an ARRAY per (customer_id, cutoff_ts); customers with
-- zero re-orders in the window produce no row here, same convention as LINK_PREDICTION
labeled AS (
    SELECT
        customer_id,
        cutoff_ts,
        ARRAY_AGG(DISTINCT product_id) WITHIN GROUP (ORDER BY product_id) AS product_id
    FROM reordered
    GROUP BY customer_id, cutoff_ts
),
-- Assign time-based splits
split_assigned AS (
    SELECT
        customer_id,
        product_id,
        cutoff_ts,
        CASE
            WHEN cutoff_ts < '2023-01-01'::TIMESTAMP_NTZ THEN 'train'
            WHEN cutoff_ts < '2023-07-01'::TIMESTAMP_NTZ THEN 'val'
            ELSE 'test'
        END AS split
    FROM labeled
)
SELECT
    customer_id,
    product_id,
    cutoff_ts AS cutoff_orders_order_ts,
    cutoff_ts AS orders_order_ts,  -- equals the cutoff in this task
    split
FROM split_assigned;

-- Step 3: validation on STAGING
SELECT
    COUNT(*)                                                                            AS total_rows,
    COUNT(*) - COUNT(customer_id)                                                       AS null_customer,
    COUNT(*) - COUNT(cutoff_orders_order_ts)                                            AS null_cutoff,
    COUNT(*) - COUNT(product_id)                                                        AS null_product_id,
    MIN(ARRAY_SIZE(product_id))                                                         AS min_list_length,
    MEDIAN(ARRAY_SIZE(product_id))                                                      AS median_list_length,
    MAX(ARRAY_SIZE(product_id))                                                         AS max_list_length,
    COUNT(*) - COUNT(DISTINCT customer_id || '|' || cutoff_orders_order_ts::VARCHAR)    AS duplicates
FROM PROD_DB.REORDER_TASK.STAGING;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.REORDER_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.REORDER_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.REORDER_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.REORDER_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.REORDER_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.REORDER_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- `prior_pairs` must use `order_ts <= cutoff_ts` — no pairs that only appear after the cutoff.
- The reorder join window must be strictly `> cutoff_ts`.
- `dst_id` must contain only products from prior-history pairs; products with no prior history must not appear in the array.
- If the source table has been truncated or overwritten (not append-only), prior pair detection may not be reliable — flag this.

## Validation extras

- `min/median/max_list_length` — very short median lists (< 2) suggest the window may be too short, or the prior-history restriction too narrow; very long lists suggest it may be too long.
- `duplicates` — any duplicate `(customer_id, cutoff_ts)` pair is a schema violation.
- Spot-check that every `product_id` in the list is (a) a prior-history pair as of `cutoff_ts` and (b) has a qualifying re-interaction strictly after `cutoff_ts`.
