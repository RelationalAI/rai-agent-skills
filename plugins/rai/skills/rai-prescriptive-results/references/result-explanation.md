# Result Explanation Templates

The full stakeholder presentation structure, decision-variable translation examples, explainability question patterns, and sensitivity framing. SKILL.md > Result Explanation Guide holds the compact ordering; load this when composing a full stakeholder-facing writeup.

## Understanding decision variables

Solution results contain values for "decision concepts" — entities created to represent optimization choices.

- `x_` prefix → decision variables controlled by the solver. Translate `x_` prefixed names to business terms when presenting results — the prefix is an internal convention that confuses business users (e.g., `x_quantity = 150` → "produce 150 units", `x_assigned = 1` → "assigned")
- Extended concepts → cross-product entities linking two base concepts (the decision space). Map back to base entities when presenting (e.g., "SiteProduct.x_quantity" → "production of Product at Site")
- Present decision values with entity context, not as raw numbers. Use business labels in result tables: "Quantity Shipped" not "x_flow", "Assigned" not "x_assigned", "Units Produced" not "x_quantity"

Common translations (code samples, API references, and Python variable names stay technical):
- `x_flow` → "shipment quantity" or "units shipped"
- `x_assigned` → "assigned" or "selected"
- `x_quantity` → "production quantity" or "units allocated"
- `x_open` → "facility is open" or "selected for use"

## Structure for Stakeholders (6-part template)

Present results in this order:

1. **Problem Context** (2-3 sentences): What problem was being solved and the business context.
   - "We optimized the allocation to minimize total cost while meeting all demand constraints."

2. **What Was Decided**: The key allocations, assignments, or quantities. Lead with the actionable output. Include objective value and what it means in business terms.
   - "The model recommends producing 500 units at Site A and 300 at Site B. Total cost: $1.2M."

3. **Why These Decisions (Key Drivers)**: Which constraints and costs drove the solution. Answer: "Why was X selected?", "Why was Y excluded?", "What's preventing Z?" — using actual entity names from the solution.
   - "Site A is used heavily because it has the lowest unit cost and sufficient capacity."
   - "Site C was not selected because its fixed cost exceeds the savings from lower transport distance."

4. **Solution Quality Assessment**: Is the solution useful? Check for non-triviality, actionability, interpretability. Flag any red flags:
   - All-zero or near-zero solution
   - Objective value outside plausible range
   - Concentration on a single entity when distribution is expected
   - Variables clustered at bounds

5. **Business Impact**: Translate the objective value and key metrics into business language. What does this mean for the organization?
   - "Total cost: $1.2M, a 15% reduction from the current allocation."
   - "All customer demand is met. Two facilities operate at >90% capacity."

6. **Recommended Next Steps**: What should the user do with this solution?
   - Validate with domain experts?
   - Run sensitivity analysis on key parameters?
   - Implement directly?
   - Investigate specific entities that behave unexpectedly?

## Answering "Why This Decision?" (Explainability)

Decision makers need to understand not just what the solution recommends, but why. Reason from the formulation — which constraints are tight, which costs/coefficients drove the choice — to answer:

- **"Why was X selected?"** → Identify which constraints and cost/value properties made X optimal. "Entity A gets 60% of allocation because it has the lowest unit cost while meeting the quality threshold."
- **"Why was Y excluded?"** → Identify which constraint or cost makes Y suboptimal. "Entity C isn't used because its fixed cost exceeds the savings from proximity despite available capacity."
- **"What's preventing Z?"** → Identify the binding constraint. "Site B can't produce more because its capacity constraint is binding at 500 units."

Frame every explanation in terms the decision maker already knows — their entities, their resources, their constraints — not variable indices or solver internals. For *why* a constraint binds or an option was excluded, `solve(sensitivity=True)` gives exact marginals on LP/QP models — a constraint's `shadow_price` (what one more unit of its RHS is worth) and a variable's `reduced_cost` (the objective marginal on its bound); see SKILL.md > Sensitivity Analysis for the sign rules and the left-out-option intuition. For MIP models (no duals) or finite/structural changes, reason from binding-constraint identification and scenario deltas.

## Sensitivity Framing

Frame sensitivity results as conditional business statements:
- "If demand increases by 10%, total cost rises by $80K and Site B reaches full capacity."
- "The solution is robust to +/-5% cost variation -- the same facilities are selected."
- "The critical threshold is at 1,200 units of demand: beyond that, a fourth facility is needed."
