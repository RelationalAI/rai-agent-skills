# Design rules, rai-orm mapping and Step 10 translation

Examples use a neutral retail schema: `CUSTOMER_DIM`, `CUSTOMER_PROFILE` and `LOYALTY_MEMBER` (all keyed by `CUST_ID`), `ORDERS`, and a sparse `STORE_REGION` table. Substitute the project's own tables.

## Rules and why they exist

These rules target models that an LLM or an ontology subsetter reads to write queries.

| # | Rule | Failure it prevents |
|---|---|---|
| R1 | **One concept per business entity, not per table.** Merge tables whose primary key is the same identifier and that cover most of its values (e.g. `CUSTOMER_DIM` + `CUSTOMER_PROFILE` → `Customer`), with one property per business attribute. | When the same column sits on several concepts, the query writer picks the wrong copy. Table-shaped concepts add needless joins and type errors. |
| R2 | **Coded columns become business-named flags declared as `model.Property`** (`is_active_customer`, `is_not_employee`). Names and meanings come from documented business rules, glossaries or column descriptions. | Raw codes lead to guessed values and empty results. Flags named after columns (`is_actv_cust`) don't match the words in questions. Flags declared as `Relationship` can be invisible to a subsetter. |
| R3 | **Build entities from where their key is complete.** When the only table keyed by an identifier covers a small share of the values used elsewhere, populate the concept from the key column in the well-covered table. | A sparse dimension table gives the entity a stub population, so every question touching it comes back incomplete. This can be detected from the data alone. |
| R4 | **An explicit, well-named link for every join hint, and subtypes where tables share a key** (`LOYALTY_MEMBER` rows are a kind of `Customer`). | SQL can join on any column, but a model can only follow the links it declares. Missing links make questions unanswerable even with the full ontology. |
| R5 | **Fewer, cleaner properties.** Drop constant, all-null and load/audit columns (`load_dt`, `etl_batch_id`) and PII. Readings carry business meaning ("was placed on"). | Hundreds of near-duplicate properties dilute both the subsetter and the query writer. |
| R6 | **Subsetter-friendly.** Links between chosen concepts must travel with them. | A subset that keeps two concepts but drops the link between them makes the join impossible. |

## Evidence precedence

When sources disagree about a column's meaning, code values or polarity, apply this order:

1. **Workload SQL.** How the queries actually filter and join a column (e.g. `actv_cust_ind = 'Y'` in many items).
2. **Column descriptions and data.** Documented meanings and the values that really occur.
3. **Business rules and glossaries.** Prose mappings such as "active customers means `actv_cust_ind = 'N'`".

Rules:
- A business rule that contradicts the workload SQL or the data, uses a code value the column never holds, or names a column that doesn't exist is **not** used as written. Correct it to match the higher-ranked evidence when the fix is unambiguous (e.g. an obvious column-name typo). Otherwise leave the flag unnamed under "Needs meaning".
- List every conflict in the entity plan under "Evidence conflicts": the sources involved, what each says, and which one won.
- Never let a lower-ranked source override a higher one silently.

## What rai-orm v2 does by default

The defaults pull against several rules, which is why this skill exists:

- **One concept per table.** Step 3 turns every table with a key into an entity and every other column into a fact type. Fix: `merge` feedback plus the entity plan.
- **Boolean columns stay binary.** They become `{X} has <column words> {Boolean}` with the raw column name. Unary emission is documented both as `Property` and as `Relationship`. Fix: the flag dictionary, `rename` feedback and the Step 10 rules below.
- **Refactor collapses flag families into an enum** (`flag-explosion`). Fix: a `note` that business flags are intentional, and rejecting those proposals.
- **The workload "may add or promote, never prune".** Fix: `dropped_columns` with a written justification. Expect a `DROPPED_COLUMNS` warning that each justification answers.
- **No key-coverage check.** Fix: `wrong_grain` feedback for R3 entities.
- **Subtypes are only found from TYPE/KIND columns.** Fix: a `note` naming the subtype and its source table.

## Domain notes template

```markdown
# Domain notes: <project>

## Modeling conventions (apply throughout)
1. Model one concept per business entity, not per table. The entity plan below lists which tables
   each concept merges. Bind merged tables through provenance.tables. Keep exactly one property per
   business attribute; when tables repeat a column, bind it once from the most complete table.
2. Model every documented coded column as a unary flag with the business name in the flag
   dictionary, translated as `model.Property` (never `model.Relationship`). Do not collapse these
   flags into enums during refactor.
3. Build each entity from the table or key column where its identifier is complete (see
   "Entity sources"). A sparse dimension table contributes properties, not the population.
4. Add a named fact type for every join hint below, with the reading given. Model listed subtypes
   with `subtype_of`.
5. Do not model the columns in the drop list; record them as dropped_columns with the reason given.
6. Write readings as business statements ("{Order} was placed on {Date}"), never
   "{X} has <column abbreviation>".

## Entity plan
| Concept | Identifier | Population from | Also binds | Notes |
|---|---|---|---|---|

## Entity sources (R3)
- <Entity>: identifier <KEY>, population from <WELL_COVERED_TABLE>.<KEY>
  (<SPARSE_TABLE> covers <n>% of the values; it contributes properties only).

## Subtypes (R4)
| Subtype | Supertype | Source table | Membership rule |
|---|---|---|---|

## Links (R4)
| From | To | Join | Reading |
|---|---|---|---|

## Flag dictionary (R2)
| Flag | Owner | Source condition | Evidence | Reading |
|---|---|---|---|---|
| is_active_customer | Customer | actv_cust_ind = 'Y' | column description: "Y = customer is active" | {Customer} is an active customer |

## Needs meaning
Coded columns with no documented meaning; keep as plain properties for review.

## Drop list (R5)
| Table | Column | Reason |
|---|---|---|
```

## Feedback mapping

Write `feedback.yaml` in the `rai-orm` format. Concept names must match the model's names once they exist. On a first build, the modeling skill resolves them against the entity plan.

```yaml
version: 1
items:
  - id: c-r1-customer
    kind: merge
    concepts: [CustomerDim, CustomerProfile]        # rule R1; target name Customer (see entity plan)
  - id: c-r3-region
    kind: wrong_grain
    concept: Region                                 # rule R3; population from ORDERS.REGION_ID
  - id: c-r4-order-customer
    kind: missing_link
    from: Order
    to: Customer                                    # rule R4; join ORDERS.CUST_ID
  - id: c-r2-active
    kind: rename
    from: actv_cust_ind
    to: is_active_customer                          # rule R2; unary Property
  - id: c-notes
    kind: note
    text: >
      Conventions in domain-notes.md: LOYALTY_MEMBER is subtype LoyaltyMember of Customer;
      drop-list columns are intentionally omitted; flag-dictionary flags must stay unary Properties
      and must not be merged into enums by refactor.
```

| Rule | Feedback kind |
|---|---|
| R1 merge group | `merge` |
| R2 flag | `rename` (raw column → business flag) |
| R3 entity | `wrong_grain` |
| R4 join hint | `missing_link` |
| R4 subtype, R5 drops, "keep flags" | `note` |

Holdout items never go into feedback. `rai-orm` keeps feedback about holdout items sealed.

## Step 10 translation rules

These apply when the emitter is `manual:step-10`. Check the PyRel syntax against `rai-pyrel-coding` for the pinned version.

```python
# R1: one concept per entity
Customer = model.Concept("Customer", identify_by={"cust_id": Integer})

# R3: population from the complete key column, not the sparse dimension table
Region = model.Concept("Region", identify_by={"region_id": Integer})

# R4: named link on the owning concept (a Property travels with Order in a subset: R6)
Order.customer = model.Property(f"{Order} was placed by {Customer:customer}")
Customer.region = model.Property(f"{Customer} lives in {Region:region}")

# R4: subtype for a table sharing the supertype's key
LoyaltyMember = model.Concept("LoyaltyMember", extends=[Customer])

# R2: unary flag as Property, business name and reading
Customer.is_active_customer = model.Property(f"{Customer} is an active customer")
# Populate in the bindings/sources file, e.g.:
# model.where(Customer.filter_by(cust_id=src.CUST_ID), src.ACTV_CUST_IND == "Y").define(Customer.is_active_customer())

# R5: business reading
Order.placed_on = model.Property(f"{Order} was placed on {Date:placed_on}")
```

- Every flag-dictionary flag is a unary `model.Property`. Use `model.Relationship` only for genuinely many-to-many associations.
- Entity-to-entity links are a `model.Property` on the owning (many) side when functional. Add the inverse only when the workload needs that direction.
- Names are snake_case business words, with no raw column tokens such as `ind`, `cd`, `nbr`, `dt`, `flg` or `typ`. Pass project abbreviations to `lint_model.py --abbrev` (e.g. `--abbrev cust,actv,ord`).
- Keep negated flags (`is_not_employee`) only when documented business rules define them. Otherwise express negation in queries with `model.not_(...)`.

## Lint checks

| Finding | Level | Rule |
|---|---|---|
| Unary flag declared as `Relationship` | error | R2 |
| Load/audit or PII property | error | R5 |
| Boolean-valued property (`{Boolean:x}`) | warning | R2 |
| Raw-column tokens in a name or reading | warning | R2/R5 |
| Same attribute on unrelated concepts (subtype chains collapsed) | warning | R1 |
| Concept with no link or subtype edge | warning | R4/R6 |
| Entity link declared as `Relationship` | warning | R6 |
| Concept with more than `--max-properties` declarations | warning | R5 |

A model emitted straight from a denormalized schema typically shows hundreds of raw-token warnings and many `Relationship` flag errors. Expect most findings to clear after the merge, flag and drop feedback is applied.
