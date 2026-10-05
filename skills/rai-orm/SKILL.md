---
name: rai-orm
description: Routes ORM 2 model building and incremental improvement from a schema, description, workload or existing ORM YAML with feedback, preserving verification state and reporting blockers; not for the modeling procedures, workload extraction, rewrite checks or compaction themselves.
---

# ORM Modeling — Entry Point and Router
<!-- v1-SENSITIVE -->

## Summary

**What:** Chooses the ORM route, interaction mode and invocation budget, then sequences the owning skills. An existing model resumes from its saved artifacts rather than intake.

**When to use:** The user wants an ORM model and PyRel translation, proof of workload coverage, or improvement of existing ORM YAML using feedback.

**When NOT to use:** A known modeling route without a workload belongs to `rai-orm-from-schema` or `rai-orm-from-text`; direct PyRel building belongs to `rai-build-starter-ontology`; reviewing PyRel without ORM YAML belongs to `rai-ontology-design`; choosing a reasoner belongs to `rai-discovery`.

**Overview:** Resume check → intake if needed → inherited mode and invocation budget → route → run and record steps → report.

## Quick Reference

| Skill / tool | Job | Runs |
|---|---|---|
| `rai-orm-from-workload` | Workload → digest of evidence, consumed as proposals | before new modeling; only delta items on resume |
| `rai-orm-from-schema` | Schema Recovery Procedure (SRP): schema → ORM YAML → PyRel | schema modeling; commit repair batches |
| `rai-orm-from-text` | Halpin's CSDP: description → ORM YAML → PyRel | text modeling; commit repair batches |
| `connectivity.py` | Entity paths, required joins and data-tested link proposals | after modeling; each verification round |
| `rai-orm-verify` | Rewrite, check and repair workload coverage | after modeling; regression acceptance |
| `rai-orm-refactor` | Compact using existing-element paths, retaining verified coverage | after verification; assess drift, apply supported compaction |
| `state.py` | Manifest, finished steps and deterministic resume plan | before intake; after each accepted step |
| `report.py` | Statistics and actionable issues | route close |

Default workload route: **`rai-orm-from-workload` → `rai-orm-from-schema` (+ connectivity) → `rai-orm-verify` ↔ `rai-orm-refactor` → report**. Refactor assessment may keep every concept; candidate batches return through the modeling skill and verification with the same invocation budget.

| Modality | Evidence | Verification oracle |
|---|---|---|
| `sql` | joins, grain, filter columns, expressions | SQL result on source data |
| `questions` | terms, synonyms, expected concepts | user review of a sample |
| `pairs` | both plus alignment within each pair | SQL result and question meaning |

Pairs remain aligned in one artifact. Without reachable, bound data, SQL/pairs use the structural oracle.

| The user has | Route |
|---|---|
| Existing ORM model plus feedback | `state.py plan` → affected proposals → connectivity → `rai-orm-verify` ↔ `rai-orm-refactor` → report |
| Existing ORM YAML with query-shaped concepts, flag explosions, table mirrors or duplicated families | `rai-orm-refactor` → original modeling skill final commit/regeneration → `rai-orm-verify` acceptance → report |
| Schema + workload | default workload route above |
| Schema, no workload | `rai-orm-from-schema` (+ connectivity) → report |
| Description + questions, no schema | `rai-orm-from-text` (questions as CSDP artifacts) → connectivity → `rai-orm-verify` ↔ `rai-orm-refactor` → report |
| Description only | `rai-orm-from-text` → connectivity → report |
| Schema + description | `rai-orm-from-schema`; description enters SRP Step 9d as user-supplied rules |
| SQL or pairs without schema | Obtain DDL or a connection; v0.1 does not recover models from queries alone |
| Only a PyRel model | v0.1 does not import Python into ORM YAML; use the manual path in the hot-start reference or `rai-ontology-design` |

## Instructions

### Step 0 — Resume check

Before intake, if `orm-state.json` or `model.orm.yaml` is in the working directory or named by the user, run `state.py plan` from this skill's `tools/`, using `--state` and `--model-yaml` for named paths. Follow its ordered steps and resolve its blockers before applying candidates. With YAML but no manifest, the read-only plan identifies bootstrap blockers; preserve the files, discover and sandbox-check the project's emitter with `state.py init --emitter`, then plan again. Skill-built models use `--emitter manual:step-10` and the hot-start regeneration checklist. Legacy verification without an exact revision match requires a passed-item baseline recheck before it counts as resumable.

Register all existing artifact paths: `--model-yaml`, `--model-py`, `--digest`, `--repair-digest`, `--holdout-digest`, `--verification`, `--connectivity`, `--report`, `--report-markdown`, `--refactor-before`, `--refactor-metrics`. For `--model-py`, point at the existing generated file, never create a second one. Register source/workload files with repeated `--input`/`--workload`, bindings with `--binding`, and emitter dependencies with `--emitter-file`. The bootstrap blocker lists candidate Python files importing `relationalai.semantics`.

Load [hot-start.md](references/hot-start.md) for the manifest, feedback conversion, frozen passes, workload deltas, N+0 baseline and budget continuation. Reuse the saved split, repair/holdout digests, PyRel and counters. Connectivity uses the repair digest; holdout only measures coverage. Reconcile verification IDs/counts with the workload and resolve regeneration, path, emitter and binding blockers before acceptance. Legacy deltas without old contributions/snapshots need the documented full rebuild fallback. Inherit the mode and budget settings unless the user changes them; record a fresh invocation once with `update --skill rai-orm --start-invocation` and report `rounds_used_this_invocation`. Convert feedback into proposals with `source: user-feedback`; Guided reviews the structured batch before application. In One-shot mode, only required-gap link proposals are applied automatically; exploratory proposals are listed for review and never auto-applied. An existing model skips new-model intake and construction.

### Step 1 — Intake

For a new build, collect only missing facts in one message: schema/DDL/CSV or description; workload modality and file; read-only data access; and whether evaluation items must be sealed from modeling. Pass only repair evidence to modeling.

Ask the invocation budget questions together: rounds (`rounds_per_invocation`, default 5), consecutive rounds without pass-count improvement (`patience`, default 2), and whether to keep going until every item is `pass`, `inexpressible` or `oracle-error` (`until_pass`, default false). With `until_pass: true`, the round limit does not stop verification; patience still does. See the hot-start reference for accounting.

### Step 2 — Mode, chosen once

Choose Guided or One-shot once, default Guided. Every owning skill inherits it in `source.mode` and skips its own mode opener. Resume inherits the manifest's mode.

### Step 3 — Route

Choose the first matching route and state it in one line. Initialize the manifest for a new project once paths, inputs and emitter are known; record each finished step in order with `state.py update`. Never overwrite an existing manifest with `init`.

### Step 4 — Run the route

Hand modeling decisions to their owning skill. Reuse the recorded emitter to regenerate `model.py` from YAML; preserve/recheck source bindings. Validate and re-run connectivity after model changes. `--max-comparisons` defaults to 5000; `COMPARISON_CAP_REACHED` means some candidate links remain untested.

| From | To | What is passed |
|---|---|---|
| `rai-orm-from-workload` | modeling skill | repair-set digest; text modeling uses terms as artifacts |
| modeling skill | connectivity / `rai-orm-verify` | YAML, generated PyRel, bindings, same workload and inherited state |
| `rai-orm-verify` | modeling skill | generic defect proposals with `source: workload`; commit at SRP Step 9f or CSDP Step 7f |
| feedback processing | modeling skill | `source: user-feedback` proposal batch and affected ids; same review/validation/emission path |
| `rai-orm-verify` | `rai-orm-refactor` | YAML/PyRel/bindings, digest/workload, verification report and saved rewrites, mode and remaining budget of this invocation |
| `rai-orm-refactor` | original modeling skill | `provenance.origin: refactor` proposals, affected ids, existing-element path scaffolds and rollback snapshot |
| modeling skill | `rai-orm-verify` | candidate artifacts, unchanged workload/split/oracle; accept only without total or per-split pass-count loss; otherwise restore snapshot |
| accepted steps | state / report | counters, revision, paths, artifact stop reasons and processed feedback hashes |

`rai-orm-verify` owns repair iterations and regression checks. Refactor acceptance shares that invocation budget, including holdout evaluation sealed from repair selection. Read [hot-start.md](references/hot-start.md) before accepting feedback or refactor batches.

### Step 5 — Close

Run `report.py` from this skill's `tools/` with `--model model.orm.yaml`, adding `--verification model.verification.json`, `--connectivity connectivity.json` and `--digest workload.digest.yaml` when available. Show `orm-report.md`. If it starts with `BUDGET_EXHAUSTED`, print that line verbatim first, give the residual count and exact continuation steps from the hot-start reference, and keep the route incomplete. State the invocation's rounds and rounds run in total, oracle and unverified items. Never say “done” while a blocker issue stands.

Use the report's separate `entity_relationships`, `scalar_properties` and `flags` counts. When compaction ran, include before/after concept and flag counts, support coverage, accepted/kept/rolled-back proposals, per-split verified passes, residual classes and remaining suspects. Record report and connectivity paths and stop reasons with `state.py update`. Load [connectivity.md](references/connectivity.md) for islands/required joins and [statistics-and-issues.md](references/statistics-and-issues.md) for issue interpretation.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Starting intake on an existing model | Ignoring saved work | Run Step 0 before routing |
| Patching generated PyRel | Forgetting the project emitter | Edit YAML through the modeling skill and reuse the recorded command |
| Resetting rounds or the split | Treating resume as a new build | Keep N+0 baseline, continue at N+1; fresh budget only for this invocation |
| Rewriting old passes | Confusing regressions with new translations | Freeze saved PyRel; re-run it against candidates |
| Subtracting changed evidence without its old version | Legacy hashes do not preserve source content | Use stored contributions/snapshots, or the explicit full rebuild fallback |
| Modeling inside the router | Treating routing as modeling | Hand proposals to the owning skill |
| Splitting pairs or leaking holdout evidence | Losing input boundaries | Preserve alignment; keep holdout out of repairs |
| Asking mode again | Each skill has an opener | Inherit mode across the route |
| Calling loading or budget exhaustion completion | Ignoring acceptance and blockers | Verify workload, print budget line first, report remaining blockers |

## Examples

| Situation | Route taken |
|---|---|
| Synthetic DDL and query history | default workload route with execution match when bound |
| Description and questions | text modeling → connectivity → verify ↔ refactor → report; name review limits |
| DDL only | schema modeling (+ connectivity) → report |
| Existing campus model stopped at round 5, missing-link feedback | [Worked resume](references/hot-start.md#worked-example-campus): N+0 baseline at 5, next repair 6, saved passes and split retained |

## Reference files

| File | When to load |
|---|---|
| [Hot start](references/hot-start.md) | Step 0, feedback, invocation budgets or continuing after exhaustion |
| [Connectivity](references/connectivity.md) | Before hand-off or when islands/required joins remain |
| [Statistics and issues](references/statistics-and-issues.md) | Route close, especially budget exhaustion |
