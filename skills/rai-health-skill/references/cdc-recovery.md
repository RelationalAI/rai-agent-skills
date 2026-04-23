# CDC Recovery Reference

<!-- TOC -->
- [data_stream_errors Schema](#data_stream_errors-schema)
- [data_stream_batches Schema](#data_stream_batches-schema)
- [Stream Status Reference](#stream-status-reference)
- [Resume CDC](#resume-cdc)
- [Quarantine Recovery Runbook](#quarantine-recovery-runbook)
- [alter_cdc_engine_size Parameter Table](#alter_cdc_engine_size-parameter-table)
<!-- /TOC -->

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
  AND created_at >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
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

## Stream Status Reference

| Status | Meaning | Recovery |
|--------|---------|----------|
| `ACTIVE` | Healthy | None needed |
| `SUSPENDED` | Paused; CDC halted | Call `resume_cdc()` |
| `QUARANTINED` | Permanently paused; data integrity compromise | Full quarantine recovery — see below |
| `FAILED` | Batch-level failure | Inspect `data_stream_errors`, fix source data, call `resume_cdc()` |

> **Auto-quarantine gotcha:** A stream in `SUSPENDED` state for approximately **one month** is automatically promoted to `QUARANTINED`. This transition creates **no rows in `data_stream_errors`** — the stream simply changes status silently. Always check `status` from `data_stream_batches` or `cdc_status` directly rather than relying on absence of errors to confirm health.

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

---

## alter_cdc_engine_size Parameter Table

```sql
CALL relationalai.app.alter_cdc_engine_size('<size>');
```

| Size | Recommended For |
|------|----------------|
| `HIGHMEM_X64_S` | Light CDC load; default starting point |
| `HIGHMEM_X64_M` | Moderate load; frequent timeout or OOM on S |
| `HIGHMEM_X64_L` | High-volume streams — see 395019 pitfall in SKILL.md Common Pitfalls |
| `HIGHMEM_X64_SL` | Very high-volume with large memory requirements — see 395019 pitfall |

The CDC engine is suspended and recreated during a resize. Expect brief CDC downtime. Confirm the new size with:

```sql
SELECT engine_name, engine_size, engine_status FROM relationalai.api.cdc_status;
```
