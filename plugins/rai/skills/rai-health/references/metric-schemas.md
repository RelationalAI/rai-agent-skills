# Metric View Schemas and Query Patterns

<!-- TOC -->
- [Schema Stability](#schema-stability)
- [logic_reasoner__memory_utilization](#logic_reasoner__memory_utilization)
- [logic_reasoner__cpu_utilization](#logic_reasoner__cpu_utilization)
- [logic_reasoner__demand](#logic_reasoner__demand)
- [Query Patterns](#query-patterns)
<!-- /TOC -->

---

## Schema Stability

| Schema | Stability | Use For |
|--------|-----------|---------|
| `<rai_app>.OBSERVABILITY` | **Stable** — columns not removed/renamed without notice | Production dashboards, alerting |
| `<rai_app>.OBSERVABILITY_PREVIEW` | **Experimental** — may change at any time without notice | Development, evaluation |

The three reasoner utilization views are currently in `OBSERVABILITY_PREVIEW`.

Discover all available views:
```sql
SHOW VIEWS IN SCHEMA RELATIONALAI.OBSERVABILITY;
SHOW VIEWS IN SCHEMA RELATIONALAI.OBSERVABILITY_PREVIEW;
```

---

## logic_reasoner__memory_utilization

Reports memory utilization for each reasoner instance.

| Column | Type | Description |
|--------|------|-------------|
| `TIMESTAMP` | TIMESTAMP_NTZ | When the measurement was taken (UTC) |
| `REASONER_ID` | VARCHAR | Unique reasoner identifier |
| `REASONER_NAME` | VARCHAR | Name of the reasoner |
| `MEMORY_UTILIZATION` | FLOAT | Memory utilization as a ratio (0.0–1.0) |
| `ATTRIBUTES` | OBJECT | Additional reasoner attributes (evolving; may change with notice) |

---

## logic_reasoner__cpu_utilization

Reports CPU utilization for each reasoner instance.

| Column | Type | Description |
|--------|------|-------------|
| `TIMESTAMP` | TIMESTAMP_NTZ | When the measurement was taken (UTC) |
| `REASONER_ID` | VARCHAR | Unique reasoner identifier |
| `REASONER_NAME` | VARCHAR | Name of the reasoner |
| `CPU_UTILIZATION` | FLOAT | CPU utilization as a ratio (0.0–1.0) |
| `ATTRIBUTES` | OBJECT | Additional reasoner attributes (evolving; may change with notice) |

---

## logic_reasoner__demand

Reports job demand (queue pressure) for each reasoner instance.

| Column | Type | Description |
|--------|------|-------------|
| `TIMESTAMP` | TIMESTAMP_NTZ | When the measurement was taken (UTC) |
| `REASONER_ID` | VARCHAR | Unique reasoner identifier |
| `REASONER_NAME` | VARCHAR | Name of the reasoner |
| `DEMAND` | FLOAT | Job demand as a ratio (0.0+); **values > 1.0 indicate queuing** |
| `REASONER_CAPACITY` | VARCHAR | Capacity tier of the reasoner |
| `ATTRIBUTES` | OBJECT | Additional reasoner attributes (evolving; may change with notice) |

> **ATTRIBUTES note:** This is an evolving OBJECT that may contain additional metadata. Stable views
> will provide several months notice before changes; preview views may change at any time.

---

## Query Patterns

### Real-Time Snapshot (Last 5 Minutes)
```sql
SELECT REASONER_NAME, MEMORY_UTILIZATION, TIMESTAMP
FROM relationalai.observability_preview.logic_reasoner__memory_utilization
WHERE timestamp >= DATEADD(minute, -5, CURRENT_TIMESTAMP())
ORDER BY timestamp DESC;
```

### Hourly Aggregation (Last 24 Hours)
```sql
SELECT
  REASONER_NAME,
  DATE_TRUNC('hour', TIMESTAMP) AS hour,
  AVG(CPU_UTILIZATION) AS avg_cpu,
  MAX(CPU_UTILIZATION) AS max_cpu
FROM relationalai.observability_preview.logic_reasoner__cpu_utilization
WHERE timestamp >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
GROUP BY REASONER_NAME, hour
ORDER BY hour DESC;
```

### Daily Trend Analysis (Last 7 Days)
```sql
SELECT
  REASONER_NAME,
  DATE_TRUNC('day', TIMESTAMP) AS day,
  AVG(MEMORY_UTILIZATION) AS avg_memory,
  MAX(MEMORY_UTILIZATION) AS peak_memory
FROM relationalai.observability_preview.logic_reasoner__memory_utilization
WHERE timestamp >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY REASONER_NAME, day
ORDER BY day DESC;
```

### Filter to a Single Reasoner
```sql
SELECT *
FROM relationalai.observability_preview.logic_reasoner__demand
WHERE REASONER_NAME = 'my_reasoner'
  AND timestamp >= DATEADD(hour, -1, CURRENT_TIMESTAMP());
```

### Combined All-Metrics Join

See the Quick Reference section in [SKILL.md](../SKILL.md#quick-reference) for the combined three-metric join query.