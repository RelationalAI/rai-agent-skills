# Phase 3 — Infer

verbs: plan, execute, verify, ship
skill: rai-orm-from-schema
srp_steps: 5, 6, 7
flow: schema

---

## Goal

Add constraints that the DDL didn't capture but the data, the common-sense catalog, and (optionally) the LLM tier suggest. Also flag antipatterns. The YAML grows from "what the DDL said" to "what the model probably ought to be."

This is the **judgment phase**. Everything emitted here starts at `status: proposed` (except sample-derived constraints from saturated probes, which can go straight to `confirmed`). Phase 4 is where the modeler accepts or rejects.

## Inputs

- The Phase 2 YAML
- `.planning/REQUIREMENTS.md` §R4, §R5 — antipattern handling + LLM-tier policy
- `.planning/CONTEXT.md` — modality default + `enable_llm_tier` flag
- The schema `{{INPUT_PATH}}` and, if available, a live DB connection or data sample
- Skill: `rai-orm-from-schema` — Steps 5 (probe), 6 (infer), 7 (antipattern detect)

## Tasks

### Step 5 — Sample probing

If a live SQL connection or representative data sample is available:

1. For each fact type, probe role uniqueness: count distinct vs total over the corresponding column(s). Saturated probes (distinct = total over a non-trivial sample) propose a UC with `source: sample, status: confirmed`.
2. For each role, probe optionality: count nulls. Saturated non-null over the sample proposes mandatory with `source: sample, status: confirmed`.
3. Record probe metadata: `provenance: { sample_size: N, queried_at: <date>, query_anchor: <sql snippet> }`.

If no sample is available, skip Step 5 entirely. Note this in SUMMARY.md.

### Step 6 — Common-sense library + LLM tier

1. **Library lookup (Step 6a-c).** For each value type and entity-property pattern, look up `rai-orm-from-schema/references/common-sense-library.md`. Apply matching library proposals with `source: common-sense, status: proposed`.
2. **LLM tier (Step 6d) — only if `enable_llm_tier: yes` in CONTEXT.md.** For each fact type, ask the LLM to propose plausible constraints not yet in the YAML. Record each proposal with `source: llm-inferred, status: proposed`, and crucially `provenance.rationale_world_fact: <one sentence>` — without this rationale, the proposal MUST be discarded.
3. **6d spot-check.** For each LLM-tier proposal, surface it inline to the user with the rationale and ask "accept / reject / defer-to-phase-4." The user's answer is recorded in the YAML's `status` field. (This is the inline UX moment from walkthrough §4.)

### Step 7 — Antipattern detection

1. Run the antipattern catalog (`rai-orm-from-schema/references/antipattern-catalog.md`) against the current YAML.
2. For each match, annotate the offending object/fact type with `warning: <pattern-id>` and append a `proposed_resolution:` entry.
3. If `R4 antipattern_auto_resolution: apply`, apply the proposed resolution and record the change in SUMMARY.md.

## Tasks NOT in scope

| Skip in Phase 3 | Reason | Picked up in |
|---|---|---|
| Verbalization parity check | Holistic review | Phase 4 |
| Modality labelling (alethic vs deontic) | Late binding, done at verify | Phase 4 |
| PyRel translation | Code emission is its own phase | Phase 5 |

## Done when

- Every fact type has been probed (where data is available) and library-checked.
- LLM-tier proposals (if enabled) have been surfaced and either accepted, rejected, or deferred.
- Antipatterns have been flagged with `warning:` and (per policy) auto-resolved.
- The YAML conforms to `representation-format.md` for **all 27 rules** — including the provenance and status-consistency rules.
- SUMMARY.md lists: probes run, library proposals applied, LLM proposals (with disposition), antipatterns found, resolutions applied.

## Verification scope

- **All 27 format-spec rules.** Phase 3 is the first phase where every rule is in scope, because every source tier (sample, common-sense, llm-inferred) may have produced output here.
- Provenance rules (16–19) get particular attention: every inferred constraint must have a populated `provenance` block per its source type, and `llm-inferred` constraints must have `rationale_world_fact`.
- Status-consistency rules (24–27): explicit/user-supplied are confirmed; library/llm-inferred start proposed; sample is confirmed only on saturated probes.
