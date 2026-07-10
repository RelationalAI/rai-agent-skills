# Why Marketplace paid usage, not `ACCOUNT_USAGE`, for cross-account lookups

## The constraint

Snowflake's `SNOWFLAKE.ACCOUNT_USAGE.*` views (used throughout this skill's
query templates — see [queries.md](queries.md) — `SNOWPARK_CONTAINER_SERVICES_HISTORY`,
`APPLICATION_DAILY_USAGE_HISTORY`, `STORAGE_USAGE`) are always scoped to the
account you're connected to. There is no way to query another account's
`ACCOUNT_USAGE` data from a different account, even as a Marketplace
provider — this is a Snowflake platform constraint, not a permissions issue
that can be granted around.

The one exception: `SNOWFLAKE.DATA_SHARING_USAGE.MARKETPLACE_PAID_USAGE_DAILY`
is queryable from the **provider** account and includes a row per consumer
account, because the provider needs to see who owes them money for a paid
listing. This is the only legitimate cross-account visibility RAI has into a
customer's usage without a dedicated connection into that customer's own
account.

## Assumed schema (unverified — verify before relying on it)

This was not confirmed against a live account: every configured `snow`
connection in this environment used `authenticator =
"OAUTH_AUTHORIZATION_CODE"`, which requires an interactive browser login, so
a headless/background session could not run `DESCRIBE VIEW` or a `SELECT *
... LIMIT 1` to check it directly.

Per Snowflake's published documentation for this view, expect columns along
these lines:

| Column | Purpose |
|---|---|
| `USAGE_DATE` | Day of usage |
| `ORGANIZATION_NAME` / `ACCOUNT_NAME` | The **provider's** own org/account (RAI) |
| `CONSUMER_ORGANIZATION_NAME` | The customer's Snowflake organization |
| `CONSUMER_ACCOUNT_NAME` | The customer's specific account |
| `CONSUMER_ACCOUNT_LOCATOR` | Account locator for the consumer |
| `LISTING_ID` / `LISTING_GLOBAL_NAME` | Which Marketplace listing this usage is against |
| `APPLICATION_NAME` | Should be `RELATIONALAI` for RAI's native app listing |
| `CHARGE_TYPE` | e.g. compute/storage charge category |
| `USAGE` | Quantity |
| `CURRENCY` | Currency the usage/charge is denominated in |

**Always run the `LIMIT 1` probe in SKILL.md §4 first** and match the real
column names against this table rather than assuming it's accurate — this
list may be incomplete, renamed, or version-drifted from what your account
actually returns. Update this file once verified so future runs skip the
probe.

## What Mode B genuinely can't tell you

Marketplace paid usage is a billing-level rollup (usage/charge by listing and
charge type). It does **not** give you the compute-pool-level or
service-type-level granularity that Mode A gets from a direct connection
(which compute pool, which instance family, HIGHMEM vs GPU, etc.). If the
user needs that level of detail for an account with no dedicated connection,
the honest answer is that it isn't obtainable without one — say so rather
than approximating it from Marketplace figures.
