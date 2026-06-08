# Phase 1 — Elementary facts

verbs: discuss, plan, execute, verify, ship
skill: rai-orm-from-text
csdp_steps: 1
flow: text

---

## Goal

With the domain expert, verbalize **concrete, atomic example facts** drawn from the domain. By the end of this phase, the project has a locked vocabulary and a corpus of sample fact instances that subsequent phases mine for fact types.

> *"Each Customer has email EmailAddress."* — that is an elementary fact. Concrete, atomic, no compound assertions. Phase 2 abstracts these into fact types.

## Inputs

- `{{INPUT_PATH}}` (optional starting document — domain description, requirements doc, interview notes)
- `.planning/CONTEXT.md` — Halpin posture, locked vocabulary so far (may be empty at first run)
- The domain expert — required for the Discuss step
- Skill: `rai-orm-from-text` — CSDP Step 1

## Discuss step (with the expert)

`/gsd:discuss-phase 1` runs an interactive dialogue. The script:

1. Read `{{INPUT_PATH}}` (if present) and extract candidate noun phrases.
2. For each candidate, ask the expert: "Is this a thing in your domain? What do you call it?"
3. Ask the expert to produce 5–10 *concrete example facts* covering the key concepts. Avoid abstractions ("Customers have orders" — too general) in favor of specifics ("Customer 'Acme Corp' placed Order #1234 on 2026-04-01").
4. For each elementary fact the expert offers, verbalize it back: "So you'd say: *Customer Acme Corp placed Order 1234.*" Get confirmation.
5. Build the locked vocabulary: every entity term, every relationship term, every value type. Record under "Domain vocabulary" in `.planning/CONTEXT.md`.

The output of Discuss lands in `.planning/phases/01-elementary-facts/DIALOGUE.md`.

## Plan + Execute

After Discuss closes:

1. **Plan.** Decompose the dialogue into proto-object-types (the recurring nouns) and proto-fact-instances (the verbalized example sentences). The planner subagent writes this to `.planning/phases/01-elementary-facts/PLAN.md`.
2. **Execute.** Emit a partial `model.orm.yaml` with:
   - `source: { kind: text-conversation, dialogue_anchor: DIALOGUE.md, frozen_vocab_at: <date> }`
   - `object_types[]` — one per recurring entity term, with `name:` matching the expert's vocabulary
   - `fact_instances[]` (text-flow extension) — the verbalized example facts, anchored to the dialogue
   - No `fact_types[]` yet — Phase 2 abstracts those
   - No `constraints[]` yet

## Tasks NOT in scope

| Skip in Phase 1 | Reason | Picked up in |
|---|---|---|
| Drawing fact types | Requires the abstraction step | Phase 2 |
| Population checks | Phase 2 populates fact types | Phase 2 |
| Any constraint | Constraints come from data + expert confirmation | Phase 3 |

## Done when

- `DIALOGUE.md` exists in the phase folder, capturing the Discuss transcript.
- `CONTEXT.md` has a populated "Domain vocabulary" section with at least the core nouns.
- `model.orm.yaml` exists with object types named per the expert and fact_instances anchored to the dialogue.
- SUMMARY.md lists: how many elementary facts elicited, how many distinct nouns / verb-phrases identified, any vocabulary tensions flagged for Phase 2.

## Verification scope

- Format-spec rules **1–10** (structural + identifier integrity, modified for text-flow's `source.kind: text-conversation`).
- Every object type has a vocabulary anchor in `CONTEXT.md`.
- Every fact instance verbalizes as a complete English sentence (no unfilled placeholders).
- No `fact_types[]` or `constraints[]` snuck in — those would be out-of-scope Phase 1 work.
