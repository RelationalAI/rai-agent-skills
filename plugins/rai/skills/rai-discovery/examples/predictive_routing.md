# Predictive Routing Examples

Discovery-to-routing walkthroughs for predictive reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "Which suppliers will likely have the most delayed shipments next quarter?"

### Ontology signals
- `DelayPrediction` table in schema with `predicted_delay_prob`, `risk_tier`, `confidence` columns → pre-computed predictions exist
- `Shipment` concept with `delay_days` and `fiscal_quarter` → historical delay data available
- `Supplier` concept with `reliability_score` → existing reliability metric

### Reasoner classification: Predictive (pre-computed classification)
- "Will likely" + future time horizon → predictive
- Pre-computed prediction table already exists → `mode: pre_computed`
- NOT graph (question is about future outcomes, not current structure)
- NOT rules (predicting probability, not checking a known threshold)

### Implementation hint
```json
{"type": "classification", "mode": "pre_computed",
 "target_concept": "Supplier", "target_property": "delay_probability",
 "output_concept": "DelayPrediction",
 "output_properties": ["predicted_delay_prob", "risk_tier", "confidence"],
 "pre_computed_table": "DELAY_PREDICTION",
 "temporal_column": "fiscal_quarter", "prediction_horizon": "next quarter"}
```

### Modeling needs (→ rai-ontology-design)
- Map `DelayPrediction` table as a concept if not already in the model
- Establish relationship: `DelayPrediction.supplier` → `Supplier` (via business_id FK)
- Properties: `predicted_delay_prob` (Float), `risk_tier` (String), `confidence` (Float)

### Reasoner handoff
- For pre-computed mode: query the `DelayPrediction` concept filtered to the target fiscal quarter
- Rank suppliers by `predicted_delay_prob` descending
- Output: ranked supplier list with delay probability, risk tier, confidence

### Cumulative discovery note
This prediction output enables prescriptive chains:
- "Given predicted delays, how should we re-source to minimize cost?" → predictive → prescriptive
- "Set reliability threshold at 80% — exclude suppliers below" → Q8's reliability constraint uses `DelayPrediction.predicted_delay_prob`

### Reference
- Data model: `hero-user-journey/src/hero_user_journey/model/generated_corrected.py` (DelayPrediction concept)
- Downstream prescriptive use: `hero-user-journey/src/hero_user_journey/queries/q8_supplier_reliability_transport.py`
