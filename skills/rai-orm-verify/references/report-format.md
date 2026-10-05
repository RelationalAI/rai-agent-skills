# `model.verification.json` — format

Written at Step 7, next to `model.orm.yaml`. Counts, ids, class names and model element ids only: no question text, no SQL, no result rows.

```json
{
  "version": 1,
  "workload": { "kind": "pairs", "artifacts": ["setup-pairs.json"], "n_items": 109 },
  "oracle": "execution-match",
  "mode": "guided",
  "split": { "repair": 87, "holdout": 22, "rule": "every fifth id, sorted" },
  "invocations": [{ "started_round": 1, "rounds_run": 1, "stopped_because": "plateau" }],
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
    "stopped_because": "plateau", "rounds_run_total": 1
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
7. Round 0 is the initial model as received. A resumed invocation uses existing round N as its N+0 baseline and starts attempts at N+1; a baseline is not a repair attempt. Preserve historical rounds, including rolled-back attempts with their acceptance/rollback evidence.
8. Every round carries `connectivity`: component count, isolated entity ids, and required digest join ids from the repair-set check. `isolated` and `required_gaps` accept lists of strings or objects with an `id` (legacy objects without an `id` fall back to `name`). Integers are accepted as counts: the statistics report emits `isolated_count` or `required_gaps_count` and leaves the corresponding id list empty. Malformed optional connectivity values are skipped and counted in `statistics.rounds_unparsed_connectivity`, which is omitted when zero. Keep holdout connectivity separate from repair decisions; optional `holdout_connectivity` has the same shape and supplies evaluation only. Full components, table bindings, support and overlap evidence live in `connectivity.json` and proposed fact provenance.
9. `items[].pyrel` records saved files relative to this JSON file. It is the only file inventory used for the singleton concept check in the statistics report.
10. `stopped_because: budget` means the budget of this invocation stopped with residual failures, and is incomplete. Never label it done or all-pass. Step 7 runs `report.py` and leads the user summary with the first `BUDGET_EXHAUSTED` line from `orm-report.md`, including residual count and continuation step.

## Statistics and issues artifacts

Step 7 also emits `orm-report.json` and `orm-report.md` using `report.py` from `rai-orm`. Load the statistics-and-issues reference in `rai-orm` for statistics, fixed issue ids, severity, actions, privacy rules and the exact budget-first line. These artifacts complement the per-item verification log; they do not replace it. Always show the Markdown report and name the verification oracle.

## Resume and invocation accounting

- `invocations` is an append-only ordered list of `{started_round, rounds_run, stopped_because}`. `started_round` is the next repair-round number, even when `rounds_run` is 0. Baseline N+0 is existing round N; attempts span N+1 through N+`rounds_run`. `stopped_because` may be absent while an invocation is in progress. Each invocation ends with `all-pass`, `plateau` or `budget` under Step 7. `summary.stopped_because` names the latest invocation's stop.
- Record `summary.rounds_run_total` as the sum of invocation attempts (baseline checks excluded). Round numbers stay global and monotonic, including rejected attempts. The report states the latest invocation's rounds and rounds run in total, instead of describing the cumulative history as a fresh budget.
- Legacy reports without `invocations` retain their round list. Seed one legacy entry with `started_round: 1`, `rounds_run: N` (last recorded round, assuming the original baseline is 0), and the old stop reason before appending the new invocation. Do not invent individual prior invocations when their boundaries were not saved. Document a legacy partial-history limit if the original baseline is missing.
- Read `split` and `items[].split` from the previous file; never recompute them on resume. The split object holds counts/rule; the item records are the authoritative assignments. For a workload delta, archive removed ids, keep surviving assignments and record genuinely new assignments once. Historical split evidence is retained with the archived snapshot.
- Prior `pass` items keep `pyrel`, `passed_at_round`, `weak` and their oracle evidence. Run the accepted PyRel only as regression checks; test explicit removal, merge, flag-replacement and rename migrations as candidate files before replacing accepted paths. A prior pass cannot be relabeled as an exclusion to hide a regression.
- Append resumed round connectivity blocks as before. Optional invocation `baseline_check` records count-only rechecks of round N when source/model changes require them; do not overwrite round N's original evidence or charge it as an attempt.
- Settings come from `orm-state.json`: `rounds_per_invocation` 5, `patience` 2 and `until_pass` false by default. `until_pass: true` ignores the finite round cap until all items are terminal or patience is reached; it does not reset global counters, relax holdout isolation or convert `unverified` to pass.
- Refactor acceptance uses `refactor_rounds` (default 2), separately from verify rounds; assessment costs zero. Record per-skill attempts in state, including rollbacks. Record total/per-split passes, regressions, fixes, weak passes and exclusions. Require every unchanged baseline-passing id to stay passing with unchanged oracle and weak accounting. Reject a same-split pass swap even at equal totals, any total/per-split pass-count drop, changed exclusions or oracle, restoring YAML/Python/bindings/report/rewrites together; retain the attempted round and rejection evidence in the final log.

For example, an original invocation stopped at round 5 and a resume ran rounds 6 and 7:

```json
{
  "invocations": [
    {"started_round": 1, "rounds_run": 5, "stopped_because": "budget"},
    {"started_round": 6, "rounds_run": 2, "stopped_because": "all-pass"}
  ],
  "summary": {"stopped_because": "all-pass", "rounds_run_total": 7}
}
```

The resumed baseline remains round 5 with the old model. Its three saved passes are the regression inventory; they are not three new translations. The fresh invocation may spend up to five attempts by default even though five were already spent in the original invocation.

Ordinary repair acceptance differs from refactor: fixes must exceed regressions. Record each lost pass as `status: fail` with `regressed_at_round`, each fix with `passed_at_round`, and the round’s `fixes`/`regressions` counts. Use `state.py update --skill rai-orm-verify --accept-regressions` to accept that net improvement; otherwise baseline loss blocks update. The next plan lists each lost id as `REGRESSED_ITEM` until restored; exclusions cannot hide regressions. Equal or greater regressions require rollback. Verify round charges come from the last recorded round minus the previous counter; supplied `--rounds-done` must match. For a changed workload specification, record the current item `spec_hash` only after rechecking it; accepting a workload delta alone cannot renew its pass.
