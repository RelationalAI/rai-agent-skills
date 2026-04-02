"""
GNN Node Regression — Training & Prediction (Phases 7-8)
=========================================================
Regression training predicting article sales.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer configured
  - Train, Val, Test: Relationship objects
  - Article: source concept (head of Relationship template)
"""

# ── Phase 7: Train GNN ──────────────────────────────────────────────────────
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="regression",
    eval_metric="rmse",
    has_time_column=True,
    export_csv=True,
    skip_cdc=True,
    device="cuda",
    n_epochs=5,
    train_batch_size=256,
    lr=0.005,
    head_layers=2,
)
gnn.fit()

# ── Phase 8: Predict & Inspect ──────────────────────────────────────────────
Article.predictions = gnn.predictions(domain=Test)

select(
    Article.a_article_id,
    Article.predictions.predicted_value,
).where(Article.predictions).inspect()

df = select(
    Article.a_article_id,
    Article.predictions.predicted_value,
).where(Article.predictions).to_df()

print(f"Predictions: {len(df)} rows, {len(df.dropna())} after dropping NaNs")
