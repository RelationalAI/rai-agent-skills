"""
GNN Link Prediction -- Data Modeling (Phases 1-6)
=================================================
Repeated link prediction on a bipartite User-Item graph with an Interaction
edge-intermediary concept carrying timestamps.

Demonstrates: concepts, population, task relationships (link prediction with
time), graph edges via an intermediary concept, and PropertyTransformer.

For training and prediction, see `rai-predictive-training`.
"""

# -- Phase 1: Imports & Model Setup --
from relationalai.semantics import Model, select, define, Integer, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

model = Model("gnn_link_prediction_example")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# -- Phase 2: Define Concepts --
# graph (node) concepts -- User is source (predicting from), Item is target (predicting to).
# Interaction has its own identify_by because it carries `time_col` (timestamp); time_col
# only propagates for node concepts, so an edge-intermediary version (no identify_by) would
# fail validation. See `rai-predictive-training` § Known Limitations.
User = Concept("User", identify_by={"user_id": Integer})
Item = Concept("Item", identify_by={"item_id": Integer})
Interaction = Concept("Interaction", identify_by={"interaction_id": Integer})

# task table concepts
train_table_concept = Concept("TrainTable")
val_table_concept = Concept("ValidationTable")
test_table_concept = Concept("TestTable")

# -- Phase 3: Populate Concepts (from Snowflake) --
define(User.new(Table("DB.SCHEMA.USERS").to_schema()))
define(Item.new(Table("DB.SCHEMA.ITEMS").to_schema()))
define(Interaction.new(Table("DB.SCHEMA.INTERACTIONS").to_schema()))

define(train_table_concept.new(Table("DB.SCHEMA.TRAIN_LINK").to_schema()))
define(val_table_concept.new(Table("DB.SCHEMA.VAL_LINK").to_schema()))
define(test_table_concept.new(Table("DB.SCHEMA.TEST_LINK").to_schema()))

# -- Phase 4: Setup Task Relationships -- repeated_link_prediction (with time)
# Train/Val carry the Target concept in the "has" clause (no {Any:label}).
# Test omits the target: the GNN predicts which Item each User links to.
Train = Relationship(f"{User} at {Any:timestamp} has {Item}")
define(Train(User, train_table_concept.timestamp, Item)).where(
    User.user_id == train_table_concept.user_id,
    Item.item_id == train_table_concept.item_id,
)

Val = Relationship(f"{User} at {Any:timestamp} has {Item}")
define(Val(User, val_table_concept.timestamp, Item)).where(
    User.user_id == val_table_concept.user_id,
    Item.item_id == val_table_concept.item_id,
)

Test = Relationship(f"{User} at {Any:timestamp}")
define(Test(User, test_table_concept.timestamp)).where(
    User.user_id == test_table_concept.user_id,
)

# -- Phase 5: Build Graph & Edges --
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

define(Edge.new(src=Interaction, dst=User)).where(
    Interaction.user_id == User.user_id)
define(Edge.new(src=Interaction, dst=Item)).where(
    Interaction.item_id == Item.item_id)

# -- Phase 6: Configure PropertyTransformer --
pt = PropertyTransformer(
    category=[User.region, User.status, Item.category, Interaction.channel],
    continuous=[User.age, Interaction.value],
    text=[Item.name],
    datetime=[Interaction.timestamp],
    time_col=[Interaction.timestamp],
)
