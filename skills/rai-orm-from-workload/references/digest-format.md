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
2. Sections that the modality cannot produce are omitted, not left empty: a `questions` digest has only `workload` and `terms`; a `sql` digest has no `terms`.
3. Table and column names are written as in the schema when one was given (case as declared); otherwise upper-cased as parsed.
4. A join edge is unordered: `left` is the side whose `(table, columns)` sorts first. The same pair of column lists appears once.
5. Expression templates replace every literal with `?`. Two expressions that differ only in literals share one template.
6. `terms[].term` is a noun or verb phrase of at most six words. It is never a data value and never a whole question.
7. `aligned_to` exists only for `pairs`. Every target names something present in the same digest (`table`, `table`+`column`, `join_edge` id, or `expression` id).
8. No field anywhere holds a SQL literal. `distinct_literals` is a count.
9. Every list is sorted by `support` descending, then by name, so that two runs over the same workload give the same file.
