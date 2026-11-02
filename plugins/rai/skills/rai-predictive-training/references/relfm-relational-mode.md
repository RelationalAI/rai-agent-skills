# RelFM (Relational Mode)

`RelFM` (`relationalai.semantics.reasoners.predictive.estimators.relational.relfm`)
is the graph/relational-aware sibling of flat-mode `RelFMTabular`. It's a
subclass of the same `PredictiveEstimator` base that `GNN` uses, reuses GNN's
`Graph`/`PropertyTransformer`/`validation` setup, but has **no `fit()`/`load()`
/`register_model()` step** — it's zero-shot in-context learning (ICL) using
Deep Feature Synthesis (DFS) over your relational graph instead of message
passing.

```python
from relationalai.semantics.reasoners.predictive import RelFM, PropertyTransformer
```

## Workflow

Single workflow, no fit/load split like GNN has:

```python
relfm = RelFM(graph=gnn_graph, property_transformer=pt,
              source_concept=Students,
              context=Train, validation=Validation,
              task_type="binary_classification",
              eval_metric="roc_auc")
Students.predictions = relfm.predictions(domain=Test)
```

`context` plays the role GNN's `train` plays — it's the labeled set of
examples used directly as in-context examples, not a training split that
produces a stored model.

## When to use relational RelFM vs. flat RelFM vs. GNN

See `references/relfm-flat-mode.md`'s comparison table for the full picture.
In short: use relational RelFM when the predictive signal comes from
multiple related tables (via real FK joins) but you don't want to pay for or
wait on GNN training — DFS pulls in cross-table features without any
learned weights. Use GNN instead when the task is link prediction,
multilabel classification, or when message-passing over the graph structure
is expected to outperform DFS feature engineering.

## Configuration

Key constructor parameters (`estimators/relational/relfm.py`):

- `database`, `schema` — output location for prediction tables.
- `graph` — a `Graph` with `Edge` relationships already defined, same as GNN.
- `property_transformer` — a `PropertyTransformer`; auto-inferred if omitted.
- `context` — labeled examples used as in-context examples (no training).
- `validation` — used by `.score()` when no explicit `domain=` is given.
- `source_concept` — the concept predictions are made about.
- `task_type` — **only** `"binary_classification"`, `"multiclass_classification"`,
  or `"regression"`. Link prediction and multilabel classification are **not
  supported** — that restriction is enforced through the same
  `validate_task(..., allowed_task_types=...)` machinery in
  `core/task_info.py` that flat mode also uses.
- `use_current_time` (default `True`) — time-window inclusivity for temporal tasks. `False` uses strict `<` (only data **before** the prediction date; realistic forecasting, no same-day leakage); `True` uses `<=` (includes the prediction date; what-if/simulation where same-day features are known). Set `False` for production forecasting or backtests, and set it explicitly rather than relying on the default. Full semantics: [hyperparameters.md](hyperparameters.md) § GNN constructor operational flags.
- `eval_metric`, `has_time_column`, `test_batch_size`,
  `stream_logs`, `dataset_alias`, `parallel_reasoners_init` — same
  conventions as GNN.
- `n_estimators`, `random_state` — ICL ensemble knobs.
- `dfs_max_depth` — how many hops across related tables DFS pulls features
  from; valid range **1–3**, default **2**. Increasing it widens the feature
  net across more joined tables at the cost of feature-generation time.
- `sample_size`, `sampling_strategy`, `device` — same as flat mode.
- `clamp_min`, `clamp_max`, `regression_output`, `quantile_levels`,
  `norm_methods` — same regression-shaping knobs as flat mode.

## Gotchas / restrictions

- **No cycles, including self-referential foreign keys.** The constructor calls
  `_reject_self_referential_fks`, which raises `ValueError` if the graph
  contains a real FK column pointing back at its own concept (e.g.
  `Edge.new(src=Employee, dst=Employee.manager)`). Reason, straight from
  `core/metamodel_analysis.py::self_referential_fks`: RelFM featurizes with
  Deep Feature Synthesis, which walks the FK graph depth-first with **no base
  case for revisiting a table** — DFS would recurse forever. The same failure
  applies to a cycle across several concepts (A → B → C → A). The constructor
  does **not** detect that case. Do not write the script: name the edges that
  close the cycle and ask which one to drop. GNN has no such restriction
  because message passing runs a fixed number of hops regardless of cycles.
  - Note the distinction in the same module: `Edge.new(src=Student,
    dst=Student)` (no join condition) is *not* flagged — it produces no
    self-referential column and is the only way to register a single-concept
    model in a `Graph` at all. Only edges with a real FK column back to the
    same concept trip this check.
- **No edge tables.** RelFM sets `_skip_edge_tables=True` when collecting
  table queries (`core/data.py::collect_relational_table_queries`,
  `skip_edges=True`) — it operates on real relational FK joins between node
  tables directly, not GNN's message-passing edge-table abstraction. Node-level
  foreign keys link via **natural key properties** (e.g. `studentid`)
  instead of internal hash identity columns — see `use_natural_keys=True`
  threaded through `task_info.py`/`data.py`/`preparation.py`.
- **Single natural-key source concept required.** Like flat mode's
  predictor, `source_concept` must have exactly one `identify_by` column
  (`natural_key_column()` returns `None` for composite identities and
  `validate_task` raises `ValueError` in that case) — RelFM joins on that
  concept's own natural key column, not a hash identity.
- **No text semantic type in RelFM v1.** Free-text columns (descriptions,
  titles, review bodies, search queries) must be `drop`ped in the
  `PropertyTransformer` rather than annotated `text=`, unlike GNN which does
  support `text`.
- **No `fit()`/`load()`/model registry.** There's no trained-model artifact
  to reuse across sessions — every `RelFM(...)` construction with a given
  `context` is a fresh zero-shot inference setup.

## Other methods

- `.score(domain)` — same convention as flat mode and GNN: evaluate against
  a labeled domain (defaults to `validation` if `domain` is omitted).
- `.display_dataset_diagram()` / `.save_dataset_diagram()` — Graphviz-based
  visualization of the schema RelFM derived from your `Graph` (nodes, FK
  edges, DFS depth) — useful for confirming DFS is walking the joins you
  expect, especially after hitting the self-referential-FK restriction.

## Output shape

Same shape as GNN's output: `.probs` / `.predicted_labels` for
classification, `.predicted_value` (or `quantile_<N>` columns when
`quantile_levels` is set) for regression.

## Minimal walkthrough

Distilled from a churn-prediction example over an H&M-style schema. The
modeling part (imports, concepts, Snowflake loading, task relationships, graph,
`PropertyTransformer`) is **identical to GNN** — see `rai-predictive-modeling`.
The only change is swapping `GNN(...)` for `RelFM(...)` (no `fit()`).

```python
from relationalai.semantics import Model, select, define, Integer, Any
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.predictive import RelFM, PropertyTransformer

model = Model("hm_churn")
# Table is model.Table (bound to this model) -- NOT importable from relationalai.semantics
Concept, Table, Relationship = model.Concept, model.Table, model.Relationship

# graph concepts
Customer    = Concept("Customer",    identify_by={"customer_id": Integer})
Article     = Concept("Article",     identify_by={"article_id": Integer})
Transaction = Concept("Transaction")   # no identify_by -- edge table

# task table concepts (no identify_by)
train_table_concept = Concept("TrainTable")
val_table_concept   = Concept("ValidationTable")
test_table_concept  = Concept("TestTable")

# populate from Snowflake
define(Customer.new(Table("DB.SCHEMA.CUSTOMERS").to_schema()))
define(Article.new(Table("DB.SCHEMA.ARTICLES").to_schema()))
define(Transaction.new(Table("DB.SCHEMA.TRANSACTIONS").to_schema()))
define(train_table_concept.new(Table("DB.TASKS.TRAIN").to_schema()))
define(val_table_concept.new(Table("DB.TASKS.VAL").to_schema()))
define(test_table_concept.new(Table("DB.TASKS.TEST").to_schema()))

# task relationships (same arity rules as GNN; test omits the label)
TrainRel = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
ValRel   = Relationship(f"{Customer} at {Any:timestamp} has {Any:churn}")
TestRel  = Relationship(f"{Customer} at {Any:timestamp}")
define(TrainRel(Customer, train_table_concept.timestamp, train_table_concept.churn)).where(
    Customer.customer_id == train_table_concept.customer_id)
define(ValRel(Customer, val_table_concept.timestamp, val_table_concept.churn)).where(
    Customer.customer_id == val_table_concept.customer_id)
define(TestRel(Customer, test_table_concept.timestamp)).where(
    Customer.customer_id == test_table_concept.customer_id)

# graph edges
gnn_graph = Graph(model, directed=True, weighted=False)
Edge = gnn_graph.Edge
define(Edge.new(src=Transaction, dst=Customer)).where(Transaction.customer_id == Customer.customer_id)
define(Edge.new(src=Transaction, dst=Article)).where(Transaction.article_id == Article.article_id)

# features (RelFM: free text must be dropped, not `text=`)
pt = PropertyTransformer(
    drop=[Customer.customer_id, Article.article_id,
          Transaction.customer_id, Transaction.article_id,
          Article.prod_name, Article.detail_desc],
    category=[Customer.club_member_status, Article.product_type_name, ...],
    continuous=[Customer.FN, Customer.age, Transaction.price, ...],
    datetime=[Transaction.t_dat],
    time_col=[Transaction.t_dat],
)

# the only GNN -> RelFM change: RelFM(...) instead of GNN(...), no fit()
relfm = RelFM(
    database="HM_CHURN", schema="EXPERIMENTS",
    graph=gnn_graph, property_transformer=pt,
    context=TrainRel, validation=ValRel,
    task_type="binary_classification", eval_metric="roc_auc",
    has_time_column=True, device="cpu",
    n_estimators=1, dfs_max_depth=2, sample_size=2000, sampling_strategy="random",
)

print(relfm.score())

Customer.predictions = relfm.predictions(domain=TestRel)
preds = select(
    Customer.customer_id, Customer.predictions.probs, Customer.predictions.predicted_labels,
).where(Customer.predictions).to_df()
```

The task `Relationship` template itself (`{Source} at {Any:ts} has {Any:label}`,
composite/target-concept variants, etc.) follows the exact same arity rules as
GNN's task relationships — see `rai-predictive-modeling`'s
`references/task-relationships.md`. A `DATE` or `TIMESTAMP*` column on the task
table makes the task temporal: use the `at {…}` clause and `has_time_column=True`.
