---
name: rai-predictive-modeling
description: Build graph neural network (GNN) models — concepts, Snowflake data loading, task relationships, graph edges, and PropertyTransformer features. Use for node classification, regression, and link prediction tasks; for training, predictions, and evaluation, see `rai-predictive-training`. Not for creating or scaffolding the task table itself (the labelled Snowflake table this step binds to) — see `rai-predictive-task-generation`.
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
- Building the predictive layer on an existing `rai-ontology` model

**When NOT to use:**
- Training, predictions, evaluation, model management -- see `rai-predictive-training`
- Graph algorithms (centrality, community detection) -- see `rai-graph-analysis`
- Zero-shot / no-training-step prediction with `RelFM` -- the `Graph`/`PropertyTransformer` setup below also feeds `RelFM` directly (see `rai-predictive-training` § RelFM); single-table `RelFMTabular` needs no graph at all, see `rai-predictive-training`'s `references/relfm-flat-mode.md`

**Overview:** 6 steps: imports -> concepts -> populate -> task relationships -> graph -> features. When an ontology already exists, steps 1-3 reuse its model and concepts (§ Starting from an Existing Ontology).

---

## Prerequisites

### Experiment schema setup (one-time, ACCOUNTADMIN)

GNN training writes experiment artifacts to a Snowflake schema. Create a database and schema you own, then grant the RELATIONALAI native app the four required privileges:

```sql
CREATE DATABASE IF NOT EXISTS <YOUR_DB>;
CREATE SCHEMA   IF NOT EXISTS <YOUR_DB>.<YOUR_SCHEMA>;

GRANT USAGE             ON DATABASE <YOUR_DB>                         TO APPLICATION RELATIONALAI;
GRANT USAGE             ON SCHEMA   <YOUR_DB>.<YOUR_SCHEMA>           TO APPLICATION RELATIONALAI;
GRANT CREATE EXPERIMENT ON SCHEMA   <YOUR_DB>.<YOUR_SCHEMA>           TO APPLICATION RELATIONALAI;
GRANT CREATE MODEL      ON SCHEMA   <YOUR_DB>.<YOUR_SCHEMA>           TO APPLICATION RELATIONALAI;
```

All four grants are required. Then pass the same database and schema to the GNN constructor:

```python
gnn = GNN(
    exp_database="<YOUR_DB>",
    exp_schema="<YOUR_SCHEMA>",
    # ... other args (graph=, property_transformer=, train=, validation=, task_type=)
)
```

### `relationalai` package version

The predictive submodule (`relationalai.semantics.reasoners.predictive`) is not in every published `relationalai` release — `from relationalai.semantics.reasoners.predictive import GNN` raises `ModuleNotFoundError` on releases that pre-date it. Pin a release that ships the submodule (or install from the development branch when iterating against unreleased changes).

The GNN runtime dependencies (PyTorch and the RAI GNN extensions) install as the `[gnn]` **extra**, added in 1.16.0. Declare it with an explicit floor — `relationalai[gnn]>=1.16.0` — rather than a bare `--upgrade`: the floor documents the minimum that carries the extra and keeps a resolver from settling on a release too old to provide it.

### Two-engine model: Logic + Predictive

A GNN workflow runs against **two distinct reasoner engines** that must both be `READY`:

| Reasoner | Handles | Why it matters here |
|----------|---------|---------------------|
| **Logic** | `model.data()` / `Table().to_schema()` ingest, all PyRel queries (including `select(...)` over `Source.predictions`), data exports back to Snowflake | The data pipeline that feeds the GNN and reads predictions back is Logic-engine work |
| **Predictive** | `gnn.fit()` training, `gnn.predictions()` inference, experiment + model-registry writes | Where the actual GNN training and inference happen |

When training "hangs" or queries are slow, the first question is *which engine* — they have separate sizes, separate `STATUS`, separate auto-suspend timers. `rai-health` § Predictive train jobs stuck QUEUED covers the Predictive side; the Logic-engine ladder lives in `rai-health` Steps 1–3.

### Provisioning the Predictive reasoner

**Use a GPU compute type for the Predictive reasoner.** The canonical provisioning shape:

```sql
CALL RELATIONALAI.API.CREATE_REASONER_ASYNC(
    'predictive',
    '<reasoner_name>',
    'GPU_NV_S',
    OBJECT_CONSTRUCT()        -- {} — accept all defaults; or pass auto_suspend_mins, settings, …
);

-- Poll until STATUS=READY (1–3 minutes typical):
CALL RELATIONALAI.API.GET_REASONER('predictive', '<reasoner_name>');
```

`GPU_NV_S` is faster per epoch on the GNN training job and is the recommended default for predictive workloads. `HIGHMEM_X64_S` / `_M` / `_L` are also valid sizes for the predictive reasoner, but GPU is the path the platform team recommends; pick it unless you have a specific reason not to.

The `rai reasoners:create --type Predictive --size GPU_NV_S` CLI form may report an allow-list error (`Allowed sizes: HIGHMEM_X64_S, HIGHMEM_X64_M, HIGHMEM_X64_L`) on older client versions — the validation list (`relationalai/services/reasoners/constants.py::REASONER_SIZES_AWS`) trails the backend's `AWSEngineSize` Literal in `config_reasoners_fields.py`. The SQL `CREATE_REASONER_ASYNC` call above is the canonical fall-through; both reach the same backend.

Confirm current sizing options with the RelationalAI team — pool capacity and recommendations evolve.

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
| No PK (e.g. task table) | `TrainTable = Concept("TrainTable")` |

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

> **User-input boundary:** the only things you need from the user are the 3 inputs in [`references/auto-discovery.md`](references/auto-discovery.md) -- the source schema (or tables), task table FQNs, and the experiment tracking database and schema. **If the user names specific source tables, use exactly those and follow the standard flow below.** That means no proposed source graph and no building on an existing ontology. Otherwise discovery proposes the source graph: tables one link from the predicted entity are selected, tables two links away are proposed, and each row carries a leakage note. The user confirms it in the summary table (§ Proposing the Source Graph in that file). When an ontology already exists, the graph is proposed from its links (§ Starting from an Existing Ontology). Auto-derive PKs, FKs, columns, types, edges, task type, and timestamp candidates from Snowflake schema introspection. Use the in-skill `get_table_schema(table_name, database, schema)` helper in `references/auto-discovery.md` as the default schema source before any manual SQL fallback. Don't ask the user for column-level details. The discovery summary names the connected database, the estimator (`RelFM` or `GNN`), and the task type without being asked.

Two concept categories show up in a GNN pipeline, distinguished by their role in the graph:

| Category | Role |
|----------|------|
| **Graph (node)** | Source, target, or other node entities the GNN reasons over -- can carry features and `time_col` |
| **Task table** | Holds train/val/test split rows, joined to a graph concept by FK -- not used in edges; not a feature source |

`identify_by` is not required by the GNN pipeline. Pass it when you want to declare an explicit primary key for a graph concept (matches a Snowflake column); omit it for task tables and for graph concepts where you don't need an explicit PK.

### Starting from an Existing Ontology

When an ontology built with `rai-ontology` exists for the source data, in this session or as a model module in the project, build on it unless the user named specific source tables. In that case use exactly those tables and the standard flow. Otherwise, do not create a new `Model`. The ontology already holds the tables, keys, types and links that a fresh model would have to rediscover, and a fresh model usually stops at the one or two tables the task key reaches, which leaves the graph with little signal. Load [references/existing-ontology.md](references/existing-ontology.md) for the full procedure and examples. In short:

1. Import the ontology's `model` and concepts into a separate predictive module, and declare everything else on that same `model`.
2. Map the task key to one node concept. Add a concept when the key is only an attribute, or when it spans several concepts that represent the same entity.
3. Propose the graph by walking the ontology's concept-to-concept links one or two hops from the node, with a leakage note per row, and have the user confirm it. When the node merges several concepts, walk from each of them too. Stay inside the ontology's scope and say so.
4. Define edges on scalar key properties, adding them where the ontology has only entity-typed links.
5. Select features as an allow-list: pass every graph concept in `drop=` and list the features to keep.

### Graph (node) Concepts

The `identify_by` key names must exist as columns in the Snowflake table. Column-name matching is **case-insensitive** in both `identify_by` keys and property accesses -- a Snowflake column `FOO_BAR` can be referenced as `Concept.foo_bar`, `Concept.FOO_BAR`, or any other casing. Spelling still has to match exactly. Check `INFORMATION_SCHEMA.COLUMNS` or run `DESCRIBE TABLE` to confirm the columns before writing `identify_by` or property accesses. Type each key from that column's `DATA_TYPE` (`NUMBER` scale 0 → `Integer`, other `NUMBER` / `FLOAT` → `Float`, `VARCHAR`/`TEXT` → `String`, `DATE` → `Date`, `TIMESTAMP*` → `DateTime`). Do not use `Any` for a concept key when the type is known. `Any` is only for a relationship slot whose type is genuinely unknown (`{Any:ts}`, `{Any:label}`).

```python
User = Concept("User", identify_by={"user_id": Integer})
Event = Concept("Event", identify_by={"event_id": Integer})
```

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

**Split to match the prediction question.** When the task is a forecast — predicting a future period from past data — build the splits **temporally**: train on the earliest periods, validate on the next, test on the most recent, so the model is always scored on a period it has not seen. A random shuffle-and-slice (e.g. 80/10/10 by row) puts the same time range in every split, leaking seasonal and period-level signal into training — the validation metric looks healthy but reflects interpolation within a seen period, and the model degrades on a genuinely future one. A random split is right only when rows are exchangeable (the question has no time dimension).

A `DATE` or `TIMESTAMP*` column on a task table (`DATE`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ`, `TIMESTAMP_TZ`, `DATETIME`) makes the task temporal. Treat it as temporal even when the rows are already split by time: relationships use `at {Type:<slot>}`, `PropertyTransformer` sets `time_col=` for that column, and the estimator is constructed with `has_time_column=True`. A `DATE` column counts; it does not need a time of day. `has_time_column` makes the relationship time-aware for the model and does **not** itself partition train/val/test — the split is still which rows sit in each task table.

`PropertyTransformer` and the task-table pattern also work with concepts populated from local data via `model.data(df)` -- not just `Table(...).to_schema()`. Useful when some concept data lives in local CSVs (e.g. optimizer parameters) while the graph comes from Snowflake.

---

## Task Relationships

Relationships encode the task structure using a template string with three parts:
- **Head** = source concept (the concept being predicted on)
- **"at" clause** = timestamp field (required when the task table has a `DATE` or `TIMESTAMP*` column; omit only when it has neither)
- **"has" clause** = label (classification/regression) or target concept (link prediction)

For per-task-type Relationship Arity Rules and full code examples, see [references/task-relationships.md](references/task-relationships.md).

---

## Graph and Edges

A GNN earns its added complexity only when the **graph carries signal** — when a node's outcome depends on its neighbors' features or labels propagating across edges. If each row's own columns already explain the target, or the only edges are same-entity temporal lags, a tabular model is simpler and usually as accurate. Before committing to a GNN, confirm the edges are load-bearing: heterogeneous connections across concept types, or relational structure a flat feature table couldn't capture (see Common Pitfalls).

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

### Reuse for RelFM (no training step)

Everything above -- `Graph`, `Edge` definitions, `PropertyTransformer` -- is consumed identically by relational `RelFM`, not just `GNN`. If the goal is zero-shot prediction rather than a trained model, skip `rai-predictive-training`'s `fit()` step entirely and construct `RelFM(graph=..., property_transformer=..., context=Train, validation=Validation, task_type=...)` directly -- see `rai-predictive-training`'s [references/relfm-relational-mode.md](../rai-predictive-training/references/relfm-relational-mode.md). Restrictions to flag before building the graph, if RelFM is the target: RelFM cannot use a self-referential foreign key, and it cannot use a cycle that runs through several concepts. DFS feature synthesis has no base case for revisiting a table. The constructor rejects the self-referential case only, so do not write a multi-concept cycle — name the edges that close it and ask which one to drop. RelFM also does not support the `text` `PropertyTransformer` type (drop free-text fields instead).

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

Status/enum codes used as `category` features must stay `String`-typed properties. A property typed by a `model.Enum` (relationalai>=1.12) is not usable as a feature — leave any property the `PropertyTransformer` consumes as a raw `String` (see `rai-pyrel` § Enums).

The `integer` parameter is a distinct type from `continuous` -- use it for whole-number counts or ordinal values where float precision is not meaningful (e.g. review counts, position ranks):

```python
pt = PropertyTransformer(
    integer=[Review.num_votes, Standing.position],
    continuous=[Review.rating, Result.points],
    # ... other feature lists
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
# Algorithm graph (often a different topology from the GNN graph)
algo_graph = Graph(model, directed=False)
define(algo_graph.Edge.new(src=Source, dst=SourceRef)).where(...)

# Bind metric output as a Concept property
Source.pagerank = model.Property(f"{Source} has {Float:pagerank}")
model.define(Source.pagerank(graph_algo_result))

# Include as a continuous (or category) feature
pt = PropertyTransformer(
    continuous=[Source.pagerank],
    # ... other feature lists
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
| Random shuffle-and-slice split on a forecasting task | Same time range lands in all three splits, leaking seasonal/future signal | Partition task tables temporally (earliest periods → train, latest → test); see § Define and Populate Concepts |
| Missing type import | e.g. using `Date` without importing it | Add missing types to the import line |
| Column name has spaces or special characters | Python identifier rules prevent `Concept.weight(kg)` | Use `getattr(People, "weight(kg)")` to reference the field |
| `identify_by` key or property access doesn't match Snowflake column name | Typo or wrong column — matching is case-insensitive, but the column name must exist | Check `INFORMATION_SCHEMA.COLUMNS` / run `DESCRIBE TABLE` for the exact spelling |
| Train/Val/Test Relationships have different schemas | Test omits the label but also changes concept or timestamp structure | Train, Val, and Test must share the same concept and timestamp structure — only the label/target is omitted in Test |
| Link prediction join key or target column is `VARIANT` in task table | Task table stores target IDs as an array instead of one row per pair | Run `DESCRIBE TABLE` on all three split tables before writing task relationships; see `references/task-relationships.md` § Link Prediction — Task Table Format Requirements (VARIANT check) for the joined-vs-non-joined branch and the `LATERAL FLATTEN` recipe |
| Graph topology is only same-entity temporal-lag edges (no heterogeneous edges across concept types) | The GNN's value is message-passing across different entity kinds; lag-only chains carry no signal beyond what shifted/lag features in a tabular model already capture | Add heterogeneous edges across concept types, or re-scope as time-series/tabular regression outside RAI (optionally loaded as `pre_computed` for downstream reasoners) |
| Source tables taken from the tables that built the task labels, when the user named none | Those tables usually hold only the predicted entity, so the graph has little signal beyond it | Propose the source graph from the links around the entity (hop 1 selected, hop 2 proposed) and confirm it with the user; see [references/auto-discovery.md](references/auto-discovery.md) § Proposing the Source Graph |
| New `Model` built while an ontology for the same data exists, when the user named no tables | Starting from the task key alone reaches only one or two tables, so the graph carries little signal | Import the ontology's `model` and propose the graph from its links; see [references/existing-ontology.md](references/existing-ontology.md) |
| `ValueError: ... The database does not seem to be connected` after a log line saying a column's dtype "cannot be inferred" | A link column that is mostly NULL gets no inferable type, so it is left out of the export and its table loses its only link to the graph | Build that concept from only the rows where the key is set, for example `model.define(C.new(id=t.id)).where(t.key != "")` for a string key |
| Leaky or irrelevant properties of an ontology concept become features | `PropertyTransformer` auto-infers every field it is not told about, and ontology concepts carry every mapped column, including post-outcome ones | Pass each graph concept in `drop=` (default for its unmentioned fields) and list only the chosen features |
| `model.data(df)` raises `KeyError: 0` | Type inference does a label-based lookup `df[col][0]`, which fails when the DataFrame index doesn't include 0 (typical after `df.iloc[N:M]` or `df.sample()` slicing for train/val/test splits) | Call `.reset_index(drop=True)` on every sliced split before `model.data()`: `m.data(val_df.reset_index(drop=True))` |

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
| Auto-discovery | Load at the start of a pipeline: question templates, SQL for PKs, links and task structure, proposing the source graph (hops, leakage notes) and the summary table | [references/auto-discovery.md](references/auto-discovery.md) |
| Existing ontology | Load when a `rai-ontology` model exists for the source data: reuse it, map the task key, propose the graph from its links, scalar-key edges, allow-list features | [references/existing-ontology.md](references/existing-ontology.md) |
