"""Metrics, conservative hints, static support, determinism, and CLI privacy."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


TOOL = Path(__file__).with_name("compaction_metrics.py")
SPEC = importlib.util.spec_from_file_location("compaction_metrics", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURE = TOOL.parent.parent / "evals" / "fixtures" / "compact"


@pytest.fixture
def model():
    return MODULE.load_mapping(FIXTURE / "model.orm.yaml")


def fixture_metrics(model):
    return MODULE.measure(model, MODULE.load_mapping(FIXTURE / "model.verification.json"),
                          verification_dir=FIXTURE)


def reasons(report, eid):
    return {row["reason"] for row in report["suspects"] if row["concept"] == eid}


def test_planted_defects_and_healthy_concept(model):
    report = fixture_metrics(model)
    assert report["concepts"] == 5  # value types are not concepts
    assert report["source_tables"] == 4
    assert report["derived_only_concepts"] == ["selected_asset"]
    assert report["support_coverage"]["status"] == "complete"
    assert reasons(report, "selected_asset") == {"single-item"}
    assert "flag-explosion" in reasons(report, "case")
    assert "table-mirror" in reasons(report, "record_detail")
    assert reasons(report, "asset") == set()
    assert report["flag_explosions"][0]["count"] == 4
    assert report["property_distribution"] == [
        {"properties": 1, "concepts": 3}, {"properties": 2, "concepts": 1},
        {"properties": 4, "concepts": 1}]


def test_no_pyrel_skips_support_not_zero_support(model):
    report = MODULE.measure(model)
    assert report["concept_support"] is None
    assert report["single_item_concepts"] is None
    assert all(row["reason"] != "single-item" for row in report["suspects"])
    assert report["support_coverage"]["status"] == "unavailable"


def test_partial_and_invalid_rewrites_are_explicit(model, tmp_path):
    (tmp_path / "a.py").write_text("model.select(SelectedAsset.cost)\n")
    (tmp_path / "bad.py").write_text("model.select(\n")
    verification = {"workload": {"n_items": 4}, "items": [
        {"id": "a", "pyrel": "a.py"}, {"id": "b", "pyrel": "missing.py"},
        {"id": "c", "pyrel": "bad.py"}, {"id": "d"}]}
    report = MODULE.measure(model, verification, verification_dir=tmp_path)
    assert report["support_coverage"] == {
        "status": "partial", "saved_items": 1, "expected_items": 4,
        "missing_items": ["b", "d"], "invalid_items": ["c"]}
    assert report["single_item_concepts"] == ["selected_asset"]
    assert not reasons(report, "selected_asset")


def test_support_counts_items_once_and_ignores_literals_comments_imports(model, tmp_path):
    (tmp_path / "a.py").write_text(
        '# SelectedAsset Asset\ntext = "SelectedAsset Asset secret-marker"\n'
        'from model import SelectedAsset as Chosen\n'
        'from model import Asset\nmodel.select(Chosen.cost, Chosen.cost)\n')
    report = MODULE.measure(model, {"items": [{"id": "a", "pyrel": "a.py"}]},
                            verification_dir=tmp_path)
    counts = {row["concept"]: row["count"] for row in report["concept_support"]}
    assert counts["selected_asset"] == 1 and counts["asset"] == 0
    assert "secret-marker" not in json.dumps(report)


def test_duplicate_signature_ignores_owner_ids_and_table(model):
    duplicate = copy.deepcopy(model["object_types"][0])
    duplicate.update(id="asset_archive", name="AssetArchive")
    duplicate["provenance"]["table"] = "ASSET_ARCHIVE"
    model["object_types"].append(duplicate)
    for fact in list(model["fact_types"][:2]):
        new = copy.deepcopy(fact)
        new["id"] += "_archive"
        new["roles"][0] = {"object_type": "asset_archive", "role_name": "archive"}
        model["fact_types"].append(new)
    report = MODULE.measure(model)
    assert ["asset", "asset_archive"] in report["duplicate_structure_concepts"]
    assert reasons(report, "asset_archive") == {"duplicate-structure"}


def test_empty_concepts_do_not_duplicate_and_unbound_is_not_derived(model):
    model["fact_types"] = []
    model["object_types"][0].pop("provenance")
    report = MODULE.measure(model)
    assert report["duplicate_structure_concepts"] == []
    assert report["unbound_concepts"] == ["asset", "selected_asset"]
    assert report["derived_only_concepts"] == ["selected_asset"]
    assert report["suspects"] == []


@pytest.mark.parametrize("change", ["composite", "proposed", "same-table", "shared-table"])
def test_mirror_requires_confirmed_one_to_one_separate_table_bindings(model, change):
    link = model["fact_types"][-1]
    if change == "composite":
        link["constraints"][0]["roles"] = ["record", "detail"]
    elif change == "proposed":
        link["constraints"][1]["status"] = "proposed"
    elif change == "same-table":
        model["object_types"][4]["provenance"]["table"] = "RECORD"
    else:
        model["object_types"][0]["provenance"]["table"] = "RECORD"
    assert MODULE.measure(model)["table_mirrors"] == []


def test_boolean_value_properties_count_toward_flag_explosion(model):
    model["object_types"].append({"id": "boolean", "name": "BooleanValue", "kind": "value",
                                  "primitive": "Boolean"})
    model["fact_types"][3]["roles"].append({"object_type": "boolean", "role_name": "pending"})
    report = MODULE.measure(model)
    assert report["flag_explosions"][0]["count"] == 4
    assert next(row["count"] for row in report["unary_flags_per_concept"]
                if row["concept"] == "case") == 3


def test_declared_and_digest_tables_multibinding_and_determinism(model):
    model["object_types"][0]["provenance"]["tables"] = ["ASSET_HISTORY", "ASSET"]
    digest = {"tables": [{"table": "UNMODELED"}], "workload": {"n_items": 3}}
    first = MODULE.measure(model, digest=digest)
    model["object_types"].reverse()
    model["fact_types"].reverse()
    second = MODULE.measure(model, digest=digest)
    assert first == second
    table_counts = {row["table"]: row["count"] for row in first["concepts_per_source_table"]}
    assert table_counts["ASSET"] == 1 and table_counts["ASSET_HISTORY"] == 1
    assert table_counts["UNMODELED"] == 0
    assert [row["priority"] for row in first["suspects"]] == sorted(
        [row["priority"] for row in first["suspects"]], reverse=True)


def cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                          capture_output=True, text=True)


def test_cli_deterministic_and_private(model, tmp_path):
    model["object_types"][0]["provenance"]["user_quote"] = "secret-marker"
    model["constraints"] = [{"expression": "SELECT 'secret-marker'"}]
    model_path = tmp_path / "model.yaml"
    model_path.write_text(yaml.safe_dump(model))
    digest = tmp_path / "digest.yaml"
    digest.write_text('terms: [{term: secret-marker}]\n')
    output = tmp_path / "compaction.json"
    args = ["--model", model_path, "--verification", FIXTURE / "model.verification.json",
            "--digest", digest, "--out", output]
    result = cli(*args)
    assert result.returncode == 0 and result.stdout == ""
    first = output.read_bytes()
    assert b"secret-marker" not in first
    assert cli(*args).returncode == 0 and first == output.read_bytes()


def test_cli_errors_do_not_echo_input_and_cannot_overwrite(model, tmp_path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text('secret-marker: [\n')
    result = cli("--model", invalid, "--out", tmp_path / "output.json")
    assert result.returncode == 2
    assert "secret-marker" not in result.stderr + result.stdout
    valid = tmp_path / "model.yaml"
    valid.write_text(yaml.safe_dump(model))
    before = valid.read_bytes()
    assert cli("--model", valid, "--out", valid).returncode == 2
    assert valid.read_bytes() == before


def test_cli_argument_errors_do_not_echo_arbitrary_text():
    for args in [("--model", "file", "--unknown", "secret-marker"),
                 ("--out", "secret-marker")]:
        result = cli(*args)
        assert result.returncode == 2
        assert json.loads(result.stderr) == {"error": "invalid-arguments"}
        assert "secret-marker" not in result.stderr + result.stdout


def test_unresolved_roles_fail(model):
    model["fact_types"][0]["roles"][0]["object_type"] = "missing"
    with pytest.raises(ValueError):
        MODULE.measure(model)
