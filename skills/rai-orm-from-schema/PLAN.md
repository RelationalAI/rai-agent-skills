# rai-orm-from-schema — Build Plan (v1)

> **Companion to [the text-first plan](../rai-orm-from-text/PLAN.md)** (now built alongside v1). This document is v1 — the structured-input skill: input is a relational schema (live DB, DDL file, CSV samples), output is an ORM YAML model and PyRel code.

> **Scope discipline (revised 2026-04-29):** v1 matches the existing-skill pattern in this repo — `SKILL.md` + `references/` (markdown) + `examples/` (illustrative) + `evals/`. Claude does the work in-session by reading the skill and applying the rules, the same way `rai-ontology-design` works. **No Python package, no CLI, no MCP server, no pytest.** Items dropped from earlier drafts are preserved as stretch goals in [`../../notes/TODO.md`](../../notes/TODO.md) (S1–S7). The architecture decisions (YAML format, five-source provenance, alethic/deontic, SRP workflow, Halpin fidelity) all stay — only the packaging shrinks.

---

## Strategic Rationale — Why Structured First

The existing repo has two schema-first skills that go straight to PyRel: `rai-build-starter-ontology` (greenfield from Snowflake/CSV) and `rai-ontology-design` (enriching/reviewing existing models). Building `rai-orm-from-schema` on the same input class gives us a **side-by-side comparison** of two architectures — direct schema → PyRel vs schema → ORM YAML → PyRel — on identical workloads.

**Construction is independent of those skills' modeling content.** The implementer does not consult `rai-build-starter-ontology` or `rai-ontology-design` for modeling decisions, queries, naming, output on test schemas, or constraint-extraction style (S7). Generic UX/structural patterns common across the repo's skills (e.g., the Guided / One-shot interaction-mode opener) are allowed — these are repo-wide conventions, not modeling choices. PyRel idioms come from `rai-pyrel-coding`; ORM 2 vocabulary comes from Halpin's source material. Those skills appear in our deliverables only via the user-facing "When NOT to use" redirects.

**Comparison is post-release, human-judged.** After v0.1 ships, humans review both outputs side-by-side on real schemas. If reviewers find the YAML+ORM artifact more useful — better stakeholder reviewability, more constraints surfaced, easier to retarget — the architecture earns its keep before we attempt the harder text-first case. If reviewers find no advantage, we learn that without committing to the speculative text-first work.

---

## Decisions

### Inherited from the text-first plan

YAML intermediate, five-source / three-status constraint provenance, typed-library + LLM constraint inference, alethic/deontic modality, top-level `version: 1` field, Halpin copyright discipline, `rai-pyrel-coding` alignment.

### Specific to this skill

| # | Decision | Date |
|---|---|---|
| S1 | **Schema-to-ORM is the primary direction** (schema modeling — starting from existing structure and recovering a conceptual model). Text-to-ORM (forward design from requirements) is `rai-orm-from-text`'s lane. | 2026-04-27 |
| S2 | **Schema Recovery Procedure (SRP), not CSDP.** Halpin's CSDP (Conceptual Schema Design Procedure) is a seven-step methodology for *designing* an ORM model from scratch with a domain expert. We're recovering an existing model, not designing one — so we replace it with our own SRP, sketched below. | 2026-04-27 |
| S3 | **Verbalization runs *after* model recovery.** Template-driven, generated from the recovered YAML for stakeholder review. | 2026-04-27 |
| S4 | **Sample-data probing is part of the workflow.** `COUNT DISTINCT`, `MIN/MAX`, NULL rates, value distributions — used to upgrade `proposed` constraints to `confirmed` where data supports. | 2026-04-27 |
| S5 | **Boundary with existing skills must be explicit** in the skill description and "When NOT to use" text. The differentiator is the YAML+ORM artifact and its stakeholder reviewability. | 2026-04-27 |
| S6 | **Skill name:** `rai-orm-from-schema`. | 2026-04-28 |
| S7 | **Pass-bar is intrinsic, not comparative; build is independent of those skills' modeling content.** v0.1 ships when our skill meets its own quality criteria (defined under "Evals" below). The head-to-head against `rai-build-starter-ontology` is post-release, human-judged. **What's prohibited during construction:** consulting those skills' modeling decisions, output on test schemas, query specifics, naming choices, or constraint-extraction style. **What's allowed:** generic UX/structural patterns common across this repo's skills (e.g., "skills offer a Guided vs One-shot interaction mode at the start") — these are repo-wide conventions, not modeling choices. PyRel conventions come from `rai-pyrel-coding`; ORM conventions from Halpin's source material. | 2026-04-28 |
| S8 | **`confidence` field is input-source-driven.** Default `standard`; `low` only when input is CSV/Parquet (no schema at all). For live-DB/DDL inputs, DDL-derived constraints become `source: explicit, status: confirmed`. CSV-only stays `source: sample, status: proposed`; verbalization opens with a warning paragraph; generated PyRel opens with a `# WARNING: Low-confidence model` block. | 2026-04-28 |
| S9 | **No code abstraction layer.** Claude reads the queries and rules from `references/` and runs them in-session via Bash, the same way existing schema-first skills work. The DataSource interface, factory, and adapters that earlier drafts proposed are stretch goals (TODO.md S3) — not v1. | 2026-04-29 |
| S10 | **Real customer schema for benchmark: tabled.** None available. Proceed with Northwind + TPC-H + a synthetic representative; revisit later. | 2026-04-28 |
| S11 | **Shared content stays in this skill's `references/` for v1.** When `rai-orm-from-text` construction begins, factor common reference markdown into `skills/rai-orm-core/`. Tracked in TODO.md. | 2026-04-28 (revised 2026-04-29) |
| S12 | **Follow Halpin's ORM 2 closely.** Halpin's source material (`notes/orm-resources/`) is the canonical reference for: (a) YAML schema vocabulary, (b) constraint vocabulary, (c) verbalization conventions, (d) objectification, (e) reference-mode shorthand (the `Country(.code)` syntax for declaring an entity type's reference scheme inline). The skill should produce models a Halpin-trained ORM modeler would recognize as orthodox. Originality discipline: examples are ours, paraphrasing is fine, reproduction of Halpin's text or diagrams is not. | 2026-04-28 |

---

## Inputs and Outputs

**Input** — any of:

| Input shape | Notes |
|---|---|
| **Live SQL DB** (Snowflake / Postgres / MySQL / Oracle / SQLite) | Most informative case when available. Requires the user to have local Snowpark (Snowflake) or DBAPI/SQLAlchemy access from their Claude Code session — not always the case in practice. Probing enabled. |
| **DDL file** (raw `CREATE TABLE`) | Parsed via sqlglot. No live data → no probing → constraint upgrades unavailable. |
| **CSV / Parquet samples** | Common when no schema is available. Pandas-driven type inference. **Always emits `confidence: low` (S8).** |
| **DDL + CSV combined** | DDL gives structure; CSV enables sample probing. Realistic primary path when the user lacks live-DB access from their Claude session. |
| JSON Schema | Future / stretch (deferred). |

**Output:**
- `model.orm.yaml` — ORM model with full provenance.
- `model.py` — PyRel code, generated by Claude applying the translation rules from `references/orm-to-pyrel.md`.
- `model.verbalization.txt` — natural-language verbalization for stakeholder review, generated by Claude applying the patterns in `references/verbalization-patterns.md`.

---

## Workflow: the Schema Recovery Procedure (SRP)

The "thing being taught" by the skill. Ten steps:

> 1. **Inventory.** Discover tables, columns, types, PKs, FKs, UNIQUEs, NOT NULLs, CHECKs, indexes.
> 2. **Identify object types.** Each table with a PK → entity type. Junction tables (composite PK that's all-FK) flagged for objectification analysis.
> 3. **Identify fact types.** Every FK → binary fact type. Every non-FK column → role on a fact type rooted in its table's entity type. Repeated-string columns with low cardinality → value type with enumeration.
> 4. **Lift explicit constraints.** PK / UNIQUE → uniqueness. NOT NULL → mandatory. CHECK → value constraint (when parseable). FK → mandatory on the FK side.
> 5. **Probe samples** (when access permits). Cardinality, value ranges, NULL rates, distinct-value distributions. Upgrade `proposed` to `confirmed` where data supports.
> 6. **Apply constraint inference.** Typed library matches by object type / relationship pattern; LLM-driven for novel cases. All `proposed`, awaiting validation. (Full mechanics under "Constraint Provenance and Inference" below.)
> 7. **Detect schema antipatterns.** Denormalized address columns, TYPE/CATEGORY columns suggesting subtypes, ambiguous junction tables, encoded enums in VARCHAR. Flag each for user review.
> 8. **Verbalize the recovered model** end-to-end (per `references/verbalization-patterns.md`) and present to the user.
> 9. **Capture user decisions and additions.** Confirm / reject / escalate proposals; resolve antipattern ambiguities; add user-supplied constraints; label alethic / deontic. (Full mechanics under "SRP Step 9 expansion" below; includes Guided vs One-shot mode behavior.)
> 10. **Translate to PyRel** by applying the rules in `references/orm-to-pyrel.md`.

How Claude executes this: reads the SRP from SKILL.md, follows step-by-step, runs ad-hoc Python or SQL via Bash for introspection and probing, applies the markdown-documented rules for constraint inference and translation. No bundled scripts.

The locked v0.1 specification — full substeps, inputs/outputs per step, user-interaction surface, mode behavior, and antipattern catalog — is captured in [`notes/phase1-srp-workflow.md`](../../notes/phase1-srp-workflow.md). Phase 3 lifts from there into `references/srp-workflow.md`.

---

## Constraint Provenance and Inference

Every constraint in the model carries a provenance tag — where it came from, what review state it's in, and whether it's an alethic must or a deontic should. Constraints originate from five sources, ranging from hard schema facts to user-supplied domain knowledge. The system never silently asserts an inferred constraint; it proposes, the user confirms.

**Core principle: propose, never assert.** Every constraint that isn't directly lifted from DDL is a *candidate* validated with the user. This is what makes the YAML auditable and what prevents the skill from quietly turning common-sense guesses into hard schema rules.

```yaml
constraints:
  - type: uniqueness
    roles: [Child]
    source: common-sense       # explicit | sample | common-sense | llm-inferred | user-supplied
    status: proposed           # proposed | confirmed | rejected
    rationale: "Each person has exactly one biological mother."
```

### `source:` field — five values

1. **`explicit`** — PK/UNIQUE → uniqueness. NOT NULL → mandatory. CHECK → value constraint. FK → mandatory on the FK side. Lifted directly from DDL or `INFORMATION_SCHEMA`. Auto-`status: confirmed`.
2. **`sample`** — Cardinality probes on live data. Live-DB input can auto-promote to `confirmed`; CSV input always stays `proposed` (S8).
3. **`common-sense`** — Typed library lookup keyed on object type / relationship pattern, plus structural pattern recognition (e.g., self-referential binary fact type → propose acyclic + asymmetric + irreflexive). The library lives in `references/constraint-inference.md` as a markdown table — examples below. Auto-`status: proposed`.
4. **`llm-inferred`** — For object types the library doesn't cover, Claude proposes constraints from training-time world knowledge. Highest hallucination risk; flagged for explicit user review.
5. **`user-supplied`** — Constraints the user adds during the review pass (Step 9 of the SRP) when they notice domain knowledge the system missed (*"each country has exactly one capital"*, *"each project has exactly one project manager in our company"*). Auto-`status: confirmed` — they're added deliberately, not proposed for review.

Typed library examples (stored in `references/constraint-inference.md`):

| Object type / pattern | Auto-proposed constraints |
|---|---|
| `Date` | Must be valid date |
| `Money`, `Age`, `Count`, `Duration` | Non-negative |
| `Event` with start + end | `start ≤ end` |
| Self-referential `parent-of` / `ancestor-of` | Acyclic, asymmetric, irreflexive |
| `married-to` (under monogamy) | Symmetric, irreflexive, functional |
| `precedes` / `supersedes` | Acyclic, transitive |
| `contains` / `part-of` | Acyclic, asymmetric |
| "Biological parent" relations | At most one father, exactly one mother |

### `status:` field — three values

| Value | Meaning |
|---|---|
| `proposed` | Candidate, not yet reviewed. Default for `common-sense` and `llm-inferred`; also for CSV-input `sample` (S8). |
| `confirmed` | Accepted. Auto-confirmed for `explicit`, for `user-supplied` (added deliberately), and for live-DB `sample` when probing exceeds the confidence threshold. Otherwise human-confirmed during Step 9 review. |
| `rejected` | User explicitly said no. Kept in a `rejected_proposals` list so we don't re-propose. |

`source` is set once at creation. `status` evolves through review. A constraint can be `source: common-sense, status: confirmed` — originally proposed, then user-confirmed.

### Alethic vs. deontic modality

ORM 2's modality distinction labels confirmed constraints as a *must* (alethic — necessarily true) or a *should* (deontic — norm or policy with possible exceptions). Examples:

- "A child has one biological mother" → alethic.
- "A person has one spouse" → deontic.
- "An employee reports to one manager" → deontic.
- "Parenthood is acyclic" → alethic.

The user labels modality at confirmation time (Step 9e of the SRP, below). Alethic constraints become hard rules; deontic constraints emit as `# DEONTIC NOTE:` comments in PyRel since `model.require` is alethic-only.

### SRP Step 6 expansion

Step 6 ("Apply constraint inference") expands into five substeps. (Lifting explicit constraints and probing samples are SRP Steps 4 and 5 — separate top-level steps. Final user decisions on these proposals happen later, in Step 9; 6d is a narrow Guided-mode-only early filter, scope-limited to LLM-tier proposals.)

> 6a. Auto-propose constraints from the typed library (deterministic, by object type / relationship pattern).
> 6b. Auto-propose ring constraints from relationship patterns (deterministic, structural).
> 6c. Ask Claude to propose further constraints from world knowledge (LLM, novel cases).
> 6d. **LLM spot-check** (Guided mode only; opt-in). User filters obvious hallucinations from Step 6c proposals before they pollute Step 8's full-model verbalization. Library- and ring-tier proposals (6a, 6b) are NOT surfaced here — they're reviewed in context at Step 9b. No "user suggests their own" at 6d either; that path is 9d.
> 6e. Verbalize all surviving proposals back to the user in a single batch with their provenance and rationale.

### SRP Step 9 expansion

Step 9 ("Capture user decisions and additions") is the final user-decision moment, after all proposals from Step 6 have been generated, antipatterns from Step 7 have been flagged, and the whole-model verbalization from Step 8 is on the table. Six substeps:

> 9a. User reviews the whole-model verbalization (Step 8 output).
> 9b. User confirms / rejects / escalates each proposed constraint from Step 6.
> 9c. User resolves antipattern-flag ambiguities raised in Step 7.
> 9d. User adds any constraints they know but the system missed (`source: user-supplied`, auto `status: confirmed`). Examples: *"each country has exactly one capital"* (general world knowledge the LLM might miss for less-famous facts), *"each project has exactly one project manager"* (organization-specific).
> 9e. User labels every confirmed constraint as alethic or deontic.
> 9f. Commit confirmed + user-supplied to YAML. Rejected proposals go in `rejected_proposals` so we don't re-propose them.

**Guided vs One-shot mode.** In Guided mode this is interactive — Claude asks per substep (or batch by category) in conversation. In One-shot mode the substeps collapse: library-tier proposals auto-confirm, higher-tier proposals (LLM-inferred, ambiguous antipatterns) stay as `proposed` in the YAML, and the user reviews/adds post-hoc by editing the YAML directly.

### Risks of the inference layer

- **Cultural/legal variation.** Don't silently assume monogamy, the Gregorian calendar, USD currency. Library entries flag their assumptions.
- **Hallucination at the LLM tier.** Provenance + mandatory user review is the only defense.
- **Stale common sense.** Library entries need periodic review.
- **Over-constraining narrows models silently.** Always leave a clean reject path.
- **Schema-extracted constraints can be wrong too.** A `CHECK age > 0` doesn't guarantee real data complies — review confirmed constraints for surprises.
- **Foundational ontologies** (DOLCE, UFO, OntoUML) encode much of this rigorously per Guizzardi's paper — overkill for v1; a typed library is more pragmatic.

Domain-specific (organization-policy) constraints are a separate v1.5 extension via a per-deployment `domain_library.yaml`. Tracked in TODO.md item #6.

---

## YAML Representation Format

Custom YAML with rich per-constraint provenance. Core shape:

```yaml
version: 1

source:
  kind: sql                     # sql | ddl-file | csv (json-schema deferred to v1.5)
  dialect: snowflake            # snowflake | postgres | mysql | oracle | sqlite (applies when kind ∈ {sql, ddl-file})
  connection_id: prod_warehouse
  scope: { database: SALES_DW, schema: PUBLIC, tables: ["*"] }
  introspected_at: "2026-04-27T14:32:00Z"
  confidence: standard          # standard | low

object_types:
  - id: customer
    name: Customer
    kind: entity
    reference:
      mode: popular                          # popular | unit-based | general | external (composite)
      value_type: CustomerId
    provenance:
      origin: table-with-pk
      table: PUBLIC.CUSTOMERS
      pk_column: CUSTOMER_ID

fact_types:
  - reading: "{Customer} has email {EmailAddress}"
    roles: [Customer, EmailAddress]
    constraints:
      - type: uniqueness
        roles: [Customer]
        source: explicit
        status: confirmed
        rationale: "PK on PUBLIC.CUSTOMERS.CUSTOMER_ID."
        provenance: { table: PUBLIC.CUSTOMERS, column: EMAIL }

  - reading: "{Order} placed by {Customer}"
    roles: [Order, Customer]
    constraints:
      - type: mandatory
        role: Order
        source: explicit
        status: confirmed
        provenance: { table: PUBLIC.ORDERS, fk: FK_ORDERS_CUSTOMER, column: CUSTOMER_ID }
```

Every fact type and every constraint traces back to a specific schema element. This is what makes the YAML auditable: a reviewer can see *exactly why* the model claims each thing and click through to the source column.

Full schema spec lives in `references/representation-format.md` (Phase 3 deliverable). The locked v0.1 spec — covering every Halpin ORM 2 construct, the inline-vs-top-level scope rule, all five-source provenance shapes, and resolutions to the Halpin open questions — is captured in [`notes/phase1-yaml-format.md`](../../notes/phase1-yaml-format.md) and is the source of truth Phase 3 lifts from.

---

## ORM → PyRel Translation

Claude reads `references/orm-to-pyrel.md` and applies the translation rules in-session, producing `model.py` from `model.orm.yaml`. The rules are documented as four tiers (refined 2026-05-04 after Phase 1.1 read of `rai-pyrel-coding` — see `notes/phase1-pyrel-findings.md`):

- **Mechanical:** object types → `Concept` (with `identify_by`); uniqueness-on-role binary fact types → `Property` (PyRel enforces FD); multi-valued binary fact types → `Relationship`; NOT NULL → required-via-property; subtypes → `extends=[Parent]` + `model.define(Sub(Parent)).where(...)`; value constraints with enumeration → `model.Enum`; `Number.size(p,s)` for decimals.
- **Heuristic:** objectification of binary fact types → junction concept with `identify_by={"a": A, "b": B}` (canonical PyRel pattern, line 159 of rai-pyrel-coding); subtype recovery from TYPE-column hints; same-type fact types → named refs (`{Stock:stock1} and {Stock:stock2}`); unary fact types → unary `Relationship`.
- **`model.require()` tier (verbose but expressible):** ring constraints (irreflexive, asymmetric, etc. on self-references), counted frequency ("each jury has exactly 12 members"), external uniqueness over joins, join subset/exclusion. Emit as `model.require(...)` rules with explanatory comments — not idiomatic, but PyRel handles them.
- **Truly not translated:** deontic constraints. PyRel's `model.require` is alethic-only. Emit as `# DEONTIC NOTE:` comments per S8 / Constraint Provenance section.

PyRel idioms come from `rai-pyrel-coding`. Halpin-copyright discipline (S12): paraphrase, don't reproduce.

---

## Caveats

1. **Schema-recovery is fundamentally lossy.** A schema is one of many valid ORM flattenings. The original objectification, business-rule rationale, and alethic-vs-deontic distinctions don't come back from normalized tables. Output is *always* a draft for human review, never authoritative.
2. **Junction tables are ambiguous.** A composite-PK all-FK table could be: (a) an objectified binary fact type, (b) a true ternary, (c) an entity type whose PK is composite. Skill needs a default and a way to flag ambiguity.
3. **Subtype detection from TYPE/CATEGORY columns is heuristic.** `BUSINESS_TYPE` with values `'Supplier','Customer','Manufacturer'` usually means subtypes — but sometimes it's just a status flag. Probe before committing.
4. **Denormalized address / contact columns** — separate Address entity vs. inline properties depends on whether addresses are *shared* across multiple customers (then it's an entity) or strictly 1:1 with Customer (then they're properties). The skill should ask the user which case applies before committing — both are reasonable model shapes.
5. **Encoded enums in TEXT columns.** `STATUS VARCHAR` with five known values look like value types with enumeration; a schema-level CHECK isn't always present.
6. **Schema antipattern naming.** All-uppercase `_`-separated names need PyRel idiom canonicalization (lowercase, descriptive). PyRel naming from `rai-pyrel-coding`.
7. **Cardinality probing has cost.** `COUNT DISTINCT` on a billion-row table isn't free. Skill needs a sampling strategy and a budget. Guidance lives in `references/probing-strategies.md`.
8. **Build-time contamination risk.** Implementer must avoid reading `rai-build-starter-ontology`'s or `rai-ontology-design`'s implementation, queries, or output during construction (per S7).

---

## Evals and Benchmark

Two distinct activities, run at different times.

### Activity 1 — Build-time evals (the v0.1 gate)

Intrinsic quality checks: does our skill produce a good ORM model on its own merits? Run during construction and as part of declaring v0.1.

**Reference solutions.** For each benchmark schema, hand-build the expected ORM YAML — independently, without consulting `rai-build-starter-ontology` or `rai-ontology-design` (per S7). Stored in `evals/expected/<schema>.orm.yaml`. These are version-controlled and reviewed before becoming authoritative ground truth.

**Authorship and review (locked 2026-05-04, Pre-Implementation Risk #2 resolved).** Claude drafts each `expected/<schema>.orm.yaml` under explicit Halpin-grounding constraints — every constraint cites the Halpin rule that justifies it (book + chapter/section reference) and the source category (`explicit | sample | common-sense | llm-inferred | user-supplied`). the reviewer reviews line-by-line against the source material (Halpin's books, schema DDL, sample data) and accepts/rejects/edits each entry. The the reviewer-reviewed file is ground truth; Claude's draft is not. Circularity is broken because grading uses the reviewed file, not the draft. Drafting effort is Claude's; the reviewer's review time is the gating cost (~2–4 hours per schema for Northwind + TPC-H sized inputs).

**Eval cases** (data in `evals/cases.json`; reviewed by Claude in-session against the reference solutions):

| # | What we measure | Method |
|---|---|---|
| **E1** | Reference-solution match | Diff our skill's output against `expected.orm.yaml`. Concepts / fact types / explicit-source constraints must match (modulo equivalence rules below). Inferred constraints judged against the correctness rubric. |
| **E2** | Constraint coverage | Count constraints by `source` category. Targets vary by input type — see "E2 targets by input type" below. |
| **E3** | Degradation behavior | Hide one column from the schema before running. Output must reflect the absence (correct partial model + flagged ambiguity), not silently invent. |
| **E4** | Antipattern detection | Synthetic schemas with planted antipatterns (denormalized address, encoded enum in VARCHAR, ambiguous junction table, TYPE-column subtype). Output must flag each. |
| **E5** | Stakeholder reviewability | Hand the YAML to someone who doesn't know PyRel; can they validate constraints by reading verbalizations? Pass = at least one stakeholder confirms they can validate without help. |

**E1 equivalence rules.** Object types match by name modulo case; fact types match by structural shape (roles in order); reading-pattern wording can differ; explicit-source constraints must match exactly in type, target, and provenance; inferred constraints judged independently against the rubric; declaration order and pure formatting differences ignored.

**E2 targets by input type.** Coverage targets are conditional on what the input actually provides:

| Input | `explicit` target | `sample` target | `common-sense` target | `llm-inferred` target |
|---|---|---|---|---|
| Live SQL DB | 100% of DDL constraints | uniqueness on every column observed unique | every applicable library entry | best-effort |
| DDL file (no live data) | 100% of DDL constraints | N/A (no probing) | every applicable library entry | best-effort |
| CSV-only (low confidence) | N/A (no DDL) | uniqueness / mandatory inferred from sample | every applicable library entry | best-effort |
| DDL + CSV combined | 100% of DDL constraints | sample-derived upgrades where data supports | every applicable library entry | best-effort |

**Constraint correctness rubric.** A constraint is correct iff:
1. **It holds in the source.** DDL says so / sample data confirms / domain-expert judgment confirms.
2. **It's intentional, not coincidental.** A domain expert reviewing the YAML would say "yes, that's a real rule of the domain" rather than "yes, that happens to be true in this data but it's not a rule."

Sample-derived uniqueness on a column with 9,998/10,000 distinct values is probably coincidental — flagged for review, not auto-confirmed. Both gates required.

**v0.1 pass-bar:** E1 must pass on Northwind + TPC-H + the synthetic representative; E2 coverage targets met per category per schema; E3 and E4 pass on all synthetic test cases; E5 pass with at least one stakeholder.

Below this bar, we don't ship v0.1 and we don't kick off `rai-orm-from-text`.

### Activity 2 — Post-v0.1 head-to-head

After v0.1 ships, humans review our skill's output side-by-side against `rai-build-starter-ontology`'s output on the same schemas. Manual workflow at v1's small N (3 schemas). The eval-runner / benchmark-runner scripts that earlier drafts proposed are stretch goals (TODO.md S6).

Reviewers rate on: which output is more reviewable for a non-technical stakeholder, which has more correct constraints, which catches more antipatterns, which is easier to retarget, which costs less to produce. Aggregated review answers **does YAML+ORM justify its overhead?** If yes, `rai-orm-from-text` is greenlit. If no, we revisit.

This is not a build-time gate — it happens after v0.1 ships. Per S7, the build process must not be contaminated by the baseline output.

### Benchmark schemas

| Schema | Source | Why |
|---|---|---|
| **Northwind** | Public DDL | Small, classic, multiple FK levels, junction tables. |
| **TPC-H** | TPC public spec | Larger, normalized, no surprises — exercises scale. |
| **Synthetic representative** | We hand-craft | Plants the antipatterns we want to test (denormalized address, encoded enums, ambiguous junction tables, TYPE-column subtypes). Substitutes for the not-currently-available real customer schema (S10). |

---

## Pre-Implementation Risks (Watch-Out List)

Risks to internalize before kicking off the phases below. The first three are addressed inside Phase 1 — flagged separately here because they're easy to miss embedded in a phase list. The fourth is an ongoing discipline that doesn't fit any one phase.

1. **`rai-pyrel-coding` coverage.** If it doesn't cover ring constraints, deontic flagging, or junction-concept patterns, our `references/orm-to-pyrel.md` gap list grows beyond what the ORM → PyRel section currently assumes. *Mitigated by Phase 1's first task — read `rai-pyrel-coding` end-to-end before locking architecture decisions.*

2. **Reference-solution circularity.** ~~E1 ground truth cannot be both authored and graded by Claude.~~ **Resolved 2026-05-04:** Claude drafts under Halpin-grounding constraints (each constraint cites the rule + source category); the reviewer reviews line-by-line; the reviewed file is ground truth. See Activity 1 for full description.

3. **Weak synthetic fixtures.** Phase 4 inventing the synthetic schema and its antipatterns simultaneously produces weak test cases. *Mitigated by Phase 1's synthetic-schema-spec task — one-page spec written before Phase 4.*

4. **Bad-content cascade (ongoing discipline).** Bad SKILL.md → bad references → bad examples → bad evals. The plan doesn't enforce a review cycle. Suggested rhythm: SKILL.md gets the reviewer review before Phase 3 begins; each reference file gets spot-review per file as written; examples get reviewed against references before evals are built.

---

## Build Plan — Five Phases

**Phase 1 — Spec and source-material grounding (3–4 days).**
- Read `rai-pyrel-coding/SKILL.md` and its references; lock down PyRel conventions for `references/orm-to-pyrel.md`. **Capture notes during this read** (not just understanding) since `references/orm-to-pyrel.md` is written in Phase 3 — days later, details will fade. Do not read `rai-build-starter-ontology` or `rai-ontology-design` (S7).
- Read Halpin's source material from `notes/orm-resources/`:
  - `books/ORM 2 Graphical Notation.pdf` (6 pages, full read).
  - `books/ORM_Fundamentals_clean.pdf`: chapters on (a) fact types and roles, (b) reference schemes, (c) constraints (uniqueness, mandatory, value, set-comparison, frequency, ring), (d) subtyping, (e) objectification. Skip chapters on UML/ER mapping for v1; skip philosophical foundations.
  - `books/ORM_Workbook_clean.pdf`: skim for worked examples that exercise the constructs above.
  - Estimate ~80–120 pages targeted reading, not full books.
- Ground the YAML schema, constraint vocabulary, verbalization grammar, and SRP terminology in Halpin's framework (S12).
- Lock the YAML representation format with the provenance fields above.
- Lock the SRP workflow (the 10 steps).
- **Specify the synthetic representative schema:** target ~20 tables; plausible business domain (suggested: small e-commerce or logistics-ops); embed the antipatterns within a realistic schema rather than as standalone fixtures (denormalized address columns on Customer; encoded enum in `STATUS VARCHAR`; ambiguous junction table with composite PK; TYPE-column subtype split). Write a one-page spec before Phase 4 builds it.
- **Reference-solution authorship and review (locked 2026-05-04).** Claude drafts each `expected/<schema>.orm.yaml` under explicit Halpin-grounding constraints — every constraint cites the Halpin rule + source category. the reviewer reviews line-by-line against the source material; the the reviewer-reviewed file is ground truth (not the draft). See Activity 1 for full description. Resolves Pre-Impl Risk #2.
- Pick benchmark schemas (Northwind + TPC-H + synthetic representative).
- Draft the skill description text.

**Phase 2 — SKILL.md skeleton (2–3 days).**
- Frontmatter and stability tag (`v1-SENSITIVE`).
- Summary / "When to use" / "When NOT to use" — tight redirects to existing schema-first skills (the only places those skills appear in our deliverables).
- Interaction-mode opener — at the start of the conversation, Claude asks the user whether to run **Guided** (confirm proposals step by step) or **One-shot** (emit the full YAML for post-hoc review). Generic UX pattern in this repo (also used by `rai-build-starter-ontology`), allowed under S7.
- SRP workflow with concrete prompts.
- Constraint provenance & validation flow.
- Antipattern detection patterns.
- ORM → PyRel mapping (gap list).
- Common pitfalls, examples table, reference files table.

**Phase 3 — References and Examples (3–4 days).**

*References (markdown, loaded by Claude on demand):*
- `references/srp-workflow.md` — full SRP, prompt-by-prompt.
- `references/representation-format.md` — full YAML schema spec.
- `references/constraint-reference.md` — full ORM 2 constraint vocabulary.
- `references/constraint-inference.md` — typed library + proposer rules + LLM fallback. Library lives as a markdown table here.
- `references/verbalization-patterns.md` — Halpin-style controlled natural language patterns for rendering the recovered model (used in SRP Steps 6d and 8, and for `model.verbalization.txt`).
- `references/orm-to-pyrel.md` — translation rules across the three tiers.
- `references/antipattern-catalog.md` — denormalized address, encoded enums, TYPE-column subtypes, junction-table objectification, etc.
- `references/probing-strategies.md` — SQL queries, sampling strategy, cost budget.

*Examples (illustrative pattern files, like other skills):*
- `examples/movie_catalog.sql` + `.orm.yaml` + `.py` — small, illustrative; the canonical example.
- `examples/junction_objectification.sql` + `.orm.yaml` — shows ambiguity-handling.
- `examples/encoded_enum_antipattern.sql` + `.orm.yaml` — antipattern detection.
- `examples/subtype_from_type_column.sql` + `.orm.yaml` — subtype recovery.

**Phase 4 — Evals (2–3 days).**
- `evals/cases.json` — E1–E4 case definitions.
- `evals/expected/northwind.orm.yaml` + `tpc_h.orm.yaml` + `synthetic.orm.yaml` — hand-built reference solutions per the authorship/review plan locked in Phase 1. ~half a day each.
- `evals/fixtures/synthetic/schema.sql` — single-file synthetic schema with planted antipatterns (per the Phase 1.4 spec, which consolidated the originally-split fixture into one 21-table schema).
- E5 stakeholder-reviewability checklist (markdown in `evals/`).
- **Eval-run output convention.** Each manual eval run writes to `evals/results/<YYYY-MM-DD>/<schema>/{output.orm.yaml, output.py, output.verbalization.txt, diff.md}`. The `diff.md` records the E1/E2 comparison against `expected.orm.yaml`. This makes runs comparable across time and reproducible by a reviewer reading the folder.
- Manual eval methodology — Claude runs the skill on each schema, writes outputs to the convention above, then produces the diff against the reference solution.

**Phase 5 — Integration and dogfooding (ongoing).**
- Run on real RAI scenarios.
- Run dev-quality-skills-review checklist (`contrib/dev-quality-skills-review/SKILL.md`).
- Run the Activity 2 head-to-head review — our skill's output vs `rai-build-starter-ontology`'s, judged by humans.
- Bump the plugin version in `.claude-plugin/marketplace.json` (per CLAUDE.md) when the skill is ready to publish.
- **Decision point:** does the YAML+ORM architecture justify itself? If yes, unfreeze and proceed to `rai-orm-from-text`. If no, revisit the architecture.

**Total rough estimate:** ~2.5–3 weeks of focused work to v0.1, including review cycles. The original "2 weeks" estimate underweighted the volume of carefully-grounded markdown content in Phase 3 (~7 reference files × 150–300 lines each, plus 4 example triples) and the iteration time on reference solutions in Phase 4.

---

## Folder Structure (final, matches existing-skill pattern)

```
skills/rai-orm-from-schema/
  SKILL.md
  references/
    srp-workflow.md
    representation-format.md
    constraint-reference.md
    constraint-inference.md
    verbalization-patterns.md
    orm-to-pyrel.md
    antipattern-catalog.md
    probing-strategies.md
  examples/
    movie_catalog.sql
    movie_catalog.orm.yaml
    movie_catalog.py
    junction_objectification.sql
    junction_objectification.orm.yaml
    encoded_enum_antipattern.sql
    encoded_enum_antipattern.orm.yaml
    subtype_from_type_column.sql
    subtype_from_type_column.orm.yaml
  evals/
    cases.json
    reviewability_checklist.md
    expected/
      northwind.orm.yaml
      tpc_h.orm.yaml
      synthetic.orm.yaml
    fixtures/
      northwind/
        fetch.sh
        README.md
        .gitignore                       # excludes generated SQL from source control
      tpc_h/
        fetch.sh
        README.md
        .gitignore
      synthetic/
        schema.sql                       # hand-built; one file with DDL + sample data, all 21 tables + antipatterns
        README.md
    results/                            # runtime eval-run outputs (per Phase 4 convention; gitignored)
```

Same shape as `rai-ontology-design` (which has SKILL.md + references/ + examples/ + evals/). No `tools/`, no `pyproject.toml`, no `tests/`. Stretch ideas preserved in TODO.md (S1–S7).

---

## Residual Open Questions

- **Diagram rendering** — out of scope for v1. Skip.
- **NORMA `.orm` XML export** — defer to v1.5 stretch.
- **Guizzardi-critique mention in scope text** — include one sentence pointing to OntoUML/DOLCE for users who need foundational ontology.
- **Boundary aggressiveness** in "When NOT to use" text — permissive in v1, sharpen after benchmark.

(Other deferred items — including `domain_library.yaml` and the over-engineering stretch goals S1–S7 — are tracked in [`../../notes/TODO.md`](../../notes/TODO.md).)

---

## Summary

`rai-orm-from-schema` is v1, scoped to match the existing-skill pattern in this repo. **Architecture:** YAML intermediate + provenance-tracked constraint inference, applied to structured input via the Schema Recovery Procedure (SRP); grounded in Halpin's ORM 2 (S12). **Mechanism:** Claude reads the skill and applies the rules in-session — no Python package, no CLI, no MCP. **Build discipline (S7):** independent of `rai-build-starter-ontology` and `rai-ontology-design` except for user-facing redirects. **Pass-bar (S7):** intrinsic, defined by hand-built reference solutions and the E1–E5 eval cases. **Architecture validation:** post-release human-judged head-to-head against `rai-build-starter-ontology` decides whether YAML+ORM earns its keep before we attempt `rai-orm-from-text`. **Estimate:** ~2.5–3 weeks to v0.1, including review cycles.
