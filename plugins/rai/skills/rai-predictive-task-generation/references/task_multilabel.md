# Multilabel Classification — Reference

## Schema contract

Two valid forms. Prefer **long form** — it is the default expected by the downstream modeling step.

### Long form (preferred)

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | e.g. `customer_id` |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | the evaluation timestamp — used for split assignment and framework evaluation; not passed to the model directly |
| `label` | `VARCHAR` or `INTEGER` | one active label per row; multiple rows per `(entity_id, cutoff_<table>_<source_time_col>)` |

Multiple rows per `(entity_id, cutoff_<table>_<source_time_col>)` is correct — one row per active label.

### Array form (alternative)

| Column | Type | Notes |
|---|---|---|
| `entity_id` | matches source PK | |
| `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`) | matches source event-time column's type — never cast | |
| `labels` | `ARRAY` | array of active label IDs; one row per `(entity_id, cutoff_<table>_<source_time_col>)` |

Confirm which form the downstream step expects before generating — long form is the default. Whichever form is chosen, set `"label_form": "long"` or `"label_form": "array"` in `task_config.json` — `../scripts/validate_schema.py` requires it to know whether to expect a `label` or `labels` output column.

## Downstream binding

```python
Train = Relationship(f"{Customer} has {Any:label}")
define(Train(Customer, TrainTable.label)).where(Customer.customer_id == TrainTable.customer_id)

gnn = GNN(..., task_type="multilabel_classification", eval_metric="multilabel_auprc_macro")
# prediction attributes: .probs (shape [N, K]), .predicted_labels
```

## Label logic

A multilabel task answers: **"Which subset of K non-exclusive tags applies to entity X in `(cutoff_ts, cutoff_ts + Δ]`?"**

Unlike multiclass, an entity can have zero, one, or many active labels per cutoff. Entities with zero active labels are valid training examples (all-negative).

Common patterns:

| Framing | Label = |
|---|---|
| Product category propensity | Each distinct category purchased in the window |
| Topic tags | Each tag of articles read / posted in the window |
| Channel engagement | Each communication channel used in the window |

## SQL template — product category propensity (long form)

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.CATEGORY_PROPENSITY_TASK;

-- Step 2: staging (full dataset + split column)
CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    label                   VARCHAR        NOT NULL,   -- category name or category ID
    split                   VARCHAR(8)     NOT NULL
);

INSERT INTO PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING
WITH
-- Monthly cutoff timestamps spanning the study period
cutoffs AS (
    SELECT DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) AS cutoff_ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
-- Active customers: at least one order in the 90-day lookback before each cutoff
active AS (
    SELECT c.cutoff_ts, o.customer_id
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o
      ON o.order_ts <= c.cutoff_ts
     AND o.order_ts >  DATEADD('day', -90, c.cutoff_ts)
    GROUP BY 1, 2
),
-- One row per (customer, cutoff, category) for categories purchased in the forward window;
-- customers with zero purchases in the window get no row at all (long form has no way to
-- represent an all-negative entity — see Guidance below; use the array form if that matters)
labeled AS (
    SELECT DISTINCT
        a.cutoff_ts,
        a.customer_id,
        o.category AS label
    FROM active a
    JOIN PROD_DB.SALES.orders o
      ON o.customer_id = a.customer_id
     AND o.order_ts >  a.cutoff_ts
     AND o.order_ts <= DATEADD('day', 90, a.cutoff_ts)
),
-- Assign time-based splits: earliest cutoffs → train, middle → val, latest → test
split_assigned AS (
    SELECT
        customer_id,
        cutoff_ts,
        label,
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
    label,
    split
FROM split_assigned;

-- Step 3: validate on STAGING
SELECT
    COUNT(*)                                                                                    AS total_rows,
    COUNT(*) - COUNT(customer_id)                                                               AS null_customer,
    COUNT(*) - COUNT(cutoff_orders_order_ts)                                                    AS null_cutoff,
    COUNT(*) - COUNT(label)                                                                     AS null_label,
    COUNT(DISTINCT cutoff_orders_order_ts)                                                      AS cutoff_count,
    COUNT(DISTINCT label)                                                                       AS num_labels,
    ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT customer_id || '|' || cutoff_orders_order_ts::VARCHAR), 0), 2) AS avg_labels_per_entity,
    SUM(CASE WHEN split = 'train' THEN 1 ELSE 0 END)                                            AS train_rows,
    SUM(CASE WHEN split = 'val'   THEN 1 ELSE 0 END)                                            AS val_rows,
    SUM(CASE WHEN split = 'test'  THEN 1 ELSE 0 END)                                            AS test_rows
FROM PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_TASK.STAGING WHERE split = 'test';
```

## SQL template — array form

```sql
-- Step 1: schema
CREATE SCHEMA IF NOT EXISTS PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK;

-- Step 2: staging (full dataset + split column)
CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING (
    customer_id             VARCHAR        NOT NULL,
    cutoff_orders_order_ts  <source_type>  NOT NULL,   -- matches the source event-time column's actual type — do not cast
    orders_order_ts         <source_type>  NOT NULL,   -- temporal anchor (has_time_column=True); same type as above
    labels                  ARRAY          NOT NULL,
    split                   VARCHAR(8)     NOT NULL
);

-- (same CTEs as the long-form template above, except the final SELECT aggregates into an array)
INSERT INTO PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING
WITH
cutoffs AS (
    SELECT DATEADD('month', seq4(), '2022-01-01'::TIMESTAMP_NTZ) AS cutoff_ts
    FROM TABLE(GENERATOR(ROWCOUNT => 24))
),
active AS (
    SELECT c.cutoff_ts, o.customer_id
    FROM cutoffs c
    JOIN PROD_DB.SALES.orders o
      ON o.order_ts <= c.cutoff_ts
     AND o.order_ts >  DATEADD('day', -90, c.cutoff_ts)
    GROUP BY 1, 2
),
labeled AS (
    SELECT
        a.cutoff_ts,
        a.customer_id,
        ARRAY_AGG(DISTINCT o.category) AS labels
    FROM active a
    LEFT JOIN PROD_DB.SALES.orders o
      ON o.customer_id = a.customer_id
     AND o.order_ts >  a.cutoff_ts
     AND o.order_ts <= DATEADD('day', 90, a.cutoff_ts)
    GROUP BY 1, 2
),
split_assigned AS (
    SELECT
        customer_id,
        cutoff_ts,
        labels,
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
    labels,
    split
FROM split_assigned;

-- Step 3: validate on STAGING
SELECT
    COUNT(*)                                             AS total_rows,
    COUNT(DISTINCT cutoff_orders_order_ts)               AS cutoff_count,
    SUM(CASE WHEN split = 'train' THEN 1 ELSE 0 END)    AS train_rows,
    SUM(CASE WHEN split = 'val'   THEN 1 ELSE 0 END)    AS val_rows,
    SUM(CASE WHEN split = 'test'  THEN 1 ELSE 0 END)    AS test_rows
FROM PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING;

-- Step 4: materialize split tables
CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.TRAIN AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING WHERE split = 'train';

CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.VAL AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING WHERE split = 'val';

CREATE OR REPLACE TABLE PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.TEST AS
    SELECT * EXCLUDE (cutoff_orders_order_ts, split)
    FROM PROD_DB.CATEGORY_PROPENSITY_ARRAY_TASK.STAGING WHERE split = 'test';
```

## Leakage rules

- The activity filter lookback (`order_ts <= cutoff_ts`) must not use future data.
- The label window must be strictly `> cutoff_ts`.
- Label IDs / category names must come from a vocabulary built on training data only. New labels appearing in val/test are out-of-vocabulary.

## Guidance

- All-negative entities (active customers who bought nothing in the prediction window) are valid and important training examples. Do not drop them.
- **Long form cannot represent an all-negative entity as a row** — there is no zero-label sentinel row in long form, so such entities are simply absent from the table (the `JOIN` in the template above is a plain inner join for exactly this reason: an entity with zero matching labels contributes zero rows). If all-negative entities must appear as explicit training examples, use the **array form** instead — its `LEFT JOIN` naturally produces one row per entity with an empty `labels` array for entities with no purchases in the window, which is the only one of the two forms that can express "zero active labels" as a row at all.
- If the label set is very large (hundreds of categories), confirm with the user — the model's output space scales with K, and rare labels hurt training.
- The validation query should report `avg_labels_per_entity`. Typical healthy range: 1–5. Very high values suggest the window is too long or the label definition is too broad.
