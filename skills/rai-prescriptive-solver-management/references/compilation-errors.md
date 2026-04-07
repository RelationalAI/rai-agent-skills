# Table of Contents

- [Entity Reference Error — Detailed Diagnostics](#entity-reference-error--detailed-diagnostics)
- [Type Mismatch](#type-mismatch)
- [Undefined Concept/Property](#undefined-conceptproperty)
- [Zero Entities — Detailed Diagnostics](#zero-entities--detailed-diagnostics)
- [Simplest Fix Principle](#simplest-fix-principle)

---

# Compilation Errors — Detailed Diagnostics

## Entity Reference Error — Detailed Diagnostics

**Error:** "Source X.y is an entity reference to Z, not a scalar value"

The entity_creation is copying an entity reference where a scalar is expected. You must update BOTH concept_definition AND entity_creation together.

**Option A (simpler — remove the problematic property):** Remove the property from concept_definition and entity_creation entirely. Only keep properties needed for optimization.

**Option B (if you need the ID for constraints):** In concept_definition, keep Property with string type. In entity_creation, use `.id` to extract scalar: `sku_id=Demand.sku.id`.

## Type Mismatch

**Error:** "declared as 'int' but source is DATE"

Property type doesn't match source column type. Fix: change the property type to match (DATE columns should use `:str` or `:date`).

## Undefined Concept/Property

**Error:** "Concept X not found"

Referenced concept doesn't exist in base model. Fix: use correct concept name from available concepts, or create via concept_definition.

## Zero Entities — Detailed Diagnostics

**Symptom:** "Variables (0)" in formulation display

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
