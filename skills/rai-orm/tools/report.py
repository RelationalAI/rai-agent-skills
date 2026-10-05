#!/usr/bin/env python3
"""Produce deterministic ORM statistics and actionable, count-only issues."""

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import sys

import yaml

from connectivity import analyze, bindings, read_yaml


STATUSES = ("pass", "fail", "unverified", "inexpressible", "oracle-error")


def concept_usage(model, verification, base_dir):
    """Read only saved PyRel paths listed in verification, never workload text."""
    items = verification.get("items", [])
    if not any(i.get("pyrel") for i in items):
        return None
    names = {o["name"]: o["id"] for o in model.get("object_types", []) if o["kind"] == "entity"}
    usage = Counter()
    for item in items:
        if not item.get("pyrel"):
            continue
        try:
            tree = ast.parse((Path(base_dir) / item["pyrel"]).read_text())
        except (OSError, SyntaxError, UnicodeError):
            # Incomplete files cannot support a singleton-use conclusion.
            return None
        aliases = {a.asname: a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   for a in n.names if a.asname and a.name in names}
        used = set()
        for node in ast.walk(tree):
            name = node.id if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) else (node.attr if isinstance(node, ast.Attribute) else None)
            name = aliases.get(name, name)
            if name in names:
                used.add(names[name])
        usage.update(used)
    return usage


def build_report(model, verification=None, connectivity=None, digest=None, base_dir="."):
    connectivity = connectivity if connectivity is not None else analyze(model, digest)[0]
    objects = Counter(o["kind"] for o in model.get("object_types", []))
    kinds = {o["id"]: o["kind"] for o in model.get("object_types", [])}
    arities, fact_counts = Counter(), Counter()
    constraints = list(model.get("constraints", []))
    for fact in model.get("fact_types", []):
        arity = fact.get("arity", len(fact.get("roles", [])))
        arities["unary" if arity == 1 else ("binary" if arity == 2 else "n-ary")] += 1
        roles = fact.get("roles", [])
        if arity == 1:
            fact_counts["flags"] += 1
        elif arity == 2:
            if len(roles) == 2 and all(kinds.get(r["object_type"]) == "entity" for r in roles):
                fact_counts["entity_relationships"] += 1
            elif len(roles) == 2 and kinds.get(roles[1]["object_type"]) == "value":
                fact_counts["scalar_properties"] += 1
        else:
            fact_counts["n_ary"] += 1
        constraints.extend(fact.get("constraints", []))
    by_source = Counter(c.get("source", "unspecified") for c in constraints)
    by_status = Counter(c.get("status", "unspecified") for c in constraints)
    source_status = Counter((c.get("source", "unspecified"), c.get("status", "unspecified")) for c in constraints)
    bound, dropped, covered = set(), set(), set()
    for b in bindings(model):
        covered.add(b["table"])
        bound.update((b["table"], col) for col in b["columns"])
        dropped.update((b["table"], col) for col in b["dropped_columns"])
    dropped -= bound
    scoped = {t for t in model.get("source", {}).get("scope", {}).get("tables", []) if t != "*"}
    inventory = {(i["table"], col) for i in model.get("source", {}).get("columns", []) for col in i.get("columns", [])}
    stats = {"object_types": {k: objects[k] for k in ("entity", "value")},
             "fact_types": {k: fact_counts[k] for k in ("entity_relationships", "scalar_properties", "flags", "n_ary")},
             "fact_types_total_unary": arities["unary"], "fact_types_total_binary": arities["binary"],
             "fact_types_total_n_ary": arities["n-ary"],
             "constraints": {"total": len(constraints), "by_source": dict(sorted(by_source.items())),
                             "by_status": dict(sorted(by_status.items())),
                             "by_source_and_status": [{"source": a, "status": b, "count": n} for (a, b), n in sorted(source_status.items())]},
             "relationships_per_concept": connectivity.get("relationships_per_concept", []),
             "components": connectivity.get("components", []), "isolated_concepts": connectivity.get("isolated_concepts", []),
             "sources": {"tables_covered": len(covered), "covered_tables": sorted(covered),
                         "uncovered_tables": sorted(scoped - covered), "columns_bound": len(bound),
                         "columns_dropped": len(dropped),
                         "dropped_columns": [{"table": t, "column": c} for t, c in sorted(dropped)],
                         "columns_unaccounted": len(inventory - bound - dropped) if inventory else None}}
    issues = []
    def issue(identifier, severity, count, action, **evidence):
        issues.append({"id": identifier, "severity": severity, "count": count,
                       "next_action": action, **evidence})
    total = (digest or {}).get("workload", {}).get("n_items", 0)
    residual, status, rounds = 0, "unverified", []
    if verification is not None:
        summary = verification.get("summary", {})
        items = verification.get("items", [])
        total = verification.get("workload", {}).get("n_items", total or len(items))
        total = max(total, len(items))
        counts = Counter(i.get("status", "unverified") for i in items)
        for k in ("inexpressible", "oracle-error"):
            counts[k] = max(counts[k], summary.get("excluded", {}).get(k, 0))
        counts["unverified"] += max(0, total - sum(counts.values()))
        residual_by_class = Counter(summary.get("residual_by_class", {}))
        item_classes = Counter(i.get("class", "unclassified") for i in items if i.get("status") == "fail")
        for cls, count in item_classes.items():
            residual_by_class[cls] = max(residual_by_class[cls], count)
        residual = max(sum(residual_by_class.values()), counts["fail"])
        repairs = Counter(r["round"] for r in verification.get("repairs", []))
        for r in verification.get("rounds", []):
            rounds.append({"round": r["round"], "repair_pass": r.get("repair_pass", 0),
                           "holdout_pass": r.get("holdout_pass", 0), "repairs": repairs[r["round"]],
                           "regressions": r.get("regressions", 0)})
            if "connectivity" in r:
                c = r["connectivity"]
                rounds[-1]["connectivity"] = {"components": c.get("components", 0),
                                              "isolated": sorted(c.get("isolated", [])),
                                              "required_gaps": sorted(c.get("required_gaps", []))}
        repair_rate = summary.get("repair_pass_rate")
        holdout_rate = summary.get("holdout_pass_rate")
        def pass_rate(split):
            selected = [i for i in items if i.get("split") == split and i.get("status") not in {"inexpressible", "oracle-error"}]
            return sum(i.get("status") == "pass" for i in selected) / len(selected) if selected else None
        repair_rate = repair_rate if repair_rate is not None else pass_rate("repair")
        holdout_rate = holdout_rate if holdout_rate is not None else pass_rate("holdout")
        stop = summary.get("stopped_because")
        status = "budget-exhausted" if stop == "budget" and residual else ("residual-failures" if residual else ("unverified" if counts["unverified"] else "all-pass"))
        stats["verification"] = {"rounds": rounds, "regressions": sum(r["regressions"] for r in rounds),
                                 "residual_failures": residual, "residual_by_class": dict(sorted(residual_by_class.items())),
                                 "items_by_status": {k: counts[k] for k in STATUSES},
                                 "repair_pass_rate": repair_rate, "holdout_pass_rate": holdout_rate}
        if stop == "budget" and residual:
            issue("BUDGET_EXHAUSTED", "blocker", residual,
                  "Resume rai-orm-verify at Step 5 with model.verification.json; increase the round budget and re-run Step 6.")
        if stop == "plateau" or (len(rounds) >= 3 and rounds[-1]["repair_pass"] <= rounds[-2]["repair_pass"] <= rounds[-3]["repair_pass"] and residual):
            issue("PLATEAU", "warning", residual, "Review grouped residual failures at rai-orm-verify Step 4 before another repair round.")
        if repair_rate is not None and holdout_rate is not None and repair_rate - holdout_rate > 0.15 + 1e-12:
            issue("HOLDOUT_GAP", "warning", verification.get("split", {}).get("holdout", 0),
                  "Review whether repairs are general at rai-orm-verify Step 5; repairs may be fitted to the repair set.",
                  repair_pass_rate=repair_rate, holdout_pass_rate=holdout_rate)
        for k, identifier, action in [("oracle-error", "ORACLE_ERRORS", "Repair the verification oracle and re-check excluded items at rai-orm-verify Step 3."),
                                       ("inexpressible", "INEXPRESSIBLE_ITEMS", "Review excluded constructs and document the supported workload boundary.")]:
            if counts[k]:
                issue(identifier, "warning", counts[k], action)
        regressions = stats["verification"]["regressions"]
        if regressions:
            issue("REGRESSIONS", "warning", regressions, "Re-run saved passing PyRel files at rai-orm-verify Step 6 and review rollback decisions.")
        usage = concept_usage(model, verification, base_dir)
        if usage is not None:
            singletons = sorted(k for k, v in usage.items() if v == 1)
            if singletons:
                issue("SINGLE_ITEM_CONCEPTS", "warning", len(singletons),
                      "Review these concepts for query-shaped modeling against the schema and domain vocabulary.", concept_ids=singletons)
        unverified = counts["unverified"]
    else:
        unverified = total
    if unverified:
        issue("UNVERIFIED_ITEMS", "warning", unverified, "Continue oracle checks or user review at rai-orm-verify Step 3.",
              workload_share=round(unverified / total, 6) if total else None)
    components = len(connectivity.get("components", []))
    if components > 1:
        issue("ISLANDS", "warning", components, "Review connectivity.proposals.yaml using the connectivity procedure; justify remaining islands in ontology-notes.md.")
    isolated = len(connectivity.get("isolated_concepts", []))
    if isolated:
        issue("ISOLATED_CONCEPTS", "warning", isolated, "Review source bindings and data-tested link proposals for isolated concepts.")
    comparison_summary = connectivity.get("summary", {})
    if comparison_summary.get("comparison_cap_reached"):
        untested_links = comparison_summary.get("candidates_untested", 0)
        issue("COMPARISON_CAP_REACHED", "warning", untested_links,
              f"{untested_links} candidate links were not tested; raise --max-comparisons")
    gaps = len(connectivity.get("required_gaps", []))
    if gaps:
        issue("REQUIRED_JOIN_GAPS", "blocker", gaps, "Classify as missing-element at rai-orm-verify Step 4 and add proposed links with overlap evidence at Step 5.")
        if status == "all-pass":
            status = "required-gaps"
    if dropped:
        issue("DROPPED_COLUMNS", "warning", len(dropped), "Bind dropped source columns or record their justification in ontology-notes.md.")
    if verification is None:
        stats["verification"] = None
    return {"version": 1, "status": status, "statistics": stats,
            "issues": sorted(issues, key=lambda i: (i["id"] != "BUDGET_EXHAUSTED", {"blocker": 0, "warning": 1, "info": 2}[i["severity"]], i["id"]))}


def markdown(report):
    issues = report["issues"]
    budget = next((i for i in issues if i["id"] == "BUDGET_EXHAUSTED"), None)
    lines = ([f"BUDGET_EXHAUSTED: {budget['count']} residual failures. Continue: {budget['next_action']}", ""] if budget else [])
    lines += ["# ORM statistics and issues", "", f"Status: {report['status']}", ""]
    stats = report["statistics"]
    facts = stats["fact_types"]
    lines += [f"{stats['object_types']['entity']:,} concepts, {facts['entity_relationships']:,} relationships between concepts, "
              f"{facts['scalar_properties']:,} scalar properties, {facts['flags']:,} flags.",
              f"Value types: {stats['object_types']['value']:,}; n-ary fact types: {facts['n_ary']:,}.",
              f"Components: {len(stats['components'])}; isolated concepts: {len(stats['isolated_concepts'])}.",
              f"Source tables covered: {stats['sources']['tables_covered']}; columns bound: {stats['sources']['columns_bound']}; dropped: {stats['sources']['columns_dropped']}.",
              "", "## Constraints", "", "| Source | Status | Count |", "|---|---|---:|"]
    lines += [f"| {r['source']} | {r['status']} | {r['count']} |" for r in stats["constraints"]["by_source_and_status"]]
    lines += ["", "## Relationships per concept", "", "| Concept id | Name | Relationships |", "|---|---|---:|"]
    lines += [f"| {r['id']} | {r['name']} | {r['relationships']} |" for r in stats["relationships_per_concept"]]
    lines += ["", "## Components", "", "| Id | Size | Concepts | Source tables |", "|---|---:|---|---|"]
    lines += [f"| {c['id']} | {c['size']} | {', '.join(n['name'] for n in c['concepts'])} | {', '.join(c['tables'])} |" for c in stats["components"]]
    lines += ["", "Isolated concepts: " + (", ".join(n["name"] for n in stats["isolated_concepts"]) or "none") + ".",
              "Uncovered source tables: " + (", ".join(stats["sources"]["uncovered_tables"]) or "none recorded") + "."]
    if stats["sources"]["dropped_columns"]:
        lines += ["", "Dropped columns: " + ", ".join(c["table"] + "." + c["column"] for c in stats["sources"]["dropped_columns"]) + "."]
    v = stats["verification"]
    if v:
        lines += ["", "## Verification", "", "| Round | Repair passes | Holdout passes | Repairs | Regressions | Components | Isolated ids | Required gap ids |", "|---|---:|---:|---:|---:|---:|---|---|"]
        for r in v["rounds"]:
            c = r.get("connectivity")
            lines.append(f"| {r['round']} | {r['repair_pass']} | {r['holdout_pass']} | {r['repairs']} | {r['regressions']} | " +
                         (f"{c['components']} | {', '.join(c['isolated'])} | {', '.join(c['required_gaps'])} |" if c else "unknown | unknown | unknown |"))
        lines += ["", "Items by status: " + ", ".join(f"{k}={n}" for k, n in v["items_by_status"].items()) + ".",
                  f"Repair pass rate: {v['repair_pass_rate']}; holdout pass rate: {v['holdout_pass_rate']}.",
                  "Residual failures by class: " + ", ".join(f"{k}={n}" for k, n in v["residual_by_class"].items()) + "."]
    else:
        lines += ["", "Verification input absent; pass counts and rates are unknown."]
    lines += ["", "## Issues", ""]
    lines += [f"- **{i['id']}** ({i['severity']}, count {i['count']}): {i['next_action']}" +
              (f" Workload share never verified: {i['workload_share']:.1%}." if i.get("workload_share") is not None else "") for i in issues]
    if not issues:
        lines += ["No issues detected by these checks."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--verification")
    parser.add_argument("--connectivity")
    parser.add_argument("--digest")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()
    try:
        read_json = lambda p: json.loads(Path(p).read_text()) if p else None
        result = build_report(read_yaml(args.model), read_json(args.verification), read_json(args.connectivity),
                              read_yaml(args.digest) if args.digest else None,
                              Path(args.verification).parent if args.verification else Path(args.model).parent)
        target = Path(args.out_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "orm-report.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        (target / "orm-report.md").write_text(markdown(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        print("ORM report failed: check input structure and file access.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
