# Failure classes

One class per failed item. Classify from evidence: the difference between the two results, or the element of the SQL that the PyRel could not reach. The class decides where the repair goes.

## `translation`

**Signal:** the model has everything needed; the PyRel was wrong (wrong member, wrong aggregate, missing filter, wrong output columns).
**Repair:** rewrite the PyRel. No model change. Retry inside the per-item cap.
**Check before choosing another class:** can a correct PyRel be written against the model as it is, without a workaround? If yes, it is `translation`.

## `missing-element`

**Signal:** a table, column or join in the SQL has no counterpart in the model: no object type, no fact type, or no relationship between two concepts that the SQL joins.
**Repair:** add it to the YAML.
- A missing join: add the fact type the join stands for. Run the inclusion probe first (SRP Step 5); record the rate in provenance. A join whose probe fails (few values match) is not a relationship; leave the item as residual.
- A dropped column: bind it, or record why it stays dropped.

## `grain`

**Signal:** counts or sums differ by a consistent factor, or the PyRel returns the union of several tables where the SQL reads one. Typical causes:
- one concept is fed by several tables whose row sets differ, and the SQL reads one of them;
- the concept's reference scheme is coarser than the table's row grain, so rows collapse;
- the reference scheme is finer than the grain the workload groups by, so the same thing appears several times.

**Repair:** in the YAML, make the table's own grain reachable. Options, in order of preference:
1. Give the table's grain its own entity type (reference scheme = the table's smallest unique column set, checked on the data) and relate it to the coarser concept.
2. Where one concept must stay merged, add one unary fact type per source table (*"Concept appears in TABLE"*) so the rows of one table can be selected.

State the repair as a rule over all concepts with that shape, and apply it to all of them, not only to the one the item touched.

## `binding`

**Signal:** the model's structure is right but entity or fact counts differ from the table: rows are lost or duplicated between table and concept. Typical cause: a NULL in an identifying column handled differently when entities are created and when properties are attached.
**Repair:** in the data binding, not the YAML. Compare, per table and concept, the number of distinct key tuples in the table with the number of entities; per bound column, non-NULL rows with entities carrying the property. Fix every binding that shows the same pattern.

## `derivation`

**Signal:** the SQL computes something (a ratio, a CASE bucket, a date part) that several items use, and the model has no derived fact type for it, so every rewrite repeats the expression, and some get it wrong.
**Repair:** add a derived fact type (`derivation: derived` with `derivation_rule`) when the digest shows the expression in two or more items, or when a pair gives it a business name. A one-off expression is `translation`, not a model defect.

## `naming`

**Signal:** the element exists, but the rewrite did not find it: the reading or role name is a raw column name, or two members have names that cannot be told apart. Shows up as a `translation` failure that repeats across items on the same element.
**Repair:** improve the reading or role name in the YAML, using a term from the documentation or the digest. Never rename to echo one question.

## `semantics`

**Signal:** results differ only in rows with NULLs, in duplicates, or in rows without a partner (outer versus inner join); or the SQL counts rows where the PyRel counts entities.
**Repair:** usually the rewrite (make the optional part optional; count the right thing). It is a model defect only when the model cannot express the row-level reading at all, in which case it is `grain`.

## Not failures of the model

- **`inexpressible`** — the SQL uses a construct with no PyRel counterpart in the installed version. Record the construct. Do not bend the model to imitate it.
- **`oracle-error`** — the SQL fails on the data, or returns different results on two runs (no ORDER BY with LIMIT, random functions, current-date functions). Record and exclude from the rates.
