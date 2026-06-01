# GNN Hyperparameters

Hyperparameters are passed as `**train_params` kwargs to the `GNN(...)` constructor. The groups below mirror the doc's organization (`build/guides/reasoning/predictive/configure-a-GNN`).

> **Note on defaults.** The table values reflect the SDK's library defaults (`relationalai_gnns.TrainerConfig`); the example `train_params` blocks below show typical overrides for common scenarios. When in doubt, defer to the live SDK signature.

## General

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device` | str | `"cuda"` | Compute device: `"cuda"` (GPU) or `"cpu"`. Auto-falls back to `"cpu"` if the predictive reasoner has no GPU |
| `seed` | int | `42` (fixed) | Random seed for reproducibility. Keep at the fixed default unless you specifically need a different deterministic seed |

## Training loop

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_epochs` | int | 10 | Number of training epochs (full passes over the training data) |
| `max_iters` | int \| None | `None` | Cap on batch iterations per epoch. `None` processes all batches |
| `train_batch_size` | int | 128 | Training batch size |
| `val_batch_size` | int | 128 | Validation batch size |
| `eval_every` | int | 1 | Frequency (in epochs) of validation evaluation |
| `patience` | int | 5 | Epochs without validation improvement before early stopping |
| `lr` | float | 0.001 | Learning rate |
| `T_max` | int \| None | `None` | Max iterations for the cosine-annealing LR scheduler. Defaults to `n_epochs` if `None` |
| `eta_min` | float | `1e-8` | Minimum learning rate for cosine annealing |

## Labels and loss

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label_smoothing` | bool | `False` | Apply label smoothing for classification. The skill recommends `True` for link prediction (see the Link prediction example below) |
| `label_smoothing_alpha` | float | `0.1` | Smoothing strength α ∈ (0, 1). Only used when `label_smoothing=True` |
| `clamp_min` | int | 0 | Lower percentile cutoff (0–100) on the model's output distribution. 0 = no cutoff |
| `clamp_max` | int | 100 | Upper percentile cutoff (0–100). 100 = no cutoff. Restricts predictions to exclude the top portion of the distribution |

## GNN architecture

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `channels` | int | 128 | Hidden channels for the GNN, encoders, and prediction head |
| `gnn_layers` | int \| None | `None` | Number of GNN layers. Defaults to `len(fanouts)` if `None` |
| `fanouts` | list[int] | `[128, 64]` | Neighbors to sample per GNN layer. Length implicitly sets depth when `gnn_layers=None` |
| `conv_aggregation` | str | `"mean"` | Aggregation within a single edge type. One of `"mean"`, `"max"`, `"sum"` |
| `hetero_conv_aggregation` | str | `"sum"` | Aggregation across edge types in heterogeneous graphs. One of `"mean"`, `"max"`, `"sum"` |
| `gnn_norm` | str | `"layer_norm"` | Normalization for GNN layers. One of `"batch_norm"`, `"layer_norm"`, `"instance_norm"` |

### Depth vs schema diameter

A GNN propagates signal one hop per layer (or one level per neighbor-sampling step). If the source concept sits far from the concepts carrying predictive signal, the model's depth must reach them — otherwise distant nodes never contribute. When sweeping depth, sweep both `gnn_layers` and the length of `fanouts` (they coordinate).

## Prediction head

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `head_layers` | int | 1 | MLP layers in the prediction head |
| `head_norm` | str | `"batch_norm"` | Normalization for the head MLP. One of `"batch_norm"`, `"layer_norm"` |

## Temporal sampling

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_temporal_encoder` | bool | `True` | Use a temporal encoding model when `has_time_column=True` |
| `temporal_strategy` | str | `"uniform"` | Strategy for temporal neighbor sampling. `"uniform"` ignores time; `"last"` picks the most recent |

## Negative sampling (link prediction)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_negative` | int | 10 | Number of negative samples per source node |
| `negative_sampling_strategy` | str | `"random"` | `"random"` or `"degree_based"` (favors popular nodes) |

## Embeddings and shallow features

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text_embedder` | str | `"bert-base-distill"` | Text embedding model. One of `"model2vec-potion-base-4M"`, `"bert-base-distill"`. `bert-base-distill` is heavier and slower per epoch; `model2vec-potion-base-4M` is the lighter alternative for runs bottlenecked on text embedding |
| `id_awareness` | bool | `False` | Use ID-awareness embeddings (per-node learnable identity signal) |
| `shallow_embeddings_list` | list[str] | `[]` | Tables to assign learnable shallow embeddings — useful for high-cardinality categorical sources that don't have meaningful features of their own |

## GNN constructor operational flags

These are named parameters on `GNN(...)`, not `train_params` kwargs:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `test_batch_size` | int \| None | `None` | Batch size for prediction/inference |
| `stream_logs` | bool | `True` | Stream training logs to console |
| `use_current_time` | bool | `True` | Time-window inclusivity for temporal tasks. **`False`** uses strict `<` (data **before** the prediction date — realistic forecasting; no same-day leakage). **`True`** uses `<=` (data **up to and including** the prediction date — simulation / "what-if" analysis where same-day features like an active promotion are already known). Choose `False` for production forecasting, `True` for inference that reflects current conditions |
| `parallel_reasoners_init` | bool | `True` | Initialize the Predictive and Logic reasoners in parallel during `fit()`. Keep `True` unless debugging reasoner startup interleaving |

## Example configurations

Each block below shows the **overrides** typical for the named scenario; unset params keep their `TrainerConfig` defaults from the tables above.

### Node classification (CPU smoke run on a small dataset)
```python
train_params = {"device": "cpu", "n_epochs": 5, "seed": 42}  # halve epochs for a quick sanity run
```

### Node classification (production training)
```python
train_params = {"device": "cuda", "n_epochs": 20, "lr": 0.005, "seed": 42}
# Raise epochs above the default of 10 for more learning; bump lr if loss is flat
```

### Link prediction
```python
train_params = {
    "device": "cuda",
    "n_epochs": 20,
    "head_layers": 2,          # deeper head helps rank quality
    "num_negative": 20,        # more negatives stabilize the ranking loss
    "label_smoothing": True,   # the skill recommends True for link prediction (library default is False)
    "seed": 42,
}
```

### Regression with temporal data
```python
train_params = {
    "device": "cuda",
    "n_epochs": 20,
    "temporal_strategy": "last",  # uniform default ignores time; "last" picks the most recent neighbor
    "seed": 42,
}
```

## Tuning when results are poor

Two heuristics before the symptom table:

- **`lr` is usually the first knob to sweep.** The default is a starting point, not a recommendation. If training isn't producing learning (flat losses, no convergence), try `lr` above and below the default before concluding features are the problem.
- **Message-passing depth vs graph diameter.** See "Depth vs schema diameter" above. Sweep `gnn_layers` and `fanouts` together.

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Validation metric still improving at last epoch | Not enough training | Increase `n_epochs` |
| Training loss oscillates or diverges | Learning rate too high | Lower `lr` |
| Good training metric, poor validation metric | Overfitting | Reduce `n_epochs`, reduce text features, or increase `train_batch_size` |
| Very slow convergence on large dataset | Batch too small or lr too high | Increase `train_batch_size`, decrease `lr` |
| Poor results despite hyperparameter sweeps | Signal can't reach the source concept | Check the graph depth matches the schema's diameter; otherwise reduce noisy features (drop PKs/FKs, trim text fields) |
| Predictions concentrated near the mean / hedging | Output distribution under-spread | Try lower `clamp_min` and higher `clamp_max` (widen percentile band); also revisit `lr` and features |
