#!/usr/bin/env python3
"""Profile a DuckDB source schema for the rai-orm-conventions design rules.

Reads the source tables read-only and writes a JSON report of candidates for
review. It never modifies the database and never prints row values except the
distinct codes of low-cardinality indicator columns.

Usage:
    python profile_source.py --db data.duckdb --schema SOURCE_SCHEMA \
        [--join-hints hints.txt] --out source-profile.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import duckdb

INDICATOR_VALUES = {"Y", "N", "T", "F", "0", "1", "TRUE", "FALSE", "YES", "NO"}
AUDIT_NAME_RE = re.compile(
    r"(^|_)(load|etl|batch|insrt|snflk|dw|audit)(_|$)|(^|_)rec_(crt|updt)(_|$)|_dt_tm$",
    re.IGNORECASE,
)
PII_NAME_RE = re.compile(
    r"(^|_)(frst_nm|first_name|lst_nm|last_name|full_nm|mid_initial_txt|nm_prfx_txt|nm_sufx_txt|ssn|tax_id|birth_dt|dob"
    r"|email_address|eml_addr|street_nm|street_nbr|addr_line_\d|unit_nbr|ip_addr|imei)$",
    re.IGNORECASE,
)
JOIN_HINT_RE = re.compile(r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\b.*?\bjoin\w*\b.*?([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)", re.IGNORECASE)

# Below this share of all known key values, a table is a weak source for the entity (rule 3).
WEAK_COVERAGE = 0.5
# A shared key column must be unique in at least this many tables to suggest one entity (rule 1).
KEY_UNIQUE_RATIO = 0.99


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--join-hints", type=Path, help="Text file with lines like 'a.col can be joined with b.col'.")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    con = duckdb.connect(str(args.db), read_only=True)
    tables = _tables(con, args.schema)
    columns = {table: _profile_table(con, args.schema, table) for table in tables}
    hints = _join_hints(args.join_hints, tables) if args.join_hints else []
    keys = _key_groups(con, args.schema, columns, hints)

    report = {
        "schema": args.schema,
        "tables": {table: {"rows": _row_count(con, args.schema, table), "columns": len(cols)} for table, cols in columns.items()},
        "key_groups": [group for group in keys if group["unique_in"]],
        "rule1_merge_candidates": [{"key": g["key"], "tables": g["merge_candidates"]} for g in keys if g["merge_candidates"]],
        "rule2_indicator_columns": [
            {"table": table, "column": col["name"], "codes": col["codes"]}
            for table, cols in columns.items()
            for col in cols
            if col.get("codes") is not None
        ],
        "rule3_build_from_key_column": [
            {"key": g["key"], "weak_sources": g["weak_sources"], "build_from": g["build_from"], "coverage": g["coverage"]}
            for g in keys
            if g["weak_sources"]
        ],
        "rule4_subtype_candidates": [
            {"key": g["key"], "supertype_tables": sorted(set(g["unique_in"]) - set(g["subtype_candidates"])), "subtype_tables": g["subtype_candidates"]}
            for g in keys
            if g["subtype_candidates"]
        ],
        "rule4_join_hints": hints,
        "rule5_drop_candidates": _drop_candidates(columns, keys, hints),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(_summary(report), indent=2))
    return 0


def _tables(con: duckdb.DuckDBPyConnection, schema: str) -> list[str]:
    rows = con.execute(
        "select table_name from information_schema.tables where table_schema = ? and table_type = 'BASE TABLE' order by 1",
        [schema],
    ).fetchall()
    if not rows:
        raise SystemExit(f"no base tables found in schema {schema!r}")
    return [row[0] for row in rows]


def _row_count(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> int:
    return int(con.execute(f'select count(*) from "{schema}"."{table}"').fetchone()[0])


def _profile_table(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> list[dict]:
    cols = con.execute(
        "select column_name, data_type from information_schema.columns where table_schema = ? and table_name = ? order by ordinal_position",
        [schema, table],
    ).fetchall()
    rows = _row_count(con, schema, table)
    profiled = []
    for name, data_type in cols:
        nonnull, distinct = con.execute(
            f'select count("{name}"), count(distinct "{name}") from "{schema}"."{table}"'
        ).fetchone()
        entry = {
            "name": name,
            "type": data_type,
            "rows": rows,
            "nonnull": int(nonnull),
            "distinct": int(distinct),
            "codes": None,
        }
        if 0 < distinct <= 3:
            values = [
                str(value).strip().upper()
                for (value,) in con.execute(f'select distinct "{name}" from "{schema}"."{table}" where "{name}" is not null').fetchall()
            ]
            if values and set(values) <= INDICATOR_VALUES | {""}:
                entry["codes"] = sorted(values)
        profiled.append(entry)
    return profiled


def _join_hints(path: Path, tables: list[str]) -> list[dict]:
    hints = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = JOIN_HINT_RE.search(line)
        if not match:
            continue
        left_t, left_c, right_t, right_c = match.groups()
        left, right = _resolve_table(left_t, tables), _resolve_table(right_t, tables)
        hints.append(
            {
                "left": f"{left or left_t}.{left_c.upper()}",
                "right": f"{right or right_t}.{right_c.upper()}",
                "resolved": bool(left and right),
            }
        )
    return hints


def _resolve_table(name: str, tables: list[str]) -> str | None:
    """Match a hinted table name to a source table, allowing prefixed names (db_schema_table)."""
    upper = name.upper()
    matches = [table for table in tables if upper == table.upper() or upper.endswith("_" + table.upper())]
    return max(matches, key=len) if matches else None


def _key_groups(con, schema: str, columns: dict[str, list[dict]], hints: list[dict]) -> list[dict]:
    """Group columns that share a key name (or are hinted as joinable) and measure key coverage."""
    by_name: dict[str, list[str]] = defaultdict(list)
    for table, cols in columns.items():
        for col in cols:
            by_name[col["name"].upper()].append(table)
    for hint in hints:
        if not hint["resolved"]:
            continue
        for side in (hint["left"], hint["right"]):
            table, column = side.split(".", 1)
            if table not in by_name[column]:
                by_name[column].append(table)

    shared = {key for key, tables in by_name.items() if len(tables) > 1}
    primary_key = {
        table: next((c["name"].upper() for c in cols if c["name"].upper() in shared and _looks_like_key(c)), None)
        for table, cols in columns.items()
    }

    groups = []
    for key, tables in sorted(by_name.items()):
        if len(tables) < 2:
            continue
        stats = {table: next(c for c in columns[table] if c["name"].upper() == key) for table in tables if _has_column(columns[table], key)}
        if len(stats) < 2 or not any(primary_key.get(t) == key for t in stats):
            continue
        union = " union ".join(f'select "{stats[t]["name"]}" as k from "{schema}"."{t}" where "{stats[t]["name"]}" is not null' for t in stats)
        total = int(con.execute(f"select count(distinct k) from ({union})").fetchone()[0])
        if total == 0:
            continue
        coverage = {table: round(col["distinct"] / total, 4) for table, col in stats.items()}
        # A table identifies this entity only when this key is its primary key (first unique shared column).
        unique_in = [table for table in stats if primary_key.get(table) == key]
        strong_unique = [table for table in unique_in if coverage[table] >= WEAK_COVERAGE]
        weak_unique = [table for table in unique_in if coverage[table] < WEAK_COVERAGE]
        strong_any = [table for table in stats if coverage[table] >= WEAK_COVERAGE]
        groups.append(
            {
                "key": key,
                "tables": sorted(stats),
                "unique_in": sorted(unique_in),
                "distinct_key_values": total,
                "coverage": coverage,
                # Rule 1: two or more well-covered tables keyed by this column describe one entity.
                "merge_candidates": sorted(strong_unique) if len(strong_unique) > 1 else [],
                # Rule 4: a small table keyed by the same identifier as a well-covered entity table is a subtype candidate.
                "subtype_candidates": sorted(weak_unique) if strong_unique else [],
                # Rule 3: the only tables keyed by this column cover few values; build the entity from the key column elsewhere.
                "weak_sources": sorted(weak_unique) if weak_unique and not strong_unique else [],
                "build_from": sorted(table for table in strong_any if table not in unique_in) if weak_unique and not strong_unique else [],
            }
        )
    return groups


def _has_column(cols: list[dict], key: str) -> bool:
    return any(c["name"].upper() == key for c in cols)


def _looks_like_key(col: dict) -> bool:
    if col.get("codes") is not None:
        return False
    return col["nonnull"] > 0 and col["distinct"] >= KEY_UNIQUE_RATIO * col["nonnull"] and col["distinct"] > 1


def _drop_candidates(columns: dict[str, list[dict]], keys: list[dict], hints: list[dict]) -> list[dict]:
    protected = {key["key"] for key in keys}
    for hint in hints:
        protected.update(side.split(".", 1)[1] for side in (hint["left"], hint["right"]))
    candidates = []
    for table, cols in columns.items():
        for col in cols:
            name = col["name"]
            if name.upper() in protected:
                continue
            reasons = []
            if col["nonnull"] == 0:
                reasons.append("all_null")
            elif col["distinct"] == 1 and col["nonnull"] == col["rows"]:
                reasons.append("constant")
            if AUDIT_NAME_RE.search(name):
                reasons.append("audit_or_load_name")
            if PII_NAME_RE.search(name) and col.get("codes") is None:
                reasons.append("pii_name")
            if reasons:
                candidates.append({"table": table, "column": name, "reasons": reasons})
    return candidates


def _summary(report: dict) -> dict:
    reasons: dict[str, int] = defaultdict(int)
    for item in report["rule5_drop_candidates"]:
        for reason in item["reasons"]:
            reasons[reason] += 1
    return {
        "tables": len(report["tables"]),
        "columns": sum(t["columns"] for t in report["tables"].values()),
        "rule1_merge_candidates": [(g["key"], g["tables"]) for g in report["rule1_merge_candidates"]],
        "rule2_indicator_columns": len(report["rule2_indicator_columns"]),
        "rule3_build_from_key_column": [(g["key"], g["weak_sources"], g["build_from"]) for g in report["rule3_build_from_key_column"]],
        "rule4_subtype_candidates": [(g["key"], g["subtype_tables"]) for g in report["rule4_subtype_candidates"]],
        "rule4_join_hints": len(report["rule4_join_hints"]),
        "rule5_drop_candidates": dict(reasons),
    }


if __name__ == "__main__":
    raise SystemExit(main())
