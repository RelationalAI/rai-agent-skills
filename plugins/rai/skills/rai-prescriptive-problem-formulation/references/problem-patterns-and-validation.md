<!-- TOC -->
- [Common Problem Patterns](#common-problem-patterns)
  - [Assignment / scheduling](#assignment--scheduling)
  - [Network flow](#network-flow)
  - [Diet / blending](#diet--blending)
  - [Facility location](#facility-location)
  - [TSP / vehicle routing](#tsp--vehicle-routing)
  - [Multi-period / time-indexed models](#multi-period--time-indexed-models)
- [Temporal Filtering](#temporal-filtering)
  - [Date column filtering](#date-column-filtering)
  - [Epoch timestamp filtering](#epoch-timestamp-filtering)
- [Formulation Analysis](#formulation-analysis)
  - [Analysis priorities (in order)](#analysis-priorities-in-order)
  - [What NOT to do in analysis](#what-not-to-do-in-analysis)
  - [Business-to-formulation validation](#business-to-formulation-validation)
  - [Semantic Validation Checks](#semantic-validation-checks)
- [Validation Checklist](#validation-checklist)
  - [Phase 1: Structure](#phase-1-structure)
  - [Phase 2: Completeness](#phase-2-completeness)
  - [Phase 3: Feasibility](#phase-3-feasibility)
  - [Phase 4: Problem classification](#phase-4-problem-classification)
  - [Phase 5: Data](#phase-5-data)
  - [Phase 6: Problem size](#phase-6-problem-size)
  - [Severity classification](#severity-classification)
- [Problem Type Classification](#problem-type-classification)
<!-- /TOC -->

## Common Problem Patterns

Each pattern shows the minimal skeleton. Key heuristic in bold.

### Assignment / scheduling

**Key:** Binary variables scoped to valid pairs only (`where=[availability_relationship]`). Needs both per-slot coverage AND per-resource limits.

```python
problem.solve_for(Worker.x_assign(Shift, x), type="bin",
            where=[Worker.available_for(Shift)])
problem.satisfy(model.require(sum(Worker, x).per(Shift) >= min_coverage))   # forcing
problem.satisfy(model.require(sum(Shift, x).per(Worker) <= max_shifts))     # capacity
```

### Network flow

**Key:** Flow conservation (inflow == outflow at interior nodes) via `.ref()` on Edge concept. Two refs iterate independently.

```python
problem.solve_for(Edge.flow, lower=0, upper=Edge.cap)
Ei, Ej = Edge.ref(), Edge.ref()
problem.satisfy(model.require(per(Ej.j).sum(Ej.flow) == per(Ei.i).sum(Ei.flow)).where(Ei.i == Ej.j))
```

**Anti-pattern: Item x Edge cross-product.**

When the model has EDGE concepts (with source/destination) and ITEM concepts (with origin/destination), you must choose the correct formulation pattern:

**WRONG (causes INFEASIBLE or trivial solutions):**
```python
# Creating Item x Edge cross-product
model.define(ShipmentRouting.new(shipment=Shipment, operation=Operation))
# Then adding site matching constraints in .where()
# PROBLEM: Most combinations are INVALID because edges don't connect to item locations
```

**RIGHT (use flow-on-edges):**
```python
# Put flow variable directly on the edge concept
problem.solve_for(Operation.flow_quantity, type='cont', lower=0, upper=Operation.capacity)
# Add conservation constraints at nodes via model.require()
# Add source/sink constraints for supply/demand
```

**When to use each pattern:**
- **Flow-on-edges:** When you do NOT need to track individual items through the network (aggregate flow, water allocation, general network design)
- **Filtered Item x Edge:** ONLY if edges actually connect item origins to destinations — **verify with a data query first** before assuming the cross-product is valid

**Data verification requirement:** Before creating any cross-product entity, query the actual data to confirm the join conditions will produce valid (non-empty) entity sets. A cross-product where most entities are filtered out by `.where()` is a sign the wrong pattern was chosen.

### Diet / blending

**Key:** Multiarity property binding (`Food.contains(Nutrient, qty)`) for ternary data. Constraints are per-nutrient bounds.

```python
problem.solve_for(Food.amount, lower=0)
qty = Float.ref()
total = sum(qty * Food.amount).where(Food.contains(Nutrient, qty)).per(Nutrient)
problem.satisfy(model.require(total >= Nutrient.min, total <= Nutrient.max))
```

### Facility location

**Key:** Binary open/close variable linked to flow via capacity constraint (`flow <= capacity * x_open`). Multi-component objective via `model.union()`.

```python
problem.solve_for(Facility.x_open, type="bin")
problem.solve_for(Route.x_flow, lower=0)
problem.satisfy(model.require(sum(Route.x_flow).per(Facility) <= Facility.capacity * Facility.x_open))
problem.satisfy(model.require(sum(Route.x_flow).per(Customer) >= Customer.demand))  # forcing
problem.minimize(sum(model.union(sum(Facility.fixed_cost * Facility.x_open),
                           sum(Route.transport_cost * Route.x_flow))))
```

### TSP / vehicle routing

**Key:** Degree constraints (exactly 1 in-edge, 1 out-edge per node). MTZ subtour elimination with auxiliary ordering variable `u`. Symmetry breaking fixes one node.

```python
problem.solve_for(Edge.x, type="bin")
problem.solve_for(Node.u, type="int", lower=1, upper=node_count)
# Degree: sum(Edge.x).per(Node) == 1 for both in-edges and out-edges
# MTZ: Ni.u - Nj.u + node_count * Edge.x <= node_count - 1 (for non-depot nodes)
# Symmetry: model.require(Node.u == 1).where(Node.v(1))
```

### Multi-period / time-indexed models

**Key:** Two approaches -- (1) cross-product concept (`MachinePeriod`) for entity-per-period decisions, or (2) multiarity property (`FreightGroup.inv(t, x_inv)`) for time-indexed variables with `where=[t == range(...)]`.

**Inventory balance** links consecutive time steps:

```python
problem.satisfy(model.where(
    x_inv1 := Float.ref(), x_inv2 := Float.ref(),
    FreightGroup.inv(t, x_inv1), FreightGroup.inv(t + 1, x_inv2),
    TransportType.qty_tra(FreightGroup, t, x_qty_tra),
).require(x_inv1 == x_inv2 + sum(x_qty_tra).per(FreightGroup, t)))
```

**Cumulative / running-sum** uses two refs with time-ordering:

```python
Tx, Ty = Period.ref(), Period.ref()
model.where(Tx.pid <= Ty.pid).define(
    MachinePeriod.cumulative_production(sum(MachinePeriod.x_production).where(
        MachinePeriod.period(Tx)).per(Machine, Ty)))
```

### Pricing / markdown optimization

**Key:** One-hot binary selection from a discrete price/discount set per entity per period. Monotone price ladder via consecutive-period mutual exclusion. Cumulative tracking with temporal recurrence.

```python
# One-hot: exactly one discount level per (Product, Week)
problem.solve_for(Product.x_select(w, d, x), type="bin")
problem.satisfy(model.where(Product.x_select(w, d, x)).require(
    sum(d, x).per(Product, w) == 1))

# Price ladder: discount cannot decrease week-over-week
problem.satisfy(model.where(
    Product.x_select(w, d, x), Product.x_select(w2, d2, x2),
    w2.num == w.num + 1, d2.level < d.level,
).require(x + x2 <= 1))

# Cumulative sales (base case + recurrence)
problem.satisfy(model.where(w.num == 1, ...).require(z == sum(d, y).per(Product, w)))
problem.satisfy(model.where(w.num > 1, w_prev.num == w.num - 1, ...).require(
    z == z_prev + sum(d, y).per(Product, w)))
```

See `../examples/one_hot_temporal_recurrence.py`.

### Piecewise linear (PWL) cost approximation

**Key:** Reify cost segments as concept instances. Each segment gets a continuous remainder variable capped by its limit, and a binary active indicator. Exactly one segment active. Total = remainder of active segment + full capacity of lower segments.

```python
# Segment activation: exactly one active
problem.satisfy(model.require(sum(y_bin).per(t) == 1).where(...))
# Remainder within limit
problem.satisfy(model.require(x_rem <= Segment.limit * y_bin).where(...))
# Weight decomposition: active remainder + lower segments' full capacities
problem.satisfy(model.where(...).require(
    x_weight == sum(x_rem).per(t) +
    sum(Seg1.limit * y_bin).where(Seg1.seg == Seg2.seg - 1).per(t)))
```

See `../examples/multi_concept_union_objective.py`.

---

## Pattern-Specific Optimization Guidance

When a problem pattern is detected, use these detailed guides for formulation.

#### Network Flow Guidance

**Entity Creation Pattern Choice**

When the model has EDGE concepts (with source/destination attributes) and ITEM concepts (with origin/destination attributes), you must choose the correct formulation pattern:

**WRONG (causes INFEASIBLE or trivial solutions):**
```python
# Creating Item x Edge cross-product
define(ShipmentRouting.new(shipment=Shipment, operation=Operation))
# Then adding site matching constraints in .where()
# PROBLEM: Most combinations are INVALID because edges don't connect to item locations
```

**RIGHT (use flow-on-edges):**
```python
# Put flow variable directly on the edge concept
problem.solve_for(Operation.flow_quantity, type='cont', lower=0, upper=Operation.capacity)
# Add conservation constraints at nodes
# Add source/sink constraints for supply/demand
```

**When to use each pattern:**
- Flow-on-edges: When you DON'T need to track individual items through the network (aggregate flow, water allocation, general network design)
- Filtered Item x Edge: ONLY if edges actually connect item origins to destinations (verify with data query first)

**Typical Variables:** Continuous flow on edges (0 to capacity), binary edge selection (for network design).
**Common Constraints:** Flow conservation at intermediate nodes (inflow == outflow), capacity limits on edges, source constraints (outflow >= supply), sink constraints (inflow >= demand).
**Typical Objectives:** Minimize unmet demand at sinks, maximize throughput, minimize total flow cost.
**Key Entities:** NODE concepts (Sites, locations, endpoints), EDGE concepts (Operations, routes, pipelines with source and destination), ITEM concepts (optional: Shipments, orders with origin/destination — route THROUGH edges).

#### Assignment Guidance

**Typical Variables:** Binary assignment variables (0 or 1).
**Common Constraints:** Each task assigned to one resource, resource capacity limits, assignment compatibility constraints.
**Typical Objectives:** Minimize assignment cost, maximize assignments, balance workload across resources.
**Key Entities:** Resources (workers, machines), Tasks (shifts, jobs), Assignments (resource-task pairs).

#### Selection Guidance

**Typical Variables:** Binary selection variables (0 or 1).
**Common Constraints:** Budget constraints (cost limit), dependency constraints (if A then B), cardinality constraints (min/max selections).
**Typical Objectives:** Maximize total value/profit, minimize cost while meeting requirements, maximize coverage/diversity.
**Key Entities:** Items/Products (things to select), Bundles/Portfolios (collections), Dependencies (logical relationships).

#### Allocation Guidance

**Typical Variables:** Continuous or integer allocation amounts.
**Common Constraints:** Total allocation limits (budget), minimum/maximum per entity, balance or fairness constraints.
**Typical Objectives:** Maximize total utility/benefit, minimize cost, maximize fairness (minimize variance).
**Key Entities:** Resources (money, time, capacity), Recipients (projects, departments), Allocations (amounts assigned).

#### General Optimization Guidance

**Start with:**
1. Identify decision variables (what can change?)
2. Define constraints (what limits decisions?)
3. Specify objective (what to optimize?)

**Common patterns:** If moving things: consider flow variables. If choosing yes/no: consider binary variables. If assigning amounts: consider continuous variables.
**Key questions:** What are the decision points? What physical/logical limits exist? What is the ultimate goal?

---

## Temporal Filtering

Time-scoped constraints restrict optimization to a specific time window by applying `.where()` filters on date or epoch timestamp columns.

### Date column filtering

```python
problem.satisfy(model.require(
    sum(Demand.x_fulfilled).per(Product) >= sum(Demand.quantity).per(Product)
).where(Demand.due_date >= '2025-11-01', Demand.due_date <= '2025-11-30'))
```

### Epoch timestamp filtering

```python
problem.satisfy(model.require(
    sum(PullRequest.x_selected).per(Repo) <= max_reviews
).where(PullRequest.created_at >= 1759302000, PullRequest.created_at <= 1761894000))
```

Apply temporal filters on the **aggregation concept** (the one being summed/counted), not the grouping concept. Prefer filtering at the constraint level rather than creating separate filtered concepts.

---

## Formulation Analysis

When reviewing an optimization formulation, prioritize ruthlessly. The user wants to know: "Will this solve? If not, what is blocking it?"

### Analysis priorities (in order)

**1. Will cause solver failure:**
- Guaranteed infeasibility: demands > capacities, contradictory constraints, counting impossibilities
- Unused decision variables: defined but never referenced in any constraint or objective
- Empty or constant objective: no decision variables means nothing to optimize
- Problem type mismatch: integer variables requiring a continuous-only solver

**2. LIKELY PROBLEMS -- will cause poor/wrong results:**
- Objective misalignment: direction (min/max) does not match stated goal
- Missing essential constraints: no capacity limits, no demand satisfaction, no balance constraints
- Weak formulation: arbitrary Big-M values (1e9), missing bounds

**3. BEST PRACTICE NUDGES -- improvement opportunities:**
- Coefficient scaling (values span > 6 orders of magnitude)
- Tighter Big-M values possible
- Global constraints for combinatorial structure
- Symmetry breaking for equivalent solutions

### What NOT to do in analysis

- Do not get lost in syntax details -- focus on mathematical correctness
- Do not list every minor improvement -- prioritize ruthlessly
- Do not assume the worst -- if something could be right, note it as "verify"
- Do not restate the entire problem -- be concise
- Do not suggest radical reformulation unless truly necessary

### Business-to-formulation validation

Every formulation should trace back to the user's stated goals. Use this mapping framework:

| User Stated | Formulation Element | Validation Question |
|-------------|---------------------|---------------------|
| How they measure success | Objective function | Does optimizing this expression achieve their success metric? |
| What they're solving for | Decision variables | Do variables represent the decisions the user wants to control? |
| Their requirements and limits | Constraints | Do constraints enforce the rules/limits the user mentioned? |

**Validation rules:**
- Every user requirement should trace to at least one formulation element
- No orphaned formulation elements (elements that don't connect to any stated goal)
- Flag gaps where stated goals are NOT captured in the formulation
- Flag cases where the formulation does something the user didn't ask for

### Semantic Validation Checks

When validating a formulation, apply these checks in priority order.

**REQUIRED checks (violations are severity: critical):**

1. **Concept/Property References** — Verify ALL concepts and properties referenced in variables/constraints/objectives exist in available model concepts. **Exceptions:** (a) Concepts created by variables with `concept_definition` ARE valid — check variable definitions before flagging. (b) Properties matching concept names (e.g., `.site` matching `Site`) are Relationships returning that concept — comparisons like `Concept.site == Site` are valid join conditions, not errors.

2. **All Decision Variables Must Be Used** — Every decision variable MUST appear in at least one constraint OR the objective. Variables that appear nowhere are meaningless — the solver can set them to anything. Note: variables may appear via aliases (check local variable aliases).

3. **Dynamically Created Concepts Must Reference Existing Base Concepts** — If a variable's `concept_definition` creates a new concept, verify it references existing base model concepts. New concepts are typically built via cross-product of existing concepts — no new data tables required.

4. **Data Coverage for Decision Variables** — For `existing` pattern: property must exist on concept with loaded data. For `extended_property`: concept must have entities from loaded data. For `extended_concept`: all referenced concepts must exist with loaded data; entities are created as cross-product. Variable bounds should reference properties that are data-backed.

5. **Constraint Conflicts (Infeasibility)** — Constraints that are logically contradictory will cause solver failure. Examples: `x >= 10` AND `x <= 5` on same variable; capacity constraint tighter than demand requirement.

6. **Trivial Solution Vulnerability (minimize objectives)** — If the objective is MINIMIZE, verify there is a forcing constraint that requires activity (e.g., `sum(Decision.x_quantity) >= Entity.required`). Without one, the solver sets all variables to 0, cost = 0, "optimal" but useless. MAXIMIZE objectives are less prone (profit incentivizes action). If a MINIMIZE objective exists and no constraint with `>=` on demand/requirement, flag it.

7. **Per-Entity Constraints Missing `.per()` Grouping** — For per-entity constraints, the aggregation must be grouped via `.per(Entity)` and the constraint must iterate via `.where(Entity)`. **Relationship-based `.per()` is equivalent:** `.per(Concept.relationship)` where the relationship returns `Entity` is equivalent to `.per(Entity)`. Only flag if the constraint references `Entity.property` on RHS but neither the sum nor the constraint uses `.per(Entity)` or an equivalent relationship-based `.per()`.

8. **Invalid `.where()` Join Patterns** — Check all `.where()` clauses for these known-bad patterns that cause "Type could not be determined" errors or silent 0-match joins:
   - **Two relationship refs compared:** `.where(A.rel(B.rel))` — both sides are relationships to other concepts. Fix: use a Concept type on RHS (`.where(A.rel(ConceptName))`).
   - **Multi-hop RHS:** `.where(A.rel(B.other_rel.nested_prop))` — 2+ hops on RHS silently returns 0 matches. Fix: pre-materialize as enrichment property.
   - **Nested `.where()`:** `.where(.where(...))` — syntax error. Fix: use single `.where()` with comma-separated conditions.
   - **Invented relationship/property names:** References to properties not in the model schema. Fix: verify against RELATIONSHIPS and PROPERTIES sections in context.

**RECOMMENDED checks (violations are severity: warning):**

1. **Goal Alignment** — Objectives should align with the user's stated success metric
2. **Constraint Completeness** — Every user-stated requirement should map to at least one constraint
3. **Objective Alignment** — Minimize/maximize direction matches the business goal
4. **Variable Bounds** — All variables should have meaningful bounds (not placeholder values like 1e9)

**INFORMATIONAL checks (severity: info):**

1. Coefficient scaling — values spanning > 6 orders of magnitude may cause numerical issues
2. Symmetry — equivalent solutions exist that could be broken with additional constraints
3. Big-M values — could be tightened to improve solver performance

### Constraint Interaction Analysis

Constraints work in conjunction — analyze them as a system, not individually. Cross-reference with the "Constraint interaction check", "Slack variable and soft constraint patterns", and "Forcing constraint adequacy" rules in constraint-formulation.md.

Key analysis steps:
1. For each variable in a minimize objective, trace its constraint linkage (slack triad pattern)
2. Verify balance constraints have source/sink exceptions
3. Check per-entity minimums against capacity (hard minimum = no slack on LHS)
4. Ensure at least one constraint forces meaningful activity under minimization (trivial zero risk)
5. Verify coverage + slack + penalty patterns are correctly structured (don't false-positive on soft constraints)

---

## Validation Checklist

Systematic validation catches issues before the solver does (or before the solver silently produces wrong results).

### Phase 1: Structure

**Variables:**
- [ ] Every variable has a clear type (continuous/integer/binary)
- [ ] Every variable has appropriate bounds (lower and upper)
- [ ] Lower bounds <= upper bounds for all variables
- [ ] Bounds are data-backed (not arbitrary placeholder values)
- [ ] Variable type matches physical reality (discrete items -> integer)

**Constraints:**
- [ ] Every constraint includes at least one decision variable
- [ ] All concepts/properties referenced exist in the model
- [ ] Aggregation scopes are correct (grouped/filtered by correct entity)
- [ ] Constraint type matches intent (== vs <= vs >=)
- [ ] No obvious contradictions between constraints

**Objective:**
- [ ] Objective includes at least one decision variable
- [ ] Direction (minimize/maximize) matches business goal
- [ ] All referenced concepts/properties exist
- [ ] Coefficients are from actual data (not zeros or placeholders)

### Phase 2: Completeness

- [ ] Every decision variable appears in at least one constraint OR the objective
- [ ] Capacity constraints present (if resources are limited)
- [ ] Demand/requirement constraints present (if minimums exist)
- [ ] Balance constraints present (if flow or inventory tracking)
- [ ] Logical constraints present (if business rules apply)
- [ ] User's stated "what to optimize" captured in objective
- [ ] User's stated "requirements" captured in constraints
- [ ] User's stated "decisions to make" captured in variables

### Phase 3: Feasibility

- [ ] Total demand <= total capacity (or unmet demand explicitly allowed)
- [ ] Per-entity demands <= per-entity capacities
- [ ] No variable has lower_bound > upper_bound
- [ ] Bounds on sums consistent with bounds on components
- [ ] Equality constraints achievable given variable bounds
- [ ] No contradictory constraints
- [ ] Counting constraints satisfiable (resources exist to satisfy)

### Phase 4: Problem classification

- [ ] Identified as: LP / MILP / QP / QCP / NLP / CSP
- [ ] Documented whether integer/binary variables present (affects solver)
- [ ] Documented whether nonlinear terms present (affects solver)
- [ ] Documented whether primarily constraint satisfaction vs. optimization

### Phase 5: Data

- [ ] All properties referenced in variables, constraints, objective exist in model
- [ ] All referenced properties are numeric (not strings/booleans)
- [ ] No null/NaN values in critical data
- [ ] Units consistent across terms

### Phase 6: Problem size

- [ ] Variable and constraint counts estimated
- [ ] Problem is tractable (< 100k variables typically OK)
- [ ] Number of integer/binary variables considered (drives MIP difficulty)

### Severity classification

**Will prevent valid solution:**
- Unused decision variables (solver sets arbitrarily)
- Missing data references (undefined values)
- Guaranteed infeasibility (conflicting constraints/bounds)
- Problem type incompatible with available solvers

**WARNING (may cause suboptimal or wrong results):**
- Objective misalignment with stated goal
- Missing typical constraints for problem type
- Loose bounds causing numerical issues
- Large coefficient ranges (>10^6 ratio)

**INFO (suggestions for improvement):**
- Problem size concerns
- Potential redundant constraints
- Symmetry that could slow solving

---

## Problem Type Classification

Identifying the problem type early drives better formulation decisions — variable patterns, constraint structures, solver selection, and common pitfalls are all type-dependent.

For the full classification table (semantic + structural signals), disambiguation rules, per-type structural checklists, and template references, see `rai-discovery/prescriptive.md`.

Quick reference for validation use:

| Type | Key structural signal |
|------|----------------------|
| **Resource Allocation** | Continuous variables summing to a total; budget/capacity constraints |
| **Network Flow / Design** | Edge concepts with source/destination; flow conservation |
| **Routing** | Binary arc selection; degree constraints; subtour elimination |
| **Scheduling / Assignment** | Binary assignment variables; coverage + capacity constraints |
| **Pricing** | Price variables; demand-response coupling |

**Note:** Multi-period is an attribute, not a type. A multi-period problem adds time-indexed variables and balance constraints linking periods to whichever base type applies.

---

## Multi-Objective Validation

When a formulation has two objectives (via epsilon constraint loop), validate:

1. **Objectives are in tension**: improving one worsens the other under the same constraints. Test: solve each independently — if both can be optimal simultaneously, they don't need bi-objective treatment (combine into one).
2. **Secondary expressible as constraint**: the secondary objective expression can be wrapped in `model.require(expr >= eps)` or `model.require(expr <= eps)`.
3. **Scale compatibility**: if objectives are on very different scales, the epsilon range may be skewed. Consider normalizing (rates per unit rather than absolutes).
4. **Both objectives reference at least one decision variable**: otherwise one objective is constant and the "tradeoff" is trivial.
