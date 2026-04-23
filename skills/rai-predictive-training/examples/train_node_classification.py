"""
GNN Node Classification -- Training & Prediction
==================================================
Binary classification training and prediction on user data.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer instance (passed as `property_transformer=pt`)
  - Train, Val, Test: Relationship objects
  - User: source concept (head of Relationship template)
"""
from relationalai.semantics import select
from relationalai.semantics.reasoners.predictive import GNN

# -- Train GNN ---------------------------------------------------------------
gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    device="cuda",
    n_epochs=5,
)
gnn.fit()

# -- Predict & Inspect -------------------------------------------------------
User.predictions = gnn.predictions(domain=Test)

select(
    User.user_id,
    User.predictions.probs,
    User.predictions.predicted_labels,
).where(User.predictions).inspect()

df = select(
    User.user_id,
    User.predictions.probs,
    User.predictions.predicted_labels,
).where(User.predictions).to_df()

print(f"Predictions: {len(df)} rows, {len(df.dropna())} after dropping NaNs")
