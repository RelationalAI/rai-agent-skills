"""Extract deterministic, literal-free structural evidence from SQL workloads."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope


def statements(text: str) -> list[str]:
    """Split SQL without treating quoted or commented semicolons as separators."""
    pattern = r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]|--[^\n]*|/\*[\s\S]*?\*/|;"
    start, parts = 0, []
    for token in re.finditer(pattern, text):
        if token.group() == ";":
            parts.append(text[start:token.start()])
            start = token.end()
    parts.append(text[start:])
    return [p.strip() for p in parts if re.sub(r"--[^\n]*|/\*[\s\S]*?\*/", "", p).strip()]


def read_items(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        rows = json.loads(text)
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("JSON must be a list of objects")
    elif path.suffix.lower() == ".sql":
        rows = [{"sql": sql} for sql in statements(text)]
    elif path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        rows = [{"question": q.strip()} for q in text.splitlines() if q.strip()]
    return [{"id": str(r.get("id", f"i{i:04d}")),
             "sql": next((r[k] for k in ("sql", "output", "query_text", "query") if r.get(k)), None),
             "question": r.get("question") or r.get("input")} for i, r in enumerate(rows, 1)]


def edge_key(pairs: list[tuple[tuple[str, str], tuple[str, str]]]) -> tuple:
    oriented = [(min(a, b), max(a, b)) for a, b in pairs]
    oriented = sorted(set(oriented))
    return (oriented[0][0][0], tuple(a[1] for a, _ in oriented),
            oriented[0][1][0], tuple(b[1] for _, b in oriented))


def local_nodes(node: exp.Expression) -> Iterator[exp.Expression]:
    return node.walk(prune=lambda n: n is not node and isinstance(n, exp.Query))


class Schema:
    def __init__(self, path: Path | None, dialect: str) -> None:
        self.given = path is not None
        self.tables: dict[str, str] = {}
        self.columns: dict[str, dict[str, str]] = {}
        self.fks: set[tuple] = set()
        trees = sqlglot.parse(path.read_text(encoding="utf-8"), read=dialect) if path else []
        for tree in trees:
            if isinstance(tree, exp.Create) and isinstance(tree.this, exp.Schema):
                table = tree.this.this.name
                self.tables[table.upper()] = table
                self.columns[table] = {c.name.upper(): c.name for c in tree.this.find_all(exp.ColumnDef)}
        for tree in trees:
            if not isinstance(tree, exp.Create) or not isinstance(tree.this, exp.Schema):
                continue
            table = tree.this.this.name
            for fk in tree.find_all(exp.ForeignKey, exp.Reference):
                if isinstance(fk, exp.Reference) and not isinstance(fk.parent, exp.ColumnConstraint):
                    continue
                ref = fk.args.get("reference") if isinstance(fk, exp.ForeignKey) else fk
                if ref is None or not isinstance(ref.this, exp.Schema):
                    continue
                source = fk.expressions if isinstance(fk, exp.ForeignKey) else [fk.parent.parent.this]
                target = self.table(ref.this.this.name)
                pairs = [((table, self.column(table, a.name)), (target, self.column(target, b.name)))
                         for a, b in zip(source, ref.this.expressions)]
                if pairs:
                    self.fks.add(edge_key(pairs))

    def table(self, name: str) -> str:
        return self.tables.get(name.upper(), name.upper())

    def column(self, table: str, name: str) -> str:
        return self.columns.get(table, {}).get(name.upper(), name.upper())


class Digest:
    def __init__(self, schema: Schema, dialect: str) -> None:
        self.schema, self.dialect = schema, dialect
        self.records: dict[str, dict[Any, dict]] = {k: {} for k in
            ("tables", "columns", "join_edges", "grain_keys", "filter_columns", "expressions", "unresolved")}

    def add(self, section: str, key: Any, data: dict, item: int,
            counter: str | None = None, value: str | None = None) -> dict:
        record = self.records[section].setdefault(key, {**data, "_items": set(), "_counts": {}})
        record["_items"].add(item)
        if counter:
            record["_counts"].setdefault(counter, {}).setdefault(value, set()).add(item)
        return record

    def resolve(self, column: exp.Column, scope: Scope, item: int,
                seen: frozenset = frozenset()) -> set[tuple[str, str]]:
        marker = (id(scope), column.table.upper(), column.name.upper())
        if marker in seen or column.is_star:
            return set()
        sources = {a.upper(): s for a, (_, s) in scope.selected_sources.items()}
        candidates = ([sources[column.table.upper()]] if column.table.upper() in sources else
                      [] if column.table else list(sources.values()))
        matches = []
        for source in candidates:
            if isinstance(source, exp.Table):
                table = self.schema.table(source.name)
                if column.table or len(candidates) == 1 or column.name.upper() in self.schema.columns.get(table, {}):
                    matches.append({(table, self.schema.column(table, column.name))})
            elif isinstance(source, Scope):
                for projection in source.expression.selects:
                    if projection.alias_or_name.upper() == column.name.upper() or projection.is_star:
                        nodes = ([exp.column(column.name)] if projection.is_star else projection.find_all(exp.Column))
                        matches.append(set().union(*(self.resolve(c, source, item, seen | {marker}) for c in nodes)))
        if not matches and not column.table:
            projection = next((p for p in scope.expression.selects if p.alias.upper() == column.name.upper()), None)
            if projection is not None:
                return set().union(*(self.resolve(c, scope, item, seen | {marker}) for c in projection.find_all(exp.Column)))
        resolved = matches[0] if len(matches) == 1 else set()
        if not resolved and scope.parent and column.table:
            resolved = self.resolve(column, scope.parent, item, seen | {marker})
        if self.schema.given:
            for table, name in resolved:
                if name.upper() not in self.schema.columns.get(table, {}):
                    self.add("unresolved", (table, name), {"table": table, "column": name}, item)
            if not resolved:
                table = self.schema.table(column.table) if column.table else None
                data = {"table": table, "column": column.name.upper()} if table else {"column": column.name.upper()}
                self.add("unresolved", tuple(data.items()), data, item)
        return resolved

    def refs(self, node: exp.Expression, scope: Scope, item: int) -> set[tuple[str, str]]:
        return set().union(*(self.resolve(c, scope, item) for c in local_nodes(node) if isinstance(c, exp.Column)))

    def use_column(self, ref: tuple[str, str], item: int, role: str | None = None) -> None:
        self.add("columns", ref, {"table": ref[0], "column": ref[1]}, item, "roles" if role else None, role)

    def grain(self, nodes: list, evidence: str, scope: Scope, item: int) -> None:
        refs = set().union(*(self.refs(n, scope, item) for n in nodes))
        for table in sorted({t for t, _ in refs}):
            columns = tuple(sorted(c for t, c in refs if t == table))
            self.add("grain_keys", (table, columns), {"table": table, "columns": list(columns)}, item, "evidence", evidence)

    def joins(self, node: exp.Expression, kind: str, scope: Scope, item: int,
              extra: list | None = None) -> None:
        groups: dict[tuple, list] = {}
        pairs = list(extra or [])
        for eq in (n for n in local_nodes(node) if isinstance(n, exp.EQ)):
            if isinstance(eq.this, exp.Column) and isinstance(eq.expression, exp.Column):
                a, b = self.resolve(eq.this, scope, item), self.resolve(eq.expression, scope, item)
                if len(a) == len(b) == 1:
                    pairs.append((next(iter(a)), next(iter(b))))
        for a, b in pairs:
            if a[0] != b[0]:
                groups.setdefault(tuple(sorted((a[0], b[0]))), []).append((a, b))
                self.use_column(a, item, "join")
                self.use_column(b, item, "join")
        for pairs in groups.values():
            key = edge_key(pairs)
            data = {"left": {"table": key[0], "columns": list(key[1])},
                    "right": {"table": key[2], "columns": list(key[3])}}
            if self.schema.given:
                data["declared_fk"] = key in self.schema.fks
            self.add("join_edges", key, data, item, "kinds", kind)

    def filters(self, node: exp.Expression, scope: Scope, item: int) -> None:
        operators = {exp.EQ: "eq", exp.In: "in", exp.Like: "like", exp.ILike: "like",
                     exp.GT: "range", exp.GTE: "range", exp.LT: "range", exp.LTE: "range",
                     exp.Between: "range", exp.Is: "is_null"}
        for predicate in local_nodes(node):
            operator = operators.get(type(predicate))
            literals = {n.sql() for n in local_nodes(predicate) if isinstance(n, (exp.Literal, exp.Boolean, exp.Null))}
            if not operator or (operator == "is_null" and not isinstance(predicate.expression, exp.Null)):
                continue
            refs = self.refs(predicate, scope, item)
            if isinstance(predicate, exp.EQ) and isinstance(predicate.this, exp.Column) and isinstance(predicate.expression, exp.Column):
                if len({t for t, _ in refs}) > 1:
                    continue
            for ref in refs:
                record = self.add("filter_columns", ref, {"table": ref[0], "column": ref[1]}, item, "operators", operator)
                for literal in literals:
                    record.setdefault("_literals", {}).setdefault(literal, set()).add(item)
                self.use_column(ref, item, "filter")

    def expression_kind(self, node: exp.Expression) -> str | None:
        if isinstance(node, exp.Div) and any(node.find_all(exp.AggFunc)):
            return "aggregate-ratio"
        if isinstance(node, exp.Case):
            return "case"
        if isinstance(node, (exp.Extract, exp.Year, exp.Month, exp.Day, exp.DateTrunc, exp.TimestampTrunc, exp.TimeToStr)):
            return "date-part"
        if isinstance(node, exp.Anonymous) and node.name.upper() in ("DATE_PART", "DATEPART"):
            return "date-part"
        if isinstance(node, (exp.Concat, exp.DPipe, exp.Substring, exp.Upper, exp.Lower, exp.Trim)):
            return "string"
        if isinstance(node, (exp.Add, exp.Sub, exp.Mul, exp.Div, exp.Mod, exp.Neg)):
            return "arithmetic"
        return None

    def expressions(self, scope: Scope, item: int) -> None:
        for node in local_nodes(scope.expression):
            kind = self.expression_kind(node)
            if not kind:
                continue
            parent = node.parent
            while parent is not None and parent is not scope.expression and not self.expression_kind(parent):
                parent = parent.parent
            if parent is not scope.expression and parent is not None:
                continue
            refs = self.refs(node, scope, item)

            def replace(n: exp.Expression) -> exp.Expression:
                if isinstance(n, (exp.Literal, exp.Boolean, exp.Null)):
                    return exp.Placeholder()
                if isinstance(n, exp.Column):
                    resolved = self.resolve(n, scope, item)
                    if len(resolved) == 1:
                        table, column = next(iter(resolved))
                        return exp.column(column, table=table)
                return n

            template = node.transform(replace).sql(dialect=self.dialect, pretty=False, comments=False)
            self.add("expressions", (kind, template), {"kind": kind, "template": template,
                     "tables": sorted({t for t, _ in refs}), "columns": sorted(f"{t}.{c}" for t, c in refs)}, item)

    def analyze(self, tree: exp.Expression, item: int) -> None:
        for scope in traverse_scope(tree):
            if not isinstance(scope.expression, exp.Select):
                continue
            for _, source in scope.selected_sources.values():
                if isinstance(source, exp.Table):
                    table = self.schema.table(source.name)
                    self.add("tables", table, {"table": table}, item)
                    if self.schema.given and table not in self.schema.columns:
                        self.add("unresolved", (table,), {"table": table}, item)
            for column in scope.columns:
                roles = {"select"} if any(column is p for p in scope.expression.selects) else set()
                parent = column.parent
                while parent is not None and parent is not scope.expression:
                    if any(parent is p for p in scope.expression.selects):
                        roles.add("select")
                    for cls, role in ((exp.Where, "filter"), (exp.Having, "filter"), (exp.Join, "join"),
                                      (exp.Group, "group"), (exp.Order, "order"), (exp.AggFunc, "aggregate")):
                        if isinstance(parent, cls):
                            roles.add(role)
                    parent = parent.parent
                for ref in self.resolve(column, scope, item):
                    self.use_column(ref, item)
                    for role in roles:
                        self.use_column(ref, item, role)
            self.analyze_clauses(scope, item)
            self.expressions(scope, item)

    def analyze_clauses(self, scope: Scope, item: int) -> None:
        select = scope.expression
        prior = [select.args["from_"].this] if select.args.get("from_") else []
        for join in select.args.get("joins", []):
            pairs = []
            for column in join.args.get("using", []):
                right = self.resolve(exp.column(column.name, table=join.this.alias_or_name), scope, item)
                left = set()
                for source in prior:
                    table = self.schema.table(source.name) if isinstance(source, exp.Table) else ""
                    if table in self.schema.columns and column.name.upper() not in self.schema.columns[table]:
                        continue
                    left = self.resolve(exp.column(column.name, table=source.alias_or_name), scope, item)
                    if left:
                        break
                if len(left) == len(right) == 1:
                    pairs.append((next(iter(left)), next(iter(right))))
            kind = (join.side or join.args.get("kind") or "inner").lower()
            self.joins(join.args.get("on") or exp.true(), kind, scope, item, pairs)
            prior.append(join.this)
        for clause in (select.args.get("where"), select.args.get("having")):
            if clause:
                self.joins(clause, "inner", scope, item)
        self.filters(select, scope, item)
        if select.args.get("group"):
            self.grain(select.args["group"].expressions, "group_by", scope, item)
        if select.args.get("distinct"):
            self.grain(select.selects, "distinct", scope, item)
        for count in (n for n in local_nodes(select) if isinstance(n, exp.Count)):
            if isinstance(count.this, exp.Distinct):
                self.grain(count.this.expressions, "count_distinct", scope, item)

    def sections(self, item: int | None = None) -> dict:
        result = {}
        defaults = {"roles": ("select", "filter", "join", "group", "order", "aggregate"),
                    "operators": ("eq", "in", "like", "range", "is_null"),
                    "evidence": ("group_by", "count_distinct", "distinct")}
        for section, records in self.records.items():
            if section == "unresolved" and not self.schema.given:
                continue
            rows = []
            for record in records.values():
                if item is not None and item not in record["_items"]:
                    continue
                count = lambda items: len(items) if item is None else int(item in items)
                row = {k: v for k, v in record.items() if not k.startswith("_")}
                row["support"] = count(record["_items"])
                counters = dict(record["_counts"])
                for field in ({"columns": ["roles"], "grain_keys": ["evidence"],
                               "filter_columns": ["operators"]}.get(section, [])):
                    counters.setdefault(field, {})
                for field, counts in counters.items():
                    names = defaults.get(field, sorted(counts))
                    row[field] = {name: count(counts.get(name, set())) for name in names}
                if section == "filter_columns":
                    row["distinct_literals"] = sum(count(items) > 0 for items in record.get("_literals", {}).values())
                rows.append(row)
            rows.sort(key=lambda row: (-row["support"], self.name_key(row)))
            if item is None and section in ("join_edges", "expressions"):
                prefix = "je" if section == "join_edges" else "ex"
                rows = [{"id": f"{prefix}_{i}", **row} for i, row in enumerate(rows, 1)]
            result[section] = rows
        return result

    def contributions(self, items: list[dict]) -> dict:
        result = {row["id"]: self.sections(i) for i, row in enumerate(items)}
        for item in result.values():
            for row in item["filter_columns"]:
                record = self.records["filter_columns"][(row["table"], row["column"])]
                cohorts = Counter(tuple(sorted(items[i]["id"] for i in members))
                                  for members in record.get("_literals", {}).values())
                row["literal_cohorts"] = [{"items": list(members), "count": count}
                                          for members, count in sorted(cohorts.items())]
        return dict(sorted(result.items()))

    def name_key(self, row: dict) -> tuple:
        if "left" in row:
            return (row["left"]["table"], tuple(row["left"]["columns"]),
                    row["right"]["table"], tuple(row["right"]["columns"]))
        if "template" in row:
            return (row["kind"], row["template"])
        return (row.get("table", ""), row.get("column", ""), tuple(row.get("columns", [])))


class DuplicateItemID(ValueError):
    pass


def select_items(items: list[dict], ids: Path | None, split: str | None,
                 verification: Path | None) -> list[dict]:
    known = {row["id"] for row in items}
    if len(known) != len(items):
        duplicate = next(identifier for identifier, count in Counter(row["id"] for row in items).items() if count > 1)
        raise DuplicateItemID(f"duplicate workload item id: {duplicate}")
    selected = set(ids.read_text(encoding="utf-8").splitlines()) - {""} if ids else known
    if selected - known:
        raise ValueError("ids file contains unknown workload item ids")
    if split:
        if verification is None:
            raise ValueError("--split requires --verification")
        saved = json.loads(verification.read_text(encoding="utf-8"))
        assignments = {str(row["id"]): row.get("split") for row in saved.get("items", [])}
        if len(assignments) != len(saved.get("items", [])) or any(
                assignments.get(item) not in {"repair", "holdout"} for item in selected):
            raise ValueError("verification needs one saved split assignment per selected item")
        selected &= {item for item, assigned in assignments.items() if assigned == split}
    return [row for row in items if row["id"] in selected]


def build_digest(path: Path, dialect: str = "sqlite", schema: Path | None = None,
                 kind: str | None = None, no_timestamp: bool = False, ids: Path | None = None,
                 split: str | None = None, verification: Path | None = None) -> dict:
    paths = [path] if isinstance(path, Path) else list(path)
    items = [item for source in paths for item in read_items(source)]
    kind = kind or ("pairs" if any(i["sql"] for i in items) and any(i["question"] for i in items)
                    else "sql" if any(i["sql"] for i in items) else "questions")
    items = select_items(items, ids, split, verification)
    n_sql, n_questions = sum(bool(i["sql"]) for i in items), sum(bool(i["question"]) for i in items)
    workload = {"kind": kind, "artifacts": [source.name for source in paths]}
    if kind != "questions":
        workload["dialect"] = dialect
    workload.update(n_items=len(items), n_sql=n_sql, n_questions=n_questions, n_parsed=0,
                    parse_errors=[], skipped_non_select=0, extraction="tool")
    if not no_timestamp:
        workload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if kind == "questions":
        return {"workload": workload, "item_contributions": {row["id"]: {} for row in sorted(items, key=lambda r: r["id"])}}
    digest = Digest(Schema(schema, dialect), dialect)
    for item, row in enumerate(items):
        if not row["sql"]:
            continue
        try:
            trees = sqlglot.parse(row["sql"], read=dialect)
        except sqlglot.errors.SqlglotError:
            workload["parse_errors"].append(row["id"])
            continue
        for tree in trees:
            if tree is None:
                continue
            workload["n_parsed"] += 1
            if isinstance(tree, exp.Query):
                digest.analyze(tree, item)
            else:
                workload["skipped_non_select"] += 1
    workload["parse_errors"].sort()
    return {"version": 1, "workload": workload, **digest.sections(),
            "item_contributions": digest.contributions(items)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, action="append")
    parser.add_argument("--dialect", default="sqlite")
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--kind", choices=("sql", "questions", "pairs"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--no-timestamp", action="store_true")
    parser.add_argument("--ids", type=Path, help="one workload item id per line")
    parser.add_argument("--split", choices=("repair", "holdout"))
    parser.add_argument("--verification", type=Path, help="saved model.verification.json split assignments")
    args = parser.parse_args(argv)
    if args.split and not args.verification:
        parser.error("--split requires --verification")
    try:
        result = build_digest(args.input, args.dialect, args.schema, args.kind, args.no_timestamp,
                              args.ids, args.split, args.verification)
    except DuplicateItemID as error:
        parser.error(str(error))
    args.out.write_text(yaml.safe_dump(result, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
