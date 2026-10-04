---
name: rai-orm-verify
description: Verifies an ORM-derived PyRel model against a workload by rewriting each item — SQL query, natural-language question, or question+SQL pair — in PyRel, checking it (result match with the SQL on the source data, or user review of a sample when there is no SQL), and repairing the model through its ORM YAML until the workload can be rewritten. Use after an ORM model exists and the user has queries or questions it must answer — not for building the model (rai-orm-from-schema, rai-orm-from-text), extracting evidence before modeling (rai-orm-from-workload), or routine PyRel query writing (rai-querying).
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
1. Take the model, the workload, and decide the oracle
2. Split the workload into a repair set and a holdout
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

**Outputs:**
- `model.verification.json` — format in [`references/report-format.md`](references/report-format.md).
- `verification/<item id>.py` — the accepted PyRel for each item. These double as worked query examples for the model.
- A revised `model.orm.yaml`, `model.verbalization.txt` and `model.py` when repairs were made.

## Instructions

**Required dependencies:** [`rai-pyrel-coding`](../rai-pyrel-coding/SKILL.md) and [`rai-querying`](../rai-querying/SKILL.md) for writing and running the PyRel. The modeling skill that produced the model, for committing repairs.

**Read-only rule:** the source data is never written. SQL from the workload is run only as a query, with a row cap and a time cap.

### Step 1 — Oracle

Pick the column of the oracle table from two facts: is the source data reachable, and is `model.py` bound to it (it defines its concepts from the source tables, so a PyRel query returns real rows)? The ORM skills emit an unbound `model.py`; binding it is done with `rai-pyrel-coding`'s data loading before this skill runs. If either is missing, use the structural column and tell the user that the check is weaker.

### Step 2 — Repair set and holdout

With 30 or more items, set aside 20% as a **holdout** before anything is run: sort the item ids and take every fifth. The holdout is rewritten and checked like the rest, but its failures are never looked at when repairing the model. Its pass rate tells whether the repairs generalize or were fitted to the items. With fewer than 30 items there is no holdout; say so in the report.

### Step 3 — Rewrite and check

For each item:

1. Write the PyRel against `model.py`. For `sql`, the SQL is the specification. For `pairs`, the question is the specification and the SQL says what the answer's columns and meaning are. For `questions`, the question is all there is.
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
4. Save an accepted rewrite as `verification/<item id>.py`.

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

Classify from the evidence (the diff of the two results, the element that could not be reached), not from the item's wording. When the class is unclear after one look, mark it `translation` and let the retry cap decide.

### Step 5 — Repair, generically

Group the repair-set failures by class and by the model element involved. Repair a **group**, never one item:

- State the defect without reference to any item: *"concepts fed by two tables cannot return the rows of one table"*, not *"question 17 needs TABLE_X"*.
- Change `model.orm.yaml`. New object types and fact types carry `provenance.origin: workload`; new constraints carry `source: workload, status: proposed`. Provenance records the failure class and the number of items, never an item's text (see `representation-format.md`, `source: workload`).
- **Guided:** show the round's repairs as one batch for the user to accept or reject, as in SRP Step 9b. **One-shot:** apply them as `proposed`, with `# REVIEW PROPOSAL` in `model.py`.
- Commit through the modeling skill's final step (SRP Step 9f or CSDP Step 7f), so the YAML validates, then regenerate `model.verbalization.txt` and `model.py`.

A group with a single item is repaired only when the defect is plainly general. Otherwise it is left as residual and reported.

Names must come from the schema, the domain documentation, or the digest's terms. Do not invent a name to match one question's phrasing.

### Step 6 — Re-run

After each model revision, re-run every item: failures, and items that passed before (their saved PyRel may need to follow a renamed element). An item that passed and now fails is a **regression**; a round that causes more regressions than it fixes is rolled back.

### Step 7 — Stop and report

Stop when the first of these holds:
- every repair-set item is `pass`, `inexpressible` or `oracle-error`;
- two rounds in a row raise the repair-set pass count by nothing;
- the budget is reached (default 5 rounds).

Write `model.verification.json` and tell the user, in counts: the oracle used; pass rate on the repair set and on the holdout; the residual failures by class; the repairs made per round; regressions. If the holdout rate is far below the repair-set rate, say that the repairs may be fitted to the items.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Patching `model.py` | It is the file that runs | Repair the YAML and regenerate |
| A clever query that works around the model | Wanting the item to pass | That is a model failure; classify and repair |
| A repair that names an item | Fixing the symptom | State the defect without the item; repair the group |
| Looking at holdout failures | They are in the same file | The holdout is checked, never read for repairs |
| Counting empty-equals-empty as proof | Both sides returned nothing | `weak: true`; not evidence |
| Calling a structural pass "verified" | No data was reachable | Report the oracle by name |
| Marking unreviewed questions as passed | They ran without error | `unverified` until the user saw them |
| Running workload SQL that writes | A log holds every statement | SELECT only, row cap, time cap |

## Examples

| Example | Shows |
|---|---|
| [`evals/fixtures/campus/`](../rai-orm-from-workload/evals/fixtures/campus/) | A model with three planted defects (an undeclared join, a grain trap, a missing derived measure) and the workload that exposes them |

## Reference files

| File | When to load |
|---|---|
| [`references/failure-classes.md`](references/failure-classes.md) | Step 4 — classifying a failure and choosing the repair |
| [`references/report-format.md`](references/report-format.md) | Step 7 — writing `model.verification.json` |
| [`../rai-orm-from-schema/references/representation-format.md`](../rai-orm-from-schema/references/representation-format.md) | Step 5 — `source: workload` provenance |
