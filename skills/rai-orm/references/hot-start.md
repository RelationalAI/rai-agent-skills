# Hot start: incremental ORM work

Load before resuming an existing ORM YAML, converting feedback, or continuing after `BUDGET_EXHAUSTED`. v0.1 preserves an existing model and its evidence; the router delegates all model changes to the original modeling skill.

## Resume protocol

1. Run `state.py plan` from `rai-orm`'s tools before intake. Paths resolve relative to the manifest's directory, which is the project working directory. Named YAML is passed as `--model-yaml`; named manifests as `--state`. Set `--model-py` to the existing generated file, never create a second one. The `PYREL_REQUIRED` blocker lists candidate `*.py` files importing `relationalai.semantics`. A plan without a manifest is read-only bootstrap discovery. Preserve the existing YAML, Python, digest, binding, verbalization, verification file, split and saved rewrites.
2. For bootstrap, inspect the project to find its **emitter command**. Register its complete command with `init --emitter`, and additional emitter dependencies with repeated `--emitter-file`. Before accepting it, `init` runs that exact command in a temporary copy of the project under an OS sandbox: writes are restricted to the copy and network access is denied. Generated Python must be byte-identical and YAML plus all digest hashes unchanged. `EMITTER_NOT_IDEMPOTENT` refuses a destructive recovery command; `EMITTER_UNVERIFIED` records failure or an unavailable sandbox and blocks application. Resolve the command/dependencies and retry `update --skill rai-orm --emitter '...'`. Never run an unverified recovery command against the project. Skill-built models instead record `manual:step-10` and follow the checklist below; do not invent an emitter script.
3. Initialize once with all source filenames, workload files and existing artifact paths. `--input` records schema/document inputs; `--workload` additionally records per-item hashes and an immutable private copy in `.orm-workloads/`, keyed by its SHA256. Both flags repeat. Register binding files with repeated `--binding`; their paths/hashes participate in the verification revision. Supply the mode and budget. `--skill` repeats to seed known historical order; otherwise the tool infers available prior steps from artifacts. It never invents absent historical rounds. `init` refuses to overwrite a manifest; use `update` thereafter.
4. Read the plan's blockers and feedback. Convert free text as below. Review workload deltas before candidates. Restore lost baseline artifacts, split assignments or oracle instead of silently replacing them. A changed model/binding, or a legacy verification file without an exact revision match, requires a baseline regression recheck with the saved PyRel and same oracle; the old verified passes remain the acceptance floor.
5. Snapshot YAML, Python, verbalization, binding, digest, verification and saved rewrites together before proposals. Establish the resumed baseline as **round N+0**, meaning round N (the last recorded global round) with the old model, not a new round numbered 0. Preserve that history row and mark it as the invocation baseline; if rechecked, retain its original evidence and record baseline-check counts separately. Baseline checks cost no repair round. Next repair is N+1. Never overwrite prior rounds or discard verified passes to make a candidate look better.
6. Follow the plan: connectivity before verification, then refactor assessment/acceptance and report. Skip intake, full schema recovery and unchanged digest extraction. A clean current model with current verification, connectivity, refactor metrics and both report files can have an empty plan; the manual sentinel always lists its checklist step. Without a workload, verification is skipped; refactor can measure/propose but cannot accept compaction without a usable baseline oracle. For each candidate use the modeling skill's final review, YAML validation, verbalization and recorded emitter. Restore/recheck bindings before acceptance. Saved passed PyRel is run as regression checks; only unresolved items need new rewrites. Rename adaptations are explicit candidate files until accepted.
7. Repairs with more regressions than fixes roll back the consistent snapshot. A prior pass becoming an exclusion or `unverified` counts as a regression. Refactor additionally requires total and each split's verified pass counts not to drop, using the same workload, split, oracle and weak-pass accounting. Holdout remains sealed from proposal selection. A rollback never updates state to the rejected revision.
8. After each accepted finished step, `update` records skill/order, rounds done, stop reason and current revision. Mark feedback processed only after review and its disposition is recorded (accepted, rejected or retained as a pending proposal). Rejected items remain in the proposal ledger; their hashes prevent repeated presentation. Keep pending proposals visible in the report. Run the final report and record its paths/stop reason even when verification stops incomplete.

```sh
# Run from the project directory; substitute the installed tool path.
python /path/to/rai-orm/tools/state.py init \
  --input schema.sql --workload workload.pairs.json --mode guided \
  --model-py beaver_model.py --binding bindings.py \
  --emitter 'python emit_model.py --model model.orm.yaml --out beaver_model.py' \
  --rounds-per-invocation 5 --patience 2
python /path/to/rai-orm/tools/state.py plan --feedback feedback.yaml
python /path/to/rai-orm/tools/state.py update --skill rai-orm-verify \
  --rounds-done 2 --stop-reason plateau
python /path/to/rai-orm/tools/state.py update --skill feedback \
  --feedback feedback.yaml --feedback feedback.processed.yaml --feedback feedback.md
```

Pass only existing feedback files to `update`; omission is valid. Tools use the project Python environment. The command string contains file arguments only, never credentials, SQL literals or question text.

## State manifest and plan

`orm-state.json`, version 1, has no generated timestamps. JSON keys and output lists are stable, so unchanged `plan` runs are byte-identical. `plan` writes nothing. `init`/accepted workload updates write the manifest and immutable private workload snapshots; emitter registration also runs the sandbox check in a temporary copy. The tools do not import Python models or apply feedback.

| Manifest field | Meaning |
|---|---|
| `version` | Manifest format version, currently 1 |
| `inputs` | `{path, kind, sha256}`; workload inputs add `item_hashes: {id: sha256}` and `snapshot_path`; no source contents in the manifest |
| `mode` | `guided` or `one-shot`, inherited across skills |
| `budget` | `rounds_per_invocation`, `patience`, `until_pass` |
| `model_revision` | SHA256 over YAML/Python and registered binding file hashes; no timestamps added to hashed metadata |
| `artifacts` | Paths: `model_yaml`, `model_py`, `digest`, `repair_digest`, `holdout_digest`, `verification`, `connectivity`, `report`, `report_markdown`, `refactor_before`, `refactor_metrics` |
| `emitter_command` | Checked project command line, or `manual:step-10` |
| `emitter_files`, `emitter_check`, `bindings` | Registered paths/fingerprints, sandbox check result, binding paths/fingerprints |
| `emitted_facts`, `emitted_py_sha256` | Fact fingerprints and generated-file hash at the last accepted emission |
| `invocation_started_round`, `rounds_used_this_invocation` | Start recorded on first update; used rounds exclude the N+0 baseline |
| `skills_run` | Ordered finished steps with `skill`, `rounds_done`, `stop_reason`, `model_revision`; repeats preserve iteration order |
| `round_counters` | Cumulative per-skill counters; verify retains last global repair-round number |
| `artifact_hashes` | Current artifact file hashes, `null` when absent |
| `artifact_stop_reasons` | Connectivity verdict or `COMPARISON_CAP_REACHED`, report status, refactor stop reason when recorded |
| `verification_revision` | Model hash at the last accepted verification; intervening step updates do not suppress a needed baseline recheck |
| `verification_snapshot` | Exact prior split and oracle, item ids/status/split, saved PyRel paths/hashes and pass metadata |
| `last_stop_reason` | Last finished step's reason; verification's reason remains in its report/history |
| `feedback_processed` | Processed filenames and SHA256; structured files add item fingerprints for deduplication |

CLI artifact flags use the field name with hyphens: `--model-yaml`, `--model-py`, `--digest`, `--repair-digest`, `--holdout-digest`, `--verification`, `--connectivity`, `--report`, `--report-markdown`, `--refactor-before`, `--refactor-metrics`.

**Legacy builds.** File hashes prove identity, not verified behavior. Missing saved PyRel hashes are recorded without altering the verification file, but a build without an exact recorded `model_revision` match always gets `BASELINE_RECHECK_REQUIRED` and `can_resume: false`. Re-run passed items against the current YAML/Python/bindings with the original oracle and split. Record the plan's `baseline_model_revision` in the verification file's top-level `model_revision` (or latest round's `model_revision` when the top-level field is absent), only after successful checks, then `update --skill rai-orm-verify`. Unrelated updates cannot clear the baseline requirement.

The current verification file's `pyrel` reference is resolved and hashed on every plan. A changed path blocks even when its content is identical. After an explicit verified adaptation, record each passed item's current `pyrel_sha256` and current `model_revision`, then use `update --skill rai-orm-verify --accept-pyrel-paths`. Ordinary updates cannot silently accept a path change. Missing/altered content, lost passes and changed surviving split assignments remain blockers.

Reconcile verification against registered workload IDs before acceptance: missing items appear in `missing_item_ids` and schedule verification; duplicate IDs, removals, digest/workload counts and split counts block completion until reconciled. A missing verification row is not an implicit pass.
The JSON plan includes `steps` in order, `baseline_round`, `started_round` (next repair), `baseline_recheck`, budget/mode, `frozen_passed_items`, saved PyRel inventory, `new_feedback_items`, feedback file hashes, workload delta ids, `stale_artifacts` and blockers. Changed digest evidence schedules connectivity/verification; changed ancillary artifacts refresh the report. Missing emitter/YAML/Python, lost digest/verification/PyRel, missing or altered split assignments/oracle or unstructured markdown block candidate application. Malformed feedback produces `FEEDBACK_INVALID {path,item_index,field}` (zero-based item index, `null` for document errors); unresolved targets produce `FEEDBACK_TARGET_UNKNOWN`. Malformed workloads produce `WORKLOAD_INVALID {path}`. Planning continues without echoing source text; a malformed manifest produces `STATE_INPUT_INVALID`. A plan with blockers is still printed, with `can_resume: false`; the agent resolves them before executing dependent steps.

Connectivity uses `--max-comparisons 5000` by default. `COMPARISON_CAP_REACHED` records untested candidate counts: raise the cap or run focused probes, retaining that stop reason in state. Report statistics use `entity_relationships` (entity-to-entity), `scalar_properties` and `flags` separately. `report`/`report_markdown` locate `orm-report.json`/`orm-report.md`; both supplement the verification history.

## Regeneration gate and manual Step 10 checklist

`plan` checks that registered emitter files still exist and match their fingerprints. Binding changes invalidate verification even after an unrelated update. After applying fact types, regenerate and require both a changed generated-file hash and each applied fact's exact ID or reading in that Python. `EMITTER_INCOMPLETE` blocks an ignored fact; add the emitter's declaration metadata `pyrel: {owner, property, kind, target}` using its actual schema, then regenerate. An unrelated Python change is insufficient.

For `emitter_command: "manual:step-10"`, `plan` accepts the sentinel and lists `manual:step-10` instead of requiring a script. Perform this checklist before recording a modeling update:

1. Validate the current YAML through the original modeling skill and refresh verbalization.
2. Apply schema Step 10's translation rules to the whole current YAML, writing to the recorded `model_py` path. Point at the existing generated file, never create a second one.
3. Preserve/recheck every source binding; retain review/provenance markers. Include each applied fact's ID or reading in its declaration or adjacent comment.
4. Check that applied fact changes changed the generated hash and appear in Python. Resolve `EMITTER_INCOMPLETE` before acceptance.
5. Re-run saved passes and revised workload items with the same split/oracle; record the current verified revision before the verification update.

## Repair and holdout digests

Register `repair.digest.yaml` as `repair_digest` and `holdout.digest.yaml` as `holdout_digest`. Produce them using the workload tool's `--split repair --verification model.verification.json` and `--split holdout --verification model.verification.json`; use `--ids FILE` for delta extraction. Connectivity and verify Step 3 use **only the repair digest**. Holdout digest reachability measures sealed coverage and never selects repairs. Keep `workload.digest.yaml` as the aggregate inventory/report artifact. Reconcile item counts separately for each split.

In One-shot mode, automatically apply only required-gap link proposals; list exploratory proposals for review and never auto-apply them.

## Feedback format

`feedback.yaml` has `version: 1` and `items`. An `id` is optional: absent ids are deterministically derived from the item's hash. Concept targets use exact model names; rename destinations may be new names. Names and ids are identifiers, never data values. Validate targets against the YAML before proposing changes. Each item is a proposal with `source: user-feedback`, `status: proposed`, not an automatically confirmed constraint.

```yaml
version: 1
items:
  - id: f01
    kind: missing_link
    from: Enrollment
    to: Student
  - id: f02
    kind: wrong_grain
    concept: Student
  - id: f03
    kind: failing_item
    ids: [p07, p08]
```

| `kind` | Required fields | Modeling action |
|---|---|---|
| `missing_link` | `from`, `to` | Probe and propose a fact type/path; names alone do not establish an FK |
| `wrong_grain` | `concept` | Review identity/population and grain evidence |
| `merge` | `concepts` (at least two) | Propose compaction with existing paths and identity preservation |
| `split` | `concept` | Review distinct grains/populations; optional `concepts` names proposed parts |
| `rename` | `from`, `to` | Propose rename; migrate saved rewrites explicitly and verify |
| `failing_item` | `ids` | Inspect unresolved repair-set items under the verifier's oracle |
| `compact` | `concept` | Send suspect to refactor assessment, not automatic deletion |
| `note` | none; optional `text` | Agent reads locally and proposes only supported structured actions |

Optional free text goes in `feedback.md`. The **agent**, not the tool, reads it, extracts concrete actions, resolves names against the model and writes `feedback.processed.yaml` in this same format. Keep uncertain statements as `note`; avoid inventing relationships or constraints. In **Guided**, show the structured items to the user and obtain review before applying. In **One-shot**, keep proposals marked for review. After conversion/review is complete and recorded, mark `feedback.md` processed with `update --skill feedback --feedback feedback.md`, then plan with the structured file; do not mark the structured actions processed until their dispositions are recorded.

The tools output ids, names, counts, paths and hashes only. They never echo `note.text`, markdown, SQL literals, question text or data values. Extra structured fields contribute to the item's fingerprint but are not echoed; keep detailed reasoning locally in the reviewed proposal ledger. Feedback affecting a holdout item is retained for sealed evaluation only: it does not enter repairs. New proposals keep `source: user-feedback` in the feedback ledger; preserve existing constraint-source vocabulary in model YAML (feedback-based domain constraints use `user-supplied`, and remain proposed pending the modeling review). This distinction preserves format compatibility without laundering feedback into workload evidence.

Refactor changes carry `provenance.origin: refactor` and `provenance.refactor: {proposal_id, previous_origin, yaml_ids, item_ids, support}` on object/fact types; preserve original bindings/evidence. Deletions retain provenance in `refactor-proposals.yaml`. New workload-backed constraints use `source: workload` and its required provenance, never `source: refactor`. Use `provenance.tables` for merged bindings while retaining singular `provenance.table` compatibility. Accept batches through SRP Step 9f or CSDP Step 7f, validate and regenerate through the recorded emitter with One-shot review markers intact. Verification never confirms a domain rule.

## Workload delta

A changed input file hash is reported as a **workload delta** and blocks blind resume (`WORKLOAD_DELTA_REVIEW`). For tracked workloads, per-item hashes yield added, removed and changed ids. Changed ids are removed old specifications plus new specifications under the same id; only `redigest_item_ids` (new or changed ids) need extraction. Byte-only changes with identical item hashes yield an empty extraction list. Original source schema/document changes additionally block as `INPUT_CHANGED`; reconcile their model implications explicitly.

1. Keep a snapshot of the old digest, workload inventory and verification. Review `new_item_ids`, `removed_item_ids`, `changed_item_ids` and the source hashes.
2. Extract **only** new/changed repair-set items through `rai-orm-from-workload`. Keep unaffected per-item evidence and subtract removed/changed items' old contributions before adding the new evidence. Use the immutable `snapshot_path` to reconstruct old removed/changed contributions when needed. Legacy manifests with neither a valid old snapshot nor stored `item_contributions` receive `WORKLOAD_FULL_REBUILD_REQUIRED`: do not subtract using the changed source. Fully rebuild both split digests from the current inventory and preserved assignments, recheck the revised inventory, and explicitly accept with `--accept-workload-delta --full-rebuild`. Holdout evidence stays separate.
3. Preserve every surviving id's repair/holdout assignment, even if changed; archive removed ids and their history. Assign genuinely new ids once under the existing split rule and record explicit item assignments. Changed item specifications invalidate their old passes, but unchanged passed ids remain frozen. Preserve round history. Do not recompute a split over the new sorted workload.
4. Run baseline checks for the revised inventory, reconcile digest and verification counts, then record the accepted delta using `update --skill rai-orm-from-workload --accept-workload-delta`. This explicit flag advances workload hashes; ordinary updates do not. Original schema/document changes require restoring the input or a reviewed replacement manifest with archived old history; do not silently bless a changed schema.
5. Plan again and continue at the old next round. If init lacked `--workload`, the tool cannot infer precise item deltas from aggregate digest counts: register a preserved original workload inventory before relying on delta detection. Ids must be unique across workload files. Prefer explicit ids; positional `i0001` ids match the digest reader, but inserting an item can invalidate subsequent positional ids.

## Invocation budget and continuation

**Budget always means the budget of this invocation.** `rounds_per_invocation` defaults to 5; `patience` defaults to 2; `until_pass` defaults to false. Baseline N+0 does not consume a repair round. Each repair/acceptance attempt, including rolled-back candidates and refactor hand-backs, consumes one numbered round; never reset the allowance for a batch. Global rounds remain monotonic across invocations.

Stop at the first applicable condition: every workload item (including sealed holdout) is `pass`, `inexpressible` or `oracle-error`; `patience` consecutive attempts fail to increase repair-set passes; or, when `until_pass` is false, this invocation has run `rounds_per_invocation` attempts. Reset the patience streak at invocation start, never history. `until_pass: true` continues beyond the finite round allowance until the all-item terminal condition or patience stops it; unreviewed questions remain `unverified`, so user review can still be needed. Weak empty matches do not demonstrate improvement. Evaluate stop conditions in this order; reaching the round limit on an all-pass candidate is an all-pass stop.

After `BUDGET_EXHAUSTED`, follow these exact steps:

1. Print the first budget line of `orm-report.md` verbatim, residual count and oracle. Leave all artifacts and the manifest in place.
2. Run `state.py plan --state orm-state.json` with any new feedback. Resolve blockers; keep the old split and saved passed PyRel. With no manifest, bootstrap once using the preserved artifacts and emitter as above.
3. Confirm/inherit this invocation's settings. Start the fresh invocation once with `state.py update --skill rai-orm --start-invocation`; subsequent updates retain its start. To change settings at that start, add `--rounds-per-invocation 5 --patience 2 --no-until-pass` (or `--until-pass`). The first update automatically records the start when none exists; the plan prints `rounds_used_this_invocation`. A larger allowance is optional: another invocation already gets a fresh allowance.
4. Snapshot the old model and use last global round N as N+0. Convert/review feedback, run required connectivity, then enter `rai-orm-verify` at Step 4/5 with the previous verification report. Append `invocations: [{started_round: N+1, rounds_run: ..., stopped_because: ...}]`; retain all prior invocation entries. No repairs means `rounds_run: 0`.
5. Re-run frozen passes as regression checks, attempt unresolved-item repairs at N+1, and count only this invocation's attempts. Assess refactor; acceptance checks share the remaining allowance. Record finished steps and hashes with `update`.
6. Run `report.py` with the preserved/current artifacts. Print the budget line first if exhausted again, then this invocation's rounds and total rounds. Report blockers and residuals explicitly; never claim completion while a blocker stands.

## Python without YAML

**v0.1 does not import `model.py` into ORM YAML.** A Python-only resume is blocked by `YAML_REQUIRED`; do not execute or introspect the Python to manufacture an ORM representation.

Manual path: preserve `model.py` and bindings as the reference, obtain its schema/domain artifacts, and use `rai-orm-from-schema` or `rai-orm-from-text` to author and review `model.orm.yaml`. Manually reconcile identities, roles, source bindings and constraints with the reference; register a checked YAML emitter or `manual:step-10` with its checklist. Validate the YAML and compare its generated Python and workload coverage with the preserved reference before initializing a new manifest. If the user only wants to review existing PyRel, route to `rai-ontology-design` instead.

## Worked example: campus

Use the existing synthetic campus fixture from `rai-orm-from-workload`. Copy its schema and `workload.pairs.json` into a separate project directory. Suppose a prior schema-built model has a digest, a recorded emitter, accepted rewrites, the original no-holdout split (12 items), rounds 0–5 and `summary.stopped_because: budget`. Preserve all those artifacts. Feedback identifies the planted missing Enrollment–Student link:

```yaml
version: 1
items:
  - id: campus_link
    kind: missing_link
    from: Enrollment
    to: Student
```

Run `init --input schema.sql --workload workload.pairs.json --emitter 'python emit_model.py --model model.orm.yaml --out model.py'` once, using the actual project emitter, then `plan`. A legacy report first requires the N+0 recheck and verified revision acceptance above. The plan retains round 5 as N+0, starts repairs at 6, lists `campus_link` with `source: user-feedback`, freezes existing passed ids and saved PyRel, and schedules connectivity → verify → refactor → report. The unchanged workload yields no re-digestion. Removing the emitter from state makes the plan blocked.

In Guided, review the feedback batch, probe the fixture's `ENROLLMENT.LEARNER_NO`/`STUDENT.ID` candidate and preserve overlap counts (no values) in the proposed fact type. Commit/validate through schema modeling and run the recorded emitter. Verification uses the same no-holdout assignments and oracle, appends round 6 and the second invocation entry, retries unresolved items and runs saved passes as regressions. Reject a repair with more regressions than fixes. Refactor assesses drift and accepts only candidates preserving total/per-split coverage, within this invocation's allowance. Run the report, distinguishing entity relationships, scalar properties and flags; if residuals remain at the limit, its first line is `BUDGET_EXHAUSTED` and the next invocation continues from the recorded last round.
