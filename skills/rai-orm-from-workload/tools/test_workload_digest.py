"""Contract and regression tests for the workload digest CLI."""

import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


TOOL = Path(__file__).with_name("workload_digest.py")
FIXTURE = TOOL.parent.parent / "evals" / "fixtures" / "campus"
SPEC = importlib.util.spec_from_file_location("workload_digest", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_digest(source, output, *flags):
    result = subprocess.run([sys.executable, str(TOOL), "--input", str(source),
                             "--out", str(output), "--no-timestamp", *map(str, flags)],
                            capture_output=True, text=True,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    return yaml.safe_load(output.read_text())


@pytest.fixture
def campus(tmp_path):
    return run_digest(FIXTURE / "workload.sql.json", tmp_path / "digest.yaml",
                      "--schema", FIXTURE / "schema.sql")


def test_pairs_sql_equivalence(campus, tmp_path):
    pairs = run_digest(FIXTURE / "workload.pairs.json", tmp_path / "pairs.yaml",
                       "--schema", FIXTURE / "schema.sql")
    assert {k: v for k, v in campus.items() if k != "workload"} == {
        k: v for k, v in pairs.items() if k != "workload"}
    assert pairs["workload"]["kind"] == "pairs"
    assert pairs["workload"]["n_questions"] == 12
    assert "terms" not in pairs


def test_campus_join_edges(campus):
    edges = {tuple(sorted((f"{r['left']['table']}.{r['left']['columns'][0]}",
                            f"{r['right']['table']}.{r['right']['columns'][0]}"))): r
             for r in campus["join_edges"]}
    expected = [
        ("ENROLLMENT.SUBJECT_ID", "SUBJECT.ID", 4, True),
        ("ENROLLMENT.LEARNER_NO", "STUDENT.ID", 2, False),
        ("ENROLLMENT.LEARNER_NO", "STUDENT_DIRECTORY.ID", 1, False),
        ("SUBJECT.DEPT_CODE", "DEPARTMENT.CODE", 2, False),
        ("STUDENT.HOME_DEPT", "STAFF.DEPT_CODE", 1, False),
        ("STUDENT.HOME_DEPT", "DEPARTMENT.CODE", 1, False),
    ]
    assert len(edges) == 6
    for left, right, support, fk in expected:
        edge = edges[tuple(sorted((left, right)))]
        assert edge["support"] == support
        assert edge["declared_fk"] is fk
        assert edge["kinds"] == {"inner": support}


def test_campus_expressions_filters_grain(campus):
    assert len(campus["expressions"]) == 1
    expression = campus["expressions"][0]
    assert expression["kind"] == "aggregate-ratio"
    assert expression["support"] == 2
    assert "?" in expression["template"] and "50" not in expression["template"]
    filters = {(r["table"], r["column"]): r for r in campus["filter_columns"]}
    level = filters["SUBJECT", "LEVEL"]
    assert (level["operators"]["eq"], level["distinct_literals"], level["support"]) == (3, 2, 3)
    assert filters["ENROLLMENT", "TERM"]["operators"]["eq"] == 1
    assert any(r["table"] == "ENROLLMENT" and "LEARNER_NO" in r["columns"]
               and r["evidence"]["count_distinct"] == 1 for r in campus["grain_keys"])
    assert campus["unresolved"] == []
    serialized = yaml.safe_dump(campus)
    for literal in ("2024A", "UG", "PG", "50"):
        assert literal not in serialized


def test_questions_only(tmp_path):
    result = run_digest(FIXTURE / "workload.questions.txt", tmp_path / "questions.yaml")
    assert list(result) == ["workload", "item_contributions"]
    assert result["workload"]["kind"] == "questions"
    assert result["workload"]["n_items"] == 12
    assert result["workload"]["n_questions"] == 12
    assert "dialect" not in result["workload"]


def test_parse_errors_non_select_and_support(tmp_path):
    source = tmp_path / "items.json"
    source.write_text(json.dumps([
        {"id": "bad", "sql": "SELECT FROM"},
        {"sql": "DELETE FROM a"},
        {"sql": "SELECT x, x FROM a; SELECT x FROM a"},
    ]))
    result = run_digest(source, tmp_path / "digest.yaml")
    assert result["workload"]["parse_errors"] == ["bad"]
    assert result["workload"]["n_parsed"] == 3
    assert result["workload"]["skipped_non_select"] == 1
    assert result["tables"] == [{"table": "A", "support": 1}]
    assert result["columns"][0]["support"] == 1
    assert result["columns"][0]["roles"]["select"] == 1
    assert "unresolved" not in result


def test_determinism_expected_digest_and_sorting(campus, tmp_path):
    outputs = [tmp_path / "first.yaml", tmp_path / "second.yaml"]
    for output in outputs:
        run_digest(FIXTURE / "workload.sql.json", output, "--schema", FIXTURE / "schema.sql")
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    expected = FIXTURE.parent.parent / "expected" / "campus.sql.digest.yaml"
    assert outputs[0].read_bytes() == expected.read_bytes()
    assert "generated_at" not in campus["workload"]
    digest = MODULE.Digest(MODULE.Schema(None, "sqlite"), "sqlite")
    for section in ("tables", "columns", "join_edges", "grain_keys", "filter_columns", "expressions"):
        rows = campus[section]
        assert rows == sorted(rows, key=lambda r: (-r["support"], digest.name_key(r)))


@pytest.mark.parametrize("suffix,text,kind,n_items", [
    (".sql", "SELECT ';' FROM a; -- semicolon ;\n SELECT x FROM a;", "sql", 2),
    (".csv", 'query_text,question\n"SELECT x FROM a",Which objects?\n', "pairs", 1),
    (".csv", 'query\n"SELECT x\nFROM a"\n', "sql", 1),
    (".json", '[{"input":"Which objects?","output":"SELECT x FROM a"}]', "pairs", 1),
    (".json", '[{"question":"Which objects?"}]', "questions", 1),
])
def test_input_shapes(tmp_path, suffix, text, kind, n_items):
    source = tmp_path / ("input" + suffix)
    source.write_text(text)
    result = run_digest(source, tmp_path / "result.yaml")
    assert result["workload"]["kind"] == kind
    assert result["workload"]["n_items"] == n_items
    if kind != "questions":
        assert result["workload"]["n_parsed"] == n_items


def test_default_error_id_and_explicit_kind(tmp_path):
    source = tmp_path / "input.json"
    source.write_text('[{"sql":"SELECT FROM","question":"Which objects?"}]')
    result = run_digest(source, tmp_path / "digest.yaml", "--kind", "sql")
    assert result["workload"]["kind"] == "sql"
    assert result["workload"]["parse_errors"] == ["i0001"]


def test_composite_joins_using_where_and_case_preservation(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text('CREATE TABLE "Alpha" ("X" INT, "Y" INT, FOREIGN KEY ("X", "Y") REFERENCES "Beta" ("X", "Y"));'
                      'CREATE TABLE "Beta" ("X" INT, "Y" INT);')
    source = tmp_path / "queries.sql"
    source.write_text('SELECT a.X FROM Alpha a LEFT JOIN Beta b ON a.Y=b.Y AND b.X=a.X AND a.X=b.X;'
                      'SELECT a.X FROM Beta b JOIN Alpha a USING (X, Y);'
                      'SELECT a.X FROM Alpha a, Beta b WHERE a.X=b.X AND a.Y=b.Y;')
    result = run_digest(source, tmp_path / "digest.yaml", "--schema", schema)
    assert len(result["join_edges"]) == 1
    edge = result["join_edges"][0]
    assert edge["left"] == {"table": "Alpha", "columns": ["X", "Y"]}
    assert edge["right"] == {"table": "Beta", "columns": ["X", "Y"]}
    assert edge["support"] == 3
    assert edge["kinds"] == {"inner": 2, "left": 1}
    assert edge["declared_fk"] is True


def test_resolution_cte_grain_and_unresolved(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE a (id INT, unique_a INT); CREATE TABLE b (id INT, unique_b INT);")
    source = tmp_path / "query.sql"
    source.write_text("WITH named AS (SELECT unique_a AS renamed FROM a) "
                      "SELECT DISTINCT named.renamed, b.unique_b FROM named JOIN b ON named.renamed=b.id "
                      "GROUP BY named.renamed, b.unique_b;"
                      "SELECT unique_a, id, a.missing FROM a JOIN b ON a.id=b.id;"
                      "SELECT ghost.x FROM ghost;")
    result = run_digest(source, tmp_path / "digest.yaml", "--schema", schema)
    assert any(r["table"] == "a" and r["columns"] == ["unique_a"] and r["evidence"]["distinct"] == 1
               for r in result["grain_keys"])
    assert any(r["table"] == "b" and r["columns"] == ["unique_b"] for r in result["grain_keys"])
    unresolved = result["unresolved"]
    assert any(r.get("column") == "ID" and "table" not in r for r in unresolved)
    assert any(r.get("table") == "a" and r.get("column") == "MISSING" for r in unresolved)
    assert any(r.get("table") == "GHOST" and "column" not in r for r in unresolved)


def test_nested_filter_literals_stay_in_their_scope(tmp_path):
    source = tmp_path / "query.sql"
    source.write_text("SELECT x FROM a WHERE x IN (SELECT y FROM b WHERE z = 7)")
    result = run_digest(source, tmp_path / "digest.yaml")
    filters = {(r["table"], r["column"]): r for r in result["filter_columns"]}
    assert set(filters) == {("A", "X"), ("B", "Z")}
    assert filters["A", "X"]["operators"]["in"] == 1
    assert filters["A", "X"]["distinct_literals"] == 0
    assert filters["B", "Z"]["operators"]["eq"] == 1
    assert filters["B", "Z"]["distinct_literals"] == 1


def test_inline_foreign_key_and_reversed_join(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE a (x INT REFERENCES b(id)); CREATE TABLE b (id INT);")
    source = tmp_path / "query.sql"
    source.write_text("SELECT a.x FROM b JOIN a ON b.id=a.x")
    result = run_digest(source, tmp_path / "digest.yaml", "--schema", schema)
    assert result["join_edges"][0]["declared_fk"] is True


def test_using_after_other_joins(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE a (id INT); CREATE TABLE b (id INT, code INT); CREATE TABLE c (code INT);")
    source = tmp_path / "query.sql"
    source.write_text("SELECT b.code FROM a JOIN b ON a.id=b.id JOIN c USING(code)")
    result = run_digest(source, tmp_path / "digest.yaml", "--schema", schema)
    assert len(result["join_edges"]) == 2
    assert result["unresolved"] == []
    assert any(r["left"] == {"table": "b", "columns": ["code"]} and
               r["right"] == {"table": "c", "columns": ["code"]} for r in result["join_edges"])


def test_filter_operators_expression_redaction_and_timestamp(tmp_path):
    source = tmp_path / "queries.json"
    source.write_text(json.dumps([
        {"sql": "SELECT x + 42, CASE WHEN x > 8 THEN TRUE ELSE NULL END, UPPER(label), "
                "EXTRACT(YEAR FROM happened), COUNT(*), AVG(x) FROM a "
                "WHERE x IN (42, 43) AND label LIKE 'secret%' AND y BETWEEN 2 AND 4 AND z IS NULL"},
        {"sql": "SELECT x + 99 FROM a WHERE x IN (99, 42)"},
    ]))
    result = MODULE.build_digest(source)
    assert result["workload"]["generated_at"].endswith("Z")
    arithmetic = next(r for r in result["expressions"] if r["kind"] == "arithmetic")
    assert arithmetic["support"] == 2
    assert {r["kind"] for r in result["expressions"]} == {"arithmetic", "case", "string", "date-part"}
    filters = {r["column"]: r for r in result["filter_columns"]}
    assert filters["X"]["operators"]["in"] == 2
    assert filters["LABEL"]["operators"]["like"] == 1
    assert filters["Y"]["operators"]["range"] == 1
    assert filters["Z"]["operators"]["is_null"] == 1
    for expression in result["expressions"]:
        assert not any(literal in expression["template"] for literal in ("42", "99", "8", "TRUE", "NULL"))


def test_module_limits():
    source = TOOL.read_text()
    assert len(source.splitlines()) < 475
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno - node.lineno + 1 < 50, node.name
            assert node.returns is not None, node.name
            assert all(arg.annotation is not None for arg in node.args.args if arg.arg != "self"), node.name


def test_saved_splits_and_ids_select_before_extraction(tmp_path):
    source = tmp_path / "workload.json"
    source.write_text(json.dumps([
        {"id": "r", "sql": "SELECT a.id FROM a JOIN b ON a.id=b.id"},
        {"id": "h", "sql": "SELECT b.id FROM b JOIN c ON b.id=c.id"},
        {"id": "r2", "sql": "SELECT a.id FROM a JOIN b ON a.id=b.id"}]), encoding="utf-8")
    verification = tmp_path / "model.verification.json"
    verification.write_text(json.dumps({"split": {"repair": 999, "holdout": 0}, "items": [
        {"id": "h", "split": "holdout"}, {"id": "r2", "split": "repair"}, {"id": "r", "split": "repair"}]}), encoding="utf-8")
    repair = run_digest(source, tmp_path / "repair.digest.yaml", "--split", "repair", "--verification", verification)
    holdout = run_digest(source, tmp_path / "holdout.digest.yaml", "--split", "holdout", "--verification", verification)
    assert set(repair["item_contributions"]) == {"r", "r2"}
    assert set(holdout["item_contributions"]) == {"h"}
    assert [(e["left"]["table"], e["right"]["table"], e["support"]) for e in repair["join_edges"]] == [("A", "B", 2)]
    assert [(e["left"]["table"], e["right"]["table"]) for e in holdout["join_edges"]] == [("B", "C")]
    ids = tmp_path / "ids.txt"
    ids.write_text("h\nr2\n", encoding="utf-8")
    subset = run_digest(source, tmp_path / "subset.yaml", "--ids", ids, "--split", "repair", "--verification", verification)
    assert subset["workload"]["n_items"] == subset["join_edges"][0]["support"] == 1
    assert set(subset["item_contributions"]) == {"r2"}
    ids.write_text("\n", encoding="utf-8")
    empty = run_digest(source, tmp_path / "empty.yaml", "--ids", ids)
    assert empty["workload"]["kind"] == "sql"
    assert empty["workload"]["n_items"] == 0
    assert empty["join_edges"] == []


@pytest.mark.parametrize("failure", ["missing-file", "missing-assignment", "bad-assignment", "duplicate-assignment", "unknown-id", "duplicate-id"])
def test_subset_rejects_invalid_selection(tmp_path, failure):
    source = tmp_path / "queries.json"
    source.write_text('[{"id":"q","sql":"SELECT x FROM a"}]', encoding="utf-8")
    verification = tmp_path / "verification.json"
    rows = [{"id": "q", "split": "repair"}]
    if failure == "missing-assignment":
        rows = []
    elif failure == "bad-assignment":
        rows[0]["split"] = "new"
    elif failure == "duplicate-assignment":
        rows *= 2
    elif failure == "duplicate-id":
        source.write_text('[{"id":"q","sql":"SELECT x FROM a"},{"id":"q","sql":"SELECT x FROM b"}]', encoding="utf-8")
    verification.write_text(json.dumps({"items": rows}), encoding="utf-8")
    flags = ["--split", "repair"]
    if failure != "missing-file":
        flags += ["--verification", str(verification)]
    if failure == "unknown-id":
        ids = tmp_path / "ids.txt"
        ids.write_text("missing\n", encoding="utf-8")
        flags += ["--ids", str(ids)]
    out = tmp_path / "out.yaml"
    result = subprocess.run([sys.executable, str(TOOL), "--input", str(source), "--out", str(out), *flags], capture_output=True)
    assert result.returncode != 0
    assert not out.exists()


@pytest.mark.parametrize("change", ["removed", "changed"])
def test_contributions_subtract_without_old_query_text(tmp_path, change):
    source = tmp_path / "items.json"
    rows = [{"id": "gone", "sql": "SELECT a.id + 42 FROM a LEFT JOIN b ON a.id=b.id WHERE a.x IN ('private-a', 'private-shared') GROUP BY a.id"},
            {"id": "stay", "sql": "SELECT a.id + 99 FROM a JOIN b ON a.id=b.id WHERE a.x IN ('private-b', 'private-shared') GROUP BY a.id"},
            {"id": "also-stay", "sql": "SELECT a.x FROM a WHERE a.x = 'private-shared'"}]
    source.write_text(json.dumps(rows), encoding="utf-8")
    original = run_digest(source, tmp_path / "original.yaml")
    source.write_text(json.dumps(rows[1:] + ([{"id": "gone", "sql": "SELECT y FROM c WHERE y = 7"}] if change == "changed" else [])), encoding="utf-8")
    ids = tmp_path / "ids.txt"
    ids.write_text("stay\nalso-stay\n", encoding="utf-8")
    expected = run_digest(source, tmp_path / "expected.yaml", "--ids", ids)
    # This subtraction uses only the stored digest and item id; old SQL is gone.
    removed = original["item_contributions"]["gone"]
    identity = MODULE.Digest(MODULE.Schema(None, "sqlite"), "sqlite").name_key
    for section in removed:
        contributions = {identity(row): row for row in removed[section]}
        remaining = []
        for row in original[section]:
            row = {k: v.copy() if isinstance(v, dict) else v for k, v in row.items() if k != "id"}
            part = contributions.get(identity(row))
            if part:
                row["support"] -= part["support"]
                for field in ("roles", "operators", "evidence", "kinds"):
                    if field in row:
                        for name, count in part[field].items():
                            row[field][name] -= count
                        if field == "kinds":
                            row[field] = {k: v for k, v in row[field].items() if v}
                if "distinct_literals" in row:
                    row["distinct_literals"] = sum(c["count"] for c in part["literal_cohorts"] if set(c["items"]) - {"gone"})
            if row["support"]:
                remaining.append(row)
        remaining.sort(key=lambda r: (-r["support"], identity(r)))
        assert remaining == [{k: v for k, v in row.items() if k != "id"} for row in expected[section]]
    encoded = yaml.safe_dump(original)
    assert "private-" not in encoded
    assert "SELECT " not in encoded
    assert "42" not in encoded and "99" not in encoded


def test_contributions_are_per_item_not_occurrence_and_keep_empty_items(tmp_path):
    source = tmp_path / "items.json"
    source.write_text(json.dumps([
        {"id": "repeated", "sql": "SELECT x FROM a WHERE x=123; SELECT x FROM a WHERE x=123"},
        {"id": "question", "question": "Which items?"},
        {"id": "error", "sql": "SELECT FROM"}]), encoding="utf-8")
    result = run_digest(source, tmp_path / "digest.yaml")
    contributions = result["item_contributions"]
    assert list(contributions) == ["error", "question", "repeated"]
    assert contributions["repeated"]["tables"] == [{"table": "A", "support": 1}]
    assert contributions["repeated"]["filter_columns"][0]["operators"]["eq"] == 1
    assert contributions["repeated"]["filter_columns"][0]["literal_cohorts"] == [{"items": ["repeated"], "count": 1}]
    assert all(not rows for rows in contributions["error"].values())
    assert all(not rows for rows in contributions["question"].values())


def test_multiple_inputs_and_saved_split(tmp_path):
    first, second = tmp_path / "pairs.json", tmp_path / "sql.json"
    first.write_text(json.dumps([{"id": "p1", "question": "names", "sql": "SELECT name FROM asset"}]), encoding="utf-8")
    second.write_text(json.dumps([{"id": "s1", "sql": "SELECT cost FROM asset"}]), encoding="utf-8")
    out = tmp_path / "out.yaml"
    single = run_digest(first, out)
    single_bytes = out.read_bytes()
    assert MODULE.build_digest(first, no_timestamp=True) == MODULE.build_digest([first], no_timestamp=True)
    run_digest(first, out)
    assert out.read_bytes() == single_bytes
    merged = run_digest(first, out, "--input", second)
    assert merged["workload"]["artifacts"] == ["pairs.json", "sql.json"]
    assert merged["workload"]["n_items"] == 2
    assert set(merged["item_contributions"]) == {"p1", "s1"}
    assignments = tmp_path / "verification.json"
    assignments.write_text(json.dumps({"items": [{"id": "p1", "split": "repair"}, {"id": "s1", "split": "holdout"}]}), encoding="utf-8")
    split = run_digest(first, out, "--input", second, "--split", "repair", "--verification", assignments)
    assert split["workload"]["n_items"] == 1
    assert split["item_contributions"] == single["item_contributions"]
    second.write_bytes(first.read_bytes())
    result = subprocess.run([sys.executable, str(TOOL), "--input", str(first), "--input", str(second), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode != 0
    assert "duplicate workload item id: p1" in result.stderr
