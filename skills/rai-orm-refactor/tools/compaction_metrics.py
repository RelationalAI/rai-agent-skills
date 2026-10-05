"""Deterministic, metadata-only ORM compaction hints; never executes PyRel."""

import argparse
import copy
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from usage_scanner import workload_support


FLAG_THRESHOLD = 4
REASON_PRIORITY = {
    "flag-explosion": 100,
    "duplicate-structure": 80,
    "table-mirror": 70,
    "single-item": 50,
    "workload-derived": 60,
}


class MetadataArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error includes arbitrary command-line argument text.
        print(json.dumps({"error": "invalid-arguments"}), file=sys.stderr)
        raise SystemExit(2)


def load_mapping(path):
    with Path(path).open(encoding="utf-8") as stream:
        result = yaml.safe_load(stream)
    if not isinstance(result, dict):
        raise ValueError("mapping required")
    return result


def bindings(concept):
    """Only declared bindings, not guessed bindings through related entities."""
    provenance = concept.get("provenance") or {}
    tables = provenance.get("tables") or []
    if not isinstance(tables, list) or not all(isinstance(t, str) for t in tables):
        raise ValueError("invalid table names")
    if provenance.get("table"):
        tables = tables + [provenance["table"]]
    if not all(isinstance(t, str) for t in tables):
        raise ValueError("invalid table names")
    return sorted(set(tables))


def property_descriptor(fact, role_index, objects):
    """Signature ignores source tables and owner ids, retains semantic role shape."""
    roles = fact["roles"]
    targets = []
    for index, role in enumerate(roles):
        if index == role_index:
            continue
        target = objects[role["object_type"]]
        target_shape = (target["kind"], target.get("primitive") if target["kind"] == "value"
                        else target["id"])
        targets.append((role["role_name"], target_shape))
    # Normalize each fact's constraint roles by position, so owner names may differ.
    positions = {role["role_name"]: index for index, role in enumerate(roles)}
    uniqueness = sorted(tuple(sorted(positions[r] for r in constraint.get("roles", [])))
                        for constraint in fact.get("constraints", [])
                        if constraint.get("type") == "uniqueness"
                        and constraint.get("status") != "rejected")
    mandatory = sorted(positions[constraint["role"]]
                       for constraint in fact.get("constraints", [])
                       if constraint.get("type") == "mandatory"
                       and constraint.get("status") != "rejected")
    # Unary role names normally name the owner; the fact id is the predicate name.
    unary_name = fact["id"] if len(roles) == 1 else None
    return (len(roles), role_index, tuple(targets), unary_name,
            tuple(uniqueness), tuple(mandatory), fact.get("derivation", "asserted"))


def measure(model, verification=None, digest=None, verification_dir="."):
    model = copy.deepcopy(model)
    objects_list = model["object_types"]
    facts = model["fact_types"]
    if not isinstance(objects_list, list) or not isinstance(facts, list):
        raise ValueError("invalid model lists")
    objects = {obj["id"]: obj for obj in objects_list}
    if len(objects) != len(objects_list) or len({f["id"] for f in facts}) != len(facts):
        raise ValueError("duplicate model ids")
    if any(obj.get("kind") not in {"entity", "value"} or not isinstance(obj["name"], str)
           for obj in objects.values()):
        raise ValueError("invalid object type")
    for fact in facts:
        for role in fact["roles"]:
            target = objects.get(role["object_type"], {})
            name = target.get("name", role["object_type"])
            role.setdefault("role_name", name[:1].lower() + name[1:])
    entities = {eid: obj for eid, obj in sorted(objects.items()) if obj["kind"] == "entity"}
    properties, unary, booleans, signatures = (defaultdict(set) for _ in range(4))
    for fact in facts:
        roles = fact["roles"]
        if not roles or any(role["object_type"] not in objects for role in roles):
            raise ValueError("unresolved fact roles")
        for index, role in enumerate(roles):
            eid = role["object_type"]
            if eid not in entities:
                continue
            properties[eid].add(fact["id"])
            signatures[eid].add(property_descriptor(fact, index, objects))
            if len(roles) == 1:
                unary[eid].add(fact["id"])
                if "_appears_in_" not in fact["id"] and (fact.get("provenance") or {}).get("origin") != "source-membership":
                    booleans[eid].add(fact["id"])
            elif len(roles) == 2 and any(objects[r["object_type"]].get("primitive") == "Boolean"
                                         for r in roles):
                booleans[eid].add(fact["id"])

    tables = defaultdict(list)
    bound = {}
    for eid, entity in entities.items():
        bound[eid] = sorted(set(bindings(entity)) | {b["table"] for b in model.get("source_bindings", [])
                                                    if b.get("object_type") == eid})
        for table in bound[eid]:
            tables[table].append(eid)
    declared_tables = (model.get("source", {}).get("scope") or {}).get("tables", [])
    for table in declared_tables:
        if table != "*":
            tables.setdefault(table, [])
    for entry in (digest or {}).get("tables", []):
        tables.setdefault(entry["table"], [])

    duplicates = defaultdict(list)
    for eid in entities:
        if signatures[eid]:
            signature = tuple(sorted(signatures[eid], key=repr))
            duplicates[signature].append(eid)
    groups = sorted((members for members in duplicates.values() if len(members) > 1),
                    key=lambda members: tuple(members))
    flag_explosions = [{"concept": eid, "count": len(booleans[eid]),
                        "fact_types": sorted(booleans[eid])}
                       for eid in entities if len(booleans[eid]) >= FLAG_THRESHOLD]

    mirrors = []
    for fact in sorted(facts, key=lambda f: f["id"]):
        roles = fact["roles"]
        if len(roles) != 2:
            continue
        left, right = [role["object_type"] for role in roles]
        if left == right or left not in entities or right not in entities:
            continue
        singleton_keys = {tuple(c.get("roles", [])) for c in fact.get("constraints", [])
                          if c.get("type") == "uniqueness" and c.get("status") == "confirmed"}
        if not all((role["role_name"],) in singleton_keys for role in roles):
            continue
        if len(bound[left]) != 1 or len(bound[right]) != 1 or bound[left] == bound[right]:
            continue
        if any(len(tables[t]) != 1 for t in bound[left] + bound[right]):
            continue
        mirrors.append({"concepts": sorted([left, right]), "fact_type": fact["id"],
                        "tables": sorted(bound[left] + bound[right])})

    coverage, support = workload_support(entities, verification, verification_dir, digest)
    single = sorted(eid for eid in entities if support is not None and len(support[eid]) == 1)
    suspects = []

    def add(eid, reason, related=()):
        suspects.append({"concept": eid, "name": entities[eid]["name"], "reason": reason,
                         "priority": REASON_PRIORITY[reason], "related": sorted(related)})

    for explosion in flag_explosions:
        add(explosion["concept"], "flag-explosion", explosion["fact_types"])
    for group in groups:
        for eid in group:
            add(eid, "duplicate-structure", set(group) - {eid})
    for mirror in mirrors:
        for eid in mirror["concepts"]:
            add(eid, "table-mirror", [mirror["fact_type"]])
    for eid in entities:
        if not bound[eid] and (entities[eid].get("provenance") or {}).get("origin") == "workload":
            add(eid, "workload-derived")
    for eid in single:
        add(eid, "single-item", support[eid])
        suspects[-1].update(coverage=coverage["status"], lower_bound=coverage["status"] != "complete")
        if coverage["status"] != "complete":
            suspects[-1]["priority"] = 25
    suspects.sort(key=lambda entry: (-entry["priority"], entry["concept"],
                                     entry["reason"], entry["related"]))
    distribution = Counter(len(properties[eid]) for eid in entities)
    unbound = [eid for eid in entities if not bound[eid]]
    return {
        "version": 1,
        "concepts": len(entities),
        "concept_names": [obj["name"] for obj in entities.values()],
        "source_tables": len(tables),
        "concepts_per_source_table": [{"table": table, "count": len(members), "concepts": members}
                                      for table, members in sorted(tables.items())],
        "properties_per_concept": [{"concept": eid, "count": len(properties[eid]),
                                    "fact_types": sorted(properties[eid])} for eid in entities],
        "property_distribution": [{"properties": count, "concepts": number}
                                  for count, number in sorted(distribution.items())],
        "unary_flags_per_concept": [{"concept": eid, "count": len(unary[eid]),
                                     "fact_types": sorted(unary[eid])} for eid in entities],
        "unbound_concepts": unbound,
        "derived_only_concepts": [eid for eid in unbound
                                  if entities[eid].get("derivation") == "derived"],
        "support_coverage": coverage,
        "concept_support": None if support is None else [
            {"concept": eid, "count": len(support[eid]), "items": sorted(support[eid])}
            for eid in entities],
        "single_item_concepts": None if support is None else single,
        "duplicate_structure_concepts": groups,
        "flag_explosions": flag_explosions,
        "table_mirrors": mirrors,
        "suspects": suspects,
    }


def main(argv=None):
    parser = MetadataArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--verification")
    parser.add_argument("--digest")
    parser.add_argument("--model-revision", help="revision from state.py plan for assessment freshness")
    parser.add_argument("--out", default="compaction.json")
    args = parser.parse_args(argv)
    try:
        result = measure(load_mapping(args.model),
                         load_mapping(args.verification) if args.verification else None,
                         load_mapping(args.digest) if args.digest else None,
                         Path(args.verification).parent if args.verification else Path("."))
        if args.model_revision:
            result["model_revision"] = args.model_revision
        # Refuse to overwrite inputs, including saved rewrites referenced by the report.
        inputs = [Path(p).resolve() for p in [args.model, args.verification, args.digest] if p]
        if args.verification:
            report = load_mapping(args.verification)
            for item in report.get("items", []):
                if item.get("pyrel"):
                    inputs.append((Path(args.verification).parent / item["pyrel"]).resolve())
        if Path(args.out).resolve() in inputs:
            raise ValueError("output aliases input")
        Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError):
        # Exception messages can contain input text, filenames, or SQL literals.
        print(json.dumps({"error": "invalid-input-or-output"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
