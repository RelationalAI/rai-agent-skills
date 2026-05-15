# Synthetic representative fixture

## Source

Hand-built per [`notes/phase1-synthetic-schema-spec.md`](../../../../../notes/phase1-synthetic-schema-spec.md). Domain: small e-commerce + fulfilment. Designed to exercise every constraint-inference path and every antipattern category at least twice within a realistic schema shape.

## Files

| File | Tracked? | Contents |
|---|---|---|
| `schema.sql` | yes | 21-table DDL + sample data (502 lines) |
| `README.md` | yes | This file |

Unlike the Northwind and TPC-H fixtures, the synthetic schema is hand-built and committed directly — no fetch script, no licensing constraints (it's our own work, Apache 2.0 alongside the rest of the repo).

## Antipatterns planted

| Antipattern | Where | Notes |
|---|---|---|
| Denormalized address | `CUSTOMER` and `WAREHOUSE` tables — both carry `ADDRESS_LINE1/2`, `CITY`, `STATE`, `ZIP`, `COUNTRY` columns | Contrasted with `CUSTOMER_ADDRESS` (the canonical 1:N normalization). The SRP should flag both denormalized cases and propose extracting an `Address` value type. |
| Encoded enum in VARCHAR | `ORDERS.STATUS`, `SHIPMENT_EVENT.EVENT_TYPE`, `RETURN_REQUEST.REASON`, `PAYMENT.METHOD`, `CUSTOMER.TIER`, `PRODUCT.TYPE` — all VARCHAR with **no** declared CHECK constraint | Sample probing (Step 5) discovers the small distinct-value sets; Step 7 flags as antipattern; Step 9 promotes to `model.Enum`. |
| Ambiguous junction (no extras) | `ORDER_ITEM_TAG` — composite all-FK PK, no other columns | SRP default = pure m:n binary. |
| Ambiguous junction (with extras) | `ORDER_PROMOTION` — composite all-FK PK + `APPLIED_AT` column | SRP default = objectified entity. |
| TYPE-column subtype split | `PRODUCT.TYPE` + `PHYSICAL_PRODUCT_DETAILS` / `DIGITAL_PRODUCT_DETAILS` / `SUBSCRIPTION_PRODUCT_DETAILS` side tables | Each side table has rows only for products whose TYPE matches; SRP should detect the partition and emit subtypes with `extends=[Product]`. |

## Constraint-inference targets

The schema deliberately omits CHECK constraints on the encoded-enum columns and on most numeric ranges (`QUANTITY`, `DISCOUNT`, `QUANTITY_ON_HAND`, etc.) — those constraints come from sample probing. The full list of inference targets and their expected sources lives in the spec.

Key targets:
- `PRODUCT_CATEGORY.PARENT_CATEGORY_ID` self-FK → common-sense ring (acyclic + asymmetric + irreflexive).
- `INVENTORY_TRANSFER.FROM_WAREHOUSE_ID` and `TO_WAREHOUSE_ID` (same FK target) → common-sense ring (irreflexive — "transfer" semantics).
- `ORDERS.PLACED_AT <= SHIPPED_AT <= DELIVERED_AT` → common-sense temporal ordering on lifecycle timestamps.
- `RETURN_REQUEST → ORDERS.STATUS = 'DELIVERED'` → LLM-inferred subset (returns presuppose delivery).
- `CUSTOMER.EMAIL` uniqueness → common-sense (universal convention; not declared in DDL).

## Loading the fixture

Postgres:
```bash
createdb synthetic
psql -d synthetic -f schema.sql
```

The schema and sample data are in a single file (the synthetic is small enough that splitting them adds no value). The `INSERT` statements are at the end and ordered to respect FK dependencies.

## Sample data sizing

| Table | Rows |
|---|---|
| PRODUCT_CATEGORY | 10 (3-deep tree, no cycles) |
| PRODUCT | 15 (5 PHYSICAL, 5 DIGITAL, 5 SUBSCRIPTION) |
| *_PRODUCT_DETAILS | 5 each |
| CUSTOMER | 10 (all 3 tiers) |
| CUSTOMER_ADDRESS | 4 |
| WAREHOUSE | 3 |
| INVENTORY | 14 |
| INVENTORY_TRANSFER | 5 (all distinct from/to) |
| ORDERS | 20 (all 5 statuses; 8 DELIVERED, 3 SHIPPED, 4 PAID, 3 PENDING, 2 CANCELLED) |
| ORDER_ITEM | 35 (1-5 per order) |
| TAG | 5 |
| ORDER_ITEM_TAG | 10 |
| CARRIER | 4 |
| SHIPMENT | 11 |
| SHIPMENT_EVENT | 25 (2-3 per shipment) |
| RETURN_REQUEST | 5 (all against DELIVERED orders) |
| PAYMENT | 15 (one per non-cancelled order) |
| PROMOTION_CODE | 5 |
| ORDER_PROMOTION | 6 |

Sample sizes are below the 1000-row "confirmed promotion" threshold ([probing-strategies.md](../../../references/probing-strategies.md)), so sample-derived constraints stay `proposed` until user confirms at Step 9b. With a real production-scale dataset they would auto-promote to `confirmed`.
