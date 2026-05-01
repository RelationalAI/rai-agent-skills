# GNN runtime troubleshooting (lookup)

Quick symptom→fix lookup. Load when SKILL.md § Known Limitations & Runtime Troubleshooting needs the full code shape or SDK source citation.

---

## `has_time_column=True` fails

| Symptom | Cause | Fix |
|---|---|---|
| `no time column defined in data tables` | `time_col` propagates only for node concepts (with `identify_by`); your time-bearing concept is an edge intermediary | Below — full fallback |
| `ValidationError: Error processing datetime column '<name>'` (often at scale, ~27K rows is enough) | Server-side datetime processor rejects the column despite clean data + correct `datetime`/`time_col` config | Below — full fallback |

**Fallback (works for both):** drop `time_col=`, set `has_time_column=False`, drop `temporal_strategy=`, drop the date arg from `Train`/`Val`/`Test` Relationships. Keep the temporal split in pandas:

```python
# Before
pt = PropertyTransformer(datetime=[Sale.date], time_col=[Sale.date], ...)
gnn = GNN(has_time_column=True, ..., temporal_strategy="last")
Train = Relationship(f"{Sale} at {Any:date} has {Any:value}")

# After
pt = PropertyTransformer(datetime=[Sale.date], ...)
gnn = GNN(has_time_column=False, ...)
Train = Relationship(f"{Sale} has {Any:value}")
model.define(Train(Sale, TrainTable.unit_sales)).where(...)
```

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
| Re-run reports `model_run_id` from a much-earlier job; prediction hangs at "Step 2/4: Preparing model for prediction" | `gnn.fit()` is a silent no-op when `self.train_job` exists and isn't `FAILED` (`estimator.py:483-490`); `predictions()` then resolves the previous `job_id` (`job_manager.py:132-146`) | Re-instantiate `GNN(...)` on every retry. Bumping `Model("...")` is **not** the right fix — that's the workaround for the cache footgun above |

---

## Client polls forever

| Symptom | Cause | Fix |
|---|---|---|
| `gnn.fit()` polling for an unreasonable amount of time | `JobMonitor._wait_for_completion` (`job_manager.py:332-340`) polls every 5s with no timeout/retry-cap | Kill the client manually. Recover via the QUEUED runbook, re-instantiate `GNN(...)`, resubmit |
