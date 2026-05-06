# Predictive Routing Examples

Discovery-to-routing walkthroughs for predictive reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "Which entities will likely have the most at-risk activities next period?"

### Ontology signals
- `RiskPrediction` table in schema with `predicted_risk_prob`, `risk_tier`, `confidence` columns → pre-computed predictions exist
- `Activity` concept with `risk_value` and `time_period` → historical outcome data available
- `Entity` concept with `reliability_score` → existing reliability metric

### Reasoner classification: Predictive (pre-computed classification)
- "Will likely" + future time horizon → predictive
- Pre-computed prediction table already exists → `mode: pre_computed`
- NOT graph (question is about future outcomes, not current structure)
- NOT rules (predicting probability, not checking a known threshold)

### Implementation hint
```json
{"type": "node_classification", "mode": "pre_computed",
 "target_concept": "Entity", "target_property": "risk_probability",
 "output_concept": "RiskPrediction",
 "output_properties": ["predicted_risk_prob", "risk_tier", "confidence"],
 "pre_computed_table": "RISK_PREDICTION",
 "temporal_column": "time_period", "prediction_horizon": "next period"}
```

### Modeling needs (→ rai-ontology-design)
- Map `RiskPrediction` table as a concept if not already in the model
- Establish relationship: `RiskPrediction.entity` → `Entity` (via entity_id FK)
- Properties: `predicted_risk_prob` (Float), `risk_tier` (String), `confidence` (Float)

### Reasoner handoff
- For pre-computed mode: query the `RiskPrediction` concept filtered to the target time period
- Rank entities by `predicted_risk_prob` descending
- Output: ranked entity list with risk probability, risk tier, confidence

### Cumulative discovery note
This prediction output enables prescriptive chains:
- "Given predicted risks, how should we re-allocate to minimize cost?" → predictive → prescriptive
- "Set reliability threshold at 80% — exclude entities below" → downstream prescriptive uses `RiskPrediction.predicted_risk_prob` as a reliability parameter

---

## "Will this customer churn in the next period?" (GNN node classification)

### Ontology signals
- `Customer` graph node concept with feature properties (`tenure`, `plan_type`, `monthly_spend`, ...)
- Edges from `Customer` to neighbor entities — e.g. `Interaction` joining customers to support tickets, products, or other customers — provide structural signal
- Historical labeled split tables in Snowflake: `CHURN_TRAIN`, `CHURN_VAL`, `CHURN_TEST` with `customer_id`, optional `as_of_date`, and a `churned` label on train/val
- No pre-computed `predicted_churn_*` table in schema → must train a GNN

### Reasoner classification: Predictive (`rai_predictive`, node classification)
- Categorical target (`churned`) on a node concept embedded in a graph → node classification
- Graph topology around `Customer` is meaningful → `rai_predictive` (GNN) is a strong fit, not flat-table classification
- NOT rules (no fixed threshold; learned from history)
- NOT graph (predicting a future label, not summarizing current structure)

### Implementation hint
```json
{"type": "node_classification", "mode": "rai_predictive",
 "target_concept": "Customer", "target_property": "churned",
 "feature_properties": ["Customer.tenure", "Customer.plan_type", "Customer.monthly_spend"],
 "task_type": "binary_classification", "eval_metric": "roc_auc",
 "has_time_column": true,
 "train_table": "CHURN_TRAIN", "val_table": "CHURN_VAL", "test_table": "CHURN_TEST",
 "output_concept": "Customer.predictions",
 "output_properties": ["probs", "predicted_labels"]}
```

### Reasoner handoff
- → `rai-predictive-modeling`: define `Customer` graph concept, edges to neighbors, task-table concepts, `f"{Customer} at {Any:ts} has {Any:label}"` train/val Relationships
- → `rai-predictive-training`: `GNN(..., task_type="binary_classification", eval_metric="roc_auc", has_time_column=True)`, then `Customer.predictions = gnn.predictions(domain=Test)`

### Cumulative discovery note
- "Flag customers above 70% predicted churn for retention outreach" → predictive → rules
- "Allocate retention budget to highest-churn-probability segments" → predictive → prescriptive

---

## "What will each unit's output be next period?" (GNN node regression)

### Ontology signals
- `Unit` graph node concept with continuous and categorical features
- Edges from `Unit` to related entities (e.g., `BelongsTo` → `Site`, `Operates` → `Equipment`) — graph topology informs the prediction
- Historical labeled split tables with `unit_id`, `period`, and a numeric `output_value` on train/val
- No pre-computed forecast table → train a GNN regression model

### Reasoner classification: Predictive (`rai_predictive`, node regression)
- Numeric target on a graph node concept → node regression
- Graph topology around `Unit` carries signal → `rai_predictive` mode
- NOT forecasting on a time series alone (per-unit prediction, not whole-series)
- NOT prescriptive (predicting a value, not deciding allocation)

### Implementation hint
```json
{"type": "node_regression", "mode": "rai_predictive",
 "target_concept": "Unit", "target_property": "output_value",
 "feature_properties": ["Unit.capacity", "Unit.age", "Site.region"],
 "task_type": "regression", "eval_metric": "rmse",
 "has_time_column": true,
 "train_table": "OUTPUT_TRAIN", "val_table": "OUTPUT_VAL", "test_table": "OUTPUT_TEST",
 "output_concept": "Unit.predictions",
 "output_properties": ["predicted_value"]}
```

### Reasoner handoff
- → `rai-predictive-modeling`: `Unit` concept, edges, task-table concepts, `f"{Unit} at {Any:ts} has {Any:value}"` Relationships
- → `rai-predictive-training`: `GNN(..., task_type="regression", eval_metric="rmse", has_time_column=True)`

### Cumulative discovery note
- "Allocate inputs across units to maximize total predicted output subject to capacity" → predictive → prescriptive (often via aggregation/bridge concept; see `rai-predictive-training` § Aggregation and bridge concepts)

---

## "Which products should we recommend to each user?" (GNN link prediction)

### Ontology signals
- Two graph node concepts: `User` and `Item`, with feature properties on each
- `Interaction` concept joining `User` × `Item` over time (purchases, views, ratings) — the historical edge set
- Split tables for link-prediction: `LINK_TRAIN(user_id, ts, item_id)`, `LINK_VAL(user_id, ts, item_id)`, `LINK_TEST(user_id, ts)`
- Verified flat format: `item_id` is a scalar column, not a `VARIANT` array — see `rai-predictive-modeling` § Link Prediction — Task Table Format Requirements (VARIANT check)

### Reasoner classification: Predictive (`rai_predictive`, link prediction)
- "Which Y for each X" / "recommend" / "predict pair" → link prediction, not classification or regression
- Two node concepts joined by historical pair data → `rai_predictive` `link_prediction` (or `repeated_link_prediction` with time)
- NOT graph (graph reasons over current edges; link prediction predicts missing or future edges)
- NOT rules (no deterministic rule for what to recommend)

### Implementation hint
```json
{"type": "link_prediction", "mode": "rai_predictive",
 "target_concept": "User", "link_target_concept": "Item",
 "feature_properties": ["User.locale", "User.tenure", "Item.category", "Item.price"],
 "task_type": "repeated_link_prediction", "eval_metric": "link_prediction_precision@5",
 "has_time_column": true,
 "train_table": "LINK_TRAIN", "val_table": "LINK_VAL", "test_table": "LINK_TEST",
 "output_concept": "User.predictions",
 "output_properties": ["rank", "scores", "predicted_item"]}
```

### Reasoner handoff
- → `rai-predictive-modeling`: `User` and `Item` concepts, `Interaction` edges, task-table concepts, `f"{User} at {Any:ts} has {Item}"` train/val Relationships, `DESCRIBE TABLE` on all three split tables to confirm scalar (non-VARIANT) target columns
- → `rai-predictive-training`: `GNN(..., task_type="repeated_link_prediction", eval_metric="link_prediction_precision@5", head_layers=2, num_negative=20, label_smoothing=True)`

### Cumulative discovery note
- "Assign top-K predicted items per user subject to inventory and per-item exposure caps" → predictive → prescriptive (treat predicted pairs as candidate edges in an assignment problem)
- "Alert when a high-value user has no item with predicted score above 0.8" → predictive → rules
