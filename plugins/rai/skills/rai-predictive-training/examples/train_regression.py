"""
GNN Regression -- Training & Prediction
========================================
Regression training and prediction with temporal features.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer instance (passed as `property_transformer=pt`)
  - Train, Val, Test: Relationship objects
  - Interaction: source concept (head of Relationship template)
"""
from relationalai.semantics import select
from relationalai.semantics.reasoners.predictive import GNN

# -- Train GNN ---------------------------------------------------------------
# Regression typically needs more epochs than classification. Start with 20-50;
# 5 (the classification default) is a smoke test and usually plateaus at the mean.
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=True,
    device="cuda",
    n_epochs=20,
    lr=0.005,
)
gnn.fit()

# -- Predict & Inspect -------------------------------------------------------
Interaction.predictions = gnn.predictions(domain=Test)

select(
    Interaction.interaction_id,
    Interaction.predictions.predicted_value,
).where(Interaction.predictions).inspect()

df = select(
    Interaction.interaction_id,
    Interaction.predictions.predicted_value,
).where(Interaction.predictions).to_df()

print(f"Predictions: {len(df)} rows")
