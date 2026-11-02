# Fix Generation Guidelines

## Table of Contents
- [Join Path Fix Rules](#join-path-fix-rules)
- [Fix Strategy: Trivial Solution](#fix-strategy-trivial-solution)
- [Fix Strategy: Infeasible Solution](#fix-strategy-infeasible-solution)

---

## Join Path Fix Rules

When fixing trivial solutions, the primary approach is to fix broken join paths in constraints — NOT to add aggregate workarounds.

**Diagnosis steps:**
1. Identify the join condition that should link decision variables to requirements (location, SKU, ID, etc.)
2. Check the model's relationships for valid paths from BOTH sides to that shared property
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

---

## Fix Strategy: Trivial Solution

Use this strategy when the solution is OPTIMAL but trivial (all zeros, zero objective, vacuous satisfaction).
The root cause is almost always **missing forcing constraints** — the solver found a "do nothing" shortcut.

Localize first: [diagnostic-workflow.md](diagnostic-workflow.md) > Trivial-OPTIMAL: localizing the missing forcing constraint. Forcing patterns: [constraint-formulation.md](constraint-formulation.md) > Forcing constraints.

**Fix priority order:**
1. Add FORCING constraints that require meaningful activity (demand satisfaction, coverage, minimum utilization)
2. Modify existing constraints to be tighter (lower bounds, equality instead of inequality)
3. Check if existing forcing constraints reference the wrong properties or have wrong direction (>= vs <=)
4. Add new variables only if the current variable set cannot express the forcing requirement

---

## Fix Strategy: Infeasible Solution

Use this strategy when the solver returned INFEASIBLE or a previous fix caused infeasibility. The cause is over-constraining: conflicting or too-tight constraints.

**Localize before changing anything:** [diagnostic-workflow.md](diagnostic-workflow.md) > INFEASIBLE: localizing the conflict. Reading conflict membership: `rai-prescriptive-results/references/conflict-analysis.md`.

**Fix priority order** (`Problem` accumulates `satisfy` calls with no removal API, so dropping or replacing one means rebuilding the Problem without it):
1. Drop or relax a flagged constraint: an equality where an inequality suffices, a redundant pair that conflicts, a non-essential constraint
2. Soften bounds or widen ranges (e.g., `== demand` to `>= demand * 0.9`), or widen a flagged variable bound/type
3. Add slack variables to absorb infeasibility
4. Add new variables (last resort)

Re-solve after each change: the IIS is one conflict, and others may remain.
