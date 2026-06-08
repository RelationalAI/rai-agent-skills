# Phase 3 — Constraints

verbs: discuss, plan, execute, verify, ship
skill: rai-orm-from-text
csdp_steps: 4, 5, 6
flow: text

---

## Goal

Add **all the constraints** the domain expert can confirm: uniqueness, mandatoriness, value/range, set-comparison, subtyping, ring patterns. Plus apply the common-sense library and (optionally) the LLM-tier proposals.

This is the longest and most expert-dependent phase. Plan a real time budget — Step 6 in particular involves walking every fact type with the expert.

## Inputs

- The Phase 2 YAML (object types + fact types + populations)
- `.planning/CONTEXT.md` — modality default + `enable_llm_tier`
- The domain expert — required for Discuss
- Skill: `rai-orm-from-text` — CSDP Steps 4 (uniqueness + arity), 5 (mandatory + logical derivations), 6 (value + set-comparison + subtyping)

## Discuss step (with the expert)

`/gsd:discuss-phase 3` is the methodologically richest dialogue in the project. Organized in three movements:

### Step 4 movement — uniqueness + arity

For each fact type:

1. "Is this fact-type role unique per the other role? E.g., does each Customer have at most one EmailAddress?" Record the expert's answer + any nuance ("primary email — yes; alternate emails — no, those are separate facts").
2. "Is the arity right? Should this be ternary instead of binary?" (Rare; flag if it comes up.)

### Step 5 movement — mandatory + derivations

For each role:

1. "Is this role mandatory? Must every Customer have at least one EmailAddress?" Record the answer.
2. "Are any fact types logically derived? E.g., Customer.is_premium derived from Order count?" Confirm derivations flagged in Phase 2 and find new ones.

### Step 6 movement — value + set + subtypes

For each value type and entity-attribute pattern:

1. **Value constraints.** Ranges, enums, regex patterns. "Is OrderAmount always positive? Is Country one of these 50 codes?"
2. **Set-comparison.** Subset, exclusion, equality between fact types. "Every Manager is an Employee?" (subset). "An Order's billing_address and shipping_address can be the same — overlap allowed?"
3. **Subtyping.** "Are there kinds of Customer? Individual vs Corporate? Exhaustive? Exclusive?"
4. **Ring constraints.** Reflexivity, symmetry, etc. on same-type binary fact types. "If A reports to B, does B not report to A?" (irreflexive + asymmetric).
5. **6d LLM spot-check (if enabled).** After library lookups, the LLM proposes additional constraints with `rationale_world_fact`. Each is surfaced inline: "I'd suggest — *each Order has at most one PaymentMethod* — because in commerce domains payment is typically singular per transaction. Accept / reject / defer?"

Dialogue lands in `.planning/phases/03-constraints/DIALOGUE.md`.

## Plan + Execute

1. **Plan.** For each Discuss outcome, write a PLAN.md entry mapping the expert's answer to a YAML constraint declaration.
2. **Execute.** Extend the YAML:
   - Constraints from Step 4 dialogue → `source: user-supplied, status: confirmed` (expert told us directly)
   - Constraints from library lookups → `source: common-sense, status: confirmed` (library was right when expert confirmed) or `status: rejected` (expert overrode the library)
   - Constraints from LLM tier → `source: llm-inferred` with `rationale_world_fact:` populated, and `status: confirmed | proposed | rejected` per the expert's spot-check answer
3. Run the antipattern catalog over the YAML and annotate any matches.

## Tasks NOT in scope

| Skip in Phase 3 | Reason | Picked up in |
|---|---|---|
| Verbalization parity check | Holistic review | Phase 4 |
| Modality labelling (alethic vs deontic) | Late binding | Phase 4 |
| PyRel translation | Code phase | Phase 5 |

## Done when

- Every fact type's role uniqueness has been answered by the expert.
- Every role's mandatoriness has been answered.
- Value constraints, subtypes, ring constraints, set-comparisons identified by the expert are in the YAML.
- LLM-tier proposals (if enabled) have been disposed.
- Antipatterns flagged.
- SUMMARY.md catalogs: number of UCs, mandatories, value/ring/subset constraints; library hits; LLM proposals (with dispositions).

## Verification scope

- **All 27 format-spec rules.** Like the schema flow Phase 3, this is the first text-flow phase where every rule is in scope.
- Particular attention to provenance rules (16–19): every confirmed constraint has the right `source` + populated `provenance`.
- Status-consistency rules (24–27): user-supplied is confirmed; common-sense / llm-inferred follow the expert's spot-check answer.
