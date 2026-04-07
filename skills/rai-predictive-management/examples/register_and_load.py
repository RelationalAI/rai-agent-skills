"""
GNN Model Management — Register and Load Workflow
==================================================
Demonstrates the train-register-load pattern across sessions.

Session 1: Train a model and register it to Snowflake Model Registry.
Session 2: Load the registered model and generate predictions.
"""

# ── Session 1: Train and Register ───────────────────────────────────────────
# Assumes data model from `rai-predictive-modeling`:
#   gnn_graph, pt, Train, Val, Test, User

gnn = GNN(
    database="DB", schema="SCHEMA",
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True,
    device="cuda", n_epochs=5,
)
gnn.fit()

gnn.register_model(
    model_database="DB",
    model_schema="MODEL_REGISTRY",
    model_name="fraud_detector",
    version_name="v1",
    comment="Initial training run",
)


# ── Session 2: Load and Predict ─────────────────────────────────────────────
# REQUIRED: Rebuild the same graph and PT structure used during training
gnn_graph = Graph(model, directed=True, weighted=False, aggregator="sum")
Edge = gnn_graph.Edge
# ... define edges (same as training session) ...
pt = PropertyTransformer(...)  # same config as training session

gnn = GNN(
    database="DB", schema="SCHEMA",
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, pt=pt,
    model_database="DB",
    model_schema="MODEL_REGISTRY",
    model_name="fraud_detector",
    version_name="v1",
)
gnn.load()

User.predictions = gnn.predictions(domain=Test)
