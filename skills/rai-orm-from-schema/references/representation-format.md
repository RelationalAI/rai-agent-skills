# YAML Representation Format

The full schema spec for `model.orm.yaml`. Every other reference in this skill cites this file for YAML shape. Load when emitting, validating, or interpreting any part of the YAML.

Grounded in Halpin's ORM 2 vocabulary — the goal is models a Halpin-trained reader recognises as orthodox.

## Top-level structure

```yaml
version: 1                                    # mandatory; first field. Schema version of this format.

source:                                       # how the model was derived; metadata for audit
  kind: sql                                   # sql | ddl-file | csv | text-conversation
  dialect: snowflake                          # snowflake | postgres | mysql | oracle | sqlite (sql/ddl-file only)
  connection_id: prod_warehouse               # optional, for sql kind
  scope:                                      # what was introspected
    database: SALES_DW
    schema: PUBLIC
    tables: ["*"]                             # or explicit list
  introspected_at: "2026-05-04T14:32:00Z"
  confidence: standard                        # standard | low (low = degraded; e.g., CSV-only inputs)
  mode: guided                                # guided | one-shot — recorded from SRP Step 0

object_types:                                 # list of entity / value types
  - …

fact_types:                                   # list of fact types with their inline constraints
  - …

constraints:                                  # model-level (cross-fact-type or object-type-scope) constraints
  - …

rejected_proposals:                           # constraints the user rejected during Step 9b; preserved so future runs don't re-propose
  - …

deontic_notes:                                # optional textual notes that don't fit any constraint type
  - text: "…"
    rationale: "…"
```

**Two design rules govern every YAML:**

1. **Single source of truth per construct.** Every fact type has exactly one entry in `fact_types`; every constraint exactly one entry (inline or top-level by the scope rule below). No duplication.
2. **Constraint scope decides placement.** Constraints scoped to a single fact type live inline in `fact_types[].constraints`. Constraints that span fact types or are scoped to an object type live top-level in `constraints`.

| Constraint type | Scope | Placement |
|---|---|---|
| `uniqueness` (internal UC) | One fact type | inline |
| `mandatory` (single role) | One fact type | inline |
| `value` (role-scope) | One fact type | inline |
| `ring` | One fact type | inline |
| `frequency` scope=internal | One fact type | inline |
| `value-comparison` (intra-fact-type) | One fact type | inline |
| `uniqueness` scope=external | Multiple fact types | top-level |
| `mandatory-disjunctive` | Multiple fact types | top-level |
| `value` (object-type-scope) | Object type | top-level |
| `value` (role-scope hybrid: `object_type` is a primitive + `role_ref` narrows to a specific role) | One specific role of one fact type | top-level (kept with the other range proposals for grouping) |
| `subset`, `equality`, `exclusion`, `exclusive-or` | Multiple fact types | top-level |
| `frequency` scope=external | Multiple fact types | top-level |
| `value-comparison` (cross-fact-type) | Multiple fact types | top-level |
| `cardinality` (object or role) | Object type / role | top-level |
| `subtype-partition` | Object type | top-level |
| `textual` | Anywhere | top-level |

## Object types

```yaml
object_types:
  # Entity type with popular reference (single-column PK)
  - id: customer
    name: Customer
    kind: entity                              # entity | value
    reference:
      mode: popular                           # popular | unit-based | general | external
      value_type: CustomerId                  # the identifying value type (id of a value-kind object_type)
    independent: false                        # "!" marker — instances may exist without playing roles
    provenance:
      origin: table-with-pk                   # table-with-pk | junction-table | no-pk-detected | inferred-value-type
      table: PUBLIC.CUSTOMERS
      pk_column: CUSTOMER_ID

  # Entity type with unit-based reference
  - id: height
    name: Height
    kind: entity
    reference:
      mode: unit-based
      unit: cm                                # the unit string Halpin shows in the diagram
      measure_type: Length                    # the measurement category

  # Entity type with general reference (referenced by an injective binary)
  - id: book
    name: Book
    kind: entity
    reference:
      mode: general
      value_type: ISBN

  # Entity type identified externally (composite key)
  - id: enrolment
    name: Enrolment
    kind: entity
    reference:
      mode: external                          # the external UC lives in top-level constraints
    provenance:
      origin: junction-table
      table: PUBLIC.ENROLMENTS

  # Value type (self-identifying primitive)
  - id: customer_id
    name: CustomerId
    kind: value
    primitive: Integer                        # String | Integer | Float | Number | Date | DateTime | Boolean | Binary
    # For Number with scale > 0:
    # primitive: Number
    # precision: 10
    # scale: 2

  # Subtype with derivation rule
  - id: male_person
    name: MalePerson
    kind: entity
    subtype_of: [person]                      # list — multi-supertype allowed
    inherits_reference: true                  # true = dashed arrow (inherits supertype's identifier); false = solid arrow (own identifier)
    derivation: derived                       # asserted | derived | semiderived
    derivation_rule: "Each MalePerson is a Person who is of Gender 'M'."
    storage: computed                         # stored | computed (default)
```

### Field-level rules

- **`id`**: required, lowercase, snake_case, unique within `object_types`. Used by fact types and constraints to reference this object type.
- **`name`**: required, PascalCase, the user-facing name. Shown in verbalizations.
- **`kind`**: required.
- **`reference`**: required for `kind: entity`; absent for `kind: value`. The four `mode` values map directly to Halpin's reference-mode notations:
  - `popular` — Halpin's `Country(.code)` shorthand for an injective binary fact type with a primitive value type.
  - `unit-based` — `Height(cm:)` / `Salary(USD: Money)`. Carries `unit` and `measure_type`.
  - `general` — `Book(ISBN)`. Carries `value_type` only.
  - `external` — composite identifier; the actual external UC lives in top-level `constraints`.
- **`primitive`**: required for `kind: value`. One of `String | Integer | Float | Number | Date | DateTime | Boolean | Binary`. For `Number` with non-zero scale, `precision` and `scale` are mandatory.
- **`independent`**: optional, default `false`. `true` means the object type's instances may exist without playing any elementary fact roles (Halpin's `!` marker).
- **`subtype_of`**: optional list. Empty / absent means the object type is not a subtype.
- **`inherits_reference`**: required when `subtype_of` is non-empty. Maps to Halpin's solid (false) vs dashed (true) subtype arrow.
- **`derivation`**: optional, defaults to `asserted`. When `derived` or `semiderived`, `derivation_rule` is required.
- **`storage`**: optional, defaults to `computed` for derived. Set to `stored` for materialized derivations (Halpin's `**`/`++` notation).

## Fact types

```yaml
fact_types:
  # Binary, functional (1:n via uniqueness on one role)
  - id: customer_has_email
    reading: "{Customer} has email {EmailAddress}"
    inverse_reading: "is email of"             # optional; corresponds to Halpin's reverse reading
    roles:
      - object_type: customer                 # references object_types[].id
        role_name: customer                   # default = camelCase of object type
      - object_type: email_address
        role_name: email
    constraints:
      - type: uniqueness
        roles: [customer]
        preferred: false
        source: explicit
        status: confirmed
        rationale: "UNIQUE(EMAIL) on PUBLIC.CUSTOMERS."
        provenance: { table: PUBLIC.CUSTOMERS, column: EMAIL, constraint: UQ_CUSTOMERS_EMAIL }
      - type: mandatory
        role: customer
        source: explicit
        status: confirmed
        provenance: { table: PUBLIC.CUSTOMERS, column: EMAIL, nullable: false }

  # Binary m:n (junction table, not objectified)
  - id: order_item_tagged_with
    reading: "{OrderItem} tagged with {Tag}"
    roles:
      - { object_type: order_item, role_name: orderItem }
      - { object_type: tag, role_name: tag }
    constraints:
      - type: uniqueness
        roles: [orderItem, tag]               # spanning UC — neither alone unique
        preferred: true
        source: explicit
        status: confirmed
        provenance: { table: PUBLIC.ORDER_ITEM_TAG, pk: PK_ORDER_ITEM_TAG }

  # Objectified binary (junction table with extra attributes)
  - id: student_enrolled_in_course
    reading: "{Student} enrolled in {Course}"
    roles:
      - { object_type: student, role_name: student }
      - { object_type: course, role_name: course }
    objectified_as: enrolment                 # references object_types[].id
    objectification_independent: true         # Halpin's "!" — Enrolment may exist before grades recorded
    constraints:
      - type: uniqueness
        roles: [student, course]
        preferred: true
        source: explicit
        status: confirmed

  # Self-referential — explicit role names mandatory
  - id: person_parent_of_person
    reading: "{Person} is parent of {Person}"
    roles:
      - { object_type: person, role_name: parent }
      - { object_type: person, role_name: child }
    constraints:
      - type: uniqueness
        roles: [child]
        source: common-sense
        status: proposed
        rationale: "Biological mother — at most one per child."
      - type: ring
        variant: acyclic
        source: common-sense
        status: proposed
        modality: alethic

  # Unary
  - id: person_smokes
    reading: "{Person} smokes"
    arity: 1                                  # explicit; default = len(roles)
    roles:
      - { object_type: person, role_name: person }

  # Ternary with functional dependency
  - id: person_played_sport_for_country
    reading: "{Person} played {Sport} for {Country}"
    roles:
      - { object_type: person, role_name: person }
      - { object_type: sport, role_name: sport }
      - { object_type: country, role_name: country }
    constraints:
      - type: uniqueness
        roles: [person, sport]                # functional: each (person, sport) → exactly one country
        source: explicit
        status: confirmed

  # Derived fact type
  - id: person_speaks_n_languages
    reading: "{Person} speaks {NrLanguages} languages"
    roles:
      - { object_type: person, role_name: person }
      - { object_type: nr_languages, role_name: nrLanguages }
    derivation: derived
    derivation_rule: "For each Person, nrLanguages = count(languageSpoken)."
    storage: computed
```

### Field-level rules

- **`id`**: required, lowercase, snake_case, unique within `fact_types`. Used by cross-fact-type role references in top-level constraints.
- **`reading`**: required. Halpin-style mixfix template. Object placeholders `{Type}` map to roles by position. The text between placeholders is the verbalization predicate.
- **`inverse_reading`**: optional. The reverse-direction reading; Halpin notates these with `/` separators in the diagram.
- **`roles`**: required, ordered list. Order corresponds to placeholder order in `reading`.
  - **`object_type`**: required, must reference an existing `object_types[].id`.
  - **`role_name`**: required when the same object type appears in multiple roles of the same fact type (self-referential, multi-occurrence). Otherwise optional; default = camelCase of the referenced object type's name.
- **`arity`**: optional. Defaults to `len(roles)`. Setting it explicitly is a cross-check that the reading and roles agree.
- **`objectified_as`**: optional. References an `object_types[].id`. The referenced object type must have `reference.mode: external`.
- **`objectification_independent`**: optional, default `false`. Maps to Halpin's `!` on the objectification.
- **`derivation` / `derivation_rule` / `storage`**: same semantics as object types.
- **`constraints`**: optional list. Only constraint types from the inline set in the placement table above. Cross-fact-type constraints belong top-level.

### Self-referential and same-type fact types

Whenever the same object type appears in two or more roles of a single fact type, all such roles **must** carry explicit `role_name`. The role names disambiguate the roles in:

- The `reading` template (placeholder positions must agree with role order).
- Constraint `roles:` lists.
- Cross-fact-type role references.
- PyRel translation (named refs, e.g., `{Person:parent}`).

Default role names (`person` for `Person`) collide when the type repeats — emitter must derive distinct names from semantics (`parent`/`child`, `manager`/`employee`, `stock1`/`stock2`).

## Constraints — top-level (cross-fact-type and object-type scope)

```yaml
constraints:
  # External uniqueness (composite identifier across binary fact types)
  - type: uniqueness
    scope: external
    role_refs:
      - { fact_type: state_in_country, role: state }
      - { fact_type: state_has_code, role: code }
    preferred: true                           # double-bar — this composite is the entity's preferred identifier
    source: explicit
    status: confirmed
    rationale: "Composite PK (COUNTRY_ID, STATE_CODE) on PUBLIC.STATES."
    provenance: { table: PUBLIC.STATES, pk: PK_STATES }

  # Mandatory-disjunctive (inclusive-or)
  - type: mandatory-disjunctive
    role_refs:
      - { fact_type: visitor_has_passport, role: visitor }
      - { fact_type: visitor_has_license, role: visitor }
    source: common-sense
    status: proposed
    modality: alethic
    rationale: "Visitors must present at least one identity document."

  # Object-type value constraint (enumeration)
  - type: value
    object_type: gender
    allowed: ['M', 'F']
    source: explicit
    status: confirmed
    provenance: { table: PUBLIC.PEOPLE, column: GENDER, check: "GENDER IN ('M','F')" }

  # Object-type value constraint (single range)
  - type: value
    object_type: age
    range:
      min: 0
      min_inclusive: true
      max_inclusive: false                    # max omitted → open-ended above
    source: common-sense
    status: proposed
    modality: alethic

  # Object-type value constraint (multiple disjoint ranges)
  - type: value
    object_type: latitude_offset
    ranges:                                   # list form for multiple disjoint ranges
      - { min: -100, max: -20, min_inclusive: true, max_inclusive: true }
      - { min:   40, max: 100, min_inclusive: true, max_inclusive: true }
    source: user-supplied
    status: confirmed

  # Role-scope value constraint (hybrid `object_type` + `role_ref` form)
  # Use when a generic primitive value type (e.g., Integer) appears in multiple
  # roles that each want different bounds. The `object_type` names the primitive
  # being constrained; `role_ref` narrows the scope to a specific role.
  - type: value
    object_type: integer                      # the primitive being constrained
    role_ref: { fact_type: inventory_quantity_on_hand, role: quantityOnHand }
    range: { min: 0, min_inclusive: true }
    source: common-sense
    status: proposed
    modality: alethic

  # Subset
  - type: subset
    subset_role_seq:
      - { fact_type: person_smokes, role: person }
    superset_role_seq:
      - { fact_type: person_is_cancer_prone, role: person }
    source: common-sense
    status: proposed
    modality: alethic

  # Equality
  - type: equality
    role_seq_a:
      - { fact_type: patient_has_systolic_bp, role: patient }
    role_seq_b:
      - { fact_type: patient_has_diastolic_bp, role: patient }
    source: common-sense
    status: proposed

  # Exclusion
  - type: exclusion
    role_seq_a:
      - { fact_type: person_is_married, role: person }
    role_seq_b:
      - { fact_type: person_is_widowed, role: person }
    source: common-sense
    status: proposed
    modality: alethic

  # Exclusive-or — partition over a population (inclusive-or + exclusion)
  - type: exclusive-or
    role_seqs:
      - [{ fact_type: academic_is_male, role: academic }]
      - [{ fact_type: academic_is_female, role: academic }]
    source: common-sense
    status: proposed
    modality: alethic

  # External frequency
  - type: frequency
    scope: external
    role_refs:
      - { fact_type: student_enrolled_in_course, role: student }
      - { fact_type: student_enrolled_in_course, role: course }
    bound: { min: 1, max: 2 }
    source: user-supplied
    status: confirmed

  # Value-comparison across fact types
  - type: value-comparison
    operator: ">="                            # < | <= | = | >= | >
    role_a: { fact_type: project_started, role: date }
    role_b: { fact_type: project_ended, role: date }
    source: common-sense
    status: proposed
    modality: alethic

  # Object cardinality
  - type: cardinality
    scope: object
    object_type: president
    bound: { min: 1, max: 1 }
    source: user-supplied
    status: confirmed

  # Role cardinality
  - type: cardinality
    scope: role
    role_ref: { fact_type: politician_is_president, role: politician }
    bound: { max: 1 }
    source: user-supplied
    status: confirmed

  # Subtype partition (xor + exhaustive)
  - type: subtype-partition
    supertype: product
    subtypes: [physical_product, digital_product, subscription_product]
    exclusive: true
    exhaustive: true
    source: common-sense                      # inferred from TYPE column
    status: proposed
    provenance: { table: PUBLIC.PRODUCTS, column: TYPE }

  # Textual / FORML 2 constraint (catch-all)
  - type: textual
    expression: "Each Employee who has Rank 'NonExec' uses at most one CompanyCar."
    formal_language: natural                  # natural | forml2
    formal_expression: null                   # optional FORML 2 syntax if available
    source: user-supplied
    status: confirmed
    modality: alethic
```

### Cross-fact-type role references

The `{ fact_type: <id>, role: <role_name> }` tuple is the canonical cross-reference. Both fields are required. The combination must resolve — emitters and validators check that the referenced `fact_type.id` exists and that one of its roles has the matching `role_name`.

For self-referential or multi-occurrence fact types where the role name disambiguates two roles of the same object type, the role reference must use the disambiguating name (not the object-type name).

## Provenance system — every constraint carries

Every constraint entry — inline or top-level — carries the same six metadata fields. The `provenance` block's shape varies by `source`.

```yaml
- type: <constraint-type>
  # constraint-specific fields …
  source: explicit                            # explicit | sample | common-sense | llm-inferred | user-supplied
  status: confirmed                           # proposed | confirmed | rejected
  modality: alethic                           # alethic | deontic. Default = alethic if omitted.
  rationale: "Free-text explanation."         # optional for explicit; required for non-explicit sources
  provenance: { … }                           # source-specific structured pointer (see below)
```

### `source: explicit`

```yaml
provenance:
  table: PUBLIC.CUSTOMERS                     # required
  column: EMAIL                               # required when constraint scopes a single column
  columns: [COUNTRY_ID, STATE_CODE]           # required when constraint scopes multiple columns; mutually exclusive with column
  constraint: UQ_CUSTOMERS_EMAIL              # optional — DDL constraint name when present
  constraint_type: UNIQUE                     # PK | UNIQUE | NOT_NULL | CHECK | FK
  fk:                                         # required when constraint_type=FK
    references_table: PUBLIC.COUNTRIES
    references_columns: [COUNTRY_ID]
  check_expression: "AGE >= 0"                # required when constraint_type=CHECK
  ddl_line: 47                                # optional — line number in DDL file when known
```

`rationale` is optional for `explicit` because the provenance block tells the story.

### `source: sample`

```yaml
provenance:
  sample_query: "SELECT DISTINCT STATUS FROM PUBLIC.ORDERS"
  sample_size: 1245                           # row count probed
  saturation: true                            # did distinct-value count saturate (i.e., probe is conclusive)?
  observed_values: ['PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED']  # for value enumeration
  observed_range: { min: 0, max: 9999 }      # for numeric range
  null_rate: 0.00                             # for mandatory inference
```

Status promotion rules:
- Live SQL input + `saturation: true` + sample size ≥ threshold (default 1000) → `confirmed`.
- DDL-only or CSV input → stays `proposed`.

### `source: common-sense`

```yaml
provenance:
  library_entry: parent-of-self-referential   # entry id in references/constraint-inference.md
  matched_pattern: "self-referential binary with role names matching parent-of vocabulary"
  assumptions: ["Single-jurisdiction parental relationship; not adoptive."]   # surfaced in rationale
```

`rationale` is required and should restate the matched pattern in user-facing language.

### `source: llm-inferred`

```yaml
provenance:
  llm_prompt_id: returns-must-reference-delivered-orders
  rationale_world_fact: "Returns presuppose receipt; only DELIVERED orders have receipts."   # the world-fact citation, mandatory
  reviewed_at_step_6d: true                   # was this proposal surfaced during the LLM spot-check?
```

The world-fact citation is mandatory. Without it, the proposal is rejected at emission time (per SRP Step 6c discipline).

### `source: user-supplied`

```yaml
provenance:
  added_at_step: 9d                           # when in the SRP (or CSDP Step 7d) the user added this
  user_note: "Confirmed verbally during review on 2026-05-04."  # optional
```

## Text-first extensions (text-conversation source.kind)

When `source.kind: text-conversation` — used by the `rai-orm-from-text` skill — `provenance` blocks may include additional fields that trace each construct back to a dialogue turn. These fields are optional in the format but expected when the source kind is text-conversation:

```yaml
provenance:
  csdp_step: 1                                # which CSDP step emitted this (0-7, plus 7a-7f)
  dialogue_turn: 4                            # turn number in the conversation
  user_quote: "Each Movie has one canonical title in our catalog."   # the user's actual words
```

The `user_quote` field is recommended for `source: explicit` and `source: user-supplied` constraints; it makes the YAML auditable in dialogue terms.

Fact types in text-first YAMLs may also carry a `sample_population:` array — Halpin-style sample fact instances confirmed by the user at CSDP Step 1:

```yaml
fact_types:
  - id: person_born_in_country
    reading: "{Person} was born in {Country}"
    roles: [{ object_type: person, role_name: person }, { object_type: country, role_name: country }]
    sample_population:                        # 5-20 sample facts; keys are role names
      - { person: "John", country: "Australia" }
      - { person: "Mary", country: "Greece" }
    provenance: { csdp_step: 1, dialogue_turn: 4 }
```

The sample_population is rendered in the verbalization (see [verbalization-patterns.md](verbalization-patterns.md)) but is *not* used to auto-confirm sample-derived constraints (Halpin populations are too small for that — they stay `proposed` until user confirmation at CSDP Step 7b).

The `source.kind: text-conversation` mode also supports an `artifacts:` list for files the user provided (forms, requirements docs, sample data):

```yaml
source:
  kind: text-conversation
  session_id: csdp_2026_05_14_movies          # optional dialogue identifier
  artifacts:                                  # optional pointers to user-provided files
    - "user-prompt.md"
    - "sample-form.png"
  started_at: "2026-05-14T10:00:00Z"
  confidence: standard                        # always 'standard' for text-conversation
  mode: guided
```

## `rejected_proposals` — kept so future runs don't re-propose

Same shape as a regular constraint, but with `status: rejected` and two added fields:

```yaml
rejected_proposals:
  - type: ring
    fact_type: order_precedes_order
    variant: acyclic
    source: common-sense
    status: rejected
    rationale: "Library entry: precedes-acyclic."
    rejection_reason: "Domain explicitly allows reissues that point back to predecessors."
    rejected_at: "2026-05-04"
```

A future SRP run on the same schema reads `rejected_proposals` first and excludes those proposals from re-emission. The exclusion match is `(type, fact_type or object_type, variant or roles)` — exact rematch, not fuzzy.

## Validation rules

A YAML is valid when **all** of the following hold:

### Structural

1. `version: 1` is the first key.
2. `source` is present with at least `kind` and `introspected_at`.
3. `object_types`, `fact_types`, `constraints` are all present (may be empty lists).

### Identifier integrity

4. Every `object_types[].id` is unique.
5. Every `fact_types[].id` is unique.
6. Every `roles[].object_type` reference resolves to an existing `object_types[].id`.
7. Every cross-fact-type role reference (`{ fact_type, role }` form) resolves: `fact_type` exists; the named `role_name` exists on that fact type's `roles` list.
8. Every `subtype_of` reference resolves.
9. Every `subtype-partition.subtypes` and `supertype` reference resolves and the supertype is consistent with the subtypes' `subtype_of`.
10. Every `objectified_as` reference resolves to an entity-kind object type with `reference.mode: external`.

### Reading / role agreement

11. The number of `{Type}` placeholders in `reading` equals `len(roles)`.
12. The order of placeholders in `reading` corresponds to the order in `roles`.
13. When the same object type appears in multiple roles, all such roles carry distinct `role_name` values.

### Constraint placement

14. Every inline constraint (in `fact_types[].constraints`) has a type from the inline-allowed set in the placement table.
15. Every top-level constraint (in `constraints`) has a type from the top-level set.

### Provenance

16. Every constraint has `source` and `status`.
17. `rationale` is present when `source ∈ {sample, common-sense, llm-inferred, user-supplied}`.
18. `provenance` shape matches `source` per the per-source schemas above.
19. `source: llm-inferred` constraints have `provenance.rationale_world_fact` set (non-empty).

### Reference modes

20. `reference.mode: popular` requires `value_type`.
21. `reference.mode: unit-based` requires `unit` and `measure_type`.
22. `reference.mode: general` requires `value_type`.
23. `reference.mode: external` requires a corresponding `uniqueness scope: external` in top-level `constraints` whose `role_refs` reference the entity's identifying fact types.

### Status / source consistency

24. `source: explicit` constraints have `status: confirmed` (DDL-derived constraints aren't proposed for review).
25. `source: user-supplied` constraints have `status: confirmed` (user added them deliberately).
26. `source: common-sense | llm-inferred` start at `status: proposed`. They may transition to `confirmed` (Step 9b accept) or `rejected` (move to `rejected_proposals`).
27. `source: sample` is `confirmed` only when input is live SQL and the probe saturated; otherwise `proposed`.

A validator that fails any of these rules emits a structured error pointing at the offending entry. The validator is markdown-documented for v0.1; Phase 4+ stretch goal S4 introduces a Python validator if the rules grow burdensome to apply by hand.

## What this format does NOT capture in v0.1

- ~~**Role-level value constraints.**~~ (Resolved in v0.1 via the *role-scope value-constraint hybrid form*, documented below.)
- **Multi-language readings.** English only.
- **Visual / layout metadata.** No coordinates, colors, diagram positions. The YAML is the conceptual model, not a diagram.
- **Multi-rule derivation chain validation.** v0.1 captures derivation rules per construct as opaque strings. Chain consistency (rule A depends on rule B's output) is not validated.
- **FORML 2 parsing.** Textual constraints are stored verbatim; no formal-language interpretation.

These are documented gaps, not bugs. Each escalates to a v1.5+ scope item if real schemas force the issue.
