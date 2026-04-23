# Auto-Discovery

After the user provides table names, the agent automatically discovers schema details by querying Snowflake. This reference documents the conversation templates and discovery process.

## Conversation Templates

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

### Phase 1c -- Experiment Artifacts

Ask exactly this (after user responds to 1b):

```
Phase 1c: Experiment Artifacts

What Snowflake database and schema should we use for **experiment artifacts**?
(e.g., `MY_DB.EXPERIMENTS`)
```

## What to Auto-Discover

Once the user provides the table names, the agent must automatically discover the following by querying Snowflake (`DESCRIBE TABLE` or `INFORMATION_SCHEMA`). Use the snowflake-schema tool to get the schema of each table.

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
   - Numeric/float -> `regression`
   - Column matching another concept's PK -> `link_prediction` (ask user to confirm)

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

If the agent cannot connect to Snowflake or auto-discovery fails, fall back to asking the user for column details directly.
