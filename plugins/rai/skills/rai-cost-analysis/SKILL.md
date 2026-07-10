---
name: rai-cost-analysis
description: >-
  Look up or explain RelationalAI Snowflake credit consumption, cost
  estimate, and Marketplace paid usage for a specific customer account, or
  more generally understand/summarize account usage of the RelationalAI
  service. Use for specific asks ("how much is <account> using", "what's
  <account>'s RAI credit spend", "marketplace revenue/usage for <account>")
  AND for open-ended ones ("help me understand account usage for
  RelationalAI", "what's this account's RAI usage look like", "summarize RAI
  usage/spend"). Also handles the no-account case (report on whatever
  account the active connection points to). Don't use for the Streamlit
  dashboard's own live UI — that's rai_observability_dashboard.py; this
  skill is for one-off chat-driven lookups via the `snow` CLI.
---

# RAI Account Usage Lookup

Reports RelationalAI credit consumption, cost estimate, and Marketplace usage
for one Snowflake account, driven entirely from the command line via the
`snow` CLI (already installed — `snow --version` to confirm).

## Summary

**What:** Chat-driven lookup of RelationalAI Snowflake credit consumption,
projected cost, and Marketplace paid usage for a single account — resolves an
account to a `snow` connection (or falls back to Marketplace-only visibility
if there isn't one), runs read-only queries, and reports a short markdown
summary.

**When to use:**
- Specific asks: "how much is `<account>` using", "what's `<account>`'s RAI
  credit spend", "marketplace revenue/usage for `<account>`"
- Open-ended asks: "help me understand account usage for RelationalAI",
  "what's this account's RAI usage look like", "summarize RAI usage/spend"
- No-account case: report on whatever account the active connection points to

**When NOT to use:**
- The Streamlit dashboard's own live UI — that's `rai_observability_dashboard.py`;
  this skill is the one-off chat-driven equivalent, not a replacement for it
- Reasoner performance, failed transactions, or CDC/data-stream health → see
  `rai-health`
- First-time install, Snowflake connection, or `raiconfig.yaml` setup → see
  `rai-setup`

**Overview (process steps):**
1. Parse the request for an account identifier and date range (§1)
2. Resolve the account to a `snow` connection, or fall back to Marketplace-only
   visibility if none exists (§2)
3. Mode A — run the full in-account credit/storage/cost-estimate queries,
   edition-aware (§3)
4. Mode B — probe and query Marketplace paid usage only (§4)
5. Report a short markdown summary, not a raw dump (§5)

**Source of truth for SQL**: don't hand-write the queries below from scratch
every time. The maintained templates — `_Q_CREDITS_TOTAL`, `_Q_CREDITS_DAILY`,
`_Q_CREDITS_BREAKDOWN`, `_Q_STORAGE_USAGE`, `_Q_MARKETPLACE_PAID`,
`_SURCHARGE_RATES`, `_build_cost_estimate_query`, and `_show_compute_pools` —
are mirrored in [references/queries.md](references/queries.md), copied from
the RelationalAI Observability Dashboard's Streamlit app so this skill has no
runtime dependency on that app's location. Read that reference at the start
of each run and reuse those query templates verbatim (with
`{db}`/`{date_from}`/`{date_to}` substituted).

## 1. Parse the request

- Extract an **account identifier** from the user's ask (a connection profile
  name, a Snowflake account locator, or a customer/org name), and an optional
  **date range** (default: last 30 days, matching the dashboard's default).
- If no account is mentioned at all, skip resolution and just use whatever
  connection is already active / default (`snow connection list` shows a
  `is_default` flag) — report on that account directly, same as running the
  dashboard locally.

## 2. Resolve the account to a connection

```bash
snow connection list --format json
```

- Match the given identifier case-insensitively against the connection
  **names** (not necessarily the Snowflake `account` field — connection
  profiles are typically named after the customer/environment they point to,
  e.g. a profile literally named after the customer, or a `*_PROVIDER` /
  `*_CONSUMER` suffix for RAI's own environments).
- **Match found** → Mode A (full in-account breakdown, §3). This is the
  richer report: it can see the account's own `ACCOUNT_USAGE` views directly.
- **No match** → Mode B (Marketplace-only fallback, §4). Tell the user
  up front that without a dedicated connection profile, only Snowflake
  Marketplace paid-usage data is visible from the provider side — the
  detailed SPCS/warehouse/storage credit split lives inside the customer's
  own account and isn't queryable cross-account.
- If it's ambiguous which profile the user means (e.g. partial match against
  multiple), ask them to confirm rather than guessing.

Every `snow sql` call in both modes below uses `-c <connection_name>`.

**Auth note**: every configured connection uses `authenticator =
"OAUTH_AUTHORIZATION_CODE"`, which requires an interactive browser login on
first use. If a query fails with an OAuth/`client_id` error, tell the user to
run `snow connection test -c <name>` themselves in an interactive terminal to
complete the browser flow, then retry — this skill cannot complete OAuth in a
headless/background session.

## 3. Mode A — full in-account breakdown

**Before computing any cost/surcharge figures, ask the user which Snowflake
edition the account is on** (Standard / Enterprise / Business Critical).
This can't be reliably determined from a customer/consumer-side connection
(see [references/surcharge_rates.md](references/surcharge_rates.md) for why
`SHOW ACCOUNTS` and `ORGANIZATION_USAGE.ACCOUNTS` don't expose it here) —
never assume Standard by default, since it changes both the RAI surcharge
multiplier and the $/credit rate used for the Snowflake-cost side of the
report.

Run, against the resolved connection:

1. `_Q_CREDITS_TOTAL` and `_Q_CREDITS_DAILY` — SPCS credits by compute pool.
2. `_Q_CREDITS_BREAKDOWN` — full service-type split (SPCS / warehouse
   metering / serverless task) from `APPLICATION_DAILY_USAGE_HISTORY`.
3. `_Q_STORAGE_USAGE` — account storage (database/failsafe/stage TB), same
   as the dashboard's "Account Storage Usage Over Time" section.
4. Cost estimate: run `SHOW COMPUTE POOLS` (per `_show_compute_pools` in
   [references/queries.md](references/queries.md)), filter to
   `application = 'RELATIONALAI'`, then build and run the
   `_build_cost_estimate_query` template from that same reference to get
   projected surcharge USD using the `_SURCHARGE_RATES` table — this gives
   **Standard-edition** dollar rates. If the confirmed edition is Enterprise
   or Business Critical, multiply every `_SURCHARGE_RATES` surcharge value by
   that edition's multiplier (1.5× / 2×) **before** building the cost-estimate
   query — see [references/surcharge_rates.md](references/surcharge_rates.md)
   for the full per-edition rate table and formulas.

Example invocation pattern:

```bash
snow sql -c <connection_name> -q "<rendered _Q_CREDITS_BREAKDOWN with db/date_from/date_to substituted>" --format json
```

## 4. Mode B — Marketplace-only fallback

Use RAI's own Marketplace **provider** connection — from `snow connection
list`, look for the profile whose name suggests it's the provider-side
account (commonly has `PROVIDER` in the name, as opposed to `CONSUMER`
profiles which point at customer-facing environments). If more than one
looks plausible, ask the user which one is the Marketplace provider account.
See [references/marketplace_schema.md](references/marketplace_schema.md) for
background on why this view (and not `ACCOUNT_USAGE`) is the one to use here.

**First, probe the schema before filtering** — the exact consumer-account
column name isn't verified in this environment (all connections are
OAuth-only and couldn't be queried headlessly during development of this
skill):

```bash
snow sql -c <provider_connection_name> \
  -q "SELECT * FROM snowflake.data_sharing_usage.marketplace_paid_usage_daily LIMIT 1;" \
  --format json
```

Inspect the returned columns for the consumer-identifying field — expect
something like `CONSUMER_ACCOUNT_NAME` and/or `CONSUMER_ORGANIZATION_NAME`
(per Snowflake's documented schema for this view). Then filter:

```sql
SELECT *
FROM snowflake.data_sharing_usage.marketplace_paid_usage_daily
WHERE (CONSUMER_ACCOUNT_NAME = '<account>' OR CONSUMER_ORGANIZATION_NAME = '<account>')
  AND USAGE_DATE >= '<date_from>' AND USAGE_DATE <= '<date_to>'
ORDER BY USAGE_DATE DESC
```

Adjust the column names to whatever the LIMIT 1 probe actually returns before
running the filtered query — don't assume.

## 5. Report format

Summarize as a short markdown report, not a raw dump:

- **Account**: name/connection used, mode (A or B), date range.
- **Total credits** (Mode A: from `_Q_CREDITS_BREAKDOWN`; Mode B: from
  Marketplace usage rows) and the RAI-surcharge-vs-infrastructure split if
  Mode A.
- **Projected RAI engine cost estimate (USD)** from the surcharge query
  (Mode A only) — flag it as a list-price estimate, same caveat the
  dashboard shows ("actual invoiced amounts depend on your Snowflake
  contract").
- **Storage** latest TB + estimated monthly cost (Mode A only).
- A one-line note on what couldn't be captured and why (e.g. "no dedicated
  connection for this account — showing Marketplace-reported usage only,
  not the per-compute-pool breakdown").
- A small table of the top few rows if useful, not the entire result set.

### Combined Snowflake + RAI cost tables

Whenever a report shows both a Snowflake compute cost (credits × a $/credit
rate — always user-supplied or explicitly flagged as an assumption, never
invented) and the RAI surcharge, always give **both** of the following
tables, not just one:

1. **Per-pool (or per-instance-family) breakdown** — one row per compute
   pool, columns for node-hours, Snowflake credits, Snowflake cost, RAI
   Units (see below), RAI surcharge, and a Total column. This is the
   detailed view a user needs to see which pool is driving cost.
2. **Aggregated summary** — cost type as rows (Snowflake cost, RAI
   surcharge, Total), breakdown dimension as columns (infra type / pool /
   instance family), e.g.:

   | Cost type | SNOWPARK_CONTAINER_SERVICES | WAREHOUSE_METERING | SERVERLESS_TASK | Total |
   |---|---|---|---|---|
   | Snowflake cost (@$X/credit) | ... | ... | ... | ... |
   | RAI surcharge | ... | — | — | ... |
   | Total | ... | ... | ... | ... |

   This makes it easy to scan Snowflake-only vs. RAI-only totals across the
   breakdown dimension at a glance.

Always include the **RAI Units** consumed alongside the dollar surcharge
when Units are relevant to the ask (node_hours × RAI-Unit rate for that
instance family — this count is fixed regardless of edition; only the
dollar price applied to it changes). Full per-edition surcharge-rate table,
RAI-Unit rates, $/credit-by-edition table, and the reasoning/formulas behind
all of it live in
[references/surcharge_rates.md](references/surcharge_rates.md) — read it
whenever a cost/surcharge/unit figure needs computing so the rates and
edition-check requirement never drift out of sync with this file.

## Safety

Every query here is read-only (`SELECT`, `SHOW COMPUTE POOLS`, `DESCRIBE`).
No confirmation needed to run them. Never write, mutate, or drop anything in
this skill's scope.
