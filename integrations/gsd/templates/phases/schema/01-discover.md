# Phase 1 — Discover

verbs: plan, execute, verify, ship
skill: rai-orm-from-schema
srp_steps: 1, 2, 3
flow: schema

---

## Goal

Produce a `model.orm.yaml` *skeleton* containing every object type and every binary fact type derivable from the input schema, with no constraints yet. Constraint lift happens in Phase 2.

## Inputs

- `{{INPUT_PATH}}` — the schema
- `.planning/CONTEXT.md` — locked Halpin posture + project decisions
- `.planning/REQUIREMENTS.md` §R1, §R3 — input format + lift defaults
- Skill: `rai-orm-from-schema` — auto-loaded by Claude Code

## Tasks (for the planner subagent to decompose)

1. **Introspect the schema.** List every table, column, primary key, foreign key, unique constraint, NOT NULL, and CHECK. Do not yet interpret — just inventory.
2. **Classify tables.** Each table is either an *entity table* (becomes an object type) or a *junction table* (objectified fact type — deferred to Phase 2 if necessary, or modeled here if the structure is obvious).
3. **Emit object types.** One ORM 2 object type per entity table. Use the table's natural-language name (PascalCase). Record the identifier scheme: simple (single column → reference mode) or composite (composite-PK → external scheme deferred to Phase 2).
4. **Emit binary fact types from FKs.** Each FK becomes a binary fact type with two roles: the referencing entity and the referenced entity. Give it a `reading:` ("Each {A} has at most one {B}" or similar; refine later).
5. **Emit binary fact types from non-FK columns.** Each non-FK, non-PK column becomes a binary fact type from the entity to its value type.
6. **Flag deferrals.** Anything not handled (composite keys, junctions worth objectifying, CHECK constraints): note in `SUMMARY.md` for Phase 2 pickup.

## Constraints to NOT emit yet

| Skip in Phase 1 | Reason | Picked up in |
|---|---|---|
| Uniqueness constraints | Lifted from PK/UC in DDL | Phase 2 |
| Mandatory roles | Lifted from NOT NULL | Phase 2 |
| Value constraints | Lifted from CHECK | Phase 2 |
| Sample-source constraints | Require probing | Phase 3 |
| Common-sense library proposals | Require population | Phase 3 |
| LLM-tier proposals | Require Phase 3 review | Phase 3 |

## Done when

- `.planning/phases/01-discover/model.orm.yaml` exists with `version: 1`, `source: { kind: relational-schema, introspected_at: <date>, dialect: <from-CONTEXT> }`, populated `object_types` and `fact_types`, and `constraints: []`.
- Every table in the input has a corresponding object type (or is documented as deferred).
- Every FK in the input has a corresponding binary fact type.
- `SUMMARY.md` lists what was emitted, what was deferred, and why.

## Verification scope (what `rai-orm-verifier` checks here)

- Format-spec rules **1–13** (structural + identifier integrity + reading/role agreement).
- Object-type count ≈ entity-table count (with deferred junctions noted).
- Fact-type count ≈ FK count + non-FK-non-PK column count.
- Constraints list is empty (or trivially so — anything sneaking in is a Phase-1-out-of-scope signal).
