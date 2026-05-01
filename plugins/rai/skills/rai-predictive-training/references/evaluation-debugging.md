# Evaluation & Debugging

Detailed patterns for inspecting datasets, checking prediction results, and tuning model performance.

## Inspecting the Dataset

After `gnn.fit()`, inspect what data the engine received:

```python
# Visual graph of the dataset schema (requires pydot)
graph_viz = gnn.visualize_dataset()
graph_viz.write_png("dataset_schema.png")

# With data types shown
graph_viz = gnn.visualize_dataset(show_dtypes=True)
graph_viz.write_png("dataset_schema.png")
```

### Metadata and Data Config

```python
# Export full metadata as a dictionary (useful for debugging feature types)
config = gnn.dataset.metadata_dict

# Print the data config to console
gnn.dataset.print_data_config()
```

### Prediction-step timing expectations

`gnn.predictions(...)` runs a 4-step sequence (prepare test table -> load model -> submit prediction job -> load results into the logic engine). This sequence carries fixed overhead independent of test-set size, so small test sets still incur meaningful wall-clock time. Subsequent predictions in the same session are faster due to caching; fresh `GNN` instances re-pay the full cost. Don't optimize feature choices based on a first-run prediction time.

## Accessing Prediction Results

### Via Source Concept Attribute

```python
Source.predictions = gnn.predictions(domain=Test)

select(
    Source.id,
    Source.predictions.probs,
    Source.predictions.predicted_labels,
).where(Source.predictions).inspect()
```

### Via prediction_concept

Access the underlying prediction concept directly -- useful when you need to reference it without binding it to a source concept attribute:

```python
PredResult = gnn.prediction_concept
select(Source.source_id, PredResult.predicted_labels, PredResult.probs).where(
    Source.predictions(DateTime, PredResult)
).inspect()
```

### Dictionary-Style Field Indexing

Useful when the source concept name conflicts with an existing attribute:

```python
PredRelation = gnn.predictions(domain=Test)
select(
    PredRelation["beer"].name,
    PredRelation["timestamp"],
    PredRelation["prediction"].predicted_labels,
    PredRelation["prediction"].probs,
).inspect()
```

## Evaluating Results

### What "good" means

Ultimately a prediction is good if it supports the business question. That's the ground truth. Business-utility is hard to measure upfront, though, so training-time evaluation relies on intrinsic metrics as proxies. Pick the proxy that most resembles downstream use -- RMSE if the answer is a numeric value, Spearman rho if the answer is a rank-ordering, recall-at-precision if the answer is a gated decision -- and triangulate with the others.

### Reading the training loss

`gnn.fit()` prints per-epoch train and validation loss. The trajectory diagnoses training health before any test-set metric:

| Loss pattern | Likely cause | Action |
|--------------|-------------|--------|
| Both losses still decreasing at the last epoch | Not converged | Train longer (bump `n_epochs`) |
| Train loss decreasing, val loss plateau or rising | Overfitting | Stop earlier, reduce capacity, or add regularization |
| Both losses flat at a high value | Under-capacity, weak features, or LR too small | Check features; try a larger `lr` |
| Long plateau then step-change improvement | Model just learned a structural pattern | Keep training past the plateau -- best epoch may come late |

### Use multiple metrics

No single number describes quality. Before trusting predictions, look at:

- **Task metric vs a predict-baseline.** Predict-mean for regression, majority-class for classification. Compute the lift: `(baseline - model) / baseline`. Near-zero lift means the model hasn't learned anything useful.
- **Correlation** (Pearson + Spearman). Can be high even when absolute error is poor -- the model may have learned ranking but not magnitudes.
- **Prediction-range vs target-range.** `stddev(predicted) / stddev(target)`. A tight prediction band means the model is hedging toward the mean.
- **Error distribution.** Look at the residual histogram, not just aggregates -- a few huge errors can dominate RMSE while most predictions are fine.
- **Sanity-check the prediction DataFrame before using it downstream.** After `.to_df()`, verify the predicted column is free of NaN and stays in the expected range (`predicted_value >= 0` for non-negative targets, `probs` in `[0, 1]` for classification, `scores` non-null for link prediction). Silent NaN/garbage can propagate through a derived property or optimizer constraint and surface as a cryptic solver failure later.

  Pattern (warn-not-block — keeps the pipeline running while flagging suspicious output):

  ```python
  df = select(Source.id, Source.predictions.<attr>).where(Source.predictions).to_df()
  col = df["<attr>"]
  if col.isna().any() or (col < 0).any():       # adjust bounds per task type
      print(f"WARNING: {Source.__name__} predictions contain NaN or out-of-range values")
  ```

  Run a check per GNN in a multi-GNN pipeline; cheap and catches silent failures before they reach derived properties or solver constraints.

## Tuning Poor Results

If results are significantly worse than expected, check these in order:

1. **Inspect the dataset** -- run `gnn.visualize_dataset(show_dtypes=True)` and `gnn.dataset.print_data_config()` to verify feature types and edges match expectations.
2. **Reduce text features** -- too many text fields dilute signal. Start with 3-5 key text fields, add more only if metrics improve. In practice, reducing ~30 text fields to 5 improved AUROC from 57% to 68%.
3. **Adjust hyperparameters** -- see [hyperparameters.md](hyperparameters.md) "Tuning When Results Are Poor" section for symptom-based guidance.

### Regression-specific sanity checks

Regression typically needs **more epochs than classification** -- `n_epochs=5` (the quickstart default) is a smoke-test, not a training run. For a first real attempt, bump well above the default and let the loss trajectory (see "Reading the training loss" above) tell you when to stop -- if val-loss is still decreasing at the last epoch, you need more.

**Under-fitting checklist** (cheapest diagnostic first):

- **Profile the target distribution before training** -- `SELECT MIN, MAX, AVG, STDDEV FROM <task_table>` anchors what RMSE values mean. The same RMSE that's tight on a [0,1]-normalized target is meaningless on an unnormalized one.
- **Val-RMSE vs `stddev(target)`** -- if val-RMSE plateaus at or above the target's stddev, the model has collapsed to the mean.
- **Prediction-band vs target-band** -- if `stddev(predicted)` is noticeably narrower than `stddev(target)`, the model is hedging toward the mean. Under-trained regardless of RMSE.
- **Ranking vs magnitudes** -- if Pearson/Spearman correlation is moderate (>0.3) but RMSE doesn't beat the predict-mean baseline, the model has learned *ranking* but not *magnitudes*. This is under-fitting, not a feature problem -- train longer.
- **R² < 0 early in training is normal** -- it clears as the model learns the target's scale. If it persists past the early training phase, revisit features or learning rate.

### Suspiciously-good results

If a first-pass GNN returns R² > 0.95 (regression), AUROC > 0.98, or accuracy > 0.95 (classification), pause and check for leakage before trusting the model:

- Is the target/label column also listed in the `PropertyTransformer` (category/continuous/...) by accident?
- Is a feature a near-duplicate of the label (a derived property that encodes the target)?
- Does the train/val/test split share entities in ways that let the model memorize — e.g., the same source entity appears in all three splits with the label tied to that entity? Especially common in `repeated_link_prediction`, where the same (source, target) pair can recur across splits.

Strong features can legitimately produce high scores, but a cheap verification pass prevents shipping a leaky model.
