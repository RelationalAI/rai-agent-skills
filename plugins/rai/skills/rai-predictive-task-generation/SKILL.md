---
name: rai-predictive-task-generation
description: Build prediction task tables for predictive-modeling frameworks (e.g. GNN) that ingest Snowflake tables. Use this skill whenever the user wants to create, scaffold, or modify a task table for any of the six supported tasks — binary classification, multilabel classification, multiclass classification, regression, link prediction, or repeated link prediction. Trigger on phrases like "build a task table", "set up a prediction task", "label table", "training table for the GNN", "churn prediction task", "link prediction labels", and on any mention of task tables alongside Snowflake. Also trigger when the user has source tables and wants help defining a prediction problem against them, even if they don't yet know which of the six task types fits. Supports both a guided, step-by-step interview and a low-question one-shot mode — this skill asks which one up front. Not for building the graph/model from an existing task table — see `rai-predictive-modeling` — or for training/predictions/evaluation — see `rai-predictive-training`.
---

# RAI Predictive Task Table Generator

<!-- v1-SENSITIVE -->

## Summary

**What**: Produces a prediction task table for a predictive-modeling framework (e.g. GNN) — a Snowflake SQL script that materializes a single labelled table conforming to the schema contract for one of six task types: binary, multiclass, and multilabel classification, regression, link prediction, and repeated link prediction.

**When to use**: whenever the user wants to create, scaffold, or modify a task table for any of the six task types — "build a task table", "set up a prediction task", "churn prediction task", "link prediction labels" — or has source tables and a prediction goal but doesn't yet know which task type fits.

**When NOT to use**:
- Building the model's graph/data model from the task table once it exists in Snowflake — that's `rai-predictive-modeling`.
- Training the model, generating predictions, or evaluating results — that's `rai-predictive-training`.
- Constructing features — the framework builds those downstream from the task table; this skill only produces the labelled rows and join key.

**Overview**: this skill has two sub-skills sharing everything below plus the reference files in `references/`:

| Sub-skill | When | Entry point |
|---|---|---|
| `guided` | User wants to confirm each decision (table roles, task type, configuration) before any SQL is generated | [references/GUIDED.md](references/GUIDED.md) |
| `one-shot` | User wants the table built quickly with minimal back-and-forth; requires a live Snowflake connection | [references/ONE_SHOT.md](references/ONE_SHOT.md) |

This top-level `SKILL.md` asks which mode to use, then hands off to the matching sub-skill for the rest of the session.

## Choose a workflow mode

Before anything else — whether the invocation is bare or already includes a data/task description — send this as its own standalone message. Nothing else goes in this message: no greeting, no data request, no SQL.

---

**Predictive Task Table Builder**

Before we start, how would you like to work through this?

1. **Guided** — you'll walk through each decision step by step, making the calls on table roles, task type, and configuration, adjusting anything you want before I generate any SQL.
2. **One-shot** — I'll infer as much as I can myself from your data and description, and show you one consolidated summary at the end instead of confirming each step. Requires a live Snowflake connection (via `raiconfig.yaml`).

---

**If the opening message already states an explicit mode preference** — words like "one-shot", "quickly", "just build it", "low-touch", "don't ask me a bunch of questions" (→ One-shot), or "guided", "step by step", "walk me through it", "ask me along the way" (→ Guided) — skip this message entirely, state the inferred mode back in one sentence, and proceed directly to routing below.

**Otherwise**, send the message above and wait for the reply before doing anything else — including handing off to either sub-skill.

Once the mode is settled, hand off to the matching sub-skill for the rest of the session, carrying forward whatever data/task description has already been given:

- **Guided**: hand off to [references/GUIDED.md](references/GUIDED.md) — follow its "On bare invocation" section (show its greeting if no data/task description has been given yet, otherwise skip straight to its Step 1 using the description already given).
- **One-shot**: hand off to [references/ONE_SHOT.md](references/ONE_SHOT.md) — follow its Step 0 onward, showing its own bare-invocation greeting only if no data/task description has been given yet.
- **Mind changed mid-flow**: if the user asks to switch modes partway through, switch to the other sub-skill's workflow at the nearest equivalent step rather than restarting from scratch — carry over whatever table roles, schema, task type, or configuration have already been established.

## Quick reference: the six task types at a glance

Use this only as a memory aid. The `task_*.md` reference files in `references/` are the source of truth.

- **Binary** — one row per entity per cutoff, label is 0/1
- **Multiclass** — one row per entity per cutoff, label is the raw class value (no re-encoding)
- **Multilabel** — multiple rows per entity per cutoff (one per active label), or a single row with an array column
- **Regression** — one row per entity per cutoff, target is a real number
- **Link prediction** — one row per (src, cutoff), target is a LIST of dst PKs interacted with in the window (first-time or repeat); framework samples negatives internally
- **Repeated link prediction** — same list format as link prediction, but dst candidate pool restricted to pairs with prior history as of cutoff

## Downstream column naming contract

The downstream `rai-predictive-modeling` step binds the task table to a source concept via a `Relationship` template. The column names in the task table must match what that template expects — no renaming is possible after the fact. Both sub-skills follow these conventions:

| Task type | Required column name | Type | Used in relationship template |
|---|---|---|---|
| Binary / Multiclass / Multilabel | `label` | `INTEGER` or `VARCHAR` | `f"{Source} has {Any:label}"` |
| Regression | `value` | `FLOAT` | `f"{Source} has {Any:value}"` |
| Link / Repeated link prediction | FK matching the target concept's PK (e.g., `product_id`) | `ARRAY` | `f"{Source} has {Target}"` — column is a list of positive dst PKs; framework samples negatives internally |
| Temporal tasks only (STAGING only) | `cutoff_<table>_<source_time_col>` (e.g. `cutoff_orders_order_ts`, `cutoff_transactions_t_dat`) | matches the source event-time column's type (`DATE`, `TIMESTAMP_NTZ`, etc.) — never cast or normalize it | The evaluation timestamp — used internally for split assignment and label window definition. **Present in STAGING only. Exclude it (along with `split`) when creating the final TRAIN/VAL/TEST tables.** Name it by prepending `cutoff_` to `<table>_<source_time_col>`. **Omit entirely for non-temporal tasks. Never invent a synthetic timestamp as a substitute.** |
| Temporal tasks only | `<table>_<source_time_col>` (e.g. `orders_order_ts`, `transactions_t_dat`) | same type as `cutoff_<table>_<source_time_col>` above — both come from the same source column | The model's temporal anchor — the column passed via `has_time_column=True` (add `at {Any:ts}` to the relationship template; `ts` there is a PyRel-side slot alias, not a literal column name). Named by prepending the source table name to the source event time column. Equals `cutoff_<table>_<source_time_col>` in most tasks. Present in both STAGING and final split tables. |

The entity join key column (e.g., `customer_id`) must exactly match the source concept's primary key column name — this is the `.where(Source.pk == TaskTable.fk)` join in the modeling step.

If the source data uses a different name for the label (e.g., `churned`, `revenue`), alias it to `label` / `value` in the INSERT SELECT — do not pass the raw name through.

## What comes next: predictive modeling and training

The task table is the entry point to a two-step downstream pipeline. Once the table exists in Snowflake, use these two skills in order. Both also rely on a working Snowflake connection — see `rai-setup` if one isn't configured yet.

### Step A — `rai-predictive-modeling`: build the data model

The task table is wrapped as a **taskless concept** (no primary key) and connected to the source entity concept via a `Relationship`. This step also defines graph edges between source concepts and configures the `PropertyTransformer` (feature column types).

```python
# Wrap each split table as a separate taskless concept
TrainTable = Concept("TrainTable")
ValTable   = Concept("ValTable")
TestTable  = Concept("TestTable")

define(TrainTable.new(Table("DB.CHURN_TASK.TRAIN").to_schema()))
define(ValTable.new(  Table("DB.CHURN_TASK.VAL").to_schema()))
define(TestTable.new( Table("DB.CHURN_TASK.TEST").to_schema()))

# Bind each to the source concept on the shared join key
Train      = Relationship(f"{Customer} has {Any:label}")
Validation = Relationship(f"{Customer} has {Any:label}")

define(Train(Customer,      TrainTable.label)).where(Customer.customer_id == TrainTable.customer_id)
define(Validation(Customer, ValTable.label)).where(  Customer.customer_id == ValTable.customer_id)
```

Use the **`rai-predictive-modeling`** skill when you reach this step.

### Step B — `rai-predictive-training`: train the GNN and generate predictions

The GNN is instantiated with the graph, property transformer, train/val relationships, task type, and eval metric, then fitted:

```python
gnn = GNN(
    exp_database="MY_DB",
    exp_schema="MY_SCHEMA",
    graph=gnn_graph,
    property_transformer=pt,
    train=Train,
    validation=Validation,
    task_type="binary_classification",
    eval_metric="roc_auc",
)
gnn.fit()
Customer.predictions = gnn.predictions(domain=TestTable)
```

Use the **`rai-predictive-training`** skill when you reach this step.

### Task type → downstream configuration at a glance

| Task type | Relationship template | GNN `task_type` value | Default `eval_metric` | Prediction attributes |
|---|---|---|---|---|
| Binary classification | `f"{Source} has {Any:label}"` | `"binary_classification"` | `roc_auc` | `.probs`, `.predicted_labels` |
| Multiclass classification | `f"{Source} has {Any:label}"` | `"multiclass_classification"` | `accuracy` | `.probs`, `.predicted_labels` |
| Multilabel classification | `f"{Source} has {Any:label}"` | `"multilabel_classification"` | `multilabel_auprc_macro` | `.probs`, `.predicted_labels` |
| Regression | `f"{Source} has {Any:value}"` | `"regression"` | `rmse` | `.predicted_value` |
| Link prediction | `f"{Source} has {Target}"` | `"link_prediction"` | `link_prediction_precision@10` (confirm eval_k with user; also consider `recall@K` and `map@K`) | `.rank`, `.scores`, `.predicted_<target>` |
| Repeated link prediction | `f"{Source} has {Target}"` | `"repeated_link_prediction"` | `link_prediction_precision@10` (confirm eval_k with user; also consider `recall@K` and `map@K`) | `.rank`, `.scores`, `.predicted_<target>` |

## Multi-dataset experimentation

When the best label definition or window size is uncertain, generate multiple training datasets and compare model performance — without changing the val or test sets.

### The rule: fix test and val, vary train only

| Split | Rule |
|---|---|
| **TEST** | Fixed across all experiments. Same cutoff range, same entities, same label definition. Changing the test set makes model comparisons meaningless. |
| **VAL** | Fixed across all experiments. Same cutoff range and label definition. Changing val changes early-stopping behaviour and invalidates metric comparisons. |
| **TRAIN** | Varies per experiment. Different prediction windows, lookback filters, or label definitions are all fair game. |

### Schema naming convention

Give each experiment its own schema, named to reflect what varies. The TEST (and optionally VAL) table can live in a shared schema referenced by all experiments.

```
DATABASE/
├── CHURN_SHARED/
│   ├── VAL           ← fixed val, shared across all experiments
│   └── TEST          ← fixed test, shared across all experiments
├── CHURN_45D/
│   ├── STAGING       ← full dataset for this variant (used for validation queries)
│   └── TRAIN         ← 45-day prediction window
├── CHURN_90D/
│   ├── STAGING
│   └── TRAIN         ← 90-day prediction window
└── CHURN_90D_STRICT/
    ├── STAGING
    └── TRAIN         ← 90-day window + tighter activity filter
```

### How to generate this in SQL

Generate the shared val/test tables once, then generate a STAGING + TRAIN for each variant. In each variant's STAGING, include the val and test rows too (for the leakage check), but only materialise the TRAIN table — the shared val and test are already in `CHURN_SHARED`.

```sql
-- Shared schema: generated once
CREATE SCHEMA IF NOT EXISTS DB.CHURN_SHARED;
CREATE OR REPLACE TABLE DB.CHURN_SHARED.VAL  AS SELECT ... FROM DB.CHURN_45D.STAGING WHERE split = 'val';
CREATE OR REPLACE TABLE DB.CHURN_SHARED.TEST AS SELECT ... FROM DB.CHURN_45D.STAGING WHERE split = 'test';

-- Per-experiment: only TRAIN varies
CREATE SCHEMA IF NOT EXISTS DB.CHURN_90D;
-- ... STAGING INSERT with 90-day window ...
CREATE OR REPLACE TABLE DB.CHURN_90D.TRAIN AS SELECT ... FROM DB.CHURN_90D.STAGING WHERE split = 'train';
-- VAL and TEST: point to CHURN_SHARED, not regenerated
```

### When to use this

Never proactively suggest or ask about multi-dataset experimentation, at any point in either sub-skill. Apply this pattern only when the user explicitly asks to compare multiple training dataset variants (e.g. different prediction windows or activity filters) — then follow the rule above (fix test/val, vary train only).

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| `WITH ... INSERT INTO ... SELECT` | Real Snowflake requires `INSERT INTO <table>` to come *before* `WITH` — `sqlfluff`/`sqlglot`'s `snowflake` dialect models CTEs as a generic prefix and will parse this order without complaint even though Snowflake rejects it (`unexpected 'INSERT'`) | Always write `INSERT INTO <table> WITH cte AS (...) SELECT ... FROM cte`. See `utils_conventions.md`'s CTE structure section and `utils_validation.md`'s "Known gap" note. |
| `QUALIFY <condition>` used as a plain row filter | `QUALIFY` filters on a window function's result — Snowflake raises a syntax error when there's no window function anywhere in the `SELECT`/`WHERE` | Use `WHERE` for filtering that isn't based on a window function; reserve `QUALIFY` for `ROW_NUMBER()`-style dedup. See `utils_conventions.md`'s Deduplication section. |
| `invalid identifier 'REVIEW_TIME'` at runtime even though the column clearly exists | The column was created with double quotes (e.g. `"review_time"`), making it case-sensitive; `information_schema.columns` returns such columns lowercase | Check Query 1's results for lowercase column names and wrap every reference to them in double quotes throughout the generated SQL. See `utils_conventions.md`'s Case-sensitive column identifiers section. |
| A column aliased as `value`, `date`, `order`, etc. without quoting | These are Snowflake-reserved words; using one unquoted as a column alias is a syntax error | Use a descriptive alternative (`target_value`, `cutoff_date`, ...) in validation queries and intermediate CTEs — the task table's mandated `value` column itself is the one place this name is required. See `utils_conventions.md`'s Reserved words section. |
| `sqlfluff parse` and `validate_schema.py` both pass, but the statement still fails against real Snowflake | Local tools approximate the Snowflake dialect and don't model every real-engine rule (e.g. the `WITH`/`INSERT` ordering above, or duplicate CTE names, which real Snowflake silently accepts) | Prefer the EXPLAIN road whenever a live session is available — it compiles against the real engine. See `utils_validation.md`. |

## Examples

No standalone `examples/` directory — worked examples live inline, one per task type, in the `guided` sub-skill:

| Scenario | Task type | Where |
|---|---|---|
| Churn (won't place an order in the next 90 days) | Binary classification | [GUIDED.md § Examples: data scenario → task type](references/GUIDED.md) |
| Next product category purchased | Multiclass classification | [GUIDED.md § Examples: data scenario → task type](references/GUIDED.md) |
| Propensity to buy in multiple categories | Multilabel classification | [GUIDED.md § Examples: data scenario → task type](references/GUIDED.md) |
| 90-day revenue (LTV) | Regression | [GUIDED.md § Examples: data scenario → task type](references/GUIDED.md) |
| Recommend products a customer hasn't necessarily bought before | Link prediction | [GUIDED.md § Examples: data scenario → task type](references/GUIDED.md) |
| Reorder / repurchase recommendations | Repeated link prediction | [GUIDED.md § Examples: data scenario → type](references/GUIDED.md) |

Each matching `task_<type>.md` file also carries one full worked SQL template (schema contract, downstream binding, leakage rules) for its task type — load it only after the task type is confirmed (Step 2 of `GUIDED.md`).

## Reference files

| File | When to use |
|---|---|
| [references/utils_auto_execution.md](references/utils_auto_execution.md) | The user opts into automatic Snowflake execution (Step 0) — defines read/write permission tiers and the Snowpark session pattern |
| [references/utils_conventions.md](references/utils_conventions.md) | Generating any SQL — CTE style, `QUALIFY` usage, identifier-quoting rules |
| [references/utils_cutoff_policies.md](references/utils_cutoff_policies.md) | A temporal task's cutoff strategy is being configured (Step 3, after task type is confirmed) |
| [references/utils_output_format.md](references/utils_output_format.md) | Producing the final summary, or handling a user-edited-file / execution-error follow-up |
| [references/utils_python_environment.md](references/utils_python_environment.md) | Resolving the local Python venv for `sqlglot`/`sqlfluff`/Snowpark, needed by validation or auto-execution |
| [references/utils_validation.md](references/utils_validation.md) | Immediately before showing any generated SQL to the user — local-tool road vs. EXPLAIN road |
| [references/task_binary.md](references/task_binary.md) | Task type is confirmed as binary classification |
| [references/task_multiclass.md](references/task_multiclass.md) | Task type is confirmed as multiclass classification |
| [references/task_multilabel.md](references/task_multilabel.md) | Task type is confirmed as multilabel classification |
| [references/task_regression.md](references/task_regression.md) | Task type is confirmed as regression |
| [references/task_link_prediction.md](references/task_link_prediction.md) | Task type is confirmed as link prediction |
| [references/task_repeated_link_prediction.md](references/task_repeated_link_prediction.md) | Task type is confirmed as repeated link prediction |
| [scripts/validate_schema.py](scripts/validate_schema.py) | Schema-layer validation step of `utils_validation.md` — deterministic structural checks against a generated SQL artifact |
| [references/utils_one_shot_auto_inference.md](references/utils_one_shot_auto_inference.md) | Running in one-shot mode — decision rules and query templates for filling configuration fields without asking |
