# Constraint Patterns

<!-- TOC -->
- [Constraint Patterns](#constraint-patterns)
  - [Mandatory vs. optional roles](#mandatory-vs-optional-roles)
  - [Subset constraints](#subset-constraints)
  - [Equality constraints (paired presence)](#equality-constraints-paired-presence)
  - [Exclusion constraints (mutual exclusivity)](#exclusion-constraints-mutual-exclusivity)
  - [Value constraints (enumerations and ranges)](#value-constraints-enumerations-and-ranges)
  - [Self-referential relationship constraints](#self-referential-relationship-constraints)
  - [Frequency constraints](#frequency-constraints)
  - [Value-comparison constraints](#value-comparison-constraints)
<!-- /TOC -->

## Constraint Patterns

Beyond the FD enforcement provided by Property and the subtype exclusion via `extends`, RAI models benefit from explicit constraint declarations. Each constraint below should be considered as an active design decision during steps 3-5 of the design sequence. Constraints are implemented as derived properties, business rules, or validation checks in the computed layer.

### Mandatory vs. optional roles

For every Property and Relationship, decide: must every instance of the concept participate, or is participation optional? This decision affects nullability, join semantics (inner vs. outer), and downstream query correctness.

**How to apply:**

After declaring a property, ask: "Can a `{Concept}` exist without this value?"

| Decision | Meaning | PyRel implication |
|----------|---------|-------------------|
| **Mandatory** | Every entity must have this value | Load with NOT NULL source column; missing values indicate data quality issues |
| **Optional** | Some entities may lack this value | Queries using this property must handle absence (`.where()` acts as inner join -- entities without the property are excluded) |

```python
# Mandatory: every Order must have an amount
Order.amount = model.Property(f"{Order} has {Float:amount}")
# If source data has NULLs in amount, flag as data quality issue

# Optional: not every Customer has a phone number
Customer.phone = model.Property(f"{Customer} has {String:phone}")
# Queries joining on phone will silently exclude customers without phone numbers
# Use this intentionally, not accidentally
```

**Decision rule:** Default to mandatory for identity-adjacent properties (name, status, key dates). Default to optional for supplementary attributes (secondary contacts, notes, preferences). Document the choice when it's non-obvious -- a missing "optional" annotation causes silent data loss in queries.

### Subset constraints

A subset constraint declares that the population of one role must be contained within the population of another. "If X has property A, then X must also have property B" -- but not necessarily vice versa.

**How to apply:**

When one property's existence implies another's, declare the dependency explicitly:

```python
# Business rule: every entity with a shipping_date must have an order_date
# (you can't ship before ordering)
# Subset: {entities with shipping_date} subset-of {entities with order_date}

Order.order_date = model.Property(f"{Order} has {Date:order_date}")      # mandatory
Order.shipping_date = model.Property(f"{Order} has {Date:shipping_date}")  # optional

# Validate the subset constraint
Order.shipping_without_order = model.Relationship(f"{Order} has shipping but no order date")
model.define(Order.shipping_without_order()).where(
    Order.shipping_date != None,
    model.not_(Order.order_date)  # negation: order_date is absent
)
# Alert if any entities match -- this violates the subset constraint
```

**Common patterns:**
- Shipping date subset of order date (can't ship without ordering)
- End date subset of start date (can't end without starting)
- Approval date subset of submission date (can't approve without submitting)
- Enrichment properties subset of base concept (enrichment targets must exist)

### Equality constraints (paired presence)

An equality constraint (bidirectional subset) declares that two properties must be either both present or both absent. "Entity has A if and only if entity has B."

**How to apply:**

```python
# Business rule: blood pressure readings always come in pairs
# (systolic and diastolic are either both recorded or neither)
Patient.systolic = model.Property(f"{Patient} has {Float:systolic_bp}")
Patient.diastolic = model.Property(f"{Patient} has {Float:diastolic_bp}")

# Validate: flag entities with only one of the pair
Patient.incomplete_bp = model.Relationship(f"{Patient} has incomplete blood pressure")
systolic_ref = Float.ref()
diastolic_ref = Float.ref()

# Has systolic but not diastolic
model.where(
    Patient.systolic(systolic_ref),
    model.not_(Patient.diastolic)
).define(Patient.incomplete_bp())

# Has diastolic but not systolic
model.where(
    Patient.diastolic(diastolic_ref),
    model.not_(Patient.systolic)
).define(Patient.incomplete_bp())
```

**Common patterns:**
- Origin and destination (shipments always have both)
- Start date and end date on completed processes
- Latitude and longitude (geolocation always paired)
- Min and max bounds (ranges always have both endpoints)

### Exclusion constraints (mutual exclusivity)

An exclusion constraint declares that two associations cannot both hold for the same entity or entity pair. "No X can simultaneously satisfy A and B."

**How to apply:**

```python
# Business rule: no patient takes a drug they are allergic to
Patient.takes = model.Relationship(f"{Patient} takes {Drug}")
Patient.allergic_to = model.Relationship(f"{Patient} allergic to {Drug}")

# Validate exclusion: flag violations
Patient.unsafe_prescription = model.Relationship(
    f"{Patient} unsafely prescribed {Drug:drug}"
)
drug = Drug.ref()
model.where(
    Patient.takes(drug),
    Patient.allergic_to(drug)
).define(Patient.unsafe_prescription(drug))

# To enforce as a solver constraint, see `rai-prescriptive-problem-formulation`
```

**Important distinction from subtype exclusion:** Subtype exclusion (via `extends` with disjoint subtypes) constrains what an entity IS. Exclusion constraints here operate on what an entity DOES -- they apply across different Properties and Relationships involving the same entities.

**Common patterns:**
- Drug-allergy exclusion (patient cannot take drugs they're allergic to)
- Conflict-of-interest (reviewer cannot review their own submission)
- Temporal exclusion (resource cannot be in two places at the same time)
- Complementary roles (an entity acting as buyer cannot also be seller in the same transaction)

### Value constraints (enumerations and ranges)

Value constraints restrict the allowed values for a property beyond its base type. Distinguish between **type-level** constraints (all uses of the type) and **role-level** constraints (only in a specific context).

**How to apply:**

```python
# Type-level: Gender is always one of a closed set
# Use an enumeration concept (see categorization-and-advanced.md)
Gender = model.Concept("Gender", identify_by={"code": String})
# Loaded from: {'M', 'F', 'X'}

# Role-level: age used in an employment context must be 16-100,
# even though the Age type itself allows 0-150
Employee.age = model.Property(f"{Employee} has {Integer:age}")

# Validate range constraint
Employee.invalid_age = model.Relationship(f"{Employee} has invalid age")
age_ref = Integer.ref()
model.where(
    Employee.age(age_ref),
    (age_ref < 16) | (age_ref > 100)
).define(Employee.invalid_age())

# To enforce as a solver constraint, see `rai-prescriptive-problem-formulation`
```

**Constraint taxonomy:**

| Type | Example | PyRel pattern |
|------|---------|---------------|
| **Enumeration** | Status in {'Open', 'Closed', 'Pending'} | Enumeration concept with closed entity set |
| **Range** | Age in [0, 150] | Validation rule with min/max check |
| **Role-specific range** | Employment age in [16, 100] | Validation rule on the specific property context |
| **Pattern** | Email matches `*@*.*` | String validation in computed layer |

**Decision rule:** Use enumeration concepts for categorical values with a closed, named set. Use range validation rules for numeric bounds. Apply role-specific constraints when the same base type has different valid ranges in different contexts.

### Self-referential relationship constraints

When a concept has a relationship to itself (hierarchy, dependency, network), declare which structural constraints apply. The constraint choice determines what kind of graph the relationship forms.

**How to apply:**

For every self-referential Relationship, ask which of these constraints hold:

| Constraint | Meaning | Graph type | Example |
|------------|---------|------------|---------|
| **Irreflexive** | No self-loops: X cannot relate to itself | No self-edges | A task cannot depend on itself |
| **Asymmetric** | No mutual pairs: if X->Y then not Y->X | Directed, no reciprocal edges | Manager-of (if A manages B, B doesn't manage A) |
| **Acyclic** | No cycles of any length | DAG | Task dependencies, bill of materials |
| **Intransitive** | No shortcutting: if X->Y and Y->Z, then not X->Z | No redundant edges | Direct-report (skip-level is a different relationship) |
| **Transitive** | Closure included: if X->Y and Y->Z, then X->Z | Transitive closure | Ancestor-of, reachability |

```python
# Task dependency: irreflexive + acyclic (forms a DAG)
Task.depends_on = model.Relationship(f"{Task} depends on {Task}")

# Validate irreflexivity (no self-dependencies)
task1 = Task.ref()
Task.self_dependency = model.Relationship(f"{Task} has self-dependency")
model.where(Task.depends_on(task1), Task == task1).define(Task.self_dependency())

# Validate acyclicity: use graph analysis (see rai-graph-analysis)
# Build a directed graph from depends_on and check for cycles

# Organizational hierarchy: irreflexive + asymmetric + acyclic (tree)
Employee.reports_to = model.Property(f"{Employee} reports to {Employee:manager}")
# Property (not Relationship) because each employee has exactly one manager

# Part containment: irreflexive + acyclic, may need transitive closure
Part.contains = model.Relationship(f"{Part} contains {Part}")
# If you need "all descendants," compute transitive closure via graph reachability
```

**Decision rule:** Always declare at least irreflexivity for self-referential relationships (self-loops are almost never meaningful). Then decide: is the relationship directed (asymmetric)? Can it have cycles (acyclic)? Does it need transitive closure? The answers determine whether you need validation rules, graph algorithms, or both.

### Frequency constraints

A frequency constraint limits how many times an entity can appear in a role population. "Each team has exactly 3 members" or "each nurse works at most 5 shifts per week."

**How to apply:**

```python
# Business rule: each team has exactly 3 members
Team.members = model.Relationship(f"{Team} has member {Employee}")

# Validate frequency constraint
Team.member_count = model.Property(f"{Team} has {Integer:member_count}")
model.define(Team.member_count(aggs.count(Employee).per(Team)))

Team.invalid_size = model.Relationship(f"{Team} has invalid size")
count_ref = Integer.ref()
model.where(Team.member_count(count_ref), count_ref != 3).define(Team.invalid_size())

# To enforce as a solver constraint, see `rai-prescriptive-problem-formulation`
```

**Common patterns:**
- Fixed-size groups (teams, panels, committees): exactly N
- Workload limits (max shifts per nurse, max courses per student): at most N
- Minimum participation (each project must have at least 2 reviewers): at least N
- Exact coverage (each time slot filled by exactly 1 resource): exactly 1

### Value-comparison constraints

A value-comparison constraint enforces an ordering between two properties on the same entity or related entities. "Project end date must be after start date."

**How to apply:**

```python
# Business rule: end date must be after start date
Project.start_date = model.Property(f"{Project} has {Date:start_date}")
Project.end_date = model.Property(f"{Project} has {Date:end_date}")

# Validate the comparison constraint
Project.invalid_dates = model.Relationship(f"{Project} has end before start")
start_ref, end_ref = Date.ref(), Date.ref()
model.where(
    Project.start_date(start_ref),
    Project.end_date(end_ref),
    end_ref <= start_ref
).define(Project.invalid_dates())

# Cross-entity comparison: shipment departs after order is placed
Shipment.departs_before_order = model.Relationship(
    f"{Shipment} departs before order was placed"
)
ship_date, order_date = Date.ref(), Date.ref()
order = Order.ref()
model.where(
    Shipment.departure_date(ship_date),
    Shipment.order(order),
    order.order_date(order_date),
    ship_date < order_date
).define(Shipment.departs_before_order())
```

**Common patterns:**

| Constraint | Operator | Example |
|------------|----------|---------|
| Temporal ordering | `<`, `<=` | start_date < end_date |
| Budget limits | `<=` | actual_spend <= budget |
| Capacity bounds | `<=` | assigned_load <= max_capacity |
| Minimum thresholds | `>=` | quality_score >= min_acceptable |
| Matching values | `==` | invoice_total == sum(line_items) |

**Decision rule:** Whenever two numeric or temporal properties on the same entity (or connected entities) have a business ordering relationship, declare the comparison constraint explicitly. These constraints serve as both validation rules (flag violations in existing data) and solver constraints (prevent infeasible solutions in optimization).
