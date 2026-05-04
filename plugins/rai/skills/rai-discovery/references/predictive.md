<!-- TOC -->
- [Prediction Question Types](#prediction-question-types)
- [User-Type → GNN Task Type Translation](#user-type--gnn-task-type-translation)
- [Predictive Implementation Hints](#predictive-implementation-hints)
- [When Predictive vs Other Reasoners](#when-predictive-vs-other-reasoners)
- [Pre-Computed Predictions Pattern](#pre-computed-predictions-pattern)
- [Output Concepts](#output-concepts)
- [Data Sufficiency Signals](#data-sufficiency-signals)
<!-- /TOC -->

## Prediction Question Types

Predictive reasoning uses historical data patterns to predict labels, values, or links on a graph.

**Two modes:** Predictive capabilities can be delivered via **pre-computed prediction tables** (external ML outputs loaded into Snowflake) or via the **RAI predictive pipeline** (GNN-based models trained directly on the knowledge graph — see `rai-predictive-modeling` and `rai-predictive-training`). Discovery should identify both pre-computed predictions already in the data and predictive questions the data could support via GNN training.

The RAI predictive reasoner supports three task families. Anything outside these (anomaly detection, clustering, time-series forecasting on aggregate signals) is not supported natively — surface it only when a pre-computed table already exists.

| Type | Question Pattern | Ontology Signal |
|------|-----------------|-----------------|
| **Node Classification / Risk Scoring** | "Which category / risk tier does X belong to?" / "Will X churn?" / "Will X be next period?" (per-node binary/multiclass/multilabel) | Categorical target on a graph node concept, labeled historical data, status/tier fields. Temporal flavor: same plus a time column on the node. |
| **Node Regression** | "How much / what value will X be?" / "Forecast X's value next period" (per-node regression, with or without time) | Numeric target on a graph node concept + numeric/categorical features, historical actuals. Temporal flavor adds a time column on the node. |
| **Link Prediction / Recommendation** | "Will X be linked to Y?" / "Which Ys should we recommend for each X?" / "Which pairs will interact next period?" | Two node concepts joined by an interaction/edge concept; historical pair data; optionally a timestamp on the edge |

**Disambiguation rules:**
- "What will happen?" with historical labeled data → predictive
- "What should we do about it?" → predictive → prescriptive chain
- Deterministic classification from known thresholds (e.g., "high-value if spend > $10K") → rules or derived property, NOT predictive
- "What patterns exist in the network?" → graph, not predictive (unless using graph features for prediction)
- "Will edges form / which pairs are likely to interact / recommend Y for X" → predictive (link prediction), not graph; graph reasons over the **current** topology, link prediction predicts **future or missing** edges
- Per-period numeric prediction ("forecast next month's demand for each unit") → node regression with a time column (`has_time_column=True` on the GNN), not a separate forecasting task type
- Node classification or node regression with rich graph topology around the predicted entity → strong fit for `rai_predictive` (GNN) mode; flat-table classification/regression with no meaningful graph structure can still use `rai_predictive` but loses the GNN's structural advantage

---

## User-Type → GNN Task Type Translation

Discovery is the translation layer. Classify the user's question into one of three user-facing `type` values, then resolve the granular GNN `task_type` and `eval_metric` from the data signals below. Downstream `rai-predictive-modeling` and `rai-predictive-training` consume the technical fields directly.

| User-facing `type` | Sub-signal | GNN `task_type` | Default `eval_metric` | `has_time_column` |
|---|---|---|---|---|
| `node_classification` | Two-class label (boolean / 0-1) | `binary_classification` | `roc_auc` | from data |
| `node_classification` | Single label, 3+ mutually exclusive classes | `multiclass_classification` | `accuracy` | from data |
| `node_classification` | Multiple non-exclusive labels per row (e.g. tag set) | `multilabel_classification` | `multilabel_auprc_macro` | from data |
| `node_regression` | Numeric target, no per-row time column | `regression` | `rmse` | `False` |
| `node_regression` | Numeric target, per-period or per-timestamp prediction (a.k.a. "forecasting") | `regression` | `rmse` | `True` |
| `link_prediction` | Predict pairs, no time column | `link_prediction` | `link_prediction_precision@5` | `False` |
| `link_prediction` | Predict pairs over time / "what will X interact with next period" | `repeated_link_prediction` | `link_prediction_precision@5` | `True` |

Resolution rules:
- **Label cardinality** decides binary vs multiclass vs multilabel — inspect the train table's label column (or the schema description) before emitting `task_type`.
- **`has_time_column`** is true iff the train/val Relationship template carries an `at {Any:ts}` slot — equivalently, iff the task table has a per-row timestamp column the user wants the model to condition on.
- **Forecasting** is not a separate `task_type`. A "forecast next month's value per unit" question is `node_regression` → `regression` + `has_time_column=True` + a `temporal_column`.
- See `rai-predictive-training/references/task-types-and-metrics.md` for the full set of valid `(task_type, eval_metric)` pairs and `rai-predictive-modeling/references/task-relationships.md` for the matching Relationship templates.

---

## Predictive Implementation Hints

For each predictive suggestion, provide an implementation hint with these fields:

### type
Problem type — one of `node_classification`, `node_regression`, `link_prediction`. These are the only families the RAI predictive reasoner supports.

For `rai_predictive` (GNN) mode these map to the training-skill `task_type` values: `node_classification` → `binary_classification` | `multiclass_classification` | `multilabel_classification`; `node_regression` → `regression`; `link_prediction` → `link_prediction` (no time) or `repeated_link_prediction` (with time). See `rai-predictive-training` § Quick Reference.

Per-period numeric forecasting is `node_regression` with `has_time_column=True`, not a separate type. Anomaly detection and clustering are not supported — only emit them as `pre_computed` if an external ML table exists.

### mode
How prediction is delivered:
- **`pre_computed`**: A prediction/forecast table already exists in the schema. Discovery identifies it and suggests downstream use by other reasoners.
- **`rai_predictive`**: Build and train a graph neural network (GNN) using the RAI predictive pipeline (**early access** — APIs and behavior may change). See `rai-predictive-modeling` for data modeling and `rai-predictive-training` for training and evaluation.

### target_concept / target_property
What to predict.
- **Node classification / regression / forecasting:** `target_concept` is the node concept being predicted on; `target_property` is the label/value (e.g., `Customer` / `churn_flag`, `Entity` / `risk_value`).
- **Link prediction:** `target_concept` is the **source** node (head of the link, e.g., `User`); `target_property` does not apply. Add `link_target_concept` for the linked-to node type.

### link_target_concept (for link prediction only)
The destination node concept of the predicted link (e.g., `Item`). Maps to the `Target` slot in the GNN task relationship template `f"{Source} has {Target}"` and to the `target_concept` constructor argument when loading a link-prediction model. See `rai-predictive-modeling` § Task Relationships.

### feature_properties (for rai_predictive mode)
Which ontology properties serve as model inputs. E.g., `["Entity.reliability_score", "Activity.quantity", "Resource.category"]`.

### temporal_column (for time-aware tasks)
Which property provides the time dimension. Required when emitting `node_regression` or `node_classification` with `has_time_column=True`, or `repeated_link_prediction`. E.g., `Activity.time_period`, `Order.order_date`.

### prediction_horizon (optional, for time-aware tasks)
What future period to predict. E.g., "next period", "next 30 days".

### output_concept / output_properties
What the prediction produces. E.g., `RiskPrediction` / `["predicted_risk_prob", "risk_tier", "confidence"]`.

### pre_computed_table (for pre_computed mode)
Which schema table contains the predictions. E.g., `RISK_PREDICTION`.

---

## When Predictive vs Other Reasoners

- Historical labeled data + "what will happen?" → **predictive**
- "What should we do about the prediction?" → **predictive → prescriptive** chain
- Deterministic rules for classification (threshold-based, no learning) → **rules** or derived ontology property, not predictive
- "What patterns exist in the network?" (current topology) → **graph**, not predictive
- "Will edges form / which pairs interact next / recommend Y for X" → **predictive link prediction** (`rai_predictive` mode, `task_type=link_prediction` or `repeated_link_prediction`)
- Node-level label/value prediction on entities embedded in a graph → **predictive `rai_predictive` mode** (node classification / node regression)
- Per-period numeric prediction → **node regression with `has_time_column=True`**, not a separate forecasting task
- "Find anomalies / cluster entities" → **not supported by the GNN**; only emit as `pre_computed` if an external scoring/clustering table already exists in the schema
- Pre-computed prediction table exists in schema → **predictive (pre_computed mode)** — suggest downstream use

**Common chains involving predictive:**
- Predictive → Prescriptive: forecast demand/costs/risk, then optimize using those predictions as parameters or constraints
- Predictive → Rules: predict scores/probabilities, then apply threshold rules for alerting
- Graph → Predictive: extract structural features (centrality, community), then use as model inputs

---

## Pre-Computed Predictions Pattern

This is the current path for predictive capabilities. Discovery should actively look for prediction tables already in the schema.

### How to identify pre-computed predictions
Look for tables or concepts with columns/properties like:
- `predicted_*`, `forecast_*`, `expected_*` — prediction values
- `probability`, `confidence`, `score` — prediction certainty
- `risk_tier`, `risk_level`, `risk_category` — derived classifications
- Temporal scope columns (`time_period`, `prediction_date`, `horizon`) alongside prediction values

### Discovery behavior for pre-computed predictions
When a prediction table is detected:
1. **Classify it** — what kind of prediction is it? Map to one of the supported types (`node_classification`, `node_regression`, `link_prediction`). Anomaly scores or cluster labels from external systems are still valid pre-computed inputs even though they aren't supported `rai_predictive` task types — describe them with the closest match (`node_classification` for category labels, `node_regression` for continuous scores).
2. **Identify downstream use** — which other reasoners can consume this data?
   - Prescriptive: use predicted values as parameters/constraints (e.g., predicted risk probability as reliability threshold)
   - Rules: use predicted categories for alerting (e.g., flag "HIGH" risk tier entities)
   - Graph: use predicted scores as edge weights or node properties
3. **Suggest the chain** — frame as "Given predicted X, optimize/validate/analyze Y"

### Example pattern
A `RiskPrediction` table with `predicted_risk_prob` and `risk_tier` per entity per period:
- Direct question: "Which entities are predicted to be at risk next period?" → query the prediction table
- Chained: "Given predicted risks, how should we re-allocate to minimize cost?" → predictive → prescriptive
- Chained: "Flag all entities with predicted risk > 70%" → predictive → rules

---

## Output Concepts

Predictive reasoning (whether pre-computed or via the RAI predictive pipeline) adds concepts to the ontology that downstream reasoners consume:

| Prediction Type | Output Concept | Downstream Use |
|----------------|----------------|----------------|
| Node classification | `Entity.predictions` with `.probs`, `.predicted_labels` (bound on the source concept), or pre-computed concepts like `RiskPrediction` / `ChurnProbability` | Prescriptive: reliability constraint, retention allocation. Rules: risk alerting, threshold flags. |
| Node regression (incl. per-node forecasting) | `Entity.predictions.predicted_value` (bound on the source concept), or pre-computed `DemandForecast`-style concepts | Prescriptive: predicted value as a constraint parameter or objective coefficient (often via aggregation/bridge concept). |
| Link prediction / recommendation | `User.predictions` with `.rank`, `.scores`, `.predicted_<target>` (bound on the source concept) | Prescriptive: top-K predicted pairs as candidate edges in an assignment/matching problem. Rules: flag predicted pairs above a score threshold. |

These outputs are available for cumulative discovery — prescriptive problems that need predicted parameters become feasible once prediction data exists.

---

## Data Sufficiency Signals

What ontology patterns indicate prediction potential:

### For pre-computed mode (available now)
- Does a prediction/forecast table already exist in the schema?
- Look for columns named `predicted_*`, `probability`, `risk_*`, `forecast_*`, `confidence`
- Check if the prediction table links to other ontology concepts via FK (e.g., entity_id linking predictions to Entity concept)

### For rai_predictive mode (GNN training)
- **Graph topology**: At least one edge concept (FK-joined or via an interaction concept) connecting the predicted-on entity to other entities — the GNN's structural advantage comes from this. Without graph structure, node classification/regression still trains but loses most of the GNN signal.
- **Feature availability**: Target property with sufficient non-null values; 3+ candidate features with variance
- **Temporal span**: For temporal node classification/regression and `repeated_link_prediction`, at least 2 full cycles of the target period
- **Label quality**: For node classification, labels exist and are reasonably balanced (flag extreme imbalance like 99%/1%)
- **Pair history (link prediction)**: Historical (source, target [, timestamp]) rows in a flat task table — one row per pair, target column is a scalar ID, not a `VARIANT` array. See `rai-predictive-modeling` § Link Prediction — Task Table Format Requirements (VARIANT check).
- **Row count**: Rough minimums (node regression 50+, node classification 30+ per class, link prediction 100+ pairs)
- **Feature-target relationship**: At least some features plausibly related to target (domain signal)

**Minimum viable ontology for prediction:**
- *Pre-computed:* a prediction table exists and links to other concepts.
- *rai_predictive (node classification / node regression):* a graph node concept with a target property (what to predict) and 2+ feature properties, plus at least one edge concept tying it to neighbor entities.
- *rai_predictive (link prediction):* two graph node concepts plus historical (source, target) pair rows in a flat task table; optional timestamp for `repeated_link_prediction`.

See `rai-predictive-modeling` for the full data modeling workflow and `rai-predictive-training` for the task-type/eval-metric matrix.
