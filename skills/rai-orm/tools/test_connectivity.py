"""Synthetic connectivity, containment, proposal, and privacy checks."""

import json
from pathlib import Path
import subprocess
import sys

import duckdb
import pytest
import yaml

from connectivity import analyze


TOOL = Path(__file__).with_name("connectivity.py")


@pytest.fixture
def fixture(tmp_path):
    model = {"version": 1, "object_types": [
        {"id": "alpha", "name": "Alpha", "kind": "entity", "reference": {"mode": "popular"},
         "provenance": {"tables": ["ALPHA_FEED", "ALPHA_ARCHIVE"]}},
        {"id": "beta", "name": "Beta", "kind": "entity", "reference": {"mode": "popular"},
         "provenance": {"table": "BETA_FEED"}}], "fact_types": []}
    db_path = tmp_path / "synthetic.duckdb"
    db = duckdb.connect(str(db_path))
    for table in ("ALPHA_FEED", "BETA_FEED"):
        db.execute(f'CREATE TABLE "{table}" (peer_key VARCHAR, partial_key VARCHAR, unique_key VARCHAR)')
        rows = [(f"PRIVATE_PEER_{i}", f"PRIVATE_PART_{i if table == 'ALPHA_FEED' else i + 4}",
                 f"PRIVATE_{table}_{i}") for i in range(10)]
        db.executemany(f'INSERT INTO "{table}" VALUES (?, ?, ?)', rows)
    db.execute("INSERT INTO ALPHA_FEED VALUES (NULL, NULL, NULL)")
    db.execute("CREATE TABLE ALPHA_ARCHIVE AS SELECT * FROM ALPHA_FEED")
    db.close()
    model_path = tmp_path / "model.orm.yaml"
    model_path.write_text(yaml.safe_dump(model))
    return model, model_path, db_path


def cli(tmp_path, model, db=None, digest=None, *extras):
    args = [sys.executable, str(TOOL), "--model", str(model), "--out", str(tmp_path / "connectivity.json"),
            "--proposals", str(tmp_path / "connectivity.proposals.yaml")]
    if db:
        args += ["--db", str(db)]
    if digest:
        args += ["--digest", str(digest)]
    return subprocess.run(args + list(extras), capture_output=True, text=True)


def test_hidden_fk_partial_and_no_values(fixture, tmp_path):
    model, path, db_path = fixture
    assert cli(tmp_path, path, db_path).returncode == 0
    result = json.loads((tmp_path / "connectivity.json").read_text())
    assert result["summary"]["components"] == 2
    assert result["summary"]["isolated"] == 2
    assert result["components"][0]["tables"] == ["ALPHA_ARCHIVE", "ALPHA_FEED"]
    candidates = [c for c in result["candidates"] if c["left"]["table"] == "ALPHA_FEED"]
    hidden = next(c for c in candidates if c["left"]["columns"] == c["right"]["columns"] == ["peer_key"])
    partial = next(c for c in candidates if c["left"]["columns"] == c["right"]["columns"] == ["partial_key"])
    assert hidden["classification"] == "fk-like"
    assert hidden["evidence"]["distinct_left"] == 10
    assert hidden["evidence"]["null_rate_left"] == round(1 / 11, 6)
    assert partial["classification"] == "partial" and partial["partial"]
    assert partial["evidence"]["shared_distinct"] == 6
    assert partial["evidence"]["containment_left"] == 0.6
    assert all(c["classification"] != "none" for c in result["candidates"])
    assert result["summary"]["candidates_by_class"]["none"] > 0
    assert result["summary"]["candidates_by_class"]["fk-like"] == 2
    assert result["summary"]["candidates_by_class"]["partial"] == 2
    assert result["summary"]["comparison_cap"] == 5000
    assert not result["summary"]["comparison_cap_reached"]
    assert result["summary"]["candidates_untested"] == 0
    for file in ("connectivity.json", "connectivity.proposals.yaml"):
        assert "PRIVATE_" not in (tmp_path / file).read_text()
    proposals = yaml.safe_load((tmp_path / "connectivity.proposals.yaml").read_text())["fact_types"]
    assert proposals and all(p["source"] == "data" and p["status"] == "proposed" for p in proposals)
    assert all(len(p["roles"]) == 2 and p["reading"].startswith("{") for p in proposals)
    repaired = {**model, "fact_types": proposals}
    assert analyze(repaired)[0]["verdict"] == "connected"


def test_required_partial_gap_and_merged(fixture, tmp_path):
    _, path, db = fixture
    digest = {"join_edges": [
        {"id": "je_partial", "left": {"table": "ALPHA_FEED", "columns": ["partial_key"]},
         "right": {"table": "BETA_FEED", "columns": ["partial_key"]}, "support": 7},
        {"id": "je_merged", "left": {"table": "ALPHA_FEED", "columns": ["peer_key"]},
         "right": {"table": "ALPHA_ARCHIVE", "columns": ["peer_key"]}, "support": 2}]}
    digest_path = tmp_path / "digest.yaml"
    digest_path.write_text(yaml.safe_dump(digest))
    assert cli(tmp_path, path, db, digest_path, "--fail-on-required-gap").returncode == 2
    result = json.loads((tmp_path / "connectivity.json").read_text())
    assert result["verdict"] == "required-gaps"
    assert len(result["required_gaps"]) == 1
    gap = result["required_gaps"][0]
    assert gap["support"] == 7 and gap["partial"] and gap["best_candidate"]
    assert {j["id"]: j["status"] for j in result["join_checks"]}["je_merged"] == "merged"
    proposals = yaml.safe_load((tmp_path / "connectivity.proposals.yaml").read_text())["fact_types"]
    p = next(p for p in proposals if p.get("partial"))
    assert p["provenance"]["evidence"]["containment_left"] == 0.6


def test_determinism_and_no_db(fixture, tmp_path):
    _, path, db = fixture
    assert cli(tmp_path, path, db).returncode == 0
    outputs = [(tmp_path / f).read_bytes() for f in ("connectivity.json", "connectivity.proposals.yaml")]
    assert cli(tmp_path, path, db).returncode == 0
    assert outputs == [(tmp_path / f).read_bytes() for f in ("connectivity.json", "connectivity.proposals.yaml")]
    assert cli(tmp_path, path).returncode == 0
    assert json.loads((tmp_path / "connectivity.json").read_text())["candidates"] == []


def test_composite_gap_and_cap(fixture):
    model, _, db_path = fixture
    digest = {"join_edges": [{"id": "je_tuple", "left": {"table": "ALPHA_FEED", "columns": ["peer_key", "partial_key"]},
                              "right": {"table": "BETA_FEED", "columns": ["peer_key", "partial_key"]}, "support": 1}]}
    with duckdb.connect(str(db_path), read_only=True) as db:
        result, _ = analyze(model, digest, db, max_comparisons=1)
        gap_id = result["required_gaps"][0]["best_candidate"]
        candidate = next(c for c in result["candidates"] if c["id"] == gap_id)
        assert candidate["evidence"]["shared_distinct"] == 0
        assert candidate["classification"] == "none"
        assert result["summary"]["value_comparisons"] == 1
        assert result["summary"]["comparison_cap_reached"]
        assert result["summary"]["candidates_untested"] > 0
        assert all(c["test_status"] != "comparison-cap" for c in result["candidates"])
        assert result["join_checks"][0]["candidate"] == gap_id
        assert result["summary"]["candidates_by_class"]["none"] == result["summary"]["candidates_untested"] + 1


def test_nary_subtype_and_self_relationships():
    model = {"object_types": [{"id": n, "name": n.upper(), "kind": "entity", "subtype_of": ["a"] if n == "d" else []}
                              for n in "abcd"], "fact_types": [
        {"id": "ternary", "roles": [{"object_type": n} for n in "abc"]},
        {"id": "self", "roles": [{"object_type": "a"}, {"object_type": "a"}]}]}
    result, _ = analyze(model)
    assert result["verdict"] == "connected"
    assert result["summary"]["relationships"] == 3
    assert result["relationships_per_concept"][0]["relationships"] == 3


def test_missing_binding_stays_required_gap(fixture):
    model, _, _ = fixture
    digest = {"join_edges": [{"id": "missing", "left": {"table": "ALPHA_FEED", "columns": ["peer_key"]},
                              "right": {"table": "UNBOUND", "columns": ["peer_key"]}, "support": 1}]}
    result, proposals = analyze(model, digest)
    assert result["required_gaps"][0]["right_concepts"] == []
    assert result["candidates"][0]["test_status"] == "no-db"
    assert proposals["fact_types"] == []


def test_empty_null_only_keys_and_quoted_identifiers():
    model = {"object_types": [{"id": n.lower(), "name": n, "kind": "entity", "provenance": {"table": n + "_FEED"}} for n in ("Alpha", "Beta")]}
    with duckdb.connect() as db:
        for name in ("Alpha", "Beta"):
            db.execute(f'CREATE TABLE "{name}_FEED" ("peer""key" INTEGER)')
        db.execute('INSERT INTO "Alpha_FEED" VALUES (NULL)')
        result, proposals = analyze(model, db=db)
        assert result["candidates"] == []
        assert result["summary"]["candidates_by_class"] == {"fk-like": 0, "partial": 0, "none": 1}
        assert result["summary"]["value_comparisons"] == 0
        assert not result["summary"]["comparison_cap_reached"]
        assert proposals["fact_types"] == []


def test_declared_key_role_enables_dissimilar_names():
    model = {"object_types": [{"id": n.lower(), "name": n, "kind": "entity", "provenance": {"table": n + "_FEED"}} for n in ("Alpha", "Beta")],
             "source_bindings": [{"table": "Alpha_FEED", "object_type": "alpha", "key_columns": ["identifier"]}]}
    with duckdb.connect() as db:
        db.execute('CREATE TABLE "Alpha_FEED" AS SELECT i AS identifier FROM range(10) t(i)')
        db.execute('CREATE TABLE "Beta_FEED" AS SELECT i AS xyz FROM range(10) t(i)')
        result, _ = analyze(model, db=db)
        assert result["candidates"][0]["classification"] == "fk-like"
        assert result["candidates"][0]["evidence"]["name_similarity"] < 0.65


def test_prefilter_constants_nulls_and_incompatible_required_pairs():
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in ("a", "b")]}
    digest = {"join_edges": [{"id": col, "left": {"table": "a", "columns": [col]},
                              "right": {"table": "b", "columns": [col]}}
                             for col in ("constant_key", "null_key", "wrong_type_key")]}
    with duckdb.connect() as db:
        db.execute("CREATE TABLE a AS SELECT 1 AS constant_key, NULL::INTEGER AS null_key, 1 AS wrong_type_key")
        db.execute("CREATE TABLE b AS SELECT 1 AS constant_key, NULL::INTEGER AS null_key, 'one' AS wrong_type_key")
        result, _ = analyze(model, digest, db, max_comparisons=0)
    assert result["summary"]["value_comparisons"] == result["summary"]["candidates_untested"] == 0
    assert not result["summary"]["comparison_cap_reached"]
    assert result["summary"]["candidates_by_class"]["none"] == 3
    candidates = {c["id"]: c for c in result["candidates"]}
    for gap in result["required_gaps"]:
        c = candidates[gap["best_candidate"]]
        assert c["classification"] == "none"
        if gap["id"] == "wrong_type_key":
            assert c["test_status"] == "incompatible-or-missing"
        else:
            assert c["test_status"] == "degenerate-columns"
            assert c["evidence"]["distinct_left"] == (1 if gap["id"] == "constant_key" else 0)
            assert "shared_distinct" not in c["evidence"]


def test_required_gap_none_evidence_survives_without_cap(fixture):
    model, _, db_path = fixture
    digest = {"join_edges": [{"id": "disjoint", "left": {"table": "ALPHA_FEED", "columns": ["unique_key"]},
                              "right": {"table": "BETA_FEED", "columns": ["unique_key"]}}]}
    with duckdb.connect(str(db_path), read_only=True) as db:
        result, _ = analyze(model, digest, db)
    gap = result["required_gaps"][0]
    candidate = next(c for c in result["candidates"] if c["id"] == gap["best_candidate"])
    assert candidate["classification"] == "none"
    assert candidate["evidence"]["distinct_left"] == 10
    assert candidate["evidence"]["shared_distinct"] == 0
    assert all(c["required_gaps"] for c in result["candidates"] if c["classification"] == "none")
    assert result["summary"]["candidates_by_class"]["none"] > 1


def test_isolated_candidates_precede_other_components_and_exact_cap():
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}}
                              for n in ("a", "a2", "b", "b2", "z")],
             "fact_types": [{"id": n, "roles": [{"object_type": n}, {"object_type": n + "2"}]} for n in ("a", "b")]}
    with duckdb.connect() as db:
        for name in ("a", "a2", "b", "b2", "z"):
            db.execute(f'CREATE TABLE "{name}" AS SELECT i AS peer_key FROM range(10) t(i)')
        result, _ = analyze(model, db=db, max_comparisons=1)
        assert len(result["candidates"]) == 1
        first = result["candidates"][0]
        assert "z" in (first["left"]["table"], first["right"]["table"])
        assert result["summary"]["candidates_untested"] == 7
        assert result["summary"]["candidates_by_class"] == {"fk-like": 1, "partial": 0, "none": 7}
        digest = {"join_edges": [{"id": "required", "left": {"table": "a", "columns": ["peer_key"]},
                                  "right": {"table": "b", "columns": ["peer_key"]}}]}
        required, _ = analyze(model, digest, db, max_comparisons=1)
        assert required["candidates"][0]["required_gaps"] == ["required"]
        assert required["candidates"][0]["test_status"] == "tested"
        full, _ = analyze(model, db=db, max_comparisons=8)
        assert full["summary"]["value_comparisons"] == 8
        assert not full["summary"]["comparison_cap_reached"]
        assert full["summary"]["candidates_untested"] == 0
        capped, _ = analyze(model, digest, db, max_comparisons=0)
        assert capped["summary"]["candidates_untested"] == 8
        assert capped["candidates"][0]["test_status"] == "comparison-cap"
        assert capped["required_gaps"][0]["best_candidate"] == capped["candidates"][0]["id"]


def test_uniqueness_uses_named_roles_not_scalar_constraint_provenance():
    from connectivity import model_graph
    model = {"object_types": [
        {"id": "a", "name": "A", "kind": "entity", "provenance": {"table": "a", "pk_column": "id"}},
        {"id": "value", "name": "Value", "kind": "value"}],
        "fact_types": [{"id": "scalar", "roles": [
            {"object_type": "a", "role_name": "owner", "provenance": {"table": "a", "column": "id"}},
            {"object_type": "value", "role_name": "value", "provenance": {"table": "a", "column": "description"}}],
            "constraints": [{"type": "uniqueness", "roles": ["owner"],
                             "provenance": {"table": "a", "column": "description"}}]}],
        "constraints": [{"type": "uniqueness", "role_refs": [{"fact_type": "scalar", "role": "owner"}],
                         "provenance": {"table": "a", "columns": ["description", "other"]}}]}
    assert dict(model_graph(model)[4]) == {"a": {("id",)}}


@pytest.mark.parametrize("distinct,rows,declared,expected", [
    (5, 100, False, None), (5, 100, True, None),
    (10, 100, False, "partial"), (10, 100, True, "fk-like"),
    (98, 100, False, "fk-like"), (97, 100, False, "partial"),
])
def test_cardinality_and_unique_side(distinct, rows, declared, expected):
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}}
                              for n in ("a", "b")],
             "source_bindings": [{"table": "a", "object_type": "a", "key_columns": ["KEY"] if declared else []}]}
    digest = {"join_edges": [{"id": "required", "left": {"table": "a", "columns": ["key"]},
                             "right": {"table": "b", "columns": ["key"]}}]}
    with duckdb.connect() as db:
        for n in ("a", "b"):
            db.execute(f'CREATE TABLE {n} AS SELECT i % {distinct} AS key FROM range({rows}) t(i)')
        result, proposals = analyze(model, db=db)
        assert [c["classification"] for c in result["candidates"]] == ([expected] if expected else [])
        assert bool(proposals["fact_types"]) == (expected == "fk-like")
        if distinct < 10:
            assert result["summary"]["value_comparisons"] == 0
            required, _ = analyze(model, digest, db)
            assert required["candidates"][0]["classification"] == ("fk-like" if declared else "partial")
            assert required["summary"]["value_comparisons"] == 1


@pytest.mark.parametrize("arity", [2, 3])
def test_objectification_reaches_entity_roles(arity):
    roles = list("abc"[:arity])
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}}
                              for n in roles + ["enrollment"]] + [{"id": "scalar", "kind": "value"}],
             "fact_types": [{"id": "enrolled", "objectified_as": "enrollment",
                             "roles": [{"object_type": n} for n in roles + ["scalar"]]}]}
    digest = {"join_edges": [{"id": n, "left": {"table": "enrollment", "columns": [n]},
                             "right": {"table": n, "columns": ["id"]}} for n in roles]}
    result, _ = analyze(model, digest)
    assert result["summary"]["isolated"] == 0
    assert result["summary"]["relationships"] == 1
    assert all(c["relationships"] == 1 for c in result["relationships_per_concept"])
    assert result["required_gaps"] == []
    assert all(j["status"] == "reachable" for j in result["join_checks"])
    model["fact_types"][0]["status"] = "rejected"
    assert len(analyze(model, digest)[0]["required_gaps"]) == arity


def test_mixed_case_digest_deduplicates_metadata_columns(fixture):
    model, _, db_path = fixture
    digest = {"join_edges": [{"id": "upper", "left": {"table": "alpha_feed", "columns": ["PEER_KEY"]},
                             "right": {"table": "beta_feed", "columns": ["Peer_Key"]}},
                            {"id": "lower", "left": {"table": "BETA_FEED", "columns": ["peer_key"]},
                             "right": {"table": "ALPHA_FEED", "columns": ["peer_key"]}}]}
    with duckdb.connect(str(db_path), read_only=True) as db:
        result, proposals = analyze(model, digest, db)
        candidates = [c for c in result["candidates"] if c["required_gaps"]]
        assert len(candidates) == 1
        assert candidates[0]["required_gaps"] == ["lower", "upper"]
        assert candidates[0]["classification"] == "fk-like"
        assert candidates[0]["left"]["columns"] == ["peer_key"]
        automatic = [p for p in proposals["fact_types"] if p["provenance"]["required_gaps"]]
        exploratory = [p for p in proposals["fact_types"] if not p["provenance"]["required_gaps"]]
        assert len(automatic) == len(exploratory) == 1
        assert automatic[0]["provenance"]["left"]["table"] == "ALPHA_FEED"


@pytest.mark.parametrize("location", ["rejected_proposals", "fact_types", "ids", "renamed"])
def test_rejected_link_is_not_proposed_again(fixture, location):
    model, _, db_path = fixture
    with duckdb.connect(str(db_path), read_only=True) as db:
        _, first = analyze(model, db=db)
        rejected = first["fact_types"][0]
        original_id = rejected["id"]
        rejected["status"] = "rejected"
        if location == "ids":
            model["rejected_proposals"] = [original_id]
        elif location == "renamed":
            rejected["id"] = "archived-custom-id"
            for side in ("left", "right"):
                rejected["provenance"][side]["columns"] = [c.upper() for c in rejected["provenance"][side]["columns"]]
            model["rejected_proposals"] = [rejected]
        else:
            model[location] = [rejected]
        result, second = analyze(model, db=db)
    assert result["summary"]["components"] == 2
    assert len(second["fact_types"]) == len(first["fact_types"]) - 1
    assert original_id not in {p["id"] for p in second["fact_types"]}


def test_read_yaml_explicit_utf8(tmp_path, monkeypatch):
    from connectivity import read_yaml
    path = tmp_path / "model.yaml"
    path.write_text("name: Εγγραφή\n", encoding="utf-8")
    original = Path.read_text
    def read(self, *args, **kwargs):
        assert kwargs.get("encoding") == "utf-8"
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    assert read_yaml(path) == {"name": "Εγγραφή"}


def test_repair_digest_excludes_holdout_required_gaps(tmp_path):
    digest_tool = TOOL.parents[2] / "rai-orm-from-workload" / "tools" / "workload_digest.py"
    workload = tmp_path / "workload.json"
    workload.write_text(json.dumps([
        {"id": "repair", "sql": "SELECT a.id FROM a JOIN b ON a.id = b.id"},
        {"id": "holdout", "sql": "SELECT b.id FROM b JOIN c ON b.id = c.id"}]), encoding="utf-8")
    verification = tmp_path / "model.verification.json"
    verification.write_text(json.dumps({"items": [{"id": n, "split": n} for n in ("repair", "holdout")]}), encoding="utf-8")
    model = tmp_path / "model.orm.yaml"
    model.write_text(yaml.safe_dump({"object_types": [
        {"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in "abc"]}), encoding="utf-8")
    gaps = {}
    for mode in ("repair", "full", "legacy"):
        digest = tmp_path / (mode + ".digest.yaml")
        if mode != "legacy":
            args = [sys.executable, str(digest_tool), "--input", str(workload), "--out", str(digest), "--no-timestamp"]
            if mode == "repair":
                args += ["--split", "repair", "--verification", str(verification)]
            assert subprocess.run(args, capture_output=True).returncode == 0
        else:
            old = yaml.safe_load((tmp_path / "full.digest.yaml").read_text(encoding="utf-8"))
            old.pop("item_contributions")
            digest.write_text(yaml.safe_dump(old), encoding="utf-8")
        assert cli(tmp_path, model, digest=digest).returncode == 0
        result = json.loads((tmp_path / "connectivity.json").read_text(encoding="utf-8"))
        gaps[mode] = {(g["left"]["table"], g["right"]["table"]) for g in result["required_gaps"]}
    assert gaps["repair"] == {("a", "b")}
    assert gaps["full"] == gaps["legacy"] == {("a", "b"), ("b", "c")}


@pytest.mark.parametrize("key_source", ["binding", "provenance", "constraint"])
def test_composite_key_members_are_not_unique(key_source):
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in "ab"]}
    columns = ["group_id", "member_id"]
    if key_source == "binding":
        model["source_bindings"] = [{"table": n, "object_type": n, "key_columns": columns} for n in "ab"]
    elif key_source == "provenance":
        for obj in model["object_types"]:
            obj["provenance"]["pk_columns"] = columns
    else:
        model["fact_types"] = [{"id": n, "roles": [
            {"object_type": n, "role_name": c, "provenance": {"table": n, "column": c}} for c in columns],
            "constraints": [{"type": "uniqueness", "roles": columns}]} for n in "ab"]
    digest = {"join_edges": [{"id": "tuple", "left": {"table": "a", "columns": columns},
                              "right": {"table": "b", "columns": columns}}]}
    with duckdb.connect() as db:
        for n in "ab":
            db.execute(f"CREATE TABLE {n} AS SELECT i // 10 AS group_id, i % 10 AS member_id FROM range(100) t(i)")
        result, _ = analyze(model, digest, db)
    singles = [c for c in result["candidates"] if len(c["left"]["columns"]) == 1]
    assert len(singles) == 4
    assert all(c["classification"] == "partial" for c in singles)
    assert all(c["evidence"]["distinct_left"] == c["evidence"]["distinct_right"] == 10 for c in singles)
    assert next(c for c in result["candidates"] if c["required_gaps"])["classification"] == "fk-like"


@pytest.mark.parametrize("complete_key", [False, True])
def test_separate_declared_keys_do_not_declare_a_tuple(complete_key):
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in "ab"],
             "source_bindings": [{"table": n, "object_type": n, "key_columns": [c]} for n in "ab" for c in ("x", "y")]}
    if complete_key:
        model["source_bindings"] = [{"table": "a", "object_type": "a", "key_columns": ["x", "y"]}]
    digest = {"join_edges": [{"id": "tuple", "left": {"table": "a", "columns": ["x", "y"]},
                              "right": {"table": "b", "columns": ["x", "y"]}}]}
    with duckdb.connect() as db:
        for n in "ab":
            db.execute(f"CREATE TABLE {n} AS SELECT i % 10 AS x, i % 10 AS y FROM range(100) t(i)")
        result, _ = analyze(model, digest, db)
    assert next(c for c in result["candidates"] if c["required_gaps"])["classification"] == ("fk-like" if complete_key else "partial")


def test_rejected_link_case_change_without_database():
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in "ab"]}
    digest = {"join_edges": [{"id": "gap", "left": {"table": "a", "columns": ["key"]},
                             "right": {"table": "b", "columns": ["key"]}}]}
    _, first = analyze(model, digest)
    assert len(first["fact_types"]) == 1
    model["rejected_proposals"] = first["fact_types"]
    for side in ("left", "right"):
        digest["join_edges"][0][side]["columns"] = ["KEY"]
        digest["join_edges"][0][side]["table"] = digest["join_edges"][0][side]["table"].upper()
    result, second = analyze(model, digest)
    assert len(result["required_gaps"]) == 1
    assert second["fact_types"] == []


def test_cap_counts_distinct_required_gaps_and_isolated_concepts():
    model = {"object_types": [{"id": n, "name": n, "kind": "entity", "provenance": {"table": n}} for n in "abc"]}
    digest = {"join_edges": [{"id": str(i), "left": {"table": "a", "columns": ["key"]},
                             "right": {"table": "b", "columns": ["key"]}} for i in range(2)]}
    with duckdb.connect() as db:
        for n in "abc":
            db.execute(f"CREATE TABLE {n} AS SELECT i AS key FROM range(10) t(i)")
        capped, _ = analyze(model, digest, db, max_comparisons=0)
        partial, _ = analyze(model, digest, db, max_comparisons=1)
        full, _ = analyze(model, digest, db, max_comparisons=3)
    assert capped["summary"]["candidates_untested"] == 3
    assert capped["summary"]["required_gaps_untested"] == 2
    assert capped["summary"]["isolated_concepts_untested"] == 3
    assert partial["summary"]["required_gaps_untested"] == 0
    assert partial["summary"]["isolated_concepts_untested"] == 3
    assert full["summary"]["required_gaps_untested"] == full["summary"]["isolated_concepts_untested"] == 0
    from report import build_report
    issue = next(i for i in build_report(model, connectivity=capped)["issues"] if i["id"] == "COMPARISON_CAP_REACHED")
    assert "untested required gaps: 2" in issue["next_action"]
    assert "untested isolated concepts: 3" in issue["next_action"]


def test_schema_handoff_limits_one_shot_to_repair_gaps():
    skill = (TOOL.parents[2] / "rai-orm-from-schema" / "SKILL.md").read_text(encoding="utf-8")
    step = skill.split("### Step 9g", 1)[1].split("### Step 10", 1)[0]
    assert "apply only required-gap proposals" in step
    assert "list exploratory proposals for review and never auto-apply them" in step
    assert "repair-set digest, never the holdout digest" in step
    assert "../rai-orm/references/connectivity.md" in step
