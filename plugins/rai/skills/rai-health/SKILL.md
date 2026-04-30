---
name: rai-health
description: Guides diagnosis of RAI engine performance, failed transactions, CDC/data-stream health, and CDC engine management. Use when a reasoner is slow or queuing, a transaction or batch has failed, a CDC stream is suspended or quarantined, or CDC engine sizing/recovery is needed.
---
<!-- v1-STABLE -->

## Summary

**What:** A process skill for diagnosing RAI operational health across four domains: reasoner
performance (memory/CPU/demand), failed transactions, CDC / data-stream health, and CDC engine
management. Each domain has its own step with decision tables and remediation actions.

**When to use:**
- Reasoner is slow, stuck, or queuing; need to check memory, CPU, or demand metrics
- Observability views need setup, role grants, or dashboard/alerting work
- A transaction was aborted; `get_transaction_problems`, `get_own_transaction_problems`,
  or `get_load_errors` must be called
- Batch processing has failed and load errors need inspection
- A CDC task is suspended, a data stream is quarantined, or `resume_cdc` is needed
- CDC engine needs resizing (`alter_cdc_engine_size`) or force-deletion

**When NOT to use:**
- Writing PyRel models or query logic → see `rai-pyrel-coding`
- Configuring authentication or initial RAI setup → see `rai-setup`
- Managing solver optimization problems → see `rai-prescriptive-solver-management`

**Overview (process steps):**
1. Verify observability is set up (events view registered and healthy)
2. Query the three metric views: memory, CPU, demand
3. Apply threshold-based decision rules and prescribe the exact remediation action
4. Diagnose a failed transaction (get_transaction, get_load_errors, owner-restriction pitfall)
5. Diagnose CDC / data stream health (errors, batches, quarantine recovery, resume_cdc)
6. Manage the CDC engine (alter_cdc_engine_size, force delete, cdc_status)

> **Navigation:** Steps 1–3 cover reasoner health only. For CDC/stream issues go directly to
> **Step 5**. For transaction failures go directly to **Step 4**. For CDC engine sizing or
> force-delete go directly to **Step 6**.

---

## Quick Reference

### The Three Metric Views (all in `OBSERVABILITY_PREVIEW`)

| View | Key Column | Healthy Signal |
|------|-----------|----------------|
| `logic_reasoner__memory_utilization` | `MEMORY_UTILIZATION` (0.0–1.0) | < 0.80 on most runs |
| `logic_reasoner__cpu_utilization` | `CPU_UTILIZATION` (0.0–1.0) | < 0.85 sustained; < 0.95 peak |
| `logic_reasoner__demand` | `DEMAND` (0.0+) | ≤ 1.0 (> 1.0 = queuing) |

**Quickest health check — all three metrics joined, last hour:**
```sql
SELECT
  m.REASONER_NAME,
  m.TIMESTAMP,
  m.MEMORY_UTILIZATION,
  c.CPU_UTILIZATION,
  d.DEMAND,
  d.REASONER_CAPACITY
FROM relationalai.observability_preview.logic_reasoner__memory_utilization m
JOIN relationalai.observability_preview.logic_reasoner__cpu_utilization c
  ON m.REASONER_ID = c.REASONER_ID AND m.TIMESTAMP = c.TIMESTAMP
JOIN relationalai.observability_preview.logic_reasoner__demand d
  ON m.REASONER_ID = d.REASONER_ID AND m.TIMESTAMP = d.TIMESTAMP
WHERE m.TIMESTAMP >= DATEADD(hour, -1, CURRENT_TIMESTAMP())
ORDER BY m.TIMESTAMP DESC;
```

> **Always include a time-range filter.** Querying without `WHERE timestamp >= ...` scans the entire
> Event Table and incurs high Snowflake compute costs.

---

## Step 1 — Verify Observability Is Active

Before querying metrics, confirm the events view is registered and data is flowing.

```sql
CALL relationalai.app.CHECK_EVENTS_VIEW_STATUS();
```

| Status | Meaning | Action |
|--------|---------|--------|
| `Events view active` | Healthy, events flowing | None |
| `No events view registered` | Setup not done | Follow setup in `references/setup-guide.md` |
| `ERROR` | Configuration broken | Fix per error message reported |

> Run `CHECK_EVENTS_VIEW_STATUS()` whenever observability views return unexpected or empty results —
> it diagnoses most configuration issues automatically.

---

## Step 2 — Query Each Metric

### Memory Utilization
```sql
SELECT REASONER_NAME,
       AVG(MEMORY_UTILIZATION) AS avg_mem,
       MAX(MEMORY_UTILIZATION) AS peak_mem
FROM relationalai.observability_preview.logic_reasoner__memory_utilization
WHERE timestamp >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
GROUP BY REASONER_NAME;
```

### CPU Utilization
```sql
SELECT REASONER_NAME,
       AVG(CPU_UTILIZATION) AS avg_cpu,
       MAX(CPU_UTILIZATION) AS peak_cpu
FROM relationalai.observability_preview.logic_reasoner__cpu_utilization
WHERE timestamp >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
GROUP BY REASONER_NAME;
```

### Demand (Queue Pressure)
```sql
SELECT REASONER_NAME,
       AVG(DEMAND)   AS avg_demand,
       MAX(DEMAND)   AS peak_demand,
       REASONER_CAPACITY
FROM relationalai.observability_preview.logic_reasoner__demand
WHERE timestamp >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
GROUP BY REASONER_NAME, REASONER_CAPACITY;
```

> **Interpret patterns, not isolated spikes.** Utilization is naturally spiky. The key question is:
> does *almost every* workload run exceed the threshold? Isolated peaks are normal; consistent
> exceedance across runs is the signal to act.

---

## Step 3 — Health Verdicts and Actions

### OK — HEALTHY — No Action
**Signals:** `MEMORY_UTILIZATION` < 0.80, `CPU_UTILIZATION` < 0.85, `DEMAND` ≤ 1.0 on most runs.

If transactions are still failing despite healthy metrics, the problem is not resource-related —
go to **Step 4** to diagnose the transaction directly.

---

### CRITICAL — OVERLOADED — Upgrade to Larger Reasoner (Immediate)
**Signals (any of):**
- `MEMORY_UTILIZATION` > 0.80 on most workload runs
- `CPU_UTILIZATION` consistently > 0.95
- `CPU_UTILIZATION` = 1.0 AND `MEMORY_UTILIZATION` = 1.0 AND `DEMAND` > 1.0 (all hard limits hit)

**Action:** Upgrade reasoner size. No in-place resize exists — delete and recreate.
```bash
rai reasoners:suspend --type Logic --name <name>
rai reasoners:delete  --type Logic --name <name>
rai reasoners:create  --type Logic --name <name> --size <larger-size>
```

---

### ELEVATED — PLAN TO RESIZE — Proactive Warning
**Signals:** `CPU_UTILIZATION` consistently 0.85–0.95 (below critical but limited headroom for bursts).

**Action:** Schedule a resize during a low-traffic window before the next traffic spike. No immediate
action required.

---

### WARNING — QUEUING — Review Job Volume / Split Across Reasoners
**Signals:** `DEMAND` consistently > 1.0 (more jobs than available queue slots).

**Action:**
1. Investigate root cause: is a batch job or burst flooding the queue?
2. If higher concurrency is genuinely needed, route different job types to separate reasoner instances
   (send different jobs to different reasoners — do not simply upsize).
3. Upsizing is not the default fix for queuing — it is a demand and routing problem.

---

### INFORMATIONAL — UNDERUTILIZED — Downsize to Save Cost
**Signals:** `CPU_UTILIZATION` < 0.30 AND `MEMORY_UTILIZATION` never exceeds 0.30 across workload runs.

**Action:** Downgrade to a smaller reasoner — you are paying for unused capacity.
```bash
rai reasoners:suspend --type Logic --name <name>
rai reasoners:delete  --type Logic --name <name>
rai reasoners:create  --type Logic --name <name> --size <smaller-size>
```

---

### NOMINAL — IDLE — Suspend or Lower Auto-Suspend Threshold
**Signals:** `DEMAND` = 0 for extended periods.

**Action:** Suspend the reasoner or reduce its `auto_suspend` threshold to stop billing for idle time.
```bash
rai reasoners:suspend --type Logic --name <name>
```

---

## Step 4 — Diagnose a Failed Transaction

Use these procedures when a transaction appears stuck, aborted, or when load errors are reported.

### Fetch a Transaction by ID

```sql
CALL relationalai.api.get_transaction('<transaction_id>');
```

Returns the full transaction record including status, owner, start/end timestamps, and error detail.

### Get Transaction Problems

```sql
-- Problems for any transaction (requires admin-level role)
CALL relationalai.api.get_transaction_problems('<transaction_id>');

-- Problems for transactions you own (end-user role)
CALL relationalai.api.get_own_transaction_problems('<transaction_id>');
```

| Procedure | Accessible by | Returns |
|-----------|--------------|---------|
| `get_transaction_problems` | Admin roles | All transactions |
| `get_own_transaction_problems` | Any role | Only caller-owned transactions |

### Get Load Errors

```sql
CALL relationalai.api.get_load_errors('<transaction_id>');
```

Returns row-level load errors associated with a transaction: source object, error message, and
affected row count.

> **WARNING — Owner-restriction pitfall:** If `get_transaction_problems` returns **HTTP 400**, check the
> transaction owner before assuming a permissions misconfiguration:
> ```sql
> CALL relationalai.api.get_transaction('<transaction_id>');
> ```
> Then use the table below to interpret the result.

| `get_transaction` result | Meaning | Next step |
|--------------------------|---------|-----------|
| `owner` = `cdc.scheduler@erp` | Expected behavior — CDC-owned transactions are not visible to end-user roles by design | Use `SELECT * FROM relationalai.api.cdc_status` or an admin role |
| `owner` = any other identity; called `get_transaction_problems` without an admin role | Permission issue — `get_transaction_problems` requires an admin role | Grant the admin role, or switch to `get_own_transaction_problems` if you own the transaction |
| `owner` = any other identity; caller has an admin role | Genuine API failure — not a permissions problem | Open a support ticket with the transaction ID and full error response |
| `get_transaction` itself returns 400 | Invalid transaction ID, or insufficient role to read any transactions | Verify the transaction ID; if correct, confirm read access to `relationalai.api` |

When `get_transaction` returns an unexpected column or state code, or when inspecting load errors per row, see [transaction-debug.md](references/transaction-debug.md).

---

## Step 5 — Diagnose CDC / Data Stream Health

> **WARNING — Auto-quarantine gotcha:** A stream that has been in `SUSPENDED` state for
> **approximately one month** will be automatically promoted to `QUARANTINED` —
> **without creating any rows in `data_stream_errors`**. The absence of error rows does not
> mean the stream is healthy. Always confirm stream status from `cdc_status` or
> `data_stream_batches` before treating an empty errors result as a clean bill of health.

### Find Your Streams (Start Here)

```sql
SELECT * FROM relationalai.api.cdc_status;
```

Key columns: `stream_name`, `stream_status`, `engine_name`, `engine_status`. Use the `stream_name`
values from this output as `'<stream_name>'` in the queries below.

### Check Batch-Level Status

```sql
SELECT stream_name, batch_id, status, error_message, created_at
FROM relationalai.api.data_stream_batches
WHERE stream_name = '<stream_name>'
  AND created_at >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY created_at DESC;
```

> Use a 7-day window rather than 24 hours — a quarantined or long-suspended stream may have
> had no batches for days, and a 24-hour filter returns empty output indistinguishable from a
> healthy-but-idle stream.

### Check Stream-Level Errors

```sql
SELECT *
FROM relationalai.api.data_stream_errors
WHERE stream_name = '<stream_name>'
ORDER BY created_at DESC
LIMIT 50;
```

For auto-quarantined streams this may return empty — that is expected. Use
`data_stream_batches` `status` as the authoritative source.

### Stream State Verdicts

| Status | Meaning | Action |
|--------|---------|--------|
| `ACTIVE` | Healthy, batches flowing | None |
| `SUSPENDED` | Paused; no new batches | Call `resume_cdc()` — see below |
| `QUARANTINED` | Permanently paused; data integrity issue | [Follow quarantine recovery flow](references/cdc-recovery.md#quarantine-recovery-runbook) |
| `FAILED` | Batch or load error | Check `data_stream_errors` and `get_load_errors` |

### Resume a Suspended Stream

```sql
CALL relationalai.app.resume_cdc('<stream_name>');
```

### Quarantine Recovery

See [cdc-recovery.md — Quarantine Recovery Runbook](references/cdc-recovery.md#quarantine-recovery-runbook)
for the full step-by-step recovery checklist, schema reference, and official docs link.

---

## Step 6 — CDC Engine Management

> **CDC engine ≠ reasoner engine.** The CDC pipeline runs on a dedicated managed engine
> distinct from Logic reasoner engines. `alter_cdc_engine_size` targets only the CDC engine;
> the CLI commands (`rai reasoners:create/delete`) target Logic reasoners only. Do not apply
> the Step 3 CLI commands to the CDC engine.

### Check Current CDC Status

```sql
SELECT * FROM relationalai.api.cdc_status;
```

Key columns: `engine_name`, `engine_size`, `engine_status`, `stream_name`, `stream_status`.

### Resize the CDC Engine

```sql
CALL relationalai.app.alter_cdc_engine_size('<size>');
```

| Size | Use When |
|------|----------|
| `HIGHMEM_X64_S` | Small CDC load; default starting point |
| `HIGHMEM_X64_M` | Moderate load or frequent quarantine timeouts |
| `HIGHMEM_X64_L` | High-volume streams (see 395019 pitfall in Common Pitfalls) |
| `HIGHMEM_X64_SL` | Largest available; high-volume with large memory requirement (see 395019 pitfall) |

The CDC engine is suspended and recreated during a resize — expect brief CDC downtime.

### Force-Delete a Stale CDC Engine

Use when the CDC engine is stuck in a non-deletable state:

```sql
CALL relationalai.api.delete_engine('CDC_MANAGED_ENGINE', TRUE);
```

The second argument `TRUE` enables force deletion. RAI will recreate the CDC engine automatically
on the next CDC trigger. Confirm recovery with `SELECT * FROM relationalai.api.cdc_status`.

> **WARNING — If `delete_engine` returns "engine not found" but `cdc_status` still shows the engine
> as suspended:** this is a control-plane / data-plane desync — the engine record exists in
> RAI's metadata but the underlying Snowflake engine is gone. No self-serve command resolves
> this state. Run the following and retain the output for support:
> ```sql
> SELECT * FROM relationalai.api.cdc_status;
> ```
> Then open a support ticket with that output. Do not attempt `alter_cdc_engine_size` in this
> state — it will fail or create a duplicate record.

---

## Access Control

Two application roles control who can configure and who can read observability data:

| Role | Capabilities | Grant To |
|------|-------------|----------|
| `observability_admin` | Register/unregister events view; call `CHECK_EVENTS_VIEW_STATUS()` | Small trusted ops group |
| `observability_viewer` | Read-only on all observability views | Engineering and operations users |

```sql
GRANT APPLICATION ROLE relationalai.observability_viewer TO ROLE <your_role>;
GRANT APPLICATION ROLE relationalai.observability_admin  TO ROLE <your_role>;
```

---

## Cost Guardrails

Observability views are **non-materialized** — every query scans the Snowflake Event Table in real
time. No extra storage cost, but Snowflake compute credits are consumed on every query.

Cost scales with: event volume × time range × query complexity.

| Rule | Detail |
|------|--------|
| Always filter by time | `WHERE timestamp >= DATEADD(hour, -24, ...)` — never query without bounds |
| Monitor query costs | `SELECT query_id, total_elapsed_time, credits_used_cloud_services FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY WHERE query_text ILIKE '%observability%'` |
| Prefer hourly/daily aggregations for dashboards | Avoid raw per-minute scans in scheduled jobs |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| No data in metric views | Events view not registered or setup incomplete | Run `CHECK_EVENTS_VIEW_STATUS()`; complete setup if needed |
| Registration fails: "CHANGE_TRACKING" error | Change tracking not enabled on view or event table | Add `CHANGE_TRACKING = TRUE` to view definition and underlying table |
| Registration fails: "A view is already registered" | Prior view still bound | Call `UNREGISTER_EVENTS_VIEW()` first, then re-register |
| Queries are slow or expensive | Missing time-range filter scans full event table | Always add `WHERE timestamp >= DATEADD(...)` |
| `DEMAND > 1.0` but CPU is low | Job routing: one reasoner saturated, others idle | Redistribute jobs across reasoner instances |
| Isolated spikes look alarming | Normal: spiky workloads cause transient peaks | Focus on pattern across runs, not individual data points |
| `observability_viewer` cannot see views | Role not granted | Run `GRANT APPLICATION ROLE ... TO ROLE ...` as admin |
| Engine create fails: `Failed to parse 'service spec' as YAML` (Snowflake error 395019) | `ENGINE_CONFIG_OVERRIDE` is set and the size is `HIGHMEM_X64_L` or `HIGHMEM_X64_SL` | Use `HIGHMEM_X64_S` or `HIGHMEM_X64_M` until the platform fix is deployed |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Setup guide | Full 6-step observability setup | [setup-guide.md](references/setup-guide.md) |
| Metric schemas | All metric view schemas | [metric-schemas.md](references/metric-schemas.md) |
| Transaction debug | `get_transaction` / `get_load_errors` API reference and owner-restriction details | [transaction-debug.md](references/transaction-debug.md) |
| CDC recovery | `data_stream_errors`, batches schema, quarantine recovery, `resume_cdc` | [cdc-recovery.md](references/cdc-recovery.md) |
