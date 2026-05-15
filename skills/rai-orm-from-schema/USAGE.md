# Usage Guide — rai-orm-from-schema

What the skill can do, what options are available, and how to invoke it. For the full procedural definition Claude reads, see [`SKILL.md`](SKILL.md). For testing the skill, see [`evals/README.md`](evals/README.md).

---

## What the skill does

Recovers an **ORM 2 conceptual model** (YAML with full constraint provenance) from a relational schema (live database, DDL file, or CSV samples), produces a stakeholder-reviewable **verbalization** (Halpin-style controlled natural language), and translates the confirmed model to **PyRel** for use with the RelationalAI platform.

The pipeline is the **Schema Recovery Procedure (SRP)**: 10 steps from raw schema introspection to PyRel emission.

---

## Inputs

| Input kind | What you provide | Confidence | Constraints emitted |
|---|---|---|---|
| `sql` (live database) | Connection string + target schema | `standard` | All explicit (DDL) + all sample-derived (live probing) |
| `ddl-file` | Path to one or more `.sql` files with `CREATE TABLE` / `ALTER TABLE` / `CREATE INDEX` statements | `standard` | All explicit; no sample probing |
| `csv` | Directory of CSV files (one per table) with headers | `low` | Type inference + sample-derived only; no PKs/FKs/CHECKs |

**Dialects supported** (for `sql` and `ddl-file`):

| Dialect | Status | Notes |
|---|---|---|
| Postgres | ✅ Full | Reference dialect |
| Snowflake | ✅ Full | Uses `SHOW`-based catalog views; CHECKs limited |
| MySQL | ✅ Full | CHECK constraints require MySQL 8.0.16+ |
| Oracle | ✅ Full | Uses `ALL_*` views; needs DBA or owner privileges |
| SQLite | ✅ Full | CHECK introspection limited (parses `sqlite_master.sql`) |
| Other | ⚠️ Best-effort | Falls back to ANSI INFORMATION_SCHEMA; degrades to `confidence: low` if introspection paths are missing |

---

## Outputs

The skill always emits the same triple:

| File | Contents | Audience |
|---|---|---|
| `model.orm.yaml` | The recovered ORM 2 model — every constraint carries `source` + `status` + `modality` + `provenance`. Single source of truth. | Reviewers (technical and non-technical) |
| `model.verbalization.txt` | Halpin-style CNL rendering of the entire model — readable without PyRel knowledge. The primary review surface for non-PyRel stakeholders. | Domain experts, business reviewers |
| `model.py` | PyRel translation of the confirmed YAML. Includes `# DEONTIC NOTE:` and `# REVIEW MODALITY` markers for non-mechanical entries. | Engineers building on the recovered model |

By default, outputs land alongside the input or in a directory you specify. The eval-run convention is `evals/results/<YYYY-MM-DD>/<schema>/`.

---

## Interaction modes

You pick the mode at SRP **Step 0** (the very start of the conversation). The choice is recorded in `model.orm.yaml`'s `source.mode` field.

### Guided mode (default)

Claude pauses for your input at three pivot points:

| Pivot | What you do | When |
|---|---|---|
| **Step 0** | Confirm `guided` (vs One-shot) | Always, opens the run |
| **Step 6d** *(opt-in)* | Mark obvious LLM hallucinations as `rejected` before they pollute Step 8's verbalization | Only if Step 6c proposed any LLM-tier constraints; you can decline the spot-check entirely |
| **Step 9** | Six substeps: review the verbalization, confirm/reject Step 6 proposals, resolve antipattern flags, add user-supplied, label modality, commit | Always, the main user-decision moment |

Steps 1–8 and 10 are non-interactive — Claude runs them autonomously and presents output at the pivot points.

**Best for:** high-value or unfamiliar schemas, schemas with many ambiguous antipatterns, when you want the LLM-tier filter, when modality labelling matters.

### One-shot mode

The SRP runs end-to-end without pause. Claude emits the full triple in one go. You review by editing the YAML directly.

| Step 6 substep | One-shot behaviour |
|---|---|
| 6a (library) | Auto-confirm |
| 6b (ring patterns) | Auto-confirm |
| 6c (LLM tier) | Stay `proposed` |
| 6d (spot-check) | Skipped entirely |
| 6e (verbalize) | Same as Guided |

| Step 9 substep | One-shot behaviour |
|---|---|
| 9a (review verbalization) | Skipped (verbalization still emitted to the file) |
| 9b (confirm proposals) | Library-tier auto-confirm; LLM-tier and `proposed` sample stay `proposed` |
| 9c (antipattern resolution) | Catalog default applied silently; flags remain in YAML |
| 9d (user-supplied) | Skipped |
| 9e (modality labelling) | Explicit-source → `alethic`; everything else inherits `alethic` + `# REVIEW MODALITY` flag |
| 9f (commit) | Standard write |

**Best for:** fast retargeting, batch runs across many schemas, when you'll review by editing the YAML rather than answering prompts.

---

## What you can control at each step

### Step 1 — Inventory (no user input)

What's introspected:
- Tables, columns (name, type, nullability, default, comment)
- PKs, FKs, UNIQUE indexes, NOT NULLs, CHECKs, indexes
- Cross-schema FK warnings

You can constrain scope by specifying `tables: ["table_a", "table_b"]` in your invocation prompt, or by passing a subset of `.sql` files for `ddl-file` mode.

### Step 5 — Sample probes (live SQL only)

Configurable knobs (see [`references/probing-strategies.md`](references/probing-strategies.md)):

| Knob | Default | What it controls |
|---|---|---|
| Sample size cap | 10,000 rows | Trades probe accuracy for runtime |
| Confirmed-promotion minimum | 1,000 rows | Below this, status stays `proposed` |
| Per-probe timeout | 60 s | Aborted probes degrade to `proposed`, never block |
| Total probe budget | 5 min wall-clock, 100 probes | When exhausted, remaining probes skipped |
| Enum-detection threshold | < 20 distinct values | Above this, treat column as free-text |
| NULL-rate threshold | < 0.1% | Reinforces explicit NOT NULL via sample |

You can override any of these in your invocation prompt: *"...with sample size cap 50,000 and probe budget 10 minutes."*

### Step 6c — LLM tier (Guided mode 6d spot-check)

When LLM tier proposes constraints (value ranges/enums, ring constraints, subset/exclusion, mandatory, frequency), you can:
- Accept all (default)
- Reject specific ones immediately at 6d (Guided opt-in)
- Defer all to Step 9b

LLM proposals always carry `provenance.rationale_world_fact` (mandatory; rejected at emission without it).

### Step 9 — Decisions (Guided mode)

Six substeps where you have agency:

| Substep | What you do |
|---|---|
| 9a | Read the whole-model verbalization |
| 9b | Confirm / reject / escalate each proposed constraint from Step 6 (auto-batched when ≥ 5 in a category) |
| 9c | Resolve antipattern-flag ambiguities raised at Step 7 (default resolution surfaced; you can override) |
| 9d | Add constraints the system missed — free-form natural language input; Claude paraphrases back as structured form for confirmation |
| 9e | Label every confirmed non-explicit constraint as `alethic` (must) or `deontic` (should) |
| 9f | Commit (auto) |

Default modality: `alethic` for `source: explicit`; user labels everything else. If you skip 9e, defaults apply with `# REVIEW MODALITY` flags.

### Step 10 — PyRel translation (no user input)

Translation rules are deterministic given the finalized YAML. See [`references/orm-to-pyrel.md`](references/orm-to-pyrel.md) for the four-tier mapping.

---

## Constraint sources

Every constraint emitted carries `source: <one of five>`:

| Source | What it means | Default status |
|---|---|---|
| `explicit` | Lifted directly from DDL: PK / UNIQUE / NOT NULL / CHECK / FK | `confirmed` (auto) |
| `sample` | From live data probing (cardinality, value enum, range, NULL rate) | `confirmed` if live SQL + saturated + sample ≥ 1000; `proposed` otherwise |
| `common-sense` | From the typed library (object-type name match) or ring-pattern matcher | `proposed` |
| `llm-inferred` | LLM proposal from world knowledge for novel object types/relationships | `proposed` |
| `user-supplied` | Added by you at Step 9d | `confirmed` (auto) |

The library used for `common-sense` lives in [`references/constraint-inference.md`](references/constraint-inference.md). It's a markdown table — additions are diff-reviewable.

---

## Antipattern handling

The skill detects 17 antipattern codes; each has a default resolution. You override at Step 9c (Guided) or by editing the YAML's `provenance.resolution.action` (One-shot).

| Code | What it detects | Default resolution |
|---|---|---|
| `denormalized-address` | Multiple address-component columns on one table | Flag for documentation; don't auto-restructure |
| `encoded-enum-in-varchar` | Low-cardinality VARCHAR with enum-style suffix | Promote to `model.Enum` value type |
| `type-column-subtype` | TYPE/CATEGORY/KIND column + correlated side tables | Emit subtypes with `extends=[Parent]` + partition constraint |
| `ambiguous-junction-no-extras` | Composite all-FK PK, no other columns | Pure m:n binary fact type |
| `ambiguous-junction-with-extras` | Composite all-FK PK + non-FK columns | Objectified entity |
| `missing-unique` | Column unique in sample, no DDL UNIQUE | Flag candidate; user confirms |
| `missing-fk` | Column name suggests FK, no FK declared | Flag candidate; user confirms |
| `boolean-encoded-varchar` | Column with `{0,1}` / `{Y,N}` / `{T,F}` values | Promote to `Boolean` value type |
| `independent-object-type` | Table with no inbound FKs, not a junction | Propose `independent: true` |
| `no-pk-detected` | Table without a primary key | Flag for user; emit entity with external reference |
| `cross-schema-fk` | FK pointing into another schema | Inform; scope may be too narrow |
| `history-table` | Table name suffix `_HIST` / `_LOG` / `_AUDIT` | Flag for user (often skipped) |
| `lookup-table-candidate` | Code+name table referenced by FK only | Propose value-type promotion |
| `composite-fk` | Multi-column FK to composite PK | Inform; constraint emitted differently |
| `polymorphic-fk-candidate` | Same FK column references different tables | Out of v0.1 scope; flag and skip |
| `unparseable-check` | CHECK clause that can't be parsed | Emit as `textual` constraint |
| `generated-column` | Column with generation expression | Note in provenance; treat as regular for v0.1 |

Full per-antipattern detail in [`references/antipattern-catalog.md`](references/antipattern-catalog.md).

---

## What the skill can do (concrete capabilities)

✅ **Recover 13 distinct ORM 2 constructs from an existing schema** — entity types, value types, fact types (unary through n-ary), all 13 constraint types (uniqueness internal/external, mandatory, mandatory-disjunctive, value enum/range, subset/equality/exclusion/exclusive-or, frequency internal/external, ring with 11 variants, value-comparison, cardinality object/role, subtype-partition, textual).

✅ **Five-source constraint provenance** — every emitted constraint traces back to its origin (explicit DDL, sample data, library, LLM, user) with structured provenance.

✅ **Alethic vs deontic modality** — `alethic` constraints translate to `model.require(...)`; `deontic` constraints emit as `# DEONTIC NOTE:` comments in PyRel.

✅ **Antipattern detection across 17 codes** — flag-then-resolve, never silently restructure.

✅ **Stakeholder-reviewable artifact** — the verbalization is sufficient to validate the model without PyRel or schema knowledge.

✅ **Halpin-grounded vocabulary** — reference modes, fact-type readings, constraint notations, subtyping, modality all follow ORM 2.

✅ **Round-trippable YAML** — the YAML format preserves enough structure that the recovered model can be regenerated from a future SRP run on the same input (modulo sample data drift).

✅ **Reproducible across runs** — pinned commit hashes for external fixtures (Northwind, TPC-H); markdown-driven library that's diff-reviewable.

---

## What the skill does NOT do (v0.1 scope)

❌ **Diagram rendering** — no SVG/ASCII output. The verbalization is text-only.

❌ **Multi-language readings** — English only.

❌ **FORML 2 parsing** — textual constraints stored verbatim; no formal-language interpretation.

❌ **Composite value types** (`Address` as a record) — primitive value types only.

❌ **Generated-column derivation rules** — column noted but derivation expression not modelled.

❌ **Polymorphic FKs** — flagged but not modelled.

❌ **Cross-database FKs** — flagged; no multi-database recovery.

❌ **Domain-specific library** (`domain_library.yaml` for org-policy rules) — universal library only in v0.1; per-deployment domain library is v1.5.

❌ **Pytest test suite or Python package** — markdown-driven only.

❌ **MCP server** — invoked via Claude Code or other Claude Agent SDK environments only.

---

## Invocation patterns

The skill is invoked by asking Claude in a session that has access to this skill. Below are concrete prompt templates.

### Quick test (smallest possible input)

```
Run the rai-orm-from-schema SRP against
skills/rai-orm-from-schema/examples/movie_catalog.sql.
Use One-shot mode. Emit outputs to /tmp/movie-test/.
```

### Full Guided run on a fixture

```
Run the rai-orm-from-schema Schema Recovery Procedure against
skills/rai-orm-from-schema/evals/fixtures/synthetic/schema.sql.
Use Guided mode. I want to spot-check LLM proposals at Step 6d.
Emit outputs to evals/results/2026-05-06/synthetic-guided/.
```

### Live-SQL on Postgres

```
Run rai-orm-from-schema against the Postgres database 'synthetic' on
localhost:5432. Use Guided mode. Apply the default sample-probe budget
(5 min, 100 probes). Output to evals/results/2026-05-06/synthetic-live/.
```

### Custom probe budget

```
Run rai-orm-from-schema against the Snowflake schema PROD_DW.PUBLIC.
One-shot mode. Sample size cap 100,000; probe budget 15 minutes.
Skip sample probing on tables matching /^audit_/.
```

### CSV input (degraded path)

```
Run rai-orm-from-schema against the CSV files in /tmp/synthetic-csv/.
One file per table, headers in row 1. confidence: low expected.
Output to /tmp/synthetic-csv-recovery/.
```

### Re-run with a previously rejected-proposals file

```
Run rai-orm-from-schema against the same schema, but read
evals/results/2026-05-04/synthetic-guided/output.orm.yaml
first to pick up the previously-rejected proposals so they aren't
re-proposed.
```

### Generate verbalization only (no PyRel)

```
Run rai-orm-from-schema steps 1-8 only against
evals/fixtures/synthetic/schema.sql, then stop and emit just
the verbalization. Skip steps 9-10.
```

(Steps 9–10 require user decisions and PyRel translation respectively. Stopping at 8 gives you the recovered model + the verbalization for stakeholder review without committing to PyRel.)

---

## Workflow integration

This skill is a **leaf** of the rai-agent-skills workflow chain — it produces a PyRel model that downstream skills consume:

| Upstream of this skill | What it expects from upstream |
|---|---|
| (None — schema is the input) | A schema in one of the three input forms |

| Downstream of this skill | What downstream consumes |
|---|---|
| `rai-pyrel-coding` | The emitted `model.py` for further development |
| `rai-querying` / `rai-graph-analysis` / `rai-prescriptive-*` | Build queries / graphs / optimizations on the recovered model |
| `rai-ontology-design` | Enrich or evolve the recovered model |

For the full skill workflow chain, see the repo-level [`CLAUDE.md`](../../CLAUDE.md).

---

## Related artifacts

| File | Purpose |
|---|---|
| [`SKILL.md`](SKILL.md) | The procedural definition Claude reads when invoked |
| [`evals/README.md`](evals/README.md) | How to test the skill against the three benchmark fixtures |
| [`evals/cases.json`](evals/cases.json) | Eval case definitions (E1–E4) |
| [`PLAN.md`](PLAN.md) | Build plan, design decisions, scope |
| [`references/`](references/) | 8 deep-dive markdown files; loaded on demand by Claude |
| [`examples/`](examples/) | 4 illustrative example triples (DDL + YAML [+ PyRel]) |
