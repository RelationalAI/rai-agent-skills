# Task Types and Evaluation Metrics

Valid `(task_type, eval_metric)` combinations for the GNN constructor.

## Binary Classification

| task_type | eval_metric |
|-----------|-------------|
| `"binary_classification"` | `"accuracy"` |
| `"binary_classification"` | `"f1"` |
| `"binary_classification"` | `"roc_auc"` |
| `"binary_classification"` | `"average_precision"` |

## Multiclass Classification

| task_type | eval_metric |
|-----------|-------------|
| `"multiclass_classification"` | `"accuracy"` |
| `"multiclass_classification"` | `"macro_f1"` |
| `"multiclass_classification"` | `"micro_f1"` |

## Multilabel Classification

| task_type | eval_metric |
|-----------|-------------|
| `"multilabel_classification"` | `"multilabel_auprc_micro"` |
| `"multilabel_classification"` | `"multilabel_auroc_micro"` |
| `"multilabel_classification"` | `"multilabel_precision_micro"` |
| `"multilabel_classification"` | `"multilabel_auprc_macro"` |
| `"multilabel_classification"` | `"multilabel_auroc_macro"` |
| `"multilabel_classification"` | `"multilabel_precision_macro"` |

## Regression

| task_type | eval_metric |
|-----------|-------------|
| `"regression"` | `"r2"` |
| `"regression"` | `"mae"` |
| `"regression"` | `"rmse"` |

## Link Prediction

| task_type | eval_metric |
|-----------|-------------|
| `"link_prediction"` | `"link_prediction_precision@k"` |
| `"link_prediction"` | `"link_prediction_recall@k"` |
| `"link_prediction"` | `"link_prediction_map@k"` |

## Repeated Link Prediction (temporal)

| task_type | eval_metric |
|-----------|-------------|
| `"repeated_link_prediction"` | `"link_prediction_precision@k"` |
| `"repeated_link_prediction"` | `"link_prediction_recall@k"` |
| `"repeated_link_prediction"` | `"link_prediction_map@k"` |

`@k` is optional. Omit it to evaluate without a top-k cutoff (e.g. `"link_prediction_precision"`), or append a value to restrict to the top k results (e.g. `"link_prediction_precision@5"`).

## Task Type Summary

| Task Type | has_time_column | Train Relationship template | Test Relationship template |
|-----------|-----------------|---------------------------|--------------------------|
| binary_classification | True if task table has time column | `f"{Source} has {Any:label}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
| multiclass_classification | True if task table has time column | `f"{Source} has {Any:label}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
| multilabel_classification | True if task table has time column | `f"{Source} has {Any:label}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
| regression | True if task table has time column | `f"{Source} has {Any:value}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
| link_prediction | True if task table has time column | `f"{Source} has {Target}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
| repeated_link_prediction | True if task table has time column | `f"{Source} has {Target}"` (add `at {Any:ts}` if time column present) | `f"{Source}"` (add `at {Any:ts}` if time column present) |
