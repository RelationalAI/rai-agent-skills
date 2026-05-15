# Constraint Inference

The typed library + ring-pattern matcher + LLM-tier proposer rules used in SRP **Step 6**. Library entries are markdown tables; the matchers are deterministic; the LLM tier is bounded by an explicit contract.

Load at SRP Step 6.

Cross-references:
- Per-constraint vocabulary (what each constraint type *means* and translates to) → [constraint-reference.md](constraint-reference.md)
- YAML output shape (where library hits land) → [representation-format.md](representation-format.md), per-source provenance section
- Ring constraints catalog → [constraint-reference.md](constraint-reference.md)

## Three tiers, one workflow

Step 6 runs three deterministic passes (6a, 6b, 6c) followed by an opt-in user spot-check (6d, Guided only) and a verbalize-back substep (6e):

| Substep | Source | Auto-emit? | User review |
|---|---|---|---|
| 6a — Library lookup | `common-sense` | yes | Step 9b (in context) |
| 6b — Ring patterns | `common-sense` | yes | Step 9b (in context) |
| 6c — LLM tier | `llm-inferred` | yes (with mandatory rationale) | Step 6d (opt-in early filter) + Step 9b (final) |
| 6d — Spot-check | (filters 6c) | n/a | Guided only, opt-in |
| 6e — Verbalize | n/a | n/a | feeds Step 8 |

All three deterministic passes set `status: proposed`. Step 9b is the final confirmation path; 6d narrows just the LLM batch.

## 6a — Typed library

Library entries match against object types (by `name`) and value-type primitives (by `primitive`). Each entry records:
- **`id`** — stable slug identifier used by `provenance.library_entry` on emitted constraints. Stays the same across library refactors.
- **Match key** — what to look for in the YAML (case-insensitive substring on object-type / value-type / role name).
- **Proposed constraint** — what to emit if the match hits.
- **Assumption** — what the entry assumes about domain semantics; surfaces in `rationale`.

The library lives below as a markdown table. v0.1 entries cover universal-knowledge facts. Domain-specific or organization-specific rules go in a separate `domain_library.yaml` (v1.5; not yet shipped — see `notes/TODO.md` item #6).

### Object-type entries (numeric / measurable domains)

| `id` | Match key (object type name, case-insensitive contains) | Proposed constraint | Assumption |
|---|---|---|---|
| `money-positive` | `money`, `amount`, `price`, `cost`, `salary`, `revenue`, `fee`, `payment` | Value range, `min: 0, min_inclusive: true` | Single currency; non-negative monetary value |
| `age-range` | `age` | Value range, `min: 0, max: 150` (range widened) | Human age in years |
| `count-non-negative` | `count`, `quantity`, `qty` | Value range, `min: 0, min_inclusive: true` | Counts are non-negative |
| `duration-non-negative` | `duration`, `seconds`, `minutes`, `hours`, `days` | Value range, `min: 0, min_inclusive: true` | Durations are non-negative |
| `percent-0-100` | `percent`, `percentage`, `pct` | Value range, `min: 0, max: 100` | 0–100 percentage scale (not 0–1 fraction) |
| `discount-fraction` | `discount` | Value range, `min: 0, max: 1, min_inclusive: true, max_inclusive: true` | Fractional discount (0..1); promotions tracked as percent use `percent-0-100` instead |
| `rate-non-negative` | `rate`, `ratio` | Value range, `min: 0, min_inclusive: true` (no upper) | Non-negative rate |
| `score-non-negative` | `score` | Value range, `min: 0, min_inclusive: true` | Non-negative score; tighter bounds need user input |
| `temperature-no-constraint` | `temperature` | (no range proposed) | Negative temperatures are valid; library punts |
| `physical-measurement-non-negative` | `weight`, `mass`, `length`, `width`, `height`, `distance`, `volume` | Value range, `min: 0, min_inclusive: true` (no upper) | Physical measurements are non-negative |
| `latitude-range` | `latitude` | Value range, `min: -90, max: 90` | Standard geographic latitude |
| `longitude-range` | `longitude` | Value range, `min: -180, max: 180` | Standard geographic longitude |
| `year-range` | `year` | Value range, `min: 1900, max: 2100` (widened) | Reasonable contemporary year range |

### Object-type entries (temporal domains)

| `id` | Match key | Proposed constraint | Assumption |
|---|---|---|---|
| `date-contemporary` | `date`, `birth_date`, `dob` | Value range, `min: 1900-01-01` (open above) | Reasonable contemporary date range |
| `audit-timestamp-past` | `created_at`, `updated_at`, `modified_at`, `deleted_at` | Value comparison vs. NOW: `<= NOW()` | Audit timestamps are not in the future |
| `temporal-interval-start-end` | Pair: `*_started_at`/`*_start_date` and `*_ended_at`/`*_end_date` on same entity | Value-comparison constraint, `start <= end` | Common temporal-interval semantics |
| `temporal-lifecycle-placed-shipped` | Pair: `placed_at` / `order_date` and `shipped_at` on same entity | Value-comparison constraint, `placed <= shipped` | Lifecycle ordering |
| `temporal-lifecycle-shipped-delivered` | Pair: `shipped_at` / `ship_date` and `delivered_at` / `receipt_date` on same entity | Value-comparison constraint, `shipped <= delivered` | Lifecycle ordering |
| `temporal-validity-interval` | Pair: `valid_from` and `valid_to` on same entity | Value-comparison constraint, `from <= to` | Validity-interval semantics |
| `temporal-lifecycle-birth-hire` | Pair: `birth_date` and `hire_date` on same entity | Value-comparison constraint, `birth <= hire` | Employees are born before they are hired |

### Value-type entries (primitive-keyed)

| `id` | Primitive | Constraint emitted (only if other library entries don't already constrain) | Assumption |
|---|---|---|---|
| `date-valid` | `Date` | Textual constraint: "must be a valid date" | Format conformance; downstream tooling validates |
| `datetime-valid` | `DateTime` | Same as Date | Format conformance |
| (none) | `Integer` | (none — too generic) | n/a |
| (none) | `String` | (none — too generic) | n/a |

### Special-name entries

| `id` | Match key | Proposed constraint | Assumption |
|---|---|---|---|
| `email-format` | `email` | Textual constraint: "must be a valid email address" | RFC 5322 conformance |
| `email-uniqueness` | `email` | Uniqueness constraint on the value role | Email addresses are universally unique per person |
| `url-format` | `url` | Textual constraint: "must be a valid URL" | RFC 3986 conformance |
| `phone-format` | `phone`, `phone_number` | Textual constraint: "must be a valid phone number" | E.164-style |
| `country-code-iso3166` | `country_code` | Value enumeration, `allowed: <ISO 3166-1 alpha-2 list>` | ISO 3166-1 alpha-2 (~250 codes) |
| `currency-code-iso4217` | `currency_code` | Value enumeration, `allowed: <ISO 4217 list>` | ISO 4217 |
| `language-code-iso639` | `language_code` | Value enumeration, `allowed: <ISO 639-1 list>` | ISO 639-1 |
| (alias) | `iso_country`, `iso_currency`, `iso_language` | Same as the corresponding `*_code` row | Same |

The ISO enumeration lists are large; emit as a textual constraint with the rule name (`"must be ISO 4217"`) rather than expanding the enum inline. The user's review at 9b confirms the rule, not the list.

### Library entry shape on the wire

When a library hit fires, the emitted constraint carries:

```yaml
- type: <constraint-type>
  # constraint-specific fields
  source: common-sense
  status: proposed
  modality: alethic
  rationale: "<library-entry assumption restated for the user>"
  provenance:
    library_entry: <match-key-id>
    matched_pattern: "<what the matcher saw, in user-facing language>"
    assumptions: ["<assumption-1>", "<assumption-2>"]
```

Example — `Customer.email` matches the `email` library entry:

```yaml
constraints:
  - type: textual
    expression: "Customer email must be a valid email address."
    formal_language: natural
    source: common-sense
    status: proposed
    modality: alethic
    rationale: "Library entry 'email' — RFC 5322 conformance assumed for any object type or property named 'email'."
    provenance:
      library_entry: email
      matched_pattern: "object type / value type with name containing 'email'"
      assumptions: ["RFC 5322 conformance"]
```

### Library hit ordering

When multiple entries match the same target, emit one constraint per matching entry — they're independent proposals. Example: a column named `total_amount` matches both `total` (no entry) and `amount` (Money entry); the latter fires.

When two entries propose the same constraint shape (e.g., two range entries on the same object type), de-duplicate by keeping the more specific one (narrower range) and dropping the broader.

### Adding new library entries

The library is a markdown table — additions are diff-reviewable. Each new entry must include:
- A match key with case-insensitive substring semantics.
- A concrete constraint shape.
- An explicit assumption that goes into `rationale`.

Domain-specific entries (e.g., "in our org, Employees report to exactly one Manager") go in `domain_library.yaml`, not here. v1.5 scope.

## 6b — Ring-pattern matching

For every binary fact type with both roles on the same object type (or related supertypes), match the reading and role names against the ring library:

| `id` | Reading-or-role-name pattern | Proposed ring variants | Assumption |
|---|---|---|---|
| `ring-parent-of` | `parent of` / `parent-of` / role names `parent` & `child` | `acyclic`, `asymmetric`, `irreflexive` | Biological / structural parenthood; not adoptive overlay |
| `ring-married-to` | `married to` / `married-to` / role names `husband` & `wife` or `spouse_a` & `spouse_b` | `symmetric`, `irreflexive` (and a separate functional UC under monogamy assumption) | Monogamous marriage |
| `ring-precedes` | `precedes` / `comes before` / `predecessor of` | `acyclic`, `transitive` | Strict-ordering semantics |
| `ring-supersedes` | `supersedes` | `acyclic`, `transitive` | Same as `precedes` |
| `ring-contains` | `contains` / `part of` / `contained by` | `acyclic`, `asymmetric` | Mereological containment |
| `ring-reports-to` | `reports to` / role names `manager` & `employee` | `acyclic`, `asymmetric`, `irreflexive` | Hierarchical management; circular reporting disallowed |
| `ring-manages` | `manages` / `supervises` | `acyclic`, `asymmetric`, `irreflexive` | Same as `reports to` (inverse direction) |
| `ring-transfer-from-to` | `transfers to` / role names `from` & `to` (with same-type both ends) | `irreflexive` (typically modelled as `value-comparison !=` per the format spec) | "Transfers" presuppose distinct endpoints |
| `ring-friend-of` | `is friend of` / `friend of` / `friends with` | `symmetric`, `irreflexive` | Friendship is symmetric (cultural assumption — flag in rationale) |
| `ring-sibling-of` | `is sibling of` / `sibling of` | `symmetric`, `irreflexive` | Sibling relation is symmetric |
| `ring-enemies` | `enemies` / `opponent of` | `symmetric`, `irreflexive` | Antagonism is symmetric (typically) |
| `ring-extends` | `extends` / `inherits from` / role names `parent_class` & `child_class` | `acyclic`, `asymmetric`, `irreflexive` | Inheritance hierarchies are DAGs |
| `ring-replies-to` | `replies to` (in messaging/threading) | `acyclic`, `asymmetric` | Reply chains form trees |

**Multi-variant policy:** each matched pattern emits **multiple `ring` entries**, one per variant. This keeps verbalization, translation, and review independent per variant.

**Provenance:**
```yaml
- type: ring
  variant: acyclic
  source: common-sense
  status: proposed
  modality: alethic
  rationale: "Self-referential 'parent_of' relation — parenthood is acyclic by structural assumption."
  provenance:
    library_entry: ring-parent-of
    matched_pattern: "self-referential binary fact type with parent/child role names"
    assumptions: ["Biological parenthood; not adoptive."]
```

**When the pattern doesn't match:** punt to LLM tier (6c). Don't propose ring constraints from the library if the reading is ambiguous; the LLM has a better chance with novel relationship vocabulary.

**Edge cases:**
- **Self-FK with no semantic name signal** (e.g., `parent_id` on a generic table): match against role names (`parent`/`child`) which Step 3's heuristics will have generated. Library still fires.
- **Self-FK on a junction table** (rare): library doesn't fire; punt to LLM.

## 6c — LLM tier

For object types, value types, and fact types not covered by 6a or 6b, ask the LLM to propose constraints from world knowledge.

### Bounded scope (v0.1)

The LLM tier proposes only the following constraint types:

| Constraint type | Example LLM proposal |
|---|---|
| Value (range or enum) | "RetailDiscount must be between 0 and 50 — most retail discounts cap at 50%" |
| Ring (when 6b didn't fire) | "FriendOf is intransitive — friend-of-friend is not always a friend" |
| Subset / exclusion (cross-fact-type) | "Returns must reference DELIVERED orders — receipts presuppose delivery" |
| Mandatory or mandatory-disjunctive | "Every customer must have either email or phone" |
| Frequency (rare) | "Each Order has 1–10 items typically; >10 is an outlier" |

**Out of LLM scope (v0.1):**
- Uniqueness — DDL or sample only.
- Cardinality (object/role) — user-supplied only.
- Subtype-partition — Step 7's job, not Step 6c.
- Textual — user-supplied only (LLM can't articulate rules outside the structured types).

### LLM proposal contract

Every LLM-proposed constraint must carry:
- `provenance.rationale_world_fact`: a non-empty string citing the world-knowledge fact that justifies the proposal.
- `rationale`: user-facing explanation (paraphrase of `rationale_world_fact`).
- `provenance.llm_prompt_id`: the internal prompt id that generated the proposal.

Without `rationale_world_fact`, the proposal is rejected at emission time — no exception. This discipline is the single defense against hallucination.

### Per-target prompt structure

For each object type / fact type / value type that survived 6a and 6b without library hits, the LLM is prompted with:

> *Object type: `<name>`, primitive: `<primitive-or-N/A>`, source table: `<table>`, comment: `<comment-or-empty>`.*
> *What world-knowledge constraints (range, enum, ring, subset, exclusion, mandatory, frequency) might apply?*
> *For each proposed constraint, cite the world fact that justifies it. If you cannot cite a world fact, do not propose.*

Targets without world-knowledge signal (e.g., generic value types like `String`, `Integer`) yield no proposals. That's the expected outcome for most targets — most schema elements need only library or ring proposals or none at all.

### Aggregation

LLM proposals are aggregated into a single batch per Step 6. Each proposal carries its own provenance. No deduplication across targets — the same constraint shape proposed for two different targets goes through twice.

### 6c output → 6d input

The aggregated batch is the input to Step 6d (Guided-mode opt-in spot-check). In One-shot mode, 6d is skipped and the batch passes straight to 6e for verbalization, then survives into Step 8.

## 6d — LLM spot-check (Guided only, opt-in)

Mechanics live in [srp-workflow.md](srp-workflow.md) Step 6d. From a constraint-inference perspective, the spot-check operates **only on Step 6c output** (LLM-tier proposals); library and ring proposals are not surfaced here.

The user can:
- Reject obvious hallucinations one by one.
- Reject all and defer the rest to Step 9b.
- Defer everything to Step 9b (skip the spot-check entirely).

Rejected proposals at 6d move to `rejected_proposals` immediately. Step 9b doesn't see them again.

## 6e — Verbalize all surviving proposals

Render every Step 6 output (surviving 6a, 6b, 6c) using the templates in [verbalization-patterns.md](verbalization-patterns.md). The verbalization is appended to the model's `verbalization.txt` (Step 8 final pass) and served to the user at Step 9b.

## Risks and how the design addresses them

| Risk | Defense |
|---|---|
| Cultural/legal variation (monogamy, calendar, currency assumptions) | Each library entry surfaces its assumption in `rationale`; user reviews at Step 9b |
| LLM hallucination | `rationale_world_fact` discipline; Step 6d opt-in spot-check; Step 9b final review |
| Stale library entries | Markdown-table form makes additions/edits diff-reviewable; library reviewed each release |
| Over-constraining | All Step 6 outputs are `proposed`; rejection path is one click in Guided, edit-the-YAML in One-shot |
| Schema-extracted constraints might still be wrong | Step 9b confirmation flow extends to confirmed-from-explicit when the user spots a surprise (downgrade path) |

## Future-extension hooks (not in v0.1)

These are the natural extension points. Each is preserved as a stretch goal in `notes/TODO.md`:

- **Domain-specific library** (`domain_library.yaml`, v1.5): per-deployment organization-policy rules. Same shape as the universal library; extra `source: domain-library` value. See TODO.md item #6.
- **Library entry deprecation marker:** flag entries that produced too many false positives across runs, so they downgrade to `propose with low confidence` or are removed.
- **Library entry confidence:** an optional `confidence: low | medium | high` field on each entry, surfaced in `rationale`. Not in v0.1; the library is currently uniform.
- **LLM tier broadening:** adding subtype-partition or cardinality once Step 7 / user-supplied paths are mature enough that LLM-driven proposals don't conflict.

None of these are in v0.1. The universal library + ring matcher + bounded LLM tier is the v0.1 surface.
