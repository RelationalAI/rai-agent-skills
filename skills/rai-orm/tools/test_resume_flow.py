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
    assert result["steps"] == ["manual:step-10", "connectivity", "rai-orm-refactor:assess", "rai-orm-verify", "rai-orm-refactor:accept", "report"]
    assert result["budget"] == {"rounds_per_invocation": 5, "patience": 2, "until_pass": False, "refactor_rounds": 2}
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
    manifest = json.loads((tmp_path / "orm-state.json").read_text(encoding="utf-8"))
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


def test_b7ca2a7_manifest_loads_and_plans_identically(tmp_path):
    # Captured from the unmodified R5 starting code; do not regenerate with initialize.
    project_files(tmp_path)
    manifest = json.loads('''{
  "artifact_hashes": {
    "connectivity": null,
    "digest": "sha256:0cc95af8e1ca7db08645b56549a3a424b6e02f765621d8fb50a75d1d3c80b0d4",
    "holdout_digest": null,
    "model_py": "sha256:476440e569797b60f9fbc435f7245b6d22a63dcb3a5dc385f1a6656fa1d9bf18",
    "model_yaml": "sha256:2cf7af60e5d1b5aa8ca0fa461e3218c7d32818e2ed5f988ff24e9c55ef4221da",
    "refactor_before": null,
    "refactor_metrics": null,
    "repair_digest": null,
    "report": null,
    "report_markdown": null,
    "verification": "sha256:049e64af831d5c8c659ef5f84ef79a80e031b6af8bc76b3d61472e3f00674902"
  },
  "artifact_stop_reasons": {
    "connectivity": null,
    "report": null
  },
  "artifacts": {
    "connectivity": "connectivity.json",
    "digest": "workload.digest.yaml",
    "holdout_digest": "holdout.digest.yaml",
    "model_py": "model.py",
    "model_yaml": "model.orm.yaml",
    "refactor_before": "compaction.before.json",
    "refactor_metrics": "compaction.after.json",
    "repair_digest": "repair.digest.yaml",
    "report": "orm-report.json",
    "report_markdown": "orm-report.md",
    "verification": "model.verification.json"
  },
  "bindings": [],
  "budget": {
    "patience": 2,
    "refactor_rounds": 2,
    "rounds_per_invocation": 5,
    "until_pass": false
  },
  "emitted_facts": {
    "sha256": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    "snapshot_path": ".orm-facts/44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a.json"
  },
  "emitted_py_sha256": "sha256:476440e569797b60f9fbc435f7245b6d22a63dcb3a5dc385f1a6656fa1d9bf18",
  "emitter_check": {
    "status": "manual"
  },
  "emitter_command": "manual:step-10",
  "emitter_files": [],
  "feedback_processed": [],
  "inputs": [],
  "invocation_rounds": [],
  "last_stop_reason": "budget",
  "mode": "guided",
  "model_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
  "required_artifacts": [
    "digest",
    "model_py",
    "model_yaml",
    "verification"
  ],
  "retired_artifacts": {},
  "round_counters": {
    "rai-orm-from-schema": 0,
    "rai-orm-from-workload": 0,
    "rai-orm-verify": 5
  },
  "rounds_used_by_skill_this_invocation": {
    "rai-orm-refactor": 0,
    "rai-orm-verify": 0
  },
  "skills_run": [
    {
      "model_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
      "rounds_done": 0,
      "skill": "rai-orm-from-workload",
      "stop_reason": null
    },
    {
      "model_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
      "rounds_done": 0,
      "skill": "rai-orm-from-schema",
      "stop_reason": null
    },
    {
      "model_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
      "rounds_done": 5,
      "skill": "rai-orm-verify",
      "stop_reason": "budget"
    }
  ],
  "verification_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
  "verification_snapshot": {
    "items": [
      {
        "id": "q001",
        "passed_at_round": 1,
        "pyrel": "verification/q001.py",
        "pyrel_sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3",
        "split": "repair",
        "status": "pass"
      },
      {
        "id": "q002",
        "passed_at_round": 2,
        "pyrel": "verification/q002.py",
        "pyrel_sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3",
        "split": "repair",
        "status": "pass"
      },
      {
        "id": "q003",
        "passed_at_round": 3,
        "pyrel": "verification/q003.py",
        "pyrel_sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3",
        "split": "holdout",
        "status": "pass"
      },
      {
        "id": "q004",
        "split": "repair",
        "status": "fail"
      },
      {
        "id": "q005",
        "split": "repair",
        "status": "fail"
      }
    ],
    "oracle": "structural",
    "split": {
      "holdout": 1,
      "repair": 4
    }
  },
  "version": 1
}''')
    expected = json.loads('''{
  "artifact_stop_reasons": {
    "connectivity": null,
    "report": null
  },
  "baseline_model_revision": "sha256:555552ef1b5a3ecd8f1a8f63d2c961f60e2dcca649b52a5232be5a84a236d8dc",
  "baseline_recheck": false,
  "baseline_round": 5,
  "blockers": [],
  "budget": {
    "patience": 2,
    "refactor_rounds": 2,
    "rounds_per_invocation": 5,
    "until_pass": false
  },
  "can_resume": true,
  "feedback_files": [
    {
      "path": "feedback.yaml",
      "sha256": "sha256:4f29f28ce07a7a03b5a4d07e1f2d1810601144ac9192c6b9cb5010a7fd634c5b"
    }
  ],
  "frozen_passed_items": [
    "q001",
    "q002",
    "q003"
  ],
  "missing_item_ids": [],
  "mode": "guided",
  "new_feedback_items": [
    {
      "from": "Alpha",
      "id": "f01",
      "kind": "missing_link",
      "sha256": "sha256:676244ffda2c20c4656f9a0aba6e765472a58037aecb2ca3ed16becebcd14f3c",
      "source": "user-feedback",
      "status": "proposed",
      "to": "Beta"
    }
  ],
  "refactor_assessment": true,
  "rounds_remaining_by_skill": {
    "rai-orm-refactor": 2,
    "rai-orm-verify": 5
  },
  "rounds_used_by_skill_this_invocation": {
    "rai-orm-refactor": 0,
    "rai-orm-verify": 0
  },
  "rounds_used_this_invocation": 0,
  "saved_pyrel": [
    {
      "id": "q001",
      "path": "verification/q001.py",
      "sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3"
    },
    {
      "id": "q002",
      "path": "verification/q002.py",
      "sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3"
    },
    {
      "id": "q003",
      "path": "verification/q003.py",
      "sha256": "sha256:aca27f476642f64ad82f45eef003a26681aa6f680e8fe26b9c4190e25c9214d3"
    }
  ],
  "stale_artifacts": [],
  "started_round": 6,
  "steps": [
    "manual:step-10",
    "connectivity",
    "rai-orm-refactor:assess",
    "rai-orm-verify",
    "rai-orm-refactor:accept",
    "report"
  ],
  "version": 1,
  "workload_delta": {
    "changed_inputs": [],
    "changed_item_ids": [],
    "new_item_ids": [],
    "redigest_item_ids": [],
    "removed_item_ids": []
  }
}''')
    path = tmp_path / "orm-state.json"
    facts = tmp_path / manifest["emitted_facts"]["snapshot_path"]
    facts.parent.mkdir()
    facts.write_text("{}", encoding="utf-8")
    path.write_text(json.dumps(manifest), encoding="utf-8")
    before = path.read_bytes()
    result = cli(tmp_path, "plan")
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout) == expected
    assert path.read_bytes() == before
