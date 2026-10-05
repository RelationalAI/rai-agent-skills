# `workload.digest.yaml` — format

The digest is the only output of `rai-orm-from-workload`. It holds counts and structure. It never holds a SQL literal, a data value, or the full text of a question.

`support` always means: the number of workload items in which the thing occurs (an item counts once, however many times the thing occurs inside it).

```yaml
version: 1                          # mandatory; first field

workload:
  kind: pairs                       # sql | questions | pairs
  artifacts: ["setup-pairs.json"]   # the workload file(s), by name only
  dialect: postgres                 # sql / pairs only
  n_items: 109
  n_sql: 109                        # items with SQL
  n_questions: 109                  # items with a question
  n_parsed: 107                     # SQL statements parsed
  parse_errors: ["q041", "q077"]    # item ids, no text
  skipped_non_select: 0
  extraction: tool                  # tool | manual
  generated_at: "2026-10-04T12:00:00Z"

tables:                             # usage; never used to prune
  - table: ENROLLMENT
    support: 31

columns:
  - table: ENROLLMENT
    column: TERM_CODE
    support: 22
    roles: { select: 4, filter: 15, join: 0, group: 9, order: 2, aggregate: 0 }

join_edges:
  - id: je_1
    left:  { table: ENROLLMENT, columns: [STUDENT_ID] }
    right: { table: STUDENT,    columns: [ID] }
    support: 14
    kinds: { inner: 12, left: 2 }   # join kinds seen
    declared_fk: false              # filled when a schema was given; absent otherwise

grain_keys:
  - table: ENROLLMENT
    columns: [STUDENT_ID, SUBJECT_ID, TERM_CODE]
    evidence: { group_by: 6, count_distinct: 0, distinct: 1 }
    support: 7

filter_columns:
  - table: SUBJECT
    column: LEVEL
    operators: { eq: 9, in: 2, like: 0, range: 0, is_null: 0 }
    distinct_literals: 3            # how many different literals were compared against; not the literals
    support: 11

expressions:
  - id: ex_1
    kind: aggregate-ratio           # arithmetic | case | date-part | aggregate-ratio | string
    template: "SUM(CASE WHEN ENROLLMENT.GRADE >= ? THEN 1 ELSE 0 END) / COUNT(*)"
    tables: [ENROLLMENT]
    columns: [ENROLLMENT.GRADE]
    support: 5

terms:                              # questions / pairs only
  - term: "student"
    kind: concept                   # concept | property | measure | relation
    synonyms: ["learner"]
    support: 40
    aligned_to:                     # pairs only; each with its own support
      - { table: STUDENT, support: 38 }
  - term: "pass rate"
    kind: measure
    support: 5
    aligned_to:
      - { expression: ex_1, support: 5 }
  - term: "enrolled in"
    kind: relation
    support: 14
    aligned_to:
      - { join_edge: je_1, support: 9 }

unresolved:                         # names in the SQL that the schema does not have
  - { table: ENROLMENT_OLD, support: 1 }
```

## Rules

1. `version` is the first field. `workload.kind` is one of `sql`, `questions`, `pairs`.
2. Sections that the modality cannot produce are omitted, not left empty: a `questions` digest has `workload`, `item_contributions` and manually extracted `terms`; a `sql` digest has no `terms`.
3. Table and column names are written as in the schema when one was given (case as declared); otherwise upper-cased as parsed.
4. A join edge is unordered: `left` is the side whose `(table, columns)` sorts first. The same pair of column lists appears once.
5. Expression templates replace every literal with `?`. Two expressions that differ only in literals share one template.
6. `terms[].term` is a noun or verb phrase of at most six words. It is never a data value and never a whole question.
7. `aligned_to` exists only for `pairs`. Every target names something present in the same digest (`table`, `table`+`column`, `join_edge` id, or `expression` id).
8. No field anywhere holds a SQL literal. `distinct_literals` is a count.
9. Every list is sorted by `support` descending, then by name, so that two runs over the same workload give the same file.

## Subset selection

`--ids FILE` selects one workload item id per line (blank lines are ignored). `--split {repair,holdout} --verification model.verification.json` selects by `items[].id` and `items[].split` in the saved verification file, never by a fresh random split or the top-level split counts. Combined selectors intersect. Item ids must be unique; unknown requested ids, missing assignments and invalid assignments are errors. Generated ids retain their positions in the original workload, before selection.

Selection happens before parsing and counting. Both `repair.digest.yaml` and `holdout.digest.yaml` have the same format and existing keys as a full digest; `workload` counts describe only selected items. An empty selection preserves the source modality and has no structural evidence. Use `--no-timestamp` for reproducible files or hashed artifacts.

## Per-item contributions

New digests add `item_contributions`, keyed by sorted item id. Each entry contains the same structural sections as the aggregate (`tables`, `columns`, `join_edges`, `grain_keys`, `filter_columns`, `expressions`, and `unresolved` when a schema was supplied). Rows contain structural identifiers and counts only; no SQL, questions, literal values or hashes of literal values. Support and role/operator/kind/evidence counts are 0 or 1 per item, even if its SQL repeats the same evidence. SQL-free or unparseable items have empty sections; question-only digests have empty contribution mappings per item.

Contribution join edges and expressions omit aggregate `je_*`/`ex_*` ids: those ids depend on support ordering. Match rows by structural identity (table; table + column; left/right table + column tuples; table + grain columns; or expression kind + redacted template).

For example:

```yaml
item_contributions:
  q1:
    tables: [{table: SUBJECT, support: 1}]
    filter_columns:
      - table: SUBJECT
        column: LEVEL
        support: 1
        operators: {eq: 1, in: 0, like: 0, range: 0, is_null: 0}
        distinct_literals: 2
        literal_cohorts:
          - {items: [q1], count: 1}
          - {items: [q1, q2], count: 1}
```

`literal_cohorts` groups a filter column's literals by the set of item ids that use them, recording only the size of each group. Every contribution for that column repeats the column's complete cohort list, sorted by item-id tuple. This permits exact distinct-literal subtraction without retaining or hashing values: the example has one literal exclusive to q1 and one shared with q2. The per-item `distinct_literals` remains the number used by that item.

To remove a changed or deleted item's old evidence, subtract its support and counter fields from structurally matching aggregate rows, drop zero-support rows, and re-sort. For `kinds`, drop zero-count entries; retain documented zero entries for the other counters. Do **not** subtract per-item `distinct_literals` directly: remove the item's id from each cohort, discard empty cohorts, and sum their counts for the remaining column. Combine cohorts with identical remaining membership and update surviving contributions' cohort lists. Reassign aggregate join/expression ids after sorting and update any manual references to them. This subtraction needs only the stored contributions, not old query text. Counts alone cannot identify literal overlap with a newly changed query; rebuild affected filter evidence from current workload items before adding its distinct-literal evidence. Workload parse statistics and manually authored terms/alignments are outside these structural contributions and must be refreshed separately.

Legacy digests without `item_contributions` remain valid inputs, including for connectivity checks. Rebuild from the workload before trying to subtract item evidence; absence of contributions is not evidence of zero contribution.
