# Task Relationships

Relationships encode the task structure using a template string with three parts:
- **Head** = source concept (the concept being predicted on)
- **"at" clause** = optional timestamp field
- **"has" clause** = label (classification/regression) or target concept (link prediction)

## Relationship Arity Rules

| Task Type | Train/Val template | Test template |
|-----------|-------------------|---------------|
| classification (no time) | `f"{Source} has {Any:label}"` | `f"{Source}"` |
| classification (with time) | `f"{Source} at {Any:ts} has {Any:label}"` | `f"{Source} at {Any:ts}"` |
| regression (no time) | `f"{Source} has {Any:value}"` | `f"{Source}"` |
| regression (with time) | `f"{Source} at {Any:ts} has {Any:value}"` | `f"{Source} at {Any:ts}"` |
| link_prediction | `f"{Source} has {Target}"` | `f"{Source}"` |
| repeated_link_prediction | `f"{Source} at {Any:ts} has {Target}"` | `f"{Source} at {Any:ts}"` |

## Node Classification (with time)

```python
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
```

## Node Classification (no time)

```python
Train = Relationship(f"{User} has {Any:target}")
Val = Relationship(f"{User} has {Any:target}")
Test = Relationship(f"{User}")
```

## Regression (with time)

Numeric target on the source concept (e.g. a per-row value).

```python
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
```

## Regression (no time)

```python
Train = Relationship(f"{Interaction} has {Any:value}")
Val = Relationship(f"{Interaction} has {Any:value}")
Test = Relationship(f"{Interaction}")
```

## Link Prediction — Task Table Format Requirements (VARIANT check)

The GNN framework requires link prediction task tables in **flat format**: one row per `(src, timestamp, tgt)` pair.

| Split | Required columns | Notes |
|-------|-----------------|-------|
| Train | `src_id`, `timestamp`, `tgt_id` | One target per row |
| Val | `src_id`, `timestamp`, `tgt_id` | One target per row |
| Test | `src_id`, `timestamp` | No target column |

> **Before writing link prediction task table definitions, run `DESCRIBE TABLE` on all three split tables (train, val, and test) and check column types. This includes the test table — some users provide labels there for evaluation purposes.**
>
> **Warning:** if any join key or target column is `VARIANT` type (e.g. a JSON array of target IDs per row), the table is in the wrong format and the join `Target.tgt_id == train_table_concept.tgt_id` will fail with `[UnresolvedType]`. Do not flatten automatically — propose creating a LATERAL FLATTEN table to the user and wait for explicit approval before creating anything in Snowflake:
> ```sql
> -- Use CREATE TABLE (not VIEW) — Snowflake does not support change tracking on LATERAL views
> CREATE OR REPLACE TABLE my_db.my_schema.my_task_table_flat AS
> SELECT src_id, timestamp, f.value::INT AS tgt_id
> FROM my_task_table, LATERAL FLATTEN(input => tgt_array) f;
>
> ALTER TABLE my_db.my_schema.my_task_table_flat SET CHANGE_TRACKING = TRUE;
> ```
>
> **If the `VARIANT` column is not used in any relationship join** (e.g. an extra column in the test table), it produces a non-blocking warning — no action needed, keep the original table as-is.

## Link Prediction (with time / repeated_link_prediction)

```python
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
```

## Link Prediction (no time)

```python
Train = Relationship(f"{User} has {Item}")
Val = Relationship(f"{User} has {Item}")
Test = Relationship(f"{User}")
```

## Alternative: select() fragments

Instead of `Relationship` + `define()`, you can use `select()` directly. Both forms are accepted by the GNN constructor:

```python
Train = select(User, train_table_concept.timestamp, Item).where(
    User.user_id == train_table_concept.user_id,
    Item.item_id == train_table_concept.item_id,
)

Val = select(User, val_table_concept.timestamp, Item).where(
    User.user_id == val_table_concept.user_id,
    Item.item_id == val_table_concept.item_id,
)

Test = select(User, test_table_concept.timestamp).where(
    User.user_id == test_table_concept.user_id,
)
```

## Post-training aggregation (rollup shape)

A common real-world shape is: train the GNN on fine-grained events (e.g. a `Transaction` source), then aggregate predictions up to a coarser entity (e.g. `Article`) for downstream rules or optimization. This lives on the **consumption side**, not in the Relationship template -- see `rai-predictive-training` § Aggregation and bridge concepts for the `aggregates.<sum|avg|count>(Source.predictions.<attr>).per(Target).where(...)` pattern.
