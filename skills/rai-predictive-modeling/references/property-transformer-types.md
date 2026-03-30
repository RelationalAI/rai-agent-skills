# PropertyTransformer Feature Types

The `PropertyTransformer` class specifies how concept fields are transformed into GNN-compatible features.

## Feature Types

| Type | PropertyTransformer kwarg | Description | Example fields |
|------|--------------------------|-------------|----------------|
| Category | `category=[...]` | Discrete categorical values (int or string) | Gender, product code, membership status |
| Continuous | `continuous=[...]` | Numeric continuous values (float) | Age, price, rating |
| Text | `text=[...]` | Text strings (embedded via language model) | Product name, description, comment |
| Datetime | `datetime=[...]` | Timestamps or dates | Transaction date, creation date |
| Integer | `integer=[...]` | Integer values (kept as integers, not categorical) | Explicit integer IDs |
| Drop | `drop=[...]` | Exclude field from model entirely | Foreign keys, sensitive data, redundant IDs |

## Special Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_col` | list or single | Time column(s) for temporal models. Must NOT appear in `drop`. |

## Usage

```python
from relationalai.semantics.reasoners.predictive import PropertyTransformer

pt = PropertyTransformer(
    category=[Customer.gender, Article.PRODUCT_CODE, Transaction.SALES_CHANNEL_ID],
    continuous=[Customer.age, Transaction.PRICE],
    text=[Article.PROD_NAME],
    datetime=[Transaction.T_DAT],
    drop=[Customer, Article.GRAPHICAL_APPEARANCE_NAME],
    time_col=[Transaction.T_DAT],
)
```

## Drop Patterns

### Drop specific fields
```python
drop=[Article.GRAPHICAL_APPEARANCE_NAME, Article.COLOUR_GROUP_CODE]
```

### Drop all fields of a concept (identifier columns)
```python
drop=[Customer]  # drops all Customer fields (including primary key)
```

### Mixed: drop entire concept + specific fields from another
```python
drop=[Customer, Article.GRAPHICAL_APPEARANCE_NAME, Article.COLOUR_GROUP_CODE]
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
