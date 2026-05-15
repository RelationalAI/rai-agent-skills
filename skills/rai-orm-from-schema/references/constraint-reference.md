# Constraint Reference

Per-constraint vocabulary. For each ORM 2 constraint type: a short description, the ORM 2 graphical signal it corresponds to (described in words — diagrams are not reproduced; see Halpin's published work for the visual reference), the YAML form, the controlled-natural-language (CNL) verbalization template, and the PyRel translation tier.

Cross-references:
- YAML structural detail → [representation-format.md](representation-format.md)
- CNL grammar overall → [verbalization-patterns.md](verbalization-patterns.md)
- PyRel tier mechanics → [orm-to-pyrel.md](orm-to-pyrel.md)

Load when handling any constraint type beyond the basics in SKILL.md.

## Quick reference

| Constraint type | Default modality | PyRel translation tier |
|---|---|---|
| Internal uniqueness | alethic | Mechanical (`Property` FD) |
| External uniqueness | alethic | Mechanical when single key column; `model.require` for composite |
| Mandatory | alethic | Mechanical (Property is single-valued) |
| Mandatory-disjunctive | alethic | `model.require` |
| Object-type value (enum) | alethic | Mechanical (`model.Enum`) |
| Object-type value (range) | alethic | `model.require` |
| Subset | alethic | `model.require` |
| Equality | alethic | `model.require` |
| Exclusion | alethic | `model.require` |
| Exclusive-or | alethic | `model.require` |
| Frequency (internal) | alethic | `model.require` (with `count(...).per(...)`) |
| Frequency (external) | alethic | `model.require` |
| Ring (any variant) | alethic | `model.require` |
| Value-comparison | alethic | `model.require` |
| Cardinality (object/role) | alethic | `model.require` |
| Subtype-partition | alethic | Heuristic (`extends` + `define...where`) for membership; `model.require` for exclusion/exhaustion |
| Textual (FORML 2 / natural) | alethic | Not translated — emit as `# NOTE:` comment |
| Any constraint flagged deontic | deontic | Not translated — emit as `# DEONTIC NOTE:` comment |

Modality is set by the user at SRP Step 9e. The default is `alethic`. The "Default modality" column above tells you which way to lean during proposal/draft; the user always has the final word.

## Internal uniqueness (UC)

Asserts that within a single fact type, each combination of objects in a designated role (or role sequence) appears at most once across the population.

**ORM 2 graphical signal:** a horizontal bar drawn across the role boxes covered by the UC. A double bar marks the *preferred* internal UC — the one that underlies the entity type's preferred reference scheme. A dotted line excludes a role from a spanning UC (rare).

**YAML form (inline):**
```yaml
constraints:
  - type: uniqueness
    roles: [<role_name_1>, <role_name_2>, …]    # role(s) covered by the bar
    preferred: false                            # double-bar?
    source: explicit | sample | common-sense | llm-inferred | user-supplied
    status: confirmed | proposed
```

For binaries the four standard patterns:

| Pattern | Roles covered | Reading semantics |
|---|---|---|
| 1:n (UC on left) | `[A]` | A is unique; each A pairs with at most one B |
| n:1 (UC on right) | `[B]` | B is unique; each B pairs with at most one A |
| m:n (spanning UC) | `[A, B]` | Combination unique; neither alone unique |
| 1:1 (two separate UCs) | one `[A]`, one `[B]` | Both sides unique |

For *n*-ary fact types (n>2), each UC covers at least n-1 roles.

**CNL verbalization template (per standard pattern):**
- 1:n: *"Each {Reading-with-A-fixed} involves at most one {B}."*
- n:1: *"Each {Reading-with-B-fixed} is from at most one {A}."*
- m:n: *"Each {A,B} pairing occurs at most once."*

**PyRel translation:**
- 1:n on a binary FK fact type → declare as `Property` (PyRel enforces the FD).
- m:n with spanning UC → declare as `Relationship`; the spanning UC is the relationship's combined identity.
- For composite UCs across n-ary fact types, emit the binding as a junction concept with `identify_by={…}` covering the unique roles.

## External uniqueness

Asserts that a tuple of objects drawn from roles across **multiple fact types** appears at most once across the joint population. Used for composite identifiers — entities identified by several binary fact types together rather than a single one.

**ORM 2 graphical signal:** a UC bar connected via dotted lines to one role on each of two or more separate fact types. Double bar marks the preferred external identifier.

**YAML form (top-level):**
```yaml
constraints:
  - type: uniqueness
    scope: external
    role_refs:
      - { fact_type: <ft_id_1>, role: <role_name> }
      - { fact_type: <ft_id_2>, role: <role_name> }
    preferred: true                             # is this the entity's preferred composite identifier?
    source: …
    status: …
```

**CNL verbalization template:**
*"Each combination of ({Role1 verbalised in its fact type}, {Role2 verbalised in its fact type}, …) identifies at most one {EntityType}."*

When `preferred: true`:
*"…and serves as the preferred reference scheme for {EntityType}."*

**PyRel translation:**
- When the external UC corresponds to a composite PK on a junction-shaped table → translate as `Concept(identify_by={"r1": Type1, "r2": Type2, ...})`. Mechanical tier.
- When the external UC spans true binary fact types and there is no junction concept → emit as `model.require(count(...).per(...) == 1)` with explanatory comment. `model.require` tier.

## Mandatory role

Asserts that every instance of the object type at one end of a role plays that role at least once.

**ORM 2 graphical signal:** a filled dot on the role connector at the end of the object type that must play the role.

**YAML form (inline):**
```yaml
constraints:
  - type: mandatory
    role: <role_name>
    source: …
    status: …
```

**CNL verbalization template:**
*"Each {ObjectType} {predicate-with-other-roles}."*

For a binary fact type *Customer has email EmailAddress* with mandatory on `customer`:
*"Each Customer has at least one EmailAddress."*

**PyRel translation:**
- A `Property` is single-valued by definition; if the property exists for an instance, mandatory is implicit.
- For non-Property cases (`Relationship`, mandatory on the value side of a fact type), use `model.require(count(<role>).per(<EntityType>) >= 1)`.
- `mandatory` lifted from `NOT NULL` always carries `source: explicit, status: confirmed`.

## Mandatory-disjunctive (inclusive-or)

Asserts that each instance of an object type plays at least one role from a set of two or more roles, possibly across different fact types.

**ORM 2 graphical signal:** a circled dot connecting the relevant roles. Adjacent or non-adjacent roles allowed.

**YAML form (top-level):**
```yaml
constraints:
  - type: mandatory-disjunctive
    role_refs:
      - { fact_type: <ft_id_1>, role: <role_name> }
      - { fact_type: <ft_id_2>, role: <role_name> }
    source: …
    status: …
```

**CNL verbalization template:**
*"Each {ObjectType} {predicate-1} OR {predicate-2} (or both)."*

Example:
*"Each Visitor has Passport or has DriverLicence."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require((Visitor.passport != None) | (Visitor.licence != None))
  ```
  Using PyRel's `|` boolean operator, NOT Python's `or`.

## Object-type value constraint (enumeration)

Restricts the allowed values of an object type to a finite enumerated set.

**ORM 2 graphical signal:** brace-enclosed list adjacent to the object type — `{'M', 'F'}`.

**YAML form (top-level):**
```yaml
constraints:
  - type: value
    object_type: <ot_id>
    allowed: ['v1', 'v2', …]
    source: …
    status: …
```

**CNL verbalization template:**
*"{ObjectType} must take one of: {v1}, {v2}, …."*

**PyRel translation:**
- Enumeration → promote the object type to `model.Enum`. Mechanical tier:
  ```python
  Gender = model.Enum("Gender", ["M", "F"])
  ```
- Recoverable from `CHECK col IN (...)` at Step 4, or from sample probes at Step 5.

## Object-type value constraint (range)

Restricts the allowed values of an object type to one or more numeric / character ranges.

**ORM 2 graphical signal:** brace-enclosed range expression — `{0..100}`, `{1..7}`, `{(0..100]}`. Round bracket excludes endpoint; square bracket includes (default).

**YAML form (top-level), single range:**
```yaml
constraints:
  - type: value
    object_type: <ot_id>
    range:
      min: 0
      max: 100
      min_inclusive: true                       # default true
      max_inclusive: false
    source: …
    status: …
```

**Multiple disjoint ranges** use the `ranges:` list form (see [representation-format.md](representation-format.md)).

Open-ended ranges: omit `max` (or `min`).

**CNL verbalization template:**
- Closed: *"{ObjectType} must be between {min} and {max} (inclusive of {min}, exclusive of {max})."*
- Open-ended: *"{ObjectType} must be at least {min}."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require(Person.age >= 0)
  ```
- Multi-range:
  ```python
  model.require(((LatitudeOffset.value >= -100) & (LatitudeOffset.value <= -20))
                | ((LatitudeOffset.value >= 40) & (LatitudeOffset.value <= 100)))
  ```

## Subset

Asserts that the population at one role sequence is always a subset of the population at another role sequence (compatible types).

**ORM 2 graphical signal:** a dotted arrow from the subset role sequence to the superset role sequence, marked with `⊆`.

**YAML form (top-level):**
```yaml
constraints:
  - type: subset
    subset_role_seq:
      - { fact_type: <ft_id>, role: <role_name> }
    superset_role_seq:
      - { fact_type: <ft_id>, role: <role_name> }
    source: …
    status: …
```

**CNL verbalization template:**
*"If {predicate-subset}, then {predicate-superset}."*

Example:
*"If a Person smokes, then that Person is cancer-prone."*

**Join subset:** when the projection spans a join path (e.g., "if an advisor serves in a country, then that advisor speaks a language used in that country"), the subset references multiple roles in each sequence and PyRel translation involves `model.where()` joins. See [orm-to-pyrel.md](orm-to-pyrel.md).

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require(Person.smokes.implies(Person.cancer_prone))
  # or, more explicitly:
  model.require((Person.smokes == True).implies(Person.cancer_prone == True))
  ```

## Equality

Asserts that two role-sequence populations are identical.

**ORM 2 graphical signal:** dotted line between the two role sequences with `=` mark.

**YAML form (top-level):**
```yaml
constraints:
  - type: equality
    role_seq_a:
      - { fact_type: <ft_id>, role: <role_name> }
    role_seq_b:
      - { fact_type: <ft_id>, role: <role_name> }
    source: …
    status: …
```

**CNL verbalization template:**
*"A {ObjectType} {predicate-a} if and only if it {predicate-b}."*

Example:
*"A Patient has systolic-BP recorded if and only if it has diastolic-BP recorded."*

**PyRel translation:**
- `model.require` tier — express as bidirectional implication or as two subset constraints.

## Exclusion

Asserts that two role-sequence populations never overlap.

**ORM 2 graphical signal:** dotted line between the two role sequences with `⊗` mark.

**YAML form (top-level):**
```yaml
constraints:
  - type: exclusion
    role_seq_a: …
    role_seq_b: …
    source: …
    status: …
```

**CNL verbalization template:**
*"No {ObjectType} {predicate-a} and {predicate-b}."*

Example:
*"No Person is married and widowed."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require(model.not_(Person.is_married & Person.is_widowed))
  ```

## Exclusive-or (xor — partition)

Inclusive-or + exclusion: every instance plays exactly one role from the set.

**ORM 2 graphical signal:** circled dot (mandatory-disjunctive) combined with `⊗` exclusion marker.

**YAML form (top-level):**
```yaml
constraints:
  - type: exclusive-or
    role_seqs:
      - [{ fact_type: <ft_id_1>, role: <role_name> }]
      - [{ fact_type: <ft_id_2>, role: <role_name> }]
    source: …
    status: …
```

**CNL verbalization template:**
*"Each {ObjectType} either {predicate-a} or {predicate-b}, but not both."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require((Academic.is_male & model.not_(Academic.is_female))
                | (Academic.is_female & model.not_(Academic.is_male)))
  ```

## Frequency — internal

Restricts how many times an instance may appear in a role or role sequence within a single fact type.

**ORM 2 graphical signal:** numeric annotation above the role boxes — `12`, `4..7`, `≤5`, `≥2`, `2`. Range bounds inclusive on both ends.

**YAML form (inline):**
```yaml
constraints:
  - type: frequency
    scope: internal
    roles: [<role_name>, …]                     # the roles the bound applies to
    bound: { min: 2, max: 7 }                   # use omitted/null for open ends
    source: …
    status: …
```

For exact-count (`12`): `bound: { min: 12, max: 12 }`. For `≤5`: `bound: { max: 5 }`.

**CNL verbalization template:**
- Range: *"Each {Reading-with-roles-fixed} appears at least {min} and at most {max} times."*
- Exact: *"Each {Reading-with-roles-fixed} appears exactly {n} times."*
- Upper bound only: *"Each {Reading-with-roles-fixed} appears at most {max} times."*

Example: *"Each panel that includes an expert includes at least 4 and at most 7 experts."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require((count(panel_includes_expert).per(panel) >= 4)
                & (count(panel_includes_expert).per(panel) <= 7))
  ```

## Frequency — external

Restricts how many times a tuple appears across multiple fact types.

**YAML form (top-level):**
```yaml
constraints:
  - type: frequency
    scope: external
    role_refs:
      - { fact_type: <ft_id>, role: <role_name> }
      - { fact_type: <ft_id>, role: <role_name> }
    bound: { min: 1, max: 2 }
    source: …
    status: …
```

**CNL verbalization template:**
*"Each combination of {role-1-CNL}, {role-2-CNL} occurs at most {max} times."*

**PyRel translation:** `model.require` over the join. See [orm-to-pyrel.md](orm-to-pyrel.md) for the canonical pattern.

## Ring constraints

Apply to binary fact types where both roles are hosted by the same object type (or related supertypes). ORM 2 catalogues 11 named variants plus two "considering" additions in Halpin's reference work.

**Variants and their semantics:**

| Variant | Asserts |
|---|---|
| `irreflexive` | No element relates to itself |
| `asymmetric` | If `a R b` then not `b R a` (also irreflexive) |
| `intransitive` | If `a R b` and `b R c` then not `a R c` |
| `antisymmetric` | If `a R b` and `b R a` then `a = b` |
| `acyclic` | No cycles of any length |
| `asymmetric-intransitive` | Combination of the above two |
| `acyclic-intransitive` | Combination |
| `symmetric` | `a R b` iff `b R a` |
| `symmetric-irreflexive` | Combination |
| `symmetric-intransitive` | Combination |
| `purely-reflexive` | Every element relates to itself |
| `reflexive` | (Halpin "considering" addition) Every element relates to itself, but other pairings allowed |
| `transitive` | (Halpin "considering" addition) If `a R b` and `b R c` then `a R c` |

**ORM 2 graphical signal:** a distinct ring glyph adjacent to the role connector, one per variant. Deontic ring constraints use dashed lines instead of solid.

**YAML form (inline, on the binary fact type):**
```yaml
fact_types:
  - id: person_parent_of_person
    reading: "{Person} is parent of {Person}"
    roles:
      - { object_type: person, role_name: parent }
      - { object_type: person, role_name: child }
    constraints:
      - type: ring
        variant: acyclic
        source: common-sense
        status: proposed
        modality: alethic
      - type: ring
        variant: asymmetric
        source: common-sense
        status: proposed
        modality: alethic
      - type: ring
        variant: irreflexive
        source: common-sense
        status: proposed
        modality: alethic
```

**Multi-variant policy:** combinations like *Asymmetric + Intransitive* are emitted as **two separate `ring` entries**, not as a compound `variant: asymmetric+intransitive`. This keeps verbalization, translation, and review independent per variant.

**CNL verbalization template (per variant):**
- `irreflexive`: *"No {ObjectType} {reading-with-self} itself."*
- `asymmetric`: *"If {reading}, then not {reverse-reading}."*
- `acyclic`: *"{Reading} is acyclic — no chain of {readings} returns to its start."*
- `symmetric`: *"{Reading} if and only if {reverse-reading}."*
- `transitive`: *"If {a} {predicate} {b} and {b} {predicate} {c}, then {a} {predicate} {c}."*
- `intransitive`: *"If {a} {predicate} {b} and {b} {predicate} {c}, then not {a} {predicate} {c}."*

**PyRel translation:**
- All ring constraints land in the `model.require` tier with named refs:
  ```python
  # irreflexive
  model.require(model.not_(Person.parent_of(Person, parent=Person, child=Person)))

  # acyclic — requires transitive closure; verify Phase 3+ whether PyRel supports recursive rules.
  # If not natively supported, emit as a comment with a plain explanation.
  ```
- Acyclic specifically depends on whether PyRel can express transitive closure. If unsupported, emit a `# NOT-TRANSLATED:` comment with the constraint left as documentation only. See [orm-to-pyrel.md](orm-to-pyrel.md).

## Value-comparison

Asserts a comparison between two roles on the same object type using `<`, `≤`, `=`, `≥`, `>`, or `≠` (`!=`).

**ORM 2 graphical signal:** annotation `≥`, `≤`, `=`, `<`, `>` between two roles. ORM 2 has no canonical glyph for `≠`; we emit `operator: "!="` as a v0.1 extension to cover same-type "must be distinct" cases (e.g., transfer from-warehouse ≠ to-warehouse). Verbalized in CNL as *"… is not equal to …"*.

**YAML form:**

Inline (intra-fact-type):
```yaml
constraints:
  - type: value-comparison
    operator: ">="
    role_a: <role_name>
    role_b: <role_name>
    source: …
    status: …
```

Top-level (cross-fact-type):
```yaml
constraints:
  - type: value-comparison
    operator: ">="
    role_a: { fact_type: <ft_id>, role: <role_name> }
    role_b: { fact_type: <ft_id>, role: <role_name> }
    source: …
    status: …
```

**CNL verbalization template:**
*"For each {ObjectType}, {role-a-CNL} {operator-natural} {role-b-CNL}."*

Example:
*"For each Project, end-date is greater than or equal to start-date."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require(Project.end_date >= Project.start_date)
  ```

## Cardinality — object

Constrains the number of instances of an object type at any time.

**ORM 2 graphical signal:** `# = N`, `# ≤ N`, etc. adjacent to the object type.

**YAML form (top-level):**
```yaml
constraints:
  - type: cardinality
    scope: object
    object_type: <ot_id>
    bound: { min: 1, max: 1 }
    source: …
    status: …
```

**CNL verbalization template:**
- Exact: *"There is exactly one {ObjectType}."*
- Upper bound: *"There are at most {max} {ObjectType}s."*
- Lower bound: *"There are at least {min} {ObjectType}s."*

**PyRel translation:**
- `model.require` tier:
  ```python
  model.require(count(President) == 1)
  ```

## Cardinality — role

Constrains the number of instances playing a particular role.

**ORM 2 graphical signal:** `# ≤ N` etc. adjacent to a single role.

**YAML form (top-level):**
```yaml
constraints:
  - type: cardinality
    scope: role
    role_ref: { fact_type: <ft_id>, role: <role_name> }
    bound: { max: 1 }
    source: …
    status: …
```

**CNL verbalization template:**
*"At most {max} {ObjectType} plays the role of {role-name-natural}."*

**PyRel translation:** `model.require(count(Politician.is_president) <= 1)`.

## Subtype-partition

Asserts a partition over a supertype's instances by a set of subtypes. Independently encodes:
- `exclusive: true` — no instance is in two subtypes (Halpin's circled X).
- `exhaustive: true` — every supertype instance is in at least one subtype (Halpin's circled dot).

Both true → full partition. Either alone → weaker constraint.

**ORM 2 graphical signal:** circled X (exclusion) and/or circled dot (totality) at the supertype-subtype junction.

**YAML form (top-level):**
```yaml
constraints:
  - type: subtype-partition
    supertype: <ot_id>
    subtypes: [<ot_id_1>, <ot_id_2>, …]
    exclusive: true
    exhaustive: true
    source: …
    status: …
```

**CNL verbalization template:**
- Full partition: *"Every {Supertype} is exactly one of: {Subtype1}, {Subtype2}, …."*
- Exclusive only: *"No {Supertype} is more than one of: {Subtype1}, {Subtype2}, …."*
- Exhaustive only: *"Every {Supertype} is at least one of: {Subtype1}, {Subtype2}, …."*

**PyRel translation:**
- Subtype membership rules are mechanical (heuristic tier):
  ```python
  PhysicalProduct = model.Concept("PhysicalProduct", extends=[Product])
  model.define(PhysicalProduct(Product)).where(Product.type == "PHYSICAL")
  ```
- Exclusion (`exclusive: true`):
  ```python
  model.require(model.not_(PhysicalProduct & DigitalProduct))
  ```
  for each pair of subtypes.
- Exhaustiveness (`exhaustive: true`):
  ```python
  model.require(Product.implies(PhysicalProduct | DigitalProduct | SubscriptionProduct))
  ```

## Textual / FORML 2

A first-order constraint that doesn't fit any of the graphical types above. Stored as natural-language text or FORML 2 syntax.

**ORM 2 graphical signal:** footnote on the diagram referencing a textual constraint listed elsewhere.

**YAML form (top-level):**
```yaml
constraints:
  - type: textual
    expression: "Each Employee who has Rank 'NonExec' uses at most one CompanyCar."
    formal_language: natural                    # natural | forml2
    formal_expression: null                     # optional formal-language string
    source: …
    status: …
```

**CNL verbalization template:** the `expression` itself, prefixed with `[textual]`.

**PyRel translation:**
- v0.1 does not parse FORML 2. Emit as `# NOTE:` comment in `model.py`:
  ```python
  # NOTE (textual constraint, source: user-supplied):
  # Each Employee who has Rank 'NonExec' uses at most one CompanyCar.
  ```

## Modality reminder

Every constraint above can be alethic (must) or deontic (should). The `modality:` field controls translation:

- `modality: alethic` (default) → translate per the tier above.
- `modality: deontic` → emit as `# DEONTIC NOTE:` in `model.py` regardless of tier. PyRel's `model.require` is alethic-only; deontic constraints don't translate.

The user labels modality at SRP Step 9e. DDL-derived constraints inherit `alethic` automatically (the database enforces them). Common-sense, sample, llm-inferred, and user-supplied constraints require explicit modality labelling at confirmation.
