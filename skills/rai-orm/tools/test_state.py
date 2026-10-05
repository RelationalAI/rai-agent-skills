"""Determinism, workload deltas, privacy and persisted resume guards."""

import json
from pathlib import Path

import pytest
import yaml

from state import UpdateBlocked, revision, ARTIFACT_DEFAULTS, feedback_items, file_hash, initialize, item_hashes, plan, update
from test_resume_flow import cli, project_files


def initialized(project, **kwargs):
    project_files(project)
    return initialize(project, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10", **kwargs)


def test_init_records_paths_history_and_hashes(tmp_path):
    (tmp_path / "schema.sql").write_text("-- PRIVATE_SCHEMA_SENTINEL\n")
    (tmp_path / "items.json").write_text(json.dumps([{"id": f"q{i:03d}", "sql": "SELECT 'PRIVATE_LITERAL_SENTINEL'"} for i in range(1, 6)]))
    state = initialized(tmp_path, inputs=["schema.sql"], workloads=["items.json"])
    assert state == initialize(tmp_path, dict(ARTIFACT_DEFAULTS), inputs=["schema.sql"], workloads=["items.json"], emitter="manual:step-10")
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
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
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
    assert "rai-orm-from-workload" in result["steps"]
    assert not result["can_resume"]
    verification_path = tmp_path / "model.verification.json"
    verification = json.loads(verification_path.read_text())
    verification["items"] = [item for item in verification["items"] if item["id"] != "q002"]
    verification["items"][1]["status"] = "fail"  # Rechecked changed specification.
    verification["items"][1]["spec_hash"] = item_hashes(workload)["q003"]
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
    assert state["budget"] == {"rounds_per_invocation": 3, "patience": 4, "until_pass": True, "refactor_rounds": 2}


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
    assert cli(tmp_path, "init", "--emitter", "manual:step-10").returncode == 0
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
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert state["mode"] == "one-shot"


def test_no_workload_does_not_schedule_verification(tmp_path):
    project_files(tmp_path)
    (tmp_path / "model.verification.json").unlink()
    (tmp_path / "workload.digest.yaml").unlink()
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert plan(state, tmp_path)["steps"] == ["manual:step-10", "connectivity", "rai-orm-refactor:assess", "report"]


def test_missing_split_assignments_block_legacy_resume(tmp_path):
    project_files(tmp_path)
    path = tmp_path / "model.verification.json"
    verification = json.loads(path.read_text())
    verification["items"][4].pop("split")
    path.write_text(json.dumps(verification))
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert "SPLIT_ASSIGNMENTS_REQUIRED" in {b["id"] for b in plan(state, tmp_path)["blockers"]}


def test_current_all_pass_project_has_no_unnecessary_steps(tmp_path):
    project_files(tmp_path)
    path = tmp_path / "model.verification.json"
    verification = json.loads(path.read_text())
    verification["items"] = verification["items"][:3]
    verification["split"] = {"repair": 2, "holdout": 1}
    verification["summary"]["stopped_because"] = "all-pass"
    path.write_text(json.dumps(verification))
    (tmp_path / "workload.digest.yaml").write_text(yaml.safe_dump({"workload": {"n_items": 3}}))
    (tmp_path / "feedback.yaml").unlink()
    (tmp_path / "connectivity.json").write_text(json.dumps({"verdict": "connected"}))
    (tmp_path / "compaction.after.json").write_text(json.dumps({"model_revision": revision(tmp_path, ARTIFACT_DEFAULTS)}))
    (tmp_path / "orm-report.json").write_text(json.dumps({"status": "all-pass"}))
    (tmp_path / "orm-report.md").write_text("# Synthetic report\n")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert plan(state, tmp_path)["steps"] == ["manual:step-10", "report"]
    (tmp_path / "connectivity.json").write_text(json.dumps({"verdict": "islands"}))
    result = plan(state, tmp_path)
    assert result["steps"] == ["manual:step-10", "report"]
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


def codes(result):
    return {b["id"] for b in result["blockers"]}


def write_verification(project, edit):
    path = project / "model.verification.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    edit(value)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize("hand_edit", [False, True])
def test_legacy_requires_explicit_current_baseline(tmp_path, hand_edit):
    project_files(tmp_path)
    write_verification(tmp_path, lambda v: v.pop("model_revision"))
    if hand_edit:
        with (tmp_path / "model.orm.yaml").open("a", encoding="utf-8") as f:
            f.write("# hand edited\n")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert "BASELINE_RECHECK_REQUIRED" in codes(plan(state, tmp_path))
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")
    update(state, tmp_path, "connectivity")
    assert not plan(state, tmp_path)["can_resume"]
    write_verification(tmp_path, lambda v: v.update(model_revision=revision(tmp_path, ARTIFACT_DEFAULTS)))
    update(state, tmp_path, "rai-orm-verify")
    assert plan(state, tmp_path)["can_resume"]


def test_binding_invalidates_verification_across_updates(tmp_path):
    project_files(tmp_path)
    (tmp_path / "bindings.py").write_text("# original\n", encoding="utf-8")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10", bindings=["bindings.py"])
    write_verification(tmp_path, lambda v: v.update(model_revision=revision(tmp_path, ARTIFACT_DEFAULTS, state["bindings"])))
    update(state, tmp_path, "rai-orm-verify")
    assert plan(state, tmp_path)["can_resume"]
    (tmp_path / "bindings.py").write_text("# changed\n", encoding="utf-8")
    update(state, tmp_path, "connectivity")
    assert plan(state, tmp_path)["baseline_recheck"]
    assert "BASELINE_RECHECK_REQUIRED" in codes(plan(state, tmp_path))


@pytest.mark.parametrize("same_content", [False, True])
def test_current_rewrite_path_requires_verified_acceptance(tmp_path, same_content):
    state = initialized(tmp_path)
    other = tmp_path / "verification/other.py"
    other.write_text("result = Alpha\n" if same_content else "result = Beta\n", encoding="utf-8")
    write_verification(tmp_path, lambda v: v["items"][0].update(pyrel="verification/other.py"))
    assert "PASSED_PYREL_PATH_CHANGED" in codes(plan(state, tmp_path))
    if not same_content:
        assert "PASSED_PYREL_CHANGED" in codes(plan(state, tmp_path))
    before = json.dumps(state, sort_keys=True)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")
    assert json.dumps(state, sort_keys=True) == before
    write_verification(tmp_path, lambda v: [item.update(pyrel_sha256=file_hash(tmp_path / item["pyrel"]))
                                          for item in v["items"] if item.get("pyrel")])
    update(state, tmp_path, "rai-orm-verify", accept_pyrel_paths=True)
    assert plan(state, tmp_path)["can_resume"]


@pytest.mark.parametrize("damage,expected", [("added", "VERIFICATION_ITEMS_MISSING"),
                                           ("omitted", "VERIFICATION_ITEMS_MISSING"),
                                           ("duplicate", "DUPLICATE_VERIFICATION_ID"),
                                           ("removed", "VERIFICATION_ITEMS_REMOVED"),
                                           ("count", "WORKLOAD_COUNT_MISMATCH")])
def test_workload_reconciliation_blocks_update(tmp_path, damage, expected):
    rows = [{"id": f"q{i:03d}", "sql": f"SELECT {i}"} for i in range(1, 6)]
    workload = tmp_path / "items.json"
    workload.write_text(json.dumps(rows), encoding="utf-8")
    state = initialized(tmp_path, workloads=["items.json"])
    if damage == "added":
        workload.write_text(json.dumps(rows + [{"id": "q006", "sql": "SELECT 6"}]), encoding="utf-8")
    elif damage == "removed":
        workload.write_text(json.dumps(rows[:-1]), encoding="utf-8")
    elif damage == "omitted":
        write_verification(tmp_path, lambda v: v["items"].pop())
    elif damage == "duplicate":
        write_verification(tmp_path, lambda v: v["items"].append(v["items"][0]))
    else:
        write_verification(tmp_path, lambda v: v.update(workload={"n_items": 8}))
    result = plan(state, tmp_path)
    assert expected in codes(result)
    assert not result["can_resume"] and "rai-orm-verify" in result["steps"]
    if damage in {"added", "omitted"}:
        assert result["missing_item_ids"] == (["q006"] if damage == "added" else ["q005"])
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")


@pytest.mark.parametrize("text,field,index", [("{PRIVATE_SENTINEL", "document", None),
    ('{"version": 1, "items": [{"kind": "missing_link", "from": "Alpha"}]}', "to", 0),
    ('{"version": 1, "items": [{"kind": "failing_item", "ids": "q001"}]}', "ids", 0)])
def test_feedback_parse_failures_are_structured(tmp_path, text, field, index):
    state = initialized(tmp_path)
    (tmp_path / "feedback.yaml").write_text(text, encoding="utf-8")
    result = plan(state, tmp_path)
    assert {"id": "FEEDBACK_INVALID", "path": "feedback.yaml", "item_index": index, "field": field} in result["blockers"]
    assert "report" in result["steps"]
    assert "PRIVATE_SENTINEL" not in json.dumps(result)


def test_feedback_unknown_target_and_rename_destination(tmp_path):
    state = initialized(tmp_path)
    path = tmp_path / "feedback.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "items": [
        {"kind": "missing_link", "from": "Alpha", "to": "Unknown"},
        {"id": "rename", "kind": "rename", "from": "Alpha", "to": "NewName"}]}), encoding="utf-8")
    result = plan(state, tmp_path)
    assert "FEEDBACK_TARGET_UNKNOWN" in codes(result)
    assert [i["id"] for i in result["new_feedback_items"]] == ["rename"]


@pytest.mark.parametrize("malformed", ["{PRIVATE_SENTINEL", '[{"id":"q001"},{"id":"q001"}]'])
def test_workload_parse_failure_at_init_and_resume(tmp_path, malformed):
    path = tmp_path / "items.json"
    path.write_text(malformed, encoding="utf-8")
    state = initialized(tmp_path, workloads=["items.json"])
    assert {"id": "WORKLOAD_INVALID", "path": "items.json"} in plan(state, tmp_path)["blockers"]
    result = cli(tmp_path, "plan", "--workload", "items.json")
    assert result.returncode == 0
    assert "WORKLOAD_INVALID" in codes(json.loads(result.stdout))
    assert "PRIVATE_SENTINEL" not in result.stdout + result.stderr


def test_immutable_workload_and_legacy_subtraction_blocker(tmp_path):
    path = tmp_path / "items.json"
    rows = [{"id": f"q{i:03d}", "sql": f"SELECT {i}"} for i in range(1, 6)]
    original = json.dumps(rows)
    path.write_text(original, encoding="utf-8")
    state = initialized(tmp_path, workloads=["items.json"])
    record = state["inputs"][0]
    rows[-1]["sql"] = "SELECT 99"
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert (tmp_path / record["snapshot_path"]).read_text(encoding="utf-8") == original
    assert "WORKLOAD_FULL_REBUILD_REQUIRED" not in codes(plan(state, tmp_path))
    record.pop("snapshot_path")
    assert "WORKLOAD_FULL_REBUILD_REQUIRED" in codes(plan(state, tmp_path))
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    # Explicit full rebuild is accepted after digest/count/split reconciliation.
    update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True, full_rebuild=True)
    assert file_hash(tmp_path / state["inputs"][0]["snapshot_path"]) == file_hash(path)


def test_registered_old_contributions_support_changed_query(tmp_path):
    path = tmp_path / "items.json"
    rows = [{"id": f"q{i:03d}", "sql": f"SELECT {i}"} for i in range(1, 6)]
    path.write_text(json.dumps(rows), encoding="utf-8")
    project_files(tmp_path)
    digest = {"workload": {"n_items": 5}, "item_contributions": {"q005": {"joins": []}}}
    (tmp_path / "workload.digest.yaml").write_text(yaml.safe_dump(digest), encoding="utf-8")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10", workloads=["items.json"])
    record = state["inputs"][0]
    record.pop("snapshot_path")
    assert "item_contributions" not in record
    assert record["item_contribution_hashes"]["q005"].startswith("sha256:")
    rows[-1]["sql"] = "SELECT 99"
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert "WORKLOAD_FULL_REBUILD_REQUIRED" not in codes(plan(state, tmp_path))


def test_split_digest_artifacts_and_utf8_manifest(tmp_path):
    project_files(tmp_path)
    result = cli(tmp_path, "init", "--emitter", "manual:step-10", "--repair-digest", "réparation.yaml",
                 "--holdout-digest", "holdout.digest.yaml")
    assert result.returncode == 0
    state = json.loads((tmp_path / "orm-state.json").read_text(encoding="utf-8"))
    assert state["artifacts"]["repair_digest"] == "réparation.yaml"
    assert state["artifacts"]["holdout_digest"] == "holdout.digest.yaml"
    (tmp_path / "orm-state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    assert cli(tmp_path, "plan").returncode == 0


def test_nondefault_model_py_bootstrap_candidates(tmp_path):
    project_files(tmp_path)
    (tmp_path / "model.py").rename(tmp_path / "beaver_model.py")
    (tmp_path / "beaver_model.py").write_text("from relationalai.semantics import Model\n", encoding="utf-8")
    result = json.loads(cli(tmp_path, "plan").stdout)
    blocker = next(b for b in result["blockers"] if b["id"] == "PYREL_REQUIRED")
    assert blocker["candidates"] == ["beaver_model.py"]
    result = cli(tmp_path, "init", "--model-py", "beaver_model.py", "--emitter", "manual:step-10")
    assert result.returncode == 0
    assert "PYREL_REQUIRED" not in codes(json.loads(cli(tmp_path, "plan").stdout))
    assert not (tmp_path / "model.py").exists()


def test_invocation_round_start_is_retained_and_explicitly_restarted(tmp_path):
    state = initialized(tmp_path)
    update(state, tmp_path, "connectivity")
    assert state["invocation_started_round"] == 6
    append_rounds(tmp_path, 2)
    update(state, tmp_path, "rai-orm-verify", rounds_done=2)
    update(state, tmp_path, "report")
    assert plan(state, tmp_path)["rounds_used_this_invocation"] == 2
    update(state, tmp_path, "rai-orm", start_invocation=True)
    assert state["invocation_started_round"] == 8
    assert plan(state, tmp_path)["rounds_used_this_invocation"] == 0


@pytest.mark.parametrize("change", ["yaml", "digest", "python", "none"])
def test_emitter_idempotency_only_runs_in_copy(tmp_path, monkeypatch, change):
    import state as module
    # Test the copy/hash protocol independently of host sandbox availability.
    monkeypatch.setattr(module, "sandbox_prefix", lambda folder: [])
    project_files(tmp_path)
    target = {"yaml": "model.orm.yaml", "digest": "workload.digest.yaml", "python": "model.py"}.get(change)
    script = "from pathlib import Path\nPath('ran-in-copy').write_text('yes')\n"
    if target:
        script += f"p=Path({target!r}); p.write_text(p.read_text() + '# changed\\n')\n"
    (tmp_path / "emit.py").write_text(script, encoding="utf-8")
    before = {key: file_hash(tmp_path / ARTIFACT_DEFAULTS[key]) for key in ("model_yaml", "digest", "model_py")}
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py --out model.py")
    assert not (tmp_path / "ran-in-copy").exists()
    assert before == {key: file_hash(tmp_path / ARTIFACT_DEFAULTS[key]) for key in before}
    assert [f["path"] for f in state["emitter_files"]] == ["emit.py"]
    assert state["emitter_check"]["status"] == ("verified" if change == "none" else "blocked")
    if change != "none":
        assert "EMITTER_NOT_IDEMPOTENT" in codes(plan(state, tmp_path))
    else:
        (tmp_path / "emit.py").unlink()
        assert "EMITTER_MISSING" in codes(plan(state, tmp_path))


def test_emitter_sandbox_unavailable_never_executes(tmp_path, monkeypatch):
    import state as module
    def unavailable(folder):
        raise ValueError("unavailable")
    monkeypatch.setattr(module, "sandbox_prefix", unavailable)
    project_files(tmp_path)
    (tmp_path / "emit.py").write_text("raise RuntimeError('must not run')", encoding="utf-8")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    assert "EMITTER_UNVERIFIED" in codes(plan(state, tmp_path))


@pytest.mark.parametrize("output", ["unchanged", "irrelevant", "id", "reading"])
@pytest.mark.parametrize("emitter", ["manual:step-10", "python emit.py"])
def test_emitter_must_include_applied_fact_and_change_output(tmp_path, monkeypatch, output, emitter):
    import state as module
    monkeypatch.setattr(module, "sandbox_prefix", lambda folder: [])
    project_files(tmp_path)
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter=emitter)
    path = tmp_path / "model.orm.yaml"
    model = yaml.safe_load(path.read_text(encoding="utf-8"))
    model["fact_types"] = [{"id": "alpha_has_beta", "reading": "Alpha has Beta", "roles": []}]
    path.write_text(yaml.safe_dump(model), encoding="utf-8")
    if output != "unchanged":
        (tmp_path / "model.py").write_text({"irrelevant": "# other\n", "id": "# alpha_has_beta\n",
                                            "reading": "# Alpha has Beta\n"}[output], encoding="utf-8")
    result = plan(state, tmp_path)
    if output in {"unchanged", "irrelevant"}:
        assert "EMITTER_INCOMPLETE" in codes(result)
        with pytest.raises(UpdateBlocked):
            update(state, tmp_path, "connectivity")
    else:
        assert "EMITTER_INCOMPLETE" not in codes(result)


def test_old_manifest_cannot_bless_legacy_verification(tmp_path):
    state = initialized(tmp_path)
    # Older init versions incorrectly set this revision without verification evidence.
    write_verification(tmp_path, lambda v: v.pop("model_revision"))
    assert state["verification_revision"] == revision(tmp_path, ARTIFACT_DEFAULTS)
    assert "BASELINE_RECHECK_REQUIRED" in codes(plan(state, tmp_path))


def test_latest_round_exact_revision_can_bootstrap(tmp_path):
    project_files(tmp_path)
    def edit(value):
        value["rounds"][-1]["model_revision"] = value.pop("model_revision")
    write_verification(tmp_path, edit)
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    assert plan(state, tmp_path)["can_resume"]


@pytest.mark.parametrize("artifact", ["repair_digest", "holdout_digest"])
def test_split_digest_changes_and_deletion(tmp_path, artifact):
    project_files(tmp_path)
    write_verification(tmp_path, lambda v: [i.update(status="inexpressible") for i in v["items"] if i["status"] == "fail"])
    (tmp_path / "feedback.yaml").unlink()
    path = tmp_path / ARTIFACT_DEFAULTS[artifact]
    path.write_text("workload: {n_items: 1}\n", encoding="utf-8")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    path.write_text("workload: {n_items: 2}\n", encoding="utf-8")
    steps = plan(state, tmp_path)["steps"]
    assert ("rai-orm-verify" in steps) == (artifact == "repair_digest")
    path.unlink()
    assert {"id": "DIGEST_REQUIRED", "path": ARTIFACT_DEFAULTS[artifact]} in plan(state, tmp_path)["blockers"]


def test_emitter_changes_require_new_sandbox_check(tmp_path, monkeypatch):
    import state as module
    monkeypatch.setattr(module, "sandbox_prefix", lambda folder: [])
    project_files(tmp_path)
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="python emit.py")
    (tmp_path / "emit.py").write_text("# new emitter version\n", encoding="utf-8")
    assert "EMITTER_CHANGED" in codes(plan(state, tmp_path))
    update(state, tmp_path, "rai-orm", emitter="python emit.py")
    assert "EMITTER_CHANGED" not in codes(plan(state, tmp_path))
    assert state["emitter_check"]["status"] == "verified"


def test_bad_named_feedback_cannot_be_marked_processed(tmp_path):
    state = initialized(tmp_path)
    (tmp_path / "named.yaml").write_text("{PRIVATE_SENTINEL", encoding="utf-8")
    with pytest.raises(UpdateBlocked) as error:
        update(state, tmp_path, "feedback", feedback=["named.yaml"])
    assert "FEEDBACK_INVALID" in {b["id"] for b in error.value.blockers}
    assert state["feedback_processed"] == []


def test_readonly_bootstrap_preserves_workload_without_snapshot_write(tmp_path):
    project_files(tmp_path)
    (tmp_path / "items.json").write_text('[{"id":"q001","sql":"SELECT 1"}]', encoding="utf-8")
    assert cli(tmp_path, "plan", "--workload", "items.json").returncode == 0
    assert not (tmp_path / ".orm-workloads").exists()


def test_independent_refactor_budget_and_free_assessment(tmp_path):
    state = initialized(tmp_path, refactor_rounds=2)
    initial = plan(state, tmp_path)
    assert initial["steps"][1:] == ["connectivity", "rai-orm-refactor:assess", "rai-orm-verify", "rai-orm-refactor:accept", "report"]
    update(state, tmp_path, "rai-orm-refactor", rounds_done=0)
    append_rounds(tmp_path, 5)
    update(state, tmp_path, "rai-orm-verify", rounds_done=5)
    after_verify = plan(state, tmp_path)
    assert after_verify["rounds_remaining_by_skill"] == {"rai-orm-verify": 0, "rai-orm-refactor": 2}
    assert "rai-orm-verify" not in after_verify["steps"]
    assert [s for s in after_verify["steps"] if s.startswith("rai-orm-refactor:")] == ["rai-orm-refactor:assess", "rai-orm-refactor:accept"]
    update(state, tmp_path, "rai-orm-refactor", rounds_done=2, stop_reason="budget")
    result = plan(state, tmp_path)
    assert result["rounds_used_by_skill_this_invocation"] == {"rai-orm-verify": 5, "rai-orm-refactor": 2}
    assert [s for s in result["steps"] if s.startswith("rai-orm-refactor:")] == ["rai-orm-refactor:assess"]  # Free assessment remains.
    original = json.dumps(state, sort_keys=True)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-refactor", rounds_done=1)
    assert json.dumps(state, sort_keys=True) == original
    update(state, tmp_path, "rai-orm", start_invocation=True, refactor_rounds=3)
    assert plan(state, tmp_path)["rounds_remaining_by_skill"] == {"rai-orm-verify": 5, "rai-orm-refactor": 3}


def test_current_metrics_skip_only_assessment(tmp_path):
    state = initialized(tmp_path)
    metrics = tmp_path / "compaction.after.json"
    metrics.write_text(json.dumps({"model_revision": plan(state, tmp_path)["baseline_model_revision"]}), encoding="utf-8")
    result = plan(state, tmp_path)
    assert not result["refactor_assessment"]
    assert result["steps"][1:] == ["connectivity", "rai-orm-verify", "rai-orm-refactor:accept", "report"]
    metrics.write_text(json.dumps({"model_revision": "sha256:stale"}), encoding="utf-8")
    assert plan(state, tmp_path)["refactor_assessment"]


def test_refactor_budget_cli_init_update_plan(tmp_path):
    project_files(tmp_path)
    result = cli(tmp_path, "init", "--emitter", "manual:step-10", "--refactor-rounds", "3")
    assert result.returncode == 0
    assert json.loads(result.stdout)["budget"]["refactor_rounds"] == 3
    result = cli(tmp_path, "update", "--skill", "rai-orm-refactor", "--rounds-done", "1", "--refactor-rounds", "4")
    assert result.returncode == 0
    before = (tmp_path / "orm-state.json").read_bytes()
    result = cli(tmp_path, "plan", "--refactor-rounds", "6")
    assert json.loads(result.stdout)["rounds_remaining_by_skill"]["rai-orm-refactor"] == 5
    assert before == (tmp_path / "orm-state.json").read_bytes()
    assert cli(tmp_path, "plan", "--refactor-rounds", "0").returncode != 0


@pytest.mark.parametrize("artifact", ["repair_digest", "holdout_digest"])
def test_emitter_names_external_split_digest(tmp_path, artifact):
    from state import check_emitter
    (tmp_path / "emit.py").write_text("pass\n", encoding="utf-8")
    artifacts = {**ARTIFACT_DEFAULTS, artifact: "../outside.yaml"}
    result = check_emitter(tmp_path, artifacts, "python emit.py", [{"path": "emit.py"}])
    assert result["id"] == "EMITTER_UNVERIFIED"
    assert result["artifact"] == artifact and result["path"] == "../outside.yaml"
    assert "outside project folder" in result["reason"]


@pytest.mark.parametrize("cause", ["sandbox", "timeout", "symlink", "oserror", "external-argument"])
def test_emitter_specific_exception_reasons(tmp_path, monkeypatch, cause):
    import state as module
    import subprocess
    (tmp_path / "emit.py").write_text("pass\n", encoding="utf-8")
    command = "python emit.py"
    if cause == "sandbox":
        def unavailable(_):
            raise ValueError("sandbox unavailable")
        monkeypatch.setattr(module, "sandbox_prefix", unavailable)
    else:
        monkeypatch.setattr(module, "sandbox_prefix", lambda _: [])
    if cause == "timeout":
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("PRIVATE_COMMAND", 60)
        monkeypatch.setattr(module.subprocess, "run", timeout)
    if cause == "oserror":
        def failure(*args, **kwargs):
            raise PermissionError(13, "PRIVATE_CONTENTS")
        monkeypatch.setattr(module.subprocess, "run", failure)
    if cause == "symlink":
        (tmp_path / "unsafe.py").symlink_to(tmp_path / "emit.py")
    if cause == "external-argument":
        command += " /outside/config.json"
    result = module.check_emitter(tmp_path, dict(ARTIFACT_DEFAULTS), command, [{"path": "emit.py"}])
    assert result["id"] == "EMITTER_UNVERIFIED"
    assert "PRIVATE" not in json.dumps(result)
    if cause == "sandbox":
        assert result["reason"] == "sandbox unavailable"
    elif cause == "timeout":
        assert result["reason"] == "command timed out"
    elif cause == "oserror":
        assert result["errno"] == 13
    else:
        assert result["artifact"] == ("symlink" if cause == "symlink" else "command_argument")
        if cause == "symlink":
            assert result["path"] == "unsafe.py"


def test_metrics_do_not_supply_unwritten_stop_reason(tmp_path):
    from state import stop_reasons
    initialized(tmp_path)
    (tmp_path / "compaction.after.json").write_text('{"stopped_because":"invented"}', encoding="utf-8")
    assert "refactor" not in stop_reasons(tmp_path, ARTIFACT_DEFAULTS)


def test_invocation_archives_each_skill_and_until_pass_does_not_extend_refactor(tmp_path):
    state = initialized(tmp_path, until_pass=True)
    append_rounds(tmp_path, 6)
    update(state, tmp_path, "rai-orm-verify", rounds_done=6)
    update(state, tmp_path, "rai-orm-refactor", rounds_done=2)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-refactor", rounds_done=1)
    update(state, tmp_path, "rai-orm", start_invocation=True)
    assert state["invocation_rounds"][-1]["rounds_by_skill"] == {"rai-orm-verify": 6, "rai-orm-refactor": 2}
    assert state["rounds_used_by_skill_this_invocation"] == {"rai-orm-verify": 0, "rai-orm-refactor": 0}


def test_legacy_invocation_budget_is_not_reset_by_unrelated_update(tmp_path):
    state = initialized(tmp_path)
    state.pop("rounds_used_by_skill_this_invocation")
    state["invocation_started_round"] = 4
    update(state, tmp_path, "report")
    assert plan(state, tmp_path)["rounds_used_this_invocation"] == 2


def append_rounds(project, count):
    def edit(value):
        start = max(r["round"] for r in value["rounds"]) + 1
        value["rounds"].extend({"round": n} for n in range(start, start + count))
    write_verification(project, edit)


def workload_state(project):
    rows = [{"id": f"q{i:03d}", "sql": f"SELECT {i}"} for i in range(1, 6)]
    (project / "items.json").write_text(json.dumps(rows), encoding="utf-8")
    return initialized(project, workloads=["items.json"]), rows


def test_changed_pass_stays_invalid_after_delta_acceptance(tmp_path):
    state, rows = workload_state(tmp_path)
    old_spec = state["verification_snapshot"]["items"][0]["spec_hash"]
    rows[0]["sql"] = "SELECT 99"
    (tmp_path / "items.json").write_text(json.dumps(rows), encoding="utf-8")
    update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    update(state, tmp_path, "report")
    result = plan(state, tmp_path)
    assert {"id": "CHANGED_ITEM_RECHECK", "item_ids": ["q001"]} in result["blockers"]
    assert result["baseline_recheck"] and not result["can_resume"]
    assert "q001" not in result["frozen_passed_items"]
    assert state["verification_snapshot"]["items"][0]["spec_hash"] == old_spec
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")
    # Successful recheck explicitly associates its evidence with the new spec.
    write_verification(tmp_path, lambda v: v["items"][0].update(spec_hash=item_hashes(tmp_path / "items.json")["q001"]))
    update(state, tmp_path, "rai-orm-verify")
    result = plan(state, tmp_path)
    assert result["can_resume"] and not result["baseline_recheck"]
    assert "q001" in result["frozen_passed_items"]


def test_changed_specs_cannot_swap_split_assignments(tmp_path):
    state, rows = workload_state(tmp_path)
    rows[0]["sql"], rows[2]["sql"] = "SELECT 88", "SELECT 99"
    (tmp_path / "items.json").write_text(json.dumps(rows), encoding="utf-8")
    def swap(v):
        v["items"][0]["split"], v["items"][2]["split"] = "holdout", "repair"
    write_verification(tmp_path, swap)
    with pytest.raises(UpdateBlocked) as error:
        update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    assert {b["item_id"] for b in error.value.blockers if b["id"] == "ITEM_SPLIT_CHANGED"} == {"q001", "q003"}


@pytest.mark.parametrize("addition", [True, False])
def test_unbalanced_workload_delta_accepts_counts_preserves_rule(tmp_path, addition):
    state, rows = workload_state(tmp_path)
    rows = rows + [{"id": "q006", "sql": "SELECT 6"}] if addition else rows[1:]
    (tmp_path / "items.json").write_text(json.dumps(rows), encoding="utf-8")
    def edit(v):
        if addition:
            v["items"].append({"id": "q006", "status": "fail", "split": "repair"})
        else:
            v["items"] = v["items"][1:]
        v["split"]["repair"] += 1 if addition else -1
        v["workload"] = {"n_items": len(rows)}
    write_verification(tmp_path, edit)
    (tmp_path / "workload.digest.yaml").write_text(yaml.safe_dump({"workload": {"n_items": len(rows)}}), encoding="utf-8")
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")
    update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    assert plan(state, tmp_path)["can_resume"]
    write_verification(tmp_path, lambda v: v["split"].update(rule="new-rule"))
    with pytest.raises(UpdateBlocked) as error:
        update(state, tmp_path, "rai-orm-from-workload", accept_workload_delta=True)
    assert "SPLIT_CHANGED" in codes({"blockers": error.value.blockers})


@pytest.mark.parametrize("artifact", ["digest", "repair_digest", "holdout_digest"])
def test_deleted_digest_remains_required_until_restored_or_retired(tmp_path, artifact):
    project_files(tmp_path)
    path = tmp_path / ARTIFACT_DEFAULTS[artifact]
    if not path.exists():
        path.write_text("workload: {n_items: 1}\n", encoding="utf-8")
    original = path.read_bytes()
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    path.unlink()
    update(state, tmp_path, "report")
    assert "DIGEST_REQUIRED" in codes(plan(state, tmp_path))
    assert artifact in state["required_artifacts"]
    path.write_bytes(original)
    assert "DIGEST_REQUIRED" not in codes(plan(state, tmp_path))
    path.unlink()
    with pytest.raises(ValueError):
        update(state, tmp_path, "report", retire_artifacts=[artifact])
    update(state, tmp_path, "report", retire_artifacts=[artifact], retire_reason="Replaced by reviewed inventory")
    update(state, tmp_path, "report")
    assert "DIGEST_REQUIRED" not in codes(plan(state, tmp_path))
    assert state["retired_artifacts"][artifact]["reason"] == "Replaced by reviewed inventory"


def test_dependency_registration_merges_preserves_and_drops_cli(tmp_path):
    project_files(tmp_path)
    for name in ("helper.py", "extra.py", "bindings.py", "extra-bindings.py"):
        (tmp_path / name).write_text("# dependency\n", encoding="utf-8")
    assert cli(tmp_path, "init", "--emitter", "manual:step-10", "--emitter-file", "helper.py", "--binding", "bindings.py").returncode == 0
    result = cli(tmp_path, "update", "--skill", "rai-orm", "--emitter", "manual:step-10", "--emitter-file", "extra.py", "--binding", "extra-bindings.py")
    assert result.returncode == 0, result.stdout
    manifest = lambda: json.loads((tmp_path / "orm-state.json").read_text(encoding="utf-8"))
    saved = manifest()
    assert [r["path"] for r in saved["emitter_files"]] == ["extra.py", "helper.py"]
    assert [r["path"] for r in saved["bindings"]] == ["bindings.py", "extra-bindings.py"]
    assert cli(tmp_path, "update", "--skill", "report").returncode == 0
    assert manifest()["emitter_files"] == saved["emitter_files"]
    assert manifest()["bindings"] == saved["bindings"]
    assert cli(tmp_path, "update", "--skill", "rai-orm", "--emitter", "manual:step-10").returncode == 0
    assert manifest()["emitter_files"] == saved["emitter_files"]
    assert cli(tmp_path, "update", "--skill", "report", "--drop-emitter-file", "extra.py", "--drop-binding", "extra-bindings.py").returncode == 0
    assert [r["path"] for r in manifest()["emitter_files"]] == ["helper.py"]
    assert [r["path"] for r in manifest()["bindings"]] == ["bindings.py"]


def regression_round(project, losses=1, corrupt=None):
    def edit(v):
        for item in v["items"][:losses]:
            item.update(status="fail", regressed_at_round=6)
        for item in v["items"][3:]:
            item.update(status="pass", passed_at_round=6, pyrel=f"verification/{item['id']}.py")
            (project / item["pyrel"]).write_text("result = Alpha\n", encoding="utf-8")
        v["rounds"].append({"round": 6, "regressions": losses, "fixes": 2})
        if corrupt == "marker":
            v["items"][0].pop("regressed_at_round")
        elif corrupt == "exclusion":
            v["items"][0]["status"] = "inexpressible"
        elif corrupt == "counts":
            v["rounds"][-1]["fixes"] = 3
    write_verification(project, edit)


def test_verify_net_improvement_needs_flag_and_tracks_regressed_ids(tmp_path):
    state = initialized(tmp_path)
    regression_round(tmp_path)
    before = json.dumps(state, sort_keys=True)
    with pytest.raises(UpdateBlocked) as error:
        update(state, tmp_path, "rai-orm-verify")
    assert "BASELINE_PASS_LOST" in codes({"blockers": error.value.blockers})
    assert json.dumps(state, sort_keys=True) == before
    update(state, tmp_path, "rai-orm-verify", accept_regressions=True)
    result = plan(state, tmp_path)
    assert {"id": "REGRESSED_ITEM", "item_id": "q001"} in result["blockers"]
    assert not result["can_resume"]
    assert result["frozen_passed_items"] == ["q002", "q003", "q004", "q005"]
    write_verification(tmp_path, lambda v: v["items"][0].update(status="oracle-error"))
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "report")
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-verify")
    write_verification(tmp_path, lambda v: v["items"][0].update(status="pass", passed_at_round=7))
    append_rounds(tmp_path, 1)
    update(state, tmp_path, "rai-orm-verify")
    assert plan(state, tmp_path)["can_resume"]
    assert state["regressed_items"] == []


@pytest.mark.parametrize("losses,corrupt", [(2, None), (1, "marker"), (1, "exclusion"), (1, "counts")])
def test_invalid_regression_acceptance_refused(tmp_path, losses, corrupt):
    state = initialized(tmp_path)
    regression_round(tmp_path, losses, corrupt)
    before = json.dumps(state, sort_keys=True)
    with pytest.raises(UpdateBlocked) as error:
        update(state, tmp_path, "rai-orm-verify", accept_regressions=True)
    assert "REGRESSION_ACCEPTANCE_INVALID" in codes({"blockers": error.value.blockers})
    assert json.dumps(state, sort_keys=True) == before


def test_refactor_cannot_accept_net_positive_pass_loss(tmp_path):
    state = initialized(tmp_path)
    regression_round(tmp_path)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-refactor", rounds_done=1)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "rai-orm-refactor", rounds_done=1, accept_regressions=True)


@pytest.mark.parametrize("supplied", [None, 0, 2, 3])
def test_verify_round_charge_comes_from_history(tmp_path, supplied):
    state = initialized(tmp_path)
    append_rounds(tmp_path, 3)
    if supplied not in {None, 3}:
        before = json.dumps(state, sort_keys=True)
        with pytest.raises(UpdateBlocked) as error:
            update(state, tmp_path, "rai-orm-verify", rounds_done=supplied)
        assert "ROUNDS_MISMATCH" in codes({"blockers": error.value.blockers})
        assert json.dumps(state, sort_keys=True) == before
    else:
        update(state, tmp_path, "rai-orm-verify", rounds_done=supplied)
        result = plan(state, tmp_path)
        assert result["baseline_round"] == 8
        assert result["rounds_used_by_skill_this_invocation"]["rai-orm-verify"] == 3
        assert result["rounds_remaining_by_skill"]["rai-orm-verify"] == 2


@pytest.mark.parametrize("declaration", ["Alpha.links_beta = model.Property()", "links_beta = model.Property()", "links_beta_extra = model.Property()", "Alpha.links_beta_extra = model.Property()"])
def test_fact_metadata_accepts_real_declarations_without_changed_output(tmp_path, declaration):
    state = initialized(tmp_path)
    (tmp_path / "model.py").write_text(declaration, encoding="utf-8")
    state["emitted_py_sha256"] = file_hash(tmp_path / "model.py")
    model_path = tmp_path / "model.orm.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    model["fact_types"] = [{"id": "fact_01", "reading": "Alpha links Beta", "pyrel": {"owner": "Alpha", "property": "links_beta", "type": "Property"}}]
    model_path.write_text(yaml.safe_dump(model), encoding="utf-8")
    result = plan(state, tmp_path)
    if "extra" in declaration:
        blocker = next(b for b in result["blockers"] if b["id"] == "EMITTER_INCOMPLETE")
        assert blocker["missing_fact_ids"] == ["fact_01"]
        with pytest.raises(UpdateBlocked):
            update(state, tmp_path, "connectivity")
    else:
        assert "EMITTER_INCOMPLETE" not in codes(result)
        update(state, tmp_path, "connectivity")


@pytest.mark.parametrize("removed", [True, False])
def test_removed_or_rejected_fact_requires_changed_python(tmp_path, removed):
    project_files(tmp_path)
    path = tmp_path / "model.orm.yaml"
    model = yaml.safe_load(path.read_text(encoding="utf-8"))
    model["fact_types"] = [{"id": "old_fact", "reading": "Alpha links Beta"}]
    path.write_text(yaml.safe_dump(model), encoding="utf-8")
    state = initialize(tmp_path, dict(ARTIFACT_DEFAULTS), emitter="manual:step-10")
    if removed:
        model["fact_types"] = []
    else:
        model["fact_types"][0]["status"] = "rejected"
    path.write_text(yaml.safe_dump(model), encoding="utf-8")
    assert "EMITTER_INCOMPLETE" in codes(plan(state, tmp_path))
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "connectivity")
    (tmp_path / "model.py").write_text("# Removed declaration\n", encoding="utf-8")
    assert "EMITTER_INCOMPLETE" not in codes(plan(state, tmp_path))
    update(state, tmp_path, "connectivity")


@pytest.mark.parametrize("location", ["artifact", "input", "snapshot", "emitter", "binding", "saved_pyrel", "current_pyrel", "symlink"])
def test_plan_never_reads_or_hashes_external_manifest_paths(tmp_path, monkeypatch, location):
    import state as module
    state = initialized(tmp_path)
    outside = tmp_path.parent / "outside-secret.yaml"
    outside.write_text("PRIVATE_CONTENT\n", encoding="utf-8")
    if location == "artifact":
        state["artifacts"]["digest"] = str(outside)
    elif location == "input":
        state["inputs"] = [{"kind": "workload", "path": str(outside)}]
    elif location == "snapshot":
        state["inputs"] = [{"kind": "workload", "path": "items.json", "snapshot_path": str(outside)}]
    elif location in {"binding", "emitter"}:
        state["bindings" if location == "binding" else "emitter_files"] = [{"path": str(outside)}]
    elif location == "saved_pyrel":
        state["verification_snapshot"]["items"][0]["pyrel"] = str(outside)
    elif location == "current_pyrel":
        write_verification(tmp_path, lambda v: v["items"][0].update(pyrel=str(outside)))
    else:
        (tmp_path / "linked.yaml").symlink_to(outside)
        state["artifacts"]["digest"] = "linked.yaml"
    original_read, original_hash = module.read, module.file_hash
    def guarded(function):
        def call(path):
            path.resolve().relative_to(tmp_path.resolve())
            return function(path)
        return call
    monkeypatch.setattr(module, "read", guarded(original_read))
    monkeypatch.setattr(module, "file_hash", guarded(original_hash))
    result = plan(state, tmp_path)
    assert not result["can_resume"]
    assert result["blockers"][0]["id"] == "PATH_OUTSIDE_PROJECT"
    assert result["blockers"][0]["key"]
    assert "PRIVATE_CONTENT" not in json.dumps(result)
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "report")


@pytest.mark.skipif(not Path("/usr/bin/sandbox-exec").is_file(), reason="sandbox-exec unavailable")
@pytest.mark.parametrize("outside", [False, True, "home"])
def test_real_sandbox_confines_emitter_reads(tmp_path, outside):
    import sys
    from state import check_emitter
    project_files(tmp_path)
    external = tmp_path.parent / "external-input.txt"
    external.write_text("outside", encoding="utf-8")
    path = str(Path(__file__).resolve()) if outside == "home" else str(external) if outside else "model.orm.yaml"
    (tmp_path / "emit.py").write_text(
        f"from pathlib import Path\nPath({path!r}).read_text(encoding='utf-8')\n"
        "with open('/dev/null', 'w') as sink: sink.write('allowed')\n", encoding="utf-8")
    result = check_emitter(tmp_path, dict(ARTIFACT_DEFAULTS), f"{sys.executable} emit.py", [{"path": "emit.py"}])
    if outside:
        assert result["id"] == "EMITTER_UNVERIFIED"
        assert "PermissionError" in result["cause"], result
    else:
        assert result["status"] == "verified", result


@pytest.mark.parametrize("argument", ["../secret", "--config=../secret"])
def test_emitter_rejects_parent_traversal_arguments(tmp_path, monkeypatch, argument):
    import state as module
    project_files(tmp_path)
    monkeypatch.setattr(module, "sandbox_prefix", lambda folder: [])
    result = module.check_emitter(tmp_path, dict(ARTIFACT_DEFAULTS), "python emit.py " + argument, [{"path": "emit.py"}])
    assert result["artifact"] == "command_argument"
    assert result["id"] == "EMITTER_UNVERIFIED"


def test_compact_manifest_and_cli_summary_for_643_items(tmp_path):
    project_files(tmp_path)
    model_path = tmp_path / "model.orm.yaml"
    model = yaml.safe_load(model_path.read_text(encoding="utf-8"))
    model["fact_types"] = [{"id": f"entity_{i}_has_a_long_property_name", "reading": f"Entity {i} has value"} for i in range(1803)]
    model_path.write_text(yaml.safe_dump(model), encoding="utf-8")
    rows = [{"id": f"q{i:04d}", "sql": f"SELECT {i}"} for i in range(643)]
    (tmp_path / "items.json").write_text(json.dumps(rows), encoding="utf-8")
    def edit(v):
        v["items"] = [{"id": row["id"], "status": "fail", "split": "repair"} for row in rows]
        v["split"] = {"repair": len(rows), "holdout": 0}
        v["workload"] = {"n_items": len(rows)}
    write_verification(tmp_path, edit)
    digest = {"workload": {"n_items": len(rows)}, "item_contributions": {
        row["id"]: {"large_evidence": ["PRIVATE_SENTINEL" * 50] * 5} for row in rows}}
    (tmp_path / "workload.digest.yaml").write_text(yaml.safe_dump(digest), encoding="utf-8")
    result = cli(tmp_path, "init", "--emitter", "manual:step-10", "--workload", "items.json")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.encode()) < 5000
    manifest = (tmp_path / "orm-state.json").read_bytes()
    assert len(manifest) < 300000
    assert b'"item_contributions"' not in manifest
    assert b'PRIVATE_SENTINEL' not in manifest
    result = cli(tmp_path, "update", "--skill", "report")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.encode()) < 5000
    assert len((tmp_path / "orm-state.json").read_bytes()) < 300000


@pytest.mark.parametrize("damage", ["missing", "changed", "outside"])
def test_emitted_fact_sidecar_is_required_and_confined(tmp_path, damage):
    state = initialized(tmp_path)
    record = state["emitted_facts"]
    path = tmp_path / record["snapshot_path"]
    if damage == "missing":
        path.unlink()
        expected = "EMITTED_FACTS_REQUIRED"
    elif damage == "changed":
        path.write_text('{"forged":"hash"}', encoding="utf-8")
        expected = "EMITTED_FACTS_CHANGED"
    else:
        record["snapshot_path"] = "../outside.json"
        expected = "PATH_OUTSIDE_PROJECT"
    assert expected in codes(plan(state, tmp_path))
    with pytest.raises(UpdateBlocked):
        update(state, tmp_path, "report")


def test_inline_legacy_fact_snapshot_still_supported(tmp_path):
    from state import fact_snapshot
    state = initialized(tmp_path)
    state["emitted_facts"] = fact_snapshot(tmp_path, ARTIFACT_DEFAULTS)
    assert plan(state, tmp_path)["can_resume"]
    update(state, tmp_path, "report")
    assert (tmp_path / state["emitted_facts"]["snapshot_path"]).is_file()


def test_cli_accept_regressions_and_retire_artifact(tmp_path):
    project_files(tmp_path)
    assert cli(tmp_path, "init", "--emitter", "manual:step-10").returncode == 0
    regression_round(tmp_path)
    assert cli(tmp_path, "update", "--skill", "rai-orm-verify").returncode == 1
    result = cli(tmp_path, "update", "--skill", "rai-orm-verify", "--accept-regressions")
    assert result.returncode == 0, result.stdout
    assert "REGRESSED_ITEM" in codes(json.loads(cli(tmp_path, "plan").stdout))
    (tmp_path / "workload.digest.yaml").unlink()
    result = cli(tmp_path, "update", "--skill", "report", "--retire-artifact", "digest", "--retire-reason", "Explicitly retired")
    assert result.returncode == 0, result.stdout
    assert "DIGEST_REQUIRED" not in codes(json.loads(cli(tmp_path, "plan").stdout))
