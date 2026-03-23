---
name: rai-prescriptive-problem-formulation
description: Formulates optimization problems from ontology models covering decision variables, constraints, objectives, and common patterns. Use when building, reviewing, or debugging a formulation.
---

# Problem Formulation
<!-- v1-SENSITIVE -->

## Summary

**What:** Optimization formulation — decision variables, constraints, objectives, and common problem patterns. Assumes a problem has already been selected via discovery.

**When to use:**
- Formulating variables, constraints, and objectives for a selected problem
- Reviewing or validating an existing formulation
- Translating business requirements into mathematical formulation
- Debugging trivial solutions, infeasibility, or missing constraints
- Choosing between variable types (continuous, integer, binary)
- Designing multi-concept coordination (flow networks, selection + quantity)

**When NOT to use:**
- Problem discovery (suggesting problems for an ontology, reasoner classification) — see `rai-problem-discovery/SKILL.md`
- PyRel syntax (imports, types, property patterns, stdlib) — see `rai-pyrel-coding`
- Ontology modeling or model enrichment (concept design, gap classification) — see `rai-ontology-design`
- Solver execution and diagnostics (solver selection, parameters, numerical stability) — see `rai-prescriptive-solver-management`
- Post-solve interpretation (extraction, quality assessment, explanation) — see `rai-prescriptive-results-interpretation`
- Aggregation syntax (count/sum/per patterns) — see `rai-querying`

**Overview:**
1. Define decision variables (type, bounds, scope, naming)
2. Define constraints (forcing, capacity, balance, linking; validate interactions)
3. Define objective (direction, coefficients, multi-component handling)
4. Validate the complete formulation (structure, completeness, feasibility, data)
5. Simplify (static parameters, goals vs constraints, grouped constraints)

---

## Formulation Workflow

After a problem is selected (from problem discovery) and the ontology is enriched (if needed), build the formulation in this order:

### Step 1: Define Variables
What decisions are being made? What can the solver control?
- Start with the base model context — examine concepts, properties, relationships (Variable Context Integration)
- Identify the primary decision entity first, then auxiliary/aggregation variables (Variable Principles)
- Choose variable types (continuous/integer/binary) and set bounds from data (Advanced Variable Patterns)
- For minimize objectives, include a slack/unmet variable to avoid infeasibility

### Step 2: Define Constraints
What rules must the solution satisfy?
- Start with model structure + user goals (Constraint Context Integration)
- Add forcing constraints first — these prevent trivial zero solutions for minimize objectives
- Add capacity/resource constraints from data properties
- Add flow conservation if the model has network structure
- Derive parameters from data ranges, not arbitrary values (Parameter Derivation from Data)

### Step 3: Define Objective
What are we optimizing?
- Start with user's stated goal — map business language to minimize/maximize (Objective Context Integration)
- Reference defined variables and data properties in the expression
- Check for trivial solution risk: "If all variables = 0, are all constraints satisfied?" If yes, Step 2 needs a forcing constraint.

### Step 4: Validate
Is the formulation complete and correct?
- Every variable appears in at least one constraint or the objective
- Every constraint references at least one decision variable
- Forcing constraints exist for minimize objectives
- Join paths in `.where()` clauses connect to actual data
- Bounds are consistent (lower <= upper)

### Step 5: Simplify (iterate)
Can we reduce complexity without losing correctness?
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for hard requirements
- Group-level constraints over pairwise/granular combinations

For detailed patterns for each step, see [variable-formulation.md](references/variable-formulation.md), [constraint-formulation.md](references/constraint-formulation.md), and [objective-formulation.md](references/objective-formulation.md).

---

## Formulation Principles

These are overarching principles that apply to all optimization formulations regardless of problem type or solver.

1. **Context-aware:** Suggestions must be tailored to the specific model's entities, not generic templates.
2. **Specific, not generic:** Provide formulations with actual entity names, not abstract examples.
3. **Rationale-driven:** Explain WHY each element makes sense for THIS problem.
4. **Goal-aligned:** If the user provided goals, ensure every formulation element supports those goals.
5. **Valid variations welcome:** There is no single "right answer." Multiple valid approaches exist for most problems. Different valid formulations are acceptable and encouraged, as long as they are grounded in the model and feasible.
6. **All decision variables must be used:** Every variable must appear in at least one constraint or the objective. Variables that appear nowhere are useless -- the solver can set them to anything, which almost always indicates a bug.

---

## Business Language Framing

When presenting variables, constraints, and objectives to the user, describe them in business terms first ("ensure each customer's demand is met," "don't exceed warehouse capacity"), then provide the technical formulation. The analyst selects based on business understanding; the code is generated behind the scenes. Never force users to think in mathematical terms -- business language in, business language out, with valid PyRel as the executable bridge.

**Natural language rule for all user-facing text:** Use domain-natural language in every `description`, `rationale`, `business_mapping`, problem `statement`, and explanation field. Technical `Concept.property` references confuse business users — translate them to readable phrases:
- `Operation.cost_per_unit` -> "cost per unit for each operation"
- `sum(Shipment.quantity)` -> "total shipment volume"
- `Site.capacity` -> "each site's available capacity"
- `UnmetDemand.x_slack` -> "unmet demand quantity"
- `sum(Assignment.x_assigned).per(Worker)` -> "number of assignments per worker"

Code snippets in `solver_registration`, `expression`, and `entity_creation` fields remain technical (valid PyRel). But every field the user reads should sound like a business analyst wrote it, not a database query.

### Eliciting Constraints from Business Users

Non-OR users rarely describe their problem in terms of "constraints" and "objectives." Use these diagnostic questions to surface the formulation elements:

| Question to ask | What it surfaces |
|----------------|-----------------|
| "What limits must the solution respect?" | Capacity constraints (budget, headcount, storage, time) |
| "What must every solution achieve?" | Forcing/requirement constraints (meet all demand, cover all shifts) |
| "What would you prefer if possible, but could live without?" | Soft goals → objective terms, not hard constraints |
| "What makes a solution completely unacceptable?" | Hard constraint violations (safety, regulatory, contractual) |
| "Are there minimum service or coverage levels?" | Lower-bound forcing constraints |

**Technique:** Start with "What makes a solution unacceptable?" — this reliably surfaces hard constraints. Then ask "What would make one acceptable solution better than another?" — this surfaces objective terms.

### Business Constraint Disambiguation

Common business phrases are ambiguous between constraint and objective. Always clarify before formulating.

| Business phrase | Interpretation A (constraint) | Interpretation B (objective) |
|----------------|-------------------------------|------------------------------|
| "Keep costs under $X" | Hard budget: `total_cost <= X` | Minimize cost (no hard cap) |
| "Each store should get at least 100 units" | Hard minimum: `supply[s] >= 100` | Soft target: penalize shortfall in objective |
| "Try to balance across regions" | Hard fairness: `max - min <= threshold` | Minimize imbalance in objective |
| "We need to cover all shifts" | Hard coverage: `sum(assign[s,w]) >= 1` for all s | Maximize coverage (allow gaps) |
| "Don't use more than 3 suppliers" | Hard cardinality: `sum(use[s]) <= 3` | Minimize number of active suppliers |

**Decision rule:** If violating it makes the solution invalid or unacceptable → **constraint**. If it is a preference or "nice to have" → **objective term**. When unclear, default to soft (objective) and ask the user: "If the optimizer found a solution that violates this but saves 20% on cost, would that be acceptable?"

---

## Business-to-Formulation Mapping

Translating business language into mathematical formulation requires mapping three things: what decisions are controlled (variables), what limits must be respected (constraints), and what is being optimized (objective).

### Identifying variables from business context

| Business language | Variable type | What to look for |
|-------------------|---------------|-----------------|
| "assign", "schedule", "select" | Binary | Assignment/selection entities |
| "produce", "manufacture", "ship", "order" | Integer | Discrete units |
| "allocate %", "invest", "price" | Continuous | Divisible amounts |
| "how many", "count", "number of" | Integer | Countable quantities |
| "optimize", "balance" | Depends | The controllable quantities in the model |

### Identifying constraints from business context

| Business language | Constraint type | Pattern |
|-------------------|-----------------|---------|
| "capacity", "limit", "maximum", "cannot exceed" | Capacity | `variable <= capacity` |
| "must meet", "at least", "minimum", "require" | Requirement | `variable >= minimum` |
| "balance", "conserve", "in = out" | Conservation | `inflow == outflow` |
| "only one", "either/or", "if then" | Logical | Conditional expressions |
| "fair", "balanced", "even distribution" | Equity | Variance or ratio constraints |

### Identifying objectives from business context

| Business language | Direction | Typical expression | User-facing description |
|-------------------|-----------|-------------------|------------------------|
| "cost", "expense", "spend" | Minimize | `sum(entity.cost * entity.quantity_var)` | Minimize total operating cost |
| "profit", "revenue", "return" | Maximize | `sum(entity.price * entity.quantity_var)` | Maximize total profit across all products |
| "satisfy", "meet demand", "service" | Min unmet | `sum(demand - fulfilled)` | Minimize unmet customer demand |
| "efficient", "utilize", "throughput" | Maximize | `sum(quantity_var / capacity)` | Maximize resource utilization across facilities |
| "waste", "leftover", "unused" | Minimize | `sum(capacity - quantity_var)` | Minimize wasted capacity |
| "fair", "balanced", "equal" | Min variance | `sum((value - avg)^2)` or max-min | Balance workload evenly across teams |

---

## Multi-Concept Coordination

If you suggest MULTIPLE cross-product/junction concepts, coordinate them as follows:

**1. Flow Networks** -- If concepts represent flow at different stages:
   - Source concept (e.g., ProductionQuantity at factories)
   - Transport concept (e.g., ShipmentQuantity on routes)
   - Destination concept (e.g., FulfillmentQuantity at customers)

   These typically need conservation constraints: inflow = outflow at pure transshipment nodes, or inventory balance at storage nodes.
   **In rationale**: Note which base entity will need a balance constraint.

**2. Selection + Quantity** -- If one concept is binary (use/don't use) and another is continuous quantity on related entities:

   These typically need linking: quantity <= capacity * selection
   **In rationale**: Note the linking relationship needed.

**3. Shared Base Entities** -- If multiple decision concepts connect to the SAME base entity (e.g., both touch Site via relationships):

   These often need a balance/conservation constraint at that entity.
   **In rationale**: Explicitly state "Links to [OtherConcept] via [SharedBase]"

**NOTE**: Without linking constraints, multiple decision concepts may produce:
- Trivial solutions (all zeros -- concepts optimized independently)
- Unbounded solutions (no coupling between flows)
- Inconsistent solutions (flows don't balance)

This is often unintended, but not always wrong — the user may intentionally leave variables unlinked. Flag it as something to verify, not as an error.

**RECOMMENDED in rationale for multi-concept suggestions:**
- State how concepts relate to each other
- Identify shared base entities
- Note what type of linking constraint may be needed

---

## Formulation Simplification

Users often propose formulations that seem natural from a business perspective but create unnecessary complexity.

### Static parameters vs. dynamic calculations

**The problem:** Users want constraints that depend on dynamically calculated values ("capacity can't exceed 3x last period's utilization," "limit should be 150% of historical average").

**Why it is problematic:** Requires pulling historical data at solve time, makes the model harder to debug, creates hidden dependencies, and makes what-if analysis difficult.

**Better approach:** Use static parameters that can be easily updated. Instead of computing a dynamic cap, set a static limit that achieves the same constraint. The user can update it when planning changes.

**When dynamic IS appropriate:** The calculation is simple and stable (e.g., sum of child values), the relationship is fundamental (e.g., inventory balance), or real-time data is essential (rare in planning problems).

### Requirements vs. goals: constraint or objective?

**The fundamental distinction:**
- **Requirements** (non-negotiable) become **constraints**: must be satisfied for a valid solution
- **Goals** (can trade off) become **objective terms**: what we are trying to achieve, with priorities

It is a REQUIREMENT (constraint) if:
- Violating it makes the solution invalid/unusable
- There are contractual, legal, or safety implications
- It is a physical impossibility to violate (capacity, conservation)

It is a GOAL (objective) if:
- Missing it is undesirable but the solution is still useful
- There are trade-offs between competing targets
- Priorities exist (some targets matter more than others)
- You want visibility into how close you got

**The problem with goals-as-constraints:** Problem becomes infeasible if goals conflict with capacity. No solution tells you nothing about which goal caused the conflict. Small data changes can flip from feasible to infeasible.

**Better approach for goals:** Use shortfall variables and penalty terms in the objective. This lets the optimizer trade off between goals and shows how close you got to each target.

### Grouped constraints vs. granular combinations

**The problem:** Users specify constraints for specific entity combinations ("Facilities A and B combined must handle 60% of demand"). This creates many specific constraints, is hard to maintain as entities change, and obscures the underlying business intent.

**Better approach:** Define groups that capture the business intent. A single group constraint replaces multiple pairwise constraints. Adding/removing members means updating group membership, not rewriting constraints.

**When granular IS appropriate:** Truly entity-specific rules (contractual minimums with specific partners), temporary exceptions, or when the grouping does not exist conceptually in the business.

### Recognizing over-specification

| User says | Likely issue | Better approach |
|-----------|-------------|-----------------|
| "calculated from historical data" | Dynamic dependency | Static parameter |
| "MUST hit target" | Goal vs. requirement unclear | Clarify, then constraint or objective |
| "X and Y combined" | Granular combinations | Meaningful groups |
| "factor in the score/rating" | Complex constraint coefficient | Objective term |
| "only if", "depends on" | Conditional complexity | Simplify or use indicator |

### Simplification principles

**Prefer:**
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for requirements
- Group-level constraints over pairwise/granular combinations
- Simple bounds over conditional logic

**The test:** "If the business context changes slightly, how hard is it to update this formulation?" A good formulation requires changing one parameter or group membership. A problematic formulation requires rewriting multiple constraints.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| All-zero solution on minimize | Missing forcing constraints (demand satisfaction, coverage) | Add `sum(x).per(Entity) >= Entity.demand` or equivalent |
| Infeasible after adding constraints | Conflicting bounds or over-specified assignments | Organize constraints into essential/full tiers; add incrementally |
| Variables created but unused in objective | `solve_for` registered but objective references different properties | Verify objective expression includes all decision variable properties |
| Wrong aggregation scope | `.per(Y)` but Y not joined to the summed concept | Add explicit relationship join in `.where()` |
| Big-M too loose -> slow solve | Using arbitrary `999999` instead of data-driven bound | Use `M = capacity` or `M = max_demand` from entity properties |
| Missing forcing requirement | MINIMIZE objective with no forcing constraint yields zero | Always identify what real-world requirement forces positive activity |
| Constraint references unwired relationship | Relationship declared but no `define()` data binding | Verify all relationships in `.where()` joins have `define()` rules. Unwired relationships cause TyperError or silently match zero entities. |

### Unwired Relationships

A declared `model.Relationship()` without a corresponding `model.define()` rule has NO DATA at solve time. The relationship exists in the schema but has zero bindings.

**Symptoms:**
- `TyperError` during solve ("type inference" or "type could not be determined")
- Constraints silently match zero entities (empty joins)
- `.per(Concept)` aggregations return nothing

**Check:** For every relationship in a constraint `.where()` clause, verify a `model.define()` rule populates it. If no define rule exists, the relationship is unwired — do not use it in constraints.

**Example:**
```python
# WRONG: constraint uses unwired relationship (no define() rule)
sum(Operation.x_flow).where(Operation.transformation == Site).per(Site) >= Site.demand

# CORRECT: use a relationship with define() data binding, or join via shared identity properties
Op = Operation.ref()
UD = UnmetDemand.ref()
sum(Op.x_flow).where(Op.output_sku == UD.sku).per(UD.sku)
```

---

## Examples

| Problem Type | Pattern Demonstrated | File |
|---|---|---|
| Diet optimization | Continuous vars + ternary property join for per-nutrient constraint | [examples/diet.py](examples/diet.py) |
| Network flow | Flow conservation per node using two independent Edge refs | [examples/network_flow.py](examples/network_flow.py) |
| Shift assignment | Binary vars scoped to availability + per-entity coverage constraints | [examples/shift_assignment.py](examples/shift_assignment.py) |
| Portfolio balancing | Pairwise quadratic risk via Stock.ref() + Float.ref() covariance binding | [examples/portfolio_balancing.py](examples/portfolio_balancing.py) |
| Supply chain transport | Multi-concept coordination: inventory conservation + mode selection + model.union() objective | [examples/supply_chain_transport.py](examples/supply_chain_transport.py) |
| Retail markdown | One-hot selection, price ladder constraint, cumulative tracking with temporal recurrence | [examples/retail_markdown.py](examples/retail_markdown.py) |
| Factory production | Partitioned sub-problem solving with `populate=False` and `where=[filter]` | [examples/factory_production.py](examples/factory_production.py) |
| Traveling salesman | Derived scalar bounds, MTZ subtour elimination, degree constraints, walrus aliasing | [examples/traveling_salesman.py](examples/traveling_salesman.py) |
| Machine maintenance | Conflict-graph mutual exclusion via Conflict concept + dual `.ref()` | [examples/machine_maintenance.py](examples/machine_maintenance.py) |
| Order fulfillment | Fixed-charge facility location: FCUsage tracking concept + linking constraint | [examples/order_fulfillment.py](examples/order_fulfillment.py) |
| Hospital staffing | Overtime hinge variable + skill-filtered aggregation + unmet demand penalty | [examples/hospital_staffing.py](examples/hospital_staffing.py) |
| Sprint scheduling | Epoch filtering pipeline + skill-constrained assignment domain + weighted completion | [examples/sprint_scheduling.py](examples/sprint_scheduling.py) |
| Demand planning (temporal) | Multi-period flow conservation with time-indexed multiarity variables + model.union() objective | [examples/demand_planning_temporal.py](examples/demand_planning_temporal.py) |
| Vehicle scheduling | Fixed-charge vehicle usage with big-M linking to binary assignments | [examples/vehicle_scheduling.py](examples/vehicle_scheduling.py) |
| Grid interconnection | Capacity expansion — two coupled binary decision sets sharing a resource constraint + budget knapsack | [examples/grid_interconnection.py](examples/grid_interconnection.py) |
| Ad spend allocation | Semi-continuous variables via binary activation indicator + per-campaign and global budget | [examples/ad_spend_allocation.py](examples/ad_spend_allocation.py) |
| N-queens (Integer) | Pairwise inequality constraints with `.ref()`, `Problem(model, Integer)`, MiniZinc | [examples/n_queens.py](examples/n_queens.py) |
| Sudoku (Integer) | `all_different` global constraint with `.per()` grouping, standalone property variables | [examples/sudoku.py](examples/sudoku.py) |

---

## Formulation Analysis Context

When reviewing a formulation, the LLM must understand these naming and reference conventions to avoid false positives:

### Local Aliases and Constants

If local variable aliases are defined (e.g., `Al -> Allocation.ref()`), then `Al.quantity` is VALID — refs use the slot name, no x_ prefix. If constants are defined (e.g., `MULTIPLIER = 2.0`), they ARE defined. Do NOT flag these as "undefined" — the code compiles and runs; if something were truly undefined, RAI would catch it.

### Decision Variable Naming Convention

- Decision variable attributes use `x_` prefix: `Entity.x_var_name` in Python code
- Property template strings use the SLOT name (no x_): `"{Entity} has {var_name:float}"`
- Ref-based access uses the slot name (no x_): `E = Entity.ref(); E.var_name`
- Do NOT flag variables as unused if you see the property name in constraints/objectives

### Expression Parsing Limitations

- Constraint expressions may be TRUNCATED or SUMMARIZED (e.g., `"sum(...)"` instead of full expansion)
- Variables used inside inline aggregations (`sum()`, `select()`, `where()`) may not appear in the expression string
- **Do NOT flag variables as unused if they appear in aggregation hints or are typical for the problem type**

### Derived vs Decision Variables

- Some properties are COMPUTED (e.g., `distance = sqrt(...)`) not decision variables
- Computed properties don't need to appear in constraints
- Only flag DECISION variables (from `solve_for()`) as unused, NOT computed properties

### V1 Aggregation Patterns

Structure: `sum(X.prop).where(filter).per(grouping)`
- `.where()` on sum: FILTERS which items are aggregated
- `.per()` on sum: GROUPS the aggregation (one value per group)
- `.where()` on require(): ITERATES (one constraint per entity)

**For per-entity constraints, BOTH `.per()` AND `iteration_entity` are needed:**
- `.per(Entity)` makes sum produce one value per Entity
- `iteration_entity` makes constraint iterate over each Entity

Python variables holding expressions (e.g., `total = sum(...)`) are valid — don't flag as undefined.

### Python Variables in Constraints

Code uses Python variables for intermediate expressions. If an identifier is assigned before use, it's VALID.

---

## Formulation Validation Rules

### Issue Severity

Maps to the Semantic Validation Checks in problem-patterns-and-validation.md:
- **critical**: REQUIRED check violations — will cause runtime errors or solve failures (checks 1-6)
- **warning**: RECOMMENDED check violations — may cause suboptimal solutions (checks 7-10)
- **info**: INFORMATIONAL findings — suggestions for improvement (checks 11-13)

### Issue Categories

| Category | Check | Severity |
|----------|-------|----------|
| `invalid_reference` | References to non-existent concepts or properties | critical |
| `variable_usage` | Variables not used in constraints/objective | critical |
| `concept_definition_reference` | Dynamically created concepts reference non-existent base concepts | critical |
| `data_coverage` | Variable bounds/limits reference properties not in schema | critical |
| `constraint_conflict` | Logically contradictory constraints | critical |
| `missing_iteration_entity` | Per-entity constraint missing `.per()` on sum and/or `iteration_entity` | critical |
| `goal_alignment` | Formulation does not match user's stated goals | warning |
| `constraints` | Missing or incomplete constraints | warning |
| `objective` | Objective misalignment with stated goal | warning |
| `bounds` | Unrealistic or improperly specified bounds | warning |
| `coherence` | Logical inconsistencies between components | info |
| `problem_size` | Tractability concerns | info |
| `data_availability` | Missing data for goals | info |

### fix_action Guidelines

- Include fix_action for critical and warning issues when a concrete fix can be automated
- Only include fix_action for critical and warning issues — info-level issues and vague recommendations should not have fix_actions, since attempting to auto-fix them produces low-quality or harmful changes
- For each fix type, include ONLY the relevant definition object:
  - `add_variable` / `create_concept`: include `variable_definition` with all variable fields
  - `add_constraint`: include `constraint_definition` with name, expression, optional filter, optional iteration_entity
  - `modify_constraint`: include `constraint_definition` with fields to update, use `target` for constraint name. Use this to fix missing `.per()`: update expression to include `.per(Entity)` on aggregations.
  - `modify_variable`: include `variable_definition` with fields to update, use `target` for variable name. Use this to fix entity_creation logic, bounds, or other variable definition issues.
  - `add_iteration_entity`: include `iteration_entity` (the concept name), use `target` for constraint name
  - `modify_objective`: include `objective_definition` with type and expression
  - `remove_item`: include `item_type` ("variable" or "constraint") and use `target` for the name

### False Positive Prevention

These patterns are valid and should not be flagged as issues:

- **Syntax and "undefined" names** — RAI handles syntax validation at compile time. Flagging syntax issues here produces false positives.
- **Aliases and constants** — Check LOCAL VARIABLE ALIASES and CONSTANTS sections before flagging anything as undefined. If `Al = Allocation.ref()` is defined, then `Al.quantity` is valid. If `MULTIPLIER = 2.0` is defined, it's defined. RAI catches truly undefined names at compile time.
- **`iteration_entity` with `.per()`** — When `iteration_entity` is set, code_gen automatically adds `.per(iteration_entity)` to sums. Missing `.per()` with a set iteration_entity is not an issue.
- **Relationship-based `.per()`** — `.per(Concept.relationship)` is equivalent to `.per(Entity)` when the relationship returns that Entity type. Treat them as interchangeable.
- **Correctly formulated constraints** — When analysis concludes a constraint is correctly formulated, accept it rather than flagging as "missing_iteration_entity".
- **Concept name matching** — Use bare concept names (e.g., `Site`, `SKU`) matching EXACT names from the model context. A property name matching a concept name (e.g., `.site` and `Site`) is a valid Relationship returning the target concept.
- **Variables inside aggregations** — Expressions containing `sum()`, `select()`, or `where()` use variables within them, even if not visible in the top-level expression string.
- **Computed vs decision properties** — Only flag decision variables (from `solve_for()`) as unused, not computed properties.
- **Trust reasonable formulations** — If the formulation looks reasonable, it probably is. Only flag issues with clear evidence of error.

### Variable Usage Rules

- A variable used only in constraints (not in objective) is valid — constraints give the variable meaning
- A variable used only in the objective (not in constraints) is valid — it contributes to the optimization goal
- Only flag as "unused" if a variable appears in neither constraints nor objective
- Check constraints before concluding a variable is unused based on objective absence — the PRE-ANALYSIS section shows variable usage counts

---

## Pre-Solve Fix Patterns

### Aggregation Scope Binding

When writing `.per(A)`, ONLY reference `A` or `A.relationship.property` in `.where()` — NEVER standalone concepts.
- **WRONG:** `.where(X == OtherConcept.property).per(A)` — OtherConcept is unbound
- **RIGHT:** `.where(X == A.relationship_to_other.property).per(A)` — navigate from A

Check MODEL RELATIONSHIPS for valid paths.

### Fix: trivial_solution_risk (Missing Forcing Constraint)

A MINIMIZE objective needs a constraint that FORCES positive activity.
- Pattern: `sum(<Decision>.x_<var>).where(<join_condition>).per(<Entity>) >= <Entity>.<required>`
- Decision variable attributes use `x_` prefix; data properties (requirements, capacities) do NOT
- Look for: demand/requirement entities, quantity properties from model context

### Fix: Join Path Issues (DO THIS FIRST)

If an existing constraint has a broken join, DO NOT add aggregate workarounds like `sum(X) >= 0.5 * sum(Y)`.
Instead, FIX THE ACTUAL JOIN by finding the correct path through MODEL RELATIONSHIPS:
1. Identify what the join should match on (location, SKU, entity ID, etc.)
2. Find the path FROM the decision concept TO the matching property
3. Find the path FROM the requirement concept TO the same property
4. Both paths must lead to the SAME underlying data type

Example fix: If `Flow.destination == Customer.site` doesn't match because Customer is unbound:
- Check MODEL RELATIONSHIPS for how to reach Customer from Flow or Demand
- Likely fix: `Flow.destination == Demand.customer.site` (navigate from Demand to its customer)

### Fix: missing_conservation (Disconnected Extended Concepts)

Two extended_concept concepts sharing a base entity need a LINKING constraint.
- Pattern: `sum(<ConceptA>.x_<qty>).per(<SharedEntity>) == sum(<ConceptB>.x_<qty>).per(<SharedEntity>)`
- Decision variable attributes use `x_` prefix; base entity properties do NOT
- Look for: shared relationships between the concepts (same location, product, time)

### Fix: undeclared_variable_reference

Two strategies (prefer B when semantically equivalent):
- **Strategy A (add_variable):** Add the base model x_ property as a decision variable. Only use when the x_ property is genuinely needed as a separate decision from existing variables.
- **Strategy B (modify_constraint — PREFERRED):** Rewrite the constraint/objective to use an already-defined variable instead. This is preferred when the defined variable serves the same semantic role.

### Key Syntax Rules for Fixes

- Expression should be JUST the condition — do NOT include `require()` wrapper
- The code generator will automatically wrap with `p.satisfy(require(...))`
- Use `sum(<Concept>.<property>).per(<GroupConcept>)` for per-entity requirements
- Use ACTUAL concept/property names from the formulation

### Fixes MUST Reference Decision Variables

- Look at the VARIABLES section to identify decision variables
- Every fix constraint MUST include at least one variable from that section
- NEVER suggest constraints on data-only properties (costs, capacities, etc.)
- Data validation is not a solver constraint — if data is bad, the fix is outside optimization

---

## Known Limitations

### Multi-component objectives with `model.union()`

Do not use `+` to combine cost terms from independent concept groups — this causes `AssertionError: Union outputs must be Vars`. Use `model.union()` instead.

**Critical:** Each branch of `model.union()` must be a **per-entity expression** (bound to a concept), NOT a fully-aggregated scalar. Keep costs at concept level and let the outer `sum()` aggregate:

```python
# CORRECT: per-entity cost expressions inside model.union()
p.minimize(sum(model.union(
    FreightGroup.holding_cost * sum(x_inv).per(FreightGroup).where(...),  # per-FreightGroup
    Arc.transport_cost * Arc.x_flow,                                       # per-Arc
    Factory.unit_cost * Factory.x_production,                              # per-Factory
)))

# WRONG: scalar sums inside model.union()
p.minimize(sum(model.union(
    sum(x * FreightGroup.cost),   # scalar — causes AssertionError
    sum(Arc.x_flow * Arc.cost),   # scalar — causes AssertionError
)))
```

For parametric (time-indexed) variables, use `sum(var).per(Concept).where(...)` to aggregate over time while keeping per-entity:
```python
prod_cost = ProdCapacity.production_cost * sum(x_prod).per(ProdCapacity).where(
    ProdCapacity.x_production(t, x_prod))
```

`model.union()` collects ALL matching values from each branch (set union semantics). This is distinct from `|` (pipe), which picks the first successful branch (ordered fallback).

**Additional v1 pitfalls with parametric variables:**
- **`name=[]` must NOT traverse relationships** — use identity fields (e.g., `ProdCapacity.site_id`) not `ProdCapacity.site.name` (causes FD violation)
- **Cross-concept joins need distinct attribute names** — if two concepts both have `site_id` as `identify_by`, rename one (e.g., `wk_site_id`) to avoid ambiguity
- **Only one objective supported** — HiGHS rejects multiple `minimize()`/`maximize()` calls

### Constraint naming with lists

Name constraints with list expressions for readable debug output:

```python
p.satisfy(model.require(
    Edge.x_flow <= Edge.capacity
), name=["capacity", Edge.i, Edge.j])
# Produces names like: "capacity_1_3", "capacity_2_5"
```

List elements are joined with underscores. Use entity identifiers (IDs, names) in the list for per-entity constraint names.

### Re-Solve Behavior (1.0.3+)

Re-solving the same `Problem` instance is safe. Result import uses `experimental.load_data` with replace semantics — previous results remain intact if a subsequent solve fails. The inline formulation pattern (fresh `Problem` per scenario loop iteration) is still useful for clean separation of scenarios, but is no longer required for error recovery.

### PyRel is additive — nothing can be removed or modified in-place

PyRel's model and problem APIs are **append-only**. Every call to `model.define()`, `model.Property()`, `model.Concept()`, `p.solve_for()`, `p.satisfy()`, `p.minimize()`/`p.maximize()` **adds** to the model or problem. There is no API to remove, replace, or modify any existing element.

**This applies to the entire stack:**
- **Attributes/properties:** Adding a new `model.Property()` or `model.Relationship()` grows the model. You cannot delete or rename an existing property.
- **Concepts:** New `model.Concept()` calls add concepts. Existing concepts cannot be removed.
- **Variables:** Each `p.solve_for()` registers an additional decision variable. You cannot unregister one.
- **Constraints:** Each `p.satisfy()` accumulates. Adding a "corrected" version does not replace the original — both remain active, and the tighter one binds.
- **Objectives:** Only one `p.minimize()` or `p.maximize()` per Problem.

**Practical impact:**
- To change constraints or variables, you must create a **new Problem** and re-register all elements from scratch.
- Multi-scenario optimization must use a new `Problem` per scenario.
- Model-level changes (new properties, concepts) persist across all subsequent Problems on that model — plan the model schema before building formulations.

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Variable formulation | Types, bounds, scope, entity creation, slack variables, context integration | [variable-formulation.md](references/variable-formulation.md) |
| Constraint formulation | Forcing, capacity, balance, linking, `.where()` scoping, parameter derivation | [constraint-formulation.md](references/constraint-formulation.md) |
| Objective formulation | Direction, multi-component, penalty terms, scenario formulation | [objective-formulation.md](references/objective-formulation.md) |
| Problem patterns & validation | Common patterns (assignment, flow, knapsack) and the validation checklist | [problem-patterns-and-validation.md](references/problem-patterns-and-validation.md) |
