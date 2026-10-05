#!/usr/bin/env python3
"""Check ORM reachability and propose count-only, data-tested relationships."""

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import re
import sys

import duckdb
import networkx as nx
import yaml


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def stable_id(prefix, value):
    return prefix + hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def bindings(model):
    """Normalize explicit source bindings and legacy provenance pointers."""
    result = []
    for item in model.get("source_bindings", []):
        result.append({"table": item["table"], "object_type": item.get("object_type"),
                       "columns": list(item.get("columns", [])),
                       "dropped_columns": list(item.get("dropped_columns", [])),
                       "key_columns": list(item.get("key_columns", []))})
    for item in model.get("object_types", []) + model.get("fact_types", []):
        p = item.get("provenance", {})
        tables = p.get("tables", []) + ([p["table"]] if p.get("table") else [])
        keys = p.get("pk_columns", []) + ([p["pk_column"]] if p.get("pk_column") else [])
        columns = p.get("columns", []) + ([p["column"]] if p.get("column") else [])
        for table in tables:
            result.append({"table": table,
                           "object_type": item["id"] if item.get("kind") == "entity" else None,
                           "columns": columns + keys, "dropped_columns": [], "key_columns": keys})
        # Applied data-link facts bind both source column tuples.
        if item.get("source") == "data" and item.get("status") != "rejected":
            for side, role in zip((p.get("left"), p.get("right")), item.get("roles", [])):
                if side:
                    result.append({"table": side["table"], "object_type": role["object_type"],
                                   "columns": list(side["columns"]), "dropped_columns": [], "key_columns": []})
        for role in item.get("roles", []):
            p = role.get("provenance", {})
            if p.get("table") and p.get("column"):
                result.append({"table": p["table"], "object_type": role["object_type"],
                               "columns": [p["column"]], "dropped_columns": [], "key_columns": []})
    return result


def model_graph(model):
    entities = {o["id"]: o["name"] for o in model.get("object_types", []) if o["kind"] == "entity"}
    graph = nx.Graph()
    graph.add_nodes_from(sorted(entities))
    relationships = defaultdict(set)
    def link(a, b, rid):
        graph.add_edge(a, b)
        relationships[a].add(rid)
        relationships[b].add(rid)
    for fact in model.get("fact_types", []):
        if fact.get("status") == "rejected":
            continue
        roles = [r["object_type"] for r in fact.get("roles", []) if r["object_type"] in entities]
        for a, b in combinations(roles, 2):
            link(a, b, "fact:" + fact["id"])
        if fact.get("objectified_as") in entities:
            for role in roles:
                link(fact["objectified_as"], role, "fact:" + fact["id"])
    for o in model.get("object_types", []):
        if o["id"] in entities:
            for parent in o.get("subtype_of", []):
                if parent in entities:
                    link(o["id"], parent, "subtype:" + o["id"] + ":" + parent)
    tables = defaultdict(set)
    keys = defaultdict(set)
    for b in bindings(model):
        if b["object_type"] in entities:
            tables[b["table"]].add(b["object_type"])
        keys[b["table"]].update(b["key_columns"])
    # Uniqueness-role provenance also declares a key-like column.
    facts = {f["id"]: f for f in model.get("fact_types", [])}
    constraints = [(c, f) for f in facts.values() for c in f.get("constraints", [])]
    constraints += [(c, None) for c in model.get("constraints", [])]
    for c, fact in constraints:
        if c.get("type") != "uniqueness" or c.get("status") == "rejected":
            continue
        refs = list(c.get("role_refs", []))
        if fact:
            refs += [{"fact_type": fact["id"], "role": r} for r in c.get("roles", [])]
        for ref in refs:
            for role in facts.get(ref["fact_type"], {}).get("roles", []):
                p = role.get("provenance", {})
                if role.get("role_name") == ref["role"] and p.get("table") and p.get("column"):
                    keys[p["table"]].add(p["column"])
    return graph, entities, tables, relationships, keys


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def table_sql(table):
    return ".".join(quote(p) for p in table.split("."))


def type_family(dtype):
    dtype = dtype.upper()
    if re.match(r"^(U?TINYINT|U?SMALLINT|U?INTEGER|U?BIGINT|U?HUGEINT|DECIMAL|NUMERIC|FLOAT|DOUBLE|REAL)", dtype):
        return "numeric"
    if dtype.startswith(("VARCHAR", "CHAR", "TEXT", "STRING")):
        return "text"
    if dtype.startswith("TIMESTAMP"):
        return "timestamp"
    return dtype if dtype in {"DATE", "BOOLEAN", "BLOB", "UUID", "TIME"} else None


@lru_cache(maxsize=65536)
def name_similarity(a, b):
    normalize = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return round(SequenceMatcher(None, normalize(a), normalize(b)).ratio(), 6)


def column_counts(db, table, columns):
    """One aggregate scan per table; no source values leave DuckDB."""
    selected = [c for c, dtype in columns.items() if dtype]
    expressions = ["count(*)"]
    for col in selected:
        expressions += [f"count(DISTINCT {quote(col)})", f"count({quote(col)})"]
    counts = db.execute(f"SELECT {', '.join(expressions)} FROM {table_sql(table)}").fetchone()
    rows = counts[0]
    return {col: {"rows": rows, "distinct": counts[1 + 2 * i],
                  "null_rate": round((rows - counts[2 + 2 * i]) / rows, 6) if rows else 0.0}
            for i, col in enumerate(selected)}


def test_values(db, left, right, profiles=None):
    """Only aggregate counts cross the database boundary; composite keys stay tuples."""
    def selection(side):
        cols = side["columns"]
        selected = ", ".join(quote(c) for c in cols)
        valid = " AND ".join(quote(c) + " IS NOT NULL" for c in cols)
        table = table_sql(side["table"])
        return f"SELECT DISTINCT {selected} FROM {table} WHERE {valid}", valid, table
    a, av, at = selection(left)
    b, bv, bt = selection(right)
    def row_counts(table, valid):
        rows, nonnull = db.execute(f"SELECT count(*), count(*) FILTER (WHERE {valid}) FROM {table}").fetchone()
        return rows, round((rows - nonnull) / rows, 6) if rows else 0.0
    if profiles is not None and len(left["columns"]) == len(right["columns"]) == 1:
        pa = profiles[left["table"]][left["columns"][0]]
        pb = profiles[right["table"]][right["columns"][0]]
        distinct_a, distinct_b = pa["distinct"], pb["distinct"]
        shared = db.execute(f"SELECT count(*) FROM ({a} INTERSECT {b})").fetchone()[0]
        null_a, null_b = pa["null_rate"], pb["null_rate"]
        rows_a, rows_b = pa["rows"], pb["rows"]
    else:
        distinct_a, distinct_b, shared = db.execute(
            f"WITH a AS ({a}), b AS ({b}) SELECT (SELECT count(*) FROM a), "
            "(SELECT count(*) FROM b), (SELECT count(*) FROM (SELECT * FROM a INTERSECT SELECT * FROM b))"
        ).fetchone()
        rows_a, null_a = row_counts(at, av)
        rows_b, null_b = row_counts(bt, bv)
    return {"distinct_left": distinct_a, "distinct_right": distinct_b, "shared_distinct": shared,
            "containment_left": round(shared / distinct_a, 6) if distinct_a else 0.0,
            "containment_right": round(shared / distinct_b, 6) if distinct_b else 0.0,
            "null_rate_left": null_a, "null_rate_right": null_b,
            "rows_left": rows_a, "rows_right": rows_b}


def analyze(model, digest=None, db=None, fk=0.98, partial=0.30, max_comparisons=5000):
    graph, names, tables, relations, keys = model_graph(model)
    groups = sorted((sorted(c) for c in nx.connected_components(graph)), key=lambda c: (-len(c), c))
    component_of = {n: i for i, group in enumerate(groups) for n in group}
    isolated = sorted(n for n in graph if not (set(graph.neighbors(n)) - {n}))
    components = [{"id": f"component_{i + 1}", "size": len(group),
                   "concepts": [{"id": n, "name": names[n]} for n in group],
                   "tables": sorted(t for t, nodes in tables.items() if nodes.intersection(group))}
                  for i, group in enumerate(groups)]
    # Resolve case-insensitively, but never guess an ambiguous unqualified table.
    def resolve(table):
        exact = [t for t in tables if t.casefold() == table.casefold()]
        suffix = [t for t in tables if t.split(".")[-1].casefold() == table.casefold()]
        return exact[0] if exact else (suffix[0] if len(suffix) == 1 else table)
    gaps, joins = [], []
    for edge in sorted((digest or {}).get("join_edges", []), key=lambda e: e["id"]):
        left = {"table": resolve(edge["left"]["table"]), "columns": list(edge["left"]["columns"])}
        right = {"table": resolve(edge["right"]["table"]), "columns": list(edge["right"]["columns"])}
        a, b = tables[left["table"]], tables[right["table"]]
        state = "merged" if a & b else ("reachable" if any(nx.has_path(graph, x, y) for x, y in product(a, b)) else "required_gap")
        joins.append({"id": edge["id"], "status": state})
        if state == "required_gap":
            gaps.append({"id": edge["id"], "left": left, "right": right, "support": edge.get("support", 0),
                         "left_concepts": sorted(a), "right_concepts": sorted(b), "best_candidate": None})
    columns, profiles = {}, {}
    if db:
        for table in sorted(tables):
            try:
                metadata = db.execute(f"SELECT * FROM {table_sql(table)} LIMIT 0").description
                columns[table] = {column[0]: type_family(str(column[1])) for column in metadata}
                profiles[table] = column_counts(db, table, columns[table])
            except duckdb.Error:
                columns[table] = {}
    requests = {}
    def canonical(side):
        table = resolve(side["table"])
        metadata = {c.casefold(): c for c in columns.get(table, {})}
        return {"table": table, "columns": [metadata.get(c.casefold(), c) for c in side["columns"]]}
    keys = {t: {c.casefold() for c in cols} for t, cols in keys.items()}
    def declared(side):
        return bool(side["columns"]) and all(c.casefold() in keys.get(side["table"], set()) for c in side["columns"])
    def signature(left, right):
        return tuple(sorted((s["table"], tuple(s["columns"])) for s in (left, right)))
    def add(left, right, required=None):
        # Canonical sides ensure digest orientation cannot change evidence or ids.
        sides = sorted([left, right], key=lambda s: (s["table"], s["columns"]))
        key = signature(left, right)
        request = requests.setdefault(key, {"id": stable_id("candidate_", sides), "left": sides[0], "right": sides[1], "required_gaps": []})
        if required and required not in request["required_gaps"]:
            request["required_gaps"].append(required)
    for gap in gaps:
        gap["left"], gap["right"] = canonical(gap["left"]), canonical(gap["right"])
        add(gap["left"], gap["right"], gap["id"])
    rejected = list(model.get("rejected_proposals", [])) + [
        f for f in model.get("fact_types", []) if f.get("status") == "rejected"]
    rejected_ids = {p if isinstance(p, str) else p.get("id") for p in rejected}
    rejected_links = set()
    for proposal in rejected:
        if not isinstance(proposal, dict):
            continue
        provenance = proposal.get("provenance", {})
        if provenance.get("left") and provenance.get("right"):
            rejected_links.add((signature(canonical(provenance["left"]), canonical(provenance["right"])),
                                tuple(sorted(r["object_type"] for r in proposal.get("roles", [])))))
    gap_pairs = {tuple(sorted((g["left"]["table"], g["right"]["table"]))) for g in gaps}
    isolated_tables = {t for t, nodes in tables.items() if nodes.intersection(isolated)}
    def pair_priority(pair):
        return (pair not in gap_pairs, not any(t in isolated_tables for t in pair), pair)
    def candidate_requests():
        yield from sorted(requests.values(), key=lambda r: r["id"])
        # Stream exploratory pairs instead of retaining hundreds of thousands of dictionaries.
        for ta, tb in sorted(combinations(sorted(columns), 2), key=pair_priority):
            if not tables[ta] or not tables[tb] or any(component_of[a] == component_of[b] for a, b in product(tables[ta], tables[tb])):
                continue
            for ca, cb in product(sorted(columns[ta]), sorted(columns[tb])):
                if not columns[ta][ca] or columns[ta][ca] != columns[tb][cb]:
                    continue
                if ca.casefold() not in keys.get(ta, set()) and cb.casefold() not in keys.get(tb, set()) and name_similarity(ca, cb) < 0.65:
                    continue
                left, right = {"table": ta, "columns": [ca]}, {"table": tb, "columns": [cb]}
                if signature(left, right) not in requests:
                    yield {"left": left, "right": right, "required_gaps": []}
    candidates, proposals, comparisons, untested = [], [], 0, 0
    by_class = Counter()
    gaps_by_id = {g["id"]: g for g in gaps}
    joins_by_id = {j["id"]: j for j in joins}
    for r in candidate_requests():
        left, right = r["left"], r["right"]
        compatible = len(left["columns"]) == len(right["columns"]) and bool(left["columns"])
        for a, b in zip(left["columns"], right["columns"]):
            dtype = columns.get(left["table"], {}).get(a)
            compatible &= bool(dtype) and dtype == columns.get(right["table"], {}).get(b)
        evidence = {"name_similarity": round(sum(name_similarity(a, b) for a, b in zip(left["columns"], right["columns"])) / max(len(left["columns"]), 1), 6)}
        classification, test_status = "none", "no-db" if db is None else "incompatible-or-missing"
        if db and compatible:
            # Degenerate columns cannot establish a meaningful link. Tuple probes
            # still compare whole keys; a constant member may belong to a valid key.
            degenerate = False
            if len(left["columns"]) == 1:
                pa = profiles[left["table"]][left["columns"][0]]
                pb = profiles[right["table"]][right["columns"][0]]
                degenerate = not pa["distinct"] or not pb["distinct"] or pa["distinct"] == pb["distinct"] == 1
            if degenerate:
                test_status = "degenerate-columns"
                evidence.update({"distinct_left": pa["distinct"], "distinct_right": pb["distinct"],
                                 "null_rate_left": pa["null_rate"], "null_rate_right": pb["null_rate"]})
            elif not r["required_gaps"] and len(left["columns"]) == 1 and min(pa["distinct"], pb["distinct"]) < 10:
                test_status = "low-cardinality"
            elif comparisons >= max_comparisons:
                test_status = "comparison-cap"
                untested += 1
            else:
                comparisons += 1
                try:
                    evidence.update(test_values(db, left, right, profiles))
                    test_status = "tested"
                    rate = max(evidence["shared_distinct"] / evidence["distinct_left"] if evidence["distinct_left"] else 0,
                               evidence["shared_distinct"] / evidence["distinct_right"] if evidence["distinct_right"] else 0)
                    unique_side = any(declared(side) or (
                        evidence["rows_" + label] > 0 and
                        evidence["distinct_" + label] / evidence["rows_" + label] >= 0.98)
                        for side, label in ((left, "left"), (right, "right")))
                    classification = "fk-like" if rate >= fk and unique_side else ("partial" if rate >= partial else "none")
                except duckdb.Error:
                    test_status = "probe-error"
        r.update({"classification": classification, "test_status": test_status, "evidence": evidence})
        by_class[classification] += 1
        if classification == "none" and not r["required_gaps"]:
            continue
        r.setdefault("id", stable_id("candidate_", [left, right]))
        if classification == "partial":
            r["partial"] = True
        candidates.append(r)
        for gap_id in r["required_gaps"]:
            gap = gaps_by_id[gap_id]
            gap["best_candidate"] = r["id"]
            gap["partial"] = classification == "partial"
            joins_by_id[gap_id]["candidate"] = r["id"]
        if classification == "fk-like" or r["required_gaps"]:
            for a, b in product(sorted(tables[left["table"]]), sorted(tables[right["table"]])):
                if a == b or nx.has_path(graph, a, b):
                    continue
                proposal = {"id": stable_id("data_link_", [r["id"], a, b]),
                            "reading": "{" + names[a] + "} relates to {" + names[b] + "}",
                            "roles": [{"object_type": a, "role_name": "left"}, {"object_type": b, "role_name": "right"}],
                            "status": "proposed", "source": "data",
                            "provenance": {"origin": "data", "left": left, "right": right,
                                           "required_gaps": r["required_gaps"], "test_status": test_status, "evidence": evidence}}
                if classification == "partial":
                    proposal["partial"] = True
                if (proposal["id"] not in rejected_ids and
                        (signature(left, right), tuple(sorted((a, b)))) not in rejected_links):
                    proposals.append(proposal)
    counts = [{"id": n, "name": names[n], "relationships": len(relations[n])} for n in sorted(names)]
    result = {"version": 1, "summary": {"concepts": len(names), "relationships": len(set().union(*relations.values())) if relations else 0,
              "components": len(groups), "largest_component": len(groups[0]) if groups else 0, "isolated": len(isolated),
              "value_comparisons": comparisons, "comparison_cap": max_comparisons,
              "comparison_cap_reached": untested > 0, "candidates_untested": untested,
              "candidates_by_class": {k: by_class[k] for k in ("fk-like", "partial", "none")}},
              "components": components, "isolated_concepts": [{"id": n, "name": names[n]} for n in isolated],
              "relationships_per_concept": counts, "join_checks": joins, "required_gaps": gaps, "candidates": sorted(candidates, key=lambda r: r["id"]),
              "verdict": "required-gaps" if gaps else ("islands" if len(groups) > 1 else "connected")}
    return result, {"version": 1, "fact_types": sorted(proposals, key=lambda p: p["id"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--db")
    parser.add_argument("--digest")
    parser.add_argument("--out", default="connectivity.json")
    parser.add_argument("--proposals", default="connectivity.proposals.yaml")
    parser.add_argument("--fk-containment", type=float, default=0.98)
    parser.add_argument("--partial-containment", type=float, default=0.30)
    parser.add_argument("--max-comparisons", type=int, default=5000)
    parser.add_argument("--fail-on-required-gap", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.partial_containment <= args.fk_containment <= 1 or args.max_comparisons < 0:
        parser.error("invalid containment thresholds or comparison cap")
    db = None
    try:
        if args.db:
            db = duckdb.connect(args.db, read_only=True)
        result, proposals = analyze(read_yaml(args.model), read_yaml(args.digest) if args.digest else None,
                                    db, args.fk_containment, args.partial_containment, args.max_comparisons)
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        Path(args.proposals).write_text(yaml.safe_dump(proposals, sort_keys=False), encoding="utf-8")
        return 2 if args.fail_on_required_gap and result["required_gaps"] else 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, duckdb.Error):
        # Exceptions can contain source values or SQL; never print their text.
        print("Connectivity check failed: check input structure and database access.", file=sys.stderr)
        return 1
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
