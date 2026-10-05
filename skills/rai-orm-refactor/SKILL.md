---
name: rai-orm-refactor
description: Compacts an existing ORM ontology when workload repairs produce query-shaped concepts, flag explosions, table mirrors or duplicated families while preserving verified answerability, not for model building (rai-orm-from-schema, rai-orm-from-text), the rewrite check (rai-orm-verify), or review of non-ORM PyRel models (rai-ontology-design).
---

# ORM Ontology Compaction
<!-- v1-SENSITIVE -->

## Summary

**What:** Measures an ORM ontology, tests suspect concepts against paths through existing fact types, and proposes a smaller business ontology without reducing workload coverage. A path scaffold is PyRel-shaped pseudo-code, not an executed rewrite or proof of result equivalence.

**When to use:** An existing `model.orm.yaml` has drifted after workload repairs: one concept per question, many flags, table mirrors, or duplicated families.

**When NOT to use:** Building a model belongs to `rai-orm-from-schema` or `rai-orm-from-text`; checking rewrites belongs to `rai-orm-verify`; reviewing a PyRel model without an ORM stage belongs to `rai-ontology-design`.

**Overview:** Measure → select suspects → scaffold existing paths → propose a batch → commit through the modeling skill and reverify → compare metrics. Low support ranks a concept for review; it never justifies removing a business entity by itself.

## Quick Reference

| Input / output | Purpose |
|---|---|
| `model.orm.yaml`, `model.py`, binding and verbalization | Existing ORM model and generated artifacts |
| Optional `model.verification.json` and its saved PyRel | Baseline pass counts and concept support |
| Optional `workload.digest.yaml` and its workload artifacts | Structural evidence and item specifications |
| `compaction.before.json`, `compaction.after.json` | Counts, names, ranked hints and scan coverage |
| `refactor-proposals.yaml`, `refactor-paths.md` | Proposed batch, provenance and per-item scaffolds |
| `ontology-notes.md` | Reasons for keeping suspects and verification limits |

Run from the skill directory, using model paths for the working model:

```sh
python tools/compaction_metrics.py --model /work/model.orm.yaml \
  --verification /work/model.verification.json --digest /work/workload.digest.yaml \
  --out /work/compaction.before.json
```

| Decision | Gate |
|---|---|
| Remove / merge | Every affected item has an existing-element path; domain facts and identity remain represented |
| Keep | A needed step, identity, role, constraint or source population would be lost |
| Accept batch | Modeling validation and regeneration succeed; every unchanged baseline-passing id stays passing with unchanged oracle and weak accounting |
| Roll back | Any unchanged baseline pass is lost, either split loses passes, or the check cannot establish the same baseline |

## Instructions

**Modes:** Inherit `source.mode` and the route's mode. If unset, default to Guided. Guided shows one concrete proposal batch and its scaffolds for review, then uses the modeling skill's acceptance step. One-shot applies the candidate as `proposed` and emits `# REVIEW PROPOSAL` through the modeling skill; successful verification does not confirm a domain rule. Questions without review remain `unverified` in One-shot.

**Dependencies:** Use `rai-pyrel-coding` and `rai-querying` for actual operator syntax, the original modeling skill for YAML representation and emission, and `rai-orm-verify` for the acceptance check. Read-only source access, split, oracle, weak matches and retry limits remain owned by `rai-orm-verify`.

### Step 1 — Measure and establish the baseline

The router first invokes an **assessment only** pass (`rai-orm-refactor:assess`) after connectivity and before verification: measure and list suspects, make no model changes, and spend no rounds. Write `compaction.after.json` with `--model-revision` set to `baseline_model_revision` from `state.py plan`; a matching revision lets the router skip this assessment. Acceptance (`rai-orm-refactor:accept`) follows verification and has its own `refactor_rounds` allowance (default 2 per invocation).

Run `tools/compaction_metrics.py` on the YAML; pass the verification report and digest when available. PyRel paths in the report resolve relative to that report. Load [compaction-metrics.md](references/compaction-metrics.md) to interpret counts and reason codes. Missing PyRel means support is unavailable, not zero.

Before any candidate edits, establish a current `rai-orm-verify` baseline against this model revision and the same workload. Reuse a report only when its revision, binding, workload, split and oracle match. Record repair and holdout pass counts, passed item ids, weak passes and exclusions. Snapshot the YAML, generated Python, verbalization, binding files, report and saved rewrites so a rollback restores one consistent revision.

If no workload or usable verification oracle exists, measurements and proposals can be delivered; keep the model unchanged and state that acceptance is pending verification. Never treat an unverified baseline of zero as proof of preservation.

### Step 2 — Pick suspects

Use the ranked `suspects` list to choose a bounded batch (default: at most five concepts). Combine entries for the same concept. Inspect each concept's roles, identifier, bindings, derivation, constraints and domain evidence before deciding whether it is query-shaped. Zero workload support, no table binding, and a one-table binding are not removal criteria. Load [refactor-patterns.md](references/refactor-patterns.md) for the matching symptom and tests.

### Step 3 — Scaffold every affected item

For each suspect, list every item that uses it. Start with the saved PyRel; if absent, use the item's SQL/question in the original artifact named by the digest or verification report, matched by id. The digest holds no SQL/question text; its structural entries locate evidence, not full item specifications. Inspect remaining repair items for uses that the static scan missed; do not assume partial support is exhaustive.

Write each scaffold in `refactor-paths.md` using [orm-path-scaffold.md](references/orm-path-scaffold.md). Name the entity ids, fact type ids, role directions, property ids, operator sequence, result grain and output columns. Use parameter names in place of literals. For entity removal, exclude the suspect and its proposed replacements from the available elements: otherwise the test is circular. For flag compaction, retain the business entity and exclude the flag family being replaced. Every entity, property and relationship in the scaffold resolves against the existing YAML and generated model; local refs and aggregate expressions are allowed, new model declarations are not.

Preserve the verifier's holdout isolation: it may scaffold and check affected holdout items as a sealed acceptance exercise, but their question text, failure details and scaffolds do not guide proposal selection or repair. Require its coverage attestation for those items before accepting the batch. If any affected item's use or path cannot be established, keep the suspect pending evidence.

### Step 4 — Decide and record proposals

When every affected item has a path, propose removing or merging the suspect, retaining its information as a derived fact type, value type, subtype or path as appropriate. First ensure the ontology still expresses its domain facts, identifiers, source population distinctions, constraints and non-workload uses. A scaffold demonstrates expressibility; it does not decide that a business entity is expendable.

If any item needs an absent element or the domain needs the concept's identity, keep it and record the blocking element ids and general reason in `ontology-notes.md`. Never invent a concept to match one item's phrasing. Names come from schema, domain documentation or the digest's terms.

Every proposal in `refactor-proposals.yaml` carries `provenance.origin: refactor`, status, affected YAML ids, item ids/counts, the pattern, and scaffold references. Deletions retain their provenance in this ledger. New or changed object/fact types carry `provenance.origin: refactor` plus `provenance.refactor` pointing to the proposal id and prior origin; retain original binding and evidence fields. Constraint `source` stays in the modeling format's vocabulary: workload-backed new constraints use `source: workload`, `status: proposed`, and its required verification provenance. Do not introduce `source: refactor` or rewrite existing constraint evidence.

### Step 5 — Apply, hand back to verification, accept or roll back

Apply the reviewed/proposed batch in a candidate revision through `rai-orm-from-schema` SRP Step 9f or `rai-orm-from-text` CSDP Step 7f. Run that skill's representation validation, resolve dangling roles, subtype references, objectifications, references and constraints, then regenerate `model.verbalization.txt` and `model.py` through its translation step. Restore/recheck bindings for the regenerated model. Edit the YAML via this procedure, never patch `model.py` independently.

Hand the candidate and same workload to `rai-orm-verify`. Re-run every item, including previous passes and the holdout. For removals, merges, flag replacements and renames, use the candidate-rewrite migration procedure in [refactor-patterns.md](references/refactor-patterns.md). Keep original passing files until candidate files verify equivalent; rewrites cannot bypass the ontology through source tables. Keep the baseline oracle, split, exclusions and weak-pass accounting fixed. Changing a prior pass to an exclusion or unverified status is a loss, not preservation.

Accept only if every unchanged baseline-passing id remains passing, with unchanged oracle, split and weak-pass accounting; also preserve total/per-split pass counts and exclusions. Equal totals cannot compensate for a lost pass (including a same-split pass swap). Run `python tools/acceptance.py --baseline baseline.verification.json --candidate candidate.verification.json`; acceptance requires exit 0 plus modeling validation and executed oracle checks. A scaffold alone cannot accept a batch. If verification fails, is incomplete, or downgrades the oracle, restore the snapshot including generated files, bindings and saved rewrites; record the rejected batch and counts. Verifier repairs cannot be used to silently reintroduce query-shaped concepts; reassess such a batch.

Bound compaction to `refactor_rounds` (default 2 attempts per invocation); stop earlier when no supported proposal remains or two consecutive batches yield no accepted metric improvement. Count accepted and rolled-back attempts with `state.py update --skill rai-orm-refactor --rounds-done 1`; assessment costs zero. Refactor never consumes verify rounds, nor verify refactor rounds. Do not reset the allowance per batch. If either budget expires, report **budget exhausted** prominently with verified counts, residual classes and remaining suspects; do not imply completion.

### Step 6 — Report before / after

Rerun the metrics on the accepted model (or restored baseline after rejection). Report concept count, per-table counts, property distribution, unary flag counts, unbound/derived-only counts, support coverage, single-item counts, duplicate groups, flag explosions, table mirrors and remaining suspects. Compare only support counts with comparable PyRel coverage.

State accepted/kept/rolled-back proposals, baseline and final pass counts for each split, oracle, weak passes, residual failures and stop reason. Fewer concepts is useful only with preserved business meaning and verified coverage. List any pending proposals separately from accepted batches.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Deleting a single-item business entity | Confusing support with domain importance | Test paths and identity; keep domain facts |
| Using the suspect in its own scaffold | Circular proof | Remove it from the available-element inventory |
| Inventing `.path()`, `.exists()` or SQL escape hatches | Pseudo-code treated as an API | Use existing relation applications and documented operators |
| Replacing independent flags with one enum | Assuming mutual exclusion | Verify exclusivity, completeness and NULL behavior first |
| Merging directory and registered populations | Similar keys treated as identical grains | Preserve population membership and identifier multiplicity |
| Treating a scaffold as an execution pass | No result comparison | Hand the committed candidate to `rai-orm-verify` |
| Promoting refactor proposals automatically | A successful query treated as a domain rule | Keep One-shot proposals marked for review |
| Hiding a verification budget stop | A bounded loop mistaken for completion | Report budget exhaustion and residual counts prominently |

## Examples

| Example | Shows |
|---|---|
| [Path scaffolds](references/orm-path-scaffold.md) | Three worked existing-element paths using the synthetic campus fixture |
| [Synthetic compaction model](evals/fixtures/compact/model.orm.yaml) | Query-shaped concept, flags, table mirror and healthy entity |
| [Eval cases](evals/cases.json) | Preservation, rollback, privacy and routing checks |

## Reference files

| File | When to load |
|---|---|
| [compaction-metrics.md](references/compaction-metrics.md) | Step 1 — metric definitions, scan limits and default thresholds |
| [orm-path-scaffold.md](references/orm-path-scaffold.md) | Step 3 — grammar, operators, existing-element audit and worked paths |
| [refactor-patterns.md](references/refactor-patterns.md) | Steps 2–4 — choose a pattern and its preservation tests |

See [rai-orm](../rai-orm/SKILL.md) for the router's existing refactor wiring.
