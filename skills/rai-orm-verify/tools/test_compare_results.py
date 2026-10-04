"""Tests for content-based result comparison, including CLI exit statuses."""

import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


TOOL = Path(__file__).with_name("compare_results.py")
SPEC = importlib.util.spec_from_file_location("compare_results", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
compare = MODULE.compare


def write_csv(path, header, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                          capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})


def test_column_permutation():
    result = compare([["Ada", "12"], ["Ben", "13"]], [["13", "Ben"], ["12", "Ada"]])
    assert result == {"match": True, "reason": "ok", "weak": False,
                      "expected_rows": 2, "actual_rows": 2}


def test_column_multisets_are_only_pruning():
    assert not compare([[1, "A"], [2, "B"]], [[1, "B"], [2, "A"]])["match"]
    assert compare([[1, 1, 0], [1, 0, 1], [0, 1, 1]],
                   [[1, 0, 1], [0, 1, 1], [1, 1, 0]])["match"]


def test_duplicate_candidate_columns_require_backtracking():
    left = [[1, 1, "A"], [1, 2, "B"], [2, 1, "C"], [2, 2, "D"]]
    right = [[1, 1, "A"], [2, 1, "B"], [1, 2, "C"], [2, 2, "D"]]
    assert compare(left, right)["match"]


def test_row_order_and_ordered():
    assert compare([[1], [2]], [[2], [1]])["match"]
    result = compare([[1], [2]], [[2], [1]], ordered=True)
    assert not result["match"] and result["reason"] == "values"
    assert compare([["A", 1], ["B", 2]], [[1, "A"], [2, "B"]], ordered=True)["match"]


@pytest.mark.parametrize("left,right,match", [
    ("0.6666666667", "0.666666666666667", True),
    ("0.66", "0.67", False),
    ("1e-10", "0", True),
    ("1e-8", "0", False),
    ("1000000", "1000000.5", True),
    ("1000000", "1000002", False),
    (" 001.0 ", "1", True),
    ("1e400", "1e400", True),
    (" text ", "text", True),
])
def test_numeric_tolerance_and_stripping(left, right, match):
    assert compare([[left]], [[right]])["match"] is match


def test_custom_tolerance():
    assert compare([["0.66"]], [["0.67"]], rel_tol=0.1)["match"]
    assert compare([["0.6666666667"]], [["0.666666666666667"]], rel_tol=0)["match"]
    assert not compare([["1"]], [["1.0000005"]], rel_tol=0)["match"]
    with pytest.raises(ValueError):
        compare([], [], rel_tol=-1)


def test_tolerance_requires_bipartite_matching():
    # A greedy first match consumes the only partner of the second row.
    assert compare([["1.0000005"], ["1.0000015"]], [["1.000001"], ["1"]])["match"]
    assert compare([["1.0000005", "A"], ["1.0000015", "A"]],
                   [["1.000001", "A"], ["1", "A"]])["match"]


@pytest.mark.parametrize("null", ["", "NULL", "None", "null", None, " NULL "])
def test_null_equivalence(null):
    assert compare([[null]], [[""]])["match"]
    assert not compare([[null]], [["0"]])["match"]


def test_duplicates_and_reason_counts():
    assert compare([["A"], ["A"], ["B"]], [["B"], ["A"], ["A"]])["match"]
    assert compare([["A"], ["A"], ["B"]], [["A"], ["B"], ["B"]])["reason"] == "values"
    assert compare([[1, 2]], [[1]])["reason"] == "column-count"
    assert compare([[1]], [[1], [1]])["reason"] == "row-count"


def test_empty_weak():
    assert compare([], []) == {"match": True, "reason": "ok", "weak": True,
                               "expected_rows": 0, "actual_rows": 0}
    assert compare([], [[1]])["reason"] == "row-count"
    assert compare([[]], [[]])["match"]
    assert not compare([[]], [[]])["weak"]


def test_dictionary_rows():
    assert compare([{"name": "Ada", "id": "1"}], [{"number": "1", "person": "Ada"}])["match"]


def test_cli_headers_permutation_and_exit_codes(tmp_path):
    expected, actual = tmp_path / "a.csv", tmp_path / "b.csv"
    write_csv(expected, ["name", "id"], [["Ada", 1], ["Ben", 2]])
    write_csv(actual, ["unrelated", "headings"], [[2, "Ben"], [1, "Ada"]])
    args = ["--expected", expected, "--actual", actual]
    matched = cli(*args)
    assert matched.returncode == 0 and json.loads(matched.stdout)["match"]
    mismatched = cli(*args, "--ordered")
    assert mismatched.returncode == 1 and json.loads(mismatched.stdout)["reason"] == "values"
    missing = cli("--expected", tmp_path / "missing.csv", "--actual", actual)
    assert missing.returncode == 2 and not json.loads(missing.stdout)["match"]
    usage = cli("--expected", expected)
    assert usage.returncode == 2 and not json.loads(usage.stdout)["match"]
    assert cli(*args, "--rel-tol", "-1").returncode == 2


def test_cli_empty_headers_and_count_reasons(tmp_path):
    expected, actual = tmp_path / "a.csv", tmp_path / "b.csv"
    args = ["--expected", expected, "--actual", actual]
    write_csv(expected, ["a", "b"], [])
    write_csv(actual, ["x", "y"], [])
    assert json.loads(cli(*args).stdout)["weak"]
    write_csv(actual, ["x"], [])
    result = cli(*args)
    assert result.returncode == 1
    assert json.loads(result.stdout)["reason"] == "column-count"
    write_csv(actual, ["x", "y"], [[1, 2]])
    assert json.loads(cli(*args).stdout)["reason"] == "row-count"


def test_cli_malformed_csv(tmp_path):
    expected, actual = tmp_path / "a.csv", tmp_path / "b.csv"
    write_csv(expected, ["a", "b"], [[1, 2]])
    actual.write_text("a,b\n1\n")
    result = cli("--expected", expected, "--actual", actual)
    assert result.returncode == 2
    assert not json.loads(result.stdout)["match"]
