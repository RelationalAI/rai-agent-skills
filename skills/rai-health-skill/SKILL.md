---
name: rai-health-skill
description: Guides diagnosis of RAI engine performance issues and recommends remediation. Use when an engine is slow, unresponsive, or needs scaling.
---
<!-- v1-STABLE -->

## Summary

**What:** A process skill for setting up RAI observability, reading the three core reasoner metrics
(memory, CPU, demand), interpreting utilization patterns, and prescribing the correct remediation action.

**When to use:**
- User asks "is my reasoner healthy?" or "why is my engine slow/stuck/queuing?"
- User wants to check memory, CPU, or demand utilization numbers
- User wants to set up observability views or register the events view
- User needs to grant observability access to a team member
- User wants to scale, resize, or shut down a reasoner based on metrics
- User wants to build dashboards or alerting on reasoner metrics

**When NOT to use:**
- Writing PyRel models or query logic → see `rai-pyrel-coding`
- Configuring authentication or initial RAI setup → see `rai-configuration`
- Managing solver optimization problems → see `rai-prescriptive-solver-management`

**Overview (process steps):**
1. Verify observability is set up (events view registered and healthy)
2. Query the three metric views: memory, CPU, demand
3. Apply threshold-based decision rules to form a health verdict
4. Prescribe the exact remediation action in plain text

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

### ✅ HEALTHY — No Action
**Signals:** `MEMORY_UTILIZATION` < 0.80, `CPU_UTILIZATION` < 0.85, `DEMAND` ≤ 1.0 on most runs.

---

### 🔴 OVERLOADED — Upgrade to Larger Reasoner (Immediate)
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

### 🟡 PLAN TO RESIZE — Proactive Warning
**Signals:** `CPU_UTILIZATION` consistently 0.85–0.95 (below critical but limited headroom for bursts).

**Action:** Schedule a resize during a low-traffic window before the next traffic spike. No immediate
action required.

---

### 🟠 QUEUING — Review Job Volume / Split Across Reasoners
**Signals:** `DEMAND` consistently > 1.0 (more jobs than available queue slots).

**Action:**
1. Investigate root cause: is a batch job or burst flooding the queue?
2. If higher concurrency is genuinely needed, route different job types to separate reasoner instances
   (send different jobs to different reasoners — do not simply upsize).
3. Upsizing is not the default fix for queuing — it is a demand and routing problem.

---

### 🔵 UNDERUTILIZED — Downsize to Save Cost
**Signals:** `CPU_UTILIZATION` < 0.30 AND `MEMORY_UTILIZATION` never exceeds 0.30 across workload runs.

**Action:** Downgrade to a smaller reasoner — you are paying for unused capacity.
```bash
rai reasoners:suspend --type Logic --name <name>
rai reasoners:delete  --type Logic --name <name>
rai reasoners:create  --type Logic --name <name> --size <smaller-size>
```

---

### ⚪ IDLE — Suspend or Lower Auto-Suspend Threshold
**Signals:** `DEMAND` = 0 for extended periods.

**Action:** Suspend the reasoner or reduce its `auto_suspend` threshold to stop billing for idle time.
```bash
rai reasoners:suspend --type Logic --name <name>
```

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

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Setup guide | Full 6-step observability setup | [setup-guide.md](references/setup-guide.md) |
| Metric schemas | All metric view schemas | [metric-schemas.md](references/metric-schemas.md) |