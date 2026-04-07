---
name: rai-predictive-modeling
description: Build GNN data models — concepts, Snowflake data loading, task relationships, graph edges, and PropertyTransformer features.
---

# Predictive Modeling
<!-- v1-SENSITIVE -->

## Summary

**What:** Encodes the data modeling workflow for GNN pipelines — from imports through graph construction and feature configuration.

**When to use:**
- Defining domain concepts (entity types) and their primary keys
- Loading data from Snowflake tables into concepts
- Setting up train/validation/test task relationships
- Building a graph with edges between concepts
- Configuring PropertyTransformer feature annotations

**When NOT to use:**
- Training a GNN model or generating predictions — see `rai-predictive-training`
- Registering or loading saved models — see `rai-predictive-management`
- Running graph algorithms (centrality, community, etc.) — see `rai-graph-analysis`

**Overview:**
1. Imports and Model setup
2. Define concepts (graph entities + task tables)
3. Populate concepts from Snowflake
4. Define task relationships (train/val/test splits)
5. Build graph and define edges
6. Configure PropertyTransformer (optional)

---

## Quick Reference

**Imports:**
```python
from relationalai.semantics import Model, select, define, Integer, String, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
```

Additional type imports as needed: `Date`, `DateTime`, `Float`.

**Model setup:**
```python
model = Model("<model_name>")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship
```

**Concept patterns:**

| Pattern | Code |
|---------|------|
| Single PK | `User = Concept("User", identify_by={"user_id": Integer})` |
| Composite PK | `Class = Concept("Class", identify_by={"courseid": Integer, "year": Integer})` |
| No PK | `Transaction = Concept("Transaction")` |
| Task table | `train_table_concept = Concept("TrainTable")` |

**Relationship arity rules:**

| Task Type | Train/Val template | Test template |
|-----------|-------------------|---------------|
| classification (no time) | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| classification (with time) | `f"{Source} at {Any:ts} has {Any:label}"` | `f"{Source} at {Any:ts}"` |
| regression (no time) | `f"{Source} has {Any:value}"` | `f"{Source}"` |
| regression (with time) | `f"{Source} at {Any:ts} has {Any:value}"` | `f"{Source} at {Any:ts}"` |
| link_prediction | `f"{Source} has {Target}"` | `f"{Source}"` |
| repeated_link_prediction | `f"{Source} at {Any:ts} has {Target}"` | `f"{Source} at {Any:ts}"` |

**Graph init:**
```python
gnn_graph = Graph(model, directed=True, weighted=False, aggregator="sum")
Edge = gnn_graph.Edge
```

---

## Imports and Model Setup

Every GNN pipeline starts with these imports:

```python
from relationalai.semantics import Model, select, define, Integer, String, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import GNN, PropertyTransformer
```

Add type imports based on your concept primary keys and data:
- `Integer` — integer primary keys
- `String` — string primary keys
- `Any` — flexible types in Relationship templates
- `Date`, `DateTime` — temporal fields
- `Float` — float values

Unpack the DSL primitives from the Model:

```python
model = Model("<model_name>")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship
```

---

## Define and Populate Concepts

### Graph Concepts

Graph concepts represent domain entities. Define with `identify_by` for primary keys:

```python
Customer = Concept("Customer", identify_by={"customer_id": Integer})
Article = Concept("Article", identify_by={"article_id": Integer})
Transaction = Concept("Transaction")  # no PK — identity from data source
```

Populate from Snowflake using fully qualified table names:

```python
define(Customer.new(Table("DB.SCHEMA.CUSTOMERS").to_schema()))
define(Article.new(Table("DB.SCHEMA.ARTICLES").to_schema()))
define(Transaction.new(Table("DB.SCHEMA.TRANSACTIONS").to_schema()))
```

### Task Table Concepts

Task table concepts hold train/validation/test split data. They have no `identify_by`:

```python
train_table_concept = Concept("TrainTable")
val_table_concept = Concept("ValidationTable")
test_table_concept = Concept("TestTable")

define(train_table_concept.new(Table("DB.SCHEMA.TRAIN").to_schema()))
define(val_table_concept.new(Table("DB.SCHEMA.VAL").to_schema()))
define(test_table_concept.new(Table("DB.SCHEMA.TEST").to_schema()))
```

---

## Task Relationships

Relationships encode the task structure using a template string. The template has three parts:
- **Head** = source concept (the concept being predicted on)
- **"at" clause** = optional timestamp field
- **"has" clause** = label (classification/regression) or target concept (link prediction)

### Node Classification (with time)

```python
Train = Relationship(f"{User} at {Any:timestamp} has {Any:target}")
define(Train(User, train_table_concept.timestamp, train_table_concept.target)).where(
    User.user_id == train_table_concept.user
)

Val = Relationship(f"{User} at {Any:timestamp} has {Any:target}")
define(Val(User, val_table_concept.timestamp, val_table_concept.target)).where(
    User.user_id == val_table_concept.user
)

Test = Relationship(f"{User} at {Any:timestamp}")
define(Test(User, test_table_concept.timestamp)).where(
    User.user_id == test_table_concept.user
)
```

### Node Classification (no time)

```python
Train = Relationship(f"{User} has {Any:target}")
Val = Relationship(f"{User} has {Any:target}")
Test = Relationship(f"{User}")
```

### Node Regression (with time)

```python
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
```

> **Link prediction has two task types — do not choose for the user.**
> `link_prediction` (static, no timestamps) and `repeated_link_prediction` (temporal, with timestamps) serve different data shapes. The correct choice depends on whether the user's data has temporal ordering. Present both options and ask the user which applies to their data.

### Link Prediction (with time / repeated_link_prediction)

```python
Train = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
define(Train(Customer, train_table_concept.timestamp, Article)).where(
    Customer.customer_id == train_table_concept.customer_id,
    Article.article_id == train_table_concept.article_id,
)

Val = Relationship(f"{Customer} at {Any:timestamp} has {Article}")
define(Val(Customer, val_table_concept.timestamp, Article)).where(
    Customer.customer_id == val_table_concept.customer_id,
    Article.article_id == val_table_concept.article_id,
)

Test = Relationship(f"{Customer} at {Any:timestamp}")
define(Test(Customer, test_table_concept.timestamp)).where(
    Customer.customer_id == test_table_concept.customer_id,
)
```

### Link Prediction (no time)

```python
Train = Relationship(f"{Customer} has {Article}")
Val = Relationship(f"{Customer} has {Article}")
Test = Relationship(f"{Customer}")
```

---

## Graph and Edges

Create the graph with standard defaults and define edges via field equality:

```python
gnn_graph = Graph(model, directed=True, weighted=False, aggregator="sum")
Edge = gnn_graph.Edge

define(Edge.new(src=Transaction, dst=Customer)).where(
    Transaction.customer_id == Customer.customer_id)
define(Edge.new(src=Transaction, dst=Article)).where(
    Transaction.article_id == Article.article_id)
```

### Self-Referential Edges

When both sides of an edge are the same concept, use `.ref()`:

```python
PostRef = Post.ref()
define(Edge.new(src=Post, dst=PostRef)).where(
    PostRef.parent_id == Post.id)
```

### Multiple Typed Edges Between Same Pair

```python
BB1Edge = Concept("BB1Edge", extends=[Edge])
BB2Edge = Concept("BB2Edge", extends=[Edge])

Bref = B.ref()
define(BB1Edge.new(src=B, dst=Bref)).where(B.field1 == Bref.id)
define(BB2Edge.new(src=B, dst=Bref)).where(B.field2 == Bref.id)
```

---

## Feature Configuration

`PropertyTransformer` annotates concept fields with their semantic types. Organize fields by concept, then combine:

```python
# User features
category_user = [User.locale, User.gender]
datetime_user = [User.joinedAt]
continuous_user = [User.birthyear]

# Event features
category_event = [Event.city, Event.state, Event.country]
datetime_event = [Event.start_time]

pt = PropertyTransformer(
    category=[*category_user, *category_event],
    datetime=[*datetime_user, *datetime_event],
    continuous=[*continuous_user],
    time_col=[Event.start_time],
)
```

### Feature Type Guidelines

| Data type | Annotation |
|-----------|-----------|
| Boolean flags, enum/status codes | `category` |
| Ages, prices, ratings | `continuous` |
| Free-form text, names, descriptions | `text` |
| Dates, timestamps | `datetime` |

PropertyTransformer is optional — omitting it auto-infers all field types. For production, explicit annotation is recommended. Use `drop` to exclude fields or entire concepts: `drop=[Customer, Article.COLOUR_GROUP_CODE]`.

For the full feature type reference including drop patterns, see [references/property-transformer-types.md](references/property-transformer-types.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Concept name is plural (e.g. "Customers") | Naming convention — inconsistent concept references | Use singular names: `Concept("Customer")` |
| Task table concept has `identify_by` | Task tables don't need primary keys — causes unexpected join behavior | Use plain `Concept("TrainTable")` with no `identify_by` |
| Snowflake table name not fully qualified | Missing database or schema prefix — `TableNotFoundError` | Use `"DATABASE.SCHEMA.TABLE"` format |
| Test Relationship includes label/target | Test data should not contain the answer — data leakage, meaningless results | Omit the "has" clause: `f"{Source}"` or `f"{Source} at {Any:ts}"` |
| Positional args in `define(Train(...))` don't match template | Template and population call must align — runtime error or silent wrong column binding | Match the order: source, [timestamp], [label/target] |
| Self-referential edge without `.ref()` | Same concept on both sides creates ambiguity — runtime error | Use `PostRef = Post.ref()` for the destination |
| `time_col` fields not in `datetime` list | Both lists must include the field — time column not encoded as temporal feature | Add time columns to both `datetime=[...]` and `time_col=[...]` |
| Task table concept used in edge definition | Only graph concepts participate in edges — invalid graph structure | Edges connect domain entities, not task tables |
| Missing type import | e.g. using `Date` without importing it — `NameError` | Add missing types to the import line |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Node classification | Binary classification with temporal features (User/Event/EventAttendee) | [examples/node_classification_snowflake.py](examples/node_classification_snowflake.py) |
| Node regression | Regression predicting article sales on H&M data (Customer/Article/Transaction) | [examples/node_regression_snowflake.py](examples/node_regression_snowflake.py) |
| Link prediction | Repeated link prediction on H&M data (Customer/Article/Transaction) | [examples/link_prediction_snowflake.py](examples/link_prediction_snowflake.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| PropertyTransformer types | Full feature type reference, drop patterns, and guidelines | [references/property-transformer-types.md](references/property-transformer-types.md) |
