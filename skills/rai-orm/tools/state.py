#!/usr/bin/env python3
"""Persist an ORM route and print a deterministic, content-free resume plan.

Commands never execute the recorded emitter or mutate model/workload artifacts.
Paths are relative to the working directory (the manifest's parent).
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

import yaml


VERSION = 1
KINDS = {"missing_link", "wrong_grain", "merge", "split", "rename", "failing_item", "compact", "note"}
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
ITEM_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
ARTIFACT_DEFAULTS = {
    "model_yaml": "model.orm.yaml", "model_py": "model.py",
    "digest": "workload.digest.yaml", "verification": "model.verification.json",
    "connectivity": "connectivity.json", "report": "orm-report.json",
    "report_markdown": "orm-report.md", "refactor_before": "compaction.before.json",
    "refactor_metrics": "compaction.after.json",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path):
    return sha(path.read_bytes()) if path.is_file() else None


def read(path):
    if not path.is_file():
        return None
    value = yaml.safe_load(path.read_text())
    return value


def mapping(path):
    value = read(path)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("mapping required")
    return value


def relative(path, base):
    path = Path(path)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def revision(base, artifacts):
    return sha(canonical({key: file_hash(base / artifacts[key]) for key in ("model_yaml", "model_py")}))


def sql_statements(text):
    # Match the digest tool's positional ids without a SQL-parser dependency.
    pattern = r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`[^`]*`|\[[^\]]*\]|--[^\n]*|/\*[\s\S]*?\*/|;"
    start, parts = 0, []
    for token in re.finditer(pattern, text):
        if token.group() == ";":
            parts.append(text[start:token.start()])
            start = token.end()
    parts.append(text[start:])
    return [part.strip() for part in parts if re.sub(r"--[^\n]*|/\*[\s\S]*?\*/", "", part).strip()]


def item_hashes(path):
    """Hash each item in memory; return ids and hashes, never its contents."""
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix in {".json", ".yaml", ".yml"}:
        rows = json.loads(text) if suffix == ".json" else yaml.safe_load(text)
        if isinstance(rows, dict):
            rows = rows.get("items")
    elif suffix == ".csv":
        rows = list(csv.DictReader(io.StringIO(text)))
    elif suffix == ".sql":
        rows = [{"sql": sql} for sql in sql_statements(text)]
    else:
        rows = [{"question": line.strip()} for line in text.splitlines() if line.strip()]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid workload")
    result = {}
    for index, row in enumerate(rows, 1):
        identifier = str(row.get("id", f"i{index:04d}"))
        if not ITEM_ID.fullmatch(identifier) or identifier in result:
            raise ValueError("invalid or duplicate item id")
        # Metadata such as generated_at does not make an item a different query.
        content = {"sql": next((row[k] for k in ("sql", "output", "query_text", "query") if row.get(k)), None),
                   "question": row.get("question") or row.get("input")}
        result[identifier] = sha(canonical(content))
    return dict(sorted(result.items()))


def record_missing_pyrel_hashes(base, path, items):
    # Legacy reports have no hashes. Record file identity without claiming that
    # hashing the file verifies its result or changing the verification report.
    for item in items:
        if item.get("pyrel") and not item.get("pyrel_sha256"):
            item["pyrel_sha256"] = file_hash((base / path).parent / item["pyrel"])


def verification_snapshot(base, path):
    value = mapping(base / path)
    items = []
    for item in value.get("items", []):
        identifier = str(item["id"])
        if not ITEM_ID.fullmatch(identifier):
            raise ValueError("invalid item id")
        saved = {key: item[key] for key in ("id", "split", "status", "pyrel", "pyrel_sha256", "passed_at_round", "weak") if key in item}
        items.append(saved)
    record_missing_pyrel_hashes(base, path, items)
    return {"split": value.get("split"), "oracle": value.get("oracle"),
            "items": sorted(items, key=lambda item: item["id"])}


def last_round(value):
    return max((int(r["round"]) for r in value.get("rounds", [])), default=0)


def stop_reasons(base, artifacts):
    connectivity = mapping(base / artifacts["connectivity"])
    report = mapping(base / artifacts["report"])
    metrics = mapping(base / artifacts["refactor_metrics"])
    return {"connectivity": ("COMPARISON_CAP_REACHED" if connectivity.get("summary", {}).get("comparison_cap_reached")
                             else connectivity.get("verdict")),
            "report": report.get("status"),
            "refactor": metrics.get("stopped_because", metrics.get("summary", {}).get("stopped_because"))}


def initialize(base, artifacts, inputs=(), workloads=(), emitter=None, mode=None,
               rounds_per_invocation=5, patience=2, until_pass=False, skills=()):
    if rounds_per_invocation < 1 or patience < 1:
        raise ValueError("positive budgets required")
    records = []
    seen = set()
    for kind, paths in (("input", inputs), ("workload", workloads)):
        for supplied in paths:
            path = relative(supplied, base)
            if path in seen or not (base / path).is_file():
                raise ValueError("missing or duplicate input")
            seen.add(path)
            record = {"path": path, "kind": kind, "sha256": file_hash(base / path)}
            if kind == "workload":
                record["item_hashes"] = item_hashes(base / path)
            records.append(record)
    all_ids = [identifier for record in records for identifier in record.get("item_hashes", {})]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("item ids must be unique across workloads")
    verification = mapping(base / artifacts["verification"])
    counter = last_round(verification)
    model = mapping(base / artifacts["model_yaml"])
    if mode is None:
        mode = verification.get("mode", model.get("source", {}).get("mode", "guided"))
    if mode not in {"guided", "one-shot"}:
        raise ValueError("invalid saved mode")
    if not skills:
        skills = []
        if (base / artifacts["digest"]).is_file():
            skills.append("rai-orm-from-workload")
        if model:
            skills.append("rai-orm-from-text" if model.get("source", {}).get("kind") == "text-conversation" else "rai-orm-from-schema")
        if (base / artifacts["connectivity"]).is_file():
            skills.append("connectivity")
        if verification:
            skills.append("rai-orm-verify")
        if (base / artifacts["refactor_metrics"]).is_file():
            skills.append("rai-orm-refactor")
        if (base / artifacts["report"]).is_file():
            skills.append("report")
    rev = revision(base, artifacts)
    reasons = stop_reasons(base, artifacts)
    stop = verification.get("summary", {}).get("stopped_because")
    return {"version": VERSION, "inputs": sorted(records, key=lambda record: record["path"]),
            "mode": mode, "budget": {"rounds_per_invocation": rounds_per_invocation, "patience": patience, "until_pass": until_pass},
            "model_revision": rev, "artifacts": artifacts, "emitter_command": emitter,
            "skills_run": [{"skill": skill, "rounds_done": counter if skill == "rai-orm-verify" else 0,
                            "stop_reason": stop if skill == "rai-orm-verify" else reasons.get("refactor" if skill == "rai-orm-refactor" else skill),
                            "model_revision": rev} for skill in skills],
            "round_counters": {skill: counter if skill == "rai-orm-verify" else 0 for skill in skills},
            "artifact_hashes": {key: file_hash(base / path) for key, path in sorted(artifacts.items())},
            "artifact_stop_reasons": reasons, "verification_revision": rev,
            "verification_snapshot": verification_snapshot(base, artifacts["verification"]),
            "last_stop_reason": stop, "feedback_processed": []}


def feedback_items(path):
    value = mapping(path)
    if value.get("version") != 1 or not isinstance(value.get("items"), list):
        raise ValueError("invalid feedback version or items")
    result = []
    for item in value["items"]:
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            raise ValueError("invalid feedback kind")
        kind = item["kind"]
        required = {"missing_link": ("from", "to"), "wrong_grain": ("concept",), "merge": ("concepts",),
                    "split": ("concept",), "rename": ("from", "to"), "failing_item": ("ids",),
                    "compact": ("concept",), "note": ()}[kind]
        if any(key not in item for key in required):
            raise ValueError("missing feedback target")
        # Unknown fields, including note text, contribute only to its fingerprint.
        # Thus arbitrary prose cannot leak through tool output.
        fingerprint = sha(canonical(item))
        projected = {"id": item.get("id", "feedback_" + fingerprint[7:19]), "kind": kind,
                     "sha256": fingerprint, "source": "user-feedback", "status": "proposed"}
        for key in ("from", "to", "concept", "concepts", "ids"):
            if key in item:
                values = item[key] if isinstance(item[key], list) else [item[key]]
                pattern = ITEM_ID if key == "ids" else NAME
                if not values or any(not isinstance(v, str) or not pattern.fullmatch(v) for v in values):
                    raise ValueError("invalid feedback target")
                if key in {"concepts", "ids"} and not isinstance(item[key], list):
                    raise ValueError("list required")
                projected[key] = sorted(values) if isinstance(item[key], list) else item[key]
        if not isinstance(projected["id"], str) or not ITEM_ID.fullmatch(projected["id"]):
            raise ValueError("invalid feedback id")
        if kind == "merge" and len(projected["concepts"]) < 2:
            raise ValueError("merge requires two concepts")
        result.append(projected)
    if len({item["id"] for item in result}) != len(result):
        raise ValueError("duplicate feedback id")
    return sorted(result, key=lambda item: item["id"])


def plan(state, base, feedback=()):
    if state.get("version") != VERSION:
        raise ValueError("unsupported state version")
    artifacts = state["artifacts"]
    blockers = []
    def block(code, **details):
        blockers.append({"id": code, **details})
    if not (base / artifacts["model_yaml"]).is_file():
        block("YAML_REQUIRED", path=artifacts["model_yaml"])
    if not (base / artifacts["model_py"]).is_file():
        block("PYREL_REQUIRED", path=artifacts["model_py"])
    if not state.get("emitter_command"):
        block("EMITTER_REQUIRED")
    if state["artifact_hashes"].get("digest") and not (base / artifacts["digest"]).is_file():
        block("DIGEST_REQUIRED", path=artifacts["digest"])
    verification = mapping(base / artifacts["verification"])
    snapshot = state["verification_snapshot"]
    if snapshot.get("items") and not verification:
        block("VERIFICATION_REQUIRED", path=artifacts["verification"])
    if snapshot.get("split") is not None and snapshot["split"] != verification.get("split"):
        block("SPLIT_CHANGED")
    if snapshot.get("oracle") and snapshot["oracle"] != verification.get("oracle"):
        block("ORACLE_CHANGED")
    current_items = {item["id"]: item for item in verification.get("items", [])}
    if len(current_items) != len(verification.get("items", [])):
        block("DUPLICATE_VERIFICATION_ID")
    if verification and (not verification.get("split") or
                         any(item.get("split") not in {"repair", "holdout"} for item in verification.get("items", []))):
        block("SPLIT_ASSIGNMENTS_REQUIRED")
    new_ids, removed_ids, changed_ids, changed_inputs = set(), set(), set(), []
    for record in state["inputs"]:
        path = base / record["path"]
        if not path.is_file():
            block("INPUT_MISSING", path=record["path"])
            continue
        if file_hash(path) == record["sha256"]:
            continue
        changed_inputs.append(record["path"])
        if record["kind"] != "workload":
            block("INPUT_CHANGED", path=record["path"])
            continue
        old, current = record["item_hashes"], item_hashes(path)
        new_ids.update(set(current) - set(old))
        removed_ids.update(set(old) - set(current))
        changed_ids.update(identifier for identifier in set(old) & set(current) if old[identifier] != current[identifier])
    if changed_inputs:
        block("WORKLOAD_DELTA_REVIEW", paths=sorted(changed_inputs))
    invalidated = removed_ids | changed_ids
    frozen = []
    for item in snapshot["items"]:
        if item.get("status") != "pass" or item["id"] in invalidated:
            continue
        frozen.append(item["id"])
        current = current_items.get(item["id"], {})
        if current.get("status") != "pass":
            block("BASELINE_PASS_LOST", item_id=item["id"])
        if current.get("split") != item.get("split"):
            block("ITEM_SPLIT_CHANGED", item_id=item["id"])
        saved_path = item.get("pyrel")
        saved = (base / artifacts["verification"]).parent / saved_path if saved_path else None
        if saved is None or not saved.is_file():
            block("PASSED_PYREL_MISSING", item_id=item["id"])
        else:
            current_hash = file_hash(saved)
            if item.get("pyrel_sha256") != current_hash or (
                    current.get("pyrel_sha256") is not None and current["pyrel_sha256"] != current_hash):
                block("PASSED_PYREL_CHANGED", item_id=item["id"])
    # Check every surviving assignment, including sealed holdout failures.
    for item in snapshot["items"]:
        if item["id"] not in invalidated and current_items.get(item["id"], {}).get("split") != item.get("split"):
            if not any(b.get("item_id") == item["id"] and b["id"] == "ITEM_SPLIT_CHANGED" for b in blockers):
                block("ITEM_SPLIT_CHANGED", item_id=item["id"])
    processed_hashes = {entry["sha256"] for entry in state["feedback_processed"]}
    processed_items = {h for entry in state["feedback_processed"] for h in entry.get("item_hashes", [])}
    new_feedback, pending_files = {}, []
    defaults = [name for name in ("feedback.yaml", "feedback.processed.yaml", "feedback.md") if (base / name).is_file()]
    for supplied in sorted(set(feedback) | set(defaults)):
        path_name = relative(supplied, base)
        path = base / path_name
        if not path.is_file():
            block("FEEDBACK_MISSING", path=path_name)
            continue
        hashed = file_hash(path)
        if hashed in processed_hashes:
            continue
        pending_files.append({"path": path_name, "sha256": hashed})
        if path.suffix.lower() == ".md":
            block("FEEDBACK_NEEDS_STRUCTURE", path=path_name)
            continue
        for item in feedback_items(path):
            if item["sha256"] not in processed_items:
                new_feedback[item["sha256"]] = item
    current_revision = revision(base, artifacts)
    counter = max(state["round_counters"].get("rai-orm-verify", 0), last_round(verification))
    residual = any(item.get("status") not in {"pass", "inexpressible", "oracle-error"}
                   for item in verification.get("items", []))
    changed_model = current_revision != state.get("verification_revision", state["model_revision"])
    stale = sorted(key for key, path in artifacts.items()
                   if file_hash(base / path) != state["artifact_hashes"].get(key))
    dirty = changed_model or bool(new_feedback) or bool(changed_inputs) or "digest" in stale or not verification
    digest = mapping(base / artifacts["digest"])
    has_workload = bool(verification or any(record["kind"] == "workload" for record in state["inputs"])
                        or digest.get("workload", {}).get("n_items"))
    steps = []
    if (changed_inputs and (new_ids or removed_ids or changed_ids)) or (
            not (base / artifacts["digest"]).is_file() and not state["artifact_hashes"].get("digest")
            and any(record["kind"] == "workload" for record in state["inputs"])):
        steps.append("rai-orm-from-workload")
    if dirty or residual or not (base / artifacts["connectivity"]).is_file():
        steps.append("connectivity")
    if dirty or residual:
        if has_workload:
            steps.append("rai-orm-verify")
        steps.append("rai-orm-refactor")
    elif not (base / artifacts["refactor_metrics"]).is_file():
        steps.append("rai-orm-refactor")
    if steps or stale or any(not (base / artifacts[key]).is_file() for key in ("report", "report_markdown")):
        steps.append("report")
    return {"version": VERSION, "steps": steps, "baseline_round": counter, "started_round": counter + 1,
            "baseline_model_revision": current_revision, "baseline_recheck": changed_model,
            "budget": state["budget"], "mode": state["mode"], "frozen_passed_items": sorted(frozen),
            "saved_pyrel": [{"id": item["id"], "path": item.get("pyrel"), "sha256": item.get("pyrel_sha256")}
                            for item in snapshot["items"] if item["id"] in frozen],
            "new_feedback_items": sorted(new_feedback.values(), key=lambda item: (item["id"], item["sha256"])),
            "feedback_files": sorted(pending_files, key=lambda entry: entry["path"]),
            "workload_delta": {"changed_inputs": sorted(changed_inputs), "new_item_ids": sorted(new_ids),
                               "removed_item_ids": sorted(removed_ids), "changed_item_ids": sorted(changed_ids),
                               "redigest_item_ids": sorted(new_ids | changed_ids)},
            "stale_artifacts": stale, "artifact_stop_reasons": stop_reasons(base, artifacts),
            "blockers": sorted(blockers, key=lambda b: canonical(b)), "can_resume": not blockers}


def update(state, base, skill, rounds_done=0, stop_reason=None, emitter=None, feedback=(),
           accept_workload_delta=False, rounds_per_invocation=None, patience=None, until_pass=None):
    if rounds_done < 0:
        raise ValueError("negative rounds")
    if not NAME.fullmatch(skill) or (stop_reason is not None and not NAME.fullmatch(stop_reason)):
        raise ValueError("step metadata must be identifiers")
    if emitter is not None:
        state["emitter_command"] = emitter
    for key, value in (("rounds_per_invocation", rounds_per_invocation), ("patience", patience), ("until_pass", until_pass)):
        if value is not None:
            if key != "until_pass" and value < 1:
                raise ValueError("positive budgets required")
            state["budget"][key] = value
    if accept_workload_delta:
        # The agent has reviewed the delta, re-digested only added/changed ids,
        # and preserved surviving split assignments before advancing the hashes.
        for record in state["inputs"]:
            if record["kind"] == "workload":
                record["sha256"] = file_hash(base / record["path"])
                record["item_hashes"] = item_hashes(base / record["path"])
    rev = revision(base, state["artifacts"])
    state["skills_run"].append({"skill": skill, "rounds_done": rounds_done, "stop_reason": stop_reason, "model_revision": rev})
    counters = state["round_counters"]
    counters[skill] = counters.get(skill, 0) + rounds_done
    if skill == "rai-orm-verify":
        state["verification_revision"] = rev
        counters[skill] = max(counters[skill], last_round(mapping(base / state["artifacts"]["verification"])))
        state["verification_snapshot"] = verification_snapshot(base, state["artifacts"]["verification"])
    if accept_workload_delta:
        state["verification_snapshot"] = verification_snapshot(base, state["artifacts"]["verification"])
    record_missing_pyrel_hashes(base, state["artifacts"]["verification"], state["verification_snapshot"]["items"])
    state["model_revision"] = rev
    state["last_stop_reason"] = stop_reason
    state["artifact_hashes"] = {key: file_hash(base / path) for key, path in sorted(state["artifacts"].items())}
    state["artifact_stop_reasons"] = stop_reasons(base, state["artifacts"])
    processed = {entry["sha256"]: entry for entry in state["feedback_processed"]}
    for supplied in feedback:
        name = relative(supplied, base)
        path = base / name
        entry = {"path": name, "sha256": file_hash(path)}
        if entry["sha256"] is None:
            raise ValueError("missing feedback")
        if path.suffix.lower() != ".md":
            entry["item_hashes"] = sorted(item["sha256"] for item in feedback_items(path))
        processed[entry["sha256"]] = entry
    state["feedback_processed"] = sorted(processed.values(), key=lambda entry: (entry["path"], entry["sha256"]))
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "update", "plan"):
        p = sub.add_parser(command)
        p.add_argument("--state", default="orm-state.json")
        if command in {"init", "plan"}:
            for key, default in ARTIFACT_DEFAULTS.items():
                p.add_argument("--" + key.replace("_", "-"), default=default)
            p.add_argument("--input", action="append", default=[])
            p.add_argument("--workload", action="append", default=[])
            p.add_argument("--mode", choices=("guided", "one-shot"))
        if command in {"init", "update"}:
            p.add_argument("--emitter")
            p.add_argument("--rounds-per-invocation", type=int, default=5 if command == "init" else None)
            p.add_argument("--patience", type=int, default=2 if command == "init" else None)
            p.add_argument("--until-pass", action=argparse.BooleanOptionalAction, default=False if command == "init" else None)
            p.add_argument("--skill", action="append" if command == "init" else "store", default=[] if command == "init" else None,
                           required=command == "update")
        if command in {"update", "plan"}:
            p.add_argument("--feedback", action="append", default=[])
        if command == "update":
            p.add_argument("--rounds-done", type=int, default=0)
            p.add_argument("--stop-reason")
            p.add_argument("--accept-workload-delta", action="store_true")
    args = parser.parse_args(argv)
    target = Path(args.state).resolve()
    base = target.parent
    try:
        if args.command == "init" or (args.command == "plan" and not target.exists()):
            artifacts = {key: relative(getattr(args, key), base) for key in ARTIFACT_DEFAULTS}
            result = initialize(base, artifacts, args.input, args.workload, getattr(args, "emitter", None), args.mode,
                                getattr(args, "rounds_per_invocation", 5), getattr(args, "patience", 2),
                                getattr(args, "until_pass", False), getattr(args, "skill", ()))
            if args.command == "init":
                if target.exists():
                    raise ValueError("state already exists; use update")
                target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
            else:
                result = plan(result, base, args.feedback)
        else:
            result = mapping(target)
            if result.get("version") != VERSION:
                raise ValueError("unsupported state version")
            if args.command == "plan":
                result = plan(result, base, args.feedback)
            else:
                result = update(result, base, args.skill, args.rounds_done, args.stop_reason, args.emitter,
                                args.feedback, args.accept_workload_delta, args.rounds_per_invocation, args.patience, args.until_pass)
                target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, yaml.YAMLError):
        # Never print exceptions: parsers include snippets of private input.
        print(json.dumps({"error": "STATE_INPUT_INVALID"}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
