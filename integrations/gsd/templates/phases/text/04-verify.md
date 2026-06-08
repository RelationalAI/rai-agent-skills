# Phase 4 — Verify

verbs: plan, execute, verify, ship
skill: rai-orm-from-text
csdp_steps: 7
flow: text

---

## Goal

Walk the entire model's verbalization with the domain expert and label modality (alethic vs deontic) for every constraint. By the end of this phase, the YAML is *frozen* for translation — every status is `confirmed`, every modality is labeled.

> Phase 4 has no Discuss verb because Phase 3 already concluded the expert dialogue. Phase 4's expert interaction is *read-the-verbalization-aloud*, not new elicitation. If new questions surface, they're a phase rewind, not phase 4 work.

## Inputs

- The Phase 3 YAML
- `.planning/CONTEXT.md` — terminology preferences + locked domain vocabulary
- The domain expert — for verbalization review (not Discuss-formatted; informal walk-through)
- Skill: `rai-orm-from-text` — CSDP Step 7 (final review + modality)

## Tasks

### Verbalize

1. For each object type, emit a definitional sentence using the expert's vocabulary.
2. For each fact type, emit the reading with sample fillers from the population.
3. For each constraint, emit the natural-language form (see the schema-flow `04-verify.md` for the per-constraint forms — they're identical).
4. Write the full verbalization to `.planning/phases/04-verify/model.verbalization.txt`.

### Review with expert

1. Walk the verbalization with the expert. For each sentence:
   - "Does this read as how you'd say it?" — confirm fluency.
   - "Is this true?" — confirm content.
2. For each constraint:
   - "Is this *must* (alethic) or *should* (deontic)?" Label accordingly in the YAML.
   - "Are there exceptions?" — if yes and the expert can articulate them, downgrade to deontic.
3. Any constraint the expert challenges goes to `status: under_review` and is documented in SUMMARY.md. Likely a phase-3 rewind to re-elicit.

## Tasks NOT in scope

| Skip in Phase 4 | Reason | Picked up in |
|---|---|---|
| New constraint elicitation | If new constraints needed, rewind to Phase 3 | (rewind) |
| PyRel emission | Code phase | Phase 5 |
| Schema deployment | This is a conceptual modeling project | Out of scope |

## Done when

- `model.verbalization.txt` exists at the project root.
- Every constraint has a modality label (alethic or deontic).
- No constraints remain at `status: proposed` (or any remaining are flagged for Phase 3 rewind in SUMMARY.md).
- Expert has signed off on the verbalization walk.
- SUMMARY.md captures: walk duration, expert acceptance ratio, any rewind-flagged items.

## Verification scope

- **All 27 format-spec rules.**
- **Verbalization parity**: every fact type and every constraint must have a verbalization that reads as a complete English sentence; the verifier checks for unfilled `{X}` placeholders and ungrammatical concatenations.
- **No-proposed invariant** (or documented rewinds).
- **E1 diff against `evals/expected/{{PROJECT_NAME}}.orm.yaml`** if present; otherwise `skipped (no reference)`.
