# Schema Recovery Procedure (SRP) — Full Workflow

The complete 10-step workflow with substeps, mechanics, edge cases, mode behavior, and worked examples. Load when a step's summary in SKILL.md isn't enough.

The SRP is the inverse of Halpin's CSDP (Conceptual Schema Design Procedure). CSDP goes domain → ORM forward; the SRP goes schema → ORM backward.

Cross-references:
- YAML output shape per step → [representation-format.md](representation-format.md)
- Per-constraint vocabulary → [constraint-reference.md](constraint-reference.md)
- Per-dialect SQL and probe queries → [probing-strategies.md](probing-strategies.md)
- Constraint inference library → [constraint-inference.md](constraint-inference.md)
- Antipattern catalog → [antipattern-catalog.md](antipattern-catalog.md)
- Verbalization templates → [verbalization-patterns.md](verbalization-patterns.md)
- PyRel translation rules → [orm-to-pyrel.md](orm-to-pyrel.md)

## Workflow shape

| Step | Title | User interaction? |
|---|---|---|
| 0 | Interaction-mode opener | Guided: yes |
| 1 | Inventory | no |
| 2 | Identify object types | no |
| 3 | Identify fact types | no |
| 4 | Lift explicit constraints | no |
| 5 | Probe samples | no |
| 6 | Apply constraint inference | Guided: yes (6d LLM spot-check, opt-in) |
| 7 | Detect schema antipatterns | no |
| 8 | Verbalize the recovered model | no (output for user) |
| 9 | Capture user decisions | Guided: yes (six substeps); One-shot: no |
| 10 | Translate to PyRel | no |

User-interaction surface is concentrated in Steps 0, 6d, and 9.

## Step 0 — Interaction-mode opener (Guided only)

In One-shot mode, this step is skipped — the SRP starts at Step 1.

In Guided mode, Claude prompts:

> *I can run this in two modes:*
> - *Guided — I confirm proposals with you step by step. Best for high-value or unfamiliar schemas.*
> - *One-shot — I emit the full YAML in one pass; you review by editing the file. Best for fast retargeting.*
> *Which would you prefer?*

The user's choice is recorded in `source.mode` of the YAML. Default = Guided if no answer is given (conservative: explicit confirmation beats silent acceptance).

**This is the only step where the user can pick the mode.** Once recorded, the SRP follows the chosen mode end-to-end.

## Step 1 — Inventory

**Input:** connection / DDL file / CSV path. Source `kind` reflects input type.

**Output:** in-memory schema description: tables, columns (name, type, nullability, default, comment), PKs, FKs, UNIQUE indexes, NOT NULLs, CHECKs, indexes.

**Mechanics:**
- For input kind `sql` — query INFORMATION_SCHEMA per dialect. See [probing-strategies.md](probing-strategies.md) "Step 1 — Inventory" for canonical queries.
- For input kind `ddl-file` — parse the DDL with a dialect-aware parser; structural extraction of `CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`, `COMMENT ON`.
- For input kind `csv` — infer column types from sampled values; PKs/FKs/CHECKs absent. Set `source.confidence: low`.

**Records in the YAML:**
```yaml
source:
  kind: sql
  dialect: snowflake
  scope: { database: …, schema: …, tables: ["*"] }
  introspected_at: "2026-05-04T14:32:00Z"
  confidence: standard
  mode: guided
```

**Edge cases:**
- **Large schemas (> 100 tables):** apply scope filtering at this step. Default = all tables; explicit `tables:` list narrows. The skill warns if scope returns 0 tables.
- **Cross-schema FKs:** capture them but flag as `provenance.warning: "cross-schema-fk"`. They may indicate the scope is too narrow.
- **Views:** v0.1 ignores views. Phase 4+ may enrich.
- **System tables:** filter out (`pg_*`, `sqlite_*`, etc.).

## Step 2 — Identify object types

**Input:** Step 1 output.

**Output:** YAML `object_types` populated with `kind`, `reference`, `provenance`. No subtypes yet (Step 7 detects them).

**Mechanics — per table:**

| Schema signal | Object-type emission |
|---|---|
| Single-column PK | Entity type, `reference.mode: popular`, `value_type` from PK column primitive |
| Composite PK (no all-FK pattern) | Entity type, `reference.mode: external`. External UC emitted in Step 4 |
| Junction table: composite PK that is all-FK, no extra non-FK columns | Flag as **pure m:n binary candidate**. Don't emit an entity type yet; defer to Step 7 antipattern resolution |
| Junction table: composite PK that is all-FK, has extra non-FK columns | Flag as **objectified binary candidate**. Emit entity type with `reference.mode: external` provisionally |
| Table without PK | Entity type with `provenance.origin: no-pk-detected, provenance.warning: "no-pk-detected"`. Raised at Step 7 |

**Value types** are extracted lazily — emitted in Step 3 when first referenced as the value side of a fact type.

**Naming:**
- `id` (YAML key): snake_case derived from table name. `PUBLIC.CUSTOMERS` → `customer`. Drop the `S` plural suffix when present.
- `name` (PascalCase): derived from `id`. `customer` → `Customer`.

**Edge cases:**
- **Single-row "options" tables** (e.g., a `SETTINGS` table with one row): emit as object type with `independent: true` proposal. Common-sense source.
- **Audit/history tables** (suffix `_HIST`, `_LOG`, `_AUDIT`): include as entity types but flag with `provenance.warning: "history-table"`. The user decides at Step 9 whether to keep or skip.
- **Lookup-only tables** (e.g., `CURRENCIES` with code+name): often map to value types in the recovered model; flag with `provenance.warning: "lookup-table-candidate"`. Default emission is entity type; Step 9 may convert.

## Step 3 — Identify fact types

**Input:** Steps 1–2 output.

**Output:** YAML `fact_types` populated with `id`, `reading`, `roles`, optional `objectified_as` / `derivation`.

**Mechanics — per source table:**

For each entity type's source table, walk its columns:

| Column type | Fact type emission |
|---|---|
| FK | Binary fact type linking this entity to the referenced entity. Reading derived heuristically from FK column name; default `"{A} has-a {B}"` when no signal. Mandatory inferred from NOT NULL (Step 4 emits the constraint). |
| Non-FK, non-PK | Binary fact type linking the entity to a value type. Reading: `"{Entity} has {value-name} {ValueType}"`. Value type emitted lazily if not present. |
| Self-referential FK (table referencing itself) | Binary fact type with both roles on the same object type. **Both roles must carry explicit `role_name`.** |

For junction tables flagged at Step 2 as **objectified candidates**:
- Emit the underlying binary fact type (e.g., `"{Student} enrolled in {Course}"`) with `objectified_as: <junction_id>` provisionally.
- Extra columns on the junction → fact types rooted in the objectification entity.
- Objectification confirmed in Step 7 / 9c.

For junction tables flagged as **pure m:n candidates**:
- Emit the binary fact type only (no objectification).
- Decision confirmed in Step 7 / 9c.

**Reading derivation heuristics (default):**

| FK column-name pattern | Generated reading template |
|---|---|
| `placed_by_<entity>_id` | `"{Source} placed by {Target}"` |
| `<verb>_by_<entity>_id` | `"{Source} <verb> by {Target}"` |
| `<entity>_id` (simple FK) | `"{Source} relates to {Target}"` (dull but safe) |
| `parent_<entity>_id` | `"{Source} has parent {Target}"` |
| `child_<entity>_id` | `"{Source} has child {Target}"` |
| `<adjective>_<entity>_id` | `"{Source} has {adjective} {Target}"` |

For non-FK columns:

| Column-name pattern | Generated reading |
|---|---|
| `<noun>_at` (timestamp) | `"{Entity} was {noun} at {DateTime}"` |
| `<noun>_date` | `"{Entity} has {noun} {Date}"` |
| `is_<noun>` (boolean) | `"{Entity} is {noun}"` (unary fact type) |
| Default | `"{Entity} has <noun> {ValueType}"` |

These are heuristics for *initial* readings. The user may rewrite them in Step 9d (treated as a user-supplied edit, not a new constraint).

**Self-referential role naming:**

When a table has an FK pointing at itself, the two roles need distinct names. Heuristic:
- Referencing-side role: derived from the FK column name. `parent_id` → `parent`; `manager_id` → `manager`; `previous_id` → `previous`.
- Referenced-side role: derived from the table name. `EMPLOYEES` → `employee`.

Result: fact type `"{Employee} reports to {Employee}"` with roles `[{role_name: employee}, {role_name: manager}]`.

**Edge cases:**
- **Multi-column FK** (composite FK referencing a composite PK): emit as a single binary fact type with the referenced entity, BUT mark `provenance.warning: "composite-fk"` so the constraint lift in Step 4 knows to emit a join-style mandatory rather than per-column.
- **Self-FK on a junction table:** rare but real (e.g., a `MERGE` table linking two `ACCOUNT` rows). Emit as binary fact type on the source entity type with explicit role names.
- **Same FK column referenced by two tables:** treat as polymorphism candidate. Out of v0.1 scope; emit a `provenance.warning: "polymorphic-fk-candidate"`.

## Step 4 — Lift explicit constraints

**Input:** Steps 1–3 output.

**Output:** YAML constraints with `source: explicit, status: confirmed` and full `provenance` blocks.

**Lift catalog:**

| DDL element | Emitted constraint(s) |
|---|---|
| PK (single column) | Internal UC, `preferred: true`, on the PK role. Mandatory on the PK role (PKs are NOT NULL by definition). |
| PK (composite, on a non-junction entity) | External UC, `scope: external, preferred: true`, across the binary fact types for each PK column. Mandatory on each role. |
| PK (composite, on a junction entity that's been promoted to objectified or pure m:n) | Internal UC `preferred: true` spanning the involved roles. |
| UNIQUE (single column) | Internal UC, `preferred: false`. |
| UNIQUE (composite) | External UC, `scope: external, preferred: false`. |
| NOT NULL | Mandatory on the corresponding role. (Reinforced if also implied by FK or PK; emit single entry, not duplicates.) |
| FK | Mandatory on the FK side of the binary fact type. (The fact type itself was emitted in Step 3; this step adds the constraint.) |
| CHECK `col IN ('v1', 'v2', ...)` | Object-type or role value constraint, `allowed: [v1, v2, ...]`. |
| CHECK `col BETWEEN x AND y` | Value constraint, `range: { min: x, max: y, min_inclusive: true, max_inclusive: true }`. |
| CHECK `col >= x` / `col <= y` (single bound) | Value constraint, `range: { min: x }` or `range: { max: y }`. |
| CHECK `col >= x AND col <= y` | Same as `BETWEEN`. |
| CHECK `colA <op> colB` (same-table column comparison) | Inline value-comparison constraint. |
| CHECK with `OR` of disjoint ranges | Multi-range value constraint, `ranges: [...]`. |
| CHECK that is parseable but doesn't fit the above | `type: textual`, `formal_language: natural`, `expression` = raw clause. |
| Unparseable CHECK | Skip; record `provenance.warning: "unparseable-check"`. Emit a `# NOTE:` warning in the model output. |

**Default values** are not constraints. Recorded in `provenance.column_default` for traceability; no constraint emitted.

**Edge cases:**
- **CHECK that references multiple tables (rare; trigger-like):** out of v0.1 scope. Emit as `type: textual`.
- **CHECK with subquery:** out of v0.1 scope. Emit as `type: textual` with the raw clause.
- **Generated columns:** treat the column as derived. Emit the corresponding fact type with `derivation: derived` and `derivation_rule:` set to the generation expression. Stretch goal — v0.1 emits as a regular column with `provenance.warning: "generated-column"`.
- **Snowflake's `MASKING POLICY` and similar:** out of v0.1 scope.

## Step 5 — Probe samples

**Input:** Step 4 output + the live data source.

**Output:** additional constraints with `source: sample`. Status follows the promotion rule below.

**Mechanics:** see [probing-strategies.md](probing-strategies.md) for the full per-probe SQL and decision rules.

**Promotion rule (from `phase1-srp-workflow.md`, locked):**

| Input kind | Status of probe-derived constraint |
|---|---|
| Live SQL, saturated probe, sample size ≥ 1000 | `confirmed` |
| Live SQL, unsaturated probe or sample size < 1000 | `proposed` |
| DDL-only or CSV input | (probes skipped; not applicable) |

**Probe budget:** 5 minutes total wall-clock, 100 probes maximum per SRP run. When exhausted, remaining probes skipped — target constraints stay `proposed` without sample provenance. See [probing-strategies.md](probing-strategies.md) "Probing budget" for details.

**Discipline reminder:** sample-detected uniqueness (column unique in data but no DDL UNIQUE) does **not** auto-emit a UC. Step 7 flags it as a candidate; Step 9c is the only confirmation path. The schema author may have allowed duplicates intentionally.

## Step 6 — Apply constraint inference

**Input:** Steps 1–5 output.

**Output:** additional constraints with `source: common-sense` (substeps 6a, 6b) or `source: llm-inferred` (substep 6c). All start at `status: proposed`.

**Substeps:**

### 6a — Library lookup

For each entity type, value type, and binary fact type, match against the typed library in [constraint-inference.md](constraint-inference.md). Examples:
- Object type `Money`/`Age`/`Count`/`Duration` → value constraint `range: { min: 0, min_inclusive: true }`.
- Object type `Date` → value constraint "must be a valid date".
- Binary fact type with reading containing "started"/"start" plus another fact type with "ended"/"end" on the same entity → value-comparison `start ≤ end`.

Each library entry records its assumptions (e.g., `Money` → assumes single currency). The `rationale` field on the proposed constraint surfaces these.

### 6b — Ring-pattern matching

For every binary fact type with both roles on the same object type (or related supertypes), match the role-name pattern against the ring library:

| Reading / role-name pattern | Proposed ring constraints |
|---|---|
| Reading contains "parent of"/"parent-of" | `acyclic`, `asymmetric`, `irreflexive` |
| Reading contains "married to"/"married-to" | `symmetric`, `irreflexive`, with a separate functional UC under monogamy assumption |
| Reading contains "precedes"/"supersedes"/"comes before" | `acyclic`, `transitive` |
| Reading contains "contains"/"part of" | `acyclic`, `asymmetric` |
| Reading contains "reports to"/"manages" | `acyclic`, `asymmetric`, `irreflexive` |
| Otherwise | nothing — punt to LLM (6c) |

Each matched pattern emits multiple `ring` entries (one per variant) per the multi-variant policy in [representation-format.md](representation-format.md).

### 6c — LLM tier

For object types, value types, and fact types not covered by the library, ask the LLM tier to propose constraints from world knowledge.

**LLM proposal contract:** every LLM-proposed constraint must include:
- `provenance.rationale_world_fact`: the world-fact citation (non-empty string).
- A clear `rationale` field surfacing the reasoning in user-facing language.

Without these, the proposal is rejected at emission. This discipline is the only defense against hallucination.

**Bounded scope (v0.1):** LLM tier proposes only the following constraint types:
- Value (range and enumeration where library missed)
- Ring (when the pattern doesn't match library)
- Subset / exclusion (cross-fact-type)
- Mandatory / mandatory-disjunctive
- Frequency (rare; usually requires domain context)

**Out of LLM scope (v0.1):** subtype-partition (Step 7's job), uniqueness (DDL/sample only), cardinality (user-supplied only), textual (user-supplied only).

### 6d — LLM spot-check (Guided mode only, opt-in)

Surface just the Step 6c LLM-tier proposals to the user. Library and ring proposals (6a, 6b) are NOT surfaced here — they're reviewed in context at Step 9b.

The user can:
- Mark obvious hallucinations as `rejected` immediately (move to `rejected_proposals`).
- Defer all decisions to Step 9b (skip the spot-check entirely).

Survivors continue with `status: proposed` into Steps 7 / 8.

In One-shot mode, 6d is skipped entirely.

The substep is opt-in within Guided. Claude prompts:

> *I have N LLM-proposed constraints with their rationales. Want to spot-check them now (mark obvious hallucinations as rejected) or defer all decisions to Step 9?*

If the user picks "defer", everything stays `proposed` and continues unchanged.

### 6e — Verbalize all surviving proposals

Render Step 6 outputs (surviving 6a, 6b, 6c) in CNL and store as input to Step 8. No user interaction; this is a preparation substep.

**Risks of the inference layer (recall from SKILL.md):**
- Cultural/legal variation — library entries flag their assumptions.
- Hallucination at the LLM tier — the `rationale_world_fact` discipline is the defense.
- Stale common sense — library entries need periodic review.
- Over-constraining narrows models silently — leave a clean reject path.

## Step 7 — Detect schema antipatterns

**Input:** Steps 1–6 output.

**Output:** antipattern flags attached to relevant entries via `provenance.warning: <code>`. No constraints emitted directly here; flags drive the user's Step 9c decision.

**Mechanics:** the catalog of detection signals and resolution defaults is in [antipattern-catalog.md](antipattern-catalog.md). Step 7 walks the YAML and applies each detection rule. Flags are codes; the catalog is the lookup.

**Discipline:**
- Antipatterns are **flagged, never silently corrected.** The user resolves at Step 9c.
- Detection is **conservative** — false negatives are preferred over false positives. TPC-H runs should produce zero antipattern flags.
- Sample-driven uniqueness candidates and missing-FK candidates do **NOT** auto-emit constraints. They flag for user confirmation only.

## Step 8 — Verbalize the recovered model

**Input:** Steps 1–7 output.

**Output:** human-readable verbalization saved to `<schema>.verbalization.txt`.

**Mechanics:** apply the patterns in [verbalization-patterns.md](verbalization-patterns.md) to render every model element in CNL. Output structure:
1. Header (schema, source, timestamp).
2. Object types section (one paragraph per object type).
3. Fact types section (one paragraph per fact type, including its inline constraints).
4. Top-level constraints section.
5. Antipattern flags section (call-outs).
6. Rejected proposals section (appendix; default scope = confirmed + proposed only, but full appendix readable at the end).

The verbalization is the primary review surface for non-PyRel stakeholders. Reading it should be sufficient to validate or challenge the model without seeing the YAML or the original schema.

**Phase 3 deferred-question default — verbalization detail level:** confirmed + proposed constraints in the main body; rejected proposals in an appendix at the end. User can ask for "appendix only" if they want a leaner main body.

## Step 9 — Capture user decisions and additions

**Input:** Steps 1–8 output.

**Output:** finalized YAML — proposals confirmed/rejected, user-supplied constraints added, modality labels applied.

**Substeps:**

### 9a — Review the verbalization

Claude presents the Step 8 verbalization to the user. The user reads, takes notes, asks clarifying questions. No commitments yet.

### 9b — Confirm/reject Step 6 proposals

Claude walks through the proposals from Step 6 (excluding any already rejected at Step 6d). The user accepts, rejects, or defers each.

**Phase 3 deferred-question default — batching policy:** auto-batch when ≥ 5 proposals in a single category (e.g., "I have 12 ring-constraint proposals; here they are with rationales — confirm all / reject all / decide individually"). Below 5, go one-by-one.

The user can defer any single decision; deferred items stay `proposed` (still reviewable post-hoc by editing the YAML).

### 9c — Resolve antipattern ambiguities

For each Step 7 antipattern flag, Claude presents the catalog's default resolution and asks the user to confirm or override. See [antipattern-catalog.md](antipattern-catalog.md) for the per-antipattern resolution menus.

### 9d — User-supplied constraints

Claude prompts:

> *Are there constraints you know but the system missed? Examples: "each project has exactly one manager", "every order with status='SHIPPED' has a non-null shipped_at".*

**Phase 3 deferred-question default — UX:** free-form natural-language input. The user writes the rule; Claude paraphrases back to the structured form for confirmation, then emits the YAML entry with `source: user-supplied, status: confirmed`.

If the user's natural-language description is ambiguous, Claude asks one clarifying question. If still ambiguous after one round, emit as `type: textual` rather than guessing the structured form.

### 9e — Modality labelling

For every confirmed constraint with `source ∈ {common-sense, sample, llm-inferred, user-supplied}`, ask the user: alethic or deontic?

Defaults:
- `source: explicit` → automatically `alethic` (DDL-derived constraints are by definition alethic — the database enforces them).
- All others → user labels at this substep. If skipped, default is `alethic` with a `# REVIEW MODALITY` flag carried into the PyRel output.

### 9f — Commit

Write the finalized YAML to `model.orm.yaml`. Move rejected proposals to `rejected_proposals`. Validate against the rules in [representation-format.md](representation-format.md) before write.

**Mode behavior:**

| Substep | Guided mode | One-shot mode |
|---|---|---|
| 9a | User reads verbalization | Skipped (verbalization still emitted to the file) |
| 9b | Interactive (auto-batch ≥ 5) | Library-tier auto-confirms; LLM-tier and `proposed` sample stay `proposed` |
| 9c | Interactive | Catalog default resolutions applied silently; flags remain |
| 9d | Interactive (free-form input) | Skipped |
| 9e | Interactive | `explicit` → `alethic`; everything else → `alethic` + `# REVIEW MODALITY` flag |
| 9f | Standard write | Standard write |

## Step 10 — Translate to PyRel

**Input:** finalized YAML from Step 9f.

**Output:** `model.py` containing the PyRel translation.

**Mechanics:** apply the four-tier rules from [orm-to-pyrel.md](orm-to-pyrel.md) to each YAML entry.

**Output structure:**
1. Header comment with strict-mode reminder (`implicit_properties: false` recommendation per `rai-pyrel-coding`).
2. Imports from `relationalai.semantics`.
3. `model = Model(...)` declaration.
4. Concept declarations (object types).
5. Property and Relationship declarations (binary fact types, by multiplicity).
6. Subtype `define...where` rules.
7. `model.require()` calls (verbose-tier constraints: ring, frequency, external UC, value-comparison, set-comparison).
8. `# DEONTIC NOTE:` comments for deontic constraints.
9. `# NOTE:` comments for textual / FORML 2 constraints.
10. `# REVIEW MODALITY` and `# REVIEW PROPOSAL` flags carried over from One-shot mode (when applicable).

**No user interaction.** Step 10 is fully deterministic given the finalized YAML.

## Phase 3 deferred-question defaults (recap)

The following defaults were deferred from Phase 1.6's lock and are set here:

1. **Step 5 sample-size cap:** 10,000 rows; minimum for confirmed promotion = 1,000. Distinct-count saturation = unchanged across last 1,000 rows of sample.
2. **Step 5 timeout:** 60s per probe, 5min total budget per SRP run.
3. **Step 5 NULL-rate threshold for mandatory inference:** < 0.1%.
4. **Step 6c LLM bounds:** value (range/enum), ring, subset/exclusion, mandatory(-disjunctive), frequency. Excludes uniqueness, cardinality, subtype-partition, textual.
5. **Step 8 verbalization detail level:** confirmed + proposed in main body; rejected in appendix.
6. **Step 9b batching policy:** auto-batch when ≥ 5 proposals per category; one-by-one below.
7. **Step 9d user-supplied UX:** free-form input with paraphrase-back confirmation; one clarifying-question round; emit as `textual` if still ambiguous.

These can be tuned during Phase 4 evals or post-Activity-2. Recording them here makes the SRP reproducible across sessions.

## Worked walkthrough — small example

A 4-table schema illustrates Steps 1–10 end-to-end. Tables:

```sql
CREATE TABLE CUSTOMER (
  CUSTOMER_ID INTEGER PRIMARY KEY,
  EMAIL VARCHAR(200) NOT NULL UNIQUE,
  TIER VARCHAR(10) NOT NULL CHECK (TIER IN ('BRONZE', 'SILVER', 'GOLD'))
);

CREATE TABLE ORDERS (
  ORDER_ID INTEGER PRIMARY KEY,
  CUSTOMER_ID INTEGER NOT NULL REFERENCES CUSTOMER(CUSTOMER_ID),
  STATUS VARCHAR(20) NOT NULL,
  PLACED_AT TIMESTAMP NOT NULL,
  TOTAL_AMOUNT DECIMAL(10,2) NOT NULL CHECK (TOTAL_AMOUNT >= 0)
);

CREATE TABLE PRODUCT (
  PRODUCT_ID INTEGER PRIMARY KEY,
  NAME VARCHAR(200) NOT NULL,
  UNIT_PRICE DECIMAL(10,2) NOT NULL CHECK (UNIT_PRICE > 0)
);

CREATE TABLE ORDER_ITEM (
  ORDER_ID INTEGER NOT NULL REFERENCES ORDERS(ORDER_ID),
  PRODUCT_ID INTEGER NOT NULL REFERENCES PRODUCT(PRODUCT_ID),
  QUANTITY INTEGER NOT NULL CHECK (QUANTITY > 0),
  PRIMARY KEY (ORDER_ID, PRODUCT_ID)
);
```

**Step 1** — inventory: 4 tables, columns, PKs, FKs, NOT NULLs, CHECKs lifted from INFORMATION_SCHEMA.

**Step 2** — object types:
- `customer` (entity, popular reference, `value_type: CustomerId`)
- `orders` (entity, popular reference, `value_type: OrdersId`)
- `product` (entity, popular reference, `value_type: ProductId`)
- `order_item` (entity, external reference — composite PK, all-FK, has extra column `QUANTITY` → flagged as **objectified-binary candidate**)
- Lazy value types: `CustomerId`, `OrdersId`, `ProductId`, `String`, `Integer`, `DateTime`, `Number(10,2)`

**Step 3** — fact types:
- `customer_has_email`: `"{Customer} has email {String}"`
- `customer_has_tier`: `"{Customer} has tier {String}"` (CHECK in Step 4 will narrow `String` to enum `{BRONZE, SILVER, GOLD}`)
- `orders_placed_by_customer`: `"{Orders} placed by {Customer}"`
- `orders_has_status`: `"{Orders} has status {String}"`
- `orders_placed_at`: `"{Orders} was placed at {DateTime}"`
- `orders_has_total`: `"{Orders} has total {Number}"`
- `product_has_name`: `"{Product} has name {String}"`
- `product_has_unit_price`: `"{Product} has unit-price {Number}"`
- `order_item_for_orders`: `"{OrderItem} for {Orders}"` (objectification candidate; underlying binary)
- `order_item_for_product`: `"{OrderItem} for {Product}"`
- `order_item_has_quantity`: `"{OrderItem} has quantity {Integer}"`

**Step 4** — explicit constraints:
- PK constraints → preferred internal UCs on each entity's identifying role.
- `EMAIL UNIQUE` → internal UC on `customer_has_email[customer]`.
- `NOT NULL` on every column → mandatory on the corresponding role.
- `FK ORDERS.CUSTOMER_ID → CUSTOMER` → mandatory on `orders_placed_by_customer[orders]`.
- `CHECK TIER IN (...)` → object-type value constraint on a new value type `Tier` (split from `String`).
- `CHECK TOTAL_AMOUNT >= 0`, `UNIT_PRICE > 0`, `QUANTITY > 0` → value range constraints on `Number`/`Integer`.

**Step 5** — sample probes:
- `STATUS` distinct-value enumeration: probe finds `{'PENDING', 'PAID', 'SHIPPED', 'DELIVERED'}`. Propose value enum on `String` for that role.
- NULL rates probed; all NOT NULLs reinforced by sample.

**Step 6** — inference:
- 6a library: `Money` library entry matches `UNIT_PRICE` and `TOTAL_AMOUNT` (via the `Number(10,2)` + name pattern); the existing CHECK already pins `>= 0` and `> 0`, so library proposes nothing new.
- 6b ring: no self-referential fact types in this schema; nothing emitted.
- 6c LLM: proposes a value-comparison constraint "`orders.placed_at` should not be in the future" — declined at 6d as too speculative for this domain (the user's call).

**Step 7** — antipatterns:
- `STATUS` flagged as encoded-enum-in-VARCHAR (already promoted to enum at Step 5; flag confirms the catalog match).
- `ORDER_ITEM` flagged as objectified-binary candidate (composite PK all-FK + `QUANTITY` extra column).
- No denormalized addresses, no TYPE-column subtype, no missing FKs.

**Step 8** — verbalization rendered.

**Step 9** — user decisions:
- 9b: confirms the STATUS enum (auto-confirmed via sample saturation).
- 9c: confirms `OrderItem` as objectified entity (default resolution).
- 9d: adds *"each Customer has at least one Order"* (mandatory-disjunctive on customer) — surface as `source: user-supplied`.
- 9e: labels everything `alethic` except the *"customer must have one order"* rule which they label `deontic` (it's a business goal, not a hard fact).
- 9f: commits.

**Step 10** — PyRel translation:
- `Customer = model.Concept("Customer", identify_by={"id": Integer})`
- `Customer.email = model.Property(...)` with `Customer.email` enforced unique by FD
- `Tier = model.Enum("Tier", ["BRONZE", "SILVER", "GOLD"])`
- `OrderItem = model.Concept("OrderItem", identify_by={"order": Orders, "product": Product})`
- `model.require(Orders.total_amount >= 0)` etc. for value ranges
- `# DEONTIC NOTE: each Customer should have at least one Order.`

The walkthrough mirrors the synthetic schema's shape at smaller scale; full synthetic walkthrough lives in the example files when Phase 3 examples are written.
