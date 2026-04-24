# CDC Recovery Reference

<!-- TOC -->
- [data_stream_errors Schema](#data_stream_errors-schema)
- [data_stream_batches Schema](#data_stream_batches-schema)
- [Resume CDC](#resume-cdc)
- [Quarantine Recovery Runbook](#quarantine-recovery-runbook)
<!-- /TOC -->

> For **Stream State Verdicts** see
> [SKILL.md — Step 5](../SKILL.md#step-5--diagnose-cdc--data-stream-health); for the
> **`alter_cdc_engine_size` size table** see
> [SKILL.md — Step 6](../SKILL.md#step-6--cdc-engine-management).

---

## data_stream_errors Schema

```sql
SELECT *
FROM relationalai.api.data_stream_errors
WHERE stream_name = '<stream_name>'
ORDER BY created_at DESC;
```

| Column | Type | Description |
|--------|------|-------------|
| `stream_name` | VARCHAR | Identifier of the data stream |
| `error_type` | VARCHAR | Category: `LOAD_ERROR`, `PARSE_ERROR`, `SCHEMA_MISMATCH`, etc. |
| `error_message` | VARCHAR | Human-readable error detail |
| `batch_id` | VARCHAR | The batch that triggered this error |
| `row_count` | NUMBER | Affected row count |
| `created_at` | TIMESTAMP_NTZ | When the error was recorded |

---

## data_stream_batches Schema

```sql
SELECT *
FROM relationalai.api.data_stream_batches
WHERE stream_name = '<stream_name>'
  AND created_at >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY created_at DESC;
```

| Column | Type | Description |
|--------|------|-------------|
| `stream_name` | VARCHAR | Identifier of the data stream |
| `batch_id` | VARCHAR | Unique batch identifier |
| `status` | VARCHAR | `COMPLETED`, `FAILED`, `PENDING`, `PROCESSING` |
| `row_count` | NUMBER | Rows in this batch |
| `error_message` | VARCHAR | Batch-level error (null if successful) |
| `created_at` | TIMESTAMP_NTZ | Batch creation time |
| `finished_at` | TIMESTAMP_NTZ | Batch completion time (null if pending/processing) |

---

## Resume CDC

```sql
CALL relationalai.app.resume_cdc('<stream_name>');
```

**Preconditions:**
- Stream status must be `SUSPENDED` or `FAILED` — quarantined streams require the full recovery flow below
- CDC engine must be in a healthy state (`SELECT * FROM relationalai.api.cdc_status`)
- Underlying Snowflake data source must be accessible

---

## Quarantine Recovery Runbook

Official step-by-step recovery: **https://docs.relational.ai/manage/data/#fix-quarantined-streams**

High-level flow:
1. Identify the quarantined stream via `cdc_status` or `data_stream_batches`
2. Fix the root cause (schema change, source table permissions, stale offsets)
3. Follow the drop-and-recreate stream procedure in the official docs
4. Monitor `data_stream_batches` for new `COMPLETED` batches after recreation
