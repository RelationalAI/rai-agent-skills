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
{"type": "classification", "mode": "pre_computed",
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
