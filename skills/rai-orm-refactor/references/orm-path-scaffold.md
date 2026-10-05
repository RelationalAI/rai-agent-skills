# ORM path scaffold

A scaffold tests whether a workload item needs a concept or merely a walk plus operators. It is PyRel-shaped pseudo-code: it need not execute, but every model element resolves. Consult `rai-pyrel-coding` for expression syntax and `rai-querying` for selection, grouping, ranking and result semantics. Do not invent a `PATH` API or a generic `.exists()` method.

## Grammar and audit

```text
scaffold := item-id + inventory + input-grain + path + operators + output-grain
inventory := existing entity ids, value/property ids, fact ids and role directions
path := entity-ref ( --existing fact(role bindings)--> entity-ref )*
operators := filter | project | deduplicate | group | aggregate | rank
             | compare | exists | not-exists | union | intersection | difference
             | membership | arithmetic | conditional | missing-value-test
```

Branches, shared dimensions, inverse traversals and independent refs are allowed; bind each hop explicitly rather than relying on fragile multi-hop comparisons in `.where()`. An inverse traversal applies the existing fact with the target bound; it does not create an inverse fact. Group, arithmetic and comparison operate on expressions and refs, not newly declared concepts.

For each scaffold record:

1. Item id, suspect id, specification artifact/id, and inventory of surviving elements.
2. Walk with fact ids, role direction and join kind. A local ref names an occurrence, not a new entity type.
3. Parameter placeholders, grouping grain, distinct/multiset behavior, null handling and output column names.
4. Each required operator and any syntax/semantics to confirm with the syntax skills.
5. Conclusion: `path-available` or `blocked` with missing element ids/operator class, never item text.

Resolve all inventory entries against the existing YAML and generated Python before writing the scaffold. Exclude the suspect, its dependent facts being deleted, and proposed replacement declarations. Parameter identifiers stand in for filter values; no values or item wording go in proposal or metrics outputs. A replacement can be proposed later, but cannot provide a missing step in this test. If the representation lacks a needed relationship, record the failure; do not synthesize a relationship, reconstruct a join from source columns or embed SQL.

## Operator vocabulary

These one-line examples use only the campus inventory below. `parameter_*` identifiers are local inputs; `model`, `aggs`, `distinct`, `rank`, `desc`, `top` and `bottom` are syntax handles. Imports and actual runnable lowering belong to the syntax skills.

```python
student = Student.ref()  # Independent entity occurrence
walk = model.where(Enrollment.student(student), Enrollment.subject(Subject))  # Walk / join
inverse = model.where(Enrollment.subject(Subject)).select(Enrollment.term)  # Inverse walk
filtered = model.where(Enrollment.term == parameter_term)  # Filter
projection = model.select(Subject.title)  # Project
deduplicated = model.select(distinct(Student.full_name))  # Deduplicate all output columns
grouped = aggs.count(Enrollment).per(Subject.title)  # Group by property value
counted = aggs.count(Enrollment)  # Count at entity grain
summed = aggs.sum(Enrollment.grade)  # Sum
minimum = aggs.min(Enrollment.grade)  # Minimum
maximum = aggs.max(Enrollment.grade)  # Maximum
average = aggs.avg(Enrollment.grade)  # Average (query context)
joined_text = aggs.string_join(Subject.title)  # String aggregation; delimiter per syntax skill
ranked = rank(desc(Enrollment.grade))  # Ranking / ordering; no order_by() API
highest = top(parameter_n, Enrollment.grade)  # Top-N
lowest = bottom(parameter_n, Enrollment.grade)  # Bottom-N
compared = model.where(Enrollment.grade >= parameter_cutoff)  # Comparison
having = model.where(aggs.count(Enrollment).per(Subject) > parameter_minimum)  # Aggregate comparison
exists = model.where(Student, Enrollment.student(Student)).select(distinct(Student.full_name))  # Exists via a bound fact
absent = model.where(Student, model.not_(Enrollment.student(Student)))  # Not-exists with correlated Student
member = model.where(Subject.level.in_(parameter_levels))  # Membership
either = model.where(model.union(Enrollment.grade < parameter_low, Enrollment.grade > parameter_high))  # Union / set OR
both = model.where(Enrollment.grade >= parameter_low, Enrollment.grade <= parameter_high)  # Intersection / conjunction
difference = model.where(Enrollment.grade >= parameter_low, model.not_(Enrollment.grade > parameter_high))  # Set difference
ratio = aggs.sum(Enrollment.grade) / aggs.count(Enrollment)  # Arithmetic; denominator semantics need checking
conditional = aggs.count(Enrollment).where(Enrollment.grade >= parameter_cutoff) | 0  # Ordered fallback, not set OR
missing = model.where(Enrollment, model.not_(Enrollment.grade))  # Missing-value test, subject to binding's NULL mapping
```

Set operations must project compatible columns and preserve required multiplicity; `model.union()` is set-style, not SQL `UNION ALL`. `&` or multiple `.where()` conditions conjoin; `|` is ordered fallback, not set union. An existence test projects the correlated entity after applying the existing fact; do not count matching rows unless the item asks for a count. If the allowed vocabulary cannot preserve bag semantics, recursion, an outer join or a window frame, mark the scaffold blocked and have `rai-orm-verify` classify the limitation. Successful Python parsing says nothing about PyRel runtime behavior.

## Campus inventory

The original synthetic campus fixture belongs to `rai-orm-from-workload`. This skill supplies a small existing [path model](../evals/fixtures/campus-path/model.orm.yaml) for the worked examples below; it models the fixture's entity relationships explicitly and is not a claimed complete verified campus model. Generate/bind it through the modeling and coding skills for execution. In a user's model, use their actual ids and emitted handles.

| Existing entity/property handle | YAML element |
|---|---|
| `Student`, `Staff`, `Subject`, `Department`, `Enrollment` | `student`, `staff`, `subject`, `department`, `enrollment` |
| `Student.full_name` | `student_has_full_name` → value type `name` |
| `Student.home_department` | `student_has_home_department` → `department` |
| `Staff.department` | `staff_has_department` → `department` |
| `Subject.title`, `Subject.level` | `subject_has_title`, `subject_has_level` → `title`, `level` |
| `Subject.department` | `subject_has_department` → `department` |
| `Department.name` | `department_has_name` → value type `name` |
| `Enrollment.student`, `Enrollment.subject` | `enrollment_has_student`, `enrollment_has_subject` |
| `Enrollment.term`, `Enrollment.grade` | `enrollment_has_term`, `enrollment_has_grade` → `term`, `grade` |

Identifiers use entity reference modes; Enrollment's identifier is the external tuple of student, subject and term. The path model intentionally leaves directory membership out: an item needing that population would be blocked against this inventory. A table merge needs to preserve the distinction between registered students and directory rows.

## Worked scaffold 1 — Walk, filter and deduplicate (`p02`)

Test a query-shaped concept representing students selected for one term. Specification: campus pair `p02`. Surviving path: `Enrollment --enrollment_has_student--> Student`; filter `enrollment_has_term`. Result grain: distinct `Student.full_name` values, matching the item's SQL projection rather than counting enrolled rows.

```python
e, student = Enrollment.ref(), Student.ref()
scaffold = model.where(
    e.student(student),
    e.term == parameter_term,
).select(distinct(student.full_name))
```

Audit: all handles resolve in the inventory. The term-selection concept contributes no identity or domain role to this item. A different term is the same path with a different parameter. Verify duplicate names, repeated enrollments and source binding coverage before removing the concept.

## Worked scaffold 2 — Multi-hop grouping and conditional ratio (`p04`)

Test a query-shaped concept representing departments labeled by a computed rate. Specification: campus pair `p04`. Path: `Enrollment --enrollment_has_subject--> Subject --subject_has_department--> Department`. Values: `enrollment_has_grade`, `department_has_name`. Group by department **name**, matching the SQL grain even if two department ids share a name.

```python
e, subject, department = Enrollment.ref(), Subject.ref(), Department.ref()
join = (e.subject(subject), subject.department(department))
denominator = aggs.count(e).where(*join).per(department.name)
numerator = aggs.count(e).where(*join, e.grade >= parameter_cutoff).per(department.name) | 0
scaffold = model.where(*join).select(distinct(
    department.name,
    numerator * 1.0 / denominator,
))
```

Audit: the ratio is a local expression, not a newly declared model property. Denominator counts Enrollment instances, including a missing grade; numerator counts only matching grades. The inner path excludes departments with no enrollments and guarantees a positive denominator. Check fallback scope and numeric division with `rai-querying` before lowering this pseudo-code. Verify NULL grades, all-failing groups and shared department names. If useful beyond the item, the same expression can motivate a derived fact type after the existing-element test.

## Worked scaffold 3 — Shared dimension without a shortcut (`p11`)

Test a query-shaped concept representing staffing for a student's home department. Specification: campus pair `p11`. Path: `Student --student_has_home_department--> Department <--staff_has_department-- Staff`. There is no Student–Staff fact type. The shared Department binds both existing facts; group by student **full name** to preserve the item's SQL grain.

```python
student, department, staff = Student.ref(), Department.ref(), Staff.ref()
join = (student.home_department(department), staff.department(department))
staff_count = aggs.count(staff).where(*join).per(student.full_name)
scaffold = model.where(*join).select(distinct(student.full_name, staff_count))
```

Audit: inverse traversal uses `staff_has_department`, not a fabricated direct relationship. Verify equal full names and matching-pair multiplicity (SQL counts staff rows once for each joined student row). A PyRel aggregate may need different lowering to preserve that multiset; if no lowering exists under the allowed operators, this scaffold is blocked rather than evidence for deletion. NULL home departments and departments without staff are excluded by the source item's inner joins. The path is a reasoning scaffold, and `rai-orm-verify` decides acceptance.
