# Auto-Discovery

After the user names the source data and the task tables, the agent discovers schema details by querying Snowflake and proposes which source tables to use. This reference documents the conversation templates and discovery process.

## How to use this workflow

Walk through each phase **sequentially**. For each phase, use the **exact question template** below -- do not rephrase, reorder, or add extra questions. Wait for the user's answers before proceeding to the next phase. If the user provides information that covers multiple phases, acknowledge it and skip to the next uncovered phase. Skipping a question never skips confirming the source graph: the summary table always shows the proposed source tables and waits for the user (§ Proposing the Source Graph). The tables that were used to build the task labels are not the source set. They usually hold only the predicted entity, and its signal often sits in the tables linked to it.

## Conversation Templates

**Phase 1 is split into three sub-steps. Ask each one separately and wait for the user's response before moving to the next.**

### Phase 1a -- Source Data

If an ontology already exists for the source data, skip this question: the ontology's scope defines the source data (see [existing-ontology.md](existing-ontology.md)). Otherwise, ask exactly this:

```
Phase 1a: Source Data

Which Snowflake database and schema hold your **source data**?
(e.g., `MY_DB.MY_SCHEMA`)
If you already know which tables to use, list them too. Either way, I'll propose
the tables linked to what you're predicting for you to confirm.

If you have a schema diagram or image, feel free to share it and I'll extract the details.
```

Tables the user lists are preselected in the proposed source graph. Linked tables are still proposed alongside them.

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

The user-input boundary is the 3 prompts above (source schema or tables, task FQNs, experiment db and schema), plus confirming the summary table. **Do not ask the user** for column names, PKs, FKs, label/target columns, timestamp columns, task type, or feature types — those are friction the user often can't answer without checking the schema themselves. Use the in-skill helper below first (`get_table_schema(table_name, database, schema)`), then infer:

1. **Column names and types** for all source and task tables
2. **Primary keys** -- identify PK columns. Do **not** rely on the `_id` suffix alone -- many real tables have non-`_id` PKs (e.g., `sku`, `email`, `isbn`) or multiple `_id` columns where only one is the PK and the rest are FKs. Detect in this order:

   **a. Declared constraint (authoritative).** Snowflake records primary keys in its constraint metadata when the table was defined with `PRIMARY KEY`. Query:

   ```sql
   SHOW PRIMARY KEYS IN TABLE <db>.<schema>.<table>
   ```

   If a result is returned, use those columns as the PK (composite PKs return multiple rows -- preserve `ORDINAL_POSITION` order).

   **b. Uniqueness probe (fallback when no declared PK).** Many Snowflake tables omit `PRIMARY KEY` declarations. For each candidate column, probe:

   ```sql
   SELECT
       COUNT(*)                AS n_rows,
       COUNT(<col>)            AS n_non_null,
       COUNT(DISTINCT <col>)   AS n_distinct
   FROM <db>.<schema>.<table>
   ```

   A column is a PK candidate when `n_non_null = n_rows` (no NULLs) **and** `n_distinct = n_rows` (fully unique). Probe candidates in this priority order:
   1. Columns whose name matches the singular table name + `_id` (`CUSTOMERS` -> `customer_id`, `c_customer_id`).
   2. Columns named `id` or ending in `_id`, `_key`, `_code`, `_no`, `_number`.
   3. Short string/number columns that look like natural keys (`sku`, `email`, `isbn`, `ean`, `upc`, `username`).
   4. Any other non-nullable column flagged by the schema.

   Stop at the first candidate that satisfies the uniqueness probe. If none do, try **composite** keys: probe pairs of columns with `COUNT(DISTINCT col_a, col_b) = COUNT(*)`.

   **c. Disambiguating multiple `_id` columns.** When a table has several `_id` columns (e.g., `TRANSACTIONS` with `t_id`, `t_customer_id`, `t_article_id`), only the one that passes the uniqueness probe **on this table** is the PK; the rest are FKs into other concepts (used in step 3). Confirm by checking which `<x>_id` value appears once per row vs. many times.

   If the probe still leaves ambiguity (e.g., no unique column, only composite candidates, or a synthetic surrogate is needed), surface the candidate columns + their `n_distinct / n_rows` ratios in the summary table and ask the user to confirm.

   **Key type.** Type each `identify_by` key from that column's `DATA_TYPE` (and `NUMERIC_SCALE` for `NUMBER`). Do not type a concept key as `Any` when the column type is known. `Any` is only for a relationship slot whose type is genuinely unknown, such as `{Any:ts}` or `{Any:label}` on a task relationship.

   | `DATA_TYPE` | `identify_by` type |
   |-------------|--------------------|
   | `NUMBER` with `NUMERIC_SCALE` 0, `INT`, `INTEGER`, `BIGINT` | `Integer` |
   | `FLOAT`, `DOUBLE`, `NUMBER` with scale > 0 | `Float` |
   | `VARCHAR`, `STRING`, `TEXT` | `String` |
   | `BOOLEAN` | `Boolean` |
   | `DATE` | `Date` |
   | `TIMESTAMP`, `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ`, `TIMESTAMP_TZ`, `DATETIME` | `DateTime` |

3. **Foreign key relationships** -- detect links by value coverage plus a name match, not by identical column names: real schemas often name the reference `<x>_id` or `<x>_uuid` while the key is plain `id` or `uuid`. The rule and the coverage query are in § Proposing the Source Graph.

   **Cycles, before any script (RelFM).** Walk those edges before writing the script. A cycle is any path that returns to a concept already on it: a self-referential foreign key, or a loop across several concepts. RelFM featurizes with depth-first search and has no base case for revisiting a table, so a cycle does not terminate. The constructor rejects a self-referential foreign key. It does **not** reject a cycle built from several joins — do not write that script. Name the edges that close the cycle and ask which one to drop. GNN may keep a cycle; message passing runs a fixed number of hops.
4. **Graph concepts** -- each table in the confirmed source graph becomes a concept (use singular form of table name)
5. **Edges** -- derived from FK relationships found above. A RelFM graph that contains a cycle is not ready to write.
6. **Task structure** -- from task table columns, infer:
   - Join key (column matching a source concept PK)
   - Label/target column (non-key, non-timestamp column) or target concept (for link prediction)
   - Time column (columns with DATE/TIMESTAMP type)
7. **Task type** -- infer from the label column. Data type alone is not enough (e.g., a `NUMBER` column can be a 0/1 binary label, a small-cardinality multiclass code, or a true regression target). Probe the **train** task table with SQL to disambiguate.

   **Step 7a — single-label probe.** Run for the candidate label column:

   ```sql
   SELECT
       COUNT(DISTINCT <label_col>) AS distinct_count,
       MIN(<label_col>)            AS min_val,
       MAX(<label_col>)            AS max_val,
       COUNT(*)                    AS n_rows
   FROM <db>.<schema>.<train_table>
   WHERE <label_col> IS NOT NULL
   ```

   Run via the same Snowpark session: `session.sql(query).collect()`.

   Decision rules (combine with the column's `DATA_TYPE` from `get_table_schema`):
   - `distinct_count == 2` (any type, e.g. `{0,1}`, `{TRUE,FALSE}`, `{"yes","no"}`) -> `binary_classification`
   - `distinct_count` more than 2 on a non-float type (`NUMBER` with scale 0, `VARCHAR`, `BOOLEAN`) -> `multiclass_classification`
   - Float type (`FLOAT`, `DOUBLE`, `NUMBER` with scale > 0) **and** `distinct_count` is high relative to `n_rows` -> `regression`
   - Label column matches another concept's PK -> `link_prediction` (ask user to confirm)

   **Step 7b — multilabel probe.** Multilabel shows up in three shapes. Check them in this order -- cheapest schema-only signal first, then the schema-shape signal, then the data-pattern signal that the first two cannot see:

   *Shape A — single `ARRAY` / `VARIANT` column holding a list of labels per row.* Most explicit encoding, and detectable from `DATA_TYPE` alone. If the candidate label column's `DATA_TYPE` is `ARRAY` or `VARIANT`, confirm row-level structure:

   ```sql
   SELECT
       TYPEOF(<label_col>)                           AS json_type,
       AVG(ARRAY_SIZE(<label_col>))                  AS avg_labels_per_row,
       COUNT(DISTINCT f.value::STRING)               AS distinct_labels
   FROM <db>.<schema>.<train_table>,
        LATERAL FLATTEN(input => <label_col>) f
   WHERE <label_col> IS NOT NULL
   GROUP BY 1
   ```

   If `json_type = 'ARRAY'` and `avg_labels_per_row > 1` for at least some rows -> `multilabel_classification`. If `avg_labels_per_row` is always exactly 1, treat the unwrapped value as a single label and re-run step 7a.

   *Shape B — multiple binary indicator columns* (e.g., `is_sports`, `is_news`, `is_finance`). Schema-level signal: after excluding the join key and time column, if 2+ remaining non-key columns look binary, it is likely multilabel. Probe each candidate:

   ```sql
   SELECT
       '<col>' AS column_name,
       COUNT(DISTINCT <col>) AS distinct_count,
       MIN(<col>) AS min_val,
       MAX(<col>) AS max_val
   FROM <db>.<schema>.<train_table>
   WHERE <col> IS NOT NULL
   ```

   If 2+ columns each have `distinct_count == 2` with values in `{0,1}` / `{TRUE,FALSE}` -> `multilabel_classification`.

   *Shape C — duplicated rows with different single labels.* The sneaky case: the table looks single-label at first glance (one label column, one value per row), but the same entity appears on multiple rows with **different** label values. This is multilabel encoded long-form, not single-label. Always run this probe last, before settling on binary/multiclass/regression -- shapes A and B cannot see it because the schema looks identical to a normal single-label table.

   Pick the right uniqueness key based on whether the task has a time column (step 8):

   - **Non-temporal task** (`has_time_column = False`): a single-label task should have at most one label per `<join_key>`. Probe:

     ```sql
     SELECT
         COUNT(*)                                            AS n_rows,
         COUNT(DISTINCT <join_key>)                          AS n_entities,
         SUM(CASE WHEN n_labels > 1 THEN 1 ELSE 0 END)       AS n_multilabeled_entities,
         MAX(n_labels)                                       AS max_labels_per_entity
     FROM (
         SELECT <join_key>, COUNT(DISTINCT <label_col>) AS n_labels
         FROM <db>.<schema>.<train_table>
         WHERE <label_col> IS NOT NULL
         GROUP BY <join_key>
     )
     ```

   - **Temporal task** (`has_time_column = True`): a single-label task should have at most one label per `(<join_key>, <time_col>)` -- the same entity *can* legitimately appear across multiple timestamps with different labels (that is just the temporal task, not multilabel). Probe on the composite key instead:

     ```sql
     SELECT
         COUNT(*)                                            AS n_rows,
         COUNT(DISTINCT <join_key>, <time_col>)              AS n_entity_time_pairs,
         SUM(CASE WHEN n_labels > 1 THEN 1 ELSE 0 END)       AS n_multilabeled_pairs,
         MAX(n_labels)                                       AS max_labels_per_pair
     FROM (
         SELECT <join_key>, <time_col>, COUNT(DISTINCT <label_col>) AS n_labels
         FROM <db>.<schema>.<train_table>
         WHERE <label_col> IS NOT NULL
         GROUP BY <join_key>, <time_col>
     )
     ```

   Decision rule:
   - `n_multilabeled_entities > 0` (or `n_multilabeled_pairs > 0` in the temporal case) -> `multilabel_classification`.
   - Otherwise the long-form duplication is benign (same row repeated, or temporal entries with one label each), and step 7a's result stands.

   If the result is ambiguous (e.g., integer column with ~10 distinct values could be either multiclass or a discretized regression target, or a small number of multilabeled entities that could be data-quality issues rather than true multilabel), surface the counts in the summary table and let the user confirm.

   **Step 7c — link prediction confirmation.** If the candidate task type is `link_prediction` (label column matches another concept's PK), confirm new-vs-repeated with the user before settling on `link_prediction` vs `repeated_link_prediction`. Use this prompt verbatim after the discovery summary:

   ```
   I detected a **link prediction** task. One more question:

   Are you predicting **new** links (connections that don't exist yet) or **repeated** interactions (e.g., a customer re-purchasing an item they've bought before)?

   - **New links** -> `link_prediction`
   - **Repeated interactions** -> `repeated_link_prediction`
   ```

8. **Has time column** -- detect a time column on the task table. A `DATE` or `TIMESTAMP*` column on train, val, or test makes the task **temporal**. Set `has_time_column=True` and treat it as temporal: task relationships use the `at {Type:<slot>}` clause (see `task-relationships.md`), `PropertyTransformer` sets `time_col=` (and lists that property in `datetime=`), and `GNN(...)` / `RelFM(...)` is constructed with `has_time_column=True`. This is **independent of task type** -- any task type can be temporal. A `DATE` column counts; it does not need a time of day. Do not set `has_time_column=False` because the rows are already split by time, or because that column was dropped from features. Set `False` and omit `at {…}` only when no column matches **a**, **b**, or **c** below.

   Detect in this order:

   **a. Native time types from `DATA_TYPE` (authoritative).** From `get_table_schema`, flag any column whose `DATA_TYPE` is one of:

   ```
   DATE, TIME,
   TIMESTAMP, DATETIME,
   TIMESTAMP_NTZ, TIMESTAMP_LTZ, TIMESTAMP_TZ
   ```

   Do **not** rely on column-name heuristics first -- a column named `timestamp` may be stored as `NUMBER` (epoch seconds/ms), and a column named `t_dat` or `ship_date` may be a true `DATE`. Type wins over name. Read `DATA_TYPE` from `INFORMATION_SCHEMA`; do not guess `TEXT` from the column name. A match here is decisive: the task is temporal.

   **b. Epoch-encoded times stored as integers (probe).** When the schema has an integer column whose name suggests time (`timestamp`, `ts`, `time`, `date`, `dt`, `epoch`, `event_time`, `created_at`, `updated_at`, etc.), confirm with a value-range probe:

   ```sql
   SELECT
       MIN(<col>) AS min_val,
       MAX(<col>) AS max_val,
       COUNT(*)   AS n_rows
   FROM <db>.<schema>.<task_table>
   WHERE <col> IS NOT NULL
   ```

   Plausible epoch ranges (rough heuristics around the year 2000 -- 2100):
   - Seconds: ~`9e8` -- `4e9`
   - Milliseconds: ~`9e11` -- `4e12`
   - Microseconds: ~`9e14` -- `4e15`

   If the values fall in a plausible range, treat the column as a time column. The PyRel-side definition still uses `Any` (e.g., `{Any:ts}`); the GNN reasoner handles the integer epoch as the time slot.

   **c. ISO-string dates stored as VARCHAR (probe).** When a `VARCHAR`/`STRING` column has a time-suggestive name, validate with `TRY_TO_TIMESTAMP` / `TRY_TO_DATE`:

   ```sql
   SELECT
       COUNT(*)                          AS n_rows,
       COUNT(<col>)                      AS n_non_null,
       COUNT(TRY_TO_TIMESTAMP(<col>))    AS n_parses_ts,
       COUNT(TRY_TO_DATE(<col>))         AS n_parses_date
   FROM <db>.<schema>.<task_table>
   WHERE <col> IS NOT NULL
   ```

   If `n_parses_ts = n_non_null` (or `n_parses_date = n_non_null`), the column is an ISO date/timestamp. Prefer rewriting the task table to a real `TIMESTAMP` column, but otherwise accept it.

   **d. Disambiguating multiple time columns.** If the task table has more than one time-typed column (e.g., a row `created_at` plus an `event_time`), pick the one that represents the **as-of** time for the prediction (the `WHERE` clause in `WHERE event_time <= ...`), not row-creation metadata. When unclear, surface both in the summary table and let the user confirm.

   If no column matches **a**, **b**, or **c**, set `has_time_column=False` and **omit** the `at {Type:<slot>}` clause from the task relationships.

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
        SELECT COLUMN_NAME, DATA_TYPE, NUMERIC_SCALE
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

    return [
        {
            "column_name": row["COLUMN_NAME"],
            "data_type": row["DATA_TYPE"],
            "numeric_scale": row["NUMERIC_SCALE"],
        }
        for row in rows
    ]
```

For each task table and each source table (listed by the user or proposed in the source graph), as a fully qualified name `DB.SCHEMA.TABLE`:

1. Parse into `database=DB`, `schema=SCHEMA`, `table_name=TABLE`.
2. Call the in-skill helper `get_table_schema(table_name=TABLE, database=DB, schema=SCHEMA)`.
3. Treat the returned `column_name` values as canonical Snowflake column names (case-insensitive matching allowed for concept/property references, but spelling must match).
4. If the helper returns an `error`, retry once after uppercasing parts; if still failing, ask the user for `DESCRIBE TABLE` output for only the failing table.

Use `DESCRIBE TABLE` / manual SQL only as fallback when the Snowpark helper cannot return schema.


## Proposing the Source Graph

Propose the source tables from the links around the predicted entity, and let the user confirm them in the summary table. A graph limited to the tables named up front, or to the tables that built the labels, often holds only the entity itself, and the model then has little to learn from. The same procedure applies with an ontology: walk its concepts and links instead of the raw tables (see [existing-ontology.md](existing-ontology.md)).

1. **Find the node.** Check which table's unique key holds the task join key's values, separately for each split.
   - **One table:** start there.
   - **The key is unique in no table** (it is only a column carried by several tables): the entity has no table of its own. Start from every table that carries the key, and plan a node concept whose identity is that key, populated from all of them.
   - **The keys spread over twin tables** (same columns, such as current and archived copies): treat the twins as one node, populated from all of them, and show them as one row.

2. **Find links.** A column `a` in table `C` links to the unique key `b` of table `P` when both hold:
   - **Name:** `a` refers to `P` or to `b` (`<p>_id`, `<p>_uuid`, `parent_<p>_id`, or the same name). Integer surrogate keys overlap by accident, so value coverage alone is not enough for them.
   - **Coverage:** almost all distinct non-null values of `a` appear in `b`.

   ```sql
   SELECT COUNT(DISTINCT c.<a>)                                          AS n_values,
          COUNT(DISTINCT CASE WHEN p.<b> IS NOT NULL THEN c.<a> END)    AS n_matched
   FROM <db>.<schema>.<C> c
   LEFT JOIN (SELECT DISTINCT <b> FROM <db>.<schema>.<P>) p ON c.<a> = p.<b>
   WHERE c.<a> IS NOT NULL
   ```

   A column that is entirely NULL has no coverage to measure. When its twin table holds values, test the link on the twin.

3. **Walk two hops.** Hop 1 is every table linked directly to the node, in either direction. Hop 2 is every table linked to a hop-1 table. Preselect hop 1 (and any tables the user listed), propose hop 2 for the user to add, and stop there.

4. **Attach a leakage note to each row.** Judge each table by when its values were recorded relative to the prediction time:

   | Table kind | Note |
   |---|---|
   | Event log with a timestamp per row (transactions, actions) | Usable when cut off at the prediction time with `time_col`. Rows after it can contain the outcome itself. |
   | The entity table itself | Mixed. Name the columns recorded after the outcome (final state, end or deletion times, lifecycle flags) as leaky. |
   | Current-state snapshot with no event time (balances, usage counters) | High. Values are rewritten after the prediction time and can encode the label directly. |
   | Reference data (types, catalogs) | Low, apart from deletion or validity flags. |

## Summary Table Template

Present the discovery results to the user as a summary table for confirmation before proceeding. Always name the connected database, the estimator, and the task type in this summary without being asked. The estimator is the one this session is building (`RelFM` or `GNN`). The connected database is the Snowflake database the session is using; if the source tables live in a different database, name that too. Do not write a RelFM script whose edges contain a cycle: name the edges that close it and ask which one to drop.

```
Here's what I discovered from your tables:

**Connected database:** `<database>`
**Estimator:** `<RelFM|GNN>`

**Proposed source graph** (hop 1 selected; say which hop-2 tables to add or which to drop):
| Hop | Table (+ twins) | Concept | PK | PK type | Rows | Link to graph | Leakage note | Selected |
|-----|-----------------|---------|-----|---------|------|---------------|--------------|----------|
| 0 | ... (node) | ... | ... | Integer | ... | - | ... | yes |
| 1 | ... | ... | ... | ... | ... | `<C>.<a> -> <P>.<b>` | ... | yes |
| 2 | ... | ... | ... | ... | ... | ... | ... | proposed |

<With an ontology: "Scope: the <module> ontology. Tables it does not map were not considered.">

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
**Has time column:** `<true|false>`

Does this look correct? I'll proceed with this structure.
```

## Fallback

If the helper cannot connect to Snowflake or auto-discovery fails, fall back to asking the user for `DESCRIBE TABLE` output (or column lists with types) for only the affected tables.
