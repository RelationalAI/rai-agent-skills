# Query templates and rate tables

Self-contained copies of the SQL templates, rate tables, and query-building
logic this skill drives from — mirrored from the RelationalAI Observability
Dashboard's `rai_observability_dashboard.py` (the Streamlit app backing the
live UI mentioned in this skill's frontmatter) so this skill has no runtime
dependency on that file's location. Treat this file, not the dashboard, as
the source of truth when running the workflow in [SKILL.md](../SKILL.md) —
if the dashboard's logic changes in a way that matters, update this file to
match rather than going back to the dashboard at run time.

Every query below takes `{db}` (the RelationalAI Native App database,
usually `RELATIONALAI`), `{date_from}`, and `{date_to}` — substitute with
Python `str.format()`-style placeholders before running via `snow sql -q`.

## `_Q_CREDITS_TOTAL` — SPCS credits by compute pool (total)

```sql
SELECT COMPUTE_POOL_NAME, SUM(CREDITS_USED) AS CREDITS_USED
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
WHERE APPLICATION_NAME = 'RELATIONALAI'
  AND START_TIME >= '{date_from}'
  AND START_TIME <  DATEADD(day, 1, '{date_to}')
GROUP BY COMPUTE_POOL_NAME
ORDER BY CREDITS_USED DESC
```

## `_Q_CREDITS_DAILY` — SPCS credits by compute pool (daily trend)

```sql
SELECT DATE_TRUNC('day', START_TIME) AS DAY,
    COMPUTE_POOL_NAME,
    SUM(CREDITS_USED)                AS CREDITS_USED
FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY
WHERE APPLICATION_NAME = 'RELATIONALAI'
  AND START_TIME >= '{date_from}'
  AND START_TIME <  DATEADD(day, 1, '{date_to}')
GROUP BY DAY, COMPUTE_POOL_NAME
ORDER BY DAY ASC
```

## `_Q_CREDITS_BREAKDOWN` — full service-type split

SPCS / warehouse metering / serverless task, from
`APPLICATION_DAILY_USAGE_HISTORY`. **Does not include storage** — Snowflake
doesn't support attributing storage per native app, so storage must come
from `_Q_STORAGE_USAGE` (account-wide) separately.

```sql
SELECT
    USAGE_DATE,
    CREDITS_USED AS TOTAL_CREDITS,
    SUM(CASE WHEN b.value:"serviceType"::STRING = 'WAREHOUSE_METERING'
             THEN b.value:"credits"::NUMBER(38,9) ELSE 0 END) AS WAREHOUSE_METERING_CREDITS,
    SUM(CASE WHEN b.value:"serviceType"::STRING = 'SERVERLESS_TASK'
             THEN b.value:"credits"::NUMBER(38,9) ELSE 0 END) AS SERVERLESS_TASK_CREDITS,
    SUM(CASE WHEN b.value:"serviceType"::STRING = 'SNOWPARK_CONTAINER_SERVICES'
             THEN b.value:"credits"::NUMBER(38,9) ELSE 0 END) AS SNOWPARK_CONTAINER_SERVICES_CREDITS
FROM SNOWFLAKE.ACCOUNT_USAGE.APPLICATION_DAILY_USAGE_HISTORY,
    LATERAL FLATTEN(INPUT => CREDITS_USED_BREAKDOWN, OUTER => TRUE) b
WHERE APPLICATION_NAME = 'RELATIONALAI'
  AND USAGE_DATE >= '{date_from}'
  AND USAGE_DATE <= '{date_to}'
GROUP BY USAGE_DATE, CREDITS_USED
ORDER BY USAGE_DATE DESC
```

Reconciliation note (surfaces the same caveat the dashboard shows): this
query's `SNOWPARK_CONTAINER_SERVICES_CREDITS` figure comes from the native
app's self-reported `APPLICATION_DAILY_USAGE_HISTORY`, while the cost
estimate below comes from `METERING_HISTORY` via `SNOWPARK_CONTAINER_SERVICES_HISTORY`
— Snowflake's direct metering of the underlying compute pools. Small
differences (~1–2%) between the two are expected (rounding, attribution
timing) and don't indicate an error in either figure.

## `_Q_STORAGE_USAGE` — account storage (database/failsafe/stage TB)

Account-wide, not RAI-attributable specifically (RAI uses randomly-named
stages for model storage, so spikes here may correlate with RAI activity
but can't be isolated to it).

```sql
SELECT
    USAGE_DATE,
    ROUND(STORAGE_BYTES  / POWER(1024, 4), 4) AS DATABASE_TB,
    ROUND(FAILSAFE_BYTES / POWER(1024, 4), 4) AS FAILSAFE_TB,
    ROUND(STAGE_BYTES    / POWER(1024, 4), 4) AS STAGE_TB,
    ROUND((STORAGE_BYTES + FAILSAFE_BYTES + STAGE_BYTES) / POWER(1024, 4), 4) AS TOTAL_TB
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE USAGE_DATE >= '{date_from}'
  AND USAGE_DATE <= '{date_to}'
ORDER BY USAGE_DATE DESC
```

Snowflake list-price storage rates (USD per TB per month), used to turn
`TOTAL_TB` into an estimated cost — same list-price caveat as everywhere
else in this skill (confirm the account's actual negotiated rate if
precision matters):

| Tier | $/TB/month |
|---|---|
| On-Demand | $40.00 |
| Capacity  | $23.00 |

Estimated daily cost = `TOTAL_TB × rate / 30`.

## `_Q_MARKETPLACE_PAID` — Marketplace paid usage (Mode B fallback)

```sql
SELECT TOP 100 * FROM snowflake.data_sharing_usage.marketplace_paid_usage_daily
```

(SKILL.md §4 filters this further by consumer account/org and date range
once the real column names are confirmed via a `LIMIT 1` probe — see
[marketplace_schema.md](marketplace_schema.md).)

## `_show_compute_pools` — list RAI-owned compute pools

```sql
SHOW COMPUTE POOLS
```

Then filter the result to the `name`, `instance_family`, and `application`
columns, keeping only rows where `application = 'RELATIONALAI'`.

## `_SURCHARGE_RATES` — SPCS credit/surcharge rates by instance family

Standard-edition dollar rates (Snowflake Service Consumption Table, Apr
2026). `credits_per_hour` converts a pool's `CREDITS_USED` into node-hours;
`surcharge_per_hour` is the RAI software surcharge in USD/node-hour (`—` =
not applicable, e.g. plain CPU pools carry no RAI surcharge).

| `instance_family` | credits_per_hour | surcharge_per_hour (Standard, USD) |
|---|---|---|
| HIGHMEM_X64_L  | 4.44 | 124 |
| HIGHMEM_X64_SL | 2.93 | 92  |
| HIGHMEM_X64_M  | 1.11 | 28  |
| HIGHMEM_X64_S  | 0.28 | 6   |
| GPU_NV_S       | 0.57 | 18  |
| CPU_X64_M      | 0.22 | —   |
| CPU_X64_S      | 0.11 | —   |
| CPU_X64_XS     | 0.06 | —   |

For Enterprise/Business Critical dollar rates and the RAI Units table, see
[surcharge_rates.md](surcharge_rates.md) — that file's per-edition
multipliers apply on top of the Standard `surcharge_per_hour` values above.

## `_build_cost_estimate_query` — projected surcharge USD

Given the RAI-owned pools from `_show_compute_pools` (each with a `name` and
`instance_family`) and a `{date_from}`/`{date_to}` range, build and run:

```sql
WITH pool_rates AS (
    -- one row per RAI pool with a known instance_family:
    -- SELECT '<pool_name>' AS pool_name, <credits_per_hour> AS credits_per_hour, <surcharge_per_hour_or_NULL> AS surcharge_per_hour
    -- ... UNION ALL ...
),
pool_families AS (
    -- one row per RAI pool:
    -- SELECT '<pool_name>' AS pool_name, '<instance_family>' AS instance_family
    -- ... UNION ALL ...
),
consumption AS (
    SELECT
        h.START_TIME,
        h.COMPUTE_POOL_NAME,
        pf.instance_family,
        h.CREDITS_USED,
        r.credits_per_hour,
        r.surcharge_per_hour,
        h.CREDITS_USED / NULLIF(r.credits_per_hour, 0)        AS node_hours,
        (h.CREDITS_USED / NULLIF(r.credits_per_hour, 0))
            * r.surcharge_per_hour                             AS projected_surcharge_usd
    FROM SNOWFLAKE.ACCOUNT_USAGE.SNOWPARK_CONTAINER_SERVICES_HISTORY h
    JOIN pool_rates r          ON h.COMPUTE_POOL_NAME = r.pool_name
    LEFT JOIN pool_families pf ON h.COMPUTE_POOL_NAME = pf.pool_name
    WHERE h.APPLICATION_NAME = 'RELATIONALAI'
      AND h.START_TIME >= '{date_from}'
      AND h.START_TIME <  DATEADD(day, 1, '{date_to}')
)
SELECT
    DATE_TRUNC('day', START_TIME)  AS usage_date,
    COMPUTE_POOL_NAME,
    instance_family,
    SUM(CREDITS_USED)              AS total_credits,
    SUM(node_hours)                AS total_node_hours,
    SUM(projected_surcharge_usd)   AS total_projected_surcharge_usd
FROM consumption
GROUP BY 1, 2, 3
ORDER BY usage_date DESC, total_projected_surcharge_usd DESC NULLS LAST
```

Populate `pool_rates` and `pool_families` from the live `_show_compute_pools`
result: one `UNION ALL` row per RAI pool, looking up `credits_per_hour` /
`surcharge_per_hour` for its `instance_family` in the `_SURCHARGE_RATES`
table above. Skip pools whose `instance_family` isn't in that table (unknown
rate). If the confirmed Snowflake edition is Enterprise or Business
Critical, multiply every `surcharge_per_hour` value by that edition's
multiplier (1.5× / 2×, per [surcharge_rates.md](surcharge_rates.md)) before
building `pool_rates`.
