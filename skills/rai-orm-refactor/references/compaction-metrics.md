# Compaction metrics

The tool reads ORM metadata and statically parses saved PyRel. It never runs queries or copies readings, derivation text, SQL, literals, question text or rows into its output. Output contains counts, identifiers, element names and fixed reason/status codes. Input/output paths are not included. Errors use a fixed code without parser exception text.

## Invocation and schema

```sh
python tools/compaction_metrics.py --model model.orm.yaml \
  --verification model.verification.json --digest workload.digest.yaml --out compaction.json
```

`--model` is required; other inputs are optional; `--out` defaults to `compaction.json`. Exit 0 means the report was written, 2 means invalid/unreadable input or unwritable output. Relative saved PyRel paths resolve beside the verification report; absolute paths are accepted. The tool refuses an output path that aliases an input or a listed rewrite. It measures representation-format YAML, not arbitrary PyRel models; use the modeling skill's full validator before acceptance.

| JSON field | Meaning |
|---|---|
| `concepts`, `concept_names` | Entity-kind object types only, including subtypes and objectifications; value types are not counted as concepts |
| `source_tables` | Distinct explicit source scope tables, declared entity bindings and digest tables; wildcard `*` is not a table |
| `concepts_per_source_table` | Count and ids of entities bound to each table; multibound entities count once on each table; named tables without bindings count zero |
| `properties_per_concept` | Incident fact type count and ids, including relationships and unary fact types; a repeated entity role counts the fact once |
| `property_distribution` | Histogram: number of concepts with each incident-fact count; identifier shorthand is not an additional fact |
| `unary_flags_per_concept` | Unary fact count and ids; binary Boolean-valued facts are excluded here but included in flag-explosion detection |
| `unbound_concepts` | Entities with neither `provenance.table` nor `provenance.tables`; lack of a binding is not proof of derivation |
| `derived_only_concepts` | Unbound entities explicitly marked `derivation: derived`; semiderived and unknown derivation are excluded |
| `concept_support` | Per-entity distinct item count and item ids whose saved PyRel uses the entity's `name` or `id`; `null` when no PyRel can be scanned |
| `support_coverage` | `complete`, `partial` or `unavailable`, scanned/expected counts, missing and syntax-invalid item ids; expected count is the largest of report item count, report workload count and digest workload count |
| `single_item_concepts` | Exactly one scanned item mentions the concept; `null` without scanned files; with partial coverage this is an observed lower bound |
| `duplicate_structure_concepts` | Groups with identical nonempty property signatures; no claim of equivalent identity or population |
| `flag_explosions` | Entities with at least four unary or binary Boolean fact types, with count and fact ids; enum eligibility needs a semantic test |
| `table_mirrors` | Pairs of separately singly bound entities, each the only entity on its table, joined by a binary with confirmed singleton uniqueness on both roles (a 1:1 identifying candidate) |
| `suspects` | One entry per concept/reason/evidence group: concept id, name, reason code, priority and related ids; sorted by descending priority, concept id, reason, related ids |

`provenance.table` is one binding name; `provenance.tables` optionally records a list for merged entities. The tool does not infer a binding from a neighbor or assume a subtype inherits one. A table-mirror candidate's 1:1 link does not prove equal key values or equal populations: check preferred identifiers, mandatory roles and binding evidence before merging. Composite uniqueness over both roles means m:n and does not count as a mirror. Top-level external uniqueness is not guessed into a 1:1 binary.

## Signatures and support limits

A property's structural signature includes arity, owner-role position, other roles' names, value primitives or entity target ids, normalized uniqueness/mandatory role positions, and derivation status. Source tables, owner names, readings and derivation formulas are ignored. Unary predicates retain their fact ids, avoiding an assertion that unrelated flags mean the same thing. Exact duplicate signatures are a review hint; semantic synonyms, inverse readings, inherited properties and historical families may require manual review. Empty structures are not duplicate candidates.

Support uses Python AST name loads and attribute loads, plus used `from ... import Concept as Alias` aliases. Repeated mentions count once per item. Comments, string literals and unused imports do not count. The tool never executes imports. Dynamic string lookups, wildcard imports, indirect helper calls and transitive dependencies can be missed; unrelated Python variables with matching names can be counted. Check the actual saved query and generated model before deciding its uses. Syntax-invalid files are reported without their text.

Complete coverage means every reported/expected item has a readable, parseable saved PyRel file, not that static name matching proves all dependencies. Missing accepted rewrites and failed items commonly make coverage partial. Single-item reason codes are emitted only for complete coverage; no scan emits `null`, not misleading zero support. Zero observed support never makes a concept a suspect by itself. A digest supplements table counts and expected item count; it cannot supply saved query usage or full item text.

## Default ranking and thresholds

| Reason code | Default priority | Review test |
|---|---|---|
| `flag-explosion` | 100 | Four or more Boolean facts: can one categorical value type preserve the meanings? |
| `duplicate-structure` | 80 | Same signature: are identity, grain, roles and time semantics also the same? |
| `table-mirror` | 70 | Separate table concepts with a confirmed 1:1 link: does identity survive combining them? |
| `single-item` | 50 | One item under a complete scan: can the concept be expressed through a path over business entities? |

These are starting thresholds and ordering, not ontology rules or automatic deletion criteria. Independent Boolean facts may all be necessary; legitimate entities may have one query each; identical property shapes may represent distinct things. The CLI uses fixed defaults for reproducibility. Record any different review threshold in `ontology-notes.md` rather than implying the tool used it.

Reports are deterministic under model/list reordering and unchanged inputs. No timestamps, hash of data, values, literal lists or question excerpts are generated. Compare distribution and suspect counts before/after, and compare support only with equivalent scan coverage. Domain fidelity and verified pass counts remain the acceptance criteria.
