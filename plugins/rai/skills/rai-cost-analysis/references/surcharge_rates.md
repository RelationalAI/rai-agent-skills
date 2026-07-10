# RAI surcharge & RAI Unit rates by Snowflake edition

The `_SURCHARGE_RATES` table (see [queries.md](queries.md)) hardcodes
**Standard edition** dollar rates only. Enterprise and Business Critical
multiply those same dollar rates — they do not change the number of RAI
Units a pool consumes per node-hour, only the dollar price of each unit.

- **Enterprise** surcharge $/node-hr = Standard rate × **1.5**
- **Business Critical** surcharge $/node-hr = Standard rate × **2.0**

## Per-instance-family rates

| Instance family | RAI Units / node-hr (fixed, all editions) | Standard $/hr | Enterprise $/hr | Business Critical $/hr |
|---|---|---|---|---|
| HIGHMEM_X64_L  | 62 | $124.00 | $186.00 | $248.00 |
| HIGHMEM_X64_SL | 46 | $92.00  | $138.00 | $184.00 |
| HIGHMEM_X64_M  | 14 | $28.00  | $42.00  | $56.00  |
| HIGHMEM_X64_S  | 3  | $6.00   | $9.00   | $12.00  |
| GPU_NV_S       | 9  | $18.00  | $27.00  | $36.00  |
| CPU_X64_M      | 0  | —       | —       | —       |
| CPU_X64_S      | 0  | —       | —       | —       |
| CPU_X64_XS     | 0  | —       | —       | —       |

RAI Units/node-hr is **edition-invariant** by construction: it equals
Standard $/hr ÷ $2, and also equals Enterprise $/hr ÷ $3, and Business
Critical $/hr ÷ $4 — all three resolve to the same unit count for a given
family. This is why RAI Units consumed doesn't need to be recomputed per
edition, only the dollar price applied to it does.

## $/RAI Unit and $/Snowflake credit by edition

Per the user's guidance, the Snowflake credit price used for the
"Snowflake compute cost" side of a report tracks the same per-edition scale
as the RAI Unit price (both are list-price simplifications — always confirm
the account's actual negotiated Snowflake contract rate if precision
matters):

| Edition | $/RAI Unit | $/Snowflake credit (list-price assumption) |
|---|---|---|
| Standard | $2 | $2 |
| Enterprise | $3 | $3 |
| Business Critical | $4 | $4 |

## Formulas

```
edition_multiplier(edition) = 1.0 (Standard) | 1.5 (Enterprise) | 2.0 (Business Critical)
surcharge_$_per_hour(family, edition) = standard_rate(family) × edition_multiplier(edition)
RAI_units_per_hour(family) = standard_rate(family) / 2        # invariant across editions
node_hours(pool) = CREDITS_USED(pool) / credits_per_hour(family)   # from _SURCHARGE_RATES
surcharge_usd(pool, edition) = node_hours(pool) × surcharge_$_per_hour(family, edition)
rai_units(pool) = node_hours(pool) × RAI_units_per_hour(family)
snowflake_cost_usd(pool, edition) = credits(pool) × price_per_credit(edition)
```

## How to determine the account's edition

Cannot reliably be queried from a customer/consumer-side connection:

- `SHOW ACCOUNTS` run from a non-organization-account connection omits the
  `edition` column entirely (only returns `organization_name`,
  `account_name`, `snowflake_region`, `account_locator`,
  `is_organization_account`).
- `SNOWFLAKE.ORGANIZATION_USAGE.ACCOUNTS` returns zero rows unless the
  query is run from the organization's designated admin account.

**Always ask the user which edition the account is on** (Standard /
Enterprise / Business Critical) before computing any surcharge or
Snowflake-cost figures — never assume Standard by default.
