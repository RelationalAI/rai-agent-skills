"""Compare CSV query results by content, with column and row permutations."""

from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Sequence


def normalize(value: Any) -> Decimal | str | None:
    """Normalize CSV nulls and numbers without losing numeric precision."""
    if value is None:
        return None
    value = str(value).strip()
    if value in ("", "NULL", "None", "null"):
        return None
    try:
        number = Decimal(value)
        return number if number.is_finite() else value
    except InvalidOperation:
        return value


def equal(left: Any, right: Any, rel_tol: float) -> bool:
    if isinstance(left, Decimal) and isinstance(right, Decimal):
        tolerance = max(Decimal("1e-9"), Decimal(str(rel_tol)) * max(abs(left), abs(right)))
        return abs(left - right) <= tolerance
    return left == right


def multiset_match(left: Sequence, right: Sequence, matches: Callable) -> bool:
    """Use bipartite matching: approximate equality is not transitive."""
    if len(left) != len(right):
        return False
    candidates = [[j for j, b in enumerate(right) if matches(a, b)] for a in left]
    assigned: dict[int, int] = {}
    reverse: dict[int, int] = {}
    for start in sorted(range(len(left)), key=lambda i: len(candidates[i])):
        queue, parents, found = [start], {}, False
        for i in queue:
            for j in candidates[i]:
                if j in parents:
                    continue
                parents[j] = i
                if j in assigned:
                    queue.append(assigned[j])
                    continue
                while j is not None:
                    i = parents[j]
                    previous = reverse.get(i)
                    assigned[j], reverse[i] = i, j
                    j = previous
                found = True
                break
            if found:
                break
        if not found:
            return False
    return True


def column_mapping(left: list, right: list, ordered: bool, rel_tol: float) -> bool:
    width = len(left[0])
    candidates = {
        i: [j for j in range(width) if multiset_match(
            [row[i] for row in left], [row[j] for row in right],
            lambda a, b: equal(a, b, rel_tol))]
        for i in range(width)
    }
    order = sorted(range(width), key=lambda i: (len(candidates[i]), i))

    def search(mapping: dict[int, int], used: set[int]) -> bool:
        if len(mapping) == width:
            return True
        i = order[len(mapping)]
        for j in candidates[i]:
            if j in used:
                continue
            mapping[i] = j
            matches = lambda a, b: all(equal(a[x], b[y], rel_tol) for x, y in mapping.items())
            valid = (all(matches(a, b) for a, b in zip(left, right)) if ordered
                     else multiset_match(left, right, matches))
            if valid and search(mapping, used | {j}):
                return True
            del mapping[i]
        return False

    return search({}, set())


def compare(expected_rows: Sequence, actual_rows: Sequence,
            ordered: bool = False, rel_tol: float = 1e-6) -> dict:
    """Compare sequences of rows (sequences or insertion-ordered dictionaries)."""
    if rel_tol < 0 or not Decimal(str(rel_tol)).is_finite():
        raise ValueError("rel_tol must be finite and nonnegative")
    left = [[normalize(v) for v in (r.values() if isinstance(r, dict) else r)] for r in expected_rows]
    right = [[normalize(v) for v in (r.values() if isinstance(r, dict) else r)] for r in actual_rows]
    result = {"match": False, "reason": "values", "weak": False,
              "expected_rows": len(left), "actual_rows": len(right)}
    widths = {len(row) for row in left + right}
    if len(widths) > 1:
        result["reason"] = "column-count"
    elif len(left) != len(right):
        result["reason"] = "row-count"
    elif not left or column_mapping(left, right, ordered, rel_tol):
        result.update(match=True, reason="ok", weak=not left)
    return result


def read_csv(path: Path) -> tuple[int, list[list[str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, None)
        if header is None:
            raise ValueError("CSV header is missing")
        rows = list(reader)
    if any(len(row) != len(header) for row in rows):
        raise ValueError("CSV row width differs from header")
    return len(header), rows


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({"match": False, "reason": message, "weak": False,
                          "expected_rows": 0, "actual_rows": 0}))
        self.exit(2)


def main(argv: list[str] | None = None) -> int:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--ordered", action="store_true")
    parser.add_argument("--rel-tol", type=float, default=1e-6)
    args = parser.parse_args(argv)
    try:
        n_left, left = read_csv(args.expected)
        n_right, right = read_csv(args.actual)
        result = compare(left, right, args.ordered, args.rel_tol)
        if n_left != n_right:
            result.update(match=False, reason="column-count", weak=False)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        print(json.dumps({"match": False, "reason": str(error), "weak": False,
                          "expected_rows": 0, "actual_rows": 0}))
        return 2
    print(json.dumps(result))
    return 0 if result["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
