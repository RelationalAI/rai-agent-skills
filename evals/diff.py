"""Compare a current run's pass/fail map against a stored baseline.

Baseline format (per skill):
    {
      "<eval_id>": [
        {"expectation": "...", "passed": true|false},
        ...
      ],
      ...
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def to_passmap(results: dict[str, list[dict]]) -> dict[str, list[dict[str, Any]]]:
    """Project a per-skill results dict to {eval_id: [{expectation, passed}, ...]}."""
    out: dict[str, list[dict[str, Any]]] = {}
    for eid, exp_list in results.items():
        out[str(eid)] = [
            {"expectation": e["expectation"], "passed": bool(e["passed"])}
            for e in exp_list
        ]
    return out


def compare(
    current: dict[str, list[dict]],
    baseline: dict[str, list[dict]] | None,
) -> dict:
    if baseline is None:
        return {
            "first_run": True,
            "regressions": [],
            "improvements": [],
            "unchanged": [],
            "added": [],
            "removed": [],
        }

    regressions: list[dict] = []
    improvements: list[dict] = []
    unchanged: list[dict] = []
    added: list[dict] = []
    removed: list[dict] = []

    cur = to_passmap(current)

    for eid, exp_list in cur.items():
        base_list = baseline.get(eid, [])
        # Index baseline by expectation text (resilient to reordering).
        base_by_text = {e["expectation"]: bool(e["passed"]) for e in base_list}
        for exp in exp_list:
            text = exp["expectation"]
            now_pass = bool(exp["passed"])
            if text not in base_by_text:
                added.append({
                    "eval_id": eid,
                    "expectation": text,
                    "passed": now_pass,
                })
                continue
            was_pass = base_by_text[text]
            row = {"eval_id": eid, "expectation": text}
            if was_pass and not now_pass:
                regressions.append(row)
            elif not was_pass and now_pass:
                improvements.append(row)
            else:
                unchanged.append({**row, "passed": now_pass})

    # Detect removed expectations / removed evals.
    for eid, base_list in baseline.items():
        cur_texts = {e["expectation"] for e in cur.get(eid, [])}
        for be in base_list:
            if be["expectation"] not in cur_texts:
                removed.append({
                    "eval_id": eid,
                    "expectation": be["expectation"],
                    "was_passed": bool(be["passed"]),
                })

    return {
        "first_run": False,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "added": added,
        "removed": removed,
    }


def load_baseline(path: Path) -> dict[str, list[dict]] | None:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def write_baseline(path: Path, current: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(to_passmap(current), f, indent=2, sort_keys=True)
