# Model Introspection

## Table of Contents
- [Recommended API: `inspect.*`](#recommended-api-inspect)
- [Lower-level Access](#lower-level-access)
- [Field Attributes](#field-attributes)
- [Quick Examples](#quick-examples)

---

Public APIs for discovering model structure at runtime. Useful for inspect-before-authoring checks, post-scaffolding verification, query construction over unfamiliar models, and long-session re-grounding.

## Recommended API: `inspect.*`

`relationalai.semantics.inspect` provides the stable, typed, JSON-safe introspection surface. **Prefer it over the lower-level collections below.**

```python
from relationalai.semantics import inspect

schema = inspect.schema(model)          # full ModelSchema (frozen dataclass)
fields = inspect.fields(rel)            # tuple[FieldRef, ...] for select()
concept = inspect.to_concept(handle)    # resolve any DSL handle to its Concept
```

See [inspect-module.md](inspect-module.md) for full usage, including targeted dict-style access, library-internal concept filtering, and when-not-to-use guidance.

**Canonical idioms:**

```python
# Select every field of a relationship (handles inheritance and alt readings correctly)
model.select(*inspect.fields(Customer.orders)).to_df()

# Check whether a property exists before adding it
# (ConceptInfo.properties is a tuple — match by .name)
customer_props = {p.name for p in inspect.schema(model)["Customer"].properties}
if "tier" not in customer_props:
    ...  # safe to add

# Dump schema for user-facing verification
inspect.schema(model).to_dict()
```

## Lower-level Access

These collections remain available as a fallback, but `inspect.*` is the recommended surface for everything listed below.

| API | Type | Description |
|-----|------|-------------|
| `model.concepts` | `list[Concept]` | All concepts in creation order |
| `model.concept_index` | `dict[str, Concept]` | Lookup concept by name |
| `model.relationships` | `list[Relationship]` | All relationships/properties |
| `model.relationship_index` | `dict[str, Relationship]` | Lookup by short name |
| `model.tables` | `list[Table]` | Explicitly declared `Table` references |
| `model.table_index` | `dict[str, Table]` | Lookup table by path |
| `model.data_items` | `list[Data]` | Inline data sources from `model.data(...)` — **separate from `model.tables`** |
| `model.defines` | `KeyedSet[Fragment]` | All `define()` fragments |
| `model.requires` | `KeyedSet[Fragment]` | All `require()` fragments |
| `model.enums` | `list[type[ModelEnum]]` | Enum types |

**Note on data sources:** `model.tables` does **not** include inline `model.data(pd.DataFrame(...))` sources — those live in `model.data_items`. Utilities that list "every data source" must check both. `inspect.schema()` covers both in a single call.

**Note on relationship inspection:**

| API | Type | Description |
|-----|------|-------------|
| `rel.to_df()` | method | Materialize relationship tuples as DataFrame |
| `rel.inspect()` | method | Print relationship data to stdout |

## Field Attributes

Two distinct surfaces — use the right one for your task.

**Structured field metadata** is on `RelationshipInfo.fields` from `inspect.schema(model)`. Each element is a `FieldInfo`:

| API | Type | Description |
|-----|------|-------------|
| `field.name` | `str` | Field role name (e.g., "customer", "cost") |
| `field.type_name` | `str` | Field type name (e.g., `"Integer"`, `"String"`). String, not a Concept object. |
| `field.is_input` | `bool` | Whether field is an input field |
| `field.is_list` | `bool` | Whether field is list-valued |

Use this when you need to read field metadata programmatically.

**Selectable field references** from `inspect.fields(rel)` are `FieldRef` objects — usable directly in `select()` but NOT for reading field metadata. `FieldRef` does not expose `.name` / `.type_name` / `.is_input` / `.is_list` directly; attribute access on a `FieldRef` delegates through a DSL proxy and raises if you try to use it for introspection.

```python
# For select() — correct use:
model.select(*inspect.fields(Order.line_items)).to_df()

# For metadata — go through the schema, not through inspect.fields:
rel_info = next(r for r in schema["Order"].relationships if r.name == "line_items")
for field in rel_info.fields:
    print(field.name, field.type_name)
```

## Quick Examples

```python
from relationalai.semantics import inspect

# List concepts excluding reasoner internals
# (Note: underscore-prefix is not reliable — prescriptive registers Variable,
# Constraint, Objective, Variable_<id>, etc. See inspect-module.md § Filtering
# Library-Internal Concepts for the list-based filter.)
schema = inspect.schema(model)
user_concepts = [c for c in schema.concepts if not c.name.startswith("_")]

# Find all properties on a concept, including inherited ones
# ConceptInfo.properties is a tuple[RelationshipInfo, ...]
order_props = schema["Order"].properties

# Select every field of a relationship — canonical idiom
model.select(*inspect.fields(Order.line_items)).to_df()

# Confirm property type before coding against it
# (match by .name; type is on .type_name as a string)
amount_type = next(p.type_name for p in schema["Order"].properties if p.name == "amount")

# Lower-level equivalents (fallback only)
for concept in model.concepts:
    print(concept)
Order = model.concept_index["Order"]
```

For join patterns and export workflows, see [joins-and-export.md](joins-and-export.md).
