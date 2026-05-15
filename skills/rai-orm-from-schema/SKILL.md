---
name: rai-orm-from-schema
description: Recovers an ORM 2 conceptual model (YAML with full constraint provenance — explicit / sample / common-sense / llm-inferred / user-supplied, alethic vs deontic, antipattern flags) from a relational schema (live DB, DDL file, CSV samples), then translates to PyRel. Produces a stakeholder-reviewable intermediate artifact. Use for schema-driven model recovery — not for greenfield builds that go direct to PyRel without an ORM stage (rai-build-starter-ontology), enriching/reviewing an already-loaded PyRel model (rai-ontology-design), or text-only inputs without schema (see the text-first companion rai-orm-from-text, which uses Halpin's CSDP for forward design).
---

# Schema-to-ORM Recovery
<!-- v1-SENSITIVE -->

## Summary

**What:** Schema Recovery Procedure (SRP) — a 10-step workflow that reads a relational schema (live DB, DDL file, or CSV samples), recovers an ORM 2 conceptual model with full constraint provenance, verbalizes it for stakeholder review, and translates the confirmed model to PyRel. Output is `model.orm.yaml` + `model.verbalization.txt` + `model.py`.

**When to use:**
- Schema-driven model recovery — recovering a Halpin-style ORM 2 model from an existing database
- Producing a stakeholder-reviewable intermediate artifact (the YAML) when non-PyRel reviewers must validate the model
- Recovering implicit constraints (acyclic hierarchies, value enumerations, mandatory roles, ring constraints) with explicit provenance and user-confirmation flow
- Detecting and flagging schema antipatterns (denormalized address columns, encoded enums in VARCHAR, ambiguous junction tables, TYPE-column subtype splits) before they become PyRel
- Comparing two PyRel-target architectures (direct schema→PyRel vs schema→ORM→PyRel) on identical workloads

**When NOT to use:**
- Greenfield builds that go direct to PyRel without an ORM stage — see `rai-build-starter-ontology`
- Enriching, reviewing, or evolving a PyRel model that already loads and queries — see `rai-ontology-design`
- PyRel syntax reference (Concept, Property, Relationship, model.require, f-string patterns) — see `rai-pyrel-coding`
- Text-only inputs (requirements documents, domain descriptions, no schema or data) — see `rai-orm-from-text` (the text-first companion skill, which uses Halpin's CSDP for forward design)
- Querying, graph analysis, optimization formulation — see the respective reasoner skills (`rai-querying`, `rai-graph-analysis`, `rai-prescriptive-*`)

**Overview:**
1. Open with mode choice — Guided (interactive confirmation) or One-shot (full YAML for post-hoc review)
2. Inventory the schema (DDL / INFORMATION_SCHEMA / CSV introspection per dialect)
3. Recover object types and fact types from tables, columns, PKs, FKs
4. Lift explicit constraints (PK / UNIQUE / NOT NULL / CHECK / FK) and probe live data for sample-driven constraints
5. Apply constraint inference — typed library for common patterns, LLM tier for novel cases — all proposed, never asserted
6. Detect schema antipatterns and flag for user resolution
7. Verbalize the recovered model end-to-end (Halpin-style controlled natural language)
8. Capture user decisions — confirm / reject / add / label alethic vs deontic
9. Translate the finalized YAML to PyRel via four-tier rules (mechanical / heuristic / model.require / not-translated)

## Quick Reference

| Artifact | Contents | Audience |
|---|---|---|
| `model.orm.yaml` | The recovered ORM 2 model with every constraint carrying `source` + `status` + `modality` + `provenance`. Single source of truth. | Reviewers (technical and non-technical) |
| `model.verbalization.txt` | Halpin-style controlled natural language (CNL) rendering of the entire model — readable without PyRel knowledge. | Stakeholders |
| `model.py` | PyRel translation of the confirmed YAML. Includes `# DEONTIC NOTE:` and `# REVIEW MODALITY` markers for non-mechanical entries. | Engineers |

**Five-source provenance taxonomy** — every constraint carries one:

| `source` | Meaning | Default `status` |
|---|---|---|
| `explicit` | Lifted directly from DDL (PK, UNIQUE, NOT NULL, CHECK, FK) | `confirmed` |
| `sample` | Probed from live data (cardinality, value enumeration, range) | live SQL: `confirmed`; DDL/CSV: `proposed` |
| `common-sense` | Typed-library lookup or structural ring-pattern match | `proposed` |
| `llm-inferred` | LLM proposal for novel object types/relationships | `proposed` |
| `user-supplied` | Added by user during Step 9 review | `confirmed` |

**Core principle: propose, never assert.** Constraints not lifted from DDL are *candidates* validated with the user.

## Inputs and Outputs

**Inputs (one of):**
- Live database connection (Snowflake / Postgres / MySQL / Oracle / SQLite — dialect-aware introspection via INFORMATION_SCHEMA or equivalent).
- DDL file (`.sql` with `CREATE TABLE` / `ALTER TABLE` / `CREATE INDEX` statements).
- CSV samples (typed inference; `confidence: low`; PKs/FKs/CHECKs absent).

**Outputs (always emitted as the triple):**
- `model.orm.yaml` — full canonical YAML; format spec in [`references/representation-format.md`](references/representation-format.md).
- `model.verbalization.txt` — CNL rendering; patterns in [`references/verbalization-patterns.md`](references/verbalization-patterns.md).
- `model.py` — PyRel translation; rules in [`references/orm-to-pyrel.md`](references/orm-to-pyrel.md).

## Instructions

**Required dependencies:** [`rai-pyrel-coding`](../rai-pyrel-coding/SKILL.md) for PyRel idioms used in Step 10. No dependency on `rai-ontology-design` or `rai-build-starter-ontology` — this skill is self-contained for schema recovery (per the build discipline locked in PLAN.md).

**Working principle:** propose, never assert. Every constraint that isn't lifted directly from DDL gets an explicit confidence path through Steps 6–9 before reaching the YAML as `confirmed`.

### Step 0 — Interaction-mode opener

Before introspecting anything, ask the user:

> *I can run this in two modes:*
> - *Guided — I confirm proposals with you step by step. Best for high-value or unfamiliar schemas.*
> - *One-shot — I emit the full YAML in one pass; you review by editing the file. Best for fast retargeting.*
> *Which would you prefer?*

Default to Guided if no answer. Record the choice in `source.mode` of the YAML.

In **Guided** mode, the SRP pauses for user input at three pivot points (after Step 0 itself, after Step 7, and across Step 9's six substeps). In **One-shot** mode, those pauses collapse — library-tier proposals auto-confirm; LLM-tier proposals stay `proposed` for the user to review by editing the YAML.

### Step 1 — Inventory

Discover tables, columns, types, PKs, FKs, UNIQUE indexes, NOT NULLs, CHECK constraints, indexes, comments. Mechanics by input kind:

- **`sql` (live database)**: query INFORMATION_SCHEMA per dialect. Snowflake / Postgres / MySQL / Oracle / SQLite covered. Concrete queries in [`references/probing-strategies.md`](references/probing-strategies.md).
- **`ddl-file`**: parse with the dialect-aware parser; structural extraction.
- **`csv`**: infer types from sampled values; mark `source.confidence: low`.

Record introspection metadata in YAML `source.scope`, `source.dialect`, `source.introspected_at`.

### Step 2 — Identify object types

For each table:
- **Single-column PK** → entity type with `reference.mode: popular` (Halpin's term for the `Country(.code)` shorthand). The `value_type` derives from the PK column's primitive type.
- **Composite PK** → entity type with `reference.mode: external`. The corresponding external uniqueness constraint is emitted in Step 4.
- **Junction table (composite PK that's all-FK, no extra columns)** → flagged as **pure m:n binary** candidate; no entity type emitted yet (decision in Step 7).
- **Junction table with extra columns** → flagged as **objectified binary** candidate; entity type emitted with `reference.mode: external`.
- **Table without PK** → entity type with `provenance.warning: "no-pk-detected"`; raised at Step 7.

Value types are extracted lazily — emitted in Step 3 when first referenced.

Halpin reference modes (`popular`, `unit-based`, `general`, `external`) are documented in [`references/representation-format.md`](references/representation-format.md).

### Step 3 — Identify fact types

For each entity type's source table:
- Each FK → binary fact type linking this entity to the referenced entity. Reading derived from FK column name (`placed_by_customer_id` → `"{Order} placed by {Customer}"`); falls back to `"{A} has-a {B}"`.
- Each non-FK, non-PK column → binary fact type linking to a value type. Reading: `"{Entity} has {value-name} {ValueType}"`.
- Self-referential FKs → fact type with both roles on the same object type, **with explicit `role_name`** for each role (default derived from FK column on referencing side, supertype name on referenced side).
- For junction tables flagged as objectified candidates: emit the underlying binary fact type with `objectified_as: <junction_id>`; objectification confirmed in Step 7.

Reading and role-naming heuristics are detailed in [`references/srp-workflow.md`](references/srp-workflow.md) Step 3.

### Step 4 — Lift explicit constraints

Every entry produced by this step carries `source: explicit, status: confirmed`, with `provenance` pointing to the originating DDL element.

| DDL element | Emitted constraint |
|---|---|
| PK (single column) | Internal UC, `preferred: true`, on the PK role |
| PK (composite) | External UC across the corresponding binary fact types, `preferred: true` |
| UNIQUE (single column) | Internal UC, `preferred: false` |
| UNIQUE (composite) | External UC, `preferred: false` |
| NOT NULL | Mandatory on the corresponding role |
| FK | Mandatory on the FK side (FKs cannot be unbound) |
| CHECK `col IN (literal-list)` | Object-type or role value constraint, `allowed: [...]` |
| CHECK `col BETWEEN x AND y` | Value constraint with `range: { min, max, inclusive }` |
| CHECK `colA <op> colB` | Inline value-comparison constraint |
| Other parseable CHECK | `type: textual`, `formal_language: natural`, raw expression |
| Unparseable CHECK | Skip with a `# NOTE:` warning in the output |

Default values are not constraints; recorded in `provenance` for traceability.

### Step 5 — Probe samples

Run cardinality / value-enumeration / range / NULL-rate / distinct-count probes against live data (when access permits). Each probe-derived entry carries `source: sample` with provenance recording the sample query.

Promotion rules:
- **Live SQL input**: `proposed` → `confirmed` if probe confidence exceeds the threshold (cardinality matches expected, no violations in ≥1000-row sample, distinct-value count saturates).
- **DDL-only or CSV input**: stays `proposed` (no live data to confirm).

Probe types and SQL queries are catalogued in [`references/probing-strategies.md`](references/probing-strategies.md). Default sample-size cap and confidence threshold are documented there.

**Discipline:** sample-detected uniqueness (column unique in data but no DDL UNIQUE) is **flagged in Step 7 as a candidate**, not auto-emitted as a UC. The schema author may have allowed duplicates intentionally.

### Step 6 — Apply constraint inference

Five substeps:

> **6a.** Auto-propose constraints from the **typed library** keyed on object-type names and primitives. Examples: `Money`/`Age`/`Count`/`Duration` → non-negative; `Date` → must be valid; `Event { start ≤ end }`. Library lives in [`references/constraint-inference.md`](references/constraint-inference.md).
>
> **6b.** Auto-propose **ring constraints** from structural patterns. Self-referential binary fact types match against library entries (`parent-of` → acyclic + asymmetric + irreflexive; `married-to` → symmetric + irreflexive + functional under monogamy; `precedes` → acyclic + transitive).
>
> **6c.** Ask the LLM tier to propose further constraints from world knowledge for object types/relationships the library doesn't cover. Each proposal must include rationale citing the world fact that justifies it.
>
> **6d.** **LLM spot-check** (Guided mode only; opt-in). Surface just the Step 6c LLM-tier proposals to the user with their rationales — *not* the library or ring proposals (those are deterministic; the user reviews them at Step 9b). The user can mark obvious hallucinations as `rejected` immediately so they don't pollute Step 8's full-model verbalization. The user can also defer all decisions to Step 9b. **Why narrow:** Step 6c is the highest hallucination-risk source; library and ring proposals are reviewed in context at Step 8. **Why no "suggest your own"** at 6d: Step 9d already covers user-supplied constraints, and the user has better recall after Step 8's full verbalization.
>
> **6e.** Verbalize all surviving Step 6 proposals back to the user in a single batch with provenance and rationale.

All surviving Step 6 outputs carry `status: proposed`. Step 9b is the final confirmation path; Step 6d is a narrow early filter for LLM-tier hallucinations only. In One-shot mode, Step 6d is skipped — LLM proposals stay `proposed` for review by editing the YAML directly.

**Risks of the inference layer:**
- Cultural/legal variation — don't silently assume monogamy, the Gregorian calendar, USD currency. Library entries flag their assumptions.
- Hallucination at the LLM tier — provenance + mandatory user review is the only defense.
- Stale common sense — library entries need periodic review.
- Over-constraining narrows models silently — always leave a clean reject path.

### Step 7 — Detect schema antipatterns

Catalog (full version in [`references/antipattern-catalog.md`](references/antipattern-catalog.md)):

| Antipattern | Detection signal | Default resolution |
|---|---|---|
| Denormalized address columns | Multiple columns matching `(line1\|line2\|address\|street\|city\|state\|zip\|postal\|country)` on the same table | Propose extracting an `Address` value type |
| Encoded enum in VARCHAR | Low-cardinality VARCHAR with enum-style suffix (`STATUS`, `TYPE`, `KIND`, etc.) | Propose `value` constraint with sample-derived `allowed: [...]` |
| TYPE-column subtype split | TYPE/CATEGORY/KIND column + side tables FK'd from this table whose existence correlates with TYPE values | Propose subtypes per TYPE value with `extends=[Parent]`; emit subtype-partition constraint |
| Ambiguous junction (no extras) | Composite PK that's all-FK, no other columns | Default = pure m:n; user may override in 9c |
| Ambiguous junction (with extras) | Composite PK that's all-FK + non-FK columns | Default = objectified entity; user may override |
| Missing UNIQUE constraint | Sample shows uniqueness, no DDL UNIQUE | Flag in `provenance.warning`; do NOT auto-propose |
| Missing FK | Column name `*_id` referencing another table's PK by name convention, no FK declared | Flag as candidate; do NOT auto-emit fact type |
| Boolean encoded as VARCHAR/INT | Values restricted to `{0,1}`, `{Y,N}`, or `{true,false}` | Propose value type `Boolean` |
| Independent object type | No inbound FKs and not a junction | Propose `independent: true` |

Antipattern flags attach as `provenance.warning: <code>` on the affected YAML entry. The user sees them surfaced in the verbalization (Step 8).

### Step 8 — Verbalize the recovered model

Render the entire model in Halpin-style CNL. Save to `model.verbalization.txt`. Patterns:

- **Object type**: *"Customer is identified by CustomerId."*
- **Fact type with constraints**: *"Customer has email EmailAddress. Each Customer has at most one EmailAddress."*
- **Subtype**: *"PhysicalProduct is a kind of Product. Each PhysicalProduct has weight Weight."*
- **Constraint with provenance prefix**: *"[from PK] Each Order is placed by exactly one Customer."* / *"[proposed from common-sense] Parenthood is acyclic."*
- **Antipattern flag**: *"⚠ Address columns on Customer (address_line1..country) appear denormalized — consider extracting an Address value type."*

The verbalization is the primary review surface for non-PyRel stakeholders. Reading it should be sufficient to validate or challenge the model without seeing the YAML or the original schema.

Full pattern library in [`references/verbalization-patterns.md`](references/verbalization-patterns.md).

### Step 9 — Capture user decisions and additions

Six substeps:

> **9a.** User reviews the whole-model verbalization (Step 8 output).
> **9b.** User confirms / rejects / escalates each proposed constraint from Step 6.
> **9c.** User resolves antipattern-flag ambiguities from Step 7.
> **9d.** User adds any constraints they know but the system missed (`source: user-supplied`, auto-`status: confirmed`).
> **9e.** User labels every confirmed constraint as `alethic` (must) or `deontic` (should). Default `alethic` for `source: explicit`; user labels `common-sense` / `sample` / `llm-inferred` / `user-supplied`.
> **9f.** Commit confirmed + user-supplied to YAML. Rejected proposals go to `rejected_proposals` so future runs don't re-propose.

**Mode behavior:**
- **Guided**: each substep is interactive; batch within a substep when ≥5 items (e.g., "I have 12 ring-constraint proposals — confirm all / reject all / decide individually").
- **One-shot**: substeps collapse — library-tier auto-confirms; LLM-tier and `proposed`-status sample stay `proposed`; antipatterns get default resolutions; explicit-source labeled `alethic`; everything else inherits `alethic` with `# REVIEW MODALITY` flag.

This is the only step with mandatory user interaction in Guided mode (Step 0's mode opener excepted).

### Step 10 — Translate to PyRel

Apply the four-tier rules from [`references/orm-to-pyrel.md`](references/orm-to-pyrel.md) to the finalized YAML. Output `model.py`:

| Tier | Constructs | PyRel form |
|---|---|---|
| **Mechanical** | Object types; uniqueness-on-role binary fact types; multi-valued binary; NOT NULL; subtypes; value enumerations; decimal types | `Concept(identify_by=...)`, `Property` (FD-enforced), `Relationship`, `model.Enum`, `Number.size(p,s)`, `extends=[Parent]` + `define...where` |
| **Heuristic** | Objectified binary; subtype recovery from TYPE columns; same-type fact types; unaries | Junction concept with `identify_by={"a": A, "b": B}`; named refs `{Stock:stock1}`; unary `Relationship` |
| **`model.require()` (verbose)** | Ring constraints; counted frequency; external uniqueness over joins; subset / exclusion / equality | `model.require(...)` with explanatory comments |
| **Truly not translated** | Deontic constraints | `# DEONTIC NOTE:` comments |

Output structure: header comment with strict-mode reminder, imports from `relationalai.semantics`, Concept declarations, Property/Relationship declarations, subtype rules, `model.require()` calls, deontic and review-flag comments.

## Constraint Provenance and Validation Flow

Every constraint in the model carries:

```yaml
- type: <constraint-type>
  # constraint-specific fields …
  source: explicit | sample | common-sense | llm-inferred | user-supplied   # set once
  status: proposed | confirmed | rejected                                    # evolves through review
  modality: alethic | deontic                                                # set at Step 9e; default alethic
  rationale: "Free-text explanation."                                        # required for non-explicit sources
  provenance: { … }                                                          # source-specific structured pointer
```

**Rules:**
- `source` is set once at creation. Never changes.
- `status` evolves through review. `proposed → confirmed` (via Step 9b or auto-promote) or `proposed → rejected` (Step 9b explicit reject; archived in `rejected_proposals`).
- `modality` defaults to `alethic`; deontic must be explicit. Deontic constraints emit as `# DEONTIC NOTE:` comments in PyRel.
- `rationale` required for `source ∈ {sample, common-sense, llm-inferred}` so the user knows *why* this was proposed.
- `rejected_proposals` (top-level YAML field) keeps rejected items so future runs don't re-propose.

Domain-specific (organization-policy) constraints are a separate v1.5 extension via per-deployment `domain_library.yaml`. Tracked in `notes/TODO.md` item #6.

## Antipattern Detection

Antipatterns are detected in Step 7 and flagged on the affected YAML entries via `provenance.warning: <code>`. Resolution defaults are documented in the Step 7 catalog above; full catalog with detection SQL, resolution mechanics, and false-positive guidance lives in [`references/antipattern-catalog.md`](references/antipattern-catalog.md).

**Discipline:**
- Antipatterns are **flagged, never silently corrected.** The user resolves at Step 9c.
- Detection is **conservative** — false negatives (missing a real antipattern) are preferred over false positives (calling clean schema "antipattern"). TPC-H runs should produce zero antipattern flags.
- Sample-driven uniqueness candidates and missing-FK candidates do **not** auto-emit constraints. They flag for user confirmation only.

## ORM → PyRel Translation

Four tiers (table above; full rules in [`references/orm-to-pyrel.md`](references/orm-to-pyrel.md)).

**Halpin-copyright discipline (S12):** translation rules are paraphrased from Halpin's published work, not reproduced. Examples are ours. PyRel idioms come from `rai-pyrel-coding`.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Asserting an inferred constraint in the YAML as `confirmed` without user review | Skipping Step 9b in Guided mode, or assuming One-shot's auto-confirm covers LLM-tier | LLM-tier and `sample`-on-CSV stay `proposed` always until user review. Library-tier auto-confirms only in One-shot mode. |
| Inventing fact types from name conventions (`*_id`) without an actual FK | Treating "missing FK" antipattern as auto-resolution | Step 7 flags missing-FK candidates. Do NOT emit a fact type until the user confirms in Step 9c. |
| Using Python's `and`/`or`/`not` in PyRel `model.require()` | Forgetting PyRel's boolean operator rules | Use `&` / `\|` / `model.not_()`. Triggers compile-time `[Invalid operator] Cannot use python's 'bool check'`. |
| Reference mode = `derived` for a single-column PK | Mistaking Halpin's `popular` mode for "derived" terminology | Halpin's term is `popular`. `derived` refers to derivation status, not reference mode. |
| Combining ring variants in one entry (`variant: asymmetric+intransitive`) | Looking at Halpin's compound names and assuming one YAML entry | Emit each variant as a separate `ring` constraint entry. Cleaner verbalization, cleaner translation, independent confirm/reject. |
| Promoting sample-derived uniqueness to a UC without user confirmation | Conflating "data is unique" with "schema requires uniqueness" | Sample uniqueness flags as Step 7 candidate only. UC emission requires DDL UNIQUE or explicit user confirmation. |
| Translating a deontic constraint to `model.require()` | Ignoring the `modality` field | Deontic emits as `# DEONTIC NOTE:` comments. `model.require` is alethic-only. |
| Using bare `Number` for decimal types | Forgetting PyRel's Number.size requirement | Always `Number.size(precision, scale)` for non-integer decimal types per `rai-pyrel-coding`. |

## Examples

| Pattern | Files |
|---|---|
| Canonical small example covering object types, fact types, mechanical translation | [`examples/movie_catalog.sql`](examples/movie_catalog.sql) + [`movie_catalog.orm.yaml`](examples/movie_catalog.orm.yaml) + [`movie_catalog.py`](examples/movie_catalog.py) |
| Junction table — pure m:n vs objectified | [`examples/junction_objectification.sql`](examples/junction_objectification.sql) + [`.orm.yaml`](examples/junction_objectification.orm.yaml) |
| Encoded-enum antipattern recovery | [`examples/encoded_enum_antipattern.sql`](examples/encoded_enum_antipattern.sql) + [`.orm.yaml`](examples/encoded_enum_antipattern.orm.yaml) |
| TYPE-column subtype recovery | [`examples/subtype_from_type_column.sql`](examples/subtype_from_type_column.sql) + [`.orm.yaml`](examples/subtype_from_type_column.orm.yaml) |

## Reference files

| File | When to load |
|---|---|
| [`references/srp-workflow.md`](references/srp-workflow.md) | Detailed mechanics for any SRP step — heuristics, edge cases, error recovery. Load when a step's summary above isn't enough. |
| [`references/representation-format.md`](references/representation-format.md) | Full YAML schema spec — every field, every constraint type, every provenance shape. Load when emitting or validating a YAML structure. |
| [`references/constraint-reference.md`](references/constraint-reference.md) | Per-constraint vocabulary — ORM 2 graphical notation, YAML form, verbalization template, PyRel translation tier. Load when handling any constraint type beyond the basics. |
| [`references/constraint-inference.md`](references/constraint-inference.md) | Typed library + ring-pattern matcher + LLM-tier proposer rules. Load at Step 6. |
| [`references/verbalization-patterns.md`](references/verbalization-patterns.md) | Halpin-style CNL templates for every model element. Load at Steps 6d and 8. |
| [`references/orm-to-pyrel.md`](references/orm-to-pyrel.md) | Four-tier translation rules. Load at Step 10. |
| [`references/antipattern-catalog.md`](references/antipattern-catalog.md) | Full antipattern catalog with detection SQL, resolution mechanics, false-positive guidance. Load at Step 7. |
| [`references/probing-strategies.md`](references/probing-strategies.md) | Per-dialect SQL for INFORMATION_SCHEMA introspection and Step 5 sample probes. Sample-size caps and timeouts. Load at Steps 1 and 5. |
