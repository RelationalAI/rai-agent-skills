# Antipattern Catalog

Schema antipatterns detected at SRP **Step 7**, with detection signal, detection SQL or heuristic, default resolution, resolution menu (for Step 9c), and false-positive guidance. Antipatterns surface as `provenance.warning: <code>` flags on the affected YAML entry.

Load at SRP Step 7 (and again at Step 9c when resolving flags).

Cross-references:
- Step 7 placement in workflow → [srp-workflow.md](srp-workflow.md)
- Per-dialect SQL syntax → [probing-strategies.md](probing-strategies.md)
- Resolution shapes (subtypes, value enums, etc.) → [constraint-reference.md](constraint-reference.md)

## Discipline

Two design rules govern every antipattern entry:

1. **Flag, never silently correct.** The user resolves at Step 9c. Default resolutions are surfaced for One-shot mode and as the proposed answer in Guided.
2. **Conservative detection.** False negatives (missing a real antipattern) are preferred over false positives. Clean schemas (TPC-H) should produce zero antipattern flags. Each detection signal documents its false-positive risk; ambiguous matches downgrade to a softer "candidate" flag rather than a hard antipattern.

## Quick reference

| Code | Antipattern | Detection scope | Default resolution |
|---|---|---|---|
| `denormalized-address` | Multiple address-shaped columns on one table | Column-name pattern match | Propose `Address` value type extraction |
| `encoded-enum-in-varchar` | Low-cardinality VARCHAR with enum-style suffix | Step 5 distinct-value probe | Promote to `value` constraint with sample values |
| `type-column-subtype` | TYPE/CATEGORY/KIND VARCHAR + correlated side tables | Column + FK correlation | Propose subtype partition |
| `ambiguous-junction-no-extras` | Composite all-FK PK, no other columns | Table structure | Default = pure m:n binary |
| `ambiguous-junction-with-extras` | Composite all-FK PK + non-FK columns | Table structure | Default = objectified entity |
| `missing-unique` | Sample-unique column, no DDL UNIQUE | Step 5 sample probe | Flag candidate; user confirms |
| `missing-fk` | `*_id` column matching another table's PK by name; no FK declared | Name-pattern match | Flag candidate; user confirms |
| `boolean-encoded-varchar` | Column with values restricted to boolean encoding | Step 5 distinct-value probe | Promote to `Boolean` value type |
| `independent-object-type` | Table with no inbound FKs, not a junction | Schema topology | Propose `independent: true` |
| `no-pk-detected` | Table without a primary key | INFORMATION_SCHEMA absence | Flag for user; emit entity with external reference |
| `cross-schema-fk` | FK pointing into another schema | INFORMATION_SCHEMA scan | Inform user; scope may be too narrow |
| `history-table` | Table name ends in `_HIST`, `_LOG`, `_AUDIT` | Name pattern | Flag for user (often skipped) |
| `lookup-table-candidate` | Table with code+name only, used by FK only | Schema topology | Propose value-type promotion |
| `composite-fk` | Multi-column FK referencing composite PK | Schema topology | Inform user; constraint emitted differently |
| `polymorphic-fk-candidate` | Same FK column references two different tables (rare) | Schema topology | Flag; out of v0.1 scope |
| `unparseable-check` | CHECK constraint that can't be parsed into a structured form | Parse failure at Step 4 | Emit as `textual` |
| `generated-column` | Column with generation expression | DDL extraction | Note in provenance; treat as regular column for v0.1 |

The full per-antipattern detail follows.

## `denormalized-address`

**Detection signal:** a single table has multiple columns whose names match the address-component pattern: `(line1|line2|address|street|city|state|region|zip|postal|country)` — case-insensitive.

**Detection rule:** ≥ 3 distinct matches in one table → flag; 2 matches → flag with `severity: low` (often legitimate, e.g., a `Customer` with just `city` and `country` columns); 1 match → no flag.

**Default resolution:** Propose extracting an `Address` value type:
```yaml
object_types:
  - id: address
    name: Address
    kind: value
    primitive: composite     # Phase 3 stretch — composite value types
    fields:
      line1: String
      line2: String
      city: String
      state: String
      postal_code: String
      country: String
```

For v0.1, where composite value types aren't fully fleshed out, the default resolution is:
- Surface the antipattern flag in verbalization.
- Don't restructure the model unilaterally.
- Recommend the user create an `Address` entity type manually if they want normalization.

**Resolution menu (Step 9c):**
- **Confirm denormalization** — leave columns as-is; antipattern flag stays in YAML for documentation but no model restructuring.
- **Extract Address value type** — restructure: emit `Address` entity, link via fact type, drop the original columns from the source entity's fact types.
- **Skip** — remove the flag without action.

**False-positive guidance:**
- A `Customer` with just `name` and `city` is not denormalized; 1-2 matches don't fire.
- A `Warehouse` with the same address columns alongside `Customer` is two separate flags, not a "shared address" inference.
- Tables that only have one address shape (e.g., a dedicated `Address` table) don't fire.

## `encoded-enum-in-varchar`

**Detection signal:** Step 5's distinct-value probe found a low-cardinality VARCHAR column. Trigger conditions:
- Column type is VARCHAR / TEXT / CHAR.
- Column name ends in `STATUS`, `TYPE`, `KIND`, `CATEGORY`, `STATE`, `LEVEL`, `CLASS`, or `MODE`.
- Distinct count from sample is < 20.

**Detection rule:** all three trigger conditions met → flag.

**Default resolution:** Step 5 already proposed a value constraint with `allowed: [<sample values>]`. Step 7's flag confirms the antipattern interpretation. PyRel translation promotes to `model.Enum` (mechanical tier).

**Resolution menu:**
- **Confirm enum** — promote to `model.Enum` in PyRel. Default.
- **Keep as free-text** — reject the value constraint; treat the column as open-ended String. (Used when the sample values are coincidental, e.g., a mostly-empty `NOTES` column that happened to have only a few sampled values.)
- **Refine the enum** — user adds or removes values from the proposed `allowed` list.

**False-positive guidance:**
- A `description` or `notes` column is rarely an enum even if the sample is small. Trigger conditions exclude these via the name-pattern requirement.
- A `STATUS` column with 50+ distinct values is not an enum at v0.1's threshold; the cardinality cutoff guards against this.

## `type-column-subtype`

**Detection signal:** TYPE-column-driven subtype split. Trigger conditions:
- A VARCHAR column whose name matches `(TYPE|CATEGORY|KIND|CLASS|VARIANT)` — case-insensitive.
- The column's distinct values from Step 5 sample probe are well-defined (≤ 10 distinct values).
- One or more side tables have FKs into this table whose presence correlates with specific TYPE values (i.e., physical-product-details rows exist only when `TYPE='PHYSICAL'`).

**Detection rule:** the correlation must be visible — for each detected TYPE value, at least one side table's row count correlates ≥ 90% with that value (sample-derived).

**Default resolution:** Propose subtypes per TYPE value with `extends=[Parent]` and a `subtype-partition` constraint:
```yaml
object_types:
  - id: physical_product
    name: PhysicalProduct
    kind: entity
    subtype_of: [product]
    inherits_reference: true              # dashed arrow — share parent's identity
    derivation: derived
    derivation_rule: "Each PhysicalProduct is a Product whose Type is 'PHYSICAL'."
  # … similar for digital_product, subscription_product

constraints:
  - type: subtype-partition
    supertype: product
    subtypes: [physical_product, digital_product, subscription_product]
    exclusive: true
    exhaustive: true
    source: common-sense
    status: proposed
    provenance: { table: PUBLIC.PRODUCTS, column: TYPE }
```

The `exhaustive: true` is set when the sample shows every parent row has a TYPE value (NOT NULL is already explicit in DDL). `exclusive: true` is implicit in TYPE-column semantics (a column has one value per row).

**Resolution menu:**
- **Accept partition** — emit the subtype rules and partition constraint. Default.
- **Accept subtypes without partition** — emit the subtypes but mark `exclusive: false` or `exhaustive: false` if the user knows of overlap or unaccounted-for rows.
- **Reject subtype split** — keep `Product` as a single entity type with `Type` as a value constraint. Rejection moves to `rejected_proposals`.

**False-positive guidance:**
- A `TYPE` column without correlated side tables is just an enum, not a subtype split. Detection rule's correlation requirement guards this.
- A `CATEGORY` column where one row can have multiple categories (junction table) is not a subtype split.
- Three or more side tables with weak correlation → don't fire; ask the user instead.

## `ambiguous-junction-no-extras`

**Detection signal:** a junction table with composite PK that's all-FK and no other columns. Step 2 already flagged the table as a candidate.

**Default resolution:** treat as **pure m:n binary fact type**. Don't emit an entity type for the junction.

**Resolution menu:**
- **Pure m:n binary** — emit a binary fact type connecting the two referenced entities. Default.
- **Objectified entity** — emit an entity type with `reference.mode: external` and a corresponding external UC.

The structural difference to the user:
- Pure m:n: `Order tagged with Tag` — no Order-Tag identity exists separately.
- Objectified: `OrderTag` is an entity that may itself play roles (e.g., `OrderTag was applied at DateTime`).

Default = pure m:n because if the user wanted objectification they would have added an explicit attribute.

**False-positive guidance:**
- Surrogate-PK junction tables (PK is a single auto-increment column, FKs are separate) are not flagged here — they're `lookup-table-candidate` or just regular entities.

## `ambiguous-junction-with-extras`

**Detection signal:** a junction table with composite PK that's all-FK PLUS at least one non-FK, non-PK column.

**Default resolution:** treat as **objectified entity**. The extra column is an attribute of the objectification.

**Resolution menu:**
- **Objectified entity** — emit entity type with `reference.mode: external`, FK fact types for each PK column, attribute fact types for each extra column. Default.
- **Pure m:n with denormalized attribute** — keep as pure m:n binary; the extra column becomes a constraint on the binary (rare but possible).

Default = objectified because the extra column is a strong signal that the relationship has its own identity.

**False-positive guidance:**
- Audit columns (`created_at`, `updated_at`) on a junction table don't necessarily mean objectification — but Step 9c lets the user override the default if they're just bookkeeping.

## `missing-unique`

**Detection signal:** Step 5's functional-dependency probe found a non-PK column with `total = distinct_count` AND `total >= 1000`.

**Detection rule:** sample is unique → flag. Don't propose a UC.

**Default resolution:** flag only — no constraint emitted automatically. Step 9c presents the candidate and the user decides.

**Resolution menu:**
- **Confirm uniqueness** — emit an internal UC, `source: user-supplied, status: confirmed`.
- **Reject** — the column is unique by accident in the data, not by rule. No constraint emitted.

**False-positive guidance:**
- A column unique in 1000-row sample may not be unique at scale. Discipline: never auto-emit; user always decides.
- Sample-uniqueness on small tables (< 1000 rows) doesn't fire — too small to be meaningful.

## `missing-fk`

**Detection signal:** column name pattern `<entity>_id` (or `<entity>_code`, `<entity>_key`) where:
- `<entity>` matches another table's name (singularized).
- That other table has a single-column PK.
- No actual FK is declared between them.

**Detection rule:** name + structural match → flag. Don't emit a fact type for the implied relationship.

**Default resolution:** flag only — Step 9c presents the candidate and the user decides.

**Resolution menu:**
- **Confirm FK** — emit a fact type linking the two entities + a mandatory constraint per the pattern. `source: user-supplied`.
- **Reject** — the column name happens to match but is not a foreign key (e.g., `external_user_id` is not the same as `user_id`).

**False-positive guidance:**
- The discipline is firm — the SRP must NOT silently invent fact types from name conventions. Half the false positives in DDL recovery come from this kind of guess.
- A column named exactly like another table's PK (`USER_ID` matching `USER.USER_ID`) is the strongest signal; weaker matches downgrade.

## `boolean-encoded-varchar`

**Detection signal:** Step 5's distinct-value probe found a column with values restricted to one of:
- `{0, 1}` (numeric)
- `{'Y', 'N'}` (single-char string)
- `{'YES', 'NO'}`
- `{'TRUE', 'FALSE'}` (case-insensitive)
- `{'T', 'F'}` (single-char string)

**Default resolution:** propose promoting the column's value type to `Boolean`. Emit a transformation note in provenance.

**Resolution menu:**
- **Promote to Boolean** — value type changes to `Boolean`. Default.
- **Keep as-is** — column remains String/Integer; flag stays for documentation.

**False-positive guidance:**
- A column with `{0, 1}` values may legitimately be a count (`is_complete` count of 0 or 1 entities). Detection rule prefers a name signal — column names ending in `IS_*`, `HAS_*`, `_FLAG`, `_BOOL` reinforce the match. Without the name signal, downgrade to soft flag.

## `independent-object-type`

**Detection signal:** an entity type's source table has no inbound FKs from any other table in scope, and the table is not itself a junction.

**Default resolution:** propose `independent: true` on the entity type. Halpin's `!` marker.

**Resolution menu:**
- **Confirm independent** — keep `independent: true`. Default.
- **Reject** — table happens to have no inbound FKs in this schema slice but isn't truly independent (e.g., scope is too narrow).

**False-positive guidance:**
- Cross-schema FKs (Step 7's `cross-schema-fk` detection) downgrade this flag — if there are FKs from another schema, the entity is not truly independent.
- Lookup-table candidates often look independent; check the `lookup-table-candidate` flag first.

## `no-pk-detected`

**Detection signal:** INFORMATION_SCHEMA shows the table has no PRIMARY KEY constraint.

**Default resolution:** emit the entity type with `provenance.origin: no-pk-detected, provenance.warning: "no-pk-detected"`. The entity has no internal reference scheme; flag the unresolvable identity.

**Resolution menu:**
- **User-supplied identifier** — user names columns to serve as identity; emit those as a composite PK-equivalent UC.
- **Skip the table** — remove from the model entirely; Step 9c's edit causes the entity type to be removed.
- **Synthetic surrogate** — emit a synthetic identifier note (out of v0.1 scope; flag for v1.5).

**False-positive guidance:** rarely a false positive — schemas without PKs genuinely lack a reference scheme. The detection is a true antipattern.

## `cross-schema-fk`

**Detection signal:** an FK column's referenced table is in a different schema than the SRP's scope.

**Default resolution:** record the FK in provenance but don't emit a fact type to a non-scoped target. Inform the user that scope may be too narrow.

**Resolution menu:**
- **Expand scope** — re-run SRP with the cross-schema target included.
- **Treat target as opaque** — emit a fact type to a placeholder entity type with `provenance.warning: "out-of-scope-entity"`.
- **Drop the FK** — skip the relationship.

## `history-table`

**Detection signal:** table name ends in `_HIST`, `_HISTORY`, `_LOG`, `_AUDIT`.

**Default resolution:** emit the entity type with `provenance.warning: "history-table"`. Don't apply special handling at v0.1.

**Resolution menu:**
- **Include in model** — keep the entity. Default.
- **Skip** — remove from the model; common case for audit tables that don't carry domain meaning.

**False-positive guidance:** a table named `BLOG_HISTORY` for a blog-publishing system is genuinely a domain table, not an audit. Name pattern is a soft signal.

## `lookup-table-candidate`

**Detection signal:** a table with:
- Two or three columns total: one PK, one descriptive (typically `name`/`description`/`label`), maybe one ordering (`sort_order`).
- Referenced by FKs from other tables.

**Default resolution:** flag as value-type-promotion candidate. v0.1 keeps as entity type; v1.5 may auto-promote.

**Resolution menu:**
- **Keep as entity** — default. Lookup tables can play roles.
- **Promote to value type** — collapse the lookup; the referenced FK columns become value-type-typed roles.

## `composite-fk`

**Detection signal:** an FK with multiple columns referencing a composite PK.

**Default resolution:** emit one binary fact type linking the entities, but use `provenance.warning: "composite-fk"`. The Step 4 lift emits a join-style mandatory.

**Resolution menu:** typically no user choice needed; this is informational. Step 9c may surface it for confirmation.

**False-positive guidance:** none — composite FKs are factually present.

## `polymorphic-fk-candidate`

**Detection signal:** the same FK column referencing two different tables in different rows (e.g., a `target_id` column where `target_type` distinguishes which table). Detection requires sample-data inspection at Step 5.

**Default resolution:** **out of v0.1 scope.** Flag as `polymorphic-fk-candidate` with `severity: high` and surface the antipattern; don't emit fact types.

**Resolution menu (Step 9c, v1.5+):**
- The user manually splits the column into two distinct fact types based on `target_type`.

For v0.1: the SRP halts on this construct gracefully — emit the source entity, omit the relationship, surface the flag.

## `unparseable-check`

**Detection signal:** Step 4's CHECK parser fails on a `CHECK (...)` clause.

**Default resolution:** emit the constraint as `type: textual, formal_language: natural` with the raw clause text and `provenance.warning: "unparseable-check"`.

**Resolution menu:**
- **Keep as textual** — the user accepts; PyRel emits as `# NOTE:` comment.
- **Discard** — remove from model.
- **User rewrites in structured form** — user provides a structured constraint; the textual form is dropped.

## `generated-column`

**Detection signal:** column metadata indicates it's computed (e.g., Snowflake `IS_AUTO_INCREMENT` or `GENERATED ALWAYS AS`).

**Default resolution:** record the generation expression in `provenance.column_default` and emit the column as a regular fact type with `provenance.warning: "generated-column"`. v0.1 doesn't model derivation rules from generation expressions.

**Resolution menu:**
- **Treat as derived** — user upgrades the fact type to `derivation: derived` with the expression as `derivation_rule`. v1.5 will automate this.
- **Treat as regular** — column behaves like any other for the purposes of the model.

## Antipattern flag shape

Every flag attaches to the YAML entry it's about (object type, fact type, or column-bearing reference) via `provenance.warning`:

```yaml
object_types:
  - id: customer
    name: Customer
    kind: entity
    reference: …
    provenance:
      origin: table-with-pk
      table: PUBLIC.CUSTOMERS
      warning: denormalized-address
      warning_detail:
        matched_columns: [ADDRESS_LINE1, ADDRESS_LINE2, CITY, STATE, ZIP, COUNTRY]
        severity: high
```

For multi-flag entries, `warnings:` is a list. The catalog above lists single-flag-per-entry as the common case; multi-flag is allowed when truly orthogonal (e.g., a table can be both `history-table` and `independent-object-type`).

## Step 9c interaction shape

In Guided mode, Step 9c walks the antipattern flags one at a time (or batches when ≥ 5 of the same code per the Step 9 batching policy):

> *I flagged `<antipattern-code>` on `<entity-or-fact-type>`. The default resolution is `<default-action>`. Confirm, override, or skip?*

The user's decision is recorded in `provenance.resolution`:

```yaml
provenance:
  warning: encoded-enum-in-varchar
  resolution:
    action: promote_to_enum         # or override_label, skip
    decided_at: 9c
    decided_by: user
```

The flag itself stays in the YAML (for traceability); only `resolution` evolves. A future SRP run on the same schema can read past resolutions to skip questions the user already answered (Phase 4+ scope; not v0.1).

## What this catalog does NOT cover in v0.1

- **Schema smells beyond the listed codes.** Dead columns (always NULL), redundant indexes, naming inconsistencies — out of scope. The SRP is for ORM recovery, not full schema review.
- **Cross-schema or cross-database antipatterns** beyond the simple `cross-schema-fk` flag.
- **Performance antipatterns** (missing indexes, table fragmentation). Out of scope; this skill is conceptual, not physical.
- **Cycle detection in FK graphs** beyond self-FK (already covered by `Step 6b ring-pattern matching`). Multi-table FK cycles (e.g., A→B→C→A) emerge but are not flagged in v0.1.

These are documented gaps. Real schemas may surface new antipatterns; the catalog is extended by adding new codes, detection signals, and resolution menus — markdown-table form makes additions diff-reviewable.
