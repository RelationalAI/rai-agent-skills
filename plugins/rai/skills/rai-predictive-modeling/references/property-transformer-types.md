# PropertyTransformer Feature Types

The `PropertyTransformer` class specifies how concept fields are transformed into GNN-compatible features.

## Feature Types

| Type | PropertyTransformer kwarg | Description | Example fields |
|------|--------------------------|-------------|----------------|
| Category | `category=[...]` | Discrete categorical values (int or string) | Gender, product code, membership status |
| Continuous | `continuous=[...]` | Numeric continuous values (float) | Age, price, rating |
| Text | `text=[...]` | Text strings (embedded via language model) | Product name, description, comment |
| Datetime | `datetime=[...]` | Timestamps or dates | Transaction date, creation date |
| Integer | `integer=[...]` | Whole-number counts or ordinal values (not IDs) | Review counts, position ranks |
| Drop | `drop=[...]` | Exclude field from model entirely | Foreign keys, sensitive data, redundant IDs |

## Special Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_col` | list or single | Time column(s) for temporal models. Must NOT appear in `drop`. When multiple concepts have date fields, list all of them: `time_col=[Interaction.timestamp, Session.started_at, Order.placed_at, ...]`. Fields in `time_col` must also appear in `datetime`. |

## Usage

```python
from relationalai.semantics.reasoners.predictive import PropertyTransformer

pt = PropertyTransformer(
    category=[User.status, Item.category, Interaction.channel],
    continuous=[User.age, Interaction.value],
    text=[Item.name],
    datetime=[Interaction.timestamp],
    drop=[User.internal_code, Item.legacy_sku],
    time_col=[Interaction.timestamp],
)
```

## Drop Patterns

### Drop specific fields
```python
drop=[Item.legacy_sku, Item.internal_code]
```

### Drop all fields of a concept (identifier columns)
```python
drop=[User]  # drops all User fields (including primary key)
```

### Mixed: drop entire concept + specific fields from another
```python
drop=[Interaction, Item.legacy_sku, Item.internal_code]
```

## Default Behavior

Fields not mentioned in any category are auto-inferred by the GNN engine (equivalent to the `Infer` embedding type). This is usually fine for most fields, but explicitly annotating them improves reproducibility.

## Guidelines

- **Primary key / identifier fields**: Usually `drop` (they don't carry predictive signal)
- **Foreign key join columns**: Usually `drop` (the graph structure captures the relationship)
- **Numeric IDs that encode meaning** (e.g. product_code): Use `category`
- **Free-form text**: Use `text`
- **Dates/timestamps**: Use `datetime`. If it's the temporal ordering column, also add to `time_col`
- **Boolean flags**: Use `category`
- **Continuous measurements**: Use `continuous`
