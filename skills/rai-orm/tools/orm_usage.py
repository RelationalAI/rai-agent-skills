"""Shared static, per-item concept usage; never executes saved rewrites."""

import ast
from pathlib import Path


def referenced_symbols(source):
    """Names and attributes only: comments and string literals cannot add support."""
    tree = ast.parse(source)
    symbols = set()
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            symbols.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            symbols.add(node.attr)
    # An import without a use does not count; an alias used as a root does.
    symbols.update(aliases[s] for s in list(symbols) if s in aliases)
    return symbols


def workload_support(entities, verification, verification_dir, digest):
    if verification is None:
        return {"status": "unavailable", "saved_items": 0}, None
    items = verification.get("items") or []
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    item_ids = [item["id"] for item in items]
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("duplicate workload ids")
    totals = [len(items), (verification.get("workload") or {}).get("n_items", 0),
              ((digest or {}).get("workload") or {}).get("n_items", 0)]
    expected = max(totals)
    support = {eid: set() for eid in entities}
    missing, invalid, saved = [], [], 0
    for item in sorted(items, key=lambda entry: entry["id"]):
        item_id = item["id"]
        if not isinstance(item_id, str):
            raise ValueError("invalid item id")
        if not item.get("pyrel"):
            missing.append(item_id)
            continue
        try:
            path = Path(item["pyrel"])
            if not path.is_absolute():
                path = Path(verification_dir) / path
            symbols = referenced_symbols(path.read_text(encoding="utf-8"))
        except OSError:
            missing.append(item_id)
            continue
        except (SyntaxError, UnicodeError):
            invalid.append(item_id)
            continue
        saved += 1
        for eid, entity in entities.items():
            if entity["name"] in symbols or eid in symbols:
                support[eid].add(item_id)
    status = "unavailable" if saved == 0 else "complete" if saved == expected else "partial"
    coverage = {"status": status, "saved_items": saved, "expected_items": expected,
                "missing_items": missing, "invalid_items": invalid}
    return coverage, support if saved else None


