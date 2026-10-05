"""CLI resume from an exhausted invocation, using only synthetic artifacts."""

import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from state import ARTIFACT_DEFAULTS, revision


TOOL = Path(__file__).with_name("state.py")


def cli(project, *args):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=project, capture_output=True, text=True)


def project_files(project):
    model = {"version": 1, "source": {"kind": "ddl-file", "mode": "guided"},
             "object_types": [{"id": "alpha", "name": "Alpha", "kind": "entity"},
                              {"id": "beta", "name": "Beta", "kind": "entity"}], "fact_types": []}
    (project / "model.orm.yaml").write_text(yaml.safe_dump(model))
    (project / "model.py").write_text("# Synthetic emitter output\n")
    (project / "emit.py").write_text("# Project-specific emitter\n")
    (project / "workload.digest.yaml").write_text(yaml.safe_dump({"version": 1, "workload": {"n_items": 5}}))
    (project / "verification").mkdir()
    items = []
    for index in range(1, 6):
        item = {"id": f"q{index:03d}", "split": "holdout" if index == 3 else "repair",
                "status": "pass" if index <= 3 else "fail"}
        if index <= 3:
            item["pyrel"] = f"verification/q{index:03d}.py"
            item["passed_at_round"] = index
            (project / item["pyrel"]).write_text("result = Alpha\n")
        else:
            item["class"] = "missing-element"
        items.append(item)
    value = {"model_revision": revision(project, ARTIFACT_DEFAULTS), "version": 1, "oracle": "structural", "split": {"repair": 4, "holdout": 1},
             "rounds": [{"round": i, "repair_pass": 2, "holdout_pass": 1} for i in range(6)],
             "items": items, "summary": {"stopped_because": "budget"},
             "invocations": [{"started_round": 1, "rounds_run": 5, "stopped_because": "budget"}]}
    (project / "model.verification.json").write_text(json.dumps(value))
    (project / "feedback.yaml").write_text(yaml.safe_dump({"version": 1, "items": [
        {"id": "f01", "kind": "missing_link", "from": "Alpha", "to": "Beta"}]}))
    return value


def test_resume_flow(tmp_path):
    project_files(tmp_path)
    originals = {name: (tmp_path / name).read_bytes() for name in
                 ("model.orm.yaml", "model.py", "workload.digest.yaml", "model.verification.json")}
    initialized = cli(tmp_path, "init", "--emitter", "manual:step-10")
    assert initialized.returncode == 0, initialized.stderr
    first = cli(tmp_path, "plan")
    assert first.returncode == 0, first.stderr
    result = json.loads(first.stdout)
    assert result["started_round"] == 6 and result["baseline_round"] == 5
    assert result["frozen_passed_items"] == ["q001", "q002", "q003"]
    assert [item["id"] for item in result["new_feedback_items"]] == ["f01"]
    assert result["new_feedback_items"][0]["source"] == "user-feedback"
    assert result["steps"] == ["manual:step-10", "connectivity", "rai-orm-verify", "rai-orm-refactor", "report"]
    assert result["budget"] == {"rounds_per_invocation": 5, "patience": 2, "until_pass": False}
    assert result["can_resume"]
    assert first.stdout == cli(tmp_path, "plan").stdout
    assert originals == {name: (tmp_path / name).read_bytes() for name in originals}
    manifest = json.loads((tmp_path / "orm-state.json").read_text())
    manifest["emitter_command"] = None
    (tmp_path / "orm-state.json").write_text(json.dumps(manifest))
    blocked = json.loads(cli(tmp_path, "plan").stdout)
    assert not blocked["can_resume"]
    assert "EMITTER_REQUIRED" in {item["id"] for item in blocked["blockers"]}


@pytest.mark.parametrize("damage,blocker", [(None, None), ("edit", "PASSED_PYREL_CHANGED"),
                                           ("delete", "PASSED_PYREL_MISSING")])
def test_legacy_resume_cli(tmp_path, damage, blocker):
    verification = project_files(tmp_path)
    (tmp_path / "feedback.yaml").unlink()
    verification_path = tmp_path / "model.verification.json"
    verification.pop("model_revision")
    verification_path.write_text(json.dumps(verification), encoding="utf-8")
    original = verification_path.read_bytes()
    assert all("pyrel_sha256" not in item for item in verification["items"])
    initialized = cli(tmp_path, "init", "--emitter", "manual:step-10", "--skill", "rai-orm-verify")
    assert initialized.returncode == 0, initialized.stderr
    manifest = json.loads(initialized.stdout)
    saved = manifest["verification_snapshot"]["items"][:3]
    assert all(item["pyrel_sha256"].startswith("sha256:") for item in saved)
    assert [item["passed_at_round"] for item in saved] == [1, 2, 3]
    rewrite = tmp_path / "verification/q001.py"
    if damage == "edit":
        rewrite.write_text("result = Beta\n")
    elif damage == "delete":
        rewrite.unlink()
    planned = cli(tmp_path, "plan")
    assert planned.returncode == 0, planned.stderr
    result = json.loads(planned.stdout)
    assert result["started_round"] == max(row["round"] for row in verification["rounds"]) + 1
    assert result["frozen_passed_items"] == ["q001", "q002", "q003"]
    assert not result["can_resume"]
    assert result["baseline_recheck"]
    assert "BASELINE_RECHECK_REQUIRED" in {b["id"] for b in result["blockers"]}
    if blocker:
        assert {"id": blocker, "item_id": "q001"} in result["blockers"]
    assert verification_path.read_bytes() == original
