---
name: rai-ontology
description: Builds and evolves RAI ontologies — greenfield starter builds from Snowflake tables or local data, and all domain-modeling decisions (concepts, relationships, identity, subtypes, data mapping, layering, enrichment). Use when creating a new RAI model, starting a proof of concept, onboarding a dataset, or reviewing and enriching an existing ontology. Authoring the PyRel itself (syntax, data loading, rules, queries) is `rai-pyrel`.
---

# Ontology
<!-- v1-STABLE -->

## Summary

**What:** Building a working RAI ontology from raw data, and the design decisions that shape it — concepts, relationships, properties, identity, data mapping, layering, and enrichment.

**When to use:**
- Starting a new RAI project from Snowflake tables or local CSV files (the [Greenfield Build Workflow](#greenfield-build-workflow))
- Enriching an existing model — adding properties, relationships, or subtypes to a model that already loads and queries
- Reviewing or evolving a model — assessing gaps (READY / MODEL_GAP / DATA_GAP), examining inventories, applying advanced patterns
- Any concept / relationship / property design decision, including cross-product decision concepts for optimization

**When NOT to use:**
- PyRel authoring of any kind — syntax, data loading, queries, derived-property rules — see `rai-pyrel`
- Optimization formulation (variables, constraints, objectives) — see `rai-prescriptive-problem`

**Overview:** Scope the questions → discover and analyze source data → identify concepts with identities → identify relationships and properties → validate the design against the schema → generate code → validate with queries. The [Design Principles](#concept-design-principles) sections are the authority the workflow steps apply; enrichment and gap classification extend an already-working model.

---

## Quick Reference

| Decision | Choose | Pattern |
|----------|--------|---------|
| Has own PK / identity? | **Concept** | `model.Concept("Name", identify_by={"id": Type})` |
| Scalar value on entity? | **Property** | `model.Property(f"{Concept} has {Type:name}")` |
| Functional FK (each A → one B)? | **Property** | `model.Property(f"{Order} placed by {Customer:customer}")` |
| Many-to-many link? | **Relationship** | `model.Relationship(f"{A} links to {B}")` |
| Boolean flag? | **Unary Relationship** | `model.Relationship(f"{Concept} is active")` |
| Fundamental category of a concept? | **Subtype** | `model.Concept("Supplier", extends=[Business])` |
| Recurring `.where()` filter? | **Subtype** | `model.Concept("Sub", extends=[Parent])` |
| Many-to-many with data? | **Junction concept** | Concept with compound identity |

**Layer structure:** Core (source→semantic) → Computed (derived logic) → Application (queries, reports)

**Naming:** Singular business nouns for concepts (`Customer`), lowercase for properties (`amount`), related concept name for relationships (`customer`).

---

## Greenfield Build Workflow

Start from the business domain — what concepts exist, what questions must the model answer — then find data mappings. Domain-first modeling produces better models than table-to-concept mapping because user intent drives concept selection rather than table structure.

Document your findings and decisions at each step so others can follow the reasoning.

**Interaction mode:** Before starting, ask the user which mode they prefer:
- **Guided** — present your proposed design at each step and confirm before proceeding. Best when the user has domain context to share along the way; they know their domain better than the data does.
- **One-shot** — produce the best result you can in a single pass. Best when the user wants speed and will review/iterate after.

### Step 1 — Scope

Before looking at any data, define:
- **1-3 concrete questions** the model must answer
- **What is out of scope** — explicitly exclude tables/domains not needed yet

Keep the first version to ~10-15 must-have properties. A tight scope keeps the model small enough to implement and validate without rework.

| Goal | In scope | Out of scope |
|---|---|---|
| Identify delayed orders | Orders, shipments, delay timestamps | Returns, carrier contracts, inventory |

### Step 2 — Discover source data

**Data loading decision:** Use `model.Table()` for Snowflake-backed data (any size, production-ready). Use `model.data()` for prototyping with DataFrames only (≤ hundreds of rows) or inline scenario data not in Snowflake. For connection setup, see `rai-setup`.

Pull the full column inventory first — it stays load-bearing through Step 6:

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, NUMERIC_PRECISION, NUMERIC_SCALE
FROM <database>.INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = '<schema>' ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

> **Keep this result available throughout the workflow.** `DATA_TYPE` and `NUMERIC_SCALE` are the authoritative source for deriving RAI property types in Step 6. Never infer types from column names, CSV samples, or example ontologies.

**Analyze each table:** business purpose, likely PKs (`_ID` suffixes, identity/NOT NULL columns), inferred FKs (columns matching other tables' PKs), soft-joins (shared codes across tables), `IS_`/`HAS_` prefixes (boolean flags), and `STATUS`/`TYPE`/`CATEGORY` columns with repeated values (enum or subtype candidates). Nullability, identity flags, and column comments are stronger signals than names alone.

**Identify data shape.** Source tables arrive in one of two shapes, classified per table:
- **Raw events / measurements** — one row per occurrence; metrics must be *derived* downstream from the raw rows.
- **Pre-aggregated statistics** — one row per entity, pair, or time bucket carrying already-computed values (including long-form `(entity_i, entity_j, value)` matrices). Bind directly; do not re-aggregate — worked example: the pairwise value matrix in [build-examples.md](references/build-examples.md).

**Run the EDA queries** in [discovery-queries.md](references/discovery-queries.md) — load it now if you are executing this step. It covers: row count and PK uniqueness, FK cardinality, null rates, value distributions for enum/category columns, subtype discovery (TYPE columns that partition entities), relationship multiplicity (1:1 / 1:N / M:N — Step 4 depends on this), and, for graph/network data, topology tracing (node-type-to-node-type edge counts, NULL-FK gap checks) that reveals hidden tiers before Step 3.

### Step 3 — Identify concepts

Work domain-first: brainstorm business entities broadly — both obvious entities (tables with clear PKs) and implied entities (referenced but not directly represented) — then map each to an authoritative source. Reject any concept that cannot be grounded. Apply [Concept Design Principles](#concept-design-principles).

Define each concept's identity from the authoritative source's PK columns. Identity is intrinsic: a concept without an identity key is not yet a concept.

**Check for subtypes:** If Step 2 EDA found TYPE/CATEGORY columns that partition a concept into fundamentally different kinds (e.g. `BUSINESS_TYPE` with values `Supplier` and `Customer`), model these as subtypes using `extends` — when each kind carries its own properties or relationships, not for every enum column. If you find yourself writing the same `.where()` filter repeatedly, promote it to a named subtype. See [categorization-and-advanced.md](references/categorization-and-advanced.md).

**Validate:** each concept maps to at least one authoritative source, has a clear identity, and the set is orthogonal (see [Concept orthogonality](#concept-orthogonality)).

**Identity hygiene.** Prefer minimal identity (1-2 natural-key fields). If the only natural identity you can find is >3 fields, pause: (a) does the source table have a surrogate ID you missed? (b) is this really a measurement that belongs as a Relationship payload on a smaller concept? If both answers are no, keep the compound identity but flag the concept as a candidate for scope cuts.

### Step 4 — Identify relationships and properties

**Choose Property or Relationship per link** from the Step 2 multiplicity results: Property for many-to-one (scalar attributes AND functional FKs), Relationship for one-to-many / many-to-many, multi-field associations, and boolean flags. The full decision rule, FD semantics, and failure modes are in [Relationship Principles](#relationship-principles).

Then assign remaining columns as properties of their parent concepts, grouped by topic. Not every column needs a property — omit columns with no business meaning for the scoped questions.

**Anti-bundle rule.** Each scalar attribute should be its own `Property`. Packing more than two unrelated scalars into a single `Relationship` makes them un-queryable (you can't filter or aggregate on one field). Reserve multi-field Relationships for genuinely co-occurring data (e.g. a date range `{Promotion} active from {DateTime:start} to {DateTime:end}`).

**Same-type-slot disambiguation.** When a `Relationship` has two slots of the same concept type, the slots are roles and must be distinguished: either split into two `Property` declarations whose attribute names are the roles, or label both slots — `f"{Lane} from {Location:origin} to {Location:destination}"`. Without this, `model.define(...)` silently binds both slots to whichever column you list first. Verify with a Step 7 query that origin ≠ destination on at least one row.

### Step 5 — Validate design

Validate the proposed design against source data before coding:

| Check | What to confirm |
|-------|-----------------|
| Identity columns | Exist in source and uniquely identify rows |
| Associations | Valid FK or join key exists; multiplicity determined (1:1 / N:1 → Property; 1:N / M:N → Relationship) |
| Properties | Source column exists with compatible data type |
| Concept grounding | Every concept maps to an authoritative source |
| Orthogonality | No two concepts represent the same entity set |
| Threshold scale | For any planned threshold (subtype or flag), check `min/max/avg` of the property first — assuming 0-100 when the data is 0-10 captures nothing or everything |
| Fact decomposition | Each relationship is irreducible and survives sample-data + counterexample checks — apply [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) to steps 3-5 output |

**Type validation is the gate.** Verify every property's RAI type against `INFORMATION_SCHEMA.COLUMNS` using the [type mapping table](#data-mapping-guidance) — a single mismatch causes a `TyperError` at query time that blocks ALL queries on the model with no indication of which property failed. The high-risk cases: date-like columns stored as TEXT or TIMESTAMP_NTZ (use `String` / `DateTime`, not `Date`), `NUMBER` scale (scale > 0 → `Float`), BOOLEAN (→ `Boolean` property or unary Relationship), and numeric IDs (a `PHONE` column may be NUMBER — the schema dictates, not the name).

### Step 6 — Generate code

> **GATE: Do not proceed until Step 5 type validation is complete.** Derive every property type from the type mapping table and the Step 2 `INFORMATION_SCHEMA.COLUMNS` output.

Follow conventions in `rai-pyrel`. Worked end-to-end builds (Sources class, FK binding, junction concepts, pairwise matrices) are in [build-examples.md](references/build-examples.md) — load it when generating your first build or when a binding pattern is unclear. Put everything in a single file named after the domain (`supply_chain.py`, `fraud.py`) — easiest to iterate on. When the model grows (multiple reasoners, derived layers, shared logic), split into a package per [Layering Principles](#layering-principles).

> **If you split into a package:** never name the directory `model/` when your `Model` variable is also called `model` — Python resolves `import model.xxx` to the directory, shadowing the variable. Use a domain-specific name (`sc_model/`, `fraud_model/`).

### Step 7 — Validate with queries

Add validation queries to the bottom of `<domain>.py` and fix any import errors or empty results before considering the ontology complete. For query syntax, see `rai-pyrel`. Import aggregates with `from relationalai.semantics.std import aggregates`.

**7a — Spot-check property types** for each `BOOLEAN`, `DATE`, and `NUMBER` column in the Step 2 schema output — the three most common sources of silent `TyperError`.

**7b — Count instances per concept** to confirm data binding loaded rows:

```python
df = model.select(aggregates.count(MyConcept).alias("count")).to_df()
# Expect: count matches source table row count. Zero means data binding failed.
```

> `aggregates.count(C)` on a concept with zero instances returns an *empty* DataFrame, not `count=0`. For chained workflows where a placeholder concept is populated by a later step, verify declaration via `inspect.schema()` membership instead.

**7c — Verify relationships** to confirm FK joins resolved:

```python
df = model.select(ConceptA.id.alias("a"), ConceptB.id.alias("b")).where(
    ConceptA.my_relationship(ConceptB)).to_df()
# Expect: non-empty. Empty means the FK join didn't match.
```

**7d — Answer the scoped questions** from Step 1 — each should be answerable with a select/where query.

**7e — Report what actually registered.** Emit an `inspect.schema()` summary — the canonical "here's what got built" artifact, distinct from "here's what I intended to build":

```python
from relationalai.semantics import inspect

schema = inspect.schema(model)
print(schema)                                  # full dump for small models
for c in (schema[n] for n in scoped_concepts): # targeted for larger models
    idents = ", ".join(f"{f.name}:{f.type_name}" for f in c.identify_by)
    print(f"{c.name} [id: {idents}], extends={c.extends}")
    for prop in c.properties:
        print(f"  .{prop.name}: {prop.type_name}")
    for rel in c.relationships:
        print(f"  ~{rel.name}: {rel.reading}")
print(f"Tables: {[t.name for t in schema.tables]}")
```

`inspect.schema()` enriches the summary with table-backed type information — for properties created via `Concept.new(table.to_schema())` it reports concrete types even when the frontend model types them as `Any`. See `rai-pyrel/references/inspect-module.md`. To also surface source columns not yet mapped (the MODEL_GAP candidates), diff the summary against the source table columns — see `rai-discovery` § Computing the classification from `inspect.schema()`.

---

## Concept Design Principles

### When to create a new concept vs. adding a property

**Create a concept** when the thing has its own identity, its own properties, and participates in multiple relationships. **Add a property** when the value only makes sense in the context of its parent. **Decision rule:** if you would give it a primary key in a relational schema, it is a concept; if it would be a column on someone else's table, it is a property.

### Concept orthogonality

- **No-overlap test**: if two proposed concepts always have the same entity set, merge them — two names for the same thing is not two concepts.
- **Not-a-property-group test**: if a proposed concept is a bundle of attributes with no independent identity, make them properties on the parent. *Exception:* a "property group" with its own identity shared across parents IS a concept (Address shared by multiple customers, with its own lifecycle).
- **Hidden intermediate concept heuristic**: multiple columns sharing the same 1:N join pattern that aren't individually meaningful FKs suggest a missing concept — `warehouse_id`, `warehouse_name`, `warehouse_city` on ORDERS means a Warehouse concept is missing.

### Domain-driven design: business concepts first

Model the business domain, then map to physical schema during data loading. Never mirror table or column names — domain naming keeps constraints self-documenting (`sum(Order.amount).per(Customer) <= Customer.credit_limit`) and schema-resilient (renames only touch the loading layer).

| Schema Pattern | Domain Pattern |
|----------------|----------------|
| `TBL_CUST`, `CUSTOMER_TABLE` | `Customer` |
| `CUST_ID` | `id` (on Customer) |
| `ORD_AMT` | `amount` (on Order) |
| `FK_CUST_ID` | `customer` (relationship to Customer) |

### Computed vs. pre-computed data, and business rules

When source data includes pre-computed columns (`total_revenue`, `customer_score`), prefer recomputing in the semantic layer from base facts — the model stays authoritative and auditable, and the derived definition means the same thing for every consumer. Import pre-computed values only when the computation is expensive, needs data outside the model (ML scores, external ratings), or the pre-computed value IS the authoritative source.

```python
# PREFER: recompute from base facts — the derivation encodes a domain rule
LineItem.total_price = model.Property(f"{LineItem} has {Float:total_price}")
model.define(LineItem.total_price((LineItem.unit_price * LineItem.quantity * (1 - LineItem.discount)) * (1 + LineItem.tax_rate)))
Order.revenue = model.Property(f"{Order} has {Float:revenue}")
model.define(Order.revenue(sum(LineItem.total_price).per(Order)))

# OK: import when base facts unavailable or computation is opaque
Customer.credit_score = model.Property(f"{Customer} has {Float:credit_score}")
model.define(Customer.credit_score(TABLE__CUSTOMERS.credit_score)).where(
    Customer.id == TABLE__CUSTOMERS.cust_id)
```

**Judgment call:** not every derivable value needs a canonical definition. Ask whether the calculation is a domain rule that should mean the same thing everywhere — if so, define it; a merely convenient aggregation may not need to live in the model. Authoring classification/tier/flag rules in natural-language terms is `rai-pyrel`.

### Entity count guidance

Entity counts of zero at introspection time are normal — concepts loaded from data or created via `model.define(X.new(...))` populate at runtime; do not flag them as gaps. Reference entities (countries, currencies) may exist without participating in any relationship; only declare mandatory participation when the domain truly requires it.

### Compound identity for multi-key entities

```python
LineItem = model.Concept("LineItem", identify_by={"order": Order, "product": Product})
```

**Decision rule:** compound identity for natural multi-key domain entities (LineItem, Enrollment); cross-product `model.define(X.new(...))` for derived entities that combine concepts.

### Additional concept patterns

- **Value type concepts:** `CustomerID`, `ProductPrice` extend base types for type safety (`{ConceptName}{AttributeName}` naming). Required for reference models; raw types OK for prototyping.
- **Concept creation with identify_by:** three valid patterns — `identify_by=` at creation, separate identity `Property` + `.new()`, or `Concept.identify_by(existing_prop)` for custom reading strings.

See [advanced-modeling.md](references/advanced-modeling.md) for both.

### Use strict mode during development

Set `implicit_properties: false` in `raiconfig.yaml` under the model's config to catch typos and undefined property references at definition time — without it, accessing an undeclared property silently creates one.

---

## Relationship Principles

### Property vs. Relationship: choosing the right connector

`Property` is a subclass of `Relationship`; the only difference is at compile time: **Property automatically enforces a functional dependency (FD)** — all fields except the last are keys, the last field is the unique value. Relationship is multi-valued by default.

**Key principle: the choice is about multiplicity. Property is for many-to-one associations; Relationship is for many-to-many.** This applies regardless of whether the value is a primitive or a concept — a truly functional concept-to-concept FK (each Order has exactly one Customer) should be a Property.

| Aspect | Property | Relationship |
|--------|----------|--------------|
| Primary use | Many-to-one (functional) — scalar attributes and functional FKs | Many-to-many |
| FD enforcement | Automatic — compiler adds uniqueness constraint | None — duplicates allowed |
| Arity | Any (unary, binary, ternary+) | Any |
| Violation behavior | `FDError: Found non-unique values` on duplicate keys | No error — all values stored |

```python
Order.amount = model.Property(f"{Order} has {Float:amount}")
Order.placed_by = model.Property(f"{Order} placed by {Customer:customer}")   # functional FK
Order.is_rush = model.Property(f"{Order} is rush order")                     # unary flag
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}") # ternary with FD

Customer.placed_order = model.Relationship(f"{Customer} placed order {Order}")  # one-to-many inverse
Task.depends_on = model.Relationship(f"{Task} depends on {Task}")                # many-to-many self-ref
```

**Why Property when appropriate:** the FD catches data-quality issues at define time instead of silently producing wrong aggregations, and it carries real performance benefits. Most associations in a data model are functional, so Property is the default once multiplicity is established. The primary failure mode is mismatched cardinality — `FDError: Found non-unique values` is the constraint doing its job. When multiplicity is genuinely uncertain, Relationship tolerates anything, but defaulting to it to avoid establishing multiplicity is discouraged.

**Solver safety:** scalar attributes used as solver variable bounds or coefficients (`capacity`, `cost`, `min_spend`) **must** be Property, not Relationship — the solver's CSV export assumes scalar Properties resolve to one value per entity; Relationship here can raise `AttributeError: 'Table' object has no attribute '_rel'` during solve.

### Properties on relationships (hyper edges)

When data naturally lives on the association itself — a grade on a student-course enrollment, a cost on a route — model it as an N-ary Property where the participating entities are keys and the data is the value:

```python
Route.cost = model.Property(f"{Supplier} to {Warehouse} costs {Float:cost}")
```

The FD rule applies: all fields except the last are keys. If the association carries *multiple* data attributes, use a junction concept instead.

### Many-to-many through junction concepts

When a many-to-many association carries data, create a junction concept (a bare Relationship suffices when it carries none):

```python
Enrollment = model.Concept("Enrollment")
Enrollment.student = model.Property(f"{Enrollment} has student {Student:student}")
Enrollment.course = model.Property(f"{Enrollment} has course {Course:course}")
Enrollment.grade = model.Property(f"{Enrollment} has {Float:grade}")
```

### Additional relationship patterns

| Pattern | Summary | Reference |
|---------|---------|-----------|
| Reading string quality | ≤8 static words, precise verbs, max 3 fields, don't echo owner concept | [advanced-modeling.md](references/advanced-modeling.md) |
| Inverse relationships | `.alt()` for concise inverse declaration | [advanced-modeling.md](references/advanced-modeling.md) |
| Role naming / same-type refs | `{Person:payer}` roles; `.ref()` for same-type instances | [advanced-modeling.md](references/advanced-modeling.md) |
| Constraint vocabulary | Mandatory/optional, subset, exclusion, self-referential, frequency, value-comparison | [constraint-patterns.md](references/constraint-patterns.md) |
| Decomposition checks | Irreducibility, sample-data validation, counterexample — verify ternaries are truly irreducible | [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) |

---

## Data Mapping Guidance

**Snowflake type mapping** (the authority for Step 5 validation and all property declarations):

| Snowflake type | RAI type | Notes |
|---|---|---|
| VARCHAR, TEXT, STRING | `String` | Date-like TEXT columns are still `String` |
| NUMBER with scale > 0 | `Float` (or `Number.size(p,s)`) | Check `NUMERIC_SCALE` |
| NUMBER, INT (scale = 0) | `Integer` | Conceptually-continuous values (e.g. `CAPACITY_MW`) in NUMBER(38,0)? Flag to the user — the DDL may need FLOAT |
| FLOAT, DOUBLE, REAL | `Float` | |
| DATE | `Date` | |
| TIMESTAMP_NTZ / _LTZ / _TZ | `DateTime` | `Date` against a TIMESTAMP column raises `TyperError` |
| BOOLEAN | `Boolean` property or unary `Relationship` | Prefer the unary Relationship when the flag reads naturally ("Order is urgent") |

**Load data** with `model.define(C.new(id=TABLE.key))`; **bind properties and relationships** with `model.define(...).where(...)`. Full data-loading API (CSV, Snowflake, `lookup`, required vs optional columns, boolean flags): `rai-pyrel` [data-loading.md](../rai-pyrel/references/data-loading.md). Minimal worked example: [examples/value_type_fk_resolution.py](examples/value_type_fk_resolution.py).

### Authoritative vs. joinable sources

- **Authoritative source**: the table where the concept's identity is defined (where the PK lives) — use for `model.define(C.new(id=TABLE.key))`.
- **Joinable source**: a table that references the concept via FK — use for relationship binding with `model.define(...).where(...)`.

**Enrichment source selection:** find the authoritative table for the target concept; use the needed column there directly; if the column lives elsewhere, verify a reliable FK join path to the target; if none exists, flag it — the enrichment may need an intermediate relationship first. Mapping from the wrong table produces incorrect or missing data.

### Handling mismatches between data and model

| Mismatch | Strategy |
|----------|----------|
| One table represents multiple concepts | Load the same table into multiple concepts with different `.where()` filters |
| One concept needs data from multiple tables | Load each table, bind with `model.define(...).where(...)` |
| Column has no business meaning | Omit it — not every column needs a property |
| Cryptic column naming | Map to descriptive property names during loading |
| Related concepts with no explicit FK | `model.define(A.rel(B)).where(A.shared_field == B.shared_field)` |

### Subconcept creation from filtered data

When one table contains multiple entity types differentiated by a TYPE column (suppliers, customers, warehouses in one BUSINESS table), create subconcepts filtered at entity creation:

```python
define(_Supplier.new(id=TABLE__BUSINESS.id)).where(TABLE__BUSINESS.type == "SUPPLIER")
define(_Supplier.name(TABLE__BUSINESS.name)).where(_Supplier.id == TABLE__BUSINESS.id)
```

---

## Layering Principles

A single file is fine for starter ontologies. Split into a package when multiple reasoners share the base model, derived logic is reused across 2+ applications, or the file exceeds ~300 lines with distinct loading vs. business-logic sections. One-way dependencies: **core → computed → apps**.

| Layer | Purpose | Contains | Avoids |
|-------|---------|----------|--------|
| **Core** (`<name>/core.py`) | Physical-to-semantic translation | Concept declarations, source-bound properties, structural FKs | Aggregations, business rules |
| **Computed** (`<name>/computed.py`) | Reusable business logic | Derived properties, segmentations, subtypes | App-specific filters, one-offs |
| **Application** (`apps/`) | Feature delivery | Queries, reports, optimization | Redefining concepts or rules |

If you write the same `.where()` filter 3+ times, promote it to a derived concept in the computed layer:

```python
ActiveOrder = model.Concept("ActiveOrder", extends=[Order])
model.define(ActiveOrder(Order)).where(Order.status != "cancelled", Order.ship_date > today)
```

> The package directory name and the `Model(...)` variable name must differ (`sc_model/`, not `model/`) — Python resolves `import model.core` to the directory, shadowing the variable.

---

## Model Gap Identification

Model gaps are ONLY for data that exists in the schema but isn't mapped to the model — check for "Available for PROPERTY/RELATIONSHIP enrichment" columns:

- **Property gaps** (`gap_type="property"`) — unmapped scalar columns (costs, capacities, quantities)
- **Relationship gaps** (`gap_type="relationship"`) — unmapped FK columns (ending in `_ID`), *unless* the FK target is already linked via an existing relationship

Each gap must reference a specific `source_table` and `source_column` — without them the enrichment cannot generate the correct `define()` rule. In relationship gaps, `from_concept` is the concept whose source table contains the FK column; optional `madlib`/`description` fields refine the generated declaration.

| Gap type | Required fields | Example |
|----------|----------------|---------|
| `property` | `concept`, `property_name`, `data_type`, `source_table`, `source_column` | `Product.unit_cost` (float) from `PRODUCTS.UNIT_COST` |
| `relationship` | `from_concept`, `to_concept`, `relationship_name`, `source_table`, `fk_column` | `Order→Customer` via `ORDERS.CUSTOMER_ID` |

**Base model vs. formulation layer:** a proposed "enrichment" with no source table belongs to the formulation layer, not the base model — decision variables, cross-product concepts, computed expressions, and business parameters are formulation constructs, NOT model gaps. (This is about data provenance for classification, not code placement.)

**Same-type multiarity detection:** a multiarity property referencing the same type (`{Stock} and {stock2:Stock} have {covar:float}`) IS the same-type relationship — do not also suggest a relationship gap; only suggest relationship gaps between different concepts.

---

## Enrichment Workflow

**Prerequisite:** the model already loads and queries. If no model exists yet, run the [Greenfield Build Workflow](#greenfield-build-workflow) first.

1. **Identify what the problem needs** — from the problem's `implementation_hint` and `model_gap_fixes`
2. **Classify each gap** — property, relationship, or user-supplied parameter
3. **Check schema for source columns** — every MODEL_GAP fix specifies `source_table` and `source_column`
4. **Apply enrichment** — map columns per [Data Mapping Guidance](#data-mapping-guidance)
5. **Verify** — re-examine the ontology to confirm the problem is now READY

Detailed patterns (relationship promotion, cross-product decision concepts, multi-hop relationships, scenario concepts): [enrichment-patterns.md](references/enrichment-patterns.md). Model inventory and unmapped-data classification: [examination-guidance.md](references/examination-guidance.md). Derived classification/tier/flag properties are authored with `rai-pyrel`.

---

## What's Next

After the ontology validates and queries correctly: surface what problems it can answer with `rai-discovery` (classifies questions by reasoner family and assesses readiness), enrich for the selected problem via the [Enrichment Workflow](#enrichment-workflow), then hand off to the reasoner skill (`rai-prescriptive-problem`, `rai-graph-analysis`, `rai-predictive-modeling`, or `rai-pyrel`).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Schema-driven names (`TBL_CUST`, `ORD_AMT`) | Copying schema names | Business domain names (`Customer`, `amount`) |
| Boolean columns as `String` | Guessing types from names or examples | Derive types from `INFORMATION_SCHEMA.COLUMNS` `DATA_TYPE` |
| `FDError: Found non-unique values` | `Property` used for a many-to-many association | Establish multiplicity — `Relationship` if truly M:N, or fix data quality |
| Modeling every column | No scoping step | Only model columns relevant to scoped questions |
| `model.data()` for large datasets | Treating DataFrames as production-ready | Prototyping only (≤ hundreds of rows); use `model.Table()` |
| Wrong Snowflake table path | Wrong database/schema/table | Verify with `SHOW TABLES IN SCHEMA <db>.<schema>` |
| "Object does not exist" on valid table | Role lacks access | Check `SELECT CURRENT_ROLE()` and `SHOW GRANTS ON <object>` |
| `SnowflakeChangeTrackingNotEnabledException` | `model.Table()` requires change tracking per source table | `data.ensure_change_tracking: true` in `raiconfig.yaml` (needs OWNERSHIP), or `ALTER TABLE ... SET CHANGE_TRACKING = TRUE` per table |
| First query hangs 5-10 min at `Initializing data index` | Cold start: per-table CDC stream creation + logic-engine provisioning | Pre-set `reasoners.logic.name` to a READY engine and pre-enable change tracking — see `rai-setup/references/engine-management.md` |
| Stale-source cleanup takes minutes on re-run | Re-using a model name after changing data bindings | Fresh model name during rapid iteration, or wait |
| Missing `identify_by` on data-backed concepts | Entities created without stable identity | Add `identify_by` or explicit identity `Property` + `.new()` |
| Property chain failure on cross-product concepts | `ProductStoreWeek.week.week_num` → `UninitializedPropertyException` | Store needed values directly as properties on the cross-product concept |
| Proposed concept is a property group | Attribute bundle with no independent identity | Properties on the parent concept |
| Enrichment proposed with no source table | Decision variable misclassified as MODEL_GAP | Formulation layer, not base model |
| Cross-product concept without linking constraints | Entities created unconstrained | `.where()` filter on creation or relationship constraints |
| Wrong source table for enrichment | Joinable source used instead of authoritative | Use the table from `model.define(C.new(id=TABLE.key))` |
| Property chaining in solver expressions | `DecisionConcept.rel.property` in an objective | Denormalize needed properties onto the decision concept |
| Subtype threshold yields 0 or all results | Assumed wrong data scale | Check `min/max/avg` before setting thresholds |
| Model won't load or sync at all | Engine or connection failure, not ontology code | Diagnose with `rai-setup` (connection) and `rai-health` (engine/transaction state) |

---

## Examples

| Pattern | Techniques Demonstrated | File |
|---|---|---|
| Value-type + FK resolution | Value-type concepts, FK resolution with lookup, boolean flags as unary Relationships, computed aggregations | [examples/value_type_fk_resolution.py](examples/value_type_fk_resolution.py) |
| Hierarchy + compound key | Geographic hierarchy chain, compound identity for junction concepts, derived metrics | [examples/geographic_hierarchy_compound_key.py](examples/geographic_hierarchy_compound_key.py) |
| Multi-level hierarchy | Location + time hierarchies, mutually exclusive classification rules | [examples/multi_level_hierarchy_segmentation.py](examples/multi_level_hierarchy_segmentation.py) |
| Derived concept + bridge | Derived concepts from column values, bridge entity, `.alias()` inverse | [examples/derived_concept_bridge_entity.py](examples/derived_concept_bridge_entity.py) |
| Self-referential hierarchy | Self-referential Entity→Entity, identity limited to natural key | [examples/self_referential_bom.py](examples/self_referential_bom.py) |
| Cross-product decision concept | Constrained cartesian via `.where()`, `.ref()` derived properties, generated Period concept | [examples/cross_product_decision_concept.py](examples/cross_product_decision_concept.py) |
| Large-scale bidirectional | 14 tables / 12+ concepts, unary flags, bidirectional inverses, walrus binding | [examples/large_scale_bidirectional.py](examples/large_scale_bidirectional.py) |
| Multi-schema cross-system | 4 source schemas, cross-system entity linking | [examples/multi_schema_cross_system.py](examples/multi_schema_cross_system.py) |
| Pairwise property + ref | Pairwise property, `.ref()` same-type binding, junction concept | [examples/pairwise_property_ref.py](examples/pairwise_property_ref.py) |
| Auxiliary schema enrichment | Auxiliary schema loading, composite-key enrichment, cross-schema lookup | [examples/auxiliary_schema_enrichment.py](examples/auxiliary_schema_enrichment.py) |

---

## Reference files

- Executing Step 2 discovery / EDA (row counts, multiplicity, subtype discovery, graph topology tracing)? See [discovery-queries.md](references/discovery-queries.md)
- Worked greenfield builds end-to-end (Snowflake tables, CSV, junction concepts, self-referential hierarchies, pairwise matrices, portable source paths)? See [build-examples.md](references/build-examples.md)
- Enriching a model for optimization (relationship promotion, cross-products, multi-hop, gap classification)? See [enrichment-patterns.md](references/enrichment-patterns.md)
- Categorization, subtypes, derivation modes, temporal tracking, or semantic stability? See [categorization-and-advanced.md](references/categorization-and-advanced.md)
- Advanced modeling (value types, identity patterns, ternary properties, inverses, role naming, scenario modeling)? See [advanced-modeling.md](references/advanced-modeling.md)
- Model inventory or unmapped data classification? See [examination-guidance.md](references/examination-guidance.md)
- Decomposition quality gates (irreducibility, sample data validation, counterexample)? See [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md)
- Constraint patterns beyond FD (mandatory/optional, subset, exclusion, self-referential, frequency, value-comparison)? See [constraint-patterns.md](references/constraint-patterns.md)
