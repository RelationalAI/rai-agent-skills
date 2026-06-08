# Phase 2 — Lift explicit constraints

verbs: plan, execute, verify, ship
skill: rai-orm-from-schema
srp_steps: 4
flow: schema

---

## Goal

Extend the Phase 1 YAML with **every constraint derivable mechanically from the DDL** — primary keys, unique constraints, NOT NULLs, CHECK constraints, composite identifiers. All emitted with `source: explicit, status: confirmed`.

By the end of this phase, the YAML carries every constraint the DDL author actually wrote down. Phase 3 will then *infer* further constraints from data and common-sense.

## Inputs

- `.planning/phases/01-discover/model.orm.yaml` (or project-root `model.orm.yaml` if Phase 1 wrote there)
- `.planning/REQUIREMENTS.md` §R3 — the lift rules table (PK → preferred UC, NOT NULL → mandatory, etc.)
- `.planning/CONTEXT.md` — confirms the dialect and any locked overrides
- The input schema `{{INPUT_PATH}}`
- Skill: `rai-orm-from-schema` — uses Step 4 of the SRP

## Tasks

1. **Lift PKs.** For each entity's PK, emit a uniqueness constraint scoped to the entity's identifying fact type(s). Mark `preferred: true`. Composite PKs become a top-level UC over the relevant role refs + an entity `reference.mode: external`.
2. **Lift UNIQUE constraints (non-PK).** Each UNIQUE on a column or column group becomes a UC over the corresponding fact-type role(s).
3. **Lift NOT NULL.** Each NOT NULL on a non-PK column becomes a mandatory role on the corresponding fact type's entity-side role.
4. **Lift CHECK constraints.** Categorize each CHECK:
   - **Range / enum-like** → value constraint on the value type
   - **Cross-column comparison** → ring constraint (if pattern matches) or note as `source: explicit` "complex" constraint
   - **Untranslatable** → record verbatim in YAML's `raw_check:` field; the verbalizer will pass through
5. **Objectify junctions.** Any junction table flagged in Phase 1 becomes an objectified fact type (`objectified_as:` pointing to the junction's role tuple).
6. **Provenance discipline.** Every constraint emitted here has `source: explicit`, `status: confirmed`, `provenance: { ddl_anchor: <table.constraint_name or column>, lifted_at: <date> }`.

## Tasks NOT in scope

| Skip in Phase 2 | Reason | Picked up in |
|---|---|---|
| Sample-derived UCs | Require live probe | Phase 3 |
| Mandatory roles inferred from common sense | Library lookup | Phase 3 |
| Subtype detection | Population analysis | Phase 3 |
| Antipattern flagging | Catalog scan | Phase 3 |
| Verbalization parity check | Holistic review | Phase 4 |

## Done when

- Every PK, UNIQUE, NOT NULL, and CHECK in the input schema has been either (a) lifted into a constraint with `source: explicit`, or (b) recorded as "deferred to Phase 3" in `SUMMARY.md` with a reason.
- Junctions are objectified (or documented as "kept relational" with a reason).
- The YAML still parses against `representation-format.md`.
- `SUMMARY.md` lists each lifted constraint by DDL anchor → ORM target.

## Verification scope

- Format-spec rules **1–13** (from Phase 1) plus:
- Rules **14–16** (constraint placement: inline vs top-level).
- Rule **24** (`source: explicit` constraints have `status: confirmed`).
- Spot-check: number of UCs ≈ number of PKs + UNIQUEs in DDL.
- Spot-check: number of mandatory roles ≈ number of NOT NULL columns in DDL.

Note: not running all 27 rules here because the inference-source rules (17–19, 25–27) are vacuously satisfied when there are no inferred constraints yet.
