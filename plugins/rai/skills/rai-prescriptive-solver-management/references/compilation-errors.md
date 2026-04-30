# Table of Contents

- [Entity Reference Error — Detailed Diagnostics](#entity-reference-error--detailed-diagnostics)
- [Type Mismatch](#type-mismatch)
- [Undefined Concept/Property](#undefined-conceptproperty)
- [Zero Entities — Detailed Diagnostics](#zero-entities--detailed-diagnostics)
- [Simplest Fix Principle](#simplest-fix-principle)

---

# Compilation Errors — Detailed Diagnostics

## Entity Reference Passed as Scalar

**Symptom:** `model.define(...)` accepts the schema, but the next query/solve raises a generic `RAIException: [TyperError] Type errors detected during type inference (see above for details).` (the diagnostic body is often blank — see `rai-pyrel-coding/references/common-pitfalls.md` § `TyperError` with empty diagnostic body for surfacing tips).

Cause: `entity_creation` copies an entity-typed Property (FK) into a slot declared with a scalar type (Integer, Float, String).

**Option A (simpler — remove the problematic property):** Remove the property from concept_definition and entity_creation entirely. Only keep properties needed for optimization.

**Option B (if you need the ID for constraints):** In concept_definition, keep Property with the scalar type. In entity_creation, use `.id` to extract scalar: `sku_id=Demand.sku.id`.

## Type Mismatch

Property declared with one scalar type but the source DataFrame column is a different type (e.g., declared `:int` but source is a date string, or declared `:str` but source is `Int64`). Surfaces at query time as a generic `[TyperError]`. Fix: align the Property's declared type with the source column dtype, or convert the column upstream (e.g., `df["col"] = pd.to_datetime(df["col"]).dt.date` before `model.data(df)`).

## Undefined Concept/Property

**Symptom:** depends on the access pattern — `model.concept_index["Foo"]` raises `KeyError: 'Foo'`; `model.Foo` (attribute access on a name never declared) raises `AttributeError: 'Model' object has no attribute 'Foo'`. There is no PyRel error string `"Concept X not found"`.

Cause: referencing a concept name that was never created via `model.Concept(...)`. Fix: typo check, or declare the concept before referencing.

## Zero Entities — Detailed Diagnostics

**Symptom:** `problem.display()` prints `Problem (numeric type: Float): empty` (or `Integer`) when the registered variables are all bound to entity sets with zero rows. Confirm with `problem.num_variables() == 0` (engine-side) or by checking `problem.display(part)` of a specific variable group.

The entity_creation expression produced no entities — likely a join mismatch. Fix: verify join conditions match actual data relationships.

When entity creation produces ZERO entities (cross-product or filtered concept has no instances), diagnose using this taxonomy:

**1. Non-existent concept reference:** The `entity_creation` uses a concept name that doesn't exist in the model.
- Look for typos or incorrect concept names (e.g., references "Stock2" when only "Stock" exists)
- Check against the AVAILABLE CONCEPTS list

**2. Join condition mismatch:** The `.where()` condition matches nothing.
- Check if relationship paths are valid in the model
- Check if property values actually exist in data (e.g., filtering by a status that has no matching rows)

**3. Missing relationship:** The `concept_definition` creates relationships that don't connect to data.
- Verify relationship targets exist and have entities loaded
- Check if the relationship is defined in the model schema

**4. Over-filtering:** The `.where()` clause is too restrictive.
- Multiple filter conditions that together match nothing
- Each condition alone might match rows, but the intersection is empty

**Fix requirements:**
- Use ONLY concepts from the available concepts list
- Reference actual relationships and properties from the model context
- The fix must produce entities (join/filter must match some data)
- Prefer relaxing filters over completely restructuring the entity creation
