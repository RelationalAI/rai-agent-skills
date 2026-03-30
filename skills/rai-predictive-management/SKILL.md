---
name: rai-predictive-management
description: Register trained GNN models to Snowflake Model Registry and load previously trained models for inference. Use after training with rai-predictive-training, or when loading a saved model by registry key or run ID.
---

# Predictive Management
<!-- v1-SENSITIVE -->

## Summary

**What:** Encodes the model lifecycle workflow — registering trained GNN models and loading them for later inference.

**When to use:**
- Saving a trained model to Snowflake Model Registry
- Loading a previously registered model by name and version
- Loading a model by run ID
- Understanding the train-register-load multi-session workflow

**When NOT to use:**
- Defining concepts, building graphs, or configuring features — see `rai-predictive-modeling`
- Training a model or generating predictions — see `rai-predictive-training`

**Overview:**
1. Register a trained model with `gnn.register_model()`
2. Load a model by registry key or run ID with `GNN(...).load()`
3. Generate predictions with the loaded model

---

## Quick Reference

**Register:**
```python
gnn.register_model(
    model_database="MY_DB",
    model_schema="MODEL_REGISTRY",
    model_name="fraud_detector",
    version_name="v1",
)
```

**Load by registry key:**
```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    model_database="MY_DB", model_schema="MODEL_REGISTRY",
    model_name="fraud_detector", version_name="v1",
)
gnn.load()
```

**Load by run ID:**
```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    model_run_id="01c2d9a0-0711-c54d-000a-1dc707f7a1e6",
)
gnn.load()
```

**What to include vs. omit when loading:**

| Include | Omit |
|---------|------|
| `database`, `schema` | `train`, `validation` |
| `exp_database`, `exp_schema` | `task_type`, `eval_metric` |
| `graph`, `pt` | hyperparameters (`device`, `n_epochs`, etc.) |
| model identifier (registry key or run ID) | |

---

## Register a Model

After `gnn.fit()` completes, register the model to the Snowflake Model Registry:

```python
gnn.register_model(
    model_database="MY_DB",
    model_schema="MODEL_REGISTRY",
    model_name="fraud_detector",
    version_name="v1",
    comment="Initial training run",  # optional
)
```

The combination of `(model_database, model_schema, model_name, version_name)` uniquely identifies a registered model.

---

## Load a Model

### By Registry Key

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    model_database="MY_DB",
    model_schema="MODEL_REGISTRY",
    model_name="fraud_detector",
    version_name="v1",
)
gnn.load()

User.predictions = gnn.predictions(domain=Test)
```

### By Run ID

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    model_run_id="01c2d9a0-0711-c54d-000a-1dc707f7a1e6",
)
gnn.load()

User.predictions = gnn.predictions(domain=Test)
```

After `gnn.load()`, use `gnn.predictions(domain=Test)` exactly as after `gnn.fit()` — the prediction workflow is the same (see `rai-predictive-training`).

---

## Train-Register-Load Workflow

A typical multi-session workflow:

### Session 1: Train and Register

```python
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True,
    device="cuda", n_epochs=5,
)
gnn.fit()
gnn.register_model(
    model_database="MY_DB", model_schema="MODEL_REGISTRY",
    model_name="fraud_detector", version_name="v1",
)
```

### Session 2: Load and Predict

Rebuild the graph and PropertyTransformer with the same structure as training, then load:

```python
# Rebuild graph and pt (same as training session)
gnn_graph = Graph(model, directed=True, weighted=False, aggregator="sum")
# ... define edges ...
pt = PropertyTransformer(...)

gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    model_database="MY_DB", model_schema="MODEL_REGISTRY",
    model_name="fraud_detector", version_name="v1",
)
gnn.load()
User.predictions = gnn.predictions(domain=Test)
```

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Calling `register_model()` before `fit()` | Model must be trained first | Always call `gnn.fit()` before `gnn.register_model()` |
| Omitting `graph` or `pt` when loading | Loaded models still need the graph structure | Provide the same `graph` and `pt` used during training |
| Passing `train`, `validation`, or hyperparameters when loading | These are training-only parameters | Omit `train`, `validation`, `task_type`, `eval_metric`, and all hyperparameters |
| Reusing the same `(name, version)` tuple | Registry keys must be unique | Use a new `version_name` for each registration |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Register and load | Complete train-register-load workflow across sessions | [examples/register_and_load.py](examples/register_and_load.py) |
