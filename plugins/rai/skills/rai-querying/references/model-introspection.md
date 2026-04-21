# Model Introspection

## Table of Contents
- [Core Collections](#core-collections)
- [Relationship / Property Inspection](#relationship--property-inspection)
- [Field Attributes](#field-attributes)
- [Quick Examples](#quick-examples)

---

Public API for discovering model structure at runtime. Useful for dynamic code generation, model validation, and exploring unfamiliar models.

## Core Collections

| API | Type | Description |
|-----|------|-------------|
| `model.concepts` | `list[Concept]` | All concepts in creation order |
| `model.concept_index` | `dict[str, Concept]` | Lookup concept by name |
| `model.relationships` | `list[Relationship]` | All relationships/properties |
| `model.relationship_index` | `dict[str, Relationship]` | Lookup by short name |
| `model.tables` | `list[Table]` | All table references |
| `model.table_index` | `dict[str, Table]` | Lookup table by path |
| `model.defines` | `KeyedSet[Fragment]` | All define() fragments |
| `model.requires` | `KeyedSet[Fragment]` | All require() fragments |
| `model.enums` | `list[type[ModelEnum]]` | Enum types |

## Relationship / Property Inspection

| API | Type | Description |
|-----|------|-------------|
| `rel.to_df()` | method | Materialize relationship tuples as DataFrame |
| `rel.inspect()` | method | Print relationship data to stdout |

## Field Attributes

| API | Type | Description |
|-----|------|-------------|
| `field.name` | `str` | Field role name (e.g., "customer", "cost") |
| `field.type` | `Concept` | Field type (always resolved in v1) |
| `field.is_input` | `bool` | Whether field is an input field |
| `field.is_list` | `bool` | Whether field is list-valued |

## Quick Examples

```python
# List all concept names — print() shows readable names (one per line)
for concept in model.concepts:
    print(concept)          # → Customer

# Lookup by name
Order = model.concept_index["Order"]

# Find all properties/relationships on a concept
order_rels = [r for r in model.relationships if any(
    str(f.type) == "Order" for f in r
)]

# Check what tables are loaded
for table in model.tables:
    print(table)
```

For detailed introspection patterns (classification, property maps, data inspection), see [joins-and-export.md](joins-and-export.md) § Schema Introspection Reference.
