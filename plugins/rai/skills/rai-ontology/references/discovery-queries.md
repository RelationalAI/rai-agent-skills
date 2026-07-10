# Discovery and EDA Queries

SQL for Step 2 of the Greenfield Build Workflow — run these via the `snow` CLI or a Snowpark session before identifying concepts. The multiplicity results feed Step 4's Property-vs-Relationship decisions; the subtype discovery feeds Step 3.

## Snowpark session for discovery

```python
from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

session: snowpark.Session = create_config().get_session(SnowflakeConnection)
session.sql("""
    SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE,
           NUMERIC_PRECISION, NUMERIC_SCALE
    FROM <database>.INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = '<schema>'
    ORDER BY TABLE_NAME, ORDINAL_POSITION
""").show()
```

Keep this result available through Step 6 — `DATA_TYPE` and `NUMERIC_SCALE` are the authoritative source for every RAI property type.

## Basic EDA

```sql
-- Row count and PK uniqueness
SELECT COUNT(*), COUNT(DISTINCT <pk_col>) FROM <database>.<schema>.<table>;

-- FK cardinality
SELECT COUNT(DISTINCT <fk_col>), COUNT(*) FROM <database>.<schema>.<table>;

-- Null rate
SELECT COUNT(*) AS total, COUNT(<col>) AS non_null,
    ROUND(1 - COUNT(<col>) / COUNT(*), 2) AS null_rate
FROM <database>.<schema>.<table>;

-- Value distribution for enum/category columns
SELECT <col>, COUNT(*) AS cnt FROM <database>.<schema>.<table>
GROUP BY <col> ORDER BY cnt DESC LIMIT 20;

-- Subtype discovery: TYPE/CATEGORY/CLASS columns with few values that
-- partition entities into fundamentally different kinds
-- e.g., BUSINESS_TYPE with values 'Supplier','Customer' → subtypes of Business
SELECT <type_col>, COUNT(*) AS cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
FROM <database>.<schema>.<table>
GROUP BY <type_col> ORDER BY cnt DESC;

-- Relationship multiplicity: determine 1:1, 1:N, or M:N
-- Run for each FK — Step 4's Property-vs-Relationship choice depends on this
SELECT
    ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT <fk_col>), 0), 2) AS avg_rows_per_fk,
    MAX(cnt) AS max_rows_per_fk
FROM (
    SELECT <fk_col>, COUNT(*) AS cnt
    FROM <database>.<schema>.<table>
    GROUP BY <fk_col>
);
```

## Graph / network topology tracing

When the data describes a network (nodes connected by edges via FK chains), trace the full path before identifying concepts — this reveals hidden layers, missing connections, and whether intermediate concepts are needed to bridge tiers:

```sql
-- What node types connect to what? Reveals tiers and layers.
SELECT source.TYPE AS from_type, dest.TYPE AS to_type, COUNT(*) AS edges
FROM <edge_table> e
JOIN <node_table> source ON e.SOURCE_ID = source.ID
JOIN <node_table> dest ON e.DEST_ID = dest.ID
GROUP BY from_type, to_type ORDER BY edges DESC;

-- Check for NULL FKs that create invisible network gaps
SELECT COUNT(*) AS broken_edges FROM <edge_table>
WHERE DEST_ID IS NULL OR SOURCE_ID IS NULL;
```

## Type validation pull (Step 5)

Re-use the Step 2 `INFORMATION_SCHEMA.COLUMNS` pull above (optionally filtered with `AND TABLE_NAME IN (...)`); `DATA_TYPE` and `NUMERIC_SCALE` are the columns that drive the type mapping.

Always run this before writing property declarations — a single type mismatch raises `TyperError` at query time and blocks ALL queries on the model without naming the offending property.
