"""Per-id preservation and executable synthetic migration/rollback workflow."""

import copy
import json
from pathlib import Path

import duckdb
import pytest
import yaml

from acceptance import attempt, evaluate


def baseline():
    return {"oracle": "execution-match", "workload": {"n_items": 2}, "split": {"repair": 2},
            "items": [{"id": "p1", "split": "repair", "status": "pass", "weak": False},
                      {"id": "p2", "split": "repair", "status": "fail"}],
            "summary": {"weak_passes": 0, "excluded": {}}}


def test_same_split_pass_swap_is_rejected():
    before = baseline()
    after = copy.deepcopy(before)
    after["items"][0]["status"] = "fail"
    after["items"][1]["status"] = "pass"
    assert evaluate(before, after) == {"accepted": False, "reasons": ["baseline-pass-lost:p1"]}


@pytest.mark.parametrize("damage", ["oracle", "weak", "missing", "split", "excluded", "unverified", "duplicate"])
def test_preservation_risky_paths(damage):
    before = baseline()
    after = copy.deepcopy(before)
    if damage == "oracle":
        after["oracle"] = "structural"
    elif damage == "weak":
        after["items"][0]["weak"] = True
    elif damage == "missing":
        after["items"].pop(0)
    elif damage == "split":
        after["items"][0]["split"] = "holdout"
    elif damage in {"excluded", "unverified"}:
        after["items"][0]["status"] = "inexpressible" if damage == "excluded" else damage
    else:
        after["items"].append(after["items"][0])
    assert not evaluate(before, after)["accepted"]


@pytest.mark.parametrize("wrong_filter", [False, True])
def test_remove_concept_candidate_rewrite_accept_or_rollback(tmp_path, wrong_filter):
    # Local executable model stand-in; the independent DuckDB oracle checks
    # results, not strings/AST shapes. No live PyRel service is required.
    model = {"object_types": [{"id": "asset", "name": "Asset", "kind": "entity"},
                               {"id": "selected", "name": "SelectedAsset", "kind": "entity"}], "fact_types": []}
    (tmp_path / "model.orm.yaml").write_text(yaml.safe_dump(model), encoding="utf-8")
    (tmp_path / "model.py").write_text("Asset = [(1, 3), (2, 8), (3, 10)]\nSelectedAsset = [a for a in Asset if a[1] >= 8]\n", encoding="utf-8")
    (tmp_path / "accepted.py").write_text("result = [(a[0],) for a in SelectedAsset]\n", encoding="utf-8")
    for name in ("bindings.py", "model.verbalization.txt"):
        (tmp_path / name).write_text("baseline\n", encoding="utf-8")
    before = baseline()
    before["items"] = before["items"][:1]
    before["items"][0]["pyrel"] = "accepted.py"
    before["workload"]["n_items"] = before["split"]["repair"] = 1
    (tmp_path / "verification.json").write_text(json.dumps(before), encoding="utf-8")
    paths = ["model.orm.yaml", "model.py", "accepted.py", "candidate.py", "bindings.py", "model.verbalization.txt", "verification.json"]
    snapshot = {p: (tmp_path / p).read_bytes() for p in paths if (tmp_path / p).exists()}
    db = duckdb.connect()
    expected = db.execute("SELECT id FROM (VALUES (1,3),(2,8),(3,10)) t(id,cost) WHERE cost >= 8").fetchall()
    db.close()
    def execute(path):
        namespace = {}
        exec((tmp_path / "model.py").read_text(encoding="utf-8"), namespace)
        exec((tmp_path / path).read_text(encoding="utf-8"), namespace)
        return namespace["result"]
    assert execute("accepted.py") == expected
    def apply():
        model["object_types"] = model["object_types"][:1]
        (tmp_path / "model.orm.yaml").write_text(yaml.safe_dump(model), encoding="utf-8")
        (tmp_path / "model.py").write_text("Asset = [(1, 3), (2, 8), (3, 10)]\n", encoding="utf-8")
        cutoff = 10 if wrong_filter else 8
        (tmp_path / "candidate.py").write_text(f"result = [(a[0],) for a in Asset if a[1] >= {cutoff}]\n", encoding="utf-8")
        (tmp_path / "bindings.py").write_text("candidate\n", encoding="utf-8")
    def verify():
        assert (tmp_path / "accepted.py").read_bytes() == snapshot["accepted.py"]
        result = copy.deepcopy(before)
        result["items"][0].update(status="pass" if execute("candidate.py") == expected else "fail", pyrel="candidate.py")
        (tmp_path / "verification.json").write_text(json.dumps(result), encoding="utf-8")
        return result
    result = attempt(tmp_path, paths, before, apply, verify)
    assert result["accepted"] == (not wrong_filter)
    if wrong_filter:
        assert all((tmp_path / p).read_bytes() == content for p, content in snapshot.items())
        assert not (tmp_path / "candidate.py").exists()
    else:
        assert "SelectedAsset" not in (tmp_path / "model.py").read_text(encoding="utf-8")
        assert len(yaml.safe_load((tmp_path / "model.orm.yaml").read_text(encoding="utf-8"))["object_types"]) == 1
        assert execute("candidate.py") == expected
        assert (tmp_path / "accepted.py").read_bytes() == snapshot["accepted.py"]


def test_verifier_exception_restores_snapshot(tmp_path):
    (tmp_path / "model.py").write_text("baseline", encoding="utf-8")
    def apply():
        (tmp_path / "model.py").write_text("candidate", encoding="utf-8")
    def verify():
        raise RuntimeError("oracle unavailable")
    with pytest.raises(RuntimeError):
        attempt(tmp_path, ["model.py"], baseline(), apply, verify)
    assert (tmp_path / "model.py").read_text(encoding="utf-8") == "baseline"


def test_acceptance_cli_rejects_invalid_input_without_contents(tmp_path):
    import subprocess
    import sys
    bad = tmp_path / "bad.json"
    bad.write_text('{"PRIVATE_CONTENTS":', encoding="utf-8")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("acceptance.py")),
                             "--baseline", str(bad), "--candidate", str(bad)], capture_output=True, text=True)
    assert result.returncode == 2 and "PRIVATE_CONTENTS" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["accepted"] is False
