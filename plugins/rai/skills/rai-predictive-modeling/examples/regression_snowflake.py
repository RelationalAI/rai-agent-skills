"""
GNN Regression -- Data Modeling (Phases 1-6)
=============================================
Regression with temporal features on a bipartite User-Item graph.
The source concept (Interaction) carries the numeric target to predict.

Demonstrates: concepts, population, regression task relationships with
`{Any:value}`, graph edges, and PropertyTransformer with time_col.

For training and prediction, see `rai-predictive-training`.
"""

# -- Phase 1: Imports & Model Setup --
from relationalai.semantics import Model, select, define, Integer, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

model = Model("gnn_regression_example")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# -- Phase 2: Define Concepts --
# graph concepts -- the source concept (the one being predicted on) needs its
# own primary key. If the source table lacks one, add a row_number column in
# Snowflake first (e.g. via a view or derived table).
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

define(train_table_concept.new(Table("DB.SCHEMA.TRAIN").to_schema()))
define(val_table_concept.new(Table("DB.SCHEMA.VAL").to_schema()))
define(test_table_concept.new(Table("DB.SCHEMA.TEST").to_schema()))

# -- Phase 4: Setup Task Relationships -- regression (with time)
# Train/Val carry the numeric target in the "has" clause as {Any:value}.
# Test omits the target: the GNN predicts it.
Train = Relationship(f"{Interaction} at {Any:timestamp} has {Any:value}")
define(Train(Interaction, train_table_concept.timestamp, train_table_concept.value)).where(
    Interaction.interaction_id == train_table_concept.interaction_id,
)

Val = Relationship(f"{Interaction} at {Any:timestamp} has {Any:value}")
define(Val(Interaction, val_table_concept.timestamp, val_table_concept.value)).where(
    Interaction.interaction_id == val_table_concept.interaction_id,
)

Test = Relationship(f"{Interaction} at {Any:timestamp}")
define(Test(Interaction, test_table_concept.timestamp)).where(
    Interaction.interaction_id == test_table_concept.interaction_id,
)

# -- Phase 5: Build Graph & Edges --
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

define(Edge.new(src=Interaction, dst=User)).where(
    Interaction.user_id == User.user_id,
)
define(Edge.new(src=Interaction, dst=Item)).where(
    Interaction.item_id == Item.item_id,
)

# -- Phase 6: Configure PropertyTransformer --
# Drop PKs/FKs explicitly -- fields not listed in any category get auto-inferred
# as features, so PKs/FKs must be in `drop=[...]` to actually be excluded.
pt = PropertyTransformer(
    category=[User.region, User.status, Item.category, Interaction.channel],
    continuous=[User.age],
    text=[Item.name],
    datetime=[Interaction.timestamp],
    time_col=[Interaction.timestamp],
    drop=[
        User.user_id, Item.item_id, Interaction.interaction_id,
        Interaction.user_id, Interaction.item_id,
    ],
)
