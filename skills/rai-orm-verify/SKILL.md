---
name: rai-orm-verify
description: Verifies workload rewrites against an ORM-derived PyRel model, repairs defects through its YAML and reports connectivity and budget exhaustion when an existing model must answer SQL, questions or pairs; not for building models (rai-orm-from-schema, rai-orm-from-text), extracting workload evidence (rai-orm-from-workload), or routine query writing (rai-querying).
---

# Workload Verification of an ORM Model
<!-- v1-SENSITIVE -->

## Summary

**What:** The acceptance test of an ORM model. A model that loads is not yet a model that answers. This skill rewrites the user's workload in PyRel against `model.py`, checks every rewrite against an oracle, classifies each failure, repairs the *model* (not the query) through `model.orm.yaml`, and repeats until the workload passes or a stop condition is met. Output is `model.verification.json` plus one PyRel file per item.

**When to use:**
- An ORM model exists (from `rai-orm-from-schema` or `rai-orm-from-text`) and the user has SQL, questions, or pairs it must answer
- The user asks whether the model is "right", "complete", or "ready"
- A model was changed and the workload must be re-checked

**When NOT to use:**
- No model yet — see `rai-orm-from-schema` or `rai-orm-from-text`, or `rai-orm` to pick
- Extracting evidence from the workload before modeling — see `rai-orm-from-workload`
- Writing one PyRel query for its own sake — see `rai-querying` and `rai-pyrel-coding`
- Reviewing a PyRel model that did not come through an ORM YAML — see `rai-ontology-design`

**Overview:**
1. Resume saved verification state when present; otherwise take the model/workload and decide the oracle
2. Preserve the existing repair/holdout split; create it only for a new workload
3. Rewrite each item in PyRel and check it
4. Classify the failures
5. Repair the model through the YAML, generically
6. Re-run, including the items that passed before
7. Stop on pass, plateau, or budget; report

## Quick Reference

**Oracle by modality and data access:**

| Workload | Data reachable, model bound to it | No data, or model not bound |
|---|---|---|
| `sql` | **Execution match**: the PyRel result equals the SQL result | **Structural**: the PyRel compiles, and every table, column and join of the SQL is reached through the model |
| `pairs` | Execution match, and the PyRel's verbalization says what the question asks | Structural, and the verbalization check |
| `questions` | **User review**: the PyRel runs; the user verifies a sample of verbalized rewrites | User review; the PyRel only compiles |

The report always names the oracle used. A structural or user-review pass is never reported as an execution match.

**Item status:**

| Status | Meaning |
|---|---|
| `pass` | Checked against the oracle and accepted |
| `fail` | Rewritten but rejected by the oracle, or not rewritable; carries a failure class |
| `inexpressible` | The SQL uses something PyRel cannot express; not a model defect |
| `oracle-error` | The SQL itself fails or is not deterministic; not a model defect |
| `unverified` | `questions` only: rewritten and runs, but not in the sample the user reviewed |

**Core principle: fix the model, not the query.** A rewrite that needs a trick to get around the model is a failure of the model. Repairs go into `model.orm.yaml` and `model.py` is regenerated from it.

## Inputs and Outputs

**Inputs:**
- `model.orm.yaml` and `model.py` (and the data binding, when there is one).
- The workload file, in one modality (`sql`, `questions`, `pairs`). The same file that was given to `rai-orm-from-workload`, when that skill ran.
- Read-only access to the source data, when it exists.
- On resume: `orm-state.json`, prior `model.verification.json`, its saved PyRel and the recorded project emitter command. Inherit mode, oracle, split and invocation budget from state.

**Outputs:**
- `model.verification.json` — format in [`references/report-format.md`](references/report-format.md).
- `verification/<item id>.py` — the accepted PyRel for each item. These double as worked query examples for the model.
- `connectivity.json`, `connectivity.proposals.yaml`, `orm-report.json`, `orm-report.md` — graph evidence, proposed links, and statistics with actionable issues.
- A revised `model.orm.yaml`, `model.verbalization.txt` and `model.py` when repairs were made.

## Instructions

**Required dependencies:** `rai-pyrel-coding` and `rai-querying` for writing and running the PyRel. The modeling skill that produced the model, for committing repairs.

**Read-only rule:** the source data is never written. SQL from the workload is run only as a query, with a row cap and a time cap.

### Resume mode — before Step 1

When verification/state already exists, use `rai-orm`'s resume plan and hot-start protocol. Read the previous verification report before writing anything: retain all rounds and repairs, append an invocation entry, and continue repair numbers from the last global round N at N+1. Establish N+0 as the unchanged model baseline at round N; baseline checks consume no repair round. Snapshot YAML, generated artifacts, bindings, report and saved rewrites together. Inherit the saved oracle and mode; a weaker oracle needs explicit resolution, not silent replacement.

Keep every prior `pass` and its accepted PyRel as the baseline regression inventory. Validate saved paths before candidates. Reset only the invocation's attempt allowance and patience streak. Resume at classification/repair of unresolved items; skip workload extraction and split construction for unchanged inputs. For workload deltas, preserve surviving assignments and old rounds under `rai-orm`'s delta protocol.

### Step 1 — Oracle

Pick the column of the oracle table from two facts: is the source data reachable, and is `model.py` bound to it (it defines its concepts from the source tables, so a PyRel query returns real rows)? The ORM skills emit an unbound `model.py`; binding it is done with `rai-pyrel-coding`'s data loading before this skill runs. If either is missing, use the structural column and tell the user that the check is weaker.

### Step 2 — Repair set and holdout

On resume, read `split` and every `items[].split` from the previous file and **never recompute the split**. Count-only legacy splits are recoverable only from saved item assignments; missing assignments block repair until the original split is restored.

For a new workload only, with 30 or more items, set aside 20% as a **holdout** before anything is run: sort the item ids and take every fifth. The holdout is rewritten and checked like the rest, but its failures are never looked at when repairing the model. Its pass rate tells whether the repairs generalize or were fitted to the items. With fewer than 30 items there is no holdout; say so in the report.

### Step 3 — Rewrite and check

At the start of **each round**, run `connectivity.py` from `rai-orm` with the current YAML and `--digest repair.digest.yaml` (state artifact `repair_digest`); produce it with the workload tool's `--split repair --verification model.verification.json`. Never substitute the aggregate `workload.digest.yaml` when a holdout exists. Register `holdout.digest.yaml` (`holdout_digest`), produced with `--split holdout --verification model.verification.json`, for measurement only; add read-only `--db` access when available. Follow the connectivity procedure in `rai-orm`; use its recorded connectivity path and `--max-comparisons` (default 5000). Record components, isolated concept ids and required gap ids in that round's `connectivity` block. Check holdout reachability separately; never use holdout gaps or proposals to choose repairs. A repair-set workload join with no graph path is `missing-element`, even before its rewrite runs. A join between tables feeding the same concept is `merged`, not a gap.

For each item:

1. For a prior `pass`, load its saved PyRel unchanged and run it only as a regression check; do not create a fresh translation. For unresolved/new items, write the PyRel against `model.py`. For `sql`, the SQL is the specification. For `pairs`, the question is the specification and the SQL says what the answer's columns and meaning are. For `questions`, the question is all there is.
2. Run it. On an error, fix the PyRel and retry, at most 4 runs per item per round.
3. Check it:
   - **Execution match** — run the SQL read-only and compare the two result sets:
     ```
     python tools/compare_results.py --expected sql_result.csv --actual pyrel_result.csv [--ordered]
     ```
     Columns are matched by content, not by name or position. Rows are compared as a multiset; `--ordered` only when the SQL has ORDER BY and the question depends on the order. Numbers match within a relative tolerance of 1e-6.
   - **Structural** — list the tables, columns and join edges of the SQL; each must be reached by the PyRel through a concept, a fact type and a relationship of the model.
   - **Verbalization** (`pairs`, `questions`) — state in one sentence what the PyRel returns, in the model's readings. For `pairs`, it must say what the question asks.
   - **User review** (`questions`) — see Step 3b.
4. Save an accepted rewrite as `verification/<item id>.py`. Keep prior accepted rewrites intact while testing candidates; renamed-element adaptations are explicit candidate copies until accepted.

An empty result on both sides is a weak match: mark the item `pass` with `weak: true`, and do not count it as evidence that a repair worked.

### Step 3b — User review for `questions`

The user cannot review everything, so they review a sample that covers the model:
- **Guided:** show 5 to 10 items, chosen so that together they touch as many different concepts and relationships as possible, each as: the question, the one-sentence verbalization of the PyRel, and (when data exists) the first rows. Ask for yes / no / "not what I meant" per item. A "no" is a `fail`; ask what was meant, in one line.
- **One-shot:** write the same sample to `verification/review.md` and mark every item `unverified`.

Items outside the sample stay `unverified`. They are never reported as passed.

### Step 4 — Classify failures

Each `fail` gets one class from [`references/failure-classes.md`](references/failure-classes.md). The class says where the repair goes:

| Class | Repair goes to |
|---|---|
| `translation` | The PyRel rewrite; no model change |
| `missing-element` | The YAML: an object type, fact type or relationship is absent |
| `grain` | The YAML: a concept merges or splits rows differently from how the workload uses the table |
| `binding` | The data binding: rows or values are lost between table and concept |
| `derivation` | The YAML: a derived fact type the workload uses is absent |
| `naming` | The YAML: readings or role names hide the element from a reader of the question |
| `semantics` | The rewrite or the YAML: NULL, duplicate, or join-kind behavior differs |

Classify from the evidence (the diff of the two results, the element that could not be reached), not from the item's wording. Required connectivity gaps are always `missing-element`, never `translation`. For other unclear failures after one look, mark them `translation` and let the retry cap decide.

### Step 5 — Repair, generically

Group the repair-set failures by class and by the model element involved. Repair a **group**, never one item:

- State the defect without reference to any item: *"concepts fed by two tables cannot return the rows of one table"*, not *"question 17 needs TABLE_X"*.
- Change `model.orm.yaml`. New object types and fact types carry `provenance.origin: workload`; new constraints carry `source: workload, status: proposed`. Provenance records the failure class and the number of items, never an item's text (see `representation-format.md`, `source: workload`).
- For required connectivity gaps, add the data-tested link proposal with `source: data`, `status: proposed` and `provenance.evidence`. Preserve `partial: true` and overlap counts for partial candidates; probe and review untested or zero-overlap candidates before applying them. Re-run connectivity after repair. An unjustified missing path remains `missing-element`.
- **Guided:** show the round's repairs as one batch for the user to accept or reject, as in SRP Step 9b. **One-shot:** apply them as `proposed`, with `# REVIEW PROPOSAL` in `model.py`.
- Commit through the modeling skill's final step (SRP Step 9f or CSDP Step 7f), so the YAML validates, then regenerate `model.verbalization.txt` and `model.py` with the recorded project emitter command. Reuse that command and restore/recheck bindings; a missing emitter blocks repairs.

A group with a single item is repaired only when the defect is plainly general. Otherwise it is left as residual and reported.

Names must come from the schema, the domain documentation, or the digest's terms. Do not invent a name to match one question's phrasing.

### Step 6 — Re-run

After each model revision, re-run every item against the same split and oracle: new/unresolved rewrites and prior passes using their saved PyRel. Count a prior pass becoming excluded or `unverified` as a **regression**. A round that causes more regressions than it fixes is rolled back to the consistent snapshot, including saved rewrites and bindings; retain the attempted round and rollback evidence in history.

For a `rai-orm-refactor` candidate, re-run the baseline workload including prior passes and sealed holdout. Report total/per-split passes, regressions, fixes, weak passes and exclusions. Accept only when total and each split's verified pass counts do not drop and regressions do not exceed fixes; otherwise restore the consistent snapshot. Share the remaining budget of this invocation across all refactor hand-backs; do not reset it for each batch. Keep holdout failure details/scaffolds out of proposal selection.

### Step 7 — Stop and report

Read `rounds_per_invocation` (default 5), `patience` (default 2) and `until_pass` (default false) from state. Stop when the first applicable condition holds:

- every workload item, including holdout, is `pass`, `inexpressible` or `oracle-error`;
- `patience` consecutive attempts do not increase repair-set verified passes (weak empty matches do not demonstrate improvement);
- with `until_pass: false`, the budget of this invocation has run `rounds_per_invocation` repair/acceptance attempts.

With `until_pass: true`, continue beyond the finite round allowance until the all-item terminal condition or patience stops the loop. Unreviewed questions remain `unverified`. Count attempted/rolled-back rounds and refactor acceptance rounds; baseline N+0 costs no repair round. A fresh invocation resets the allowance and patience streak while global round numbers continue. A sealed holdout failure may prevent all-pass but never supplies repair evidence.

Write `model.verification.json`, retaining prior rounds, connectivity blocks, split assignments, pass metadata and saved PyRel paths. Append `invocations: [{started_round, rounds_run, stopped_because}]`; report rounds run in this invocation and in total. Use the [report format](references/report-format.md) for legacy migration and accounting. Record the finished step with `state.py update` from `rai-orm`.

Run `report.py` from `rai-orm` with `--model model.orm.yaml --verification model.verification.json --connectivity connectivity.json`, adding `--digest` when available (use recorded paths). Show `orm-report.md` and follow `rai-orm`'s statistics-and-issues reference. When the budget of this invocation is exhausted with residual failures, **lead with the first `BUDGET_EXHAUSTED` line verbatim**, including residual count and continuation action. Use `rai-orm`'s hot-start continuation protocol for the fresh invocation. Keep the run incomplete while blocker issues remain; name the oracle and its limits.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Resetting split or round numbers on resume | Treating a fresh invocation budget as a new model | Read the prior file; use N+0 baseline and N+1 next repair |
| Rewriting passed items on resume | Retrying every translation | Reuse saved PyRel as regression checks; snapshot candidate adaptations |
| Patching `model.py` | It is the file that runs | Repair the YAML and regenerate |
| A clever query that works around the model | Wanting the item to pass | That is a model failure; classify and repair |
| A repair that names an item | Fixing the symptom | State the defect without the item; repair the group |
| Looking at holdout failures | They are in the same file | The holdout is checked, never read for repairs |
| Counting empty-equals-empty as proof | Both sides returned nothing | `weak: true`; not evidence |
| Calling a structural pass "verified" | No data was reachable | Report the oracle by name |
| Marking unreviewed questions as passed | They ran without error | `unverified` until the user saw them |
| Running workload SQL that writes | A log holds every statement | SELECT only, row cap, time cap |
| Calling a required join gap a translation error | Retrying a rewrite against disconnected concepts | Classify `missing-element`; propose the link with overlap evidence. |
| Burying budget exhaustion in statistics | Treating the stop as completion | Show the report's budget line first, with residual count and continuation step. |

## Examples

| Example | Shows |
|---|---|
| Campus fixture from `rai-orm-from-workload` | A model with three planted defects (an undeclared join, a grain trap, a missing derived measure) and the workload that exposes them; setup in [eval cases](evals/cases.json) |

## Reference files

| File | When to load |
|---|---|
| [`references/failure-classes.md`](references/failure-classes.md) | Step 4 — classifying a failure and choosing the repair |
| [`references/report-format.md`](references/report-format.md) | Step 7 — writing `model.verification.json` |
| [Resume accounting](references/report-format.md#resume-and-invocation-accounting) | Before a resumed invocation — preserve split, history and saved passes |

Load `rai-orm` for hot-start, connectivity and statistics-and-issues procedures; load `rai-orm-from-schema` for the representation format and workload provenance.
