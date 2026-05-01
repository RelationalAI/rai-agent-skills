"""
GNN Link Prediction -- Training & Prediction
==============================================
Repeated link prediction training and prediction.

Assumes data model from `rai-predictive-modeling`:
  - gnn_graph: Graph with edges defined
  - pt: PropertyTransformer instance (passed as `property_transformer=pt`)
  - Train, Val, Test: Relationship objects
  - User: source concept, Item: target concept
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
    task_type="repeated_link_prediction",
    eval_metric="link_prediction_precision@5",
    has_time_column=True,
    device="cuda",
    n_epochs=5,
    train_batch_size=256,
    lr=0.005,
    head_layers=2,
    num_negative=20,
    label_smoothing=True,
)
gnn.fit()

# -- Predict & Inspect -------------------------------------------------------
# .predicted_<target> attribute name is always lowercase: Target `Item` -> .predicted_item
User.predictions = gnn.predictions(domain=Test)

select(
    User.user_id,
    Item.item_id,
    User.predictions.rank,
    User.predictions.scores,
).where(
    User.predictions.predicted_item == Item,
).inspect()
