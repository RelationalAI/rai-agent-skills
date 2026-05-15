# Verbalization Patterns

Halpin-style controlled natural language (CNL) templates for rendering an ORM 2 model as readable text. Used in SRP **Step 6e** (verbalize Step 6 proposals) and **Step 8** (verbalize the full recovered model). The verbalization is the primary review surface for non-PyRel stakeholders.

Output goes to `<schema>.verbalization.txt`.

Load at SRP Steps 6e and 8.

Cross-references:
- Per-constraint vocabulary → [constraint-reference.md](constraint-reference.md)
- YAML structure being verbalized → [representation-format.md](representation-format.md)
- Workflow placement → [srp-workflow.md](srp-workflow.md)

## Halpin-grounded design

ORM 2's CNL principle: every model element should have a natural-language reading that a domain expert can validate **without seeing the diagram or the YAML**. The verbalization is the model's externalised meaning.

This skill follows that principle. Each verbalization pattern below is grounded in Halpin's published examples, paraphrased to avoid copyright reproduction (S12). Examples are ours.

Discipline:
- One sentence per claim. Compound sentences obscure where the burden of validation lies.
- Use object-type names verbatim from the YAML (PascalCase). The user matches them against their domain vocabulary.
- Provenance prefixes on inferred / proposed constraints — the user knows immediately which claims are schema-derived and which are inferred.

## Verbalization document structure

The full Step 8 verbalization has the following sections in order:

```
=== Header ===
Model from <schema>, introspected at <timestamp> via <kind>.

=== Object Types ===
<one paragraph per object type>

=== Fact Types ===
<one paragraph per fact type, including its inline constraints>

=== Top-level Constraints ===
<one paragraph per top-level constraint>

=== Antipattern Flags ===
<call-outs grouped by code>

=== Appendix: Rejected Proposals ===
<list with reasons>
```

Each section is a sequence of CNL paragraphs. Provenance prefixes mark non-explicit constraints. Empty sections are omitted.

## Object types

### Entity type with popular reference

Pattern:
> *{Name} is identified by {value-type-name}.*

Example:
> *Customer is identified by CustomerId.*

When the value type is not a primitive but another named entity (rare with `popular`):
> *{Name} is identified by its {value-type-name}.*

### Entity type with unit-based reference

Pattern:
> *{Name} is identified by a value in {unit} ({measure-type}).*

Example:
> *Height is identified by a value in cm (Length).*

### Entity type with general reference

Pattern:
> *{Name} is identified by {value-type-name}.* (same as popular)

Halpin distinguishes `general` from `popular` notationally; verbalization is the same since both abbreviate an injective binary fact type.

### Entity type with external (composite) reference

Pattern:
> *{Name} is identified by the combination of {role-1-CNL} and {role-2-CNL} ... .*

Example:
> *Enrolment is identified by the combination of student enrolment and course enrolment.*

The role CNLs come from the fact types referenced by the external UC.

### Value type

Pattern:
> *{Name} is a value of type {primitive}.*

Example:
> *EmailAddress is a value of type String.*

For `Number(p, s)`:
> *{Name} is a value of type Number with precision {p} and scale {s}.*

### Subtype

Pattern (with inherited reference / dashed arrow):
> *{Name} is a kind of {Supertype}, inheriting the reference of {Supertype}. {Derivation rule, if derived}.*

Pattern (with own reference / solid arrow):
> *{Name} is a kind of {Supertype}, identified by {value-type-name}. {Derivation rule, if derived}.*

Examples:
> *PhysicalProduct is a kind of Product, inheriting the reference of Product. Each PhysicalProduct is a Product whose Type is 'PHYSICAL'.*
> *Student is a kind of Person, identified by StudentNumber.*

### Independent flag

Append to any object type's verbalization when `independent: true`:
> *(Independent — instances may exist without playing any elementary fact roles.)*

## Fact types

### Binary fact type

Pattern (uniqueness on left role — 1:n):
> *{Reading-with-roles-instantiated-as-types}. Each {Left} {predicate-CNL} at most one {Right}.*

Example (`Customer has email EmailAddress` with UC on customer):
> *Customer has email EmailAddress. Each Customer has at most one EmailAddress.*

Pattern (m:n — spanning UC):
> *{Reading}. Each combination of {Left} and {Right} occurs at most once.*

Example:
> *OrderItem tagged with Tag. Each combination of OrderItem and Tag occurs at most once.*

Pattern (1:1 — UCs on both roles):
> *{Reading}. Each {Left} {predicate-CNL} at most one {Right}, and each {Right} {reverse-predicate-CNL} at most one {Left}.*

Example:
> *Person has nationalId NationalId. Each Person has at most one NationalId, and each NationalId is held by at most one Person.*

### Mandatory enrichment

When a role has a mandatory constraint, add an "at least one" sentence:
> *Each {ObjectType} has at least one {OtherType}.*

Combined with uniqueness:
> *Each Customer has exactly one EmailAddress.* (mandatory + uniqueness on the Customer role)

### Unary fact type

Pattern:
> *Each {Type} {predicate}.* — when mandatory.
> *Some {Type}s {predicate}.* — when not mandatory.

Examples:
> *Some Persons smoke.*
> *Each Order is rush-priority.* (when mandatory + Boolean-flag-style unary)

### Ternary+ fact type

Pattern:
> *{Reading-with-all-roles-instantiated}. Each combination of {role-tuple} {uniqueness-clause}.*

Example (with UC on `(person, sport)`):
> *Person played Sport for Country. Each combination of Person and Sport played one Country.*

### Self-referential fact type

Pattern:
> *{Reading} (with two roles on {Type}, named {role-name-1} and {role-name-2}).*

Example:
> *Person is parent of Person (with two roles on Person, named parent and child).*

The role-name annotation is essential — without it, the user can't tell which role is which.

### Objectified fact type

Pattern:
> *{Reading}. This is objectified as {Junction-name}{, which is independent if so}.*

Example:
> *Student enrolled in Course. This is objectified as Enrolment, which is independent (an Enrolment may exist before the grade is recorded).*

### Derived fact type

Pattern:
> *{Reading}. This fact type is derived: {derivation-rule}.*

Example:
> *Person speaks NrLanguages languages. This fact type is derived: For each Person, nrLanguages = count(languageSpoken).*

## Constraints — by type

Each constraint's CNL pattern is also documented in [constraint-reference.md](constraint-reference.md). The patterns below are the canonical Step 8 verbalizations.

### Internal uniqueness

Inline within the fact type's paragraph (already covered by the fact-type pattern above).

### External uniqueness

Pattern:
> *Each combination of {role-1-CNL} and {role-2-CNL} ... identifies at most one {EntityType}.*

When `preferred: true`, append:
> *This is the preferred reference scheme of {EntityType}.*

### Mandatory

Inline with the fact-type paragraph (already covered).

### Mandatory-disjunctive

Pattern:
> *Each {ObjectType} {predicate-1} or {predicate-2}{ or … }.*

Example:
> *Each Visitor has Passport or has DriverLicence.*

### Object-type value (enumeration)

Pattern:
> *{ObjectType} must take one of: {v1}, {v2}, …, {vn}.*

Example:
> *Status must take one of: 'PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'.*

### Object-type value (range)

Pattern (closed):
> *{ObjectType} must be between {min} and {max} (inclusive of {min}, {inclusive/exclusive} of {max}).*

Pattern (open above):
> *{ObjectType} must be at least {min}.*

Pattern (open below):
> *{ObjectType} must be at most {max}.*

Pattern (multi-range):
> *{ObjectType} must be in one of the ranges: {range-1}, {range-2}, ….*

### Subset

Pattern:
> *If {predicate-subset}, then {predicate-superset}.*

Example:
> *If a Person smokes, then that Person is cancer-prone.*

### Equality

Pattern:
> *A {ObjectType} {predicate-a} if and only if it {predicate-b}.*

Example:
> *A Patient has systolic-BP recorded if and only if it has diastolic-BP recorded.*

### Exclusion

Pattern:
> *No {ObjectType} {predicate-a} and {predicate-b}.*

Example:
> *No Person is married and widowed.*

### Exclusive-or

Pattern:
> *Each {ObjectType} either {predicate-a} or {predicate-b} (not both).*

For partition:
> *Each {ObjectType} is exactly one of: {Subtype-1}, {Subtype-2}, …, {Subtype-n}.*

### Frequency (internal)

Pattern (range):
> *Each {Reading-with-roles-fixed} appears at least {min} and at most {max} times.*

Pattern (exact):
> *Each {Reading-with-roles-fixed} appears exactly {n} times.*

Example:
> *Each panel that includes an expert includes at least 4 and at most 7 experts.*

### Frequency (external)

Pattern:
> *Each combination of {role-1-CNL}, {role-2-CNL} occurs at most {max} times.*

### Ring constraints

One sentence per variant (per the multi-variant policy).

| Variant | CNL pattern |
|---|---|
| `irreflexive` | *No {ObjectType} {predicate} itself.* |
| `asymmetric` | *If {a} {predicate} {b}, then not {b} {predicate} {a}.* |
| `intransitive` | *If {a} {predicate} {b} and {b} {predicate} {c}, then not {a} {predicate} {c}.* |
| `antisymmetric` | *If {a} {predicate} {b} and {b} {predicate} {a}, then {a} = {b}.* |
| `acyclic` | *{Reading} is acyclic — no chain of {predicate-instances} returns to its start.* |
| `symmetric` | *{a} {predicate} {b} if and only if {b} {predicate} {a}.* |
| `transitive` | *If {a} {predicate} {b} and {b} {predicate} {c}, then {a} {predicate} {c}.* |
| `purely-reflexive` | *Every {ObjectType} {predicate} itself.* |
| `reflexive` | *Every {ObjectType} {predicate} itself (other pairings allowed).* |

For combined variants (e.g., `acyclic + irreflexive + asymmetric`), emit three separate sentences — one per ring-constraint entry in the YAML.

### Value-comparison

Pattern:
> *For each {ObjectType}, {role-a-CNL} is {comparison-natural} {role-b-CNL}.*

Comparison natural-language:
- `<` → "less than"
- `<=` → "less than or equal to"
- `=` → "equal to"
- `>=` → "greater than or equal to"
- `>` → "greater than"
- `!=` → "not equal to" (v0.1 extension; see constraint-reference.md)

Example:
> *For each Project, end-date is greater than or equal to start-date.*

### Cardinality (object)

Pattern (exact):
> *There is exactly one {ObjectType}.*

Pattern (upper):
> *There are at most {max} {ObjectType}s.*

Pattern (lower):
> *There are at least {min} {ObjectType}s.*

Pattern (range):
> *There are at least {min} and at most {max} {ObjectType}s.*

### Cardinality (role)

Pattern:
> *At most {max} {ObjectType} plays the role of {role-name-natural}.*

### Subtype-partition

Patterns:

Full partition:
> *Every {Supertype} is exactly one of: {Subtype-1}, …, {Subtype-n}.*

Exclusive only:
> *No {Supertype} is more than one of: {Subtype-1}, …, {Subtype-n}.*

Exhaustive only:
> *Every {Supertype} is at least one of: {Subtype-1}, …, {Subtype-n}.*

### Textual

Pattern:
> *[textual constraint] {expression}*

The bracketed prefix marks that this is a textual constraint, not a structured constraint type.

## Provenance prefixes

Every constraint sentence is prefixed with its provenance, so the user knows whether it's schema-derived or inferred:

| Source | Status | Prefix |
|---|---|---|
| `explicit` | `confirmed` | `[from PK]`, `[from UNIQUE]`, `[from NOT NULL]`, `[from CHECK]`, `[from FK]`, `[from UNIQUE INDEX]` |
| `sample` | `confirmed` | `[from sample data, confirmed]` |
| `sample` | `proposed` | `[from sample data, proposed]` |
| `common-sense` | `confirmed` | `[from common-sense library, confirmed]` |
| `common-sense` | `proposed` | `[from common-sense library, proposed]` |
| `llm-inferred` | `confirmed` | `[from LLM inference, confirmed]` |
| `llm-inferred` | `proposed` | `[from LLM inference, proposed]` |
| `user-supplied` | `confirmed` | `[user-supplied]` |

Examples:
> *[from PK] Each Customer is identified by exactly one CustomerId.*
> *[from CHECK] Status must take one of: 'PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'.*
> *[from common-sense library, proposed] Parenthood is acyclic.*
> *[from LLM inference, proposed] Returns must reference orders that have been delivered.*
> *[user-supplied] Each Project has exactly one project manager.*

When a constraint is `modality: deontic`, append `(deontic — should rule, possibly violated)`:

> *[user-supplied, deontic — should rule, possibly violated] Each Customer should have at least one Order.*

## Antipattern call-outs

Antipattern flags appear in their own section (after Top-level Constraints, before Appendix). Pattern:

> *⚠ {AntipatternCode} on {entity-or-fact-type}: {one-line description}. Default resolution: {default-resolution}. {Detail.}*

Examples:
> *⚠ denormalized-address on Customer: address columns address_line1, line2, city, state, zip, country appear denormalized. Default resolution: extract Address value type. Matched columns: ADDRESS_LINE1, ADDRESS_LINE2, CITY, STATE, ZIP, COUNTRY.*
> *⚠ ambiguous-junction-with-extras on OrderItem: composite all-FK PK with extra column QUANTITY. Default resolution: treat as objectified entity (alternative: pure m:n binary).*
> *⚠ encoded-enum-in-varchar on Order.STATUS: low-cardinality VARCHAR with enum-style suffix; sample yielded 5 distinct values. Default resolution: promote to value enum.*

The user reads the call-outs at Step 9c and confirms / overrides each.

## Appendix: rejected proposals

Pattern:
> *{Original-CNL-of-the-rejected-constraint}. Rejected on {date}: {reason}.*

Example:
> *Order precedence is acyclic. Rejected on 2026-05-04: domain explicitly allows reissues that point back to predecessors.*

The appendix lets future SRP runs read what was already rejected, and lets reviewers see "we considered this and decided no."

## Worked snippet

For the small `Customer / Order / Product / OrderItem` example from [srp-workflow.md](srp-workflow.md), the verbalization output reads (excerpts):

```
=== Object Types ===

Customer is identified by CustomerId.
[user-supplied] Customer is identified by exactly one CustomerId.

Order is identified by OrderId. (Independent — instances may exist without playing any elementary fact roles.)

OrderItem is identified by the combination of order role and product role of the
order_item_for_orders and order_item_for_product fact types.

Product is identified by ProductId.

Tier is a value of type String.

=== Fact Types ===

Customer has email EmailAddress.
[from UNIQUE] Each Customer has at most one EmailAddress.
[from PK / NOT NULL] Each Customer has at least one EmailAddress.
                 → therefore each Customer has exactly one EmailAddress.

Customer has tier Tier.
[from CHECK] Tier must take one of: 'BRONZE', 'SILVER', 'GOLD'.

Order placed by Customer.
[from PK] Each Order placed by exactly one Customer.
[from FK + NOT NULL] Each Order is placed by at least one Customer.
                  → therefore each Order is placed by exactly one Customer.

Order has total Number.
[from CHECK] total must be at least 0.

OrderItem for Order. This is objectified as OrderItem.
[from PK] Each combination of OrderItem.order and OrderItem.product is unique.

OrderItem has quantity Integer.
[from CHECK] quantity must be at least 1.

=== Top-level Constraints ===

[user-supplied, deontic — should rule, possibly violated]
Each Customer should have at least one Order.

=== Antipattern Flags ===

⚠ ambiguous-junction-with-extras on OrderItem: composite all-FK PK with extra
  column QUANTITY. Default resolution: treat as objectified entity (alternative:
  pure m:n binary).

⚠ encoded-enum-in-varchar on Order.STATUS: sample yielded 5 distinct values
  ('PENDING', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'). Default resolution:
  promote to value enum.

=== Appendix: Rejected Proposals ===

(none)
```

The verbalization is the user's primary review surface — they can read it without understanding YAML or PyRel and validate every claim against domain knowledge.

## What this format does NOT cover in v0.1

- **Localization.** English only. Halpin's CNL extends to other languages; v0.1 doesn't.
- **Verbalization editing as part of Step 9d.** When the user wants to rewrite a reading (e.g., `"Order placed by Customer"` → `"Order is from Customer"`), they edit the YAML's `reading:` field directly. v1.5 may add a guided rewrite path.
- **Diagram rendering.** No ASCII / SVG diagram generation. Verbalization is text-only. v1.5+ stretch.
- **FORML 2 verbalization.** Textual constraints render as the raw `expression`; no formal-language translation.
