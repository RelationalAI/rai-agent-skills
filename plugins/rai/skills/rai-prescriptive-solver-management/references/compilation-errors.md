# Table of Contents

- [Entity Reference Error — Detailed Diagnostics](#entity-reference-error--detailed-diagnostics)
- [Type Mismatch](#type-mismatch)
- [Undefined Concept/Property](#undefined-conceptproperty)
- [Zero Entities — Detailed Diagnostics](#zero-entities--detailed-diagnostics)
- [Simplest Fix Principle](#simplest-fix-principle)

---

# Compilation Errors — Detailed Diagnostics

> **General PyRel compile errors** (`[TyperError]` with empty body, type mismatches between Property and DataFrame dtype, `KeyError` from `model.concept_index["Foo"]`, `AttributeError` from `model.Foo` on a name never declared) live in `rai-pyrel-coding/references/common-pitfalls.md` — see § `TyperError` with empty diagnostic body and surrounding rows. The notes below cover the same errors as they appear specifically in optimization formulations.

## Entity Reference Passed as Scalar (in entity_creation)

`entity_creation` copies an entity-typed Property (FK) into a slot declared with a scalar type (Integer, Float, String). Surfaces later as a `[TyperError]` at query/solve time.

**Option A (simpler — remove the problematic property):** Remove the property from concept_definition and entity_creation entirely. Only keep properties needed for optimization.

**Option B (if you need the ID for constraints):** In concept_definition, keep the Property with the scalar type. In entity_creation, use `.id` to extract the scalar: `sku_id=Demand.sku.id`.

## Type Mismatch (Property vs DataFrame column)

Same root cause as the general PyRel case (declared `:int` but source is a date string, etc.) — see `rai-pyrel-coding/references/common-pitfalls.md`. In a prescriptive formulation, the symptom typically appears at the first `problem.solve()` rather than at an earlier query, because optimization workflows often defer materialization until solve time.

## Undefined Concept/Property

Standard Python lookup errors (`KeyError` from `model.concept_index["Foo"]`, `AttributeError` from `model.Foo`) when the concept name was never declared via `model.Concept(...)`. Same pattern as in any PyRel code — fix by typo-checking or declaring the concept before referencing it.

## Zero Entities — Detailed Diagnostics

**Symptom:** `problem.display()` reports the problem as empty / shows zero registered variables; equivalently `problem.num_variables() == 0`. Use `problem.display(part)` to inspect a specific variable group.

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
