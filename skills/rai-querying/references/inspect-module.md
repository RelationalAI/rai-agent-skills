# `relationalai.semantics.inspect` — Public Model Introspection API

## Table of Contents
- [When to Use](#when-to-use)
- [`inspect.schema(model)`](#inspectschemamodel)
- [`inspect.fields(rel)`](#inspectfieldsrel)
- [`inspect.to_concept(obj)`](#inspecttoconceptobj)
- [Data Sources: `model.data_items`](#data-sources-modeldata_items)
- [Filtering Library-Internal Concepts](#filtering-library-internal-concepts)
- [When Not to Use](#when-not-to-use)

---

Three public functions in `relationalai.semantics.inspect` replace ad-hoc access to underscored internals (`_name`, `_relationships`, `_identify_by`). They provide a stable, typed, JSON-safe view of a model at runtime. Available from `relationalai>=1.0.14`.

```python
from relationalai.semantics import inspect
```

**Reading `~relationship` entries.** `ConceptInfo.relationships` formats each as `~{short_name}: {reading_string}` — e.g., `~my_short_name: A links to B`. The prefix after `~` is the **`short_name`** (for query disambiguation), NOT the Python attribute name. The attribute name is whatever was assigned on the concept: `A.rel = model.Relationship(..., short_name="my_short_name")` → use `A.rel(B)` in queries, not `A.my_short_name(B)`.

## When to Use

**Prefer `inspect.*` over direct `model.concepts` / `.relationships` / `.tables` access** for:

- **Inspect-before-authoring** — Before adding a rule, derived property, or decision variable, check `inspect.schema()[concept]` to detect duplicates, confirm names, pick up the real type. Closes hallucinated-surface, wrong-type, and duplicate-authoring failure modes in a single call.
- **Post-action verification** — After scaffolding or modifying a model, dump `inspect.schema().to_dict()` to report *what actually registered* instead of *what you intended*.
- **Session-hygiene re-grounding** — See [Re-grounding after drift](#re-grounding-after-drift) below.
- **Prescriptive formulation** — When authoring `solve_for` / `satisfy` / `minimize` / `maximize` over an existing model, verify every referenced concept and property against `inspect.schema()` before handing the formulation to the solver.

### Re-grounding after drift

The agent's mental model of an RAI model drifts over long sessions. Re-ground with `inspect.schema()` when any of these signal applies:

- **After `/compact`** — compression is lossy by design; concepts and property types you had in working memory may not have survived.
- **After ~30+ turns** on the same model — incremental reads leave gaps; a single `inspect.schema()` is cheaper than re-reading the source files.
- **When resuming work on an existing model** — new session, previous conversation's context is gone.
- **Before authoring on a "familiar" concept** — "I remember `Customer` has a `tier` property" is exactly the kind of confident-but-wrong recall that causes silent failures. Check first.

This pattern is cross-cutting: it applies to rules-authoring, querying, prescriptive formulation, and any skill that builds on existing model surface. One call; trust the result over memory.

## `inspect.schema(model)`

Returns a `ModelSchema` — a frozen dataclass containing concepts, properties (including inherited, with cycle-safe traversal), relationships, tables, inline data sources, enums, and rules.

```python
schema = inspect.schema(model)

# Human-readable
print(schema)

# Dict-style lookup by concept name
customer_info = schema["Customer"]

# JSON-safe serialization
import json
json.dumps(schema.to_dict())
```

**Typical usage patterns:**

`ConceptInfo.properties` is a `tuple[RelationshipInfo, ...]`, not a dict. Match by `.name` on each entry; read type via `.type_name` (a string like `"Integer"`).

```python
# Does a property already exist before adding it?
customer_prop_names = {p.name for p in schema["Customer"].properties}
if "tier" not in customer_prop_names:
    # safe to add

# What's the real type of this column?
amount_type = next(p.type_name for p in schema["Order"].properties if p.name == "amount")

# What concepts are in the model? (exclude reasoner internals — see filtering section)
user_concepts = [c for c in schema.concepts if not c.name.startswith("_")]
```

**Targeted output for large models:** `schema["Person"]` returns just that concept's `ConceptInfo`. Use this when the full `to_dict()` dump would be too large to share back — it narrows the output you hand the user, not the work the call does (constructing `schema` already walked the whole model).

## `inspect.fields(rel)`

Returns a tuple of `FieldRef` objects for a relationship or chain — directly usable in `select()`. Replaces manual field unpacking.

```python
# Canonical idiom — select every field of a relationship
model.select(*inspect.fields(Item.successors)).to_df()

# Equivalent to the manual form, but handles inheritance and alt readings correctly:
# model.select(Item.successors["s"], Item.successors["data"]).to_df()
```

**Behavior:**
- Excludes the owner field by default. Pass `include_owner=True` to include it.
- Handles inherited properties correctly — `inspect.fields(Adult.name)` works when `name` is declared on `Person`.
- Normalizes alt readings to the parent relationship so field ordering is consistent.
- For direct `Relationship` / `Reading` handles, the owner is inferred when unique.

## `inspect.to_concept(obj)`

Resolves any DSL Variable (Chain, Ref, Expression, FieldRef, etc.) to its underlying `Concept`. Useful for reusable helpers that accept any handle type.

```python
# Accepts any DSL handle — raises by default if resolution fails
concept = inspect.to_concept(handle)

# Defensive use — returns None instead of raising
concept = inspect.to_concept(handle, default=None)
```

**When to reach for this:** writing a helper that should work uniformly whether the caller passes `Customer`, `Customer.orders`, `Customer.orders.total`, or an expression. Without `to_concept`, such helpers usually either assume one shape (and break on others) or branch on `isinstance` chains (which miss subclasses).

## Data Sources: `model.data_items`

`model.tables` only includes explicitly declared `Table` objects. Inline data loaded via `model.data(pd.DataFrame(...))` is tracked separately in `model.data_items`.

```python
# Full list of data sources — BOTH tables and inline data
all_sources = list(model.tables) + list(model.data_items)
```

Skills or utilities that list "every data source feeding this model" must check both. `inspect.schema()` covers both in a single call.

## Filtering Library-Internal Concepts

Reasoners (prescriptive, graph, paths) register their own concepts on the shared model. These show up in `inspect.schema()` output and are usually noise for user-facing introspection. The exact names depend on which reasoners you've used — there is no clean prefix pattern.

**Known reasoner-registered names** (non-exhaustive; current as of `relationalai==1.0.14`):

| Reasoner | Concept names registered |
|---|---|
| prescriptive (after `Problem(...)` + `solve_for` / `satisfy` / `minimize` / `maximize`) | `Variable`, `Expression`, `Constraint`, `Objective`, plus per-solve `Variable_<id>` / `Constraint_<id>` / `Objective_<id>` subconcepts |
| graph | varies by algorithm invoked |

**Filter pattern:**

```python
# Inspect what's there, then drop the reasoner-registered names you've exercised.
schema = inspect.schema(model)
reasoner_names = {"Variable", "Expression", "Constraint", "Objective"}
user_concepts = [
    c for c in schema.concepts
    if c.name not in reasoner_names
    and not any(c.name.startswith(p + "_") for p in reasoner_names)
]
```

If the user asks "what's in my model?" and you dump everything without filtering, the output is confusing. Inspect first to see the actual names in the current model, then filter by list — don't rely on a fixed prefix.

## When Not to Use

`inspect` calls cost turns and tokens. Skip them when:

- **Greenfield authoring** — the model is empty or near-empty; nothing to inspect.
- **Short single-shot tasks** — no session history to drift from; inspect just adds a turn.
- **Highly templated work** — when the task is "follow this template exactly", re-deriving its structure via inspect is wasted motion.

A useful heuristic: inspect *before* writing code that references existing model surface. Skip it for writing fresh concepts, simple one-shot queries, or template-driven work.
