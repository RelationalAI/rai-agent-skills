"""
GNN Node Classification -- Data Modeling (Phases 1-6)
=====================================================
Binary classification on user data from Snowflake with temporal features.
Demonstrates: concepts, population, task relationships, graph, and features.

For training and prediction, see `rai-predictive-training`.
"""

# -- Phase 1: Imports & Model Setup --
from relationalai.semantics import Model, select, define, Integer, String, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

model = Model("gnn_node_classification_example")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# -- Phase 2: Define Concepts --
# graph (node) concepts
User = Concept("User", identify_by={"user_id": Integer})
Event = Concept("Event", identify_by={"event_id": Integer})
EventAttendee = Concept("EventAttendee")

# task table concepts
train_table_concept = Concept("TrainTable")
val_table_concept = Concept("ValidationTable")
test_table_concept = Concept("TestTable")

# -- Phase 3: Populate Concepts (from Snowflake) --
define(User.new(Table("DB.SCHEMA.USERS").to_schema()))
define(Event.new(Table("DB.SCHEMA.EVENTS").to_schema()))
define(EventAttendee.new(Table("DB.SCHEMA.EVENT_ATTENDEES").to_schema()))

define(train_table_concept.new(Table("DB.SCHEMA.TRAIN").to_schema()))
define(val_table_concept.new(Table("DB.SCHEMA.VAL").to_schema()))
define(test_table_concept.new(Table("DB.SCHEMA.TEST").to_schema()))

# -- Phase 4: Setup Task Relationships --
Train = Relationship(f"{User} at {Any:timestamp} has {Any:target}")
define(Train(User, train_table_concept.timestamp, train_table_concept.target)).where(
    User.user_id == train_table_concept.user_id
)

Val = Relationship(f"{User} at {Any:timestamp} has {Any:target}")
define(Val(User, val_table_concept.timestamp, val_table_concept.target)).where(
    User.user_id == val_table_concept.user_id
)

Test = Relationship(f"{User} at {Any:timestamp}")
define(Test(User, test_table_concept.timestamp)).where(
    User.user_id == test_table_concept.user_id
)

# -- Phase 5: Build Graph & Edges --
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

define(Edge.new(src=Event, dst=User)).where(
    Event.user_id == User.user_id)
define(Edge.new(src=EventAttendee, dst=Event)).where(
    EventAttendee.event == Event.event_id)
define(Edge.new(src=EventAttendee, dst=User)).where(
    EventAttendee.user_id == User.user_id)

# -- Phase 6: Configure PropertyTransformer --
category_user = [User.locale, User.gender]
datetime_user = [User.joinedAt]
continuous_user = [User.birthyear]

category_event = [Event.city, Event.state, Event.zip, Event.country]
datetime_event = [Event.start_time]
continuous_event = [Event.lat, Event.lng]

category_event_attendee = [EventAttendee.status]
datetime_event_attendee = [EventAttendee.start_time]

pt = PropertyTransformer(
    category=[*category_user, *category_event, *category_event_attendee],
    datetime=[*datetime_user, *datetime_event, *datetime_event_attendee],
    continuous=[*continuous_user, *continuous_event],
    time_col=[Event.start_time],
)
