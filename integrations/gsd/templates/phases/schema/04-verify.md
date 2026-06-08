# Phase 4 — Verify

verbs: plan, execute, verify, ship
skill: rai-orm-from-schema
srp_steps: 8, 9
flow: schema

---

## Goal

Verbalize the entire model in Halpin-style CNL and walk the user through every `status: proposed` constraint for accept / reject decisions. By the end of this phase, the YAML's `status: proposed` set should be empty (every proposal is now confirmed or rejected, with rejections archived).

This is the **stakeholder-facing phase**. The verbalization is what a non-modeler reads to validate the model.

## Inputs

- The Phase 3 YAML
- `.planning/CONTEXT.md` — terminology preferences (the verbalizer reads these to produce consistent CNL)
- Skill: `rai-orm-from-schema` — Steps 8 (verbalize) + 9 (user decisions)

## Tasks

### Step 8 — Verbalize

1. For each object type, emit a definitional sentence: "An *Entity* is identified by its *property*."
2. For each fact type, emit the reading as a sentence: "Each *Customer* places *Order*." (Use the reading template from the YAML; substitute role-fillers per the `reading:` field.)
3. For each constraint, emit the natural-language form per the constraint type:
   - Uniqueness: "Each *Customer* has at most one *email address*."
   - Mandatory: "Each *Customer* must have at least one *email address*."
   - Value: "*Order amount* is between 0 and 1,000,000."
   - Ring: "If *Employee A* manages *Employee B*, then *Employee B* does not manage *Employee A*."
   - Etc.
4. Write the full verbalization to `.planning/phases/04-verify/model.verbalization.txt`.

### Step 9 — User decisions

1. For each `status: proposed` constraint, present its verbalization + provenance to the user:
   - "Proposed: *Each Customer has at most one email address*."
   - "Source: common-sense library / llm-inferred / sample (size N)"
   - "Rationale (if LLM): *one-sentence justification*"
   - "Accept / Reject / Defer"
2. Apply the user's decision:
   - **Accept** → `status: confirmed`
   - **Reject** → move the constraint to `rejected_proposals` with the rejection reason
   - **Defer** → leave at `status: proposed` and document why in SUMMARY.md (rare; ideally a new probe or new domain dialogue lands later)
3. **Modality decisions.** For each constraint, confirm or override the modality. Default is `alethic`; the user may downgrade to `deontic` for soft rules.

## Tasks NOT in scope

| Skip in Phase 4 | Reason | Picked up in |
|---|---|---|
| PyRel emission | Code generation is its own phase | Phase 5 |
| Re-probing the database | If a new probe is needed, that's a phase rewind, not phase 4 work | (rewind to 3) |
| Schema migration recommendations | This project is conceptual modeling, not refactoring | Out of scope |

## Done when

- `model.verbalization.txt` exists at the project root.
- No constraints remain at `status: proposed` (or any remaining are explicitly listed in SUMMARY.md with a "deferred-because" note).
- Every constraint has a modality label (alethic or deontic).
- The verifier's E1 diff (if a reference solution exists) runs cleanly.
- SUMMARY.md lists: number of proposals accepted, rejected, deferred; any modality overrides.

## Verification scope

- **All 27 format-spec rules.**
- **Verbalization parity**: every fact type and every constraint must have a verbalization that reads as a complete English sentence. The verifier checks for unfilled placeholders (`{X}` that didn't get substituted) and ungrammatical concatenations.
- **No-proposed invariant** (or documented deferrals).
- **E1 diff against `evals/expected/{{PROJECT_NAME}}.orm.yaml`** if present; otherwise reported as `skipped (no reference)`.
