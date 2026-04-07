# Prediction Attributes by Task Type

After calling `gnn.predictions(domain=Test)`, the prediction results are attached to the source concept (head of the Relationship) and accessed via `select(...)`.

## Classification (binary, multiclass, multilabel)

| Attribute | Type | Description |
|-----------|------|-------------|
| `Source.predictions.probs` | float/array | Probability distribution over classes |
| `Source.predictions.predicted_labels` | int/str | Predicted class label (argmax of probs) |

```python
Source.predictions = gnn.predictions(domain=Test)
select(
    Source.id,
    Source.predictions.probs,
    Source.predictions.predicted_labels,
).where(Source.predictions).inspect()
```

## Regression

| Attribute | Type | Description |
|-----------|------|-------------|
| `Source.predictions.predicted_value` | float | Predicted continuous value |

```python
Source.predictions = gnn.predictions(domain=Test)
select(
    Source.id,
    Source.predictions.predicted_value,
).where(Source.predictions).inspect()
```

## Link Prediction (link_prediction, repeated_link_prediction)

| Attribute | Type | Description |
|-----------|------|-------------|
| `Source.predictions.rank` | int | Ranking position (1, 2, 3, ...) |
| `Source.predictions.scores` | float | Relevance/similarity score |
| `Source.predictions.predicted_<target>` | reference | Predicted target concept instance |

The `predicted_<target>` attribute name is derived from the target concept in the Relationship template. For example, if the Relationship tail is `Article`, the attribute is `predicted_article`.

```python
Source.predictions = gnn.predictions(domain=Test)
select(
    Source.source_id,
    Target.target_id,
    Source.predictions.rank,
    Source.predictions.scores,
).where(
    Source.predictions.predicted_article == Target,
).inspect()
```

## Using `.to_df()` Instead of `.inspect()`

Replace `.inspect()` with `.to_df()` to get a pandas DataFrame:

```python
df = select(
    Source.id,
    Source.predictions.probs,
    Source.predictions.predicted_labels,
).where(Source.predictions).to_df()
```
