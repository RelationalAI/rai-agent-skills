# Phase 5 — Translate to PyRel

verbs: plan, execute, verify, ship
skill: rai-orm-from-schema
srp_steps: 10
flow: schema

---

## Goal

Translate the verified `model.orm.yaml` into a PyRel `model.py` that loads into RAI. The translation is mechanical — every YAML element maps to a PyRel construct per a fixed table. No new domain judgment happens here.

## Inputs

- The Phase 4 YAML (verified, no `status: proposed` remaining)
- `.planning/CONTEXT.md` — target dialect
- Skill: `rai-orm-from-schema` — Step 10 (translate)
- Skill: `rai-pyrel-coding` (auto-loaded — provides PyRel syntax rules)

## Tasks

1. **Emit module preamble.** Imports, dialect declaration, model docstring (sourced from PROJECT.md vision).
2. **Emit one PyRel class per object type.** Use the `name:` from the YAML; PascalCase.
3. **Emit fact-type properties.** Binary fact types become properties on the owning entity (or association properties for objectified fact types).
4. **Emit constraints.** Each YAML constraint becomes a PyRel constraint declaration. Modality maps: `alethic` → hard constraint; `deontic` → soft constraint (warning).
5. **Emit subtype hierarchies.** Subtype-partitions become subclass declarations with the appropriate partition discipline (exclusive, exhaustive, or both per the YAML).
6. **Verify the output parses.** Run `python -c "import ast; ast.parse(open('model.py').read())"` as a smoke check. If it doesn't parse, fix the translator, not the output.
7. **Name agreement check.** Every class name in `model.py` must appear as an object-type name in `model.orm.yaml`. Every constraint label in `model.py` must trace back to a YAML constraint id.

## Tasks NOT in scope

| Skip in Phase 5 | Reason | Picked up in |
|---|---|---|
| Performance tuning of the PyRel model | Conceptual modeling project, not optimization | Downstream |
| Runtime testing against data | Requires a live RAI workload setup | Downstream |
| API documentation generation | Project ends at PyRel source | Downstream |

## Done when

- `model.py` exists at the project root.
- `python -c "import ast; ast.parse(open('model.py').read())"` exits 0.
- Every YAML object type has a corresponding PyRel class.
- Every YAML fact type has a corresponding property.
- Every YAML constraint has a corresponding PyRel constraint declaration.
- SUMMARY.md records the translation mapping (one line per YAML construct → PyRel construct).

## Verification scope

- All 27 format-spec rules on `model.orm.yaml` (still must hold).
- PyRel parse check (`ast.parse` succeeds).
- Name agreement: every PyRel class ↔ YAML object type; every PyRel constraint ↔ YAML constraint id.
- If a reference `model.py` exists at `evals/expected/{{PROJECT_NAME}}.py`, an E2 (PyRel-equivalence) diff. Otherwise reported as `skipped (no reference)`.

## After `/gsd:ship 5`

- All five phases archived under `.planning/phases/0N-*/SHIPPED.md`.
- A PR is opened (if the project is a git repo) summarizing the E1 verdict, E2 verdict, and the antipattern catalog.
- The emitted `model.py` is ready to load in RAI.
