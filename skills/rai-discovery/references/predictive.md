<!-- TOC -->
- [Prediction Question Types](#prediction-question-types)
- [Predictive Implementation Hints](#predictive-implementation-hints)
- [When Predictive vs Other Reasoners](#when-predictive-vs-other-reasoners)
- [Pre-Computed Predictions Pattern](#pre-computed-predictions-pattern)
- [Output Concepts](#output-concepts)
- [Data Sufficiency Signals](#data-sufficiency-signals)
<!-- /TOC -->

## Prediction Question Types

Predictive reasoning uses historical data patterns to forecast outcomes, classify entities, or detect anomalies.

**Two modes:** Predictive capabilities can be delivered via **pre-computed prediction tables** (external ML outputs loaded into Snowflake) or via the **RAI predictive pipeline** (GNN-based models trained directly on the knowledge graph — see `rai-predictive-modeling` and `rai-predictive-training`). Discovery should identify both pre-computed predictions already in the data and predictive questions the data could support via GNN training.

| Type | Question Pattern | Ontology Signal |
|------|-----------------|-----------------|
| **Classification / Risk Scoring** | "Which category / risk tier does X belong to?" | Categorical target, labeled historical data, status/tier fields |
| **Regression** | "How much / what value will X be?" | Numeric target + numeric/categorical features, historical actuals |
| **Forecasting** | "What will happen next period?" | Temporal properties (date, time_period, period index), time-series data |
| **Anomaly Detection** | "What's unusual or unexpected?" | Many numeric properties, historical baselines, status/flag fields |
| **Clustering** | "What natural segments exist?" (unsupervised) | Many numeric/categorical properties, no obvious target variable |

**Disambiguation rules:**
- "What will happen?" with historical labeled data → predictive
- "What should we do about it?" → predictive → prescriptive chain
- Deterministic classification from known thresholds (e.g., "high-value if spend > $10K") → rules or derived property, NOT predictive
- "What patterns exist in the network?" → graph, not predictive (unless using graph features for prediction)

---

## Predictive Implementation Hints

For each predictive suggestion, provide an implementation hint with these fields:

### type
Problem type: `classification`, `regression`, `forecasting`, `anomaly_detection`, `clustering`.

### mode
How prediction is delivered:
- **`pre_computed`**: A prediction/forecast table already exists in the schema. Discovery identifies it and suggests downstream use by other reasoners.
- **`rai_predictive`**: Build and train a graph neural network (GNN) using the RAI predictive pipeline (**early access** — APIs and behavior may change). See `rai-predictive-modeling` for data modeling and `rai-predictive-training` for training and evaluation.

### target_concept / target_property
What to predict. E.g., `Entity` / `risk_value`, or `Customer` / `churn_flag`.

### feature_properties (for rai_predictive mode)
Which ontology properties serve as model inputs. E.g., `["Entity.reliability_score", "Activity.quantity", "Resource.category"]`.

### temporal_column (for forecasting)
Which property provides the time dimension. E.g., `Activity.time_period`, `Order.order_date`.

### prediction_horizon (for forecasting)
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
- "What patterns exist in the network?" → **graph**, not predictive (unless using graph features for prediction)
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
1. **Classify it** — what kind of prediction is it? (classification, regression, forecasting)
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
| Risk classification | `RiskPrediction` with probability, risk_tier | Prescriptive: reliability constraint. Rules: risk alerting. |
| Demand forecasting | `DemandForecast` with predicted_quantity | Prescriptive: demand parameter for allocation/inventory. |
| Churn classification | `ChurnProbability` with probability | Prescriptive: optimize retention resource allocation. |
| Anomaly scoring | `AnomalyScore` with score | Rules: flag entities above threshold. |

These outputs are available for cumulative discovery — prescriptive problems that need predicted parameters become feasible once prediction data exists.

---

## Data Sufficiency Signals

What ontology patterns indicate prediction potential:

### For pre-computed mode (available now)
- Does a prediction/forecast table already exist in the schema?
- Look for columns named `predicted_*`, `probability`, `risk_*`, `forecast_*`, `confidence`
- Check if the prediction table links to other ontology concepts via FK (e.g., entity_id linking predictions to Entity concept)

### For rai_predictive mode (GNN training)
- **Feature availability**: Target property with sufficient non-null values; 3+ candidate features with variance
- **Temporal span**: For forecasting, at least 2 full cycles of the target period (period-level prediction needs 2+ periods of history)
- **Label quality**: For classification, labels exist and are reasonably balanced (flag extreme imbalance like 99%/1%)
- **Row count**: Rough minimums (regression 50+, classification 30+ per class, forecasting 2+ full periods)
- **Feature-target relationship**: At least some features plausibly related to target (domain signal)

**Minimum viable ontology for prediction:** For pre-computed: a prediction table exists and links to other concepts. For rai_predictive (GNN): at least one concept with a target property (what to predict) and 2+ feature properties (what to predict from), backed by sufficient historical data. See `rai-predictive-modeling` for the full data modeling workflow.
