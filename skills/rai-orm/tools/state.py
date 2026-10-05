#!/usr/bin/env python3
"""Persist an ORM route and print a deterministic, content-free resume plan.

Emitter checks execute only in an isolated temporary project copy.
Paths are relative to the working directory (the manifest's parent).
"""

import argparse
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import sys

import yaml


VERSION = 1
KINDS = {"missing_link", "wrong_grain", "merge", "split", "rename", "failing_item", "compact", "note"}
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
ITEM_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
ARTIFACT_DEFAULTS = {
    "model_yaml": "model.orm.yaml", "model_py": "model.py",
    "digest": "workload.digest.yaml",
    "repair_digest": "repair.digest.yaml", "holdout_digest": "holdout.digest.yaml", "verification": "model.verification.json",
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
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
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


def revision(base, artifacts, bindings=()):
    hashes = {key: file_hash(base / artifacts[key]) for key in ("model_yaml", "model_py")}
    if bindings:
        hashes["bindings"] = {relative(Path(b["path"]).resolve() if Path(b["path"]).is_absolute()
                                      else Path(b["path"]), base): file_hash(base / b["path"])
                              for b in bindings}
    return sha(canonical(hashes))


def verified_revision(value):
    if value.get("model_revision"):
        return value["model_revision"]
    rounds = value.get("rounds", [])
    return max(rounds, key=lambda row: int(row["round"])).get("model_revision") if rounds else None


def preserve_workload(base, record):
    """Keep private source bytes outside the content-free manifest, keyed by hash."""
    source = base / record["path"]
    target = base / ".orm-workloads" / (record["sha256"][7:] + source.suffix)
    target.parent.mkdir(exist_ok=True)
    if target.exists() and file_hash(target) != record["sha256"]:
        raise ValueError("workload snapshot corrupted")
    if not target.exists():
        target.write_bytes(source.read_bytes())
    record["snapshot_path"] = relative(target, base)


def sandbox_prefix(folder):
    # A temporary cwd alone is not a sandbox: emitters can use absolute paths.
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("sandbox unavailable")
    runtime = {str(Path(sys.prefix).resolve()), str(Path(sys.base_prefix).resolve()),
               str(Path(sys.executable).resolve().parent.parent)}
    readable = sorted(runtime | {str(folder.resolve()), "/System/Library", "/System/Volumes/Preboot/Cryptexes/OS",
                                "/usr/lib", "/usr/bin", "/bin", "/sbin", "/opt/homebrew/bin", "/usr/local/bin",
                                "/Library/Frameworks", "/Library/Apple", "/opt/homebrew/lib", "/usr/local/lib"})
    filters = " ".join("(subpath " + json.dumps(path) + ")" for path in readable)
    profile = ('(version 1)(allow default)(deny network*)(deny mach-lookup)'
               '(deny file-read*)(allow file-read-metadata)(deny file-write*)(deny process-exec)'
               '(allow file-read* ' + filters + ' (literal "/") (literal "/dev/null") (literal "/dev/urandom"))'
               '(allow file-write* (subpath ' + json.dumps(str(folder.resolve())) + ') (literal "/dev/null"))'
               '(allow process-exec ' + filters + ')')
    return ["/usr/bin/sandbox-exec", "-p", profile]


def emitter_files(base, command, supplied=()):
    paths = set(supplied)
    if command and command != "manual:step-10":
        for token in shlex.split(command):
            if token.endswith(".py"):
                paths.add(relative(token, base))
                break
    records = [{"path": relative(path, base)} for path in sorted(paths)]
    unsafe = path_blockers({"artifacts": {"verification": ARTIFACT_DEFAULTS["verification"]}, "emitter_files": records}, base)
    if unsafe:
        raise UpdateBlocked(unsafe)
    return [{**record, "sha256": file_hash(base / record["path"])} for record in records]


class UnsafeEmitterPath(ValueError):
    def __init__(self, artifact, path):
        self.artifact, self.path = artifact, path


def check_emitter(base, artifacts, command, files):
    if command == "manual:step-10":
        return {"status": "manual"}
    if not command:
        return {"status": "blocked", "id": "EMITTER_REQUIRED"}
    if not files or any(not (base / f["path"]).is_file() for f in files):
        return {"status": "blocked", "id": "EMITTER_UNVERIFIED", "reason": "emitter file missing or unregistered"}
    try:
        keys = [key for key in ("model_yaml", "model_py", "digest", "repair_digest", "holdout_digest")
                if key in artifacts]
        for key, supplied in [(key, artifacts[key]) for key in keys] + [("emitter_file", f["path"]) for f in files]:
            try:
                (base / supplied).resolve().relative_to(base.resolve())
            except ValueError:
                raise UnsafeEmitterPath(key, os.path.relpath(base / supplied, base)) from None
        with tempfile.TemporaryDirectory(prefix="orm-emitter-") as directory:
            root = Path(directory)
            prefix = sandbox_prefix(root)
            project = root / "project"
            shutil.copytree(base, project, symlinks=True,
                            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".orm-workloads"))
            for p in sorted(project.rglob("*")):
                if p.is_symlink():
                    raise UnsafeEmitterPath("symlink", p.relative_to(project).as_posix())
            args = shlex.split(command)
            for index, arg in enumerate(args):
                value = arg.partition("=")[2] if arg.startswith("-") and "=" in arg else arg
                if not Path(value).is_absolute() and ".." in Path(value).parts:
                    raise UnsafeEmitterPath("command_argument", arg)
                if Path(arg).is_absolute():
                    try:
                        args[index] = str(project / Path(arg).resolve().relative_to(base.resolve()))
                    except ValueError:
                        if index != 0:
                            raise UnsafeEmitterPath("command_argument", os.path.relpath(arg, base)) from None
            keys = [key for key in ("model_yaml", "model_py", "digest", "repair_digest", "holdout_digest")
                    if key in artifacts]
            paths = {key: project / (base / artifacts[key]).resolve().relative_to(base.resolve()) for key in keys}
            before = {key: file_hash(path) for key, path in paths.items()}
            result = subprocess.run(prefix + args, cwd=project, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE, text=True, timeout=60,
                                    env={"PATH": str(Path(sys.executable).parent) + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
                                         "HOME": str(root), "TMPDIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"})
            if result.returncode:
                return {"status": "blocked", "id": "EMITTER_UNVERIFIED", "reason": "sandbox command failed",
                        "cause": (result.stderr or "no stderr from command").replace(str(root), "<sandbox>")[-2000:].strip(),
                        "returncode": result.returncode}
            changed = sorted(key for key, path in paths.items() if file_hash(path) != before[key])
            if changed or before["model_py"] is None:
                return {"status": "blocked", "id": "EMITTER_NOT_IDEMPOTENT", "artifacts": changed}
            return {"status": "verified"}
    except UnsafeEmitterPath as error:
        return {"status": "blocked", "id": "EMITTER_UNVERIFIED",
                "reason": "unsafe project path: artifact outside project folder or symlink",
                "artifact": error.artifact, "path": error.path}
    except subprocess.TimeoutExpired:
        return {"status": "blocked", "id": "EMITTER_UNVERIFIED", "reason": "command timed out"}
    except OSError as error:
        return {"status": "blocked", "id": "EMITTER_UNVERIFIED",
                "reason": "sandbox or file operation failed", "errno": error.errno}
    except ValueError as error:
        return {"status": "blocked", "id": "EMITTER_UNVERIFIED",
                "reason": "sandbox unavailable" if str(error) == "sandbox unavailable" else "invalid emitter command or project paths"}


def fact_snapshot(base, artifacts):
    return {str(f["id"]): sha(canonical(f)) for f in mapping(base / artifacts["model_yaml"]).get("fact_types", [])
            if f.get("status") != "rejected"}


def preserve_emitted_facts(base, facts):
    """Keep large fact inventories in an immutable, hash-checked sidecar."""
    data = canonical(facts)
    hashed = sha(data)
    path = base / ".orm-facts" / (hashed[7:] + ".json")
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        raise UpdateBlocked([{"id": "PATH_OUTSIDE_PROJECT", "key": "emitted_facts.snapshot_path"}]) from None
    path.parent.mkdir(exist_ok=True)
    if path.exists() and file_hash(path) != hashed:
        raise UpdateBlocked([{"id": "EMITTED_FACTS_CHANGED"}])
    if not path.exists():
        path.write_bytes(data)
    return {"snapshot_path": relative(path, base), "sha256": hashed}


def regeneration_blockers(state, base):
    previous = state.get("emitted_facts", {})
    if "snapshot_path" in previous and "sha256" in previous:
        path = base / previous["snapshot_path"]
        try:
            path.resolve().relative_to(base.resolve())
        except ValueError:
            return [{"id": "PATH_OUTSIDE_PROJECT", "key": "emitted_facts.snapshot_path"}]
        hashed = file_hash(path)
        if hashed != previous["sha256"]:
            return [{"id": "EMITTED_FACTS_REQUIRED" if hashed is None else "EMITTED_FACTS_CHANGED"}]
        previous = mapping(path)
    current = fact_snapshot(base, state["artifacts"])
    applied_ids = {key for key, hashed in current.items() if previous.get(key) != hashed}
    applied = [f for f in mapping(base / state["artifacts"]["model_yaml"]).get("fact_types", [])
               if str(f["id"]) in applied_ids]
    removed = set(previous) - set(current)
    if not applied and not removed:
        return []
    output = base / state["artifacts"]["model_py"]
    text = output.read_text(encoding="utf-8") if output.is_file() else ""
    def emitted(fact):
        metadata = fact.get("pyrel") or {}
        prop = metadata.get("property") if isinstance(metadata, dict) else None
        # A whole property identifier also matches Owner.property declarations.
        return (str(fact["id"]) in text or bool(fact.get("reading") and fact["reading"] in text)
                or bool(prop and re.search(r"(?<!\w)" + re.escape(prop) + r"(?!\w)", text)))
    missing = sorted(str(f["id"]) for f in applied if not emitted(f))
    if missing or (removed and file_hash(output) == state.get("emitted_py_sha256")):
        return [{"id": "EMITTER_INCOMPLETE", "fact_ids": sorted(applied_ids | removed),
                 "missing_fact_ids": missing, "removed_fact_ids": sorted(removed),
                 "action": "Add pyrel: {owner, property, type} to fact_types entries read by the emitter; regenerate."}]
    return []


def inventory(base, records):
    hashes, blockers = {}, []
    for record in records:
        if record["kind"] != "workload":
            continue
        try:
            current = item_hashes(base / record["path"])
        except (OSError, ValueError, TypeError, UnicodeError, yaml.YAMLError):
            blockers.append({"id": "WORKLOAD_INVALID", "path": record["path"]})
            continue
        overlap = set(hashes) & set(current)
        if overlap:
            blockers.append({"id": "DUPLICATE_WORKLOAD_ID", "item_ids": sorted(overlap)})
        hashes.update(current)
    return hashes, blockers


def reconciliation(base, artifacts, records, verification, snapshot):
    hashes, blockers = inventory(base, records)
    items = verification.get("items", [])
    ids = [str(item["id"]) for item in items]
    if len(ids) != len(set(ids)):
        blockers.append({"id": "DUPLICATE_VERIFICATION_ID"})
    tracked = any(r["kind"] == "workload" for r in records)
    expected = set(hashes) if tracked else {str(item["id"]) for item in snapshot.get("items", [])}
    missing, extra = expected - set(ids), set(ids) - expected
    if missing:
        blockers.append({"id": "VERIFICATION_ITEMS_MISSING", "item_ids": sorted(missing)})
    if tracked and extra:
        blockers.append({"id": "VERIFICATION_ITEMS_REMOVED", "item_ids": sorted(extra)})
    counts = {"verification": verification.get("workload", {}).get("n_items"),
              "digest": mapping(base / artifacts["digest"]).get("workload", {}).get("n_items")}
    if tracked:
        counts["inventory"] = len(hashes)
    for source, count in sorted(counts.items()):
        if count is not None and count != len(ids):
            blockers.append({"id": "WORKLOAD_COUNT_MISMATCH", "source": source,
                             "expected": count, "actual": len(ids)})
    for split, count in (verification.get("split") or {}).items():
        if split in {"repair", "holdout"} and isinstance(count, int):
            actual = sum(item.get("split") == split for item in items)
            if count != actual:
                blockers.append({"id": "SPLIT_COUNT_MISMATCH", "split": split, "expected": count, "actual": actual})
    return hashes, missing, blockers


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


def verification_snapshot(base, path, specs=None):
    value = mapping(base / path)
    items = []
    for item in value.get("items", []):
        identifier = str(item["id"])
        if not ITEM_ID.fullmatch(identifier):
            raise ValueError("invalid item id")
        saved = {key: item[key] for key in ("id", "split", "status", "pyrel", "pyrel_sha256", "passed_at_round", "weak", "spec_hash", "regressed_at_round") if key in item}
        if specs and identifier in specs:
            saved.setdefault("spec_hash", specs[identifier])
        items.append(saved)
    record_missing_pyrel_hashes(base, path, items)
    return {"split": value.get("split"), "oracle": value.get("oracle"),
            "items": sorted(items, key=lambda item: item["id"])}


def last_round(value):
    return max((int(r["round"]) for r in value.get("rounds", [])), default=0)


def stop_reasons(base, artifacts):
    connectivity = mapping(base / artifacts["connectivity"])
    report = mapping(base / artifacts["report"])
    return {"connectivity": ("COMPARISON_CAP_REACHED" if connectivity.get("summary", {}).get("comparison_cap_reached")
                             else connectivity.get("verdict")),
            "report": report.get("status")}


def initialize(base, artifacts, inputs=(), workloads=(), emitter=None, mode=None,
               rounds_per_invocation=5, patience=2, until_pass=False, skills=(), bindings=(),
               emitter_paths=(), persist_inputs=True, refactor_rounds=2):
    if rounds_per_invocation < 1 or patience < 1 or refactor_rounds < 1:
        raise ValueError("positive budgets required")
    supplied_state = {"artifacts": artifacts,
                      "inputs": [{"path": p} for p in (*inputs, *workloads)],
                      "bindings": [{"path": p} for p in bindings],
                      "emitter_files": [{"path": p} for p in emitter_paths]}
    unsafe = path_blockers(supplied_state, base)
    if not unsafe:
        unsafe = path_blockers(supplied_state, base, mapping(base / artifacts["verification"]))
    if unsafe:
        raise UpdateBlocked(unsafe)
    records = []
    seen = set()
    for kind, paths in (("input", inputs), ("workload", workloads)):
        for supplied in paths:
            path = relative(supplied, base)
            if path in seen or (kind != "workload" and not (base / path).is_file()):
                raise ValueError("missing or duplicate input")
            seen.add(path)
            record = {"path": path, "kind": kind, "sha256": file_hash(base / path)}
            if kind == "workload":
                try:
                    record["item_hashes"] = item_hashes(base / path)
                    contributions = mapping(base / artifacts["digest"]).get("item_contributions", {})
                    if isinstance(contributions, dict):
                        record["item_contribution_hashes"] = {i: sha(canonical(contributions[i]))
                                                              for i in sorted(record["item_hashes"]) if i in contributions}
                    if persist_inputs:
                        preserve_workload(base, record)
                except (OSError, ValueError, TypeError, UnicodeError, yaml.YAMLError):
                    record["item_hashes"] = {}
            records.append(record)
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
    binding_records = [{"path": relative(p, base), "sha256": file_hash(base / p)} for p in sorted(bindings)]
    rev = revision(base, artifacts, binding_records)
    files = emitter_files(base, emitter, emitter_paths)
    emitter_check = check_emitter(base, artifacts, emitter, files)
    reasons = stop_reasons(base, artifacts)
    stop = verification.get("summary", {}).get("stopped_because")
    return {"version": VERSION, "inputs": sorted(records, key=lambda record: record["path"]),
            "mode": mode, "budget": {"rounds_per_invocation": rounds_per_invocation, "patience": patience, "until_pass": until_pass, "refactor_rounds": refactor_rounds},
            "model_revision": rev, "artifacts": artifacts, "emitter_command": emitter,
            "skills_run": [{"skill": skill, "rounds_done": counter if skill == "rai-orm-verify" else 0,
                            "stop_reason": stop if skill == "rai-orm-verify" else reasons.get("refactor" if skill == "rai-orm-refactor" else skill),
                            "model_revision": rev} for skill in skills],
            "rounds_used_by_skill_this_invocation": {"rai-orm-verify": 0, "rai-orm-refactor": 0},
            "invocation_rounds": [],
            "round_counters": {skill: counter if skill == "rai-orm-verify" else 0 for skill in skills},
            "artifact_hashes": {key: file_hash(base / path) for key, path in sorted(artifacts.items())},
            "required_artifacts": sorted(key for key, path in artifacts.items() if (base / path).is_file()),
            "retired_artifacts": {},
            "artifact_stop_reasons": reasons, "verification_revision": verified_revision(verification),
            "bindings": binding_records, "emitter_files": files, "emitter_check": emitter_check,
            "emitted_facts": (preserve_emitted_facts(base, fact_snapshot(base, artifacts)) if persist_inputs
                              else fact_snapshot(base, artifacts)), "emitted_py_sha256": file_hash(base / artifacts["model_py"]),
            "verification_snapshot": verification_snapshot(base, artifacts["verification"], inventory(base, records)[0]),
            "last_stop_reason": stop, "feedback_processed": []}


class FeedbackInvalid(ValueError):
    def __init__(self, item_index, field):
        self.item_index, self.field = item_index, field


class UpdateBlocked(ValueError):
    def __init__(self, blockers):
        self.blockers = blockers


def feedback_items(path):
    try:
        value = mapping(path)
    except (OSError, ValueError, UnicodeError, yaml.YAMLError):
        raise FeedbackInvalid(None, "document") from None
    if value.get("version") != 1 or not isinstance(value.get("items"), list):
        raise FeedbackInvalid(None, "version" if value.get("version") != 1 else "items")
    result = []
    for item_index, item in enumerate(value["items"]):
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str) or item["kind"] not in KINDS:
            raise FeedbackInvalid(item_index, "kind")
        kind = item["kind"]
        required = {"missing_link": ("from", "to"), "wrong_grain": ("concept",), "merge": ("concepts",),
                    "split": ("concept",), "rename": ("from", "to"), "failing_item": ("ids",),
                    "compact": ("concept",), "note": ()}[kind]
        if any(key not in item for key in required):
            raise FeedbackInvalid(item_index, next(key for key in required if key not in item))
        # Unknown fields, including note text, contribute only to its fingerprint.
        # Thus arbitrary prose cannot leak through tool output.
        try:
            fingerprint = sha(canonical(item))
        except (ValueError, TypeError):
            raise FeedbackInvalid(item_index, "item") from None
        projected = {"id": item.get("id", "feedback_" + fingerprint[7:19]), "kind": kind,
                     "sha256": fingerprint, "source": "user-feedback", "status": "proposed"}
        for key in ("from", "to", "concept", "concepts", "ids"):
            if key in item:
                values = item[key] if isinstance(item[key], list) else [item[key]]
                pattern = ITEM_ID if key == "ids" else NAME
                if not values or any(not isinstance(v, str) or not pattern.fullmatch(v) for v in values):
                    raise FeedbackInvalid(item_index, key)
                if key in {"concepts", "ids"} and not isinstance(item[key], list):
                    raise FeedbackInvalid(item_index, key)
                projected[key] = sorted(values) if isinstance(item[key], list) else item[key]
        if not isinstance(projected["id"], str) or not ITEM_ID.fullmatch(projected["id"]):
            raise FeedbackInvalid(item_index, "id")
        if kind == "merge" and len(projected["concepts"]) < 2:
            raise FeedbackInvalid(item_index, "concepts")
        result.append(projected)
    if len({item["id"] for item in result}) != len(result):
        raise FeedbackInvalid(next(i for i, item in enumerate(result) if item["id"] in {r["id"] for r in result[:i]}), "id")
    return sorted(result, key=lambda item: item["id"])


def path_blockers(state, base, verification=None):
    paths = [("artifacts." + key, base / path) for key, path in state["artifacts"].items()]
    for field in ("inputs", "emitter_files", "bindings"):
        for index, record in enumerate(state.get(field, [])):
            paths.append((f"{field}[{index}].path", base / record["path"]))
            if record.get("snapshot_path"):
                paths.append((f"{field}[{index}].snapshot_path", base / record["snapshot_path"]))
    emitted = state.get("emitted_facts", {})
    if "snapshot_path" in emitted and "sha256" in emitted:
        paths.append(("emitted_facts.snapshot_path", base / emitted["snapshot_path"]))
    parent = (base / state["artifacts"]["verification"]).parent
    for label, value in (("verification_snapshot", state.get("verification_snapshot", {})),
                         ("verification", verification or {})):
        for index, item in enumerate(value.get("items", [])):
            if item.get("pyrel"):
                paths.append((f"{label}.items[{index}].pyrel", parent / item["pyrel"]))
    blockers = []
    for key, path in paths:
        try:
            path.resolve().relative_to(base.resolve())
        except ValueError:
            blockers.append({"id": "PATH_OUTSIDE_PROJECT", "key": key})
    return sorted(blockers, key=canonical)


def unsafe_plan(state, blockers):
    counter = state.get("round_counters", {}).get("rai-orm-verify", 0)
    budget = {"refactor_rounds": 2, **state.get("budget", {})}
    used = state.get("rounds_used_by_skill_this_invocation", {"rai-orm-verify": 0, "rai-orm-refactor": 0})
    return {"version": VERSION, "steps": [], "baseline_round": counter, "started_round": counter + 1,
            "baseline_model_revision": state.get("model_revision"), "baseline_recheck": True,
            "rounds_used_by_skill_this_invocation": used, "rounds_used_this_invocation": used.get("rai-orm-verify", 0),
            "rounds_remaining_by_skill": {"rai-orm-verify": max(0, budget.get("rounds_per_invocation", 5) - used.get("rai-orm-verify", 0)),
                                         "rai-orm-refactor": max(0, budget["refactor_rounds"] - used.get("rai-orm-refactor", 0))},
            "budget": budget, "mode": state.get("mode"), "frozen_passed_items": [], "saved_pyrel": [],
            "missing_item_ids": [], "refactor_assessment": False, "new_feedback_items": [], "feedback_files": [],
            "workload_delta": {"changed_inputs": [], "new_item_ids": [], "removed_item_ids": [],
                               "changed_item_ids": [], "redigest_item_ids": []},
            "stale_artifacts": [], "artifact_stop_reasons": {}, "blockers": blockers, "can_resume": False}


def split_rule(split):
    return {key: value for key, value in (split or {}).items() if key not in {"repair", "holdout"}}


def plan(state, base, feedback=()):
    if state.get("version") != VERSION:
        raise ValueError("unsupported state version")
    artifacts = {**ARTIFACT_DEFAULTS, **state["artifacts"]}
    unsafe = path_blockers({**state, "artifacts": artifacts}, base)
    if unsafe:
        return unsafe_plan(state, unsafe)
    verification = mapping(base / artifacts["verification"])
    unsafe = path_blockers(state, base, verification)
    if unsafe:
        return unsafe_plan(state, unsafe)
    blockers = []
    def block(code, **details):
        blockers.append({"id": code, **details})
    if not (base / artifacts["model_yaml"]).is_file():
        block("YAML_REQUIRED", path=artifacts["model_yaml"])
    if not (base / artifacts["model_py"]).is_file():
        block("PYREL_REQUIRED", path=artifacts["model_py"], candidates=sorted(
            relative(p, base) for p in base.glob("*.py")
            if p.resolve().is_relative_to(base.resolve()) and "relationalai.semantics" in p.read_text(encoding="utf-8")))
    if not state.get("emitter_command"):
        block("EMITTER_REQUIRED")
    elif state["emitter_command"] != "manual:step-10":
        check = state.get("emitter_check", {"id": "EMITTER_UNVERIFIED", "reason": "no sandbox check recorded"})
        if check.get("status") != "verified":
            blockers.append({key: value for key, value in check.items() if key != "status"})
        for record in state.get("emitter_files", []):
            hashed = file_hash(base / record["path"])
            if hashed is None:
                block("EMITTER_MISSING", path=record["path"])
            elif hashed != record["sha256"]:
                block("EMITTER_CHANGED", path=record["path"])
    for record in state.get("bindings", []):
        if not (base / record["path"]).is_file():
            block("BINDING_MISSING", path=record["path"])
    blockers.extend(regeneration_blockers(state, base))
    for key in ("digest", "repair_digest", "holdout_digest"):
        if key in state.get("required_artifacts", [k for k, v in state["artifact_hashes"].items() if v]) and not (base / artifacts[key]).is_file():
            block("DIGEST_REQUIRED", path=artifacts[key])
    verification = mapping(base / artifacts["verification"])
    snapshot = state["verification_snapshot"]
    if snapshot.get("items") and not verification:
        block("VERIFICATION_REQUIRED", path=artifacts["verification"])
    if snapshot.get("split") is not None and snapshot["split"] != verification.get("split"):
        block("SPLIT_CHANGED", counts_only=split_rule(snapshot["split"]) == split_rule(verification.get("split")))
    if snapshot.get("oracle") and snapshot["oracle"] != verification.get("oracle"):
        block("ORACLE_CHANGED")
    current_items = {item["id"]: item for item in verification.get("items", [])}
    workload_hashes, missing_ids, inventory_blockers = reconciliation(
        base, artifacts, state["inputs"], verification, snapshot)
    blockers.extend(inventory_blockers)
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
        try:
            old, current = record["item_hashes"], item_hashes(path)
        except (OSError, ValueError, TypeError, UnicodeError, yaml.YAMLError):
            if not any(b["id"] == "WORKLOAD_INVALID" and b["path"] == record["path"] for b in blockers):
                block("WORKLOAD_INVALID", path=record["path"])
            continue
        affected = (set(old) - set(current)) | {i for i in set(old) & set(current) if old[i] != current[i]}
        preserved = record.get("snapshot_path")
        if affected and (not preserved or file_hash(base / preserved) != record["sha256"]):
            contributions = mapping(base / artifacts["digest"]).get("item_contributions", {})
            hashes = record.get("item_contribution_hashes", {})
            if not all(i in contributions and hashes.get(i) == sha(canonical(contributions[i])) for i in affected):
                block("WORKLOAD_FULL_REBUILD_REQUIRED", path=record["path"], item_ids=sorted(affected))
        new_ids.update(set(current) - set(old))
        removed_ids.update(set(old) - set(current))
        changed_ids.update(identifier for identifier in set(old) & set(current) if old[identifier] != current[identifier])
    if changed_inputs:
        block("WORKLOAD_DELTA_REVIEW", paths=sorted(changed_inputs))
    changed_specs = {item["id"] for item in snapshot["items"]
                     if item["id"] in workload_hashes and item.get("spec_hash") != workload_hashes[item["id"]]}
    pending_rechecks = sorted(i for i in changed_specs
                             if current_items.get(i, {}).get("spec_hash") != workload_hashes[i]
                             or current_items.get(i, {}).get("status") not in {"pass", "fail", "inexpressible", "oracle-error"})
    if pending_rechecks:
        block("CHANGED_ITEM_RECHECK", item_ids=pending_rechecks)
    for identifier in state.get("regressed_items", []):
        block("REGRESSED_ITEM", item_id=identifier)
    invalidated = removed_ids | changed_ids | changed_specs
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
        saved_path, current_path = item.get("pyrel"), current.get("pyrel")
        parent = (base / artifacts["verification"]).parent
        saved = (parent / saved_path).resolve() if saved_path else None
        referenced = (parent / current_path).resolve() if current_path else None
        if saved != referenced:
            block("PASSED_PYREL_PATH_CHANGED", item_id=item["id"])
        if referenced is None or not referenced.is_file():
            block("PASSED_PYREL_MISSING", item_id=item["id"])
        else:
            current_hash = file_hash(referenced)
            if (item.get("pyrel_sha256") is not None and item["pyrel_sha256"] != current_hash) or (
                    current.get("pyrel_sha256") is not None and current["pyrel_sha256"] != current_hash):
                block("PASSED_PYREL_CHANGED", item_id=item["id"])
    # Check every surviving assignment, including sealed holdout failures.
    for item in snapshot["items"]:
        if item["id"] in current_items and current_items[item["id"]].get("split") != item.get("split"):
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
        try:
            items = feedback_items(path)
        except FeedbackInvalid as error:
            block("FEEDBACK_INVALID", path=path_name, item_index=error.item_index, field=error.field)
            continue
        concepts = {obj["name"] for obj in mapping(base / artifacts["model_yaml"]).get("object_types", [])}
        known_ids = set(workload_hashes) | set(current_items)
        for item in items:
            targets = []
            for key in ("from", "to", "concept", "concepts", "ids"):
                if key not in item or (item["kind"] == "rename" and key == "to") or (item["kind"] == "split" and key == "concepts"):
                    continue
                values = item[key] if isinstance(item[key], list) else [item[key]]
                targets.extend(v for v in values if v not in (known_ids if key == "ids" else concepts))
            if targets:
                block("FEEDBACK_TARGET_UNKNOWN", path=path_name, item_id=item["id"], targets=sorted(targets))
                continue
            if item["sha256"] not in processed_items:
                new_feedback[item["sha256"]] = item
    current_revision = revision(base, artifacts, state.get("bindings", []))
    counter = max(state["round_counters"].get("rai-orm-verify", 0), last_round(verification))
    residual = any(item.get("status") not in {"pass", "inexpressible", "oracle-error"}
                   for item in verification.get("items", []))
    changed_model = (current_revision != state.get("verification_revision") or
                     bool(verification and verified_revision(verification) != current_revision))
    if changed_model and verification:
        block("BASELINE_RECHECK_REQUIRED", item_ids=sorted(frozen))
    stale = sorted(key for key, path in artifacts.items()
                   if file_hash(base / path) != state["artifact_hashes"].get(key))
    dirty = changed_model or bool(pending_rechecks) or bool(state.get("regressed_items")) or bool(new_feedback) or bool(changed_inputs) or bool({"digest", "repair_digest"} & set(stale)) or bool(inventory_blockers) or not verification
    digest = mapping(base / artifacts["digest"])
    has_workload = bool(verification or any(record["kind"] == "workload" for record in state["inputs"])
                        or digest.get("workload", {}).get("n_items"))
    steps = []
    if (changed_inputs and (new_ids or removed_ids or changed_ids)) or (
            not (base / artifacts["digest"]).is_file() and not state["artifact_hashes"].get("digest")
            and any(record["kind"] == "workload" for record in state["inputs"])):
        steps.append("rai-orm-from-workload")
    budget = {"refactor_rounds": 2, **state["budget"]}
    used = dict(state.get("rounds_used_by_skill_this_invocation", {
        "rai-orm-verify": max(0, counter - state.get("invocation_started_round", counter + 1) + 1),
        "rai-orm-refactor": 0}))
    remaining = {"rai-orm-verify": max(0, budget["rounds_per_invocation"] - used.get("rai-orm-verify", 0)),
                 "rai-orm-refactor": max(0, budget["refactor_rounds"] - used.get("rai-orm-refactor", 0))}
    metrics = mapping(base / artifacts["refactor_metrics"])
    metrics_current = metrics.get("model_revision") == current_revision
    if dirty or residual or not (base / artifacts["connectivity"]).is_file():
        steps.append("connectivity")
    assessment = not metrics_current
    if assessment:
        steps.append("rai-orm-refactor:assess")
    if dirty or residual:
        if has_workload and (remaining["rai-orm-verify"] or budget.get("until_pass")):
            steps.append("rai-orm-verify")
    if has_workload and remaining["rai-orm-refactor"] and (dirty or residual or assessment or metrics.get("suspects")):
        steps.append("rai-orm-refactor:accept")
    if state.get("emitter_command") == "manual:step-10":
        steps.insert(0, "manual:step-10")
    if steps or stale or any(not (base / artifacts[key]).is_file() for key in ("report", "report_markdown")):
        steps.append("report")
    return {"version": VERSION, "steps": steps, "baseline_round": counter, "started_round": counter + 1,
            "baseline_model_revision": current_revision, "baseline_recheck": changed_model or bool(pending_rechecks),
            "missing_item_ids": sorted(missing_ids),
            "rounds_used_this_invocation": used.get("rai-orm-verify", 0),
            "rounds_used_by_skill_this_invocation": used, "rounds_remaining_by_skill": remaining,
            "refactor_assessment": assessment,
            "budget": budget, "mode": state["mode"], "frozen_passed_items": sorted(frozen),
            "saved_pyrel": [{"id": item["id"], "path": item.get("pyrel"), "sha256": item.get("pyrel_sha256")}
                            for item in snapshot["items"] if item["id"] in frozen],
            "new_feedback_items": sorted(new_feedback.values(), key=lambda item: (item["id"], item["sha256"])),
            "feedback_files": sorted(pending_files, key=lambda entry: entry["path"]),
            "workload_delta": {"changed_inputs": sorted(changed_inputs), "new_item_ids": sorted(new_ids),
                               "removed_item_ids": sorted(removed_ids), "changed_item_ids": sorted(changed_ids),
                               "redigest_item_ids": sorted(new_ids | changed_ids)},
            "stale_artifacts": stale, "artifact_stop_reasons": stop_reasons(base, artifacts),
            "blockers": sorted(blockers, key=lambda b: canonical(b)), "can_resume": not blockers}


def update(state, base, skill, rounds_done=None, stop_reason=None, emitter=None, feedback=(),
           accept_workload_delta=False, rounds_per_invocation=None, patience=None, until_pass=None,
           accept_pyrel_paths=False, full_rebuild=False, start_invocation=False, refactor_rounds=None,
           bindings=(), emitter_paths=(), drop_emitter_files=(), drop_bindings=(),
           retire_artifacts=(), retire_reason=None, accept_regressions=False):
    # Validate before changing the caller's manifest; failed acceptance is atomic.
    original_state = state
    state = copy.deepcopy(state)
    artifacts = {**ARTIFACT_DEFAULTS, **state["artifacts"]}
    state["artifacts"] = artifacts
    unsafe = path_blockers(state, base)
    if unsafe:
        raise UpdateBlocked(unsafe)
    verification = mapping(base / artifacts["verification"])
    unsafe = path_blockers(state, base, verification)
    if unsafe:
        raise UpdateBlocked(unsafe)
    for field, additions, drops in (("bindings", bindings, drop_bindings),
                                    ("emitter_files", emitter_paths, drop_emitter_files)):
        registered = {r["path"]: r for r in state.get(field, []) if r["path"] not in drops}
        for path in additions:
            path = relative(path, base)
            registered[path] = {"path": path, "sha256": None}
        state[field] = [registered[p] for p in sorted(registered)]
    unsafe = path_blockers(state, base)
    if unsafe:
        raise UpdateBlocked(unsafe)
    for field, additions in (("bindings", bindings), ("emitter_files", emitter_paths)):
        for record in state[field]:
            if record["path"] in {relative(p, base) for p in additions}:
                record["sha256"] = file_hash(base / record["path"])
    if emitter is not None or emitter_paths or drop_emitter_files:
        state["emitter_command"] = emitter if emitter is not None else state.get("emitter_command")
        paths = [r["path"] for r in state["emitter_files"]]
        state["emitter_files"] = emitter_files(base, state["emitter_command"], paths)
        unsafe = path_blockers(state, base)
        if unsafe:
            raise UpdateBlocked(unsafe)
        state["emitter_check"] = check_emitter(base, artifacts, state["emitter_command"], state["emitter_files"])
    state.setdefault("required_artifacts", sorted(k for k, v in state["artifact_hashes"].items() if v))
    for key in retire_artifacts:
        if key not in artifacts or not retire_reason or not retire_reason.strip():
            raise ValueError("artifact key and retirement reason required")
        state.setdefault("retired_artifacts", {})[key] = {"reason": retire_reason}
        state["required_artifacts"] = [k for k in state["required_artifacts"] if k != key]
    if skill == "rai-orm-verify":
        charge = last_round(verification) - state["round_counters"].get(skill, 0)
        if charge < 0 or (rounds_done is not None and rounds_done != charge):
            raise UpdateBlocked([{"id": "ROUNDS_MISMATCH", "recorded": charge, "supplied": rounds_done}])
        rounds_done = charge
    elif rounds_done is None:
        rounds_done = 0
    check = plan(state, base, feedback)
    if accept_workload_delta:
        check["blockers"] = [b for b in check["blockers"] if not (b["id"] == "SPLIT_CHANGED" and b.get("counts_only"))]
    if accept_regressions:
        if skill != "rai-orm-verify":
            raise UpdateBlocked([{"id": "REGRESSION_ACCEPTANCE_INVALID"}])
        previous = {i["id"]: i for i in state["verification_snapshot"]["items"]}
        current = {i["id"]: i for i in verification.get("items", [])}
        lost = {i for i in previous if previous[i].get("status") == "pass" and current.get(i, {}).get("status") != "pass"}
        rounds = {r["round"]: r for r in verification.get("rounds", [])}
        valid = bool(lost)
        for identifier in lost:
            item = current.get(identifier, {})
            number = item.get("regressed_at_round")
            row = rounds.get(number, {})
            regressions = sum(current.get(i, {}).get("regressed_at_round") == number for i in lost)
            fixes = sum(i.get("status") == "pass" and i.get("passed_at_round") == number
                        and previous.get(i["id"], {}).get("status") != "pass" for i in current.values())
            valid &= (item.get("status") == "fail" and isinstance(number, int)
                      and number > state["round_counters"].get(skill, 0)
                      and row.get("regressions") == regressions and row.get("fixes") == fixes and fixes > regressions)
        if not valid:
            raise UpdateBlocked([{"id": "REGRESSION_ACCEPTANCE_INVALID"}])
        state["regressed_items"] = sorted(set(state.get("regressed_items", [])) | lost)
        check["blockers"] = [b for b in check["blockers"] if not (b["id"] == "BASELINE_PASS_LOST" and b.get("item_id") in lost)]
    current_items = {i["id"]: i for i in verification.get("items", [])}
    if any(current_items.get(i, {}).get("status") not in {"pass", "fail"} for i in state.get("regressed_items", [])):
        raise UpdateBlocked([{"id": "REGRESSED_ITEM", "item_id": i} for i in state["regressed_items"]
                             if current_items.get(i, {}).get("status") not in {"pass", "fail"}])
    required = {"PATH_OUTSIDE_PROJECT", "WORKLOAD_INVALID", "DUPLICATE_WORKLOAD_ID", "DUPLICATE_VERIFICATION_ID",
                "VERIFICATION_ITEMS_MISSING", "VERIFICATION_ITEMS_REMOVED", "WORKLOAD_COUNT_MISMATCH",
                "EMITTED_FACTS_REQUIRED", "EMITTED_FACTS_CHANGED", "SPLIT_COUNT_MISMATCH", "EMITTER_INCOMPLETE", "EMITTER_MISSING", "EMITTER_CHANGED"}
    if skill == "rai-orm-refactor":
        required.add("REGRESSED_ITEM")
    if feedback:
        required.update({"FEEDBACK_INVALID", "FEEDBACK_TARGET_UNKNOWN", "FEEDBACK_MISSING"})
    if accept_workload_delta and not full_rebuild:
        required.add("WORKLOAD_FULL_REBUILD_REQUIRED")
    if skill in {"rai-orm-verify", "rai-orm-refactor"} or accept_workload_delta:
        required.update({"PASSED_PYREL_PATH_CHANGED", "PASSED_PYREL_CHANGED", "PASSED_PYREL_MISSING",
                         "BASELINE_PASS_LOST", "ITEM_SPLIT_CHANGED", "SPLIT_CHANGED", "ORACLE_CHANGED",
                         "SPLIT_ASSIGNMENTS_REQUIRED"})
        if accept_pyrel_paths:
            required -= {"PASSED_PYREL_PATH_CHANGED", "PASSED_PYREL_CHANGED"}
        if skill == "rai-orm-verify":
            required.add("CHANGED_ITEM_RECHECK")
        if skill == "rai-orm-verify" and verified_revision(verification) != revision(base, artifacts, state.get("bindings", [])):
            required.add("BASELINE_RECHECK_REQUIRED")
            check["blockers"].append({"id": "BASELINE_RECHECK_REQUIRED", "reason": "record current model_revision after rechecking"})
    if accept_pyrel_paths:
        for item in verification.get("items", []):
            if item.get("status") == "pass":
                referenced = (base / artifacts["verification"]).parent / item.get("pyrel", "")
                if not referenced.is_file() or item.get("pyrel_sha256") != file_hash(referenced):
                    check["blockers"].append({"id": "PYREL_ACCEPTANCE_UNVERIFIED", "item_id": item["id"]})
        required.add("PYREL_ACCEPTANCE_UNVERIFIED")
        if skill != "rai-orm-verify":
            raise UpdateBlocked([{"id": "PYREL_ACCEPTANCE_UNVERIFIED"}])
    blocked = [b for b in check["blockers"] if b["id"] in required]
    if blocked:
        raise UpdateBlocked(blocked)
    if start_invocation:
        state.setdefault("invocation_rounds", []).append({
            "started_round": state.get("invocation_started_round", state["round_counters"].get("rai-orm-verify", 0) + 1),
            "rounds_by_skill": dict(check["rounds_used_by_skill_this_invocation"])})
    if "rounds_used_by_skill_this_invocation" not in state:
        state["rounds_used_by_skill_this_invocation"] = dict(check["rounds_used_by_skill_this_invocation"])
    if start_invocation:
        state["rounds_used_by_skill_this_invocation"] = {"rai-orm-verify": 0, "rai-orm-refactor": 0}
    state["budget"].setdefault("refactor_rounds", 2)
    if start_invocation or "invocation_started_round" not in state:
        state["invocation_started_round"] = state["round_counters"].get("rai-orm-verify", 0) + 1
    if rounds_done < 0:
        raise ValueError("negative rounds")
    if not NAME.fullmatch(skill) or (stop_reason is not None and not NAME.fullmatch(stop_reason)):
        raise ValueError("step metadata must be identifiers")
    for key, value in (("rounds_per_invocation", rounds_per_invocation), ("refactor_rounds", refactor_rounds), ("patience", patience), ("until_pass", until_pass)):
        if value is not None:
            if key != "until_pass" and value < 1:
                raise ValueError("positive budgets required")
            state["budget"][key] = value
    used = state["rounds_used_by_skill_this_invocation"]
    allowance = {"rai-orm-verify": "rounds_per_invocation", "rai-orm-refactor": "refactor_rounds"}
    if skill in allowance:
        new_used = used.get(skill, 0) + rounds_done
        if new_used > state["budget"][allowance[skill]] and not (skill == "rai-orm-verify" and state["budget"].get("until_pass")):
            raise UpdateBlocked([{"id": "BUDGET_EXHAUSTED", "skill": skill}])
        used[skill] = new_used
    if accept_workload_delta:
        # The agent has reviewed the delta, re-digested only added/changed ids,
        # and preserved surviving split assignments before advancing the hashes.
        for record in state["inputs"]:
            if record["kind"] == "workload":
                record["sha256"] = file_hash(base / record["path"])
                record["item_hashes"] = item_hashes(base / record["path"])
                preserve_workload(base, record)
                # Old contributions must never be reused for a newly accepted source version.
                record.pop("item_contributions", None)
                contributions = mapping(base / artifacts["digest"]).get("item_contributions", {})
                record["item_contribution_hashes"] = {i: sha(canonical(contributions[i]))
                                                      for i in sorted(record["item_hashes"]) if i in contributions}
    rev = revision(base, state["artifacts"], state.get("bindings", []))
    state["skills_run"].append({"skill": skill, "rounds_done": rounds_done, "stop_reason": stop_reason, "model_revision": rev})
    counters = state["round_counters"]
    counters[skill] = counters.get(skill, 0) + rounds_done
    if skill == "rai-orm-verify":
        state["verification_revision"] = rev
        counters[skill] = max(counters[skill], last_round(mapping(base / state["artifacts"]["verification"])))
        state["verification_snapshot"] = verification_snapshot(base, state["artifacts"]["verification"], inventory(base, state["inputs"])[0])
        state["regressed_items"] = [i for i in state.get("regressed_items", []) if current_items.get(i, {}).get("status") != "pass"]
    elif accept_workload_delta:
        previous = {i["id"]: i for i in state["verification_snapshot"]["items"]}
        specs = inventory(base, state["inputs"])[0]
        state["verification_snapshot"] = verification_snapshot(base, state["artifacts"]["verification"], specs)
        for item in state["verification_snapshot"]["items"]:
            old = previous.get(item["id"], {})
            if old and old.get("spec_hash") != specs.get(item["id"]) and current_items.get(item["id"], {}).get("spec_hash") != specs.get(item["id"]):
                item["spec_hash"] = old.get("spec_hash")
                if item.get("status") == "pass":
                    item["status"] = "unverified"
    record_missing_pyrel_hashes(base, state["artifacts"]["verification"], state["verification_snapshot"]["items"])
    state["emitted_facts"] = preserve_emitted_facts(base, fact_snapshot(base, artifacts))
    state["emitted_py_sha256"] = file_hash(base / artifacts["model_py"])
    if skill == "rai-orm-verify":
        for binding in state.get("bindings", []):
            binding["sha256"] = file_hash(base / binding["path"])
    state["rounds_used_this_invocation"] = used.get("rai-orm-verify", 0)
    state["model_revision"] = rev
    state["last_stop_reason"] = stop_reason
    state["artifact_hashes"] = {key: file_hash(base / path) for key, path in sorted(state["artifacts"].items())}
    state["required_artifacts"] = sorted(set(state["required_artifacts"]) | {
        k for k, v in state["artifact_hashes"].items() if v and k not in state.get("retired_artifacts", {})})
    for record in state["inputs"]:
        legacy = record.pop("item_contributions", {})
        if legacy:
            record.setdefault("item_contribution_hashes", {i: sha(canonical(v)) for i, v in sorted(legacy.items())})
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
    original_state.clear()
    original_state.update(state)
    return original_state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "update", "plan"):
        p = sub.add_parser(command)
        p.add_argument("--state", default="orm-state.json")
        p.add_argument("--refactor-rounds", type=int, default=2 if command == "init" else None)
        if command in {"init", "plan"}:
            for key, default in ARTIFACT_DEFAULTS.items():
                p.add_argument("--" + key.replace("_", "-"), default=default)
            p.add_argument("--input", action="append", default=[])
            p.add_argument("--workload", action="append", default=[])
            p.add_argument("--binding", action="append", default=[])
            p.add_argument("--emitter-file", action="append", default=[])
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
            p.add_argument("--rounds-done", type=int)
            p.add_argument("--binding", action="append", default=[])
            p.add_argument("--emitter-file", action="append", default=[])
            p.add_argument("--drop-binding", action="append", default=[])
            p.add_argument("--drop-emitter-file", action="append", default=[])
            p.add_argument("--retire-artifact", action="append", default=[])
            p.add_argument("--retire-reason")
            p.add_argument("--accept-regressions", action="store_true")
            p.add_argument("--stop-reason")
            p.add_argument("--accept-workload-delta", action="store_true")
            p.add_argument("--accept-pyrel-paths", action="store_true")
            p.add_argument("--full-rebuild", action="store_true")
            p.add_argument("--start-invocation", action="store_true")
    args = parser.parse_args(argv)
    target = Path(args.state).resolve()
    base = target.parent
    try:
        if args.command == "init" or (args.command == "plan" and not target.exists()):
            if args.command == "init" and target.exists():
                raise ValueError("state already exists; use update")
            artifacts = {key: relative(getattr(args, key), base) for key in ARTIFACT_DEFAULTS}
            result = initialize(base, artifacts, args.input, args.workload, getattr(args, "emitter", None), args.mode,
                                getattr(args, "rounds_per_invocation", 5), getattr(args, "patience", 2),
                                getattr(args, "until_pass", False), getattr(args, "skill", ()),
                                args.binding, args.emitter_file, persist_inputs=args.command == "init",
                                refactor_rounds=args.refactor_rounds if args.refactor_rounds is not None else 2)
            if args.command == "init":
                if target.exists():
                    raise ValueError("state already exists; use update")
                target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            else:
                result = plan(result, base, args.feedback)
        else:
            result = mapping(target)
            if result.get("version") != VERSION:
                raise ValueError("unsupported state version")
            if args.command == "plan":
                if args.refactor_rounds is not None:
                    if args.refactor_rounds < 1:
                        raise ValueError("positive budgets required")
                    result["budget"]["refactor_rounds"] = args.refactor_rounds
                result = plan(result, base, args.feedback)
            else:
                result = update(result, base, args.skill, args.rounds_done, args.stop_reason, args.emitter,
                                args.feedback, args.accept_workload_delta, args.rounds_per_invocation, args.patience, args.until_pass,
                                args.accept_pyrel_paths, args.full_rebuild, args.start_invocation, args.refactor_rounds,
                                args.binding, args.emitter_file, args.drop_emitter_file, args.drop_binding,
                                args.retire_artifact, args.retire_reason, args.accept_regressions)
                target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if args.command in {"init", "update"}:
            checked = plan(result, base)
            result = {"version": result["version"], "round_counters": result["round_counters"],
                      "model_revision": result["model_revision"], "budget": result["budget"],
                      "rounds_used_by_skill_this_invocation": result["rounds_used_by_skill_this_invocation"],
                      "blockers": sorted({b["id"] for b in checked["blockers"]}), "can_resume": checked["can_resume"]}
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except UpdateBlocked as error:
        print(json.dumps({"blockers": error.blockers, "can_resume": False}, sort_keys=True))
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError, yaml.YAMLError):
        # Never print exceptions: parsers include snippets of private input.
        print(json.dumps({"error": "STATE_INPUT_INVALID"}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
