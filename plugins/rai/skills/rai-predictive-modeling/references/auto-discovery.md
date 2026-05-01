# Auto-Discovery

After the user provides table names, the agent automatically discovers schema details by querying Snowflake. This reference documents the conversation templates and discovery process.

## How to use this workflow

Walk through each phase **sequentially**. For each phase, use the **exact question template** below -- do not rephrase, reorder, or add extra questions. Wait for the user's answers before proceeding to the next phase. If the user provides information that covers multiple phases, acknowledge it and skip to the next uncovered phase.

## Conversation Templates

**Phase 1 is split into three sub-steps. Ask each one separately and wait for the user's response before moving to the next.**

### Phase 1a -- Source Tables

Ask exactly this:

```
Phase 1a: Source Tables

What are your **source table** fully qualified names?
(e.g., `MY_DB.MY_SCHEMA.CUSTOMERS`, `MY_DB.MY_SCHEMA.TRANSACTIONS`)

If you have a schema diagram or image, feel free to share it and I'll extract the details.
```

### Phase 1b -- Task Tables

Ask exactly this (after user responds to 1a):

```
Phase 1b: Task Tables

What are your **task table** fully qualified names for train/val/test?
(e.g., `MY_DB.TASKS.TRAIN`, `MY_DB.TASKS.VAL`, `MY_DB.TASKS.TEST`)
```

### Phase 1c -- Experiment Tracking

Ask exactly this (after user responds to 1b):

```
Phase 1c: Experiment Tracking

What Snowflake database and schema should we use for **experiment tracking**?
(e.g., `MY_DB.EXPERIMENTS`)
```

## What to Auto-Discover (and what NOT to ask)

The user-input boundary is the 3 prompts above (source FQNs, task FQNs, experiment db and schema). **Do not ask the user** for column names, PKs, FKs, label/target columns, timestamp columns, task type, or feature types — those are friction the user often can't answer without checking the schema themselves. Use the in-skill helper below first (`get_table_schema(table_name, database, schema)`), then infer:

1. **Column names and types** for all source and task tables
2. **Primary keys** -- identify PK columns
3. **Foreign key relationships** -- detect FK columns by matching column names across tables (e.g., `customer_id` in `TRANSACTIONS` matches `customer_id` PK in `CUSTOMERS`)
4. **Graph concepts** -- each source table becomes a concept (use singular form of table name)
5. **Edges** -- derived from FK relationships found above
6. **Task structure** -- from task table columns, infer:
   - Join key (column matching a source concept PK)
   - Label/target column (non-key, non-timestamp column) or target concept (for link prediction)
   - Time column (columns with DATE/TIMESTAMP type)
7. **Task type** -- infer from the label column:
   - Binary/boolean or 2-value categorical -> `binary_classification`
   - Multi-value categorical -> `multiclass_classification`
   - Multiple label columns for the same row, or array/list-of-labels target -> `multilabel_classification`
   - Numeric/float -> `regression`
   - Column matching another concept's PK -> `link_prediction` (ask user to confirm)

**Note: multiclass vs multilabel**
- **Multiclass**: each row has exactly one label chosen from many classes (e.g., `sports` *or* `news` *or* `finance`).
- **Multilabel**: each row can have multiple labels at the same time (e.g., `sports` *and* `news`).

### Required execution pattern (Snowpark first, then helper)

Set up a Snowpark session once (follow `rai-setup`), then reuse it for schema discovery.

Use this implementation directly:

```python
import re
from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")
session: snowpark.Session = create_config().get_session(SnowflakeConnection)


def get_table_schema(table_name: str, database: str, schema: str) -> list[dict]:
    """Return Snowflake table columns as [{'column_name': ..., 'data_type': ...}]."""
    table_name = table_name.strip()
    database = database.strip()
    schema = schema.strip()

    if not table_name or not database or not schema:
        return [{"error": "table_name, database, and schema are required and cannot be empty."}]

    for field_name, value in [("database", database), ("schema", schema), ("table_name", table_name)]:
        if not _IDENTIFIER_RE.fullmatch(value):
            return [{"error": f"Invalid {field_name}: '{value}'. Use only letters, numbers, and underscores."}]

    query = """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{schema}'
          AND TABLE_NAME = '{table}'
        ORDER BY ORDINAL_POSITION
    """.format(
        database=database.upper(),
        schema=schema.upper(),
        table=table_name.upper(),
    )

    try:
        rows = session.sql(query).collect()
    except Exception as exc:
        return [{"error": f"Snowflake query failed: {exc}"}]

    if not rows:
        return [{"error": f"No columns found for {database}.{schema}.{table_name}. Check the name and permissions."}]

    return [{"column_name": row["COLUMN_NAME"], "data_type": row["DATA_TYPE"]} for row in rows]
```

For each user-provided fully qualified table name `DB.SCHEMA.TABLE`:

1. Parse into `database=DB`, `schema=SCHEMA`, `table_name=TABLE`.
2. Call the in-skill helper `get_table_schema(table_name=TABLE, database=DB, schema=SCHEMA)`.
3. Treat the returned `column_name` values as canonical Snowflake column names (case-insensitive matching allowed for concept/property references, but spelling must match).
4. If the helper returns an `error`, retry once after uppercasing parts; if still failing, ask the user for `DESCRIBE TABLE` output for only the failing table.

Use `DESCRIBE TABLE` / manual SQL only as fallback when the Snowpark helper cannot return schema.

## Link Prediction Detection

If link prediction is detected, after presenting the discovery summary, ask the user:

```
I detected a **link prediction** task. One more question:

Are you predicting **new** links (connections that don't exist yet) or **repeated** interactions (e.g., a customer re-purchasing an item they've bought before)?

- **New links** -> `link_prediction`
- **Repeated interactions** -> `repeated_link_prediction`
```

## Summary Table Template

Present the discovery results to the user as a summary table for confirmation before proceeding:

```
Here's what I discovered from your tables:

**Source Tables & Concepts:**
| Table | Concept | PK | Other Columns |
|-------|---------|-----|---------------|
| ... | ... | ... | ... |

**Edges (FK relationships):**
| From | To | Join Condition |
|------|-----|---------------|
| ... | ... | ... |

**Task Tables:**
| Split | Table | Join Key -> Concept | Label/Target | Time Column |
|-------|-------|-------------------|--------------|-------------|
| Train | ... | ... | ... | ... |
| Val | ... | ... | ... | ... |
| Test | ... | ... | ... (none) | ... |

**Inferred task type:** `<task_type>`

Does this look correct? I'll proceed with this structure.
```

## Fallback

If the helper cannot connect to Snowflake or auto-discovery fails, fall back to asking the user for `DESCRIBE TABLE` output (or column lists with types) for only the affected tables.
