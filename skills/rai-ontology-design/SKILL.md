---
name: rai-ontology-design
description: Covers RAI domain modeling decisions — concepts, relationships, data mapping, model composition, enrichment, and advanced modeling patterns. Use when reviewing, enriching, or evolving an existing ontology — not for greenfield starter builds (see rai-build-starter-ontology).
---

# Ontology Design
<!-- v1-STABLE -->

## Summary

**What:** Domain modeling decisions — concepts, relationships, properties, data mapping, model composition, and model enrichment for optimization.

**When to use:**
- **As design authority** — consulted by `rai-build-starter-ontology` during greenfield builds for concept, relationship, and property design decisions
- **Enriching an existing model** — adding properties, relationships, or subtypes to a model that already loads and queries
- **Reviewing or evolving a model** — assessing model gaps, examining ontology inventories, applying advanced patterns
- **Working with modeler exports** — understanding and extending models exported from the RAI modeler (latest or legacy format)
- Mapping schema columns to model properties and relationships
- Assessing model gaps for optimization (READY / MODEL_GAP / DATA_GAP)
- Designing cross-product decision concepts for optimization

**When NOT to use:**
- Building a first ontology from scratch — start with `rai-build-starter-ontology`, which uses this skill as its design authority
- PyRel syntax reference (imports, types, f-string patterns, stdlib) — see `rai-pyrel-coding`
- Optimization formulation (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Query construction (select, aggregation, joins) — see `rai-querying`

**Overview:**
1. Analyze source tables (PKs, FKs, soft-joins, business purpose)
2. Identify and validate concepts with their identities (brainstorm, validate against data, define keys)
3. Identify relationships (FKs, shared keys, business links)
4. Assign remaining columns as properties
5. Define subtypes for recurring filters (optional)

---

## Quick Reference

| Decision | Choose | Pattern |
|----------|--------|---------|
| Has own PK / identity? | **Concept** | `model.Concept("Name", identify_by={"id": Type})` |
| Scalar value on entity? | **Property** | `model.Property(f"{Concept} has {Type:name}")` |
| Link to another concept? | **Relationship** | `model.Relationship(f"{A} links to {B}")` |
| Boolean flag? | **Unary Relationship** | `model.Relationship(f"{Concept} is active")` |
| Fundamental category of a concept? | **Subtype** | `model.Concept("Supplier", extends=[Business])` |
| Recurring `.where()` filter? | **Subtype** | `model.Concept("Sub", extends=[Parent])` |
| Many-to-many with data? | **Junction concept** | Concept with compound identity |

**Layer structure:** Core (source→semantic) → Computed (derived logic) → Application (queries, reports)

**Naming:** Singular business nouns for concepts (`Customer`), lowercase for properties (`amount`), related concept name for relationships (`customer`).

---

## Design Decision Sequence

These are the design decisions that underlie any ontology, whether built from scratch via `rai-build-starter-ontology` or evolved incrementally. They are listed in dependency order — each phase depends on the one before it. For a complete greenfield build workflow, use `rai-build-starter-ontology`.

Start from the business domain — what concepts exist, what questions must the model answer — then find data mappings. Domain-first modeling produces better models than table-to-concept mapping because user intent drives concept selection rather than table structure.

0. **Scope first (for new models)** -- Define 1-3 concrete questions the model must answer and explicitly list what is out of scope. Keep the first version to ~10-15 must-have properties. A tight scope keeps the model small enough to implement and validate without rework. Example:

   | Goal | In scope | Out of scope |
   |---|---|---|
   | Identify delayed orders | Orders, shipments, delay timestamps | Returns, carrier contracts, inventory |

1. **Analyze sources** -- Understand each table's business purpose, identify likely PKs (identity/auto-increment columns, NOT NULL, `id`/`*_id` patterns), infer FKs (columns whose names match other tables' PKs), and spot soft-joins (shared codes or categories across tables). Note `STATUS`/`TYPE`/`CATEGORY` columns with repeated string values — these should be typed enum concepts, not raw strings. Pay attention to column nullability, identity flags, and column comments — these are stronger signals than column names alone.

2. **Identify and validate concepts with their identities** -- Brainstorm the business entities present in the data. Think broadly: include both obvious entities (tables with clear PKs) and implied entities (referenced but not directly represented). For each proposed concept, map it to at least one authoritative source table -- if it cannot be grounded, reject it. Then define the concept's identity from the authoritative source's PK columns. Identity is intrinsic to concept definition, not a separate step: a concept without an identity key is not yet a concept. Check that proposed concepts are orthogonal (see Concept Orthogonality below).

3. **Identify links** -- Find relationships between two or more concepts. Look for FK columns, shared keys, and business associations. Each link should connect independently meaningful concepts.

4. **Identify properties** -- Assign remaining columns as attributes of their parent concepts, grouped by topic for readability. Not every column needs a property -- omit columns with no business meaning for the problem.

5. **Define subtypes for recurring filters (optional)** -- If you find yourself writing the same `.where()` filter repeatedly (e.g., active customers, open orders), promote the filter to a named subtype using `extends`. This makes the filter reusable and queryable as a first-class concept. See Categorization Patterns in [categorization-and-advanced.md](references/categorization-and-advanced.md).

6. **Validate data scale before setting thresholds** -- When defining subtypes or computed flags with numeric thresholds (e.g., "high traffic" locations, "high value" customers), explore the actual data distribution first. Run `model.select(aggs.min(X.prop), aggs.max(X.prop), aggs.avg(X.prop)).to_df()` to understand the value range before choosing a cutoff. Assuming a 0-100 scale when the data is actually 0-10 (or vice versa) produces zero results or captures everything.

**Key pattern: identify then validate.** Brainstorm broadly in steps 2 and 3, then validate against the schema. This avoids premature commitment to a modeling choice that doesn't survive contact with the data.

**Quality gates:** After steps 3-5, apply the checks from [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) (irreducibility, sample data validation, counterexample) to catch structural errors early.

---

## Concept Design Principles

### When to create a new concept vs. adding a property

**Create a new concept** when the thing has its own identity, its own properties, and participates in multiple relationships. A Customer, a Product, and an Order are each concepts because they are independently meaningful.

**Add a property** when the value only makes sense in the context of its parent concept. A Customer's credit limit, an Order's amount, and a Product's weight are properties because they describe, not identify.

**Decision rule:** If you would give the thing a primary key in a relational schema, it is a concept. If it would be a column on someone else's table, it is a property.

### Concept orthogonality

Before committing to a set of concepts, verify they are truly independent:

- **No-overlap test**: If two proposed concepts always have the same entity set (every instance of A is an instance of B and vice versa), merge them into one concept. Two names for the same thing is not two concepts.
- **Not-a-property-group test**: If a proposed concept is just a bundle of attributes that belong to another concept and has no independent identity, make them properties on the parent concept instead.

**Exception to the property-group test:** If the "property group" has its own identity and is shared across multiple parent entities, it IS a concept. For example:
- Address columns (street, city, zip) on a Customer table -- if each customer has exactly one address and addresses are never shared, these are Customer properties.
- Address as a shared entity (multiple customers at the same address, addresses with their own lifecycle) -- this is a separate Address concept with its own identity.

**Hidden intermediate concept heuristic:** If multiple columns in a table share the same 1:N join pattern to another concept but aren't individually meaningful FK references, a concept is likely missing between them. For example: an ORDERS table with `warehouse_id`, `warehouse_name`, `warehouse_city` all describing the same entity suggests a missing Warehouse concept. Those columns should be Warehouse properties, not Order properties.

### Domain-driven design: business concepts first

Model the business domain, then map to physical schema during data loading. Never mirror table or column names directly. This keeps constraints self-documenting (`sum(Order.amount).per(Customer) <= Customer.credit_limit`) and schema-resilient (column renames only affect the data-loading layer).

| Schema Pattern | Domain Pattern |
|----------------|----------------|
| `TBL_CUST`, `CUSTOMER_TABLE` | `Customer` |
| `CUST_ID`, `customer_id` | `id` (on Customer concept) |
| `ORD_AMT`, `order_amount` | `amount` (on Order concept) |
| `FK_CUST_ID` | `customer` (relationship to Customer) |

Use singular business nouns for concepts (Customer, Order, Product), lowercase descriptive names for properties (amount, quantity, due_date), and the related concept name or role for relationships (customer, supplier, destination).

### Computed vs. pre-computed data

When source data includes pre-computed columns (e.g., `total_revenue`, `avg_order_value`, `customer_score`), prefer recomputing in the semantic layer from base facts rather than importing the pre-computed values. This keeps the model authoritative and auditable -- you can trace any derived value back to its inputs.

**When to recompute:** The base facts exist in the model and the computation is straightforward (sums, averages, counts, ratios). Define the computation as a derived property or aggregation.

**When to import pre-computed:** The computation is expensive, requires data not in the model (ML scores, external ratings), or the pre-computed value IS the authoritative source (e.g., a vendor-provided price index).

```python
# PREFER: recompute from base facts
Customer.total_spend = model.Property(f"{Customer} has {Float:total_spend}")
model.define(Customer.total_spend(sum(Order.amount).per(Customer)))

# OK: import when base facts unavailable or computation is opaque
Customer.credit_score = model.Property(f"{Customer} has {Float:credit_score}")
model.define(Customer.credit_score(TABLE__CUSTOMERS.credit_score)).where(
    Customer.id == TABLE__CUSTOMERS.cust_id
)
```

### Capturing business rules in the semantic layer

Define domain logic and business rules as derived properties in the model so that they are computed consistently and consumers cannot alter their semantics. This is the primary reason to prefer recomputation over importing pre-computed values — it consolidates important definitions in one place.

These rules don't have to be complex. `LineItem.total_price` captures how discounts and tax are applied. `Order.revenue` captures how revenue aggregates from line items. What matters is that the calculation encodes domain meaning worth standardizing.

**Judgment call:** Not every derivable value needs a canonical definition. RAI ontologies are generally more interested in precisely defined relationships between entities than in providing aggregate grains. Ask whether the calculation is a domain rule that should mean the same thing everywhere — if so, define it; if it's just a convenient aggregation, it may not need to live in the model.

```python
# Domain rule: how line item price is calculated (discounts + tax)
LineItem.total_price = model.Property(f"{LineItem} has {Float:total_price}")
model.define(LineItem.total_price((LineItem.unit_price * LineItem.quantity * (1 - LineItem.discount)) * (1 + LineItem.tax_rate)))

# Domain rule: how order revenue aggregates from line items
Order.revenue = model.Property(f"{Order} has {Float:revenue}")
model.define(Order.revenue(sum(LineItem.total_price).per(Order)))
```

### Entity count guidance

**Entity counts of zero at introspection time are normal.** Concepts loaded from data or created via `model.define(X.new(...))` get entities at runtime. If a concept has properties defined but zero entities, it will be populated at runtime -- do not flag it as a gap.

**Independent concepts:** Reference entities (countries, currencies, categories) may exist without participating in any relationship. Do not flag zero-relationship entities as errors. Only declare mandatory role constraints when the business domain truly requires participation.

### Compound identity for multi-key entities

When an entity is uniquely identified by multiple properties, use compound identity:

```python
LineItem = model.Concept(
    "LineItem",
    identify_by={"order": Order, "product": Product}
)
```

**Decision rule:** Use compound identity for natural multi-key domain entities (LineItem, OrderProduct). Use cross-product `model.define(X.new(...))` for derived entities that combine multiple concepts.

### Additional concept patterns

- **Value type concepts:** `CustomerID`, `ProductPrice` extend base types for type safety. Use `{ConceptName}{AttributeName}` naming. Required for reference models; raw types OK for prototyping.
- **Concept creation with identify_by:** Three valid patterns — `identify_by={"field": Type}` at creation, `Property` + `.new()` (modeler style), `Concept.identify_by(existing_prop)` for custom reading strings.

See [advanced-modeling.md](references/advanced-modeling.md) for examples of both.

### Use strict mode during development

Set `implicit_properties: false` in your `raiconfig.yaml` under the model's config section to catch typos and undefined property references at definition time. Without this, accessing an undeclared property silently creates a new one (default is `true`).

---

## Relationship Principles

### Property vs. Relationship: choosing the right connector

`Property` is a subclass of `Relationship` (literally `class Property(Relationship): pass`). The only difference is at compile time: **Property automatically enforces a functional dependency (FD)** — all fields except the last are keys, the last field is the unique value. Relationship is multi-valued by default.

**Key principle: The choice between Property and Relationship is about multiplicity. Property is for many-to-one associations. Relationship is for many-to-many associations.**

**Critical v1 rule: In a Property, all fields except the last must be keyed.** The compiler enforces a functional dependency -- every combination of key fields maps to exactly one value (the last field). Violating this (e.g., putting a non-key field before the value) produces `FDError` at define time.

Establishing multiplicity is a fundamental modeling activity. When an association is many-to-one (functional), use Property. When it is many-to-many, use Relationship. This applies regardless of whether the value is a primitive or a concept — a concept-to-concept FK that is truly functional (each Order has exactly one Customer) should be a Property.

| Aspect | Property | Relationship |
|--------|----------|--------------|
| Primary use | Many-to-one (functional) associations — both scalar attributes and functional FKs | Many-to-many associations |
| Cardinality | Many-to-one (enforced FD) | Any multiplicity (multi-valued) |
| FD enforcement | Automatic — compiler adds uniqueness constraint | None — allows duplicate values per key |
| Arity | Any (unary, binary, ternary+) | Any (unary, binary, ternary+) |
| Violation behavior | `FDError: Found non-unique values` if data has duplicates for the same key | No error — all values are stored |

```python
# Property: many-to-one associations (concept → primitive value OR concept → concept FK)
Order.amount = model.Property(f"{Order} has {Float:amount}")
Site.name = model.Property(f"{Site} has {String:name}")
Order.placed_by = model.Property(f"{Order} placed by {Customer:customer}")  # functional FK

# Property: unary flag (functional — each entity is or isn't)
Order.is_rush = model.Property(f"{Order} is rush order")

# Property: ternary with FD (Food × Nutrient → qty is functional)
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")

# Relationship: many-to-many associations (no FD)
Customer.placed_order = model.Relationship(f"{Customer} placed order {Order}")  # inverse (one-to-many)
Task.depends_on = model.Relationship(f"{Task} depends on {Task}")  # many-to-many self-reference
```

**Why Property is recommended when appropriate:** Property enforces a global constraint that the association is many-to-one, catching data quality issues at define time rather than silently producing wrong aggregations. It also provides performance benefits — without FDs, programs are "heinously slow" (Chris Granger). Most associations in a data model are functional — each entity has exactly one name, cost, quantity, assigned customer, etc. — so Property should be the default choice when multiplicity is established.

**The primary failure mode** is mismatched cardinality expectations. If two rules define the same Property with overlapping keys but different values, you get `FDError: Found non-unique values`. This is the constraint doing its job — better than silently producing wrong aggregations.

**Decision rule:** Establish the multiplicity of the association. Use Property for many-to-one (functional) associations. Use Relationship for many-to-many associations. Both support any arity (unary, binary, ternary+).

**When multiplicity is uncertain:** Relationship is more flexible — it accepts any cardinality and will not error on unexpected duplicates. However, defaulting to Relationship to avoid thinking about multiplicity is discouraged. Establishing multiplicity is a fundamental modeling activity and using Property where appropriate provides both performance benefits and data quality enforcement.

**Solver safety:** Scalar attributes used as solver variable bounds or coefficients (e.g., `min_spend`, `max_spend`, `seg_len`, `slope`, `capacity`, `cost`) **must** be Property, not Relationship. The solver's CSV export assumes scalar Properties resolve to a single value per entity. Using Relationship for these can cause `AttributeError: 'Table' object has no attribute '_rel'` during solve.

### Properties on relationships (hyper edges)

Sometimes data naturally lives on the relationship between entities rather than on either entity alone -- for example, a marriage date between two people, a grade on a student-course enrollment, or a shipping cost on a supplier-warehouse route. In v1, model these as N-ary Properties or Relationships where the participating entities are keys and the data is the value:

```python
# Marriage date between two people
Marriage.date = model.Property(f"{Person:spouse1} married {Person:spouse2} on {Date:date}")

# Shipping cost on a route
Route.cost = model.Property(f"{Supplier} to {Warehouse} costs {Float:cost}")
```

The FD rule applies: all fields except the last are keys, the last field is the value. If the association carries multiple data attributes, use a junction concept instead (see Many-to-many through junction concepts above).

### Many-to-many through junction concepts

When two concepts have a many-to-many relationship and the association carries data, create a junction concept. If the many-to-many link has no attributes, a Relationship suffices.

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
| Property grouping | Group by topic; `short_name` in modeler exports | [advanced-modeling.md](references/advanced-modeling.md) |
| Inverse relationships | `.alt()` for concise inverse declaration | [advanced-modeling.md](references/advanced-modeling.md) |
| Role naming | Named roles when same concept appears twice: `{Person:payer}` | [advanced-modeling.md](references/advanced-modeling.md) |
| Same-type references | `.ref()` for relating two instances of the same type | [advanced-modeling.md](references/advanced-modeling.md) |
| Constraint vocabulary | Mandatory/optional, subset, exclusion, self-referential, frequency, value-comparison | [constraint-patterns.md](references/constraint-patterns.md) |
| Decomposition checks | Irreducibility, minimum key span — verify ternaries are truly irreducible | [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) |

---

## Ontology Examination

For guidance on producing a descriptive inventory of a model and classifying unmapped data, see [examination-guidance.md](references/examination-guidance.md).

---

## Data Mapping Guidance

### Loading and binding data to the model 

**Snowflake type mapping** (see also `rai-build-starter-ontology` for the full validation workflow):

| Snowflake type | RAI base type |
|---|---|
| VARCHAR, TEXT | `String` |
| NUMBER(p,s) where s > 0 | `Float` (or `Number.size(p,s)` for precision) |
| NUMBER, INT (no scale) | `Integer` |
| FLOAT, DOUBLE | `Float` |
| DATE | `Date` |
| TIMESTAMP_NTZ, TIMESTAMP | `DateTime` |
| BOOLEAN | `Boolean` property, or unary `Relationship` for flag-style |

Always verify column types against `INFORMATION_SCHEMA.COLUMNS` before writing property declarations. A mismatch causes a `TyperError` at query time with no detail about which property failed. Let the schema dictate the type, not the column name.

**Load data** using `model.define(C.new(id=TABLE.key))`, **bind properties and relationships** using `model.define(...).where(...)`. For complete data loading API reference (CSV, Snowflake, `filter_by`, `model.where`, required vs optional columns, boolean flags), see `rai-pyrel-coding` [data-loading.md](../rai-pyrel-coding/references/data-loading.md). For a minimal worked example, see [examples/value_type_fk_resolution.py](examples/value_type_fk_resolution.py).

**Key rules:**
- `Property` for many-to-one (functional) associations. `Relationship` for many-to-many associations.
- Domain names for concepts and properties, not schema names
- Define inverses for navigable relationships — see Additional relationship patterns below

### Authoritative vs. joinable sources

Each concept has two kinds of source table relationships:

- **Authoritative source**: The table where the concept's identity is defined (where the PK lives). Use this for `model.define(C.new(id=TABLE.key))`.
- **Joinable source**: A table that references the concept via FK but does not define it. Use this for relationship binding with `model.define(...).where(...)`.

**Why this matters for enrichment:** When a MODEL_GAP fix needs to map a new property, the `source_table` must be the authoritative source for the target concept (or a table with a reliable FK to it). Mapping from the wrong table produces incorrect or missing data. In the schema-to-ontology example above, CUSTOMERS is authoritative for Customer (used in `model.define(C.new(...))`), while ORDERS is joinable (references Customer via FK).

**Decision rule for enrichment source selection:**
1. Find the authoritative table for the target concept (the table used in `model.define(C.new(id=TABLE.key))`)
2. Check if the needed column exists in that table -- use it directly
3. If the column is in a different table, verify there is a reliable join path (FK relationship) to the target concept
4. If no reliable join path exists, flag it -- the enrichment may require an intermediate relationship first

### Handling mismatches between data and model

| Mismatch | Strategy |
|----------|----------|
| One table represents multiple concepts | Load the same table into multiple concepts with different `.where()` filters |
| One concept needs data from multiple tables | Load each table, then bind with `model.define(...).where(...)` |
| Column has no business meaning for the problem | Omit it from the model; not every column needs a property |
| Column naming is cryptic | Map to descriptive property names during loading |
| Data has no explicit FK but concepts are related | Use `model.define(A.relationship(B)).where(A.shared_field == B.shared_field)` |

### Subconcept creation from filtered data

When a single table contains multiple entity types, create subconcepts filtered by a type column:

```python
_Business = Concept("Business")
_Business.id = Property(f"{_Business} has id {String:id}")

_Supplier = Concept("Supplier")
_Supplier.id = Property(f"{_Supplier} has id {String:id}")
_Supplier.name = Relationship(f"{_Supplier} named {String:name}")

# Filter by type column during entity creation
define(_Supplier.new(id=TABLE__BUSINESS.id)).where(TABLE__BUSINESS.type == "SUPPLIER")
define(_Supplier.name(TABLE__BUSINESS.name)).where(_Supplier.id == TABLE__BUSINESS.id)
```

This pattern is common in modeler exports where a single `BUSINESS` table contains suppliers, customers, manufacturers, and warehouses differentiated by a `TYPE` column.


---

## Layering Principles

### When to split into layers

A single file is fine for starter ontologies and small projects. Split into a package when:
- Multiple reasoners (solver + graph) share the same base model
- Derived/computed logic is reused across 2+ applications
- The file exceeds ~300 lines and has distinct data-loading vs. business-logic sections

### Layer Responsibilities

When splitting, structure models in three layers with one-way dependencies: **core → computed → apps**.

> **Constraint:** The package directory name and the `Model(...)` variable name must differ. If `model = Model("my_project")`, the package cannot be called `model/`. Python resolves `import model.core` to the directory, shadowing the variable. Use a domain-specific directory name (e.g., `sc_model/`, `fraud_model/`).

| Layer | Purpose | Contains | Avoids |
|-------|---------|----------|--------|
| **Core** (`<name>/core.py`) | Physical-to-semantic translation | Concept declarations, properties bound to source columns, structural FK relationships | Aggregations, derivations, business rules |
| **Computed** (`<name>/computed.py`) | Reusable business logic | Derived properties, segmentations, calculated metrics, entity subtypes | Application-specific filters or one-off calculations |
| **Application** (`apps/`) | Feature delivery | Queries, aggregations, parameterized reports, optimization | Redefining concepts or business rules |

**Decision rule:** Raw source data mapping → Core. Reused across 2+ apps or fundamental business semantics → Computed. Everything else → Application.

### Computed Layer Design Principles

Add computed concepts only when they represent reusable derived semantics, not one-off application logic. If you write the same `.where()` filter 3+ times, promote it to a derived concept:

```python
ActiveOrder = model.Concept("ActiveOrder", extends=[Order])
model.define(ActiveOrder(Order)).where(Order.status != "cancelled", Order.ship_date > today)
```

**Rules:**
- Core owns identity and source-column bindings.
- Computed derives from core facts rather than binding directly to source columns.
- Prefer recomputing from base facts; see `Computed vs. pre-computed data` above.

---

## Model Gap Identification

Model gaps are ONLY for data that exists in the schema but isn't mapped to the model. Check the schema info:

**If there are "Available for PROPERTY enrichment" or "Available for RELATIONSHIP enrichment" columns:**
- Property gaps (gap_type="property") -- unmapped scalar columns (costs, capacities, quantities)
- Relationship gaps (gap_type="relationship") -- unmapped FK columns (ending in _ID)
- Each gap should reference a specific source_table and source_column from the schema info — without these, the enrichment tool cannot generate the correct `define()` rule

**How to detect relationship gaps:**
1. Check schema info for "Available for RELATIONSHIP enrichment (FK columns)" entries
2. Check "Relationship Semantics" in model context -- if the FK target concept is already linked via an existing relationship, it's NOT a gap
3. For each unmapped FK relevant to the problem, emit a relationship gap

**model_gap_fix fields by gap type:**

| Gap type | Required fields | Example |
|----------|----------------|---------|
| `property` | `concept`, `property_name`, `data_type`, `source_table`, `source_column` | `Product.unit_cost` (float) from `PRODUCTS.UNIT_COST` |
| `relationship` | `from_concept`, `to_concept`, `relationship_name`, `source_table`, `fk_column` | `Order→Customer` via `ORDERS.CUSTOMER_ID` |

Relationship gaps also accept optional `madlib` (PyRel reading-string, e.g., `{Order} placed by {customer:Customer}`) and `description`. `from_concept` is the concept whose source table contains the FK column.

**Base model vs. formulation layer:** If a proposed "enrichment" has no source table, it belongs to the formulation layer, not the base model. Decision variables, cross-product concepts, computed expressions, and business parameters are formulation constructs -- NOT model_gaps.

| Layer | Examples | Has source table? |
|-------|----------|-------------------|
| **Base model** | Customer, Site, Order with properties from schema | Yes -- loaded from data |
| **Formulation** | FulfillmentAssignment, production_quantity, total_cost expression | No -- created during problem setup |

Note: This distinction is about **data provenance for gap classification**, not code placement. Formulation-layer Property *definitions* still go in `define_model()`; only solver registrations go in `define_problem()`.

For concrete examples, see [enrichment-patterns.md](references/enrichment-patterns.md).

**Same-type multiarity detection:** When a concept has a multiarity property referencing the same type (e.g., `{Stock} and {stock2:Stock} have {covar:float}` or `{Node} connects to {node2:Node} with {distance:float}`), this IS the same-type relationship — do NOT suggest an additional relationship gap. The multiarity property pattern handles pairwise operations between instances of the same type. Only suggest relationship gaps between DIFFERENT concepts.

---

## Enrichment Workflow

**Prerequisite:** The model must already load and query successfully. If no model exists yet, use `rai-build-starter-ontology` first.

After problem selection, if feasibility is MODEL_GAP, enrich the ontology before formulation:

1. **Identify what the problem needs** — from the problem's `implementation_hint` and `model_gap_fixes`
2. **Classify each gap** — property (unmapped scalar column), relationship (unmapped FK column), or parameter (user-supplied value)
3. **Check schema for source columns** — every MODEL_GAP fix must specify `source_table` and `source_column` from the database schema
4. **Apply enrichment** — map columns to properties/relationships using the patterns in Data Mapping Guidance
5. **Verify** — re-examine the ontology to confirm gaps are filled and the problem is now READY

For detailed enrichment patterns, property vs relationship mapping, and source column requirements, see [enrichment-patterns.md](references/enrichment-patterns.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `FDError: Found non-unique values` | Used `Property` for a many-to-many association | Establish actual multiplicity — switch to `Relationship` if truly many-to-many, or fix data quality if it should be many-to-one |
| Schema-driven naming (`TBL_CUST`, `CUST_ID`) | Mirroring table/column names | Use business domain names (`Customer`, `id`) |
| Missing `identify_by` on data-backed concepts | Entities created without stable identity | Add `identify_by` or explicit `Property` + `.new()` |
| Property chain failure on cross-product concepts | `ProductStoreWeek.week.week_num` → `UninitializedPropertyException` | Store values directly as properties on the cross-product concept |
| Proposed concept is actually a property group | Bundle of attributes with no independent identity | Make them properties on the parent concept |
| Enrichment proposed with no source table | Decision variable or computed expression misclassified as MODEL_GAP | Belongs in formulation layer, not base model |
| Duplicate enrichment for formulation-layer concepts | Decision variables misclassified as MODEL_GAP | Decision concepts, computed expressions, and parameters are formulation, not base model |
| Cross-product concept without linking constraints | Entities created but not constrained to relationships | Add `.where()` filter on entity creation or relationship constraints |
| Wrong source table for enrichment | Mapping from joinable source instead of authoritative source | Find the authoritative table (used in `model.define(C.new(id=TABLE.key))`) |
| Property chaining in solver expressions | Accessing `DecisionConcept.relationship.property` in objective | Denormalize needed properties directly onto the decision concept |
| Subtype threshold yields 0 or all results | Assumed wrong data scale (e.g., 0-100 vs 0-10) | Always check `min/max/avg` of the property before setting threshold values |

---

## Examples

| Pattern | Techniques Demonstrated | File |
|---|---|---|
| Value-type + FK resolution | Value-type concepts, FK resolution with filter_by, boolean flags as unary Relationships, computed aggregations | [examples/value_type_fk_resolution.py](examples/value_type_fk_resolution.py) |
| Hierarchy + compound key | Geographic hierarchy chain, compound identity for junction concepts, derived metrics layered on base model | [examples/geographic_hierarchy_compound_key.py](examples/geographic_hierarchy_compound_key.py) |
| Multi-level hierarchy | Multi-level location + time hierarchies, entity classification with mutually exclusive conditional rules | [examples/multi_level_hierarchy_segmentation.py](examples/multi_level_hierarchy_segmentation.py) |
| Derived concept + bridge | Sources class, derived concepts from column values, bridge entity, `.alias()` for inverse | [examples/derived_concept_bridge_entity.py](examples/derived_concept_bridge_entity.py) |
| Self-referential hierarchy | Many concepts, individual Properties, self-referential Entity→Entity, identity limited to natural key | [examples/self_referential_bom.py](examples/self_referential_bom.py) |
| Cross-product decision concept | CSV data, cross-product decision concepts, constrained cartesian via `.where()`, `.ref()` derived properties, generated Period concept | [examples/cross_product_decision_concept.py](examples/cross_product_decision_concept.py) |
| Large-scale bidirectional | Large-scale (14 tables, 12+ concepts), unary flags, bidirectional inverses, self-referential caller/callee, walrus operator binding | [examples/large_scale_bidirectional.py](examples/large_scale_bidirectional.py) |
| Multi-schema cross-system | Multi-schema sources (4 domains), individual Properties, boolean flags as unary Relationships, cross-system entity linking | [examples/multi_schema_cross_system.py](examples/multi_schema_cross_system.py) |
| Pairwise property + ref | Binary/pairwise property, `.ref()` for same-type binding, junction concept for many-to-many | [examples/pairwise_property_ref.py](examples/pairwise_property_ref.py) |
| Auxiliary schema enrichment | Auxiliary schema loading, composite key enrichment, filter_by for cross-schema binding | [examples/auxiliary_schema_enrichment.py](examples/auxiliary_schema_enrichment.py) |
| Modeler export (legacy) | Legacy `initialize()` format, `_Concept` prefix, `Property("{...}")` strings, standalone `define()`, `.where()` binding | [examples/modeler_legacy_export.py](examples/modeler_legacy_export.py) |

---

## Reference files

- Enriching a model for optimization (relationship promotion, cross-products, multi-hop relationships, gap classification)? See [enrichment-patterns.md](references/enrichment-patterns.md)
- Categorization, subtypes, derivation modes, temporal tracking, or semantic stability? See [categorization-and-advanced.md](references/categorization-and-advanced.md)
- Advanced modeling (value types, identity patterns, ternary properties, inverse relationships, role naming, scenario modeling)? See [advanced-modeling.md](references/advanced-modeling.md)
- Modeler exports or model composition? See [modeler-and-composition.md](references/modeler-and-composition.md)
- Model inventory or unmapped data classification? See [examination-guidance.md](references/examination-guidance.md)
- Decomposition quality gates (irreducibility, sample data validation, counterexample)? See [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md)
- Constraint patterns beyond FD (mandatory/optional, subset, exclusion, self-referential, frequency, value-comparison)? See [constraint-patterns.md](references/constraint-patterns.md)
