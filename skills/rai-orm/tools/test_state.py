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
    assert plan(state, tmp_path)["steps"] == ["manual:step-10", "connectivity", "rai-orm-refactor", "report"]


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
    (tmp_path / "compaction.after.json").write_text("{}")
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
    assert record["item_contributions"] == digest["item_contributions"]
    rows[-1]["sql"] = "SELECT 99"
    path.write_text(json.dumps(rows), encoding="utf-8")
    assert "WORKLOAD_FULL_REBUILD_REQUIRED" not in codes(plan(state, tmp_path))


def test_split_digest_artifacts_and_utf8_manifest(tmp_path):
    project_files(tmp_path)
    result = cli(tmp_path, "init", "--emitter", "manual:step-10", "--repair-digest", "réparation.yaml",
                 "--holdout-digest", "holdout.digest.yaml")
    assert result.returncode == 0
    state = json.loads(result.stdout)
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
