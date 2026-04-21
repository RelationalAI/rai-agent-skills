# Observability Setup Guide

<!-- TOC -->
- [Step 2.1 — Identify the Active Event Table](#step-21--identify-the-active-event-table)
- [Step 2.2 — Create a Dedicated Schema](#step-22--create-a-dedicated-schema)
- [Step 2.3 — Create the RAI Events View](#step-23--create-the-rai-events-view)
- [Step 2.4 — Register the View](#step-24--register-the-view)
- [Step 2.5 — Unregister the View](#step-25--unregister-the-view-if-needed)
- [Step 2.6 — Validate Configuration](#step-26--validate-configuration)
- [Cost Monitoring](#cost-monitoring)
<!-- /TOC -->

> **Prerequisites:** ACCOUNTADMIN privileges (or equivalent) for Steps 2.1–2.3.
> Observability is currently a **Preview** feature.

---

## Step 2.1 — Identify the Active Event Table

Each Snowflake account has one active event table. Your observability view must reference it.

```sql
SHOW PARAMETERS LIKE 'EVENT_TABLE' IN ACCOUNT;
```

Returns the fully qualified event table name under the `value` column (e.g., `SNOWFLAKE.TELEMETRY.EVENTS`).
If no event table is set, configure the default:

```sql
ALTER ACCOUNT SET EVENT_TABLE = 'SNOWFLAKE.TELEMETRY.EVENTS';
```

**Verify change tracking is enabled** (required for incremental processing):
```sql
SHOW TABLES LIKE '<event_table_name>' IN SCHEMA <database>.<schema>;
```

Look for `change_tracking` column. If `OFF`, enable it:
```sql
ALTER TABLE <database>.<schema>.<event_table_name> SET CHANGE_TRACKING = TRUE;
```

> Note: `SNOWFLAKE.TELEMETRY.EVENTS` typically has change tracking enabled already — verify before running.

---

## Step 2.2 — Create a Dedicated Schema

```sql
CREATE DATABASE IF NOT EXISTS <your_database>;
CREATE SCHEMA IF NOT EXISTS <your_database>.rai_observability;
```

`rai_observability` is a recommendation — use any name that fits your conventions.

---

## Step 2.3 — Create the RAI Events View

This view filters the Snowflake Event Table to RAI-related metrics only. It is entirely under your
control and determines what telemetry the app can access.

```sql
CREATE OR REPLACE SECURE VIEW <your_database>.rai_observability.rai_obs
  COMMENT = 'RelationalAI Native App Observability: This view provides filtered event data
             for RelationalAI observability and is registered within the Native App.
             Please refrain from changing or deleting.'
  CHANGE_TRACKING = TRUE
AS
SELECT
  timestamp,
  value,
  record,
  record_attributes
FROM <event_table>                                              -- from Step 2.1
WHERE record_type = 'METRIC'
  AND resource_attributes['snow.database.name']::STRING = '<rai_app_name>'   -- e.g. RELATIONALAI
  AND record_attributes['snow.application.shared']::BOOLEAN = TRUE
  AND timestamp >= '<start_date>';                             -- e.g. 2026-02-01
```

**Replace placeholders:**
- `<your_database>` — database from Step 2.2
- `<event_table>` — fully qualified table name from Step 2.1
- `<rai_app_name>` — database name of your RAI Native App installation (e.g., `RELATIONALAI`)
- `<start_date>` — use today's date

**Required columns in the view:**

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | TIMESTAMP_NTZ | When the event occurred (UTC) |
| `value` | VARIANT | Primary measurement value |
| `record` | VARIANT | Telemetry record (includes metric name) |
| `record_attributes` | OBJECT | Event-specific attributes and measurements |

**Why `SECURE VIEW`:** Hides the view definition from non-owners — recommended for production.

---

## Step 2.4 — Register the View

```sql
CALL <rai_app>.app.REGISTER_EVENTS_VIEW(
  SYSTEM$REFERENCE('view', '<your_database>.rai_observability.rai_obs', 'PERSISTENT', 'SELECT')
);
```

Replace `<rai_app>` with your RAI Native App installation name and `<your_database>` with the database
from Step 2.3.

**Registration error reference:**

| Error | Cause | Resolution |
|-------|-------|-----------|
| Failed to bind view reference | Null or invalid reference | Provide a valid `SYSTEM$REFERENCE()` |
| A view is already registered | View already bound | Call `UNREGISTER_EVENTS_VIEW()` first |
| Missing a required column | View is missing required columns | Ensure all 4 required columns are present |
| Failed to enable CHANGE_TRACKING | Change tracking not enabled | Enable `CHANGE_TRACKING = TRUE` on view and underlying table(s) |

---

## Step 2.5 — Unregister the View (if needed)

Use to replace or update a registered view:
```sql
CALL <rai_app>.app.UNREGISTER_EVENTS_VIEW();
```

Common reasons: replacing the view, renaming the database/schema, or clearing a broken registration.
After unregistering, call `REGISTER_EVENTS_VIEW()` again to re-enable observability.

---

## Step 2.6 — Validate Configuration

```sql
CALL <rai_app>.app.CHECK_EVENTS_VIEW_STATUS();
```

Run this at any time to validate configuration and check that events are flowing. See the status
table in SKILL.md Step 1 for interpretation.

---

## Cost Monitoring

Track the compute credits consumed by observability queries:

```sql
SELECT query_id, query_text, total_elapsed_time, credits_used_cloud_services
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE query_text ILIKE '%<rai_app_database>.observability%'
  AND start_time >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY total_elapsed_time DESC;
```