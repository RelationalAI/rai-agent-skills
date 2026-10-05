"""Compaction preservation gate and consistent artifact rollback.

The verifier supplies reports from executed checks using the same oracle. This
module does not execute PyRel or treat scaffolds as verification evidence.
"""

import argparse
import json
from pathlib import Path


def evaluate(baseline, candidate):
    reasons = []
    for key in ("oracle", "workload", "split"):
        if baseline.get(key) != candidate.get(key):
            reasons.append(key + "-changed")
    if not baseline.get("oracle") or not any(i.get("status") == "pass" for i in baseline.get("items", [])):
        reasons.append("usable-baseline-required")
    old = {i["id"]: i for i in baseline.get("items", [])}
    new = {i["id"]: i for i in candidate.get("items", [])}
    if len(old) != len(baseline.get("items", [])) or len(new) != len(candidate.get("items", [])):
        reasons.append("duplicate-item-id")
    if set(old) != set(new):
        reasons.append("workload-ids-changed")
    for identifier, item in sorted(old.items()):
        after = new.get(identifier, {})
        if item.get("split") != after.get("split"):
            reasons.append("split-changed:" + identifier)
        if item.get("status") == "pass":
            if after.get("status") != "pass":
                reasons.append("baseline-pass-lost:" + identifier)
            if item.get("weak", False) != after.get("weak", False):
                reasons.append("weak-accounting-changed:" + identifier)
            if item.get("oracle") != after.get("oracle"):
                reasons.append("item-oracle-changed:" + identifier)
        if item.get("status") in {"inexpressible", "oracle-error"} and item.get("status") != after.get("status"):
            reasons.append("exclusions-changed:" + identifier)
    for key in ("weak_passes", "excluded"):
        if baseline.get("summary", {}).get(key) != candidate.get("summary", {}).get(key):
            reasons.append(key + "-changed")
    return {"accepted": not reasons, "reasons": sorted(set(reasons))}


def attempt(project, artifact_paths, baseline, apply_candidate, verify_candidate):
    """Run one candidate attempt; restore all registered artifacts on rejection.

    Include YAML, emitted Python, bindings, verbalization, verification and every
    accepted/candidate rewrite. Callbacks own modeling and actual oracle checks.
    Candidate rewrites use separate paths until the verifier accepts equivalence.
    """
    root = Path(project).resolve()
    paths = []
    for supplied in artifact_paths:
        path = root / supplied
        path.resolve().relative_to(root)
        if path.is_symlink():
            raise ValueError("artifact symlink")
        paths.append(path)
    snapshot = {path: path.read_bytes() if path.is_file() else None for path in paths}
    accepted = False
    try:
        apply_candidate()
        candidate = verify_candidate()
        result = evaluate(baseline, candidate)
        accepted = result["accepted"]
        return result
    finally:
        if not accepted:
            for path, content in snapshot.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()
    try:
        result = evaluate(*[json.loads(Path(p).read_text(encoding="utf-8")) for p in (args.baseline, args.candidate)])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print(json.dumps({"accepted": False, "reasons": ["invalid-verification-input"]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
