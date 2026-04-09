---
name: rai-predictive-training
description: Configure and train GNN models with hyperparameters, generate predictions, and inspect results. Use after building the data model with rai-predictive-modeling, when ready to run training or evaluate predictions.
---

# Predictive Training
<!-- v1-SENSITIVE -->

## Summary

**What:** Encodes the training and evaluation workflow for GNN pipelines — configuring the GNN estimator, running training, and generating predictions.

**When to use:**
- Configuring a GNN constructor with task type, metric, and hyperparameters
- Running `gnn.fit()` to train a model
- Generating predictions with `gnn.predictions(domain=Test)`
- Inspecting or exporting prediction results

**When NOT to use:**
- Defining concepts, loading data, or building the graph — see `rai-predictive-modeling`
- Registering or loading saved models — see `rai-predictive-management`

**Overview:**
1. Configure the GNN estimator (database, graph, task type, metric, hyperparameters)
2. Train with `gnn.fit()`
3. Generate predictions with `gnn.predictions(domain=Test)`
4. Inspect or export results

---

## Quick Reference

**GNN constructor (node classification):**
```python
gnn = GNN(
    database="DB", schema="SCHEMA",
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    train=Train, validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    device="cuda", n_epochs=5,
)
gnn.fit()
```

**Default metrics per task type:**

| Task Type | Suggested Metric |
|-----------|-----------------|
| binary_classification | `roc_auc` |
| multiclass_classification | `accuracy` |
| multilabel_classification | `multilabel_auprc_macro` |
| regression | `rmse` |
| link_prediction | `link_prediction_precision@5` |
| repeated_link_prediction | `link_prediction_precision@5` |

**Prediction attributes:**

| Task Type | Attributes |
|-----------|-----------|
| classification | `.probs`, `.predicted_labels` |
| regression | `.predicted_value` |
| link prediction | `.rank`, `.scores`, `.predicted_<target>` |

---

## GNN Constructor

The `GNN` constructor takes data locations, graph structure, task configuration, and hyperparameters.

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `database`, `schema` | Snowflake location of source data tables |
| `exp_database`, `exp_schema` | Snowflake location for experiment artifacts |
| `graph` | Graph object with edges defined (from `rai-predictive-modeling`) |
| `train`, `validation` | Relationship objects for train and validation splits |
| `task_type` | One of: `binary_classification`, `multiclass_classification`, `multilabel_classification`, `regression`, `link_prediction`, `repeated_link_prediction` |
| `eval_metric` | Evaluation metric compatible with the task type |

### Optional Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pt` | None | PropertyTransformer (omit for auto-inference) |
| `has_time_column` | False | Set `True` when Relationships use the "at" keyword |
| `stream_logs` | True | Stream training logs to console |

### Node Classification Example

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    device="cuda",
    n_epochs=5,
    lr=0.005,
)
gnn.fit()
```

### Node Regression Example (temporal)

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=True,
    device="cuda",
    n_epochs=5,
    lr=0.005,
    head_layers=2,
)
gnn.fit()
```

### Link Prediction Example (temporal)

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="repeated_link_prediction",
    eval_metric="link_prediction_precision@5",
    has_time_column=True,
    device="cuda",
    n_epochs=5,
    lr=0.005,
    head_layers=2,
    num_negative=20,
    label_smoothing=True,
)
gnn.fit()
```

### Common Hyperparameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `device` | `"cuda"` | `"cuda"` (GPU) or `"cpu"` |
| `n_epochs` | 5 | Number of training epochs |
| `lr` | 0.005 | Learning rate |
| `train_batch_size` | 256 | Training batch size |

For link prediction, also consider: `head_layers=2`, `num_negative=20`, `label_smoothing=True`.

For all hyperparameters, see [references/hyperparameters.md](references/hyperparameters.md).

---

## Training

Call `gnn.fit()` to start training. This executes the following stages:
1. Prepare dataset (load data from Snowflake)
2. Configure trainer (set up model architecture)
3. Submit training job (run on compute)

### Detecting `has_time_column`

If the Train Relationship template contains the "at" keyword (e.g. `f"{User} at {Any:timestamp} ..."`), set `has_time_column=True` in the GNN constructor.

---

## Predictions

After training, generate predictions on the test set:

```python
Source.predictions = gnn.predictions(domain=Test)
```

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
Customer.predictions = gnn.predictions(domain=Test)

select(
    Customer.customer_id,
    Article.article_id,
    Customer.predictions.rank,
    Customer.predictions.scores,
).where(
    Customer.predictions.predicted_article == Article,
).inspect()
```

The `predicted_<target>` attribute name is derived from the target concept name, always lowercase:
- Target `Article` -> `.predicted_article`
- Target `Product` -> `.predicted_product`

### As DataFrame

Replace `.inspect()` with `.to_df()` to get a pandas DataFrame:

```python
df = select(
    User.user_id,
    User.predictions.probs,
    User.predictions.predicted_labels,
).where(User.predictions).to_df()
```

For the full prediction attributes reference, see [references/prediction-attributes.md](references/prediction-attributes.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Passing `select(...)` fragments to `train=` or `validation=` | GNN expects Relationship objects — `TypeError` | Use `train=Train` with the Relationship object directly |
| Missing `has_time_column=True` | Relationships use "at" keyword but flag not set — temporal ordering ignored, degraded accuracy | Set `has_time_column=True` when templates contain "at" |
| Treating hyperparameters as named GNN parameters | Hyperparameters are `**kwargs` — `TypeError` | Pass them directly: `GNN(..., device="cuda", n_epochs=5)` |
| Expecting `gnn.predictions()` to return results | Predictions are assigned to a concept attribute — returns `None` | Use `Source.predictions = gnn.predictions(domain=Test)` |
| Using `.predicted_Article` (uppercase) | Attribute name is always lowercase — `AttributeError` | Use `.predicted_article` regardless of concept casing |
| Passing wrong object to `domain=` | Must be the Test Relationship — `TypeError` or wrong prediction scope | Use `domain=Test` with the Relationship object |
| Invalid task_type/metric combination | Not all metrics work with all task types — `ValueError` | Check the valid pairs in [references/task-types-and-metrics.md](references/task-types-and-metrics.md) |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Node classification | Binary classification training + prediction (User/Event) | [examples/train_node_classification.py](examples/train_node_classification.py) |
| Node regression | Regression training + prediction for article sales (Article) | [examples/train_node_regression.py](examples/train_node_regression.py) |
| Link prediction | Repeated link prediction training + prediction (Customer/Article) | [examples/train_link_prediction.py](examples/train_link_prediction.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Task types and metrics | All valid (task_type, eval_metric) combinations | [references/task-types-and-metrics.md](references/task-types-and-metrics.md) |
| Hyperparameters | Full hyperparameter table with types, defaults, and descriptions | [references/hyperparameters.md](references/hyperparameters.md) |
| Prediction attributes | Prediction attributes by task type with usage examples | [references/prediction-attributes.md](references/prediction-attributes.md) |
