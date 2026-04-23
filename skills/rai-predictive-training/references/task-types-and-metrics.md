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

Replace `@k` with the desired top-k value, e.g. `"link_prediction_precision@5"`.

## Task Type Summary

| Task Type | has_time_column | Train Relationship template | Test Relationship template |
|-----------|-----------------|---------------------------|--------------------------|
| binary_classification | optional | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| multiclass_classification | optional | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| multilabel_classification | optional | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| regression | optional | `f"{Source} has {Any:value}"` | `f"{Source}"` |
| link_prediction | False | `f"{Source} has {Target}"` | `f"{Source}"` |
| repeated_link_prediction | True | `f"{Source} at {Any:ts} has {Target}"` | `f"{Source} at {Any:ts}"` |
