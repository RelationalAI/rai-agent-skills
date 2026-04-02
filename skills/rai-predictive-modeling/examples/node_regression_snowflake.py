"""
GNN Node Regression — Data Modeling (Phases 1-6)
=================================================
Regression predicting article sales from H&M data in Snowflake.
Demonstrates: concepts, population, task relationships, graph, and features.

For training and prediction, see `rai-predictive-training`.
"""

# ── Phase 1: Imports & Model Setup ──────────────────────────────────────────
from relationalai.semantics import Model, select, define, Integer, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer

model = Model("gnn_node_regression_example")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# ── Phase 2: Define Concepts ────────────────────────────────────────────────
# graph concepts
Customer = Concept("Customer", identify_by={"C_customer_id": Integer})
Article = Concept("Article", identify_by={"A_article_id": Integer})
Transaction = Concept("Transaction")

# task table concepts
train_table_concept = Concept("TrainTable")
val_table_concept = Concept("ValidationTable")
test_table_concept = Concept("TestTable")

# ── Phase 3: Populate Concepts (from Snowflake) ─────────────────────────────
define(Customer.new(Table("HM_MINI.PUBLIC.CUSTOMERS").to_schema()))
define(Article.new(Table("HM_MINI.PUBLIC.ARTICLES").to_schema()))
define(Transaction.new(Table("HM_MINI.PUBLIC.TRANSACTIONS_DEDUP").to_schema()))

define(train_table_concept.new(Table("HM_MINI.TASK_SALES.TRAIN").to_schema()))
define(val_table_concept.new(Table("HM_MINI.TASK_SALES.VAL").to_schema()))
define(test_table_concept.new(Table("HM_MINI.TASK_SALES.TEST").to_schema()))

# ── Phase 4: Setup Task Relationships ─────────────────────────────────────────
Train = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
define(Train(Article, train_table_concept.timestamp, train_table_concept.sales)).where(
    Article.a_article_id == train_table_concept.article_id
)

Val = Relationship(f"{Article} at {Any:timestamp} has {Any:sales}")
define(Val(Article, val_table_concept.timestamp, val_table_concept.sales)).where(
    Article.a_article_id == val_table_concept.article_id
)

Test = Relationship(f"{Article} at {Any:timestamp}")
define(Test(Article, test_table_concept.timestamp)).where(
    Article.a_article_id == test_table_concept.article_id
)

# ── Phase 5: Build Graph & Edges ────────────────────────────────────────────
gnn_graph = Graph(model, directed=True, weighted=False, aggregator="sum")
Edge = gnn_graph.Edge

define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.t_customer_id == Customer.C_customer_id)
define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.t_article_id == Article.a_article_id)

# ── Phase 6: Configure PropertyTransformer ──────────────────────────────────
# Customer features
category_customer = [Customer.FN, Customer.ACTIVE, Customer.POSTAL_CODE,
                     Customer.CLUB_MEMBER_STATUS, Customer.FASHION_NEWS_FREQUENCY]
continuous_customer = [Customer.AGE]

# Article features
category_article = [Article.PRODUCT_CODE]
text_article = [Article.PROD_NAME]

# Transaction features
category_transaction = [Transaction.SALES_CHANNEL_ID]
continuous_transaction = [Transaction.PRICE]
datetime_transaction = [Transaction.T_DAT]

pt = PropertyTransformer(
    category=[*category_customer, *category_article, *category_transaction],
    continuous=[*continuous_customer, *continuous_transaction],
    datetime=[*datetime_transaction],
    text=[*text_article],
    time_col=[Transaction.T_DAT],
)
