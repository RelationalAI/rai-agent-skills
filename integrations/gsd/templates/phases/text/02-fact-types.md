# Phase 2 — Fact types

verbs: discuss, plan, execute, verify, ship
skill: rai-orm-from-text
csdp_steps: 2, 3
flow: text

---

## Goal

Abstract the Phase 1 elementary facts into **fact types** — predicates with named roles. Populate each fact type with the example instances from Phase 1. Combine redundant types; flag derivations.

By the end of this phase, the YAML carries object types + fact types + sample populations. Constraints come in Phase 3.

## Inputs

- The Phase 1 YAML (object types + fact instances)
- `.planning/CONTEXT.md` — locked vocabulary
- `.planning/phases/01-elementary-facts/DIALOGUE.md` — original expert input
- The domain expert — required for the Discuss step
- Skill: `rai-orm-from-text` — CSDP Steps 2 (draw fact types + populate) and 3 (combine + derive)

## Discuss step (with the expert)

`/gsd:discuss-phase 2`:

1. Present candidate fact types abstracted from Phase 1 instances. For each: "Is this how you'd express it generally? *Each Customer places at most one Order on a given Date.*"
2. Ask for additional example populations: "Can you give me three more Customer-Order pairs?" The populations become the fact type's seed.
3. Identify redundant fact types: when two candidates carry the same information ("Customer has shipping_address" and "Customer's address is shipping kind"), the expert picks the preferred reading; the other is recorded under `rejected_proposals`.
4. Identify derivations: "Order total" — is this derived from line items? If yes, mark the fact type as `derived: true` with `derivation: "sum of line_item.amount where line_item.order = self"` (informal — Phase 5 formalizes).

The dialogue lands in `.planning/phases/02-fact-types/DIALOGUE.md`.

## Plan + Execute

1. **Plan.** For each candidate fact type emerging from Discuss, write a PLAN.md entry: roles, reading template, expected population pattern, redundancy/derivation status.
2. **Execute.** Extend the YAML:
   - `fact_types[]` — one per confirmed candidate
   - Each fact type has `roles[]` (two for now; ternary deferred unless the expert insisted), `reading:` matching the expert's preferred phrasing, `population:` carrying the example instances from Phase 1 + the new ones from Phase 2 Discuss
   - `rejected_proposals[]` carries the redundant alternatives the expert dismissed
3. **Combine.** Where two fact types are exact synonyms after Discuss, fold them into one and migrate the populations.

## Tasks NOT in scope

| Skip in Phase 2 | Reason | Picked up in |
|---|---|---|
| Uniqueness constraints | Step 4 work | Phase 3 |
| Mandatory roles | Step 5 work | Phase 3 |
| Value / set-comparison / subtyping constraints | Step 6 work | Phase 3 |
| Verbalization parity check | Holistic review | Phase 4 |

## Done when

- Every Phase 1 elementary-fact instance is now anchored to a fact type's `population:`.
- Every fact type has a `reading:` confirmed by the expert.
- Redundant candidates are in `rejected_proposals` with the expert's preferred alternative noted.
- Derived fact types are flagged `derived: true` with an informal derivation note.
- SUMMARY.md lists: number of fact types emitted, number of populations, redundancies dismissed, derivations flagged.

## Verification scope

- Format-spec rules **1–13** (structural + identifier integrity + reading/role agreement).
- Every fact type has at least one population instance (otherwise it's a conjecture, not a fact type — flag and either populate or drop).
- Every `reading:` template's `{Type}` placeholder count matches the role count.
