# Workload evidence in the SRP

Load this file only when a `workload.digest.yaml` (from `rai-orm-from-workload`) was given. Without a digest the SRP runs exactly as before.

The digest is **evidence**. It never decides anything: every use below ends in a proposal that follows the SRP's own confirmation path. Three rules hold everywhere:

1. **Add or promote, never prune.** Usage counts order the review; they never remove a table, a column, a fact type or a constraint.
2. **Everything starts `proposed`.** A data probe that agrees is recorded in provenance; only the user confirms.
3. **No literals, no question text.** The YAML carries counts and digest ids (`provenance` shape: `representation-format.md`, `source: workload`).

Record the digest once at the top of the YAML: `source.artifacts: ["workload.digest.yaml"]` and `source.workload: { kind, n_items }`.

## Step 1 — Inventory

After the inventory, resolve the digest against it:
- Fill `declared_fk` on each join edge: `true` when a declared FK covers the same column pairs.
- Names in the digest's `unresolved` list are reported to the user (a workload that queries tables outside the scope is worth one question: *"the queries also use N tables that are not in scope — include them?"*).

## Step 2 — Object types: grain check

For each table with `grain_keys` in the digest, compare the entity's reference scheme with the most supported grain key.

| Finding | Action |
|---|---|
| Grain key = the PK (or the reference scheme) | Nothing. The workload agrees. |
| Grain key is coarser than the PK, support ≥ 2 | The workload aggregates this table to something that is not an object type yet. If the key columns are FKs to existing entities, nothing; if they are plain columns, note a candidate entity type for the grouping (flag `lookup-table-candidate` style; user decides at 9c). |
| No PK, and a grain key exists | Use the grain key as the *candidate* reference scheme, then run the uniqueness probe on it. Unique in the data → entity with `reference.mode: external`, uniqueness `source: workload, status: proposed`, probe recorded. Not unique → keep `no-pk-detected`. |
| Two or more tables resolve to one object type (same key, merged at Step 2 or by the user), and the workload queries them separately | Raise `provenance.warning: grain-mismatch` on the object type. Default resolution at 9c: keep the tables' own grains reachable, either as separate entity types related to the shared one, or with one unary fact type per source table (*"Customer appears in CRM_CUSTOMER"*). |

`grain-mismatch` exists only with a digest. It is the workload-side counterpart of `ambiguous-junction`: the schema allows two readings and the workload shows which one is used.

## Step 3 — Fact types: readings, role names, derived fact types

**Readings and role names (`terms`, pairs only).** Where a term is aligned to a column or a join edge with support ≥ 2 and no conflicting alignment, prefer it over the column-name heuristic for the reading or the role name. Keep the column-derived name in `provenance.column` as before. A term with conflicting alignments is not used for naming; list it at Step 9c.

Without alignment (`questions` modality), terms are not attached to anything. They are shown at Step 9d as vocabulary the user may want to map.

**Derived fact types (`expressions`).** An expression template with support ≥ 2 becomes a fact type with `derivation: derived`, `derivation_rule: <template with ? placeholders resolved to role references>`, `storage: computed`, `provenance.origin: workload`. If a term is aligned to the expression, its reading uses the term (*"{Subject} has pass rate {Ratio}"*). Templates whose placeholders stand for different literals in different items are parameterized measures, not fact types: skip them and list them at 9d.

## Step 5 — Probes requested by the digest

| Digest entry | Probe requested | Recorded as |
|---|---|---|
| `join_edges` with `declared_fk: false` | Subset/inclusion probe, both directions (the share of distinct left values found on the right, and the reverse) | `provenance.probe { kind: inclusion, rate, sample_size }` |
| `filter_columns` with `operators.eq + operators.in ≥ 2` | Distinct-value enumeration | the usual `source: sample` value-constraint proposal; the digest only caused the probe |
| `grain_keys` on a table without PK | FD/uniqueness probe on the key | `provenance.probe { kind: uniqueness, … }` |

These probes count toward the Step 5 budget. When the budget is short, probe in order of `support`.

**Inclusion threshold.** A join edge *passes* when the rate is at least 0.90 in one direction. Between 0.50 and 0.90 it is *weak*: not emitted, listed at Step 9c with its rate. Below 0.50 it is dropped from proposals and kept only in the Step 9c list. With DDL-only or CSV input no probe can run; every edge is then *unprobed* and treated as weak.

Tables that are capped samples of a larger table make inclusion rates between two such tables meaninglessly low. When both sides have exactly the same round row count, say so at 9c instead of dropping the edge.

## Step 7 — `missing-fk` with workload evidence

For each undeclared join edge that **passed**:

- Emit the fact type the join stands for, as Step 3 would for a declared FK: the referencing side is the side whose column set is not the other table's key. Reading from the aligned term when there is one, else from the column name.
- `provenance.origin: workload`, `provenance.workload { workload_kind, evidence: join-edge, digest_ref, support, n_items, probe }`, `provenance.warning: missing-fk`.
- **No** mandatory constraint (an undeclared FK may be unbound), unless the null-rate probe proposes one as `source: sample`.
- Guided: all such fact types are shown as one batch at 9c, with support and inclusion rate, for accept or reject. One-shot: they stay in the YAML, and `model.py` marks them `# REVIEW PROPOSAL`.

**Only key-to-reference edges are relationships.** One side of the edge must be the other table's key (its PK, a declared UNIQUE, or a column set the uniqueness probe found unique). An edge where neither side is a key (two tables joined on a shared code column) is not a fact type between the two entities: both columns reference the same third thing. Do not emit it. If a table keyed by that column exists, the edges from each side to that table carry the meaning; if none exists, note a `lookup-table-candidate` at 9c.

Edges that are weak, unprobed or failed are listed at 9c and not emitted. The name-convention detection of `missing-fk` is unchanged: a `*_id` match with no workload evidence is still flag-only.

## Step 8 and Step 9 — review order

With a digest, the verbalization lists object types in order of table `support` (most used first), so the user reviews what the workload depends on before the long tail. Nothing is hidden.

At Step 9c the workload items form their own group: accepted joins, weak or failed edges, `grain-mismatch` notes, derived fact types, conflicting terms.

## After Step 10

The model is ready for `rai-orm-verify`, which rewrites the workload in PyRel against `model.py`. Its repairs come back as proposals with `evidence: verification` and are committed through Step 9f.
