# Phase 5 — Translate to PyRel

verbs: plan, execute, verify, ship
skill: rai-orm-from-text
csdp_steps: 8
flow: text

---

## Goal

Translate the verified `model.orm.yaml` into a PyRel `model.py`. Mechanical mapping — same as the schema flow's Phase 5 (the YAML is the same format regardless of provenance).

## Inputs

- The Phase 4 YAML (verified, modality-labeled, no proposed remaining)
- `.planning/CONTEXT.md` — target dialect
- Skill: `rai-orm-from-text` — CSDP Step 8 (translate)
- Skill: `rai-pyrel-coding` (auto-loaded — PyRel syntax)

## Tasks

(Identical to the schema-flow Phase 5 — copy-paste of the same translation table. The YAML format does not vary by provenance.)

1. **Emit module preamble.** Imports, dialect declaration, model docstring (sourced from PROJECT.md vision).
2. **Emit one PyRel class per object type.** PascalCase names.
3. **Emit fact-type properties.** Binary fact types → properties; objectified fact types → association classes.
4. **Emit constraints.** Each YAML constraint → PyRel constraint. `alethic` → hard; `deontic` → soft.
5. **Emit subtype hierarchies.** Per the YAML's `subtype_of` and `subtype-partition` fields.
6. **Verify parse.** `python -c "import ast; ast.parse(open('model.py').read())"` must exit 0.
7. **Name agreement.** Every PyRel class ↔ a YAML object type; every PyRel constraint label ↔ a YAML constraint id.

## Tasks NOT in scope

| Skip in Phase 5 | Reason | Picked up in |
|---|---|---|
| Performance tuning | Conceptual modeling, not optimization | Downstream |
| Runtime testing | Requires RAI workload setup | Downstream |
| Documentation generation | Project ends at PyRel source | Downstream |

## Done when

- `model.py` exists at the project root.
- `ast.parse` succeeds.
- Every YAML object type has a corresponding PyRel class.
- Every YAML fact type has a corresponding property.
- Every YAML constraint has a corresponding PyRel constraint declaration.
- SUMMARY.md records the YAML → PyRel mapping line-by-line.

## Verification scope

- All 27 format-spec rules on `model.orm.yaml`.
- PyRel parse check.
- Name agreement.
- If a reference `model.py` exists at `evals/expected/{{PROJECT_NAME}}.py`, an E2 (PyRel-equivalence) diff. Otherwise `skipped (no reference)`.

## After `/gsd:ship 5`

- All five phases archived under `.planning/phases/0N-*/SHIPPED.md`.
- A PR is opened (if git repo) summarizing the E1 verdict, E2 verdict, and any antipatterns.
- The emitted `model.py` is ready to load in RAI.
