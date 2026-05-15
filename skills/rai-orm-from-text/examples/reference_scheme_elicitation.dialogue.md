# reference_scheme_elicitation — CSDP Dialogue (the most-skipped step)

Demonstrates reference-scheme elicitation at CSDP Step 1. New users default to attribute-thinking ("the customer has a name and an email"); CSDP forces an explicit decision about how each entity type is identified.

This example walks through three entity types with three different reference-mode choices: `popular`, `general`, and `external` (composite).

---

**Step 1 — Eliciting examples (turn 1–4)**

`User:` I want to model a small project-tracking domain. Projects, Employees, and Tasks. Employees work on Projects, and each Project has Tasks.

`Claude:` *Got it. Can you walk me through a concrete example?*

`User:` Project "Atlas" started 2026-01-15, status active. Employee jdoe (John Doe) works on Atlas. Task "design schema" is in project Atlas, assigned to jdoe.

`Claude:` *Let me decompose into elementary facts and verbalize each:*
- *'Project Atlas has start-date 2026-01-15.' — atomic?*
- *'Project Atlas has status "active".' — atomic?*
- *'Employee jdoe has full-name "John Doe".' — atomic?*
- *'Employee jdoe works-on Project Atlas.' — atomic?*
- *'Task "design schema" is in Project Atlas.' — atomic?*
- *'Task "design schema" assigned to Employee jdoe.' — atomic?*

`User:` All atomic.

---

**Reference-scheme elicitation — Project (turn 5–7)**

`Claude:` *Good. Now the reference schemes — how each entity type is identified.*

*For Project: you used "Atlas" as the identifier. Is the Project's name the unique identifier, or do Projects have a separate ID?*

`User:` Project names are unique in our org. So name is the identifier.

`Claude:` *Two reference-mode options:*
- *`popular`: name is the identifier directly. Like `Country(.code)` — the entity is identified by a primitive.*
- *`general`: name is a value-typed identifier like `Book(ISBN)` — distinct from a popular reference mode when the identifier is a meaningful named value rather than an arbitrary primitive.*

*For Project name as a unique-and-meaningful string, I'd use `general` with `value_type: ProjectName`. (If you wanted to add an auto-incrementing ID later, you could switch to `popular` with that ID; for now `general` matches your description.) Confirm?*

`User:` Confirm `general` with ProjectName.

---

**Reference-scheme elicitation — Employee (turn 8–10)**

`Claude:` *For Employee: you used "jdoe" as the identifier — is that a username, an employee ID, or something else?*

`User:` That's a username. We have employee IDs (numeric, internal) but in conversation we use usernames.

`Claude:` *Two questions:*
- *Should the model identify Employees by username or by ID?*
- *Are usernames guaranteed unique? Always?*

`User:` Identify by username — that's how everyone refers to them. Usernames are unique, always — we enforce that at user creation.

`Claude:` *Got it. Same situation as Project — a meaningful unique string. Reference mode `general` with `value_type: Username`. Confirm?*

`User:` Confirm.

---

**Reference-scheme elicitation — Task (turn 11–14)**

`Claude:` *For Task: you described it as "design schema" in project Atlas. Is the Task name unique across all projects, or only within a project?*

`User:` Only within a project. We can have "design schema" in two different projects without conflict.

`Claude:` *That changes things. Task is identified by the combination of project + name — that's an `external` reference mode (composite identifier). Verbalizing:*

- *Task is identified externally by `(Project, TaskName)`.*
- *Two reference-bearing fact types: 'Task in Project' and 'Task has-name TaskName'.*
- *External UC: the combination (Project, TaskName) is unique per Task.*

*This is Halpin's external reference pattern. Confirm?*

`User:` Confirm. So we'd have Task as an entity with composite key Project+Name.

`Claude:` *Right — and the external UC at Step 4 will formalize that. Note one subtle consequence: any fact type about a specific Task needs to reference both Project and TaskName, or it needs to use the Task entity that the external UC identifies. The latter is cleaner — once Task is identified, we can write 'Task assigned-to Employee', 'Task has status', etc., and the Task is identified via the external UC, not redundantly.*

`User:` Got it.

---

**Outcome:**

| Entity type | Reference mode | Identifier |
|---|---|---|
| Project | `general` | `ProjectName` (String) |
| Employee | `general` | `Username` (String) |
| Task | `external` | composite `(Project, TaskName)` |

The reference-scheme elicitation at Step 1 prevented three common mistakes:
1. Assuming Projects have an auto-generated ID when names are actually unique.
2. Using the wrong field as Employee identity (employee_id vs username).
3. Modeling Task as having a globally-unique name when in fact names are only unique within a project.

The third mistake is the kind that's only caught by asking "is this unique across all instances, or only within some scope?" — and the answer determines whether the reference mode is `general` (single-key) or `external` (composite).
