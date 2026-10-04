# Campus fixture

A small synthetic schema (SQLite) with one workload in the three modalities. Written for these evals; no external source, no license constraint.

| File | Contents |
|---|---|
| `schema.sql` | 6 tables. One declared FK (`ENROLLMENT.SUBJECT_ID`). |
| `data.sql` | 12 students, 9 directory rows, 6 staff, 6 subjects, 20 enrollments. |
| `workload.pairs.json` | 12 question+SQL pairs. |
| `workload.sql.json` | The SQL half of the pairs. |
| `workload.questions.txt` | The question half of the pairs. |

Load: `sqlite3 campus.db ".read schema.sql" ".read data.sql"`.

## What is planted

| # | Planted | Where | A correct run |
|---|---|---|---|
| 1 | Undeclared references that no naming convention finds | `ENROLLMENT.LEARNER_NO → STUDENT.ID`, `SUBJECT.DEPT_CODE → DEPARTMENT.CODE`, `STUDENT.HOME_DEPT → DEPARTMENT.CODE` | Without a digest: no fact type for them. With a `sql` or `pairs` digest: three `proposed` fact types with `provenance.origin: workload` and an inclusion rate. |
| 2 | A join that is not a relationship | `STUDENT.HOME_DEPT = STAFF.DEPT_CODE` (p11): neither side is a key | Never emitted as a fact type between Student and Staff. |
| 3 | A grain trap | `STUDENT` (12 rows) and `STUDENT_DIRECTORY` (9 rows, no PK) describe the same people; p07 and p08 count them separately; p09 joins the directory | The directory's rows stay reachable on their own: p07 returns 9, p08 returns 12. A model that merges both into one Student concept without a per-table handle fails p07 or p08. |
| 4 | A derived measure with a business name | pass rate, in p03 and p04 | `sql`: a derived fact type from the expression template. `pairs`: the same, named with the term "pass rate". |
| 5 | An enum-like filter column | `SUBJECT.LEVEL` (`UG`, `PG`) | A distinct-value probe is requested; the value constraint comes from the data, not from the SQL literals. |
| 6 | A nullable reference | `STUDENT.HOME_DEPT` is NULL for one student | No mandatory constraint on the workload-proposed fact type; p12 returns 11 students in total. |

The workload has 12 items, so `rai-orm-verify` uses no holdout here.
