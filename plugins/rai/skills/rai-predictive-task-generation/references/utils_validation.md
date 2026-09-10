# SQL Validation

Read this file immediately before showing generated SQL to the user. The final SQL artifact must pass validation before it is shown — do not treat "the query looks right" as sufficient.

**Resolve the environment first, before either road.** `../scripts/validate_schema.py` (used by both roads below) needs `sqlglot`. Read `utils_python_environment.md` and follow it now, resolving/installing `sqlglot` eagerly — unlike `sqlfluff` (below), this one is needed regardless of which road runs, so don't wait to find out which road applies before resolving it.

**First, pick a road for steps 1–2**: is automatic execution (Step 0 of the active sub-skill — `GUIDED.md` or `ONE_SHOT.md`) enabled *and* is a live Snowflake session actually established (not just opted into)? If yes, use the **EXPLAIN road** below instead of the local-tool steps — a real compile against the real schema is strictly more authoritative than any local approximation. If no live session, use the standard **local-tool road** (steps 1–2 as written).

### Local-tool road (no live Snowflake session)

1. **Syntax layer (always run)** — `sqlfluff` is only needed on this road (the EXPLAIN road doesn't use it at all), so resolve it lazily, right here: read `utils_python_environment.md` and follow it, resolving/installing `sqlfluff` into the same venv `sqlglot` was resolved into above. Then run `<venv>/bin/sqlfluff parse --dialect snowflake <file>` against the generated artifact — never a bare `sqlfluff` that might resolve elsewhere on `PATH`. A `PRS` violation means a hard syntax error (unbalanced parens, missing comma, unterminated string, etc.) — fix it and re-run until the parse is clean. Use `parse`, not full `lint`: `lint`'s default rules also flag cosmetic style (capitalization, spacing, line length) that is not part of this contract and is already governed by `utils_conventions.md`.
   - **Known gap**: sqlfluff's (and sqlglot's) `snowflake` dialect models CTEs as a generic prefix that can attach to any DML statement, so it will pass `WITH ... INSERT INTO ... SELECT` even though real Snowflake rejects it (`unexpected 'INSERT'`) — Snowflake only allows `WITH` inside the query that follows `INSERT INTO <table>`, i.e. `INSERT INTO <table> WITH cte AS (...) SELECT ... FROM cte`. Always write it in that order; a clean sqlfluff parse does not confirm this specific ordering is correct.
2. **Schema layer (always run)** — run `../scripts/validate_schema.py` via Bash. It is deterministic (no LLM, no DB connection): checks the artifact against the real database schema plus structural rules the syntax layer can't see (undefined CTE/table references, duplicate CTE names, ambiguous unqualified columns, required output columns, forbidden statements). Build two small JSON files first:
   - `db_schema.json` — one entry per fully-qualified source table confirmed in Turn 1A, straight from Query 1's results: `{"DB.SCHEMA.TABLE": {"column_name": "DATA_TYPE", ...}}`. Use the exact casing Query 1 returned — the script reuses the identifier-quoting rule from `utils_conventions.md` (a column name that isn't all-uppercase is treated as quoted/case-sensitive) automatically.
   - `task_config.json` — the confirmed Step 3 configuration: `task_type` (one of the six canonical task types), `entity_id_column` (or `src_id_column`/`dst_id_column` for link tasks), `temporal`, and (if temporal) `source_table`/`source_time_column`. `source_table` must be the **bare table name** (e.g. `orders`), not the fully-qualified `DB.SCHEMA.TABLE` form used in `db_schema.json`'s keys — it feeds directly into the `cutoff_<table>_<source_time_col>` column name from the parent `SKILL.md`'s naming contract, which is also bare-table-prefixed. For `multilabel_classification`, also include `label_form`: `"array"` or `"long"` (see `task_multilabel.md`) — the script uses it to require `labels` vs `label` as the output column and fails loudly if it's missing. `split` (optional, default `true`) — set to `false` when GUIDED.md Step 3's "No split" scenario was chosen, so the validator doesn't require a `SPLIT` output column for a config that documents not having one.

   Then run (through the venv resolved above, not a bare `python3`):
   ```
   <venv>/bin/python ../scripts/validate_schema.py <file> --db-schema db_schema.json --task-config task_config.json
   ```
   Fix any reported issue and re-run until it reports `PASSED`.

### EXPLAIN road (live Snowflake session available)

Empirically verified against a real Snowflake session (scratch database, dropped after
testing) — not just inferred from docs:

- `EXPLAIN` compiles a statement but never executes it (Snowflake's own docs: "EXPLAIN
  compiles the SQL statement, but does not execute it"), and this held for every
  statement shape this skill generates: plain `SELECT`, `INSERT ... WITH ... SELECT`,
  `CREATE TABLE ... AS SELECT`, a bare `CREATE TABLE (col TYPE, ...)`, and `CREATE
  SCHEMA` — all explain successfully. So it's safe to run on write-tier statements
  without the write confirmation `utils_auto_execution.md` otherwise requires — confirmation is
  still required later, before actually *running* any write statement for real.
- `EXPLAIN` reliably surfaces binding errors: confirmed it fails with a real `SQL
  compilation error` on an unknown column, an unknown table, and an ambiguous column
  reference.
- `EXPLAIN` does **not** reject duplicate CTE names — and this is worse than a lenient
  parse. Confirmed live: `WITH c AS (SELECT 1 AS x), c AS (SELECT 2 AS x) SELECT * FROM
  c` returns `1`, not an error — Snowflake silently binds the first definition and
  ignores the second. A duplicated CTE name in generated SQL would silently compute a
  label from the wrong CTE with no error anywhere in the pipeline. `../scripts/validate_schema.py`'s
  duplicate-CTE check is the only thing that catches this class of silent-corruption bug
  on this road; it is not optional.
- `EXPLAIN` only accepts one statement per call (confirmed: two semicolon-separated
  statements in one call fails with `"Actual statement count 2 did not match the desired
  statement count 1"`).

Given that:

1. Split the generated artifact into its individual top-level statements (same statement
   boundaries `../scripts/validate_schema.py` already uses via `sqlglot.parse`).
2. For each statement, run `EXPLAIN <statement>` via `run_sql` (per
   `utils_auto_execution.md`). Any error is a real validation failure — fix the SQL
   and re-run `EXPLAIN` on the corrected statement before moving to the next one.

   **Known, permanent exception — statements that reference an object created earlier in
   the same script** (`STAGING`, and the `TRAIN`/`VAL`/`TEST` selects that read from it):
   `EXPLAIN` never executes the earlier `CREATE`/`INSERT` statements, so by the time you
   reach these statements the object they reference does not actually exist yet.
   `EXPLAIN` will always fail on them with an "object does not exist" error — on every
   run, for every task table this skill ever generates. This is not a real validation
   failure and is not evidence of anything wrong with the generated SQL:
   - For the `INSERT INTO <target> WITH ... SELECT ...` statement, strip the `INSERT
     INTO <target>` prefix and run `EXPLAIN` on the bare `WITH ... SELECT` alone — it
     only reads from real, already-existing source tables, so this validates the actual
     label-computation logic (the highest-risk part) without hitting the missing-object
     issue at all.
   - For the DDL (`CREATE TABLE STAGING (...)`) and the split-table selects (`CREATE
     TABLE TRAIN AS SELECT * EXCLUDE (...) FROM STAGING ...`), do not attempt to work
     around the missing object (e.g. by substituting a different existing table) and do
     not report the gap. These statements are mechanically simple — a column list and a
     `SELECT * EXCLUDE (...) FROM <table> WHERE split = '...'` — and are already fully
     covered by `../scripts/validate_schema.py`'s structural checks (required output
     columns, column existence against the declared `STAGING` schema, forbidden
     statements). Treat that coverage as sufficient; this combination (bare-SELECT
     `EXPLAIN` + structural validator) **is** complete validation for this road, not a
     partial one.
3. **Always also run**, regardless of the above (through the same resolved venv):
   ```
   <venv>/bin/python ../scripts/validate_schema.py <file> --task-config task_config.json
   ```
   (no `--db-schema` — see the script's module docstring). This is what catches
   duplicate CTE names, plus the two checks no compiler can ever know about: forbidden
   statements and required output columns. `db_schema.json` still gets built either way
   (see below) — it's just not passed to this script on this road, since `EXPLAIN`
   already checked everything it would have been used for.

### Both roads

Regardless of which road ran steps 1–2, always build `db_schema.json` (Turn 1A's
confirmed schema, formatted per the local-tool road's description above).

Once the applicable layers pass, proceed to the summary in `utils_output_format.md`.

This is the full validation pipeline (syntax parser → schema validator → optional live Snowflake `EXPLAIN` when DB access is available). Both conceptual layers are automated now — which of the first two roads runs depends on whether a live Snowflake session is available this session.

