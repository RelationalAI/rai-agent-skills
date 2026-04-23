"""
GNN Model Management -- Register and Load Workflow
====================================================
Demonstrates the train-register-load pattern across sessions.

Session 1: Train a model and register it to Snowflake Model Registry.
Session 2: Load the registered model and generate predictions.
"""
from relationalai.semantics.reasoners.predictive import GNN

# -- Session 1: Train and Register -------------------------------------------
# Assumes data model from `rai-predictive-modeling`:
#   gnn_graph, pt, Train, Val, Test, User

gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    train=Train, validation=Val,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True,
    device="cuda", n_epochs=5,
)
gnn.fit()

gnn.register_model(
    model_database="DB",
    model_schema="MODEL_REGISTRY",
    model_name="my_predictor",
    version_name="v1",
    comment="Initial training run",
)


# -- Session 2: Load and Predict ---------------------------------------------
# Rebuild graph and PropertyTransformer (same structure as training session)
# gnn_graph = Graph(model, directed=True, weighted=False)
# ... define edges ...
# pt = PropertyTransformer(...)

gnn = GNN(
    exp_database="DB", exp_schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    source_concept=User,
    task_type="binary_classification",
    has_time_column=True,
    model_database="DB",
    model_schema="MODEL_REGISTRY",
    model_name="my_predictor",
    version_name="v1",
)
gnn.load()

User.predictions = gnn.predictions(domain=Test)
