---
name: rai-predictive-training
description: Configure and train GNN models, generate predictions, evaluate results, and manage trained models. Use after building the data model with rai-predictive-modeling, when ready to run training, evaluate, or manage GNN models.
---

# Predictive Training
<!-- v1-SENSITIVE -->

> **Early access.** The RAI predictive reasoner (GNN) is in early access — APIs, engine requirements, and behavior may change. Confirm the latest surface with the RelationalAI team before production use.

## Summary

**What:** Training, evaluation, and model management workflow for GNN pipelines.

**When to use:**
- Configuring the GNN estimator and hyperparameters
- Training models with `fit()`
- Generating predictions on test data
- Evaluating and debugging results
- Registering or loading saved models

**When NOT to use:**
- Defining concepts, loading data, building graphs -- see `rai-predictive-modeling`

**Overview:** 4 steps: configure GNN -> train -> predict/evaluate -> optional: register/load.

**By user intent — sections to focus on:**
- Train + read validation metric → Quick Reference + GNN Constructor + `gnn.fit()`
- + predict + downstream rule / optimization → also Predictions + Using Predictions Downstream
- + register + reload across sessions → also Model Management

## Quick Reference

### Node Classification (minimal)

```python
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, device="cuda", n_epochs=5,
)
gnn.fit()
User.predictions = gnn.predictions(domain=Test)
```

### Default Metrics

| Task Type | Suggested Metric |
|-----------|-----------------|
| binary_classification | `roc_auc` |
| multiclass_classification | `accuracy` |
| multilabel_classification | `multilabel_auprc_macro` |
| regression | `rmse` |
| link_prediction | `link_prediction_precision@5` |
| repeated_link_prediction | `link_prediction_precision@5` |

### Prediction Attributes

| Task Type | Attributes |
|-----------|-----------|
| classification | `.probs`, `.predicted_labels` |
| regression | `.predicted_value` |
| link prediction | `.rank`, `.scores`, `.predicted_<target>` |

---

## GNN Constructor

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `exp_database`, `exp_schema` | Snowflake location for experiment artifacts |
| `graph` | Graph object with edges defined |
| `train`, `validation` | Relationship objects |
| `task_type` | Task type string |
| `eval_metric` | Evaluation metric string |

### Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `property_transformer` | None | PropertyTransformer instance (omit for auto-inference) |
| `has_time_column` | False | Set `True` when Relationships use the "at" keyword |
| `dataset_alias` | None | Custom alias for the dataset |
| `stream_logs` | True | Stream training logs to console. Set `False` if log streaming is slow or unreliable — training continues server-side regardless |
| `parallel_reasoners_init` | True | Initialize reasoners in parallel at construction time |

### Node Classification Example

```python
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    device="cuda", n_epochs=5, lr=0.005,
)
gnn.fit()
```

### Link Prediction Example (temporal)

```python
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="repeated_link_prediction",
    eval_metric="link_prediction_precision@5",
    has_time_column=True,
    device="cuda", n_epochs=5, lr=0.005,
    head_layers=2, num_negative=20, label_smoothing=True,
)
gnn.fit()
```

**Note:** `gnn.fit()` trains at most once per GNN instance. If training has already completed (or is in progress), subsequent calls to `fit()` are silent no-ops. To retrain -- e.g. with different hyperparameters -- construct a new `GNN` instance.

**Multi-GNN pipelines on the same model.** Train multiple GNNs over the same entity set (e.g. regression + classification + link-prediction on the same graph) by reusing one `Graph` and one `PropertyTransformer` across all `GNN` instances; vary `task_type`, `eval_metric`, `train`/`validation`, and the source/target concepts. Bind each task's predictions to a **distinct attribute name** -- the convention `Source.predictions` collides if one source concept hosts more than one task.

```python
shared = dict(graph=gnn_graph, property_transformer=pt)
gnn_a  = GNN(**shared, train=TrainA, validation=ValA, task_type="regression", eval_metric="rmse", ...)
gnn_b  = GNN(**shared, train=TrainB, validation=ValB, task_type="binary_classification", eval_metric="roc_auc", ...)
gnn_c  = GNN(**shared, train=TrainC, validation=ValC, task_type="repeated_link_prediction", eval_metric="link_prediction_precision@5", ...)
for g in (gnn_a, gnn_b, gnn_c): g.fit()

# Distinct attributes when a source concept hosts multiple predictions:
Item.value_predictions = gnn_a.predictions(domain=TestA)
User.label_predictions = gnn_b.predictions(domain=TestB)
User.link_predictions  = gnn_c.predictions(domain=TestC)
```

Hyperparameters can also be passed as a dictionary:

```python
train_config = {"device": "cuda", "n_epochs": 10, "lr": 0.001, "train_batch_size": 512}
gnn = GNN(exp_database="DB", exp_schema="EXPERIMENTS", ..., **train_config)
gnn.fit()
```

**Unknown keys raise actionable errors.** `validate_train_params` (`relationalai.semantics.reasoners.predictive.preparation`) rejects unknown `**train_params` keys with a `ValueError` and uses `difflib` to suggest near-matches; if you accidentally pass a `GNN(...)` constructor parameter (e.g. `task_type=`) inside `train_params`, the message tells you it belongs on the constructor. Read the suggestion before second-guessing the typo.

---

## Common Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `device` | `"cuda"` | `"cuda"` (GPU) or `"cpu"` |
| `n_epochs` | 5 | Number of training epochs |
| `lr` | 0.005 | Learning rate |
| `train_batch_size` | 256 | Training batch size |

For link prediction, also consider: `head_layers=2`, `num_negative=20`, `label_smoothing=True`.

**`device="cuda"` is a paired requirement.** The client-side flag alone is not enough — the predictive reasoner engine must also be GPU-sized in `raiconfig.yaml`. Configure both or neither; mismatched settings silently fall back or fail. Heuristic: CPU HIGHMEM tiers trade training speed for more RAM; GPU is faster per epoch when the dataset fits in the GPU VM's CPU memory, HIGHMEM otherwise.

**A GNN workflow touches multiple reasoner engines — size each per its role.** At minimum, the **predictive** engine runs `fit()` and prediction jobs, and the **logic** engine runs model definitions, queries, and downstream rule evaluation; predict-then-optimize pipelines also need the **prescriptive** engine. Each is configured independently in `raiconfig.yaml` under `reasoners:` with its own `name` and `size` — appropriate sizing differs per role (GPU for predictive training, HIGHMEM CPU for logic query and rule workloads, and per-problem sizing for prescriptive). Mis-sizing one engine doesn't error loudly; the workflow still runs and silently under-performs or hits memory limits on that engine's step.

**Auto-suspend during iteration.** Set a low `auto_suspend_mins` on every engine you're using — idle pool cost can dominate total spend on small workloads. Warm pools make sense only for scheduled/production cadence. Specific tier names and per-cloud memory-vs-compute tradeoffs change over time — ask the RelationalAI team for current sizing. Full `raiconfig.yaml` structure (including the `reasoners:` block for all engine types) lives in the RAI configuration/setup skill.

**Pre-flight check the GPU compute pool before long `fit()` runs.** The predictive reasoner provisions onto a Snowpark Container Services GPU compute pool. Confirming the pool is active up front is cheap hygiene; if it's auto-suspended, jobs may queue without surfacing a clear progress signal. Substitute the pool name your account uses — `SYSTEM_COMPUTE_POOL_GPU` is the Snowflake-provided default; some accounts have a custom pool referenced from `raiconfig.yaml`:

```sql
SHOW COMPUTE POOLS;                                    -- list all + check state
ALTER COMPUTE POOL <your_gpu_pool> RESUME;             -- if state=SUSPENDED
```

For all hyperparameters and tuning guidance, see [references/hyperparameters.md](references/hyperparameters.md).

---

## Training

### fit() Stages

`gnn.fit()` runs three stages internally:
1. Data preparation and feature extraction
2. Model training over `n_epochs`
3. Evaluation on the validation set

### Known Limitations

`has_time_column=True` has two known failure modes; both share the same workaround (turn temporal off — switch to non-temporal Relationships and `has_time_column=False`):

1. **Edge-intermediary `time_col`.** When the concept carrying `time_col` is used only as an edge intermediary (no `identify_by`), validation fails with "no time column defined in data tables". `time_col` only propagates for node concepts.
2. **Datetime column processing at scale.** On larger Snowflake-loaded datasets the trainer can fail server-side with `ValidationError: Error processing datetime column '<name>'` even with the time-bearing concept as a node, clean data, and the column properly listed in both `datetime=[...]` and `time_col=[...]`. The failure is loud at submit time, not silent. Reproduced on a daily date column at ~27K-row scale, so the threshold for "scale" is low. Confirm the timestamp column type matches what the GNN datetime pipeline accepts (see `rai-predictive-modeling` § Define and Populate Concepts) and fall back to non-temporal Relationships if the issue persists. The full fallback is to make four coordinated changes: drop `time_col=` from `PropertyTransformer`, set `has_time_column=False`, drop `temporal_strategy=`, and rewrite the `Train`/`Val`/`Test` `Relationship`s to drop the date argument. Then preserve the temporal split in pandas before building the task tables:

   ```python
   # Before (fails at scale)
   pt = PropertyTransformer(
       datetime=[Sale.date],
       time_col=[Sale.date],   # <-- remove
       ...
   )
   gnn = GNN(has_time_column=True, ..., temporal_strategy="last")  # <-- both go
   Train = Relationship(f"{Sale} at {Any:date} has {Any:value}")    # <-- drop date arg

   # After (works) — keep date as a plain datetime feature; the
   # temporal split lives in pandas (train_mask/val_mask/test_mask).
   pt = PropertyTransformer(
       datetime=[Sale.date],   # convention: don't pass time_col= when has_time_column=False
       ...
   )
   gnn = GNN(has_time_column=False, ...)
   Train = Relationship(f"{Sale} has {Any:value}")
   model.define(Train(Sale, TrainTable.unit_sales)).where(...)
   ```

   The `PropertyTransformer` API itself accepts `time_col=` independent of `GNN(has_time_column=...)`; the rule "don't pass `time_col=` when `has_time_column=False`" is a convention to avoid dead annotations, not a code-enforced check.

**Engine-side compiled-relation cache footgun (not datetime-specific — surfaces after any column-type change on a bound table):** the engine caches the compiled relation type per RAI relation name and doesn't invalidate it on `ALTER TABLE`, even after stream delete + recreate. Symptom: `Encountered reference to a base relation with a mismatched signature` — but the client only shows the opaque `Failed to pull data into index: transaction was aborted (runtime error)` wrapper. Pull the real error via `RELATIONALAI.API.GET_TRANSACTION_ARTIFACTS('<txn_id>')` -> `problems.json` (presigned URL) and look at the `report` field. Workaround: rename `Model(...)` to force a fresh RAI relation namespace (downstream queries that depend on the old name need updating). Better: do schema changes before the first bind — see `rai-predictive-modeling` § Populate from Snowflake.

### Worker not ready to accept jobs

`gnn.fit()` submits successfully (Step 3/3 logs `Training job submitted`) but the train job sits in `STATE='QUEUED'` in `RELATIONALAI.API.JOBS` indefinitely, even though `GET_REASONER` returns `STATUS='READY'`. The SDK only checks reasoner-pod readiness via `api.get_reasoner` before submitting (`relationalai_gnns/core/connector.py::_check_engine_availability`); it has no notion of an in-pod worker queue, so a desynced worker on a READY pod is invisible to the client. The server-side error surfaces only when the SDK polls and the `CREATE_JOB` external function reports back:

> Request failed for external function CREATE_JOB with remote service error: 400 `{"status":"Not Found","message":"worker is not ready to accept jobs - please retry the job later"}`

For the SQL recovery runbook (suspend + resume + re-check), see `rai-health` § Predictive train jobs stuck QUEUED. After recovery, resubmit by re-instantiating `GNN(...)` — see § `gnn.fit()` is idempotent below for why bumping `Model("...")` name alone is not enough.

### `gnn.fit()` is idempotent — re-instantiate `GNN(...)` on retry

`gnn.fit()` is a silent no-op if `self.train_job` already exists and isn't `FAILED` (`relationalai/semantics/reasoners/predictive/estimator.py:483-490`). Calling `gnn.fit()` a second time on the same `GNN` Python object will **not** submit a new training job — it just logs `Training job already running/completed` and returns. The next `gnn.predictions(...)` call then resolves the *previous* `train_job.model_run_id` (which is the previous job's `job_id` per `relationalai_gnns/core/job_manager.py:132-146`).

**Symptom this explains**: a re-run of a notebook cell or a retry after a killed mid-flight run reports `model_run_id` from a much-earlier job, not the freshly-submitted one. Subsequent prediction calls operate on stale model artifacts and can hang at "Step 2/4: Preparing model for prediction".

**Workaround:** re-instantiate `GNN(...)` on every retry. Bumping `Model("...")` name is **not** the right fix for this specific bug (the SDK has no name-based experiment matching at the `_wait_obtain_model_run_id` layer) — that bump is the workaround for the engine-side compiled-relation cache footgun above, a separate issue. To force a fresh training run after a partial failure:

```python
gnn = GNN(...)   # build a new instance — required
gnn.fit()        # submits a fresh job
```

---

## Troubleshooting

### Stalled train job: SDK polls without a timeout

`relationalai_gnns/core/job_manager.py::JobMonitor._wait_for_completion` (line 332-340) polls `get_status()` every 5 seconds with no timeout, no retry cap, and no max-poll-count. While the underlying job stays in `QUEUED` or `RUNNING`, the loop is unbounded. If the row is removed from `RELATIONALAI.API.JOBS` (history retention varies by Snowflake/native-app version), `get_status()` raises rather than self-terminating cleanly — but a row that *stays* QUEUED indefinitely will never trigger that exit path.

If a `gnn.fit()` client has been polling for an unreasonable amount of time and `SELECT * FROM RELATIONALAI.API.JOBS WHERE ID = '<id>'` shows the row is still QUEUED (or returns no row), kill the client manually. Use the SUSPEND/RESUME runbook in § Worker not ready to accept jobs to recover, then re-instantiate `GNN(...)` and resubmit. Do **not** rely on `RELATIONALAI.API.JOBS` for forensics on long-stalled jobs; capture state earlier with `GET_TRANSACTION_ARTIFACTS` or engine logs when investigating.

---

## Predictions

After training, generate predictions on the test set. Two valid binding patterns:

```python
# Pattern 1 — bind to a concept attribute (queryable via select()):
Source.predictions = gnn.predictions(domain=Test)

# Pattern 2 — assign to a plain Python variable (re-callable):
predictions = gnn.predictions(domain=Test)
```

Each concept-attribute name can be assigned **once per session** — re-binding `Source.predictions` raises `[Duplicate relationship]`. To call `predictions()` multiple times in one session, use Pattern 2 or a fresh attribute name (e.g. `Source.predictions_v2`).

### Classification (binary, multiclass, multilabel)

```python
User.predictions = gnn.predictions(domain=Test)

select(
    User.user_id,
    User.predictions.probs,
    User.predictions.predicted_labels,
).where(User.predictions).inspect()
```

### Regression

```python
Unit.predictions = gnn.predictions(domain=Test)

select(
    Unit.unit_id,
    Unit.predictions.predicted_value,
).where(Unit.predictions).inspect()
```

### Link Prediction

```python
User.predictions = gnn.predictions(domain=Test)

select(
    User.user_id,
    Item.item_id,
    User.predictions.rank,
    User.predictions.scores,
).where(
    User.predictions.predicted_item == Item,
).inspect()
```

The `predicted_<target>` attribute name is always lowercase: Target `Item` -> `.predicted_item`.

### As DataFrame

Replace `.inspect()` with `.to_df()` to get a pandas DataFrame:

```python
df = select(
    User.user_id,
    User.predictions.probs,
    User.predictions.predicted_labels,
).where(User.predictions).to_df()
```

### Dictionary-Style Field Indexing

The prediction relation also supports dictionary-style field indexing, useful when the source concept name conflicts with an existing attribute:

```python
PredRelation = gnn.predictions(domain=Test)
select(
    PredRelation["beer"].name,
    PredRelation["timestamp"],
    PredRelation["prediction"].predicted_labels,
    PredRelation["prediction"].probs,
).inspect()
```

**Direct access via `gnn.prediction_concept`.** Exposes the underlying prediction concept without binding to a source attribute — useful when the source concept name conflicts with an existing attribute. Use it as the head in `select(...)`: `select(Source.source_id, gnn.prediction_concept.predicted_labels).where(Source.predictions(DateTime, gnn.prediction_concept)).inspect()`.

For the full prediction attributes reference (per-task attribute types, code shapes), see [references/prediction-attributes.md](references/prediction-attributes.md). The summary table is in Quick Reference above.

---

## Using Predictions Downstream

Once `Source.predictions = gnn.predictions(...)` runs, predictions are bound to the source concept and accessible via `Source.predictions.<attribute>` throughout the **same `Model`**. Other reasoners (rules, prescriptive, graph) consume them by deriving new properties from those attributes.

### Same-model pattern (default)

Keep training, prediction, and downstream reasoning in one `Model`. This is the idiomatic RAI flow for predict-then-optimize and predict-then-rules chains:

```python
# 1. Train and bind predictions
Item.predictions = gnn.predictions(domain=Test)

# 2. Derive a regular property from the prediction
Item.predicted_value = model.Property(f"{Item} has {Float:predicted_value}")
model.define(Item.predicted_value(Item.predictions.predicted_value))

# 3a. Predictive -> Rules: boolean flag
Item.is_high = model.Relationship(f"{Item} is high")
model.where(Item.predicted_value > threshold).define(Item.is_high())

# 3b. Predictive -> Prescriptive: Item.predicted_value can appear in
# Problem(model, Float) constraint / objective expressions.
```

### Cross-session pattern (explicit persistence)

If training and downstream reasoning run in separate processes, persist predictions to Snowflake and reload them as a fresh `Concept`:

```python
# Training session: save predictions DataFrame
df = select(Source.source_id, Source.predictions.predicted_value) \
     .where(Source.predictions).to_df()
# Then write_pandas(conn, df, "MY_PREDICTIONS", auto_create_table=True, overwrite=True)
# Grant SELECT on MY_PREDICTIONS to APPLICATION RELATIONALAI.

# Downstream session: load as a Concept in a new Model
Prediction = Concept("Prediction", identify_by={"source_id": Integer})
model.define(Prediction.new(Table("DB.SCHEMA.MY_PREDICTIONS").to_schema()))
# Derive properties from Prediction, apply rules, run a solver, etc.
```

`database=` and `schema=` on `GNN(...)` are optional and omitted throughout this skill. For durable persistence, use the explicit `write_pandas` path above.

### Aggregation and bridge concepts

When the downstream reasoner's scope differs from the GNN source -- e.g. per-source predictions feeding a per-target optimizer -- aggregate predictions via `aggregates.<agg>(...).per(Target).where(join)` and attach the result to a **bridge concept** representing the downstream scope:

```python
# GNN source predicts a value per Source (e.g. per-event regression);
# downstream scope is OptTarget, one row per coarser entity.
OptTarget = Concept("OptTarget", identify_by={"opt_target_id": Integer})
OptTarget.total_predicted_value = model.Property(f"{OptTarget} has {Float:total_predicted_value}")

agg = aggregates.sum(Source.predictions.predicted_value).per(OptTarget).where(
    Interaction.target_id == OptTarget.opt_target_id,
    Interaction.source_id == Source.source_id,
)
model.define(OptTarget.total_predicted_value(agg))
```

The bridge concept (`OptTarget`) separates *what the GNN predicted at Source scope* from *what the downstream reasoner consumes at Target scope*. Skipping the bridge and trying to use `Source.predictions.predicted_value` directly in a Target-scoped constraint forces ad-hoc joins inside each rule or objective expression. For classification or link-prediction predictions, swap `sum`/`predicted_value` for `avg`/`probs` or `count`/`scores` per the rule below.

**Choose the aggregation function by target shape.** Use `sum` for additive or count-like predictions (per-event regression values rolled up to an entity total), `avg` for proportional or probability-like predictions (mean predicted score across related source entities), `count` for link-prediction hits. Mixing them produces values that look numerically fine but don't mean what downstream expects.

**Non-additive blending of multiple signals** (e.g. combining several GNN outputs, or a GNN probability with a rule-derived flag) is also a derived-property step, not a built-in `aggregates.<fn>`. Express it as ordinary arithmetic in the property definition: a multiplicative composite (`predicted_a * (1 - w * avg_b) * (1 + w * avg_c)`) for risk-uplift-style logic, or a weighted interpolation (`alpha * rule_signal + (1 - alpha) * gnn_probs`) for hybrid scoring. Keep the bridge concept distinct from the GNN source so the blend is a regular Property the downstream reasoner can consume.

**Denormalize if the target was pre-scaled at training.** If the training target was normalized (e.g. to `[0, 1]`, or z-scored), raw predictions carry that scale too. Record the denormalization factor alongside the derived property and apply it before feeding into constraints or objectives that expect real-world units -- otherwise the downstream reasoner sees tiny numbers where it expected the real-world quantity.

For a full predict-then-optimize example chaining multiple GNNs into optimizers with bridge + aggregation, see the `retail_planning` template in the templates repo.

---

## Evaluation & Debugging

After `gnn.fit()`, inspect what data the engine received:

```python
# Visual schema with data types (requires pydot; omit show_dtypes for the simple variant)
graph_viz = gnn.visualize_dataset(show_dtypes=True)
graph_viz.write_png("dataset_schema.png")

# Full metadata dict (debugging feature types) and data-config printout
config = gnn.dataset.metadata_dict
gnn.dataset.print_data_config()
```

If results are poor, see [references/evaluation-debugging.md](references/evaluation-debugging.md) § Tuning Poor Results for the ordered checklist (dataset inspection → text-feature reduction → hyperparameter tuning) plus regression-specific sanity checks, multi-metric framing, and leakage diagnostics.

---

## Model Management

### Register a Model

After `gnn.fit()` completes:

```python
gnn.register_model(
    model_database="DB",
    model_schema="MODEL_REGISTRY",
    model_name="my_predictor",
    version_name="v1",
    comment="Initial training run",  # optional
)
```

### Load by Registry Key

```python
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    source_concept=User,
    task_type="binary_classification",
    has_time_column=True,
    model_database="DB", model_schema="MODEL_REGISTRY",
    model_name="my_predictor", version_name="v1",
)
gnn.load()
User.predictions = gnn.predictions(domain=Test)
```

### Load by Run ID

Same as above, replacing the registry key params with `model_run_id="<run_id>"`.

### What to Include vs. Omit When Loading

| Include | Omit |
|---------|------|
| `exp_database`, `exp_schema` | `database`, `schema` (now optional) |
| `graph`, `property_transformer` | `train`, `validation` |
| `source_concept` (required) | `eval_metric` |
| `task_type` (required) | hyperparameters (`device`, `n_epochs`, etc.) |
| `has_time_column=True` (if model was trained with time column) | |
| `target_concept` (required for link prediction only) | |
| model identifier (registry key or run ID) | |

### Train-Register-Load Workflow

**Session 1: Train and Register**

```python
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, device="cuda", n_epochs=5,
)
gnn.fit()
gnn.register_model(
    model_database="DB", model_schema="MODEL_REGISTRY",
    model_name="my_predictor", version_name="v1",
)
```

**Session 2: Load and Predict**

```python
# Rebuild graph and property_transformer (same structure as training)
gnn_graph = Graph(model, directed=True, weighted=False)
# ... define edges ...
pt = PropertyTransformer(...)

gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    source_concept=User,
    task_type="binary_classification",
    has_time_column=True,
    model_database="DB", model_schema="MODEL_REGISTRY",
    model_name="my_predictor", version_name="v1",
)
gnn.load()
User.predictions = gnn.predictions(domain=Test)
```

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Missing `has_time_column=True` | Templates with the "at" keyword require the flag so the trainer finds the time column | Set `has_time_column=True` when templates contain "at" |
| Using `.predicted_Item` (uppercase) | Target-attribute names are always lowercased from the Target concept name | Use `.predicted_item` |
| Invalid `task_type`/`eval_metric` combination | Not every metric applies to every task type | Check [references/task-types-and-metrics.md](references/task-types-and-metrics.md) for valid pairs |
| `register_model()` before `fit()` | Registration requires a trained model | Always call `gnn.fit()` before `gnn.register_model()` |
| `model_name` or `version_name` with spaces or special characters (e.g. `"my model"`, `"v1.0!"`) | Snowflake rejects non-identifier strings as model names, but validation only happens after full training completes | Use plain alphanumeric names with underscores only (e.g. `"my_model"`, `"V1"`) |
| Calling `register_model()` with a `(model_name, version_name)` pair that already exists in the registry | The registry enforces uniqueness — duplicate versions raise `ModelManagerError` | Use a new `version_name` (e.g. `"V2"`) or delete the existing version first |
| Calling `register_model()` on a GNN instance created in load mode | Load-mode GNN instances cannot re-register — only fit-mode instances can register models | Call `register_model()` on the `fit_gnn` instance after `fit()`, not on the `gnn` instance after `load()` |
| Omitting `graph`/`property_transformer` when loading | Load reconstructs against the same schema used during training | Provide the same `graph` and `property_transformer` used during training |
| Passing training-only params when loading | Load ignores training-time params | Omit `train`, `validation`, and hyperparameters when loading |
| Omitting `source_concept` when loading | Required to bind the loaded model to the source concept for prediction | Add `source_concept=<YourConcept>` to the load constructor |
| Omitting `task_type` when loading | Not persisted in the registry | Add `task_type="<your_task_type>"` to the load constructor |
| Omitting `target_concept` for link-prediction load | Required to resolve the prediction target concept | Add `target_concept=<YourTargetConcept>` for link prediction |
| Omitting `has_time_column` when loading a temporal model | Not persisted in the registry | Re-supply `has_time_column=True` at load time |
| Calling `fit()` on a GNN instance created in load mode | Load-mode GNN instances do not support training | Create a separate fit-mode GNN instance (with `train=`, `validation=`) and call `fit()` on that |
| Calling `load()` on a GNN instance created in fit mode (with `train=`, `validation=`) | Fit-mode GNN instances do not support `load()` | Create a separate load-mode GNN instance (with `source_concept=`, `model_name=`, `version_name=`) and call `load()` on that |
| `has_time_column=True` fails with "no time column defined in data tables" | The concept carrying `time_col` is an edge, not a node — `time_col` only propagates for node concepts | Use `has_time_column=False` with non-temporal Relationships as workaround |
| `has_time_column=True` fails with `ValidationError: Error processing datetime column '<name>'` at scale | Server-side datetime processing rejects the column despite clean data, node-level concept, and correct `datetime`/`time_col` config — second known limitation | Verify the timestamp column type matches the GNN datetime pipeline's expected format (see `rai-predictive-modeling`); fall back to non-temporal Relationships if it persists |
| `SnowflakeTableObjectsException: Failed to pull data into index: transaction was aborted (runtime error)` | Opaque client wrapper that hides the actual server-side error (commonly a stale compiled-relation signature after schema drift, but other causes possible) | Pull `problems.json` via `RELATIONALAI.API.GET_TRANSACTION_ARTIFACTS('<txn_id>')` (presigned URL) and read the `report` field for the real error. For the schema-drift case specifically, see § Known Limitations |
| Experiment schema not accessible by the RAI native app | RAI app needs explicit grants to write to the experiment schema | `GRANT USAGE ON DATABASE <db> TO APPLICATION RELATIONALAI; GRANT USAGE ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI; GRANT CREATE EXPERIMENT ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI; GRANT CREATE MODEL ON SCHEMA <db>.<schema> TO APPLICATION RELATIONALAI` |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Node classification | Binary classification training + prediction | [examples/train_node_classification.py](examples/train_node_classification.py) |
| Link prediction | Repeated link prediction training + prediction | [examples/train_link_prediction.py](examples/train_link_prediction.py) |
| Regression | Regression training + prediction | [examples/train_regression.py](examples/train_regression.py) |
| Register and load | Complete train-register-load workflow across sessions | [examples/register_and_load.py](examples/register_and_load.py) |

---

## Reference Files

| Reference | Description | File |
|-----------|-------------|------|
| Task types and metrics | All valid (task_type, eval_metric) combinations | [references/task-types-and-metrics.md](references/task-types-and-metrics.md) |
| Hyperparameters | Full hyperparameter table with types, defaults, and tuning guidance | [references/hyperparameters.md](references/hyperparameters.md) |
| Prediction attributes | Prediction attributes by task type with usage examples | [references/prediction-attributes.md](references/prediction-attributes.md) |
| Evaluation & debugging | Dataset inspection, result checking, and tuning steps | [references/evaluation-debugging.md](references/evaluation-debugging.md) |
