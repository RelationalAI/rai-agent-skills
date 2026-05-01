# Fix Generation Guidelines

## Table of Contents
- [Fix Generation Guidelines](#fix-generation-guidelines-1)
- [Join Path Fix Rules](#join-path-fix-rules)
- [Fix Strategy: Trivial Solution](#fix-strategy-trivial-solution)
- [Fix Strategy: Infeasible Solution](#fix-strategy-infeasible-solution)

---

## Fix Generation Guidelines

When generating fixes for trivial or poor-quality solutions, follow these rules:

**Root cause taxonomy:**

| Root Cause | Description | Typical Fix |
|------------|-------------|-------------|
| `missing_forcing_constraint` | No constraint requires positive variable values; "do nothing" is optimal | Add demand satisfaction or coverage constraint |
| `entity_creation_filter` | Cross-product entity creation has `.where()` joins that match zero rows | Fix join conditions to match actual data relationships |
| `disconnected_concepts` | Multiple variable sets exist but are not linked through constraints | Add conservation or linking constraints at shared entities |

**Fix priority rule:** Prefer constraint fixes (`add_constraint`, `modify_constraint`) over variable fixes (`add_variable`). Adding variables increases problem complexity; adding constraints focuses the existing formulation.

**Grounding rules — all fixes must use actual model context** (ungrounded fixes produce compile errors or silently match zero entities):
- Use actual concept and property names from the model — invented names cause compile errors
- Only reference relationships and properties that EXIST in the model
- Check data samples to understand what values are actually available
- Examine the current formulation to understand what is already defined
- Use `.per(<Entity>)` at the correct granularity based on model relationships
- Link decision variable sums to actual requirement values using correct relationship paths

**When suggesting `add_variable` (use sparingly):**
- Base the new variable's scope on existing concepts from the model — variables referencing non-existent concepts cause compile errors
- Use `.where()` filters based on actual property values from data samples
- Reference actual relationship paths that exist in the model
- For concept and variable creation syntax, see [variable-formulation.md](variable-formulation.md)

**Constraint fix requirements** (constraints without decision variables cause `ValueError` at solve time):
- Reference at least one decision variable (`x_` prefix)
- Avoid self-defeating constraints (e.g., constraining a variable to equal a value that makes the objective worse while also requiring the objective to improve)
- Connect to real requirements in the data — the fix should force positive activity

---

## Join Path Fix Rules

When fixing trivial solutions, the primary approach is to fix broken join paths in constraints — NOT to add aggregate workarounds.

**Diagnosis steps:**
1. Identify the join condition that should link decision variables to requirements (location, SKU, ID, etc.)
2. Check MODEL RELATIONSHIPS for valid paths from BOTH sides to that shared property
3. Both paths must reach the SAME underlying data — if not, find the correct navigation path
4. Common fix: Replace `UnboundConcept.property` with `BoundConcept.relationship.property`

**Example:** If `Flow.destination == Customer.site` matches nothing because `Customer` is unbound:
- Find how Customer relates to the requirement concept (e.g., `Demand.customer`)
- Fix: `Flow.destination == Demand.customer.site` (navigate from the bound concept `Demand`)

**Navigation path rules:**
- When using `.per(Entity)`, ALWAYS navigate FROM that entity
- Standalone concept references like `Customer.site` or `Site.id` typically produce a wrong join — either an unintended cartesian product across all `Customer`/`Site` rows, or no overlap with the bound rows the constraint is iterating over
- Instead use: `Demand.customer.site` (navigating from the `.per()` entity)

**Aggregate workarounds are NOT fixes:**
- Do NOT suggest constraints like `sum(X) >= 0.5 * sum(Y)` or `sum(X) >= some_fraction * total`
- These mask the real problem (broken joins) and don't properly link decisions to requirements
- If you cannot find a valid join path, report the model gap rather than working around it

**Per-entity vs aggregate constraint patterns:**
- WITHOUT `.per()` for per-entity minimums: `Decision.x_quantity >= Entity.demand` — creates one constraint per entity automatically
- WITH `.per()` for aggregation: `sum(Decision.x_quantity).per(Entity) >= Entity.required` — sums decision vars per entity

---

## Fix Strategy: Trivial Solution

Use this strategy when the solution is OPTIMAL but trivial (all zeros, zero objective, vacuous satisfaction).
The root cause is almost always **missing forcing constraints** — the solver found a "do nothing" shortcut.

**FORCING-FIRST APPROACH:**
The solver found a solution but it is trivial (all zeros or near-zero objective). This means the
formulation LACKS constraints that force meaningful activity. The solver found a "shortcut" that
satisfies all constraints by doing nothing.

Root cause is almost always: missing forcing constraints. For example:
- A minimize-cost problem with no demand satisfaction constraint: zero flow is cheapest
- An assignment problem with no coverage requirement: assigning nobody satisfies all constraints

**Fix priority order:**
1. Add FORCING constraints that require meaningful activity (demand satisfaction, coverage, minimum utilization)
2. Modify existing constraints to be tighter (lower bounds, equality instead of inequality)
3. Check if existing forcing constraints reference the wrong properties or have wrong direction (>= vs <=)
4. Add new variables only if the current variable set cannot express the forcing requirement

**Emphasis:** Focus on adding FORCING constraints — this is a TRIVIAL solution where the solver found a zero-activity shortcut.

---

## Fix Strategy: Infeasible Solution

Use this strategy when the solver returned INFEASIBLE or a previous fix caused infeasibility.
The root cause is **over-constraining** — conflicting or too-tight constraints make feasibility impossible.

**RELAXATION-FIRST APPROACH:**
This formulation was built with comprehensive constraint selection but the solver found NO feasible solution.
The constraints are mutually contradictory or over-restrictive. Before adding anything, identify which constraint to relax or drop, then **rebuild the Problem** omitting or replacing the offending `satisfy(...)` call (Problem accumulates `satisfy` calls — there is no in-place removal API):
- Are existing constraints too tight (equality where inequality would suffice)?
- Are there redundant constraints that conflict with each other?
- Can a constraint be softened (e.g., `== demand` to `>= demand * 0.9`)?
- Should a non-essential constraint be omitted from the rebuilt Problem entirely?

**Fix priority order:**
1. Drop or relax conflicting/redundant constraints (least disruptive — rebuild Problem omitting the offending `satisfy(...)`)
2. Modify existing constraints (soften bounds, widen ranges) when rebuilding
3. Add slack variables to absorb infeasibility
4. Add new variables (last resort)

**Emphasis:** PREFER omitting or relaxing existing constraints in the rebuilt Problem — this is an INFEASIBLE solution caused by over-constraining.
