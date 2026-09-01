#!/usr/bin/env python3
"""
Deterministic schema/structural validator for rai-predictive-task-generation SQL output.

No LLM, no database connection required. Checks a generated SQL artifact against:
  1. Forbidden statements (DROP/DELETE/UPDATE/TRUNCATE/ALTER)
  2. Schema-aware column/table resolution (via sqlglot, against a fed-in db schema) --
     only when --db-schema is given.
  3. Duplicate CTE names -- always. This is NOT redundant with a live EXPLAIN check:
     confirmed empirically that real Snowflake doesn't just accept a duplicated CTE name,
     it silently binds the first definition and ignores the second -- returning wrong
     results with no error at all (WITH c AS (SELECT 1 AS x), c AS (SELECT 2 AS x)
     SELECT * FROM c returns 1). This is the only check that catches that class of
     silent-corruption bug.
  4. Undefined table/CTE references -- external-table checking only when --db-schema is
     given; local CTE-reference checking always runs.
  5. Required output columns for the confirmed task type -- always.

--db-schema is optional. Omit it when a live Snowflake session is available and
`EXPLAIN <statement>` is being run against each statement instead (see
../references/utils_validation.md's "EXPLAIN road") -- in that mode this script only runs the two
checks no compiler can ever know about (forbidden statements, required output columns)
plus duplicate-CTE detection (which EXPLAIN was confirmed not to catch), rather than
re-approximating schema resolution locally when the real thing is one query away.

See ../references/utils_validation.md for how this fits into the overall validation pipeline
and for the --db-schema/--task-config JSON input file formats.

Usage:
    python3 validate_schema.py <sql_file> --db-schema <db_schema.json> --task-config <task_config.json>
    python3 validate_schema.py <sql_file> --task-config <task_config.json>   # EXPLAIN road: no --db-schema
"""
import argparse
import json
import sys

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify
from sqlglot.schema import MappingSchema

DIALECT = "snowflake"
FORBIDDEN_TYPES = (exp.Drop, exp.Delete, exp.Update, exp.TruncateTable, exp.Alter)


def quote_column_key(key: str) -> str:
    """Reuses utils_conventions.md's quoting rule: a column name that isn't all-uppercase
    was returned quoted by information_schema.columns, so it's case-sensitive and must
    be referenced quoted. Table/schema/db names in this skill's generated SQL are never
    quoted, so this normalization only applies to column keys."""
    return key if key.isupper() else f'"{key}"'


def build_schema(db_schema_path):
    mapping = {}
    known_tables = set()
    if db_schema_path is None:
        return MappingSchema(mapping, dialect=DIALECT), known_tables
    raw = json.loads(open(db_schema_path).read())
    for table_name, columns in raw.items():
        parts = table_name.split(".")
        if len(parts) != 3:
            raise ValueError(f"db-schema table key must be DATABASE.SCHEMA.TABLE, got: {table_name}")
        db, sch, tbl = parts
        mapping.setdefault(db.upper(), {}).setdefault(sch.upper(), {})[tbl.upper()] = {
            quote_column_key(col): dtype for col, dtype in columns.items()
        }
        known_tables.add(f"{db.upper()}.{sch.upper()}.{tbl.upper()}")
    return MappingSchema(mapping, dialect=DIALECT), known_tables


def table_key(table: exp.Table) -> str:
    """Normalized DB.SCHEMA.TABLE lookup key. Assumes table/schema/db parts are never
    quoted in this skill's conventions (only columns are)."""
    parts = [p.upper() for p in (table.catalog, table.db, table.name) if p]
    return ".".join(parts)


def check_forbidden_statements(statements, report):
    for stmt in statements:
        if isinstance(stmt, FORBIDDEN_TYPES):
            report.fail("forbidden_statement", f"Forbidden statement type {type(stmt).__name__}: {stmt.sql(dialect=DIALECT)[:120]}")


def cte_names(stmt) -> set:
    names = set()
    for with_ in stmt.find_all(exp.With):
        for cte in with_.expressions:
            names.add(cte.alias.upper())
    return names


def check_duplicate_ctes(stmt, report):
    for with_ in stmt.find_all(exp.With):
        seen = []
        for cte in with_.expressions:
            seen.append(cte.alias.upper())
        dupes = {n for n in seen if seen.count(n) > 1}
        if dupes:
            report.fail("duplicate_cte_name", f"Duplicate CTE name(s) {sorted(dupes)} in: {stmt.sql(dialect=DIALECT)[:120]}")


def check_undefined_references(stmt, known_tables, report, check_external=True):
    known_ctes = cte_names(stmt)
    # Bare (unqualified) references rely on Snowflake's session default db/schema, so
    # match them against just the table part of each known 3-part name.
    bare_known_tables = {key.split(".")[-1] for key in known_tables}
    for table in stmt.find_all(exp.Table):
        name = table.name.upper()
        if name in known_ctes:
            # Local CTE-reference checking always runs, regardless of check_external.
            continue
        if not check_external:
            # No fed-in schema (EXPLAIN road): no ground truth to check either bare or
            # qualified external table references against -- that's EXPLAIN's job instead.
            continue
        if table.db:
            key = table_key(table)
            if key not in known_tables:
                report.fail("undefined_reference", f"Table {key} is not a known source/created table (referenced as: {table.sql(dialect=DIALECT)})")
        elif name not in bare_known_tables:
            report.fail("undefined_reference", f"Reference to '{table.name}' matches no CTE defined in this statement and no known table")


def learn_ddl(stmt, schema, known_tables, report):
    """CREATE TABLE (col TYPE, ...) — register columns, preserving quoting."""
    if not (isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Schema)):
        return False
    table = stmt.this.this
    cols = {}
    for c in stmt.this.expressions:
        if isinstance(c, exp.ColumnDef):
            key = c.this.sql(dialect=DIALECT)
            kind = c.args.get("kind")
            cols[key] = kind.sql(dialect=DIALECT) if kind else "UNKNOWN"
    schema.add_table(table, column_mapping=cols, dialect=DIALECT)
    known_tables.add(table_key(table))
    return True


def learn_ctas(stmt, schema, known_tables, report):
    """CREATE TABLE ... AS SELECT — qualify the SELECT, register its output columns."""
    if not (isinstance(stmt, exp.Create) and isinstance(stmt.this, exp.Table) and stmt.expression is not None):
        return False
    table = stmt.this
    try:
        q = qualify(stmt.expression.copy(), schema=schema, dialect=DIALECT)
    except (OptimizeError, ParseError) as e:
        report.fail("schema_resolution", f"CREATE TABLE ... AS SELECT for {table.sql(dialect=DIALECT)} failed to qualify: {e}")
        return True
    cols = {s.alias_or_name: "UNKNOWN" for s in q.selects}
    schema.add_table(table, column_mapping=cols, dialect=DIALECT)
    known_tables.add(table_key(table))
    return True


def check_qualification(stmt, schema, report):
    try:
        qualify(stmt.copy(), schema=schema, dialect=DIALECT)
    except (OptimizeError, ParseError) as e:
        report.fail("schema_resolution", f"{type(stmt).__name__} failed to qualify: {e}")


def insert_output_columns(stmt):
    """Case-insensitive, quote-stripped output names for one INSERT's terminal SELECT.
    Quoting a contract column is a legitimate, common choice in real generated SQL (e.g.
    `value` is a reserved word in Snowflake and must be quoted just to use it as an alias
    at all), so this deliberately does not try to enforce quote-sensitivity -- only the
    name needs to match the contract, not its quoting."""
    return [sel.alias_or_name.upper() for sel in stmt.expression.selects]


REQUIRED_COLUMNS = {
    "binary_classification": ["label"],
    "multiclass_classification": ["label"],
    "regression": ["value"],
}

TASK_TYPES = {
    "binary_classification",
    "multiclass_classification",
    "multilabel_classification",
    "regression",
    "link_prediction",
    "repeated_link_prediction",
}

LINK_TASK_TYPES = {"link_prediction", "repeated_link_prediction"}


def validate_task_config(task_config, report):
    """Check task_config.json's shape before check_required_columns trusts any of its
    keys -- a missing/misnamed/typo'd field here must become a normal report.fail(...),
    not an unhandled KeyError, and a typo'd task_type must not silently pass validation
    with a wrong (near-empty) required-column set."""
    task_type = task_config.get("task_type")
    if task_type not in TASK_TYPES:
        report.fail("task_config", f"task_type must be one of {sorted(TASK_TYPES)}, got: {task_type!r}")
        return False

    if task_type in LINK_TASK_TYPES:
        missing = [k for k in ("src_id_column", "dst_id_column") if not task_config.get(k)]
        if missing:
            report.fail("task_config", f"task_type '{task_type}' requires {missing}")
            return False
    elif not task_config.get("entity_id_column"):
        report.fail("task_config", f"task_type '{task_type}' requires 'entity_id_column'")
        return False

    if task_config.get("temporal"):
        missing = [k for k in ("source_table", "source_time_column") if not task_config.get(k)]
        if missing:
            report.fail("task_config", f"temporal task_config requires {missing}")
            return False
        if "." in task_config["source_table"]:
            report.fail(
                "task_config",
                f"source_table must be the bare table name (e.g. 'orders'), not a "
                f"fully-qualified DB.SCHEMA.TABLE name like db_schema.json's keys use; "
                f"got: {task_config['source_table']!r}",
            )
            return False

    if task_type == "multilabel_classification" and task_config.get("label_form") not in ("array", "long"):
        report.fail("task_config", "multilabel_classification requires \"label_form\": \"array\" or \"long\" in task_config.json")
        return False

    return True


def check_required_columns(statements, task_config, report):
    inserts = [s for s in statements if isinstance(s, exp.Insert)]
    if not inserts:
        report.fail("required_columns", "No INSERT statement found to check output columns against")
        return

    if not validate_task_config(task_config, report):
        return

    task_type = task_config["task_type"]
    entity_cols = task_config.get("entity_id_column")
    if entity_cols is None:
        entity_cols = [task_config["src_id_column"], task_config["dst_id_column"]]
    elif isinstance(entity_cols, str):
        entity_cols = [entity_cols]

    required = [c.upper() for c in entity_cols]
    if task_config.get("split", True):
        required.append("SPLIT")

    if task_config.get("temporal"):
        table = task_config["source_table"]
        time_col = task_config["source_time_column"]
        required.append(f"cutoff_{table}_{time_col}".upper())
        required.append(f"{table}_{time_col}".upper())

    if task_type == "multilabel_classification":
        required.append("LABELS" if task_config["label_form"] == "array" else "LABEL")
    else:
        required.extend(c.upper() for c in REQUIRED_COLUMNS.get(task_type, []))

    required_set = set(required)

    for stmt in inserts:
        target = stmt.this.sql(dialect=DIALECT) if stmt.this is not None else "<unknown target>"
        actual_set = set(insert_output_columns(stmt))
        missing = required_set - actual_set
        extra = actual_set - required_set

        if missing:
            report.fail("required_columns", f"{target}: missing required output column(s): {sorted(missing)}")
        if extra:
            report.fail("required_columns", f"{target}: unexpected/extra output column(s): {sorted(extra)}")


class Report:
    def __init__(self):
        self.failures = []
        self.notes = []

    def fail(self, category, message):
        self.failures.append((category, message))

    def note(self, message):
        """A disclosure that must appear regardless of PASSED/FAILED -- e.g. which
        checks this run skipped -- so the printed report is self-describing rather
        than relying on the caller already knowing which flags were passed."""
        self.notes.append(message)

    def ok(self):
        return not self.failures

    def print_and_exit(self):
        for note in self.notes:
            print(f"NOTE: {note}")
        if not self.failures:
            print("PASSED: no schema/structural issues found.")
            return 0
        print(f"FAILED: {len(self.failures)} issue(s) found:\n")
        for category, message in self.failures:
            print(f"[{category}] {message}")
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sql_file")
    parser.add_argument("--db-schema", default=None, help="JSON: {'DB.SCHEMA.TABLE': {'col': 'TYPE', ...}}. Omit on the EXPLAIN road (see module docstring).")
    parser.add_argument("--task-config", required=True, help="JSON task config (see ../references/utils_validation.md)")
    args = parser.parse_args()

    has_external_schema = args.db_schema is not None
    report = Report()
    if not has_external_schema:
        report.note(
            "--db-schema not provided: schema-resolution and qualification checks "
            "were skipped for this run (expected on the EXPLAIN road -- see the "
            "module docstring). Only forbidden-statement, duplicate-CTE, and "
            "required-column checks ran."
        )
    schema, known_tables = build_schema(args.db_schema)
    task_config = json.loads(open(args.task_config).read())
    sql = open(args.sql_file).read()

    try:
        statements = sqlglot.parse(sql, dialect=DIALECT)
    except ParseError as e:
        print(f"FAILED: could not parse {args.sql_file}: {e}")
        return 1

    check_forbidden_statements(statements, report)

    for stmt in statements:
        if stmt is None:
            continue

        if isinstance(stmt, exp.Create):
            if learn_ddl(stmt, schema, known_tables, report):
                continue
            if isinstance(stmt.this, exp.Table) and stmt.expression is not None:
                # CREATE TABLE ... AS SELECT: check the inner SELECT for undefined
                # refs/duplicate CTEs (the DDL target itself isn't a "reference"). This
                # skill's CTAS statements only ever read from the already-locally-known
                # STAGING table, so qualifying them doesn't need the external schema.
                check_duplicate_ctes(stmt.expression, report)
                check_undefined_references(stmt.expression, known_tables, report, check_external=has_external_schema)
                learn_ctas(stmt, schema, known_tables, report)
            # else: CREATE SCHEMA or other DDL with nothing to learn/check.
            continue

        if isinstance(stmt, (exp.Insert, exp.Select)):
            check_duplicate_ctes(stmt, report)
            check_undefined_references(stmt, known_tables, report, check_external=has_external_schema)
            if has_external_schema:
                check_qualification(stmt, schema, report)

    check_required_columns(statements, task_config, report)

    return report.print_and_exit()


if __name__ == "__main__":
    sys.exit(main())
