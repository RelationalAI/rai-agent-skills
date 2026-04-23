# Transaction Debug Reference

<!-- TOC -->
- [API Overview](#api-overview)
- [get_transaction](#get_transaction)
- [get_transaction_problems / get_own_transaction_problems](#get_transaction_problems--get_own_transaction_problems)
- [get_load_errors](#get_load_errors)
- [Owner-Restriction Details](#owner-restriction-details)
<!-- /TOC -->

---

## API Overview

| Procedure | Schema | Access |
|-----------|--------|--------|
| `get_transaction('<id>')` | `relationalai.api` | Admin roles |
| `get_transaction_problems('<id>')` | `relationalai.api` | Admin roles |
| `get_own_transaction_problems('<id>')` | `relationalai.api` | Any role (own transactions only) |
| `get_load_errors('<id>')` | `relationalai.api` | Admin roles |

---

## get_transaction

Returns the full transaction record.

```sql
CALL relationalai.api.get_transaction('<transaction_id>');
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR | Transaction UUID |
| `account` | VARCHAR | Snowflake account identifier |
| `database` | VARCHAR | RAI app database name |
| `owner` | VARCHAR | Identity that initiated the transaction |
| `state` | VARCHAR | `COMPLETED`, `ABORTED`, `RUNNING`, etc. |
| `created_on` | TIMESTAMP_NTZ | Transaction start time |
| `finished_on` | TIMESTAMP_NTZ | Transaction end time (null if still running) |
| `error_message` | VARCHAR | High-level error text (if aborted) |

---

## get_transaction_problems / get_own_transaction_problems

Returns the list of problems (logical errors, constraint violations, load failures) attached to a transaction.

```sql
-- Admin: any transaction
CALL relationalai.api.get_transaction_problems('<transaction_id>');

-- End-user: only transactions you own
CALL relationalai.api.get_own_transaction_problems('<transaction_id>');
```

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | VARCHAR | Parent transaction UUID |
| `problem_type` | VARCHAR | Category: `INTEGRITY_CONSTRAINT`, `LOAD_ERROR`, `SYSTEM_ERROR`, etc. |
| `message` | VARCHAR | Human-readable error description |
| `source` | VARCHAR | Source relation or file that triggered the problem |
| `row_count` | NUMBER | Number of affected rows (for load errors) |

---

## get_load_errors

Returns row-level load errors for a specific transaction.

```sql
CALL relationalai.api.get_load_errors('<transaction_id>');
```

| Column | Type | Description |
|--------|------|-------------|
| `transaction_id` | VARCHAR | Parent transaction UUID |
| `source_object` | VARCHAR | Table or stream that produced the bad rows |
| `error_message` | VARCHAR | Parse or type-conversion error detail |
| `error_count` | NUMBER | Number of rows that failed |
| `sample_row` | VARIANT | One representative bad row (for diagnosis) |

---

## Owner-Restriction Details

**Symptom:** Calling `get_transaction_problems` on a transaction returns HTTP 400.

**Root cause:** The transaction is owned by `cdc.scheduler@erp`, an internal RAI service identity. End-user roles cannot see transactions owned by this account — the API returns 400 (not 404 and not an empty result). This is expected behavior, not a bug.

**Diagnosis path when you hit a 400:**

1. First, verify the transaction owner:
   ```sql
   CALL relationalai.api.get_transaction('<transaction_id>');
   -- If "owner" = 'cdc.scheduler@erp', the steps below apply
   ```

2. Check CDC status to find the relevant pipeline state:
   ```sql
   SELECT * FROM relationalai.api.cdc_status;
   ```

3. To get full problem details on a CDC-owned transaction, use an admin role or open a support ticket with the transaction ID.
