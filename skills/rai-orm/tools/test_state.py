"""Determinism, workload deltas, privacy and persisted resume guards."""

import json
from pathlib import Path

import pytest
import yaml

from state import ARTIFACT_DEFAULTS, feedback_items, file_hash, initialize, item_hashes, plan, update
from test_resume_flow import cli, project_files


def initialized(project, **kwargs):
    project_files(project)
    return initialize(project, dict(ARTIFACT_DEFAULTS), emitter="python emit.py", **kwargs)


def test_init_records_paths_history_and_hashes(tmp_path):
    (tmp_path / "schema.sql").write_text("-- PRIVATE_SCHEMA_SENTINEL\n")
    (tmp_path / "items.json").write_text(json.dumps([{"id": "q001", "sql": "SELECT 'PRIVATE_LITERAL_SENTINEL'"}]))
    state = initialized(tmp_path, inputs=["schema.sql"], workloads=["items.json"])
    assert state == initialize(tmp_path, dict(ARTIFACT_DEFAULTS), inputs=["schema.sql"], workloads=["items.json"], emitter="python emit.py")
    assert state["round_counters"]["rai-orm-verify"] == 5
    assert [step["skill"] for step in state["skills_run"]] == ["rai-orm-from-workload", "rai-orm-from-schema", "rai-orm-verify"]
    assert state["last_stop_reason"] == "budget"
    assert state["inputs"][0]["item_hashes"]["q001"].startswith("sha256:")
    assert "PRIVATE_" not in json.dumps(state)
    assert "generated_at" not in json.dumps(state)


@pytest.mark.parametrize("skill,accept_delta", [("connectivity", False), ("rai-orm-verify", False),
                                               ("rai-orm-from-workload", True)])
def test_update_records_missing_legacy_snapshot_hashes(tmp_path, skill, accept_delta):
    state = initialized(tmp_path)
    verification_path = tmp_path / "model.verification.json"
    original = verification_path.read_bytes()
    # Also cover upgrading a manifest whose snapshot predates saved hashes.
    for item in state["verification_snapshot"]["items"]:
        item.pop("pyrel_sha256", None)
    update(state, tmp_path, skill, accept_workload_delta=accept_delta)
    for item in state["verification_snapshot"]["items"]:
        if item["status"] == "pass":
            assert item["pyrel_sha256"] == file_hash(tmp_path / item["pyrel"])
    assert verification_path.read_bytes() == original
    assert plan(state, tmp_path)["can_resume"]


@pytest.mark.parametrize("damage", [None, "stale_at_init", "stale_after_init", "edit_and_rehash"])
def test_declared_pyrel_hash_and_snapshot_guards(tmp_path, damage):
    project_files(tmp_path)
    verification_path = tmp_path / "model.verification.json"
    verification = json.loads(verification_path.read_text())
    rewrite = tmp_path / "verification/q001.py"
    original_hash = file_hash(rewrite)
    verification["items"][0]["pyrel_sha256"] = "sha256:stale" if damage == "stale_at_init" else original_hash
    verification_path.write_text(json.dumps(verification))
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    if damage == "stale_after_init":
        verification["items"][0]["pyrel_sha256"] = "sha256:stale"
    elif damage == "edit_and_rehash":
        rewrite.write_text("result = Beta\n")
        verification["items"][0]["pyrel_sha256"] = file_hash(rewrite)
    verification_path.write_text(json.dumps(verification))
    result = plan(state, tmp_path)
    assert result["can_resume"] == (damage is None)
    assert result["blockers"] == ([] if damage is None else [{"id": "PASSED_PYREL_CHANGED", "item_id": "q001"}])


def test_unrelated_update_preserves_legacy_file_baseline(tmp_path):
    state = initialized(tmp_path)
    original_hash = state["verification_snapshot"]["items"][0]["pyrel_sha256"]
    (tmp_path / "verification/q001.py").write_text("result = Beta\n")
    update(state, tmp_path, "connectivity")
    assert state["verification_snapshot"]["items"][0]["pyrel_sha256"] == original_hash
    assert plan(state, tmp_path)["blockers"] == [{"id": "PASSED_PYREL_CHANGED", "item_id": "q001"}]


def test_workload_delta_preserves_surviving_passes(tmp_path):
    workload = tmp_path / "items.json"
    workload.write_text(json.dumps([{"id": f"q{i:03d}", "sql": f"SELECT {i}"} for i in range(1, 6)]))
    state = initialized(tmp_path, workloads=["items.json"])
    workload.write_text(json.dumps([{"id": "q001", "sql": "SELECT 1"}, {"id": "q003", "sql": "SELECT 8"},
                                    {"id": "q004", "sql": "SELECT 4"}, {"id": "q005", "sql": "SELECT 5"},
                                    {"id": "q006", "sql": "SELECT 6"}]))
    result = plan(state, tmp_path)
    assert result["workload_delta"] == {"changed_inputs": ["items.json"], "new_item_ids": ["q006"],
                                       "removed_item_ids": ["q002"], "changed_item_ids": ["q003"],
                                       "redigest_item_ids": ["q003", "q006"]}
    assert result["frozen_passed_items"] == ["q001"]
    assert result["steps"][0] == "rai-orm-from-workload"
    assert not result["can_resume"]
    verification_path = tmp_path / "model.verification.json"
    verification = json.loads(verification_path.read_text())
    verification["items"] = [item for item in verification["items"] if item["id"] != "q002"]
    verification["items"][1]["status"] = "fail"  # Changed q003 no longer claims its old pass.
    verification["items"].append({"id": "q006", "status": "fail", "split": "repair"})
    verification_path.write_text(json.dumps(verification))
    update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    accepted = plan(state, tmp_path)
    assert accepted["workload_delta"]["changed_inputs"] == []
    assert accepted["frozen_passed_items"] == ["q001"]
    assert accepted["can_resume"]


def test_processed_feedback_deduplicates_items_and_markdown(tmp_path):
    state = initialized(tmp_path)
    (tmp_path / "feedback.md").write_text("PRIVATE_QUESTION_SENTINEL")
    result = plan(state, tmp_path)
    assert "FEEDBACK_NEEDS_STRUCTURE" in {b["id"] for b in result["blockers"]}
    assert "PRIVATE_" not in json.dumps(result)
    update(state, tmp_path, "feedback", feedback=["feedback.yaml", "feedback.md"])
    assert plan(state, tmp_path)["new_feedback_items"] == []
    value = yaml.safe_load((tmp_path / "feedback.yaml").read_text())
    value["items"].append({"id": "f02", "kind": "note", "text": "PRIVATE_SQL_LITERAL_SENTINEL"})
    (tmp_path / "feedback.yaml").write_text(yaml.safe_dump(value))
    result = plan(state, tmp_path)
    assert [item["id"] for item in result["new_feedback_items"]] == ["f02"]
    assert "PRIVATE_" not in json.dumps(result) + json.dumps(state)


def test_update_keeps_order_and_advances_counter(tmp_path):
    state = initialized(tmp_path)
    verification = json.loads((tmp_path / "model.verification.json").read_text())
    verification["rounds"].append({"round": 6, "repair_pass": 3, "holdout_pass": 1})
    (tmp_path / "model.verification.json").write_text(json.dumps(verification))
    update(state, tmp_path, "rai-orm-verify", rounds_done=1, stop_reason="plateau", rounds_per_invocation=3,
           patience=4, until_pass=True)
    assert state["round_counters"]["rai-orm-verify"] == 6
    assert state["skills_run"][-1]["rounds_done"] == 1
    assert state["last_stop_reason"] == "plateau"
    assert plan(state, tmp_path)["started_round"] == 7
    assert state["budget"] == {"rounds_per_invocation": 3, "patience": 4, "until_pass": True}


@pytest.mark.parametrize("damage,blocker", [("split", "SPLIT_CHANGED"), ("item_split", "ITEM_SPLIT_CHANGED"),
                                           ("oracle", "ORACLE_CHANGED"), ("pass", "BASELINE_PASS_LOST"),
                                           ("rewrite", "PASSED_PYREL_MISSING"), ("rewrite_changed", "PASSED_PYREL_CHANGED")])
def test_resume_guards(tmp_path, damage, blocker):
    state = initialized(tmp_path)
    path = tmp_path / "model.verification.json"
    value = json.loads(path.read_text())
    if damage == "split":
        value["split"]["holdout"] = 0
    elif damage == "item_split":
        value["items"][4]["split"] = "holdout"
    elif damage == "oracle":
        value["oracle"] = "user-review"
    elif damage == "pass":
        value["items"][0]["status"] = "fail"
    elif damage == "rewrite":
        (tmp_path / "verification/q001.py").unlink()
    else:
        (tmp_path / "verification/q001.py").write_text("result = Beta\n")
    path.write_text(json.dumps(value))
    assert blocker in {b["id"] for b in plan(state, tmp_path)["blockers"]}


def test_pyrel_only_bootstrap_does_not_import(tmp_path):
    (tmp_path / "model.py").write_text("raise RuntimeError('PRIVATE_SENTINEL')\n")
    result = cli(tmp_path, "plan")
    assert result.returncode == 0
    assert "YAML_REQUIRED" in {b["id"] for b in json.loads(result.stdout)["blockers"]}
    assert not (tmp_path / "orm-state.json").exists()
    assert "PRIVATE_" not in result.stdout + result.stderr


def test_invalid_inputs_never_echo_parser_errors(tmp_path):
    (tmp_path / "orm-state.json").write_text("{PRIVATE_SENTINEL")
    result = cli(tmp_path, "plan")
    assert result.returncode == 1
    assert json.loads(result.stderr) == {"error": "STATE_INPUT_INVALID"}
    assert "PRIVATE_" not in result.stdout + result.stderr


@pytest.mark.parametrize("row", [
    {"kind": "wrong_grain", "concept": "Alpha"}, {"kind": "merge", "concepts": ["Alpha", "Beta"]},
    {"kind": "split", "concept": "Alpha"}, {"kind": "rename", "from": "Alpha", "to": "Gamma"},
    {"kind": "failing_item", "ids": ["q005", "q004"]}, {"kind": "compact", "concept": "Alpha"},
    {"kind": "note", "text": "PRIVATE_SENTINEL"},
])
def test_feedback_kinds(tmp_path, row):
    path = tmp_path / "feedback.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "items": [row]}))
    result = feedback_items(path)
    assert result[0]["kind"] == row["kind"] and result[0]["source"] == "user-feedback"
    assert "PRIVATE_" not in json.dumps(result)


def test_duplicate_item_ids_are_blocked(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(json.dumps([{"id": "q1", "sql": "SELECT 1"}] * 2))
    with pytest.raises(ValueError):
        item_hashes(path)


def test_sql_and_text_positional_ids(tmp_path):
    path = tmp_path / "items.sql"
    path.write_text("SELECT ';'; -- comment\n SELECT 2; /* only a comment */")
    assert list(item_hashes(path)) == ["i0001", "i0002"]
    path = tmp_path / "items.txt"
    path.write_text("PRIVATE_QUESTION\n\nPRIVATE_QUESTION_2\n")
    assert list(item_hashes(path)) == ["i0001", "i0002"]


def test_init_does_not_overwrite_existing_state(tmp_path):
    initialized(tmp_path)
    assert cli(tmp_path, "init", "--emitter", "python emit.py").returncode == 0
    before = (tmp_path / "orm-state.json").read_bytes()
    assert cli(tmp_path, "init").returncode == 1
    assert before == (tmp_path / "orm-state.json").read_bytes()


def test_step_update_does_not_hide_unverified_model_revision(tmp_path):
    state = initialized(tmp_path)
    (tmp_path / "model.py").write_text("# Candidate generated by emitter\n")
    update(state, tmp_path, "connectivity", stop_reason="connected")
    result = plan(state, tmp_path)
    assert result["baseline_recheck"]
    assert "rai-orm-verify" in result["steps"]


def test_yaml_mode_is_inherited_on_bootstrap(tmp_path):
    project_files(tmp_path)
    model_path = tmp_path / "model.orm.yaml"
    model = yaml.safe_load(model_path.read_text())
    model["source"]["mode"] = "one-shot"
    model_path.write_text(yaml.safe_dump(model))
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    assert state["mode"] == "one-shot"


def test_no_workload_does_not_schedule_verification(tmp_path):
    project_files(tmp_path)
    (tmp_path / "model.verification.json").unlink()
    (tmp_path / "workload.digest.yaml").unlink()
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    assert plan(state, tmp_path)["steps"] == ["connectivity", "rai-orm-refactor", "report"]


def test_missing_split_assignments_block_legacy_resume(tmp_path):
    project_files(tmp_path)
    path = tmp_path / "model.verification.json"
    verification = json.loads(path.read_text())
    verification["items"][4].pop("split")
    path.write_text(json.dumps(verification))
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    assert "SPLIT_ASSIGNMENTS_REQUIRED" in {b["id"] for b in plan(state, tmp_path)["blockers"]}


def test_current_all_pass_project_has_no_unnecessary_steps(tmp_path):
    project_files(tmp_path)
    path = tmp_path / "model.verification.json"
    verification = json.loads(path.read_text())
    verification["items"] = verification["items"][:3]
    verification["split"] = {"repair": 2, "holdout": 1}
    verification["summary"]["stopped_because"] = "all-pass"
    path.write_text(json.dumps(verification))
    (tmp_path / "feedback.yaml").unlink()
    (tmp_path / "connectivity.json").write_text(json.dumps({"verdict": "connected"}))
    (tmp_path / "compaction.after.json").write_text("{}")
    (tmp_path / "orm-report.json").write_text(json.dumps({"status": "all-pass"}))
    (tmp_path / "orm-report.md").write_text("# Synthetic report\n")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    assert plan(state, tmp_path)["steps"] == []
    (tmp_path / "connectivity.json").write_text(json.dumps({"verdict": "islands"}))
    result = plan(state, tmp_path)
    assert result["steps"] == ["report"]
    assert result["stale_artifacts"] == ["connectivity"]


def test_explicit_numeric_workload_ids(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(json.dumps([{"id": 17, "sql": "SELECT 1"}]))
    assert list(item_hashes(path)) == ["17"]


def test_lost_digest_blocks_resume(tmp_path):
    state = initialized(tmp_path)
    (tmp_path / "workload.digest.yaml").unlink()
    assert "DIGEST_REQUIRED" in {b["id"] for b in plan(state, tmp_path)["blockers"]}


def test_step_metadata_cannot_echo_free_text(tmp_path):
    state = initialized(tmp_path)
    with pytest.raises(ValueError):
        update(state, tmp_path, "rai-orm-verify", stop_reason="SELECT 'PRIVATE_SENTINEL'")
