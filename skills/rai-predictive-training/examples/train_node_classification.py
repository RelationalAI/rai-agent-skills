"""
GNN Node Classification — Training & Prediction (Phases 7-8)
=============================================================
Binary classification training and prediction on user data.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer configured
  - Train, Val, Test: Relationship objects
  - User: source concept (head of Relationship template)
"""

# ── Phase 7: Train GNN ──────────────────────────────────────────────────────
gnn = GNN(
    database="DB", schema="SCHEMA",
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="binary_classification",
    eval_metric="roc_auc",
    has_time_column=True,
    export_csv=True,
    skip_cdc=True,
    device="cuda",
    n_epochs=5,
)
gnn.fit()

# ── Phase 8: Predict & Inspect ──────────────────────────────────────────────
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
