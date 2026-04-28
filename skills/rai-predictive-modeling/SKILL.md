---
name: rai-predictive-modeling
description: Build GNN data models -- concepts, Snowflake data loading, task relationships, graph edges, and PropertyTransformer features. Use when defining entity types, loading data, or configuring graph structure for a predictive GNN pipeline.
---

# Predictive Modeling
<!-- v1-SENSITIVE -->

> **Early access.** The RAI predictive reasoner (GNN) is in early access — APIs, engine requirements, and behavior may change. Confirm the latest surface with the RelationalAI team before production use.

## Summary

**What:** Data modeling workflow for GNN pipelines -- from imports through graph construction and feature configuration.

**When to use:**
- Defining concepts and loading data from Snowflake
- Building graph structure (edges, self-references)
- Configuring task relationships (train/val/test splits)
- Setting up PropertyTransformer features

**When NOT to use:**
- Training, predictions, evaluation, model management -- see `rai-predictive-training`
- Graph algorithms (centrality, community detection) -- see `rai-graph-analysis`

**Overview:** 6 steps: imports -> concepts -> populate -> task relationships -> graph -> features

---

## Quick Reference

```python
# Imports
from relationalai.semantics import Model, select, define, Integer, String, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

model = Model("<model_name>")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship
```

| Pattern | Code |
|---------|------|
| Single PK | `User = Concept("User", identify_by={"user_id": Integer})` |
| Composite PK | `Class = Concept("Class", identify_by={"courseid": Integer, "year": Integer})` |
| No PK (task table) | `TrainTable = Concept("TrainTable")` |

```python
# Graph init
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge

# PropertyTransformer
pt = PropertyTransformer(
    category=[User.locale, User.gender],
    continuous=[User.birthyear],
    datetime=[User.joinedAt, Event.start_time],
    time_col=[Event.start_time],
)
```

---

## Imports and Model Setup

```python
from relationalai.semantics import Model, select, define, Integer, String, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import PropertyTransformer

model = Model("<model_name>")
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship
```

Additional type imports as needed: `Date`, `DateTime`, `Float`.

---

## Define and Populate Concepts

> **User-input boundary:** the only things you need from the user are the 3 inputs in [`references/auto-discovery.md`](references/auto-discovery.md) -- source table FQNs, task table FQNs, and the experiment-artifact location. Auto-derive PKs, FKs, columns, types, edges, task type, and timestamp candidates from `INFORMATION_SCHEMA` / `DESCRIBE TABLE`. Don't ask the user for column-level details.

Three concept categories show up in a GNN pipeline, distinguished by whether they declare a primary key and how they participate in the graph:

| Category | `identify_by`? | Role | Constraints |
|----------|---------------|------|-------------|
| **Graph (node)** | yes | Source, target, or other node entities the GNN reasons over | Can carry features and `time_col` |
| **Edge-intermediary** | no | Used only as `src=`/`dst=` in `Edge.new(...)` to express many-to-many or attributed relationships | **Cannot carry `time_col`** -- `time_col` only propagates for node concepts (with `identify_by`); see `rai-predictive-training` § Known Limitations |
| **Task table** | no | Holds train/val/test split rows, joined to a graph concept by FK | Not used in edges; not a feature source |

> If you have an existing ontology from `rai-build-starter-ontology`, create a new `Model` for the GNN pipeline -- concepts need `identify_by` for GNN to resolve primary keys.

### Graph (node) Concepts

The `identify_by` key names must exist as columns in the Snowflake table. Column-name matching is **case-insensitive** in both `identify_by` keys and property accesses -- a Snowflake column `FOO_BAR` can be referenced as `Concept.foo_bar`, `Concept.FOO_BAR`, or any other casing. Spelling still has to match exactly. Check `INFORMATION_SCHEMA.COLUMNS` or run `DESCRIBE TABLE` to confirm the columns before writing `identify_by` or property accesses.

```python
User = Concept("User", identify_by={"user_id": Integer})
Event = Concept("Event", identify_by={"event_id": Integer})
```

### Edge-intermediary Concepts

When a many-to-many or attributed relationship is best modeled as its own concept (e.g. `Interaction` between `User` and `Item`), and that concept's row identity isn't needed downstream, you can omit `identify_by`:

```python
EventAttendee = Concept("EventAttendee")  # used only in Edge.new(src=..., dst=...)
```

If the intermediary needs to carry the temporal column for `has_time_column=True`, give it an `identify_by` (promoting it to a graph node concept). `time_col` does not propagate from edge-intermediary concepts.

### Task Table Concepts

Task table concepts have no `identify_by`:

```python
train_table_concept = Concept("TrainTable")
val_table_concept = Concept("ValidationTable")
test_table_concept = Concept("TestTable")
```

### Populate from Snowflake

```python
define(Customer.new(Table("DB.SCHEMA.CUSTOMERS").to_schema()))
define(train_table_concept.new(Table("DB.TASKS.TRAIN").to_schema()))
```

The GNN pipeline expects pre-existing train/val/test split tables in Snowflake. Each split table must contain: a join key column matching a source concept PK, a label/target column (train/val only), and optionally a timestamp column.

`PropertyTransformer` and the task-table pattern also work with concepts populated from local data via `model.data(df)` -- not just `Table(...).to_schema()`. Useful when some concept data lives in local CSVs (e.g. optimizer parameters) while the graph comes from Snowflake.

**Timestamp column types for the GNN datetime pipeline.** Columns intended for `time_col` / `datetime` features should match a format the trainer accepts; if you're not sure what's currently supported, ask the RelationalAI team.

> **Do schema changes (any column type, not just timestamps) before the first `Model(...)` bind**, not after — `ALTER`-ing a column type on an already-bound table can leave a stale compiled-relation signature on the engine that survives stream delete + recreate. See `rai-predictive-training` § Known Limitations for the symptom, the diagnostic path, and the workaround.

**Avoid `timestamp[ns]` parquet payloads when bulk-loading via `COPY INTO TIMESTAMP_NTZ`.** Snowflake interprets the integer payload as `timestamp[us]`, multiplying every value by 1000 — pandas' default `datetime64[ns]` -> parquet round-trip silently lands timestamps tens of millions of years in the future. Two safe options: write the timestamp column as ISO-8601 strings into parquet, or load the underlying integer time index (e.g. an hour offset) and rebuild server-side via `DATEADD(HOUR, <offset_col>, '<epoch>'::TIMESTAMP_NTZ)` after `COPY INTO`.

---

## Task Relationships

Relationships encode the task structure using a template string with three parts:
- **Head** = source concept (the concept being predicted on)
- **"at" clause** = optional timestamp field
- **"has" clause** = label (classification/regression) or target concept (link prediction)

### Relationship Arity Rules

| Task Type | Train/Val template | Test template |
|-----------|-------------------|---------------|
| classification (no time) | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| classification (with time) | `f"{Source} at {Any:ts} has {Any:label}"` | `f"{Source} at {Any:ts}"` |
| regression (no time) | `f"{Source} has {Any:value}"` | `f"{Source}"` |
| regression (with time) | `f"{Source} at {Any:ts} has {Any:value}"` | `f"{Source} at {Any:ts}"` |
| link_prediction | `f"{Source} has {Target}"` | `f"{Source}"` |
| repeated_link_prediction | `f"{Source} at {Any:ts} has {Target}"` | `f"{Source} at {Any:ts}"` |

For full code examples of all task type patterns, see [references/task-relationships.md](references/task-relationships.md).

---

## Graph and Edges

```python
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
```

### Standard Edges (FK field equality)

```python
define(Edge.new(src=Interaction, dst=User)).where(
    Interaction.user_id == User.user_id)
```

### Self-Referential Edges (use `.ref()`)

```python
PostRef = Post.ref()
define(Edge.new(src=Post, dst=PostRef)).where(
    PostRef.parent_id == Post.id)
```

### Mediated Self-Reference

```python
PeopleRef = People.ref()
define(Edge.new(src=People, dst=PeopleRef)).where(
    People.Id == Related.person1,
    PeopleRef.Id == Related.person2,
)
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

The `PropertyTransformer` annotates concept fields with their semantic types for the GNN.

```python
pt = PropertyTransformer(
    category=[User.locale, User.gender, Event.city, Event.state, Event.country],
    datetime=[User.joinedAt, Event.start_time],
    continuous=[User.birthyear],
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
| Explicit integer values (not IDs) | `integer` |

The `integer` parameter is a distinct type from `continuous` -- use it for whole-number counts or ordinal values where float precision is not meaningful (e.g. review counts, position ranks):

```python
pt = PropertyTransformer(
    integer=[Review.num_votes, Standing.position],
    continuous=[Review.rating, Result.points],
    ...
)
```

### Feature Selection Strategy

- **Drop all PKs and FKs.** Graph structure already captures relationships; IDs add noise. Example: `drop=[Study.nct_id, Outcome.id, Outcome.nct_id, ...]`
- **Start with minimal `text` fields.** Text embedding is expensive and too many text fields dilute signal. Begin with 3-5 key text fields, add more only if metrics improve.
- **Use `category` for discrete location/status fields.** Fields like city, state, country have limited cardinality.
- **Use `continuous` for numeric measurements.** Counts, scores, percentages.
- **Lean feature sets beat everything-in.** In practice, reducing ~30 text fields to 5 improved AUROC from 57% to 68%.

### Graph metrics as features

Centrality, community labels, and other graph-algorithm outputs from `rai-graph-analysis` can feed the GNN as features once they're materialized as concept properties. Compute the metric on a separate Graph instance (the algorithm graph -- often a different topology from the GNN graph), bind the result, then include in the PropertyTransformer:

```python
# Algorithm graph (e.g. node-to-node, distinct from the GNN's bipartite/edge-intermediary graph)
algo_graph = Graph(model, directed=False)
define(algo_graph.Edge.new(src=Source, dst=SourceRef)).where(...)

# Bind metric output as a Concept property
Source.pagerank = model.Property(f"{Source} has {Float:pagerank}")
model.define(Source.pagerank(graph_algo_result))

# Include as a continuous (or category) feature
pt = PropertyTransformer(
    continuous=[Source.pagerank, ...],
    ...
)
```

Two-graph setups are common (the GNN graph and the algorithm graph have different shapes); name them distinctly to avoid confusion.

PropertyTransformer is optional -- omitting it auto-infers all field types. For production, explicit annotation is recommended. Use `drop` to exclude fields or entire concepts: `drop=[Interaction, Item.internal_code]`.

For the full feature type reference including drop patterns, see [references/property-transformer-types.md](references/property-transformer-types.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Concept name is plural (e.g. "Customers") | Naming convention | Use singular names: `Concept("Customer")` |
| Task table concept has `identify_by` | Task tables don't need primary keys | Use plain `Concept("TrainTable")` with no `identify_by` |
| Snowflake table name not fully qualified | Missing database or schema prefix | Use `"DATABASE.SCHEMA.TABLE"` format |
| Test Relationship includes label/target | Test data should not contain the answer | Omit the "has" clause: `f"{Source}"` or `f"{Source} at {Any:ts}"` |
| Positional args in `define(Train(...))` don't match template | Template and population call must align | Match the order: source, [timestamp], [label/target] |
| Self-referential edge without `.ref()` | Same concept on both sides creates ambiguity | Use `PostRef = Post.ref()` for the destination |
| `time_col` fields not in `datetime` list | Both lists must include the field | Add time columns to both `datetime=[...]` and `time_col=[...]` |
| Task table concept used in edge definition | Only graph concepts participate in edges | Edges connect domain entities, not task tables |
| Missing type import | e.g. using `Date` without importing it | Add missing types to the import line |
| Column name has spaces or special characters | Python identifier rules prevent `Concept.weight(kg)` | Use `getattr(People, "weight(kg)")` to reference the field |
| `identify_by` key or property access doesn't match Snowflake column name | Typo or wrong column — matching is case-insensitive, but the column name must exist | Check `INFORMATION_SCHEMA.COLUMNS` / run `DESCRIBE TABLE` for the exact spelling |
| Train/Val/Test Relationships have different schemas | Test omits the label but also changes concept or timestamp structure | Train, Val, and Test must share the same concept and timestamp structure — only the label/target is omitted in Test |
| Link prediction join key or target column is `VARIANT` in task table | Task table stores target IDs as an array instead of one row per pair | Run `DESCRIBE TABLE` on all three split tables before writing task relationships; see `references/task-relationships.md` § Link Prediction — Task Table Format Requirements (VARIANT check) for the joined-vs-non-joined branch and the `LATERAL FLATTEN` recipe |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Node classification | Binary classification data model | [examples/node_classification_snowflake.py](examples/node_classification_snowflake.py) |
| Link prediction | Repeated link prediction data model | [examples/link_prediction_snowflake.py](examples/link_prediction_snowflake.py) |
| Regression | Regression-with-time data model | [examples/regression_snowflake.py](examples/regression_snowflake.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Task relationships | Relationship template patterns for all task types with code examples | [references/task-relationships.md](references/task-relationships.md) |
| PropertyTransformer types | Full feature type reference, drop patterns, and guidelines | [references/property-transformer-types.md](references/property-transformer-types.md) |
| Auto-discovery | SQL templates for discovering PKs, FKs, edges, and task structure | [references/auto-discovery.md](references/auto-discovery.md) |
