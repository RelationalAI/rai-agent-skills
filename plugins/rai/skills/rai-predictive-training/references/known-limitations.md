# GNN runtime troubleshooting (lookup)

Quick symptom→fix lookup. Load when SKILL.md § Known Limitations & Runtime Troubleshooting needs the full code shape or SDK source citation.

---

## `has_time_column=True` fails

| Symptom | Cause | Fix |
|---|---|---|
| `no time column defined in data tables` | Temporal setup is incomplete. Typical causes: missing `at {Type:<slot>}` in the `Train`/`Val`/`Test` relationship signature, time column not bound in `define(Train(Source, train.<time_col>, ...))`, or the column is not a true `DATE`/`TIMESTAMP*` type (`rai-predictive-modeling` § Auto-Discovery step 8 has the full type list and probes) | Below — full fallback |

Use this fallback only after the temporal setup is complete and the job still errors. Do not skip `has_time_column=True` because the column is `DATE` rather than `TIMESTAMP`, or because the task tables are already split by time.

**Fallback (works for both):** drop `time_col=`, set `has_time_column=False`, drop `temporal_strategy=`, drop the date arg from `Train`/`Val`/`Test` Relationships. Keep the temporal split in pandas:

```python
# Before
pt = PropertyTransformer(datetime=[Sale.date], time_col=[Sale.date])   # ... other features
gnn = GNN(has_time_column=True, temporal_strategy="last")              # ... other args
Train = Relationship(f"{Sale} at {Any:date} has {Any:value}")

# After
pt = PropertyTransformer(datetime=[Sale.date])                         # ... other features
gnn = GNN(has_time_column=False)                                       # ... other args
Train = Relationship(f"{Sale} has {Any:value}")
model.define(Train(Sale, TrainTable.unit_sales)).where(...)
```

---

## Parquet `timestamp[ns]` interpreted as `timestamp[us]` on `COPY INTO TIMESTAMP_NTZ`

| Symptom | Cause | Fix |
|---|---|---|
| Timestamps land tens of millions of years in the future after bulk-loading via `COPY INTO TIMESTAMP_NTZ` | Snowflake interprets the integer payload as `timestamp[us]`, multiplying every value by 1000. Pandas' default `datetime64[ns]` -> parquet round-trip silently produces `timestamp[ns]`, which trips this | Either write the timestamp column as ISO-8601 strings into parquet, or load the underlying integer time index (e.g. an hour offset) and rebuild server-side via `DATEADD(HOUR, <offset_col>, '<epoch>'::TIMESTAMP_NTZ)` after `COPY INTO`. Also: do schema/type changes **before** the first `Model(...)` bind — `ALTER`-ing a column type after binding can leave a stale compiled-relation signature on the engine that survives stream delete + recreate (see § "transaction was aborted" below for the surface symptom) |

---

## `transaction was aborted (runtime error)` (opaque wrapper)

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to pull data into index: transaction was aborted (runtime error)` after a column type change | Engine cached the compiled relation per name; `ALTER TABLE` + stream recreate doesn't invalidate it. Real error: `Encountered reference to a base relation with a mismatched signature` | `CALL RELATIONALAI.API.GET_TRANSACTION_ARTIFACTS('<txn_id>')` → presigned URL → `problems.json` → `report` field. Then rename `Model(...)` to force a fresh namespace, or do schema changes before the first bind |

---

## Train job `QUEUED` while reasoner `READY`

| Symptom | Cause | Fix |
|---|---|---|
| `worker is not ready to accept jobs - please retry the job later` (server-side, surfaces only on poll) | SDK only probes pod via `api.get_reasoner` (`relationalai_gnns/core/connector.py::_check_engine_availability`); in-pod worker can be desynced | `rai-health` § Predictive train jobs stuck QUEUED (suspend + resume the predictive reasoner). After recovery, re-instantiate `GNN(...)` and resubmit |

---

## `gnn.fit()` returns a stale `model_run_id`

| Symptom | Cause | Fix |
|---|---|---|
| Re-run reports `model_run_id` from a much-earlier job; prediction hangs at "Step 2/4: Preparing model for prediction" | `gnn.fit()` is a silent no-op when `self.train_job` already exists and isn't `FAILED`; `predictions()` then resolves the previous `job_id` | Re-instantiate `GNN(...)` on every retry. Bumping `Model("...")` is **not** the right fix — that's the workaround for the cache footgun above |

---

## Client polls forever

| Symptom | Cause | Fix |
|---|---|---|
| `gnn.fit()` polling for an unreasonable amount of time | `JobMonitor._wait_for_completion` polls every 5s with no timeout/retry-cap | Kill the client manually. Recover via the QUEUED runbook, re-instantiate `GNN(...)`, resubmit |

---

## `RuntimeError: dictionary changed size during iteration` during `gnn.fit()`

| Symptom | Cause | Fix |
|---|---|---|
| `RuntimeError: dictionary changed size during iteration` raised mid-`fit()` when a concept that participates in the GNN graph also carries `model.Relationship` cross-pointers | The predictive reasoner iterates `concept._relationships` without a defensive copy while lazy relationship registration mutates the dict mid-loop | Define cross-concept references on GNN-graph concepts as FK **properties** (joined via `==` in edge definitions) instead of `model.Relationship`. The edges still resolve as property-equality conditions and never trigger the relationship walk |

---

## "Training appears stuck" — diagnostic ladder

Long-running predictive jobs are usually fine, not stuck. Use this ladder before suspending or killing anything. Each step localizes the failure to one component before the next, so you don't suspend the wrong reasoner.

1. **Reasoner status — is the Predictive engine even up?**
   ```sql
   CALL RELATIONALAI.API.GET_REASONER('predictive', '<reasoner_name>');
   ```
   `STATUS=READY` means the reasoner pod is alive. If `SUSPENDED` / `PROVISIONING` / `FAILED`, that's the problem — see `rai-health` § Predictive train jobs stuck QUEUED for recovery. `STATUS=READY` does **not** prove the in-pod worker queue is healthy — step 2 catches that case.

2. **Job ledger — did the train job actually land on a worker?**
   ```python
   client.jobs.list("Predictive", name="<reasoner_name>", only_active=True, limit=10)
   ```
   ```sql
   -- equivalent SQL
   SELECT ID, STATE, JOB_TYPE, DATEDIFF('minute', CREATED_ON, CURRENT_TIMESTAMP()) AS AGE_MIN
   FROM RELATIONALAI.API.JOBS
   WHERE STATE IN ('QUEUED','RUNNING')
     AND PAYLOAD LIKE '%"job_type": "train"%'
   ORDER BY CREATED_ON ASC;
   ```
   - One `train` job in `RUNNING` with `AGE_MIN` rising → training is progressing. Wait.
   - `QUEUED` and old (`AGE_MIN` > a few) while reasoner reports `READY` → in-pod worker desync. → `rai-health` § Predictive train jobs stuck QUEUED.
   - No train job at all but recent COMPLETED short jobs → `fit()` never made it to job submission. Look for client-side errors above the "Training job submitted" line.

3. **Experiment ledger — did training start writing artifacts?**
   ```sql
   SHOW EXPERIMENTS IN SCHEMA <exp_database>.<exp_schema>;
   ```
   A new experiment row appears within ~60 seconds of a `RUNNING` train job. If the job is `RUNNING` for several minutes and `SHOW EXPERIMENTS` shows no new run, the worker accepted the job but is failing silently before artifact creation — escalate via the QUEUED runbook (suspend + resume the predictive reasoner, then re-instantiate `GNN(...)`).

If all three checks look healthy and the run is still long, it's a real long run — let it continue, or scale the engine up (see `rai-predictive-modeling` § Engine sizing) on the next attempt.

---

## RelFM (flat and relational)

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError` constructing relational `RelFM` on a graph with a self-referential FK | `_reject_self_referential_fks` blocks graphs where a real FK column points back at its own concept (e.g. `Edge.new(src=Employee, dst=Employee.manager)`) — RelFM's Deep Feature Synthesis walks the FK graph depth-first with no base case for revisiting a table, so it would recurse forever | Restructure the edge to drop the self-referential FK column, or use `GNN` instead (message passing has no such restriction) |
| `ValueError` on `source_concept`/`context`/`domain` identity when constructing `RelFM` or `RelFMTabular`'s predictor mode | Both require the concept to be identified by **one `identify_by` column** (composite identities with 2+ columns are rejected) | Add a unique ID column in Snowflake (see relfm-flat-mode.md § Tables with no unique column; enable change tracking on it), or fall back to `GNN` (hash-based identity, no restriction) |
| Leakage warning surfaces in `relfm_forecast.get_status()["warnings"]`, not a hard failure | A `RelFMTabular` forecaster's `domain` date falls *inside* `context`'s own date range — the model has effectively already seen the true value for that date | Check `get_status()["warnings"]` explicitly when building forecast domains programmatically; trim `context`'s date range or the `domain` window so they don't overlap |
| `RelFM`/`RelFMTabular` job never touches a training pipeline, `fit()`/`load()`/`register_model()` don't exist on these classes | Both are zero-shot in-context learning estimators — every construction with a given `context` is a fresh inference setup, there is no trained-model artifact to reuse across sessions | Don't look for a register/load workflow for RelFM; re-construct with the same `context` each session, or persist predictions downstream via the same `write_pandas` pattern as GNN (see § Using Predictions Downstream) |

Full param tables, identity rules, and worked examples: [relfm-flat-mode.md](relfm-flat-mode.md), [relfm-relational-mode.md](relfm-relational-mode.md).
