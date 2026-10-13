#!/usr/bin/env python3
"""Check a generated PyRel model file against the rai-orm-conventions design rules.

Static analysis only: the file is parsed, never imported or executed. Findings are
printed as JSON; the exit code is 1 when any error-level finding exists.

Usage:
    python lint_model.py model.py [--abbrev extra,tokens] [--max-properties 40]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Generic column-suffix tokens that show a name or reading was copied from a raw column.
# Add project abbreviations with --abbrev.
RAW_TOKENS = {
    "ind", "cd", "nbr", "num", "dt", "dtm", "desc", "txt", "flg", "amt", "qty", "cnt", "typ",
    "sts", "stat", "nm", "val", "pct", "seq", "src", "tgt", "ref", "lkp", "xref",
}
AUDIT_RE = re.compile(r"(^|_)(load|etl|batch|insrt|snflk|dw|audit)(_|$)|(^|_)rec_(crt|updt)(_|$)|_dt_tm$", re.IGNORECASE)
PII_RE = re.compile(
    r"(^|_)(frst_nm|first_name|lst_nm|last_name|full_name|full_nm|ssn|tax_id|birth_date|dob|email_address|street_name|street_number|addr_line_\d|unit_number)$",
    re.IGNORECASE,
)


@dataclass
class Decl:
    owner: str
    name: str
    kind: str  # "Property" or "Relationship"
    reading: str
    concepts: list[str]  # concept placeholders in the reading, in order
    value_types: list[str]  # non-concept typed placeholders, e.g. String, Boolean
    line: int


@dataclass
class ModelInfo:
    concepts: dict[str, list[str]] = field(default_factory=dict)  # name -> extends
    decls: list[Decl] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model_file", type=Path)
    parser.add_argument("--abbrev", default="", help="Comma-separated extra raw-column tokens to flag.")
    parser.add_argument("--max-properties", type=int, default=40, help="Warn when a concept has more properties than this.")
    args = parser.parse_args()

    raw_tokens = RAW_TOKENS | {token.strip().lower() for token in args.abbrev.split(",") if token.strip()}
    info = parse_model(args.model_file.read_text(encoding="utf-8"))
    findings = check(info, raw_tokens=raw_tokens, max_properties=args.max_properties)
    summary = {
        "concepts": len(info.concepts),
        "declarations": len(info.decls),
        "errors": sum(1 for f in findings if f["level"] == "error"),
        "warnings": sum(1 for f in findings if f["level"] == "warning"),
        "by_rule": _count_by(findings, "rule"),
    }
    print(json.dumps({"summary": summary, "findings": findings}, indent=2))
    return 1 if summary["errors"] else 0


def parse_model(source: str) -> ModelInfo:
    info = ModelInfo()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        method = call.func.attr if isinstance(call.func, ast.Attribute) else None
        if method == "Concept":
            name = _const_str(call.args[0]) if call.args else None
            if name:
                info.concepts[name] = _extends(call)
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id != name:
                        info.concepts.setdefault(target.id, info.concepts[name])
        elif method in {"Property", "Relationship"} and call.args:
            target = node.targets[0]
            owner, name = _target(target)
            reading, placeholders = _reading(call.args[0])
            info.decls.append(
                Decl(
                    owner=owner,
                    name=name,
                    kind=method,
                    reading=reading,
                    concepts=[p for p, _ in placeholders],
                    value_types=[],
                    line=node.lineno,
                )
            )
    for decl in info.decls:
        decl.value_types = [p for p in decl.concepts if p not in info.concepts]
        decl.concepts = [p for p in decl.concepts if p in info.concepts]
        if not decl.owner and decl.concepts:
            decl.owner = decl.concepts[0]
    return info


def check(info: ModelInfo, *, raw_tokens: set[str], max_properties: int) -> list[dict]:
    findings: list[dict] = []

    def add(rule: str, level: str, decl: Decl | None, message: str, **extra) -> None:
        item = {"rule": rule, "level": level, "message": message}
        if decl is not None:
            item.update({"line": decl.line, "declaration": f"{decl.owner}.{decl.name}"})
        item.update(extra)
        findings.append(item)

    for decl in info.decls:
        is_unary = len(decl.concepts) == 1 and not decl.value_types
        # Rule 2: flags are unary Property declarations with business names.
        if is_unary and decl.kind == "Relationship":
            add("R2", "error", decl, "Unary flag declared as Relationship; declare it as model.Property so the subsetter sees it.")
        if decl.value_types == ["Boolean"] and len(decl.concepts) == 1:
            add("R2", "warning", decl, "Boolean-valued property; prefer a unary flag reading such as '{Customer} is an active customer'.")
        raw_name = sorted(set(_tokens(decl.name)) & raw_tokens)
        if raw_name:
            add("R2/R5", "warning", decl, f"Name looks copied from a raw column (tokens: {', '.join(raw_name)}).")
        raw_reading = sorted(set(_tokens(re.sub(r"\{[^}]*\}", " ", decl.reading))) & raw_tokens)
        if raw_reading:
            add("R5", "warning", decl, f"Reading uses raw-column words (tokens: {', '.join(raw_reading)}); give it business meaning.")
        # Rule 5: no audit or PII properties.
        if AUDIT_RE.search(decl.name):
            add("R5", "error", decl, "Load or audit column kept as a property.")
        if PII_RE.search(decl.name):
            add("R5", "error", decl, "PII column kept as a property.")

    # Rule 1: the same attribute should not be copied onto several unrelated concepts.
    owners_by_name: dict[str, set[str]] = defaultdict(set)
    for decl in info.decls:
        if decl.value_types:
            owners_by_name[decl.name].add(decl.owner)
    for name, owners in sorted(owners_by_name.items()):
        unrelated = _unrelated(owners, info.concepts)
        if len(unrelated) > 1:
            findings.append(
                {
                    "rule": "R1",
                    "level": "warning",
                    "message": f"Attribute '{name}' is declared on several unrelated concepts; keep one copy on the owning entity.",
                    "concepts": sorted(unrelated),
                }
            )

    # Rules 4 and 6: every concept should be linked to the rest of the model.
    linked: set[str] = set()
    for decl in info.decls:
        if len(decl.concepts) >= 2:
            linked.update(decl.concepts)
    for concept, extends in info.concepts.items():
        if extends:
            linked.add(concept)
            linked.update(extends)
    for concept in sorted(set(info.concepts) - linked):
        findings.append(
            {"rule": "R4/R6", "level": "warning", "message": f"Concept '{concept}' has no link to another concept.", "concept": concept}
        )
    for decl in info.decls:
        if len(decl.concepts) >= 2 and decl.kind == "Relationship":
            add("R6", "warning", decl, "Entity link declared as Relationship; a Property on the owning concept travels with it.")

    # Rule 5: keep concepts small.
    per_owner: dict[str, int] = defaultdict(int)
    for decl in info.decls:
        per_owner[decl.owner] += 1
    for owner, count in sorted(per_owner.items()):
        if count > max_properties:
            findings.append(
                {"rule": "R5", "level": "warning", "message": f"Concept '{owner}' has {count} declarations (limit {max_properties}).", "concept": owner}
            )
    return findings


def _unrelated(owners: set[str], concepts: dict[str, list[str]]) -> set[str]:
    """Collapse owners that share a supertype chain; what remains are unrelated copies."""

    def root(name: str) -> str:
        seen = set()
        while concepts.get(name) and name not in seen:
            seen.add(name)
            name = concepts[name][0]
        return name

    return {root(owner) for owner in owners}


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def _const_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _extends(call: ast.Call) -> list[str]:
    for keyword in call.keywords:
        if keyword.arg == "extends" and isinstance(keyword.value, (ast.List, ast.Tuple)):
            return [elt.id for elt in keyword.value.elts if isinstance(elt, ast.Name)]
    return []


def _target(target: ast.AST) -> tuple[str, str]:
    if isinstance(target, ast.Attribute):
        owner = target.value.id if isinstance(target.value, ast.Name) else ""
        return owner, target.attr
    if isinstance(target, ast.Name):
        return "", target.id
    return "", "?"


def _reading(node: ast.AST) -> tuple[str, list[tuple[str, str]]]:
    """Return the reading text and its placeholders as (type_or_concept, role_name)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, []
    if not isinstance(node, ast.JoinedStr):
        return "", []
    parts, placeholders = [], []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            name = value.value.id if isinstance(value.value, ast.Name) else "?"
            spec = ""
            if isinstance(value.format_spec, ast.JoinedStr):
                spec = "".join(str(v.value) for v in value.format_spec.values if isinstance(v, ast.Constant))
            placeholders.append((name, spec))
            parts.append("{" + name + (":" + spec if spec else "") + "}")
    return "".join(parts), placeholders


def _count_by(findings: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for finding in findings:
        counts[finding[key]] += 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
