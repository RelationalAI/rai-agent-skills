# RelFM Tabular (Flat Mode)

`RelFMTabular` is the standalone, zero-shot tabular estimator in
`relationalai.semantics.reasoners.predictive.estimators.relfm_tabular`. It
predicts on a single flat table with no `Graph`, no shared `Relationship`
template, and no `fit()` step — it is pure in-context learning (ICL) over
whatever rows you hand it as `context`.

```python
from relationalai.semantics.reasoners.predictive import RelFMTabular
```

`RelFMTabular(...)` is a **factory function**, not a class — it dispatches on
`task_type` to one of two concrete estimators:

- `RelFMTabularPredictor` — `task_type` in `{"binary_classification",
  "multiclass_classification", "regression"}`
- `RelFMTabularForecaster` — `task_type="forecasting"`

Both live in `estimators/relfm_tabular/{predictor.py,forecaster.py}`, share a
common base in `base.py`, and the dispatch itself is in `factory.py`.

## When to use flat mode vs. relational RelFM vs. GNN

| | RelFM (flat/tabular) | RelFM (relational) | GNN |
|---|---|---|---|
| Input shape | one standalone table (context) | multiple tables joined via a `Graph`/FK structure | multiple tables joined via a `Graph` |
| Training step | none — zero-shot ICL | none — zero-shot ICL | `fit()` required |
| Feature source | the context table's own columns only | Deep Feature Synthesis (DFS) walks FK joins across related tables | message passing across graph edges |
| Task types | classification, regression, **forecasting** | classification, regression (no link prediction, no multilabel) | classification, regression, link prediction, multilabel |
| Identity requirement | one `identify_by` column (predictor) or `(item_id, time)` composite (forecaster) | one `identify_by` column on the source concept | any identity (hash-based) |

Use flat mode when the prediction problem is genuinely single-table (a churn
score off one customer table, a time-series forecast off one history table)
and you don't want to stand up a `Graph`/`PropertyTransformer` for it. Reach
for relational `RelFM` once the signal comes from *related* tables (e.g.
transactions joined to customers joined to articles) but you still want a
zero-training model. Reach for `GNN` when you need link prediction,
multilabel classification, or when the graph-structured signal benefits from
learned message passing rather than DFS-style feature engineering.

## Terminology

- **context** — the table of past rows (with the target column filled in) that the model learns from at prediction time. It is passed to the constructor as `context=`.
- **domain** — the table of rows you want output for. You pass it to `.predictions(domain=...)`, `.forecast(domain=...)` or `.score(domain=...)`. It is a separate `Concept` from `context`.
- **item** — one series in a forecast (e.g. one store, or one store-department pair). `item_id_column` names the column that identifies it.

## Required tables

Predictor mode (classification / regression):

| Concept (example name) | Contents | Used by |
|---|---|---|
| `Train` | rows with the label column | `context=` |
| `Validation` (optional) | same columns as `Train`, with labels | `validation=`, `.score()` |
| `Test` | same feature columns, **no** label column | `.predictions(domain=...)` |

Forecasting mode — all tables are keyed by `(item_id, time)`:

| Concept (example name) | Contents | Used by |
|---|---|---|
| `History` | past rows including the target column (sales, demand, temperature, ...) | `context=` |
| `FutureWindow` | `(item_id, time)` rows for the dates you want forecast; **no** target column | `.forecast(domain=...)` |
| `ValidationWindow` (optional) | the same `(item_id, time)` rows as `FutureWindow`, **with** real target values | `.score(domain=...)` |

Rows in `FutureWindow` should be dates *after* the last date in `History`. The tables can be Snowflake tables or local DataFrames.

## Snowflake requirements (check before running)

- Snowflake sources need **change tracking**; without it the job fails with `SnowflakeChangeTrackingNotEnabledException`.
  - Check that `data.ensure_change_tracking: true` is set in `raiconfig.yaml` (default is `false`). With it on, plain tables are handled for the user.
  - For any table or view you propose creating, include the tracking statement in the same proposal, because the setting may not cover it:
    ```sql
    ALTER TABLE DB.SCHEMA.MY_TABLE SET CHANGE_TRACKING = TRUE;
    ALTER VIEW  DB.SCHEMA.MY_VIEW  SET CHANGE_TRACKING = TRUE;
    ```
  - Prefer `CREATE TABLE` over `CREATE VIEW`. Views over views or `LATERAL FLATTEN` cannot be tracked.
- The RAI app also needs `SELECT` on the tables and `USAGE` on their database and schema.
- Propose SQL to the user and wait for approval; do not create objects in Snowflake without it.

## Tables with no unique column

Predictor mode needs the concept to be identified by exactly one column: `identify_by={"customerid": Integer}`. That column must be unique per row. If no column in the user's table is unique (a combination such as `Store, Dept, Date` is not accepted), add one in Snowflake. The original tables stay untouched:

```sql
CREATE OR REPLACE TABLE DB.SCHEMA.TRAIN_WITH_ID AS
SELECT ROW_NUMBER() OVER (ORDER BY 1) AS ROW_ID, t.* FROM DB.SCHEMA.TRAIN t;
ALTER TABLE DB.SCHEMA.TRAIN_WITH_ID SET CHANGE_TRACKING = TRUE;
```

Do the same for the validation and test tables (`ROW_ID` only needs to be unique within each table), then declare `identify_by={"ROW_ID": Integer}`.

## Configuration

### Common to predictor and forecaster

- `database`, `schema` — Snowflake location to write prediction output tables. Required for `.predictions()`/`.forecast()`.
- `context` — the flat `Concept` used directly as in-context examples (plays the role GNN's `train` plays, but there is no training loop).
- `label_column` — name of the target column on `context`.
- `task_type` — `"binary_classification"`, `"multiclass_classification"`, `"regression"`, or `"forecasting"`.
- `validation` — optional; used by `.score()` when no explicit `domain=` is passed.
- `eval_metric` — e.g. `"roc_auc"`, `"rmse"`, `"mae"`.
- `use_current_time` (default `True`) — time-window inclusivity for temporal tasks. `False` uses strict `<` (only data **before** the prediction date; no same-day leakage); `True` uses `<=` (includes the prediction date). Start with the default. Only set `False` if the user asks for strictly-before semantics, and if the job then fails, retry with the default and report the error. Full semantics: [hyperparameters.md](hyperparameters.md) § GNN constructor operational flags.
- `test_batch_size`, `stream_logs`, `dataset_alias`, `device` — job/runtime knobs, same conventions as GNN/relational RelFM.
- `n_estimators`, `random_state` — ICL ensemble knobs.
- `sample_size`, `sampling_strategy` — context subsampling for large tables.

### Predictor-only (classification/regression)

- `clamp_min`, `clamp_max`, `regression_output` — bound/shape regression outputs.
- `quantile_levels` — also valid for regression, producing `quantile_<N>` output columns.
- `norm_methods` — normalization applied to numeric columns.

### Forecaster-only

- `time_column` — the datetime column.
- `item_id_column` — the series identifier column (e.g. `storeid`).
- `max_context_length` — must be `>= 1`; how much history per series is used.
- `quantile_levels` — produces `quantile_<N>` properties alongside `predicted_value`.

Note: there is **no `prediction_length` parameter**. The forecast covers
exactly the `(item_id, time)` rows in the table you pass as `domain` to
`.forecast()`. To forecast the next 14 days, put 14 rows per item in that table.

## Identity requirements

- `RelFMTabularPredictor` requires `context`/`domain` to be identified by
  **one column** — `Concept(identify_by={"col": Type})` with exactly
  one entry. Two or more columns raise `ValueError` (see § Tables with no unique column).
- `RelFMTabularForecaster` requires a **composite `(item_id, time)`
  identity** instead — that's the whole point of forecasting mode.
- Unlike relational `RelFM`, flat mode does **not** require a shared entity
  concept across context/validation/domain splits — `TrainCustomer`,
  `ValidationCustomer`, and `TestCustomer` can be three entirely independent
  `Concept`s, each self-identified by `customerid`, as long as their column
  schemas match. This is because there's no `validate_task`/graph-based
  schema binding here — each split is its own standalone table.

## Output shape

`.predictions(domain)` / `.forecast(domain)` returns a relationship with a
`.prediction` field pointing at a `PredictionResult` concept. Inspect the
concrete properties on the live estimator instance:

```python
print(list(relfm_tabular.prediction_concept._relationships.keys()))
```

- Classification: `predicted_labels`, `probs`.
- Regression: `predicted_value`, plus `quantile_<N>` per configured
  `quantile_levels`.
- Forecasting: `predicted_value`, plus `quantile_<N>` per configured
  `quantile_levels` (e.g. `quantile_10`, `quantile_50`, `quantile_90` for
  `quantile_levels=[0.1, 0.5, 0.9]`).

## Minimal walkthrough — regression

Distilled from `example/predictive/flat/relfm_tabular_regression.ipynb`:

```python
from relationalai.semantics import Model, define, select, Integer
from relationalai.semantics.reasoners.predictive import RelFMTabular

model = Model("relfm_tabular_standalone")
# Table is model.Table (bound to this model) -- NOT importable from relationalai.semantics
Concept, Table = model.Concept, model.Table

TrainCustomer      = Concept("TrainCustomer",      identify_by={"customerid": Integer})
ValidationCustomer = Concept("ValidationCustomer", identify_by={"customerid": Integer})
TestCustomer       = Concept("TestCustomer",       identify_by={"customerid": Integer})

# Snowflake source (default): flat tables, one per split
define(TrainCustomer.new(Table("DB.SCHEMA.TRAIN").to_schema()))
define(ValidationCustomer.new(Table("DB.SCHEMA.VAL").to_schema()))
define(TestCustomer.new(Table("DB.SCHEMA.TEST").to_schema()))   # no label column

# Local alternative: pandas DataFrames (reset_index(drop=True) on sliced splits)
# define(TrainCustomer.new(model.data(train_df).to_schema()))
# define(ValidationCustomer.new(model.data(val_df).to_schema()))
# define(TestCustomer.new(model.data(test_df).to_schema()))

relfm_tabular = RelFMTabular(
    database="F1_PREDICTIVE", schema="EXPERIMENTS",
    context=TrainCustomer, validation=ValidationCustomer,
    label_column="lifetime_value",
    task_type="regression", eval_metric="rmse",
    device="cpu", n_estimators=8,
)

result = relfm_tabular.score()          # scores against `validation`

TestCustomer.predictions = relfm_tabular.predictions(domain=TestCustomer)

out_df = select(
    TestCustomer.customerid,
    TestCustomer.predictions.predicted_value,
).where(TestCustomer.predictions).to_df()
```

## Minimal walkthrough — forecasting

Distilled from `example/predictive/flat/relfm_tabular_forecast.ipynb`:

```python
from relationalai.semantics import Model, define, select, Integer, Date
from relationalai.semantics.reasoners.predictive import RelFMTabular

model = Model("relfm_tabular_forecast")
# Table is model.Table (bound to this model) -- NOT importable from relationalai.semantics
Concept, Table = model.Concept, model.Table

# Type identify_by from INFORMATION_SCHEMA. Any is for an unknown relationship slot, not a concept key.
History    = Concept("History",    identify_by={"storeid": Integer, "date": Date})
FutureWindow    = Concept("FutureWindow",    identify_by={"storeid": Integer, "date": Date})
ValidationWindow = Concept("ValidationWindow", identify_by={"storeid": Integer, "date": Date})

# Snowflake source (default)
define(History.new(Table("DB.SCHEMA.CONTEXT").to_schema()))
define(FutureWindow.new(Table("DB.SCHEMA.TEST").to_schema()))        # (storeid, date) skeleton, no target column
define(ValidationWindow.new(Table("DB.SCHEMA.VALIDATION").to_schema()))  # same window, real the target column

# Local alternative: define(History.new(model.data(history_df).to_schema())), etc.

relfm_forecast = RelFMTabular(
    database="F1_PREDICTIVE", schema="EXPERIMENTS",
    context=History, label_column="sales",
    task_type="forecasting", eval_metric="mae",
    time_column="date", item_id_column="storeid",
    max_context_length=60, quantile_levels=[0.1, 0.5, 0.9],
    device="cpu",
)

FutureWindow.forecast = relfm_forecast.forecast(domain=FutureWindow)

forecast_df = select(
    FutureWindow.storeid, FutureWindow.date,
    FutureWindow.forecast.predicted_value,
    FutureWindow.forecast.quantile_10,
    FutureWindow.forecast.quantile_50,
    FutureWindow.forecast.quantile_90,
).where(FutureWindow.forecast).to_df()

score_result = relfm_forecast.score(domain=ValidationWindow)  # needs LABELED domain, unlike forecast()
```

## Things to get right

- **Forecast length.** It equals the number of rows per item in the `domain` table (see Configuration).
- **Every item in `domain` must appear in `context`**, with **at least 2 rows of history** each. Items with 0 rows are rejected before the job starts; items with only 1 row make the job fail (`A forecast needs at least 2 historical observations per series`). Either add history or remove those items from both `context` and the test/validation table.
- **`(item_id, time)` pairs in `domain` must be unique.** Duplicates are rejected before the job starts.
- **Domain dates should be after the last date in `context`.** If a domain date falls inside the context's date range, you only get a warning in `get_status()["warnings"]`, not an error, meaning the model has already seen the true value for that date.
- **`score()` and `forecast()` take different domains.** `score()` needs the table that has real target values (`ValidationWindow`); `forecast()` needs the one without (`FutureWindow`).
- **Context and validation must have the same feature columns**, else `ValueError`.
- **Avoiding target leakage in the validation table.** For `score()`, the validation table has the label column, which is expected. For `predictions()`, the test table must **not** contain the label column. Also check that no other column is derived from the label (e.g. a `next_week_sales` column next to `weekly_sales`). Drop such columns by selecting only the needed columns when creating the table or view.
- **Quantile columns** are named after the levels: `quantile_levels=[0.1, 0.5, 0.9]` gives `quantile_10`, `quantile_50`, `quantile_90`.
- **Large context tables:** tune `max_context_length`, `sample_size` and `sampling_strategy`. Also size the predictive engine in `raiconfig.yaml`, and set `device="cuda"` only on a GPU-sized engine.
- **There is no `fit`, registry or `load` step.** Each call learns in-context from the `context` you passed to the constructor.
- **Bind prediction results once.** `Test.predictions = relfm.predictions(domain=Test)` can run only once per session for a given attribute name (a second run raises `[Duplicate relationship]`). To call it again, use a new attribute name (`Test.predictions_v2`) or assign to a plain variable (`preds = relfm.predictions(...)`). With a plain variable, do not select columns of `Test` next to `preds`, as that pairs every row with every prediction. Read the key through the result instead, e.g. `preds["source"].customerid`, or use the bound attribute.
- **Local data:** `model.data(df).to_schema()` can replace `Table("DB.SCHEMA.T").to_schema()`. If the DataFrame is a slice of a bigger one, call `df.reset_index(drop=True)` first.
- **Filename/location mismatch:**
  `example/predictive/relational/relfm_tabular_store_item_demand_forecast.py`
  lives under `relational/` but uses `RelFMTabular` (flat mode) with no `Graph`. Check the import, not the path.

## Data issues to flag

When you see problems such as dates stored as `VARCHAR`, report them and propose corrective SQL (a `CREATE TABLE ... AS SELECT` with `TO_DATE(...)`, followed by `ALTER TABLE ... SET CHANGE_TRACKING = TRUE`) for the user to approve.
