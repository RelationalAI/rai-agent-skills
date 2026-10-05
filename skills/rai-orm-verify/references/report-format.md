# `model.verification.json` — format

Written at Step 7, next to `model.orm.yaml`. Counts, ids, class names and model element ids only: no question text, no SQL, no result rows.

```json
{
  "version": 1,
  "workload": { "kind": "pairs", "artifacts": ["setup-pairs.json"], "n_items": 109 },
  "oracle": "execution-match",
  "mode": "guided",
  "split": { "repair": 87, "holdout": 22, "rule": "every fifth id, sorted" },
  "rounds": [
    { "round": 0, "model_revision": "sha256:…", "repair_pass": 13, "holdout_pass": 3,
      "by_class": { "grain": 46, "missing-element": 9, "translation": 12, "semantics": 7 },
      "regressions": 0,
      "connectivity": { "components": 2, "isolated": ["group"], "required_gaps": ["je_1"] } },
    { "round": 1, "model_revision": "sha256:…", "repair_pass": 61, "holdout_pass": 14,
      "by_class": { "grain": 4, "translation": 15, "semantics": 7 },
      "regressions": 1,
      "connectivity": { "components": 1, "isolated": [], "required_gaps": [] } }
  ],
  "repairs": [
    { "round": 1, "class": "grain", "items": 46,
      "defect": "Concepts fed by two or more tables cannot return the rows of one table.",
      "change": "One unary fact type per source table on each such concept.",
      "yaml_ids": ["student_in_student_directory", "…"],
      "status": "proposed" }
  ],
  "items": [
    { "id": "q001", "split": "repair", "status": "pass", "weak": false, "runs": 2,
      "passed_at_round": 0, "pyrel": "verification/q001.py" },
    { "id": "q017", "split": "repair", "status": "fail", "class": "semantics", "runs": 4 },
    { "id": "q023", "split": "holdout", "status": "inexpressible", "construct": "recursive CTE" }
  ],
  "summary": {
    "repair_pass_rate": 0.70, "holdout_pass_rate": 0.64, "weak_passes": 2,
    "excluded": { "inexpressible": 3, "oracle-error": 1 },
    "residual_by_class": { "translation": 15, "semantics": 7, "grain": 4 },
    "stopped_because": "plateau"
  }
}
```

## Rules

1. `oracle` is one of `execution-match`, `structural`, `user-review`. One report has one oracle.
2. `split.holdout` is 0 when the workload has fewer than 30 items.
3. Pass rates are over items that are not `inexpressible` or `oracle-error`. Those are counted in `summary.excluded`.
4. For `user-review`, `unverified` items are not in the numerator of any pass rate; `summary` also carries `"reviewed": <n>` and `"unverified": <n>`.
5. `repairs[].defect` and `repairs[].change` are stated without reference to any item. `items` is a count.
6. `stopped_because` is one of `all-pass`, `plateau`, `budget`.
7. Round 0 is the model as received. A report with only round 0 means no repair was made.
8. Every round carries `connectivity`: component count, isolated entity ids, and required digest join ids from the repair-set check. Keep holdout connectivity separate from repair decisions; optional `holdout_connectivity` has the same shape and supplies evaluation only. Full components, table bindings, support and overlap evidence live in `connectivity.json` and proposed fact provenance.
9. `items[].pyrel` records saved files relative to this JSON file. It is the only file inventory used for the singleton concept check in the statistics report.
10. `stopped_because: budget` with residual failures is incomplete. Never label it done or all-pass. Step 7 runs `report.py` and leads the user summary with the first `BUDGET_EXHAUSTED` line from `orm-report.md`, including residual count and continuation step.

## Statistics and issues artifacts

Step 7 also emits `orm-report.json` and `orm-report.md` using `report.py` from `rai-orm`. Load the [statistics-and-issues format](../../rai-orm/references/statistics-and-issues.md) for statistics, fixed issue ids, severity, actions, privacy rules and the exact budget-first line. These artifacts complement the per-item verification log; they do not replace it. Always show the Markdown report and name the verification oracle.
