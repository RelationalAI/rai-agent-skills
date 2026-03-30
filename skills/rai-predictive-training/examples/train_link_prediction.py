"""
GNN Link Prediction — Training & Prediction (Phases 7-8)
=========================================================
Repeated link prediction training and prediction on H&M data.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer configured
  - Train, Val, Test: Relationship objects
  - Customer: source concept, Article: target concept
"""

# ── Phase 7: Train GNN ──────────────────────────────────────────────────────
gnn = GNN(
    database="MY_DB", schema="MY_SCHEMA",
    exp_database="MY_DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph,
    pt=pt,
    train=Train,
    validation=Val,
    task_type="repeated_link_prediction",
    eval_metric="link_prediction_precision@5",
    has_time_column=True,
    export_csv=True,
    skip_cdc=True,
    device="cuda",
    n_epochs=5,
    train_batch_size=256,
    lr=0.005,
    head_layers=2,
    num_negative=20,
    label_smoothing=True,
)
gnn.fit()

# ── Phase 8: Predict & Inspect ──────────────────────────────────────────────
Customer.predictions = gnn.predictions(domain=Test)

select(
    Customer.c_customer_id,
    Customer.age,
    Article.a_article_id,
    Customer.predictions.rank,
    Customer.predictions.scores,
).where(
    Customer.predictions.predicted_article == Article,
    Customer.age < 50,
    Customer.age > 20,
).inspect()
