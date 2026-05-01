# GNN Hyperparameters

Hyperparameters are passed as `**train_params` kwargs to the `GNN(...)` constructor.

## Common Hyperparameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device` | str | `"cuda"` | Compute device: `"cuda"` (GPU) or `"cpu"` |
| `n_epochs` | int | 5 | Number of training epochs |
| `lr` | float | 0.005 | Learning rate |
| `train_batch_size` | int | 256 | Training batch size |
| `head_layers` | int | 2 | Number of prediction head layers |
| `seed` | int | - | Random seed for reproducibility |
| `channels` | int | 64 | Hidden channel dimension |

## Link Prediction Hyperparameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_negative` | int | 20 | Number of negative samples per positive |
| `label_smoothing` | bool | True | Apply label smoothing during training |

## Advanced Hyperparameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `temporal_strategy` | str | - | Temporal modeling strategy (e.g. `"last"`) |
| `text_embedder` | str | - | Text embedding model (e.g. `"model2vec-potion-base-4M"`) |
| `max_iters` | int | - | Maximum training iterations |

## GNN Constructor Operational Flags

These are named parameters on `GNN(...)`, not train_params:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `test_batch_size` | int | None | Batch size for prediction/inference |
| `stream_logs` | bool | True | Stream training logs to console |
| `use_current_time` | bool | True | Use current time for temporal models |

## Example Configurations

### Node Classification (small dataset)
```python
train_params = {"device": "cpu", "n_epochs": 10, "seed": 42}
```

### Node Classification (large dataset)
```python
train_params = {"device": "cuda", "n_epochs": 5, "lr": 0.005, "train_batch_size": 256}
```

### Link Prediction
```python
train_params = {
    "device": "cuda",
    "n_epochs": 5,
    "train_batch_size": 256,
    "lr": 0.005,
    "head_layers": 2,
    "num_negative": 20,
    "label_smoothing": True,
}
```

### Regression with Temporal Data
```python
train_params = {
    "device": "cuda",
    "n_epochs": 5,
    "channels": 64,
    "head_layers": 2,
    "temporal_strategy": "last",
}
```

## Tuning When Results Are Poor

Two heuristics before the symptom table:

- **`lr` is usually the first knob to sweep.** The default is a starting point, not a recommendation. If training isn't producing learning (flat losses, no convergence), try `lr` above and below the default before concluding features are the problem.
- **Message-passing depth vs graph diameter.** A GNN propagates signal one hop per layer (or one level per neighbor-sampling step). If the source concept sits far from the concepts carrying predictive signal in the schema, the model's depth must reach them -- otherwise distant nodes never contribute. The depth parameter is passed through `train_params` to the trainer; inspect the trainer's accepted kwargs (e.g. on `gnn.trainer` after construction) to find the exact name.

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| Validation metric still improving at last epoch | Not enough training | Increase `n_epochs` |
| Training loss oscillates or diverges | Learning rate too high | Lower `lr` |
| Good training metric, poor validation metric | Overfitting | Reduce `n_epochs`, reduce text features, or increase `train_batch_size` |
| Very slow convergence on large dataset | Batch too small or lr too high | Increase `train_batch_size`, decrease `lr` |
| Poor results despite hyperparameter sweeps | Signal can't reach the source concept | Check the graph depth matches the schema's diameter; otherwise reduce noisy features (drop PKs/FKs, trim text fields) |
