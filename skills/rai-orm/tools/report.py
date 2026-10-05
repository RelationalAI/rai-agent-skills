#!/usr/bin/env python3
"""Produce deterministic ORM statistics and actionable, count-only issues."""

import argparse
from collections import Counter
from collections.abc import Mapping
import json
from pathlib import Path
import sys

import yaml

# Shared static scanner; also consumed by rai-orm-refactor via its compatibility module.
from orm_usage import workload_support

from connectivity import analyze, bindings, read_yaml


STATUSES = ("pass", "fail", "unverified", "inexpressible", "oracle-error")


class ReportInputError(ValueError):
    """A schema path and fixed category, never an input value."""


def check_shape(value, schema, path):
    """Check consumed fields only; ! marks required keys, * map values."""
    expected = dict if isinstance(schema, dict) else list if isinstance(schema, list) else schema
    if not isinstance(value, expected) or (isinstance(value, bool) and expected == int):
        category = {dict: "mapping", list: "list", int: "integer", str: "string"}.get(expected, "number")
        raise ReportInputError(f"{path}: expected {category}")
    if isinstance(schema, dict):
        for field, child in schema.items():
            if field == "*":
                for item in value.values():
                    check_shape(item, child, f"{path}.*")
                continue
            key = field.rstrip("!")
            child_path = f"{path}.{key}" if path else key
            if key in value:
                check_shape(value[key], child, child_path)
            elif field.endswith("!"):
                raise ReportInputError(f"{child_path}: missing key")
    elif isinstance(schema, list):
        for index, item in enumerate(value):
            check_shape(item, schema[0], f"{path}[{index}]")


def check_inputs(verification, connectivity, digest, plan, compaction):
    # Round connectivity is optional evidence, normalized separately below.
    if verification is not None:
        check_shape(verification, {
            "workload": {"n_items": int}, "split": {"holdout": int},
            "items": [{"id!": str, "status": str, "class": str, "split": str, "pyrel": str}],
            "repairs": [{"round!": int}],
            "rounds": [{"round!": int, "repair_pass": int, "holdout_pass": int, "regressions": int}],
            "invocations": [{"rounds_run!": int}],
            "summary": {"excluded": {"inexpressible": int, "oracle-error": int},
                        "residual_by_class": {"*": int},
                        "repair_pass_rate": (int, float, type(None)),
                        "holdout_pass_rate": (int, float, type(None))}}, "")
        ids = [item["id"] for item in verification.get("items", [])]
        if len(set(ids)) != len(ids):
            raise ReportInputError("items: duplicate ids")
    if connectivity is not None:
        check_shape(connectivity, {
            "relationships_per_concept": [{"id!": str, "name!": str, "relationships!": int}],
            "components": [{"id!": str, "size!": int, "concepts!": [{"name!": str}], "tables!": [str]}],
            "isolated_concepts": [{"name!": str}], "required_gaps": list,
            "summary": {"candidates_untested": int, "required_gaps_untested": int,
                        "isolated_concepts_untested": int}}, "connectivity")
    if digest is not None:
        side = {"table!": str, "columns!": [str]}
        check_shape(digest, {"workload": {"n_items": int},
                            "join_edges": [{"id!": str, "left!": side, "right!": side}]}, "digest")
    if plan is not None:
        check_shape(plan, {"budget": {"refactor_rounds": int},
                          "rounds_used_by_skill_this_invocation": {"rai-orm-refactor": int}}, "plan")
    if compaction is not None:
        check_shape(compaction, {"suspects": list}, "compaction")


def round_connectivity(block):
    """Return normalized optional evidence and the number of skipped values."""
    if not isinstance(block, Mapping):
        return None, 1
    result, unparsed = {}, 0
    components = block.get("components", 0)
    if type(components) is not int:
        components, unparsed = 0, 1
    result["components"] = components
    for field in ("isolated", "required_gaps"):
        result[field] = []
        entries = block.get(field, [])
        if type(entries) is int:
            result[field + "_count"] = entries
            continue
        if not isinstance(entries, list):
            unparsed += 1
            continue
        for entry in entries:
            if isinstance(entry, Mapping):
                entry = entry.get("id", entry.get("name"))
            if isinstance(entry, str):
                result[field].append(entry)
            else:
                unparsed += 1
        result[field].sort()
    return result, unparsed


def build_report(model, verification=None, connectivity=None, digest=None, base_dir=".", plan=None, compaction=None):
    check_inputs(verification, connectivity, digest, plan, compaction)
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
        verification_total = verification.get("workload", {}).get("n_items", len(items))
        digest_total = (digest or {}).get("workload", {}).get("n_items")
        mismatch = verification_total != len(items) or (digest_total is not None and digest_total != verification_total)
        total = max(total, verification_total, len(items))
        if mismatch:
            issue("WORKLOAD_COUNT_MISMATCH", "blocker", total,
                  "Reconcile digest and verification item counts before reporting completion.",
                  digest_items=digest_total, verification_items=verification_total, recorded_items=len(items))
        unknown = sum(i.get("status", "unverified") not in STATUSES for i in items)
        counts = Counter(i.get("status", "unverified") if i.get("status", "unverified") in STATUSES else "unverified" for i in items)
        if unknown:
            issue("UNKNOWN_ITEM_STATUS", "warning", unknown,
                  "Resolve unknown item statuses; these items count as unverified.")
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
                c, unparsed = round_connectivity(r["connectivity"])
                if c is not None:
                    rounds[-1]["connectivity"] = c
                if unparsed:
                    stats["rounds_unparsed_connectivity"] = stats.get("rounds_unparsed_connectivity", 0) + unparsed
        repair_rate = summary.get("repair_pass_rate")
        holdout_rate = summary.get("holdout_pass_rate")
        def pass_rate(split):
            selected = [i for i in items if i.get("split") == split and i.get("status") not in {"inexpressible", "oracle-error"}]
            return sum(i.get("status") == "pass" for i in selected) / len(selected) if selected else None
        repair_rate = repair_rate if repair_rate is not None else pass_rate("repair")
        holdout_rate = holdout_rate if holdout_rate is not None else pass_rate("holdout")
        stop = summary.get("stopped_because")
        status = "budget-exhausted" if stop == "budget" and (residual or counts["unverified"]) else ("residual-failures" if residual else ("unverified" if counts["unverified"] else "all-pass"))
        if mismatch and status == "all-pass":
            status = "unverified"
        invocations = [{key: invocation.get(key) for key in ("started_round", "rounds_run", "stopped_because")}
                       for invocation in verification.get("invocations", [])]
        rounds_total = max(max((r["round"] for r in rounds), default=0),
                           sum(i["rounds_run"] for i in invocations))
        stats["verification"] = {"rounds": rounds, "invocations": invocations,
                                 "rounds_run_total": rounds_total,
                                 "rounds_run_this_invocation": invocations[-1]["rounds_run"] if invocations else None,
                                 "regressions": sum(r["regressions"] for r in rounds),
                                 "residual_failures": residual, "residual_by_class": dict(sorted(residual_by_class.items())),
                                 "items_by_status": {k: counts[k] for k in STATUSES},
                                 "repair_pass_rate": repair_rate, "holdout_pass_rate": holdout_rate}
        if stop == "budget" and (residual or counts["unverified"]):
            issue("BUDGET_EXHAUSTED", "blocker", residual,
                  "Resume rai-orm at Step 0 with orm-state.json and model.verification.json; run state.py plan for a fresh invocation budget.", unverified_items=counts["unverified"])
        if stop == "plateau" or (not invocations and len(rounds) >= 3 and rounds[-1]["repair_pass"] <= rounds[-2]["repair_pass"] <= rounds[-3]["repair_pass"] and residual):
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
        entities = {o["id"]: o for o in model.get("object_types", []) if o["kind"] == "entity"}
        coverage, support = workload_support(entities, verification, base_dir, digest)
        if support is not None:
            singletons = sorted(k for k, v in support.items() if len(v) == 1)
            if singletons:
                issue("SINGLE_ITEM_CONCEPTS", "warning", len(singletons),
                      "Review these concepts for query-shaped modeling against the schema and domain vocabulary.", concept_ids=singletons,
                      coverage=coverage["status"], lower_bound=coverage["status"] != "complete")
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
        priority_counts = "; ".join(
            f"{label}: {comparison_summary[key]}" if key in comparison_summary else f"{label}: counts unavailable"
            for key, label in (("required_gaps_untested", "untested required gaps"),
                               ("isolated_concepts_untested", "untested isolated concepts")))
        issue("COMPARISON_CAP_REACHED", "warning", untested_links,
              f"Comparison cap reached; {untested_links} candidate links remain untested. "
              "Untested candidates are ranked after required-gap and isolated-concept pairs; "
              "raise --max-comparisons only if required gaps or isolated concepts are still untested. " + priority_counts)
    gaps = len(connectivity.get("required_gaps", []))
    if gaps:
        issue("REQUIRED_JOIN_GAPS", "blocker", gaps, "Classify as missing-element at rai-orm-verify Step 4 and add proposed links with overlap evidence at Step 5.")
        if status == "all-pass":
            status = "required-gaps"
    if dropped:
        issue("DROPPED_COLUMNS", "warning", len(dropped), "Bind dropped source columns or record their justification in ontology-notes.md.")
    if verification is None:
        stats["verification"] = None
    if plan is not None:
        used = plan.get("rounds_used_by_skill_this_invocation", {}).get("rai-orm-refactor", 0)
        allowance = plan.get("budget", {}).get("refactor_rounds", 2)
        current = bool(compaction and plan.get("baseline_model_revision")
                       and compaction.get("model_revision") == plan["baseline_model_revision"])
        suspects = compaction.get("suspects", []) if current else None
        if not current:
            issue("REFACTOR_ASSESSMENT_REQUIRED", "blocker", 1,
                  "Refactor work is unknown: run rai-orm-refactor assessment for the current model revision.")
            if status == "all-pass":
                status = "verified-refactor-unknown"
        if used >= allowance and (suspects is None or suspects):
            issue("REFACTOR_BUDGET_EXHAUSTED", "blocker", len(suspects) if suspects is not None else None,
                  "Resume rai-orm with a fresh refactor allowance and review remaining compaction suspects.")
            if status == "all-pass":
                status = "verified-refactor-incomplete"
    return {"version": 1, "status": status, "statistics": stats,
            "issues": sorted(issues, key=lambda i: (i["id"] != "REFACTOR_BUDGET_EXHAUSTED", i["id"] != "BUDGET_EXHAUSTED", {"blocker": 0, "warning": 1, "info": 2}[i["severity"]], i["id"]))}


def markdown(report):
    issues = report["issues"]
    budget = next((i for i in issues if i["id"] == "BUDGET_EXHAUSTED"), None)
    lines = ([f"BUDGET_EXHAUSTED: {budget['count']} residual failures. Continue: {budget['next_action']}" +
              (f" Unverified items: {budget['unverified_items']}." if budget.get("unverified_items") else ""), ""] if budget else [])
    refactor = next((i for i in issues if i["id"] == "REFACTOR_BUDGET_EXHAUSTED"), None)
    refactor_unknown = any(i["id"] == "REFACTOR_ASSESSMENT_REQUIRED" for i in issues)
    if refactor:
        remaining = "unknown" if refactor_unknown else refactor["count"]
        lines.insert(0, f"REFACTOR_BUDGET_EXHAUSTED: {remaining} remaining suspects. Continue: {refactor['next_action']}")
    lines += ["# ORM statistics and issues", "", f"Status: {report['status']}", ""]
    stats = report["statistics"]
    if refactor or refactor_unknown:
        v = stats["verification"]
        coverage = (f"{v['items_by_status']['pass']} passed; {v['residual_failures']} residual failures; "
                    f"{v['items_by_status']['unverified']} unverified." if v else "unknown.")
        lines += ["Verified workload coverage: " + coverage,
                  ("Refactor work: unknown; current assessment required." if refactor_unknown else
                   f"Refactor work: incomplete; {refactor['count']} remaining suspects."), ""]
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
        latest = v["rounds_run_this_invocation"]
        lines += ["", "## Verification", "",
                  f"Rounds run in total: {v['rounds_run_total']}; this invocation: {latest if latest is not None else 'unknown (legacy report)'}.",
                  "", "| Round | Repair passes | Holdout passes | Repairs | Regressions | Components | Isolated ids | Required gap ids |", "|---|---:|---:|---:|---:|---:|---|---|"]
        for r in v["rounds"]:
            c = r.get("connectivity")
            def entries(field):
                return f"{c[field + '_count']} (count)" if field + "_count" in c else ", ".join(c[field])
            lines.append(f"| {r['round']} | {r['repair_pass']} | {r['holdout_pass']} | {r['repairs']} | {r['regressions']} | " +
                         (f"{c['components']} | {entries('isolated')} | {entries('required_gaps')} |" if c else "unknown | unknown | unknown |"))
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


def read_input(path, key, yaml_input=False):
    if path is None:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
        value = yaml.safe_load(text) if yaml_input else json.loads(text)
    except UnicodeError:
        raise ReportInputError(f"{key}: invalid encoding") from None
    except OSError:
        raise ReportInputError(f"{key}: file access") from None
    except (ValueError, yaml.YAMLError):
        raise ReportInputError(f"{key}: invalid syntax") from None
    check_shape(value, dict, key)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--verification")
    parser.add_argument("--connectivity")
    parser.add_argument("--digest")
    parser.add_argument("--plan", help="JSON from state.py plan; reads compaction.after.json beside the model")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args()
    path = "model"
    try:
        metrics = Path(args.model).parent / "compaction.after.json"
        result = build_report(read_yaml(args.model), read_input(args.verification, "verification"),
                              read_input(args.connectivity, "connectivity"), read_input(args.digest, "digest", True),
                              Path(args.verification).parent if args.verification else Path(args.model).parent,
                              plan=read_input(args.plan, "plan"),
                              compaction=read_input(metrics, "compaction") if args.plan and metrics.is_file() else None)
        path = "out_dir"
        target = Path(args.out_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "orm-report.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (target / "orm-report.md").write_text(markdown(result), encoding="utf-8")
        return 0
    except ReportInputError as error:
        print(f"ORM report failed: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError) as error:
        category = ("file access" if isinstance(error, OSError) else
                    "missing key" if isinstance(error, KeyError) else "invalid structure")
        print(f"ORM report failed: {path}: {category}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
