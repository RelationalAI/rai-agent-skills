---
name: rai-orm-from-workload
description: Extracts modeling evidence from a workload — SQL query logs, natural-language questions, or question+SQL pairs — into a workload digest (join edges, row-grain keys, enum-like filter columns, repeated expressions, business terms and their alignment to columns) that the ORM modeling skills consume as proposals. Use before modeling when the user has queries or questions about the data — not for the modeling itself (rai-orm-from-schema, rai-orm-from-text), for checking a finished model against the workload (rai-orm-verify), or for choosing the route (rai-orm).
---

# Workload Evidence for ORM Modeling
<!-- v1-SENSITIVE -->

## Summary

**What:** Reads a workload and writes `workload.digest.yaml`: counts and structure that a schema alone does not show. The digest is an optional input of `rai-orm-from-schema` (SRP) and `rai-orm-from-text` (CSDP). Everything in it is evidence for a *proposal*; nothing in it is a model decision.

**When to use:**
- A schema declares few or no keys, and the queries show which joins are real
- Tables look alike and the queries show the row grain people actually use
- The business uses names that differ from the column names, and questions or pairs show them
- Before `rai-orm-verify`, so the model is not built blind and then repaired

**When NOT to use:**
- Building the model — see `rai-orm-from-schema` or `rai-orm-from-text`
- Checking that a finished model can answer the workload — see `rai-orm-verify`
- Choosing which ORM skill applies — see `rai-orm`
- Writing PyRel queries — see `rai-pyrel-coding`

**Overview:**
1. Take the workload file and name its modality
2. Parse the SQL side (`sql`, `pairs`) into structural evidence
3. Read the question side (`questions`, `pairs`) into terms
4. For `pairs`, align terms to the structure of their own SQL
5. Write the digest; report what could not be parsed
6. Hand the digest to the modeling skill

## Quick Reference

**What each modality yields:**

| Evidence | `sql` | `questions` | `pairs` | Consumed at |
|---|---|---|---|---|
| Table and column usage | yes | — | yes | SRP Step 8 (order of review), never to prune |
| Join edges with column pairs | yes | — | yes | SRP Step 5 (inclusion probe), Step 7 (`missing-fk`) |
| Row-grain keys (GROUP BY, COUNT DISTINCT, DISTINCT) | yes | — | yes | SRP Step 2 (reference scheme check), Step 7 |
| Enum-like filter columns | yes | — | yes | SRP Step 5 (distinct-value probe) |
| Repeated expressions | yes | — | yes | SRP Step 3 (derived fact type candidates) |
| Business terms and synonyms | — | yes | yes | SRP Step 3 (readings, role names); CSDP Step 1 |
| Term → column / join / expression alignment | — | — | yes | SRP Step 3 and Step 6c |

**Three rules:**
- **Counts and structure only.** No SQL literal and no full question text is written to the digest. Terms are noun or verb phrases, never a name, id, date or other data value.
- **Add or promote, never prune.** A table or column the workload never touches stays in the model. A workload is a sample of use, not a definition of the domain.
- **Evidence, not decisions.** The digest proposes nothing by itself; the modeling skill turns evidence into proposals under its own "propose, never assert" rule.

## Inputs and Outputs

**Inputs:**

| Modality | Accepted shapes |
|---|---|
| `sql` | A `.sql` file of statements; a query-history export (CSV or JSON with a query-text column); a JSON list with a `sql` field |
| `questions` | A text file with one question per line; a JSON list with a `question` field |
| `pairs` | A JSON or CSV list where each item has both a question and its SQL (`question`/`sql`, or `input`/`output`) |

Optional: the SQL dialect, when it is not the schema's dialect.

If part of the workload is held back to evaluate the model later, only the remaining part is an input here.

**Output:** `workload.digest.yaml`, format in [`references/digest-format.md`](references/digest-format.md).

## Instructions

**Required dependencies:** none for the digest. The schema, when there is one, is read only to resolve table and column names.

### Step 1 — Modality

Name the modality from the file's shape: SQL without questions is `sql`; questions without SQL is `questions`; both in each item is `pairs`. A file that mixes items with and without SQL is processed as `pairs` for the items that have both, and the rest as their own modality; record the three counts.

### Step 2 — SQL side (`sql`, `pairs`)

Run the digest tool:

```
python tools/workload_digest.py --input <workload file> --dialect <dialect> [--schema schema.sql] --out workload.digest.yaml
```

It parses each statement and counts, across items:
- **Tables and columns**, with the role each column plays (select, filter, join, group, order, aggregate).
- **Join edges**: the pair of tables and the column pairs of each equality join, from `JOIN … ON`, `USING`, and equality predicates in `WHERE` between two tables. `support` is the number of items that use the edge.
- **Grain keys**: the column sets in GROUP BY, COUNT(DISTINCT …) and SELECT DISTINCT.
- **Filter columns**: per column, the operators used and the *number* of distinct literals compared against, not the literals.
- **Expressions**: arithmetic, CASE, date-part and aggregate-ratio expressions with their literals replaced by placeholders, grouped by the resulting template.

Statements that do not parse are counted and listed by item id, never dropped silently. Non-SELECT statements are counted and skipped.

When the tool cannot run, do the same extraction by reading the SQL, and record `workload.extraction: manual` in the digest.

### Step 3 — Question side (`questions`, `pairs`)

Read the questions and list the **terms**: the noun phrases that name things (concept candidates), their described properties and measures, and the verb phrases that relate them. For each term record how many items use it and group obvious synonyms under one head term.

Do not record values. In *"How many students enrolled in Biology in 2019?"* the terms are *student*, *enrolled in*, *department* or *subject* (if the wording supports it); *Biology* and *2019* are values and stay out.

For `questions` without a schema, this list is the whole digest. It enters CSDP Step 1 as an artifact: each term becomes a prompt for an example, not an object type.

### Step 4 — Alignment (`pairs` only)

For each pair, link each term of the question to the part of *its own* SQL that carries it: a column, a join edge, a filter column, or an expression. Then aggregate over pairs: an alignment's `support` is the number of pairs that agree on it.

- Keep an alignment only when the link is direct in the pair (the phrase and the SQL element are about the same thing in that item). Guessing across pairs is not alignment.
- A term aligned to different columns in different pairs is recorded with all of them. That conflict is a finding: it often means two tables hold the same concept at different grains.
- A term aligned to an expression (*"pass rate"* → `SUM(CASE …)/COUNT(*)`) is a derived fact type candidate with a business name.

### Step 5 — Write and report

Write the digest. Tell the user, in counts: items read, items parsed, parse errors, join edges, grain keys, filter columns, expression templates, terms, alignments, and the unresolved names (tables or columns in the SQL that the schema does not have).

### Step 6 — Hand off

Pass `workload.digest.yaml` to the modeling skill. What that skill does with each kind of evidence is specified there (`rai-orm-from-schema`: `references/workload-evidence.md`). Keep the workload file itself for `rai-orm-verify`.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Literals or question text in the digest | Copying instead of counting | Counts and templates only; terms are phrases, not values |
| Dropping tables the workload never uses | Reading the workload as the scope | Usage orders review; it never removes anything |
| Treating a join edge as a foreign key | A join in a query is not a constraint | It is evidence; the SRP probes inclusion and proposes |
| One query deciding the grain | A single GROUP BY is one use | Report `support`; the SRP weighs it with the data |
| Splitting pairs and aligning by guess | Losing the pairing | Align inside each pair first, then aggregate |
| Using evaluation items | The whole file was handed over | Use only the part not held back for evaluation |

## Examples

| Example | Shows |
|---|---|
| [`evals/fixtures/campus/`](evals/fixtures/campus/) | One schema with the same workload in the three modalities, and the expected digest for each |

## Reference files

| File | When to load |
|---|---|
| [`references/digest-format.md`](references/digest-format.md) | Writing or reading `workload.digest.yaml` |
| [`../rai-orm-from-schema/references/workload-evidence.md`](../rai-orm-from-schema/references/workload-evidence.md) | To see how the SRP consumes each kind of evidence |
