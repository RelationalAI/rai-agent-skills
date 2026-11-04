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

**Overview:** Scope the questions → dump the source schema with `rai explore schema` → identify concepts with identities → identify relationships and properties → validate the design against the schema → generate code → validate with queries. The [Design Principles](#concept-design-principles) sections are the authority the workflow steps apply; enrichment and gap classification extend an already-working model.

---

## Quick Reference

| Decision | Choose | Pattern |
|----------|--------|---------|
| Has own PK / identity? | **Concept** | `model.Concept("Name", identify_by={"id": Type})` |
| Fact/event table, no PK at all? | **Concept keyed by row** | `model.Concept("Sale", identify_by={"row": src})` — never a compound of data columns |
| Scalar value on entity? | **Property** | `model.Property(f"{Concept} has {Type:name}")` |
| Categorical value (status, type, brand) shared across tables, grouped or filtered on, or with attributes of its own? | **Enumeration concept** keyed by the value | `model.Concept("Status", identify_by={"code": String})` — see [Categorical values](#categorical-values-enumeration-concept-or-string) |
| Code column + description column for the same thing? | **Enumeration concept** keyed by the code | Description is a property of it — never map only the description |
| Functional FK (each A → one B)? | **Property** | `model.Property(f"{Order} placed by {Customer:customer}")` |
| Many-to-many link? | **Relationship** | `model.Relationship(f"{A} links to {B}")` |
| Boolean flag? | **Unary Relationship** | `model.Relationship(f"{Concept} is active")` |
| Fundamental category of a concept? | **Subtype** | `model.Concept("Supplier", extends=[Business])` |
| Recurring `.where()` filter? | **Subtype** | `model.Concept("Sub", extends=[Parent])` |
| Many-to-many with data? | **Junction concept** | Concept with compound identity (yours to establish — `pk_candidates` is single-column only) |

**Layer structure:** Core (source→semantic) → Computed (derived logic) → Application (queries, reports)

**Naming:** Singular business nouns for concepts (`Customer`), lowercase for properties (`amount`), related concept name for relationships (`customer`).

---

## Greenfield Build Workflow

Start from the business domain — what concepts exist, what questions must the model answer — then find data mappings. Domain-first modeling produces better models than table-to-concept mapping because user intent drives concept selection rather than table structure.

Document your findings and decisions at each step so others can follow the reasoning.

**Keep the run lean.** Every tool call re-sends everything already in context, so a build's cost is turns × context, and anything printed once is paid for on every later turn:
- **Query large artifacts, never print them whole.** `schema.json`, validation output and the reference files run to tens or hundreds of KB. Print the slice a step needs — a short script over `schema.json`, `tail`/`grep` over a log, the one section of a reference (`grep -n '^#'` its headings first).
- **Batch each step's questions into one call** — one script that answers all of a step's checks, not one call per table or column.
- **Run SQL probes through a session from `raiconfig.yaml`** — `create_config().get_session(SnowflakeConnection)`, as in [discovery-queries.md](references/discovery-queries.md) — and put a step's probes in one `UNION ALL` query. Do not read `raiconfig.yaml` or the library source to build a connection of your own.
- **Write each file once, then run it in the same call.** Write `<domain>.py` whole — model and validation queries together, not appended in pieces — and run it in that call (a heredoc followed by `python <domain>.py 2>&1 | tail -n 80`). Fix failures with targeted edits, not a rewrite.
- **Wait, don't poll.** Give long commands (the schema scan, the validation run) a timeout long enough to finish in the foreground; if one is backgrounded, wait for it in one blocking call (a loop that sleeps until its output file shows it finished), not a check per turn.
- **Bound the deploy wait.** `rai models deploy --wait` has no timeout flag and can block for up to an hour on a first refresh that never starts. Give the call a timeout of about 10 minutes; if it expires, read the refresh state directly with `CALL <db>.<schema>_META.REFRESH_STATUS();` (see `rai-deployment`) instead of waiting again: report `error` when it is `FAILED`, `DEPLOY_FAILED`, or `NEVER_RUN` with a `SUSPENDED` task; while it is `RUNNING`, re-read it in one blocking loop (30s or more between reads), not one call per turn.

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

The out-of-scope column is also the Step 2 cost lever: pass `--table NAME` (repeatable, once per table) to restrict discovery to the in-scope tables. On a very large or very wide schema, start at `--depth structure` for a zero-scan overview, then re-run at `--depth profile` on the scoped set.

### Step 2 — Discover source data

**Data loading decision:** Use `model.Table()` for Snowflake-backed data (any size, production-ready). Use `model.data()` for prototyping with DataFrames only (≤ hundreds of rows) or inline scenario data not in Snowflake. For connection setup, see `rai-setup`.

**Snowflake or DuckDB — run `rai explore schema`.** One invocation produces the whole inventory: column types (with the RAI type to declare), PK candidates, FK candidates with multiplicity, value distributions, numeric ranges, and optional graph topology.

```bash
rai explore schema --database <DB> --schema <SCHEMA> --depth profile -o schema.json
```

> **Keep `schema.json` on disk through Step 7, and query it — never `cat` it.** Every subsequent step reads from it, but on a wide schema it runs to hundreds of KB: load it in a short script and print only the tables and fields the step needs. Output is deterministic (byte-identical across runs on unchanged data), and the key set is the same at every depth — keys a shallower depth did not compute are `null`, never absent.

> **Budget minutes, not seconds.** Give the call a timeout of 600s or more. If it is backgrounded anyway, wait for it in one blocking call — `until grep -q '✓' <output-file> || ! pgrep -f 'rai explore schema' >/dev/null; do sleep 15; done` with a 600s timeout, then read the file's tail (the scan prints no `✓` if it fails) — not one check per turn. A turn that ends while waiting ends the run, and the scan dies with the session.

**Depth controls cost, not shape:**
- **`profile`** — one aggregate scan per table. Required for PK candidates, multiplicity, `null_rate`, `numeric_range`, and value distributions, so it is the floor for Steps 3-5. Use it unless you have a reason not to.
- **`full`** — adds the graph-topology block. Use for graph / network-shaped data, which you can spot before running it: a table whose columns are mostly FKs into one other table, or a name like `*_EDGES` / `FOLLOWS` / `CONNECTIONS` / `*_LINKS`.
- **`structure`** — metadata only, zero table scans. Safe on a schema of any size; supplies types but no data-derived fields. Pair with `--table` on very large schemas (see Step 1), then re-run at `profile` on the scoped set.

**What to read** (field-by-field contract: [schema-json.md](references/schema-json.md)):

| Field | Use |
|---|---|
| `tables[].columns[].rai_type` | The RAI type to declare. Read it directly — never infer a type from the column name. `null` means the column's type is unmapped, not missing; fall back to the [type mapping table](#data-mapping-guidance). |
| `tables[].pk_candidates` | Identity for Step 3. The first entry is almost always the real PK; later entries are unique *by coincidence* (`EMAIL`, `PHONE`). Single-column only — composite identity stays your call. |
| `tables[].row_count` | Live `COUNT(*)` at `profile`+ — populated for views and zero-row tables too, so it is always a real expected value. |
| `tables[].columns[].value_distribution` | Enumeration-concept, subtype and enum candidates (fires at `distinct_count <= 20`). **Alphabetical on the wire — sort by count descending yourself to rank values.** For a share-of-rows figure, divide by `row_count`. |
| `tables[].columns[].numeric_range` | `{min, max}` — the real data scale, for Step 5 thresholds. |
| `fk_candidates[].multiplicity_class` | `1:1` / `N:1` / `M:N`. Drives Step 4's Property-vs-Relationship choice. |
| `graph_topology` | Present at `--depth full` when a table carries 2+ FKs to the same target — a strong hint to model that table as a `Relationship`, not a concept. Non-zero `broken_edges` means the graph has gaps; surface them to the user. |
| `warnings[]` | Degradations and undecidable inferences. **Read every entry** — an ambiguous FK is reported here rather than guessed at, and how you respond differs by warning. See [schema-json.md](references/schema-json.md) § Reading `warnings[]`. |

**CSV / DataFrame sources** have no command path — profile inline, then map columns per `rai-pyrel` [data-loading.md](../rai-pyrel/references/data-loading.md):

```python
df.dtypes                         # → RAI types: the mapping table below is the authority here
df.isna().mean()                  # null rates
df[col].value_counts().head(20)   # enum / subtype candidates
df.select_dtypes("number").agg(["min", "max"])   # threshold scale
```

**Identify data shape.** Source tables arrive in one of two shapes, classified per table:
- **Raw events / measurements** — one row per occurrence; metrics must be *derived* downstream from the raw rows. Signals: high `row_count`, a high-`distinct_count` timestamp column, `N:1` FKs, a populated `value_distribution` on a status column.
- **Pre-aggregated statistics** — one row per entity, pair, or time bucket carrying already-computed values (including long-form `(entity_i, entity_j, value)` matrices). Signals: low `row_count`, `*_RATE` / `*_AVG` / `*_TOTAL` / `*_SCORE` names, identity that is a tuple of FKs with no surrogate id. Bind directly; do not re-aggregate — worked example: the pairwise value matrix in [build-examples.md](references/build-examples.md).

**For graph / network data**, the command's topology block counts edges between *tables*. To trace tiers by a node's TYPE *column value* — which reveals hidden layers the table-level view cannot — run the one query in [discovery-queries.md](references/discovery-queries.md) before Step 3.

### Step 3 — Identify concepts

Work domain-first: brainstorm business entities broadly — both obvious entities (tables with clear PKs) and implied entities (referenced but not directly represented) — then map each to an authoritative source. Reject any concept that cannot be grounded. Apply [Concept Design Principles](#concept-design-principles).

Define each concept's identity from its authoritative source's `pk_candidates`. Take the **first** entry — later entries are usually unique by coincidence, so do not promote `EMAIL` or `PHONE` to an identity column. Every concept needs an identity; where the source declares none, that identity is the source row, not a compound you assemble from its columns (see Identity hygiene below).

**Check for subtypes:** If `value_distribution` shows TYPE/CATEGORY columns that partition a concept into fundamentally different kinds (e.g. `BUSINESS_TYPE` with values `Supplier` and `Customer`), model these as subtypes using `extends` — when each kind carries its own properties or relationships, not for every enum column. If you find yourself writing the same `.where()` filter repeatedly, promote it to a named subtype. See [categorization-and-advanced.md](references/categorization-and-advanced.md).

**Check categorical columns:** for each text column with a `value_distribution` or a name ending `_CD` / `_CODE` / `_TYPE` / `_STATUS` / `_CATEGORY`, look for the same column in other tables and for a sibling description column in its own table. `fk_candidates` will not show a value shared by two tables when neither table is keyed by it, so compare `columns[]` across tables yourself, and confirm that the value sets overlap — a shared name alone is not evidence. Decide each column with [Categorical values](#categorical-values-enumeration-concept-or-string).

**Validate:** each concept maps to at least one authoritative source, has a clear identity, and the set is orthogonal (see [Concept orthogonality](#concept-orthogonality)).

**Identity hygiene.** `pk_candidates` reports single-column candidates only — composite uniqueness is out of the command's scope, so compound identity is yours to establish. Prefer minimal identity (1-2 natural-key fields). If the only natural identity you can find is >3 fields, pause: (a) **is there a surrogate ID in `pk_candidates` you overlooked?** (b) is this really a measurement that belongs as a Relationship payload on a smaller concept? (c) **does the source declare no key at all?** — if so, use row identity, below.

**Identity when the source declares no key.** A table with no PK and no unique column — typically a fact or event table — gets its identity from the source row, never from a compound of its data columns:

```python
Sales = model.Concept("Sales", identify_by={"row": sales_src})   # sales_src = model.Table(...)
model.define(Sales.new(row=sales_src))        # required; without it the model builds and returns nothing
s = Sales.lookup(row=sales_src)
```

`Table` subclasses `Concept` and its instances are rows, so this yields exactly one entity per physical record.

**Never synthesise identity from data columns.** A compound of dimension columns is only a key if something guarantees one row per combination, and for an event table nothing does. Two real events sharing a material, plant and period are then the same entity, and they silently merge — no error, wrong totals. The same failure follows from making the fact an n-ary Relationship instead of a Concept: a Relationship holds a *set* of tuples, so rows agreeing on every argument collapse.

*Anti-pattern — the cardinality argument.* "3 materials × 2 plants × 5 months = 30 combinations, 13 rows, so the compound is unique" does not follow. Row count below the size of the dimension space says nothing about whether two rows share a cell. Reject this reasoning wherever it appears, including in your own.

*Probing distinctness is not enough either.* `COUNT(*) = COUNT(DISTINCT cols)` establishes that today's rows differ, not that the source guarantees it; tomorrow's load can collide and the model starts losing rows with no schema change to notice. Use a declared key when the source has one, row identity when it does not.

### Step 4 — Identify relationships and properties

**Choose Property or Relationship per link** by reading `fk_candidates[].multiplicity_class` from `schema.json`: `N:1` or `1:1` → Property (scalar attributes AND functional FKs); `M:N` → Relationship, and the source table is a junction. Also use a Relationship for one-to-many modelled from the parent side, multi-field associations, and boolean flags. A `null` `multiplicity_class` means there was nothing to classify from (empty table, or an all-NULL FK column) — establish multiplicity yourself before choosing. The full decision rule, FD semantics, and failure modes are in [Relationship Principles](#relationship-principles).

Then assign remaining columns as properties of their parent concepts, grouped by topic. Not every column needs a property — omit columns with no business meaning for the scoped questions.

**Anti-bundle rule.** Each scalar attribute should be its own `Property`. Packing more than two unrelated scalars into a single `Relationship` makes them un-queryable (you can't filter or aggregate on one field). Reserve multi-field Relationships for genuinely co-occurring data (e.g. a date range `{Promotion} active from {DateTime:start} to {DateTime:end}`).

**Same-type-slot disambiguation.** When a `Relationship` has two slots of the same concept type, the slots are roles and must be distinguished: either split into two `Property` declarations whose attribute names are the roles, or label both slots — `f"{Lane} from {Location:origin} to {Location:destination}"`. Without this, `model.define(...)` silently binds both slots to whichever column you list first. Verify with a Step 7 query that origin ≠ destination on at least one row.

**Constraints are user-asserted, data-proposed.** As you assign links, note the candidate constraints the Step 2 `schema.json` suggests (mandatory roles, disjunctions, frequency and cardinality bounds) and confirm each with the user in guided mode — or record it as an assumption in one-shot mode. Signal-to-question mapping: [constraint-patterns.md](references/constraint-patterns.md).

### Step 5 — Validate design

Validate the proposed design against source data before coding:

| Check | What to confirm |
|-------|-----------------|
| Identity columns | Exist in source and uniquely identify rows |
| Associations | Valid FK or join key exists; multiplicity determined (1:1 / N:1 → Property; 1:N / M:N → Relationship) |
| Properties | Source column exists with compatible data type |
| Concept grounding | Every concept maps to an authoritative source |
| Orthogonality | No two concepts represent the same entity set |
| Threshold scale | For any planned threshold (subtype or flag), read the column's `numeric_range` (`{min, max}`) first — assuming 0-100 when the data is 0-10 captures nothing or everything |
| Constraint intent | Every proposed constraint and bound is user-confirmed (guided) or recorded as an assumption (one-shot) — data proposes, the user asserts ([constraint-patterns.md](references/constraint-patterns.md)) |
| Fact decomposition | Each relationship is irreducible and survives sample-data + counterexample checks — apply [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) to steps 3-5 output |

**Type validation is the gate.** Verify every property's RAI type against `columns[].rai_type` in `schema.json` — a single mismatch causes a `TyperError` at query time that blocks ALL queries on the model with no indication of which property failed. `rai_type` already encodes the mapping rules, so the check is a comparison, not a derivation. Cross-check `data_type` on the cases where the column *name* misleads: date-like columns stored as TEXT or TIMESTAMP_NTZ (`String` / `DateTime`, not `Date`), `NUMBER` with scale > 0 (`Float`), BOOLEAN (→ `Boolean` property or unary Relationship), and numeric IDs (a `PHONE` column may be NUMBER — the schema dictates, not the name). Where `rai_type` is `null`, derive the type from the [type mapping table](#data-mapping-guidance) and flag the column to the user.

### Step 6 — Generate code

> **GATE: Do not proceed until Step 5 type validation is complete.** Take every property type from `columns[].rai_type` in `schema.json` — not from column names, CSV samples, or example ontologies. Use the [type mapping table](#data-mapping-guidance) only where `rai_type` is `null`.

Follow conventions in `rai-pyrel`. Worked end-to-end builds (Sources class, FK binding, junction concepts, pairwise matrices) are in [build-examples.md](references/build-examples.md) — when generating your first build or when a binding pattern is unclear, read the one example that matches (its `## Example N` headings name the patterns), not the whole file. Put everything in a single file named after the domain (`supply_chain.py`, `fraud.py`) — easiest to iterate on. When the model grows (multiple reasoners, derived layers, shared logic), split into a package per [Layering Principles](#layering-principles).

> **If you split into a package:** never name the directory `model/` when your `Model` variable is also called `model` — Python resolves `import model.xxx` to the directory, shadowing the variable. Use a domain-specific name (`sc_model/`, `fraud_model/`).

### Step 7 — Validate with queries

Add validation queries to the bottom of `<domain>.py` — in the same write as the model (Step 6) — and fix any import errors, query errors or empty results before considering the ontology complete. Have them print one compact line per check (`<check>  expected  actual  OK|FAIL`), not whole DataFrames, so a single run's output shows every failure. For query syntax, see `rai-pyrel`. Import aggregates with `from relationalai.semantics.std import aggregates`.

**7a — Spot-check property types** for each `BOOLEAN`, `DATE`, and `NUMBER` `data_type` in `schema.json` — the three most common sources of silent `TyperError`.

**7b — Count instances per concept** to confirm data binding loaded rows:

```python
df = model.select(aggregates.count(MyConcept).alias("count")).to_df()
# Expect: count matches the source table's `row_count` in schema.json. Zero means binding failed.
```

Run it for **every** concept, not a sample. An *error* here — not just a zero — means the model is not done, and the cause is often not the concept the error names: a single rule the SQL reasoner rejects makes every concept in the model unqueryable. The most common cause is a fact defined through its own negation (see [Common Pitfalls](#common-pitfalls)). The model still imports cleanly, so this step is the first place it shows.

At `--depth profile` and above, `row_count` is a live `COUNT(*)` and is populated for every table — including views and genuinely empty ones — so there is always a real number to compare against. A concept whose source `row_count` is `0` should load zero instances; that is a match, not a failure.

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
for c in (schema[n] for n in scoped_concepts): # targeted; print(schema) dumps every property of a wide model
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

**Create a concept** when the thing has its own identity, its own properties, and participates in multiple relationships. **Add a property** when the value only makes sense in the context of its parent. **Decision rule:** if you would give it a primary key in a relational schema — including a lookup table the source never built — it is a concept; if it only ever describes its parent, it is a property. A categorical column on someone else's table can be either: apply the next section.

### Categorical values: enumeration concept or String

Make a categorical value (status, type, category, brand) an **enumeration concept** — a concept identified by the value, or by its code — when any of these hold; otherwise keep it a `String` property. A categorical is a label from a small set that many rows share. Identifiers, columns that hold another table's key (Step 4), measures, dates and free text are not categoricals, even when `value_distribution` fires on them in a small table.

| Signal | Choose | Why |
|---|---|---|
| The same value set appears in 2+ tables or sources, with or without a lookup table | Enumeration concept | One hub links every table that carries it; `String` copies can only be joined by matching text at query time |
| The scoped questions group or filter by it | Enumeration concept | The concept holds every value, including values no fact row uses yet |
| It has attributes of its own (a tier, a description, a sort order) | Enumeration concept | The attributes need an owner |
| Display-only: read back, never grouped, filtered or joined | `String` | No concept earns its keep |
| Free text, or too messy to normalise (many spellings of one value) | `String` | Flag it to the user; record the choice as an assumption in one-shot mode |
| Two-valued flag (`Y`/`N`, `*_IND`) | Unary `Relationship` | A flag is a fact about its parent, not a category |

**Code + description pair.** When a table carries a code column and a description column for the same thing (`STATUS_CD` + `STATUS_DESC`), a lookup table has been folded into it: model an enumeration concept identified by the code, with the description as a property. Never map only the description — two codes can share a description, and other tables reference the code. Worked example: `MachineType` in [examples/cross_product_decision_concept.py](examples/cross_product_decision_concept.py).

Populate the concept from every table that carries the value, so values with no fact rows still exist. Prefer it to a `model.Enum`-typed property for values loaded from data: rows whose value is not a declared member drop silently out of member comparisons. Finding candidates in `schema.json`, populating the concept when no lookup table exists, and messy values: [categorization-and-advanced.md](references/categorization-and-advanced.md) § Enumeration concepts without a lookup table.

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

`schema.json`'s `pk_candidates` covers single-column identity only, so a multi-key entity will show **no** usable candidate — an empty or coincidental list is the signal to look for compound identity, not a sign the table lacks identity. Before committing to one, check `pk_candidates` once more for a surrogate ID that makes the compound key unnecessary.

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
| Constraint vocabulary | Mandatory/optional, inclusive-or/xor, subset, exclusion, self-referential, frequency, cardinality, value-comparison | [constraint-patterns.md](references/constraint-patterns.md) |
| Decomposition checks | Irreducibility, sample-data validation, counterexample — verify ternaries are truly irreducible | [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md) |

---

## Data Mapping Guidance

**Snowflake type mapping.** Which role this table plays depends on which Step 2 path you took:

- **Command path (`schema.json` in hand) — fallback only.** `columns[].rai_type` is the authority for Step 5 validation and every property declaration. Use this table just for the columns where `rai_type` is `null` (an unmapped source type such as VARIANT, OBJECT, ARRAY, GEOGRAPHY, or VECTOR), and when reading legacy hand-written code.
- **CSV / DataFrame path — primary source.** There is no `schema.json` and therefore no `rai_type` at all, so this table *is* the type authority: map each `df.dtypes` entry through it yourself, and apply the same name-versus-type scrutiny Step 5 describes.

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
| Column holds another concept's key, no declared FK | `model.define(A.rel(B)).where(A.ref_field == B.key_field)` |
| Two concepts share a categorical value, no FK and no lookup table | Enumeration concept keyed by the value, linked from both — not a direct A→B link, which asserts a relationship the data does not have ([Categorical values](#categorical-values-enumeration-concept-or-string)) |

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
| Rows silently lost from a fact table | Concept keyed on its dimension columns, or the fact declared as an n-ary Relationship — both make attribute values the identity, so duplicate-valued rows merge | `identify_by={"row": src}`; see Identity hygiene |
| "N combinations possible, fewer rows, so the key is unique" | Cardinality argument — invalid for event tables, which permit repeats within a cell | Reject it; row count says nothing about collisions |
| Deduplicated the source to remove "duplicate" rows | Read repeated rows as a data-quality defect when they were distinct events | Ask whether two events could legitimately share every value; for sales, shipments, readings, payments the answer is yes |
| Every query fails, including on concepts that look correct | A fact defined through its own negation — e.g. `X.flag(False)` where `not_(X.flag)` — is recursive negation; the SQL reasoner rejects the whole model, not just that rule | Apply the default where the value is read, with the `\|` fallback (`X.flag \| False`, see `rai-pyrel`), or omit it and let absence mean false |
| Schema-driven names (`TBL_CUST`, `ORD_AMT`) | Copying schema names | Business domain names (`Customer`, `amount`) |
| Boolean columns as `String` | Guessing types from names or examples | Read `columns[].rai_type` from `schema.json` |
| Ranked the wrong top value | Trusted `value_distribution`'s wire order | It is alphabetical — sort by count descending before reading a ranking |
| Ambiguous FK investigated at length, or silently dropped | Ignored `warnings[]` | Dispatch on the warning — see [schema-json.md](references/schema-json.md) § Reading `warnings[]` |
| No model written — turn ended waiting on discovery | `rai explore schema` timed out and was backgrounded | Wait in one blocking call until its output file shows `✓` or the scan exits; timeout ≥600s |
| A run takes 60+ turns and millions of context tokens | `schema.json` or a reference printed whole; the model written in appended pieces, then run and read back in separate calls; a background job checked once per turn | Query slices; write each file once and run it in the same call; wait in one blocking call — see Keep the run lean |
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
| Shared categorical (status, brand) is a `String` on each concept | Treated "a column on someone else's table" as always a property | Enumeration concept keyed by the value, populated from every table that carries it ([Categorical values](#categorical-values-enumeration-concept-or-string)) |
| Only the description of a code + description pair is mapped | Kept the readable column | Enumeration concept identified by the code; the description is its property |
| Proposed concept is a property group | Attribute bundle with no independent identity | Properties on the parent concept |
| Enrichment proposed with no source table | Decision variable misclassified as MODEL_GAP | Formulation layer, not base model |
| Cross-product concept without linking constraints | Entities created unconstrained | `.where()` filter on creation or relationship constraints |
| Wrong source table for enrichment | Joinable source used instead of authoritative | Use the table from `model.define(C.new(id=TABLE.key))` |
| Property chaining in solver expressions | `DecisionConcept.rel.property` in an objective | Denormalize needed properties onto the decision concept |
| Subtype threshold yields 0 or all results | Assumed wrong data scale | Read the column's `numeric_range` before setting thresholds |
| Model won't load or sync at all | Engine or connection failure, not ontology code | Diagnose with `rai-setup` (connection) and `rai-health` (engine/transaction state) |

---

## Examples

| Pattern | Techniques Demonstrated | File |
|---|---|---|
| Value-type + FK resolution | Value-type concepts, FK resolution with lookup, boolean flags as unary Relationships, computed aggregations | [examples/value_type_fk_resolution.py](examples/value_type_fk_resolution.py) |
| Hierarchy + compound key | Geographic hierarchy chain, compound identity for junction concepts, derived metrics | [examples/geographic_hierarchy_compound_key.py](examples/geographic_hierarchy_compound_key.py) |
| Multi-level hierarchy | Location + time hierarchies, mutually exclusive classification rules | [examples/multi_level_hierarchy_segmentation.py](examples/multi_level_hierarchy_segmentation.py) |
| Derived concept + bridge | Enumeration concepts from column values (no lookup table), bridge entity, `.alias()` inverse | [examples/derived_concept_bridge_entity.py](examples/derived_concept_bridge_entity.py) |
| Self-referential hierarchy | Self-referential Entity→Entity, identity limited to natural key | [examples/self_referential_bom.py](examples/self_referential_bom.py) |
| Cross-product decision concept | Enumeration concept from a code + description pair shared by two sources, constrained cartesian via `.where()`, `.ref()` derived properties, generated Period concept | [examples/cross_product_decision_concept.py](examples/cross_product_decision_concept.py) |
| Large-scale bidirectional | 14 tables / 12+ concepts, unary flags, bidirectional inverses, walrus binding | [examples/large_scale_bidirectional.py](examples/large_scale_bidirectional.py) |
| Multi-schema cross-system | 4 source schemas, cross-system entity linking | [examples/multi_schema_cross_system.py](examples/multi_schema_cross_system.py) |
| Pairwise property + ref | Pairwise property, `.ref()` same-type binding, junction concept, enumeration concept shared by two concepts | [examples/pairwise_property_ref.py](examples/pairwise_property_ref.py) |
| Auxiliary schema enrichment | Auxiliary schema loading, composite-key enrichment, cross-schema lookup | [examples/auxiliary_schema_enrichment.py](examples/auxiliary_schema_enrichment.py) |

---

## Reference files

- Reading `schema.json` — every field, the warning taxonomy and what each warning means for your next action, and an annotated sample? See [schema-json.md](references/schema-json.md)
- Tracing graph tiers by a node's TYPE column value (the one discovery query `rai explore schema` does not cover)? See [discovery-queries.md](references/discovery-queries.md)
- Worked greenfield builds end-to-end (Snowflake tables, CSV, junction concepts, self-referential hierarchies, pairwise matrices, portable source paths)? See [build-examples.md](references/build-examples.md)
- Enriching a model for optimization (relationship promotion, cross-products, multi-hop, gap classification)? See [enrichment-patterns.md](references/enrichment-patterns.md)
- Categorical columns as enumeration concepts (shared values, code + description pairs, no lookup table), subtypes, derivation modes, temporal tracking, or semantic stability? See [categorization-and-advanced.md](references/categorization-and-advanced.md)
- Advanced modeling (value types, identity patterns, ternary properties, inverses, role naming, scenario modeling)? See [advanced-modeling.md](references/advanced-modeling.md)
- Model inventory or unmapped data classification? See [examination-guidance.md](references/examination-guidance.md)
- Decomposition quality gates (irreducibility, sample data validation, counterexample)? See [fact-decomposition-and-validation.md](references/fact-decomposition-and-validation.md)
- Constraint patterns beyond FD (mandatory/optional, inclusive-or/xor, subset, exclusion, self-referential, frequency, cardinality, value-comparison)? See [constraint-patterns.md](references/constraint-patterns.md)
