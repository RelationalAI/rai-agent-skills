# Graph tier tracing by node type

**One query lives here — the only Step 2 discovery `rai explore schema` does not cover.** Everything else the old EDA pass did by hand (column inventory and types, row counts, PK uniqueness, FK cardinality and multiplicity, null rates, value distributions, subtype counts, numeric ranges, broken-edge counts) is in `schema.json`. See [schema-json.md](schema-json.md).

## What the command cannot tell you

`graph_topology.edge_type_pairs[].entity_type` is a **table name** — the target table shared by both FKs of a co-targeted pair. So the command answers *"which tables are joined by edge tables, and how many edges"*.

It cannot answer *"which kinds of node connect to which"* when node kind is a **TYPE column value** on a single node table. A `NODES` table holding `TYPE` values `PLANT`, `WAREHOUSE`, `STORE`, joined by one `EDGES` table, produces exactly one table-level pair (`NODES → NODES`) while hiding a three-tier supply chain. That tier structure is what reveals hidden layers, missing connections, and whether an intermediate concept is needed to bridge tiers.

## The query

Run this before Step 3 when the data describes a network **and** node kind lives in a column rather than in separate tables:

```sql
-- What node types connect to what? Reveals tiers and layers.
SELECT source.TYPE AS from_type, dest.TYPE AS to_type, COUNT(*) AS edges
FROM <edge_table> e
JOIN <node_table> source ON e.SOURCE_ID = source.ID
JOIN <node_table> dest ON e.DEST_ID = dest.ID
GROUP BY from_type, to_type ORDER BY edges DESC;
```

Substitute the real column names from `schema.json`: the edge table is the one `graph_topology` named, its two FK columns are its `fk_candidates` entries sharing a target, and the type column is the low-`distinct_count` column on the node table whose `value_distribution` lists the kinds.

Run it through the same connection the command used — `snow` CLI, or a Snowpark session:

```python
from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

session: snowpark.Session = create_config().get_session(SnowflakeConnection)
session.sql("<query above>").show()
```

## Reading the result

- **A tier chain** (`PLANT → WAREHOUSE`, `WAREHOUSE → STORE`, and no `PLANT → STORE`) means the network has ordered layers. Model the tiers as subtypes of the node concept, and check whether each hop needs its own relationship.
- **A missing pair** you expected is a data gap — raise it with the user rather than modelling the hop.
- **A pair with a small count** next to large ones is often a data-quality artifact, not a real tier.
- **`broken_edges` in `schema.json` is non-zero** — NULL FKs are excluded from these joins, so this query's totals will not sum to the edge table's `row_count`. Reconcile the two before concluding an edge type is absent.
