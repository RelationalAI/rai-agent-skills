"""Synthetic report stop conditions, statistics, privacy, and CLI checks."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from report import build_report, markdown


TOOL = Path(__file__).with_name("report.py")
MODEL = {"object_types": [{"id": "alpha", "name": "Alpha", "kind": "entity", "provenance": {"table": "ALPHA_FEED", "pk_column": "id"}},
                          {"id": "text", "name": "Text", "kind": "value", "primitive": "String"}],
         "fact_types": [{"id": "label", "roles": [{"object_type": "alpha"}, {"object_type": "text"}],
                         "constraints": [{"type": "uniqueness", "source": "explicit", "status": "confirmed"}]}],
         "source_bindings": [{"table": "ALPHA_FEED", "object_type": "alpha", "columns": ["label"], "dropped_columns": ["unused"]}]}


def verification(stop="budget"):
    return {"workload": {"n_items": 4}, "split": {"repair": 3, "holdout": 1},
            "rounds": [{"round": i, "repair_pass": 1, "holdout_pass": 0, "regressions": int(i == 1)} for i in range(3)],
            "repairs": [{"round": 1, "class": "missing-element"}],
            "items": [{"id": "q1", "split": "repair", "status": "pass"},
                      {"id": "q2", "split": "repair", "status": "fail", "class": "missing-element"},
                      {"id": "q3", "split": "repair", "status": "oracle-error"}],
            "summary": {"stopped_because": stop, "repair_pass_rate": 0.5, "holdout_pass_rate": 0.0,
                        "residual_by_class": {"missing-element": 1}}}


def test_budget_exhausted_leads_and_never_claims_done():
    result = build_report(MODEL, verification())
    text = markdown(result)
    assert text.splitlines()[0].startswith("BUDGET_EXHAUSTED: 1 residual failures. Continue: Resume rai-orm at Step 0")
    assert result["status"] == "budget-exhausted"
    assert result["issues"][0]["id"] == "BUDGET_EXHAUSTED"
    assert result["issues"][0]["severity"] == "blocker"
    assert "all-pass" not in json.dumps(result) and "all pass" not in text.lower() and "done" not in text.lower()
    ids = {i["id"] for i in result["issues"]}
    assert {"PLATEAU", "UNVERIFIED_ITEMS", "HOLDOUT_GAP", "ORACLE_ERRORS", "REGRESSIONS", "DROPPED_COLUMNS"} <= ids
    assert result["statistics"]["verification"]["rounds"][1]["repairs"] == 1
    assert result["statistics"]["verification"]["items_by_status"]["unverified"] == 1


def test_plateau():
    result = build_report(MODEL, verification("plateau"))
    assert "PLATEAU" in {i["id"] for i in result["issues"]}
    assert "BUDGET_EXHAUSTED" not in markdown(result)
    assert result["status"] == "residual-failures"


def test_all_pass():
    v = {"workload": {"n_items": 1}, "items": [{"id": "q1", "status": "pass", "split": "repair"}],
         "summary": {"stopped_because": "all-pass", "residual_by_class": {}}}
    result = build_report(MODEL, v)
    assert result["status"] == "all-pass"
    assert not any(i["id"] in {"BUDGET_EXHAUSTED", "PLATEAU", "UNVERIFIED_ITEMS"} for i in result["issues"])


def test_missing_optional_inputs_and_stats():
    result = build_report(MODEL)
    stats = result["statistics"]
    assert result["status"] == "unverified" and stats["verification"] is None
    assert stats["object_types"] == {"entity": 1, "value": 1}
    assert stats["fact_types"]["scalar_properties"] == 1
    assert stats["fact_types_total_binary"] == 1
    assert stats["constraints"]["by_source"] == {"explicit": 1}
    assert stats["sources"]["columns_bound"] == 2
    assert "Verification input absent" in markdown(result)
    result = build_report(MODEL, digest={"workload": {"n_items": 10}})
    issue = next(i for i in result["issues"] if i["id"] == "UNVERIFIED_ITEMS")
    assert issue["count"] == 10 and issue["workload_share"] == 1.0


def test_saved_pyrel_singletons_only_and_privacy(tmp_path):
    v = verification()
    assert "SINGLE_ITEM_CONCEPTS" not in {i["id"] for i in build_report(MODEL, v)["issues"]}
    (tmp_path / "q1.py").write_text('from model import Alpha as A\nresult = A\nsecret = "PRIVATE_DATA_SENTINEL"\n')
    v["items"][0]["pyrel"] = "q1.py"
    v["items"][0]["question"] = "PRIVATE_QUESTION_SENTINEL"
    v["repairs"][0]["change"] = "PRIVATE_SQL_LITERAL_SENTINEL"
    result = build_report(MODEL, v, base_dir=tmp_path)
    issue = next(i for i in result["issues"] if i["id"] == "SINGLE_ITEM_CONCEPTS")
    assert issue["concept_ids"] == ["alpha"]
    assert "PRIVATE_" not in json.dumps(result) + markdown(result)
    (tmp_path / "q1.py").unlink()
    assert "SINGLE_ITEM_CONCEPTS" not in {i["id"] for i in build_report(MODEL, v, base_dir=tmp_path)["issues"]}


def test_connectivity_issues_and_inexpressible():
    v = verification()
    v["items"].append({"id": "q4", "status": "inexpressible"})
    c = {"components": [{"id": "component_1", "size": 1, "concepts": [{"id": "alpha", "name": "Alpha"}], "tables": ["ALPHA_FEED"]},
                        {"id": "component_2", "size": 1, "concepts": [{"id": "beta", "name": "Beta"}], "tables": ["BETA_FEED"]}],
         "isolated_concepts": [{"id": "alpha", "name": "Alpha"}], "required_gaps": [{"id": "je1"}]}
    result = build_report(MODEL, v, c)
    assert {"ISLANDS", "ISOLATED_CONCEPTS", "REQUIRED_JOIN_GAPS", "INEXPRESSIBLE_ITEMS"} <= {i["id"] for i in result["issues"]}


def test_determinism_cli(tmp_path):
    model_path, verification_path = tmp_path / "model.orm.yaml", tmp_path / "model.verification.json"
    model_path.write_text(yaml.safe_dump(MODEL))
    verification_path.write_text(json.dumps(verification()))
    args = [sys.executable, str(TOOL), "--model", str(model_path), "--verification", str(verification_path), "--out-dir", str(tmp_path)]
    result = subprocess.run(args, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    first = [(tmp_path / f).read_bytes() for f in ("orm-report.json", "orm-report.md")]
    assert subprocess.run(args, capture_output=True).returncode == 0
    assert first == [(tmp_path / f).read_bytes() for f in ("orm-report.json", "orm-report.md")]
    assert (tmp_path / "orm-report.md").read_text().startswith("BUDGET_EXHAUSTED")


def test_budget_residual_without_summary_and_holdout_threshold():
    v = verification()
    v["summary"]["residual_by_class"] = {}
    v["summary"]["holdout_pass_rate"] = 0.35
    result = build_report(MODEL, v)
    assert result["status"] == "budget-exhausted"
    assert "HOLDOUT_GAP" not in {i["id"] for i in result["issues"]}


def test_digest_without_connectivity_and_round_connectivity():
    digest = {"join_edges": [{"id": "je_missing", "left": {"table": "ALPHA_FEED", "columns": ["id"]},
                              "right": {"table": "BETA_FEED", "columns": ["id"]}, "support": 2}]}
    v = verification()
    v["rounds"][0]["connectivity"] = {"components": 2, "isolated": ["alpha"], "required_gaps": ["je_missing"]}
    result = build_report(MODEL, v, digest=digest)
    assert "REQUIRED_JOIN_GAPS" in {i["id"] for i in result["issues"]}
    assert result["statistics"]["verification"]["rounds"][0]["connectivity"] == v["rounds"][0]["connectivity"]
    assert "je_missing" in markdown(result)


def test_applied_link_binds_both_column_tuples():
    model = {**MODEL, "fact_types": MODEL["fact_types"] + [
        {"id": "data_link", "source": "data", "status": "proposed",
         "roles": [{"object_type": "alpha"}, {"object_type": "alpha"}],
         "provenance": {"left": {"table": "ALPHA_FEED", "columns": ["new_key"]},
                        "right": {"table": "ALPHA_ARCHIVE", "columns": ["new_key"]}}}]}
    stats = build_report(model)["statistics"]["sources"]
    assert stats["columns_bound"] == 4 and stats["tables_covered"] == 2


def test_comparison_cap_warning():
    c = {"summary": {"comparison_cap_reached": True, "candidates_untested": 17}}
    result = build_report(MODEL, connectivity=c)
    issue = next(i for i in result["issues"] if i["id"] == "COMPARISON_CAP_REACHED")
    assert issue["severity"] == "warning" and issue["count"] == 17
    assert "raise --max-comparisons only if required gaps or isolated concepts are still untested" in issue["next_action"]
    assert "counts unavailable" in issue["next_action"]
    assert issue["next_action"] in markdown(result)
    c["summary"]["comparison_cap_reached"] = False
    assert "COMPARISON_CAP_REACHED" not in {i["id"] for i in build_report(MODEL, connectivity=c)["issues"]}


def test_fact_categories_and_business_headline():
    model = {**MODEL, "object_types": MODEL["object_types"] + [{"id": "beta", "name": "Beta", "kind": "entity"}],
             "fact_types": MODEL["fact_types"] + [
                 {"id": "relationship", "roles": [{"object_type": "alpha"}, {"object_type": "beta"}]},
                 {"id": "self", "arity": 2, "roles": [{"object_type": "alpha"}, {"object_type": "alpha"}]},
                 {"id": "flag", "roles": [{"object_type": "alpha"}]},
                 {"id": "nary", "roles": [{"object_type": n} for n in ("alpha", "beta", "text")]}]}
    result = build_report(model)
    stats = result["statistics"]
    assert stats["fact_types"] == {"entity_relationships": 2, "scalar_properties": 1, "flags": 1, "n_ary": 1}
    assert stats["fact_types_total_binary"] == 3
    assert stats["fact_types_total_unary"] == stats["fact_types_total_n_ary"] == 1
    text = markdown(result)
    assert "2 concepts, 2 relationships between concepts, 1 scalar properties, 1 flags." in text
    assert "n-ary fact types: 1" in text and "Fact types:" not in text
    stats["fact_types"]["scalar_properties"] = 1945
    assert "1,945 scalar properties" in markdown(result)


def test_resumed_round_accounting_and_privacy():
    v = verification()
    v["rounds"].extend({"round": i, "repair_pass": 1, "holdout_pass": 0} for i in range(3, 8))
    v["invocations"] = [{"started_round": 1, "rounds_run": 5, "stopped_because": "budget"},
                        {"started_round": 6, "rounds_run": 2, "stopped_because": "plateau",
                         "question": "PRIVATE_SENTINEL"}]
    result = build_report(MODEL, v)
    stats = result["statistics"]["verification"]
    assert stats["rounds_run_total"] == 7
    assert stats["rounds_run_this_invocation"] == 2
    assert "Rounds run in total: 7; this invocation: 2." in markdown(result)
    assert "PRIVATE_" not in json.dumps(result) + markdown(result)


def test_legacy_rounds_exclude_baseline():
    result = build_report(MODEL, verification())
    assert result["statistics"]["verification"]["rounds_run_total"] == 2
    assert result["statistics"]["verification"]["rounds_run_this_invocation"] is None
    assert "unknown (legacy report)" in markdown(result)


def test_unreviewed_items_keep_invocation_budget_stop_prominent():
    v = {"workload": {"n_items": 1}, "items": [{"id": "q1", "status": "unverified", "split": "repair"}],
         "invocations": [{"started_round": 1, "rounds_run": 5, "stopped_because": "budget"}],
         "summary": {"stopped_because": "budget", "residual_by_class": {}}}
    result = build_report(MODEL, v)
    assert result["status"] == "budget-exhausted"
    first_line = markdown(result).splitlines()[0]
    assert first_line.startswith("BUDGET_EXHAUSTED: 0 residual failures.")
    assert "Unverified items: 1." in first_line
    assert result["issues"][0]["unverified_items"] == 1


def test_patience_is_not_inferred_across_invocations():
    v = verification()
    v["invocations"] = [{"started_round": 1, "rounds_run": 1, "stopped_because": "budget"},
                        {"started_round": 2, "rounds_run": 1, "stopped_because": "budget"}]
    assert "PLATEAU" not in {i["id"] for i in build_report(MODEL, v)["issues"]}


def test_in_progress_invocation():
    v = verification()
    v["invocations"] = [{"started_round": 1, "rounds_run": 2}]
    result = build_report(MODEL, v)
    assert result["statistics"]["verification"]["invocations"][0]["stopped_because"] is None


def test_unknown_status_is_unverified_and_private():
    v = {"items": [{"id": "a", "status": "PRIVATE_UNKNOWN"}]}
    result = build_report(MODEL, v)
    assert result["status"] == "unverified"
    assert result["statistics"]["verification"]["items_by_status"]["unverified"] == 1
    assert any(i["id"] == "UNKNOWN_ITEM_STATUS" for i in result["issues"])
    assert "PRIVATE_UNKNOWN" not in json.dumps(result)


@pytest.mark.parametrize("digest_count,verification_count,missing", [(3, 1, 2), (1, 3, 0)])
def test_count_mismatch_never_all_pass(digest_count, verification_count, missing):
    v = {"workload": {"n_items": verification_count},
         "items": [{"id": str(i), "status": "pass"} for i in range(verification_count)]}
    result = build_report(MODEL, v, digest={"workload": {"n_items": digest_count}})
    assert result["status"] == "unverified"
    assert result["statistics"]["verification"]["items_by_status"]["unverified"] == missing
    assert any(i["id"] == "WORKLOAD_COUNT_MISMATCH" for i in result["issues"])


def test_cap_priority_counts():
    result = build_report(MODEL, connectivity={"summary": {
        "comparison_cap_reached": True, "candidates_untested": 100,
        "required_gaps_untested": 2, "isolated_concepts_untested": 3}})
    action = next(i["next_action"] for i in result["issues"] if i["id"] == "COMPARISON_CAP_REACHED")
    assert "untested required gaps: 2" in action and "untested isolated concepts: 3" in action
    assert "counts unavailable" not in action


def test_report_and_metrics_share_partial_usage_scanner(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("compaction_metrics", TOOL.parents[2] / "rai-orm-refactor" / "tools" / "compaction_metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    measure = module.measure
    (tmp_path / "a.py").write_text('from model import Alpha as A\nresult = A\n', encoding="utf-8")
    (tmp_path / "bad.py").write_text('bad(\n', encoding="utf-8")
    v = {"items": [{"id": "a", "pyrel": "a.py"}, {"id": "b", "pyrel": "bad.py"}]}
    result = build_report(MODEL, v, base_dir=tmp_path)
    m = measure(MODEL, v, verification_dir=tmp_path)
    issue = next(i for i in result["issues"] if i["id"] == "SINGLE_ITEM_CONCEPTS")
    assert issue["concept_ids"] == m["single_item_concepts"] == ["alpha"]
    assert issue["coverage"] == m["support_coverage"]["status"] == "partial"


@pytest.mark.parametrize("used,allowance,suspects,exhausted", [(2, 2, 3, True), (3, 2, 1, True), (1, 2, 3, False), (2, 2, 0, False)])
def test_refactor_budget_exhaustion(used, allowance, suspects, exhausted):
    v = {"items": [{"id": "q", "status": "pass"}]}
    plan = {"budget": {"refactor_rounds": allowance}, "rounds_used_by_skill_this_invocation": {"rai-orm-refactor": used}}
    result = build_report(MODEL, v, plan=plan, compaction={"suspects": [{}] * suspects})
    text = markdown(result)
    assert result["status"] == ("verified-refactor-incomplete" if exhausted else "all-pass")
    issues = [i for i in result["issues"] if i["id"] == "REFACTOR_BUDGET_EXHAUSTED"]
    assert bool(issues) == exhausted
    if exhausted:
        assert issues[0]["severity"] == "blocker" and issues[0]["count"] == suspects
        assert text.splitlines()[0].startswith("REFACTOR_BUDGET_EXHAUSTED:")
        assert "Verified workload coverage: 1 passed; 0 residual failures; 0 unverified." in text
        assert f"Refactor work: incomplete; {suspects} remaining suspects." in text


def test_refactor_plan_cli_and_both_budgets(tmp_path):
    (tmp_path / "model.yaml").write_text(yaml.safe_dump(MODEL), encoding="utf-8")
    (tmp_path / "verification.json").write_text(json.dumps(verification()), encoding="utf-8")
    (tmp_path / "compaction.after.json").write_text(json.dumps({"suspects": [{"concept": "alpha"}]}), encoding="utf-8")
    (tmp_path / "plan.json").write_text(json.dumps({"budget": {"refactor_rounds": 1}, "rounds_used_by_skill_this_invocation": {"rai-orm-refactor": 1}}), encoding="utf-8")
    args = [sys.executable, str(TOOL), "--model", str(tmp_path / "model.yaml"), "--verification", str(tmp_path / "verification.json"),
            "--plan", str(tmp_path / "plan.json"), "--out-dir", str(tmp_path)]
    assert subprocess.run(args, capture_output=True).returncode == 0
    result = json.loads((tmp_path / "orm-report.json").read_text(encoding="utf-8"))
    assert result["status"] == "budget-exhausted"
    assert {"BUDGET_EXHAUSTED", "REFACTOR_BUDGET_EXHAUSTED"} <= {i["id"] for i in result["issues"]}
    assert (tmp_path / "orm-report.md").read_text(encoding="utf-8").startswith("REFACTOR_BUDGET_EXHAUSTED:")
