# The dev loop and monitoring

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). See `rai-deployment` § Prerequisites.

How to develop against a deployed model — the redeploy loop, the two validation tiers, and how to read model state back out of Snowflake.

## The mental model

A deployed model is a stateful Snowflake object you manage the way a team manages a database: deploy it, inspect it, redeploy it. Development happens against a **dev schema** — the same motion as dbt: point `deployment.schema` at a schema you own, redeploy through the loop, and read state back through SQL. Every redeploy recompiles the model client-side and installs the difference — unchanged objects are skipped via stored fingerprints — so redeploying is the iteration step, not a heavyweight release event.

Reasoning runs asynchronously behind the model's refresh tasks — there is no live engine connection to watch. Everything about how the model is executing (deploy state, refresh runs, block execution, failure detail) surfaces through SQL in the model's meta schema, so the loop is: deploy, query state, fix, deploy again.

## The dev loop

1. **Point at a dev schema.** Set `deployment.schema` to a schema you own (e.g. `MY_DB.MY_MODEL_DEV`), or select a dev profile that sets it — profile mechanics in `rai-setup`.
2. **Deploy.** `rai models deploy` (add `--wait` when the next step depends on refreshed outputs — it blocks until the first refresh completes).
3. **Read state back.** `CALL <db>.<schema>_META.REFRESH_STATUS();` — one row per schedule (contract below).
4. **On failure, diagnose and redeploy.** Classify the failure by tier (next section), fix the model, and deploy into the same schema — redeploying overwrites the deployed version; there is no separate "undo" step in development.

Interactive iteration carries over from engine-backed work: interleave Snowflake reads (information schema, example values, refresh state) with model edits and redeploys — the feedback simply arrives via SQL instead of a live engine connection. Keep narrating refresh progress to the user from `REFRESH_STATUS` while a run is in flight; they should never have to think about the indirection. Poll with backoff — every status call spins the warehouse, and a refresh that takes minutes doesn't change second to second: start around 30s between reads and lengthen toward a few minutes for long refreshes.

Development conveniences (`suspend_after_mins`, `run_on_deploy`, manual schedules): [deploy-and-oplog.md](deploy-and-oplog.md) § Schedules and materialization.

## Two-tier validation

Failures split by the earliest point they *can* be detected. Always exhaust the cheap tier before waiting on the expensive one:

1. **Compile/deploy time — client-side, seconds.** Deploy loads, compiles, and type-checks the model before anything is installed — type mismatches, unknown properties, and malformed rules fail here, before any reasoner or refresh is involved. Fix everything this tier reports in one pass; each round trip is nearly free.
2. **Refresh time — data-dependent.** Constraints that depend on the data (uniqueness, references, functional dependencies) can only fail once a refresh runs against real rows. They surface as a `FAILED` refresh: outcome and message via `REFRESH_STATUS`, block-level detail in the refresh log. Iterating on one means fixing the model (or the data) and redeploying into the same dev schema.

When a data-dependent constraint fails repeatedly, probe the offending condition directly with SQL against the source tables (duplicate keys, orphaned references) before the next redeploy — a targeted `SELECT` is faster than another refresh cycle.

## Reading refresh state

### REFRESH_STATUS — the stable contract

`CALL <meta schema>.REFRESH_STATUS();` is the public, stable surface for refresh state — start every diagnosis here. One row per schedule:

| Column | Meaning |
|---|---|
| `schedule_name` | The refresh schedule |
| `status` | Latest refresh outcome: `SUCCEEDED` / `FAILED` / `RUNNING` / `NEVER_RUN`. While a deploy is in flight every schedule reports `DEPLOY_RUNNING`; if the last deploy failed (or the deployer crashed), every schedule reports `DEPLOY_FAILED` |
| `error` | Failure message when `FAILED`; the deploy's failure message when `DEPLOY_FAILED`; the task's suspension reason when `NEVER_RUN` with a `SUSPENDED` task |
| `task_schedule` | Cadence — `MANUAL` for trigger-only schedules, else the interval (e.g. `60 SECONDS`) |
| `task_state` | The schedule's Snowflake task right now: `STARTED` (armed) / `SUSPENDED` |
| `last_run_started_at` / `last_run_completed_at` | Latest run window (`last_run_completed_at` is NULL while `RUNNING`) |
| `last_success_started_at` / `last_success_completed_at` | Last successful run window |

Deployed outputs are **eventually consistent** with their sources. Within one schedule a refresh updates outputs in dependency order; schedules run independently, so dependent outputs on *different* schedules can show mixed freshness while refreshing. A refresh-time privilege failure usually means `deployment.role` can't execute tasks.

### The refresh log — block-level detail

When `REFRESH_STATUS` says `FAILED` and you need to know *which block* failed, read the meta schema's refresh log, `<meta schema>._INTERNAL_REFRESH_LOG`. It is internal (the `_INTERNAL_` prefix means columns may change between releases — `REFRESH_STATUS` is the contract), but it is the one place with per-block execution rows. Each run writes `RUN_STARTED`, `BLOCK` rows as each block starts and finishes (a `RUNNING` row, then a `SUCCESS` or `FAILURE` row), then `RUN_COMPLETE`; useful columns: `entry_type`, `state`, `target_table_names`, `block_index`, `started_at` / `ended_at`, `error_message`.

```sql
-- Block-level trace of the latest run of one schedule
SELECT entry_type, target_table_names, block_index, state, error_message
FROM MY_DB.MY_MODEL_META._INTERNAL_REFRESH_LOG
WHERE schedule_name = 'standard'
  AND run_start_time = (
    SELECT MAX(run_start_time)
    FROM MY_DB.MY_MODEL_META._INTERNAL_REFRESH_LOG
    WHERE schedule_name = 'standard'
  )
ORDER BY log_id;
```

A wedge to know about: if the deploy/refresh driver dies mid-run (killed session, crashed process), blocks can remain `RUNNING` with no terminal row and no `RUN_COMPLETE` — the log simply stops. A `RUNNING` row with an old `started_at` and no progress is a dead run, not a live one; cross-check `REFRESH_STATUS` and the task state before waiting on it.

The companion `<meta schema>._INTERNAL_PLAN` table records what was deployed — one row per plan entry with the generated SQL, its reasoner, schedule, and dependencies. Read it when you need to connect a failing block back to the model logic that produced it.

### rai doctor report — full state in one artifact

When direct queries don't add up (or you need to hand complete state to support), `rai doctor report` bundles everything into one zip: `summary.md` (the triage page — open it first), `doctor.json` (config + connectivity checks), `plan.csv` and `refresh_log.csv` samples, deploy state, op-log sync status, Snowflake task/privilege checks, and `spans.jsonl` from the latest deploy run (open with `rai debugger spans.jsonl`). The zip includes its own `skill.md` manifest describing every artifact and which were collected — follow it when interpreting a report.

For live checks without the bundle: bare `rai doctor` prints health checks; `rai config explain` shows how the active config resolved.
