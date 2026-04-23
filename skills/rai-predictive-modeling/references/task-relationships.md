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
