<!-- TOC -->
- [Native Marginals (LP/QP Duals)](#native-marginals-lpqp-duals)
  - [Reading marginals off the returned objects](#reading-marginals-off-the-returned-objects)
  - [Shadow price economics](#shadow-price-economics)
  - [Reduced cost & complementary slackness](#reduced-cost--complementary-slackness)
  - [Basis status](#basis-status)
  - [Strong-duality reconstruction](#strong-duality-reconstruction)
  - [Sign convention & scope limits](#sign-convention--scope-limits)
- [Sensitivity Analysis](#sensitivity-analysis)
  - [What-If Framing for Stakeholders](#what-if-framing-for-stakeholders)
  - [Which Parameters to Vary](#which-parameters-to-vary)
  - [Parameter Type Taxonomy](#parameter-type-taxonomy)
  - [Presenting Scenario Results](#presenting-scenario-results)
  - [Identifying Critical Parameters](#identifying-critical-parameters)
  - [Strategic vs. Operational Framing](#strategic-vs-operational-framing)
- [Pareto Frontier / Efficient Frontier Analysis](#pareto-frontier--efficient-frontier-analysis)
  - [Explaining the Frontier to Users](#explaining-the-frontier-to-users)
  - [Quality Gates (before interpretation)](#quality-gates-before-interpretation)
  - [Standardized Analysis Structure](#standardized-analysis-structure)
  - [Presenting as Operating Points](#presenting-as-operating-points)
  - [Export Patterns](#export-patterns)
  - [Key Metrics](#key-metrics)
<!-- /TOC -->

## Native Marginals (LP/QP Duals)

`solve(sensitivity=True)` populates LP/QP **dual** information directly on the objects `solve_for()` and `satisfy()` return. These are *exact* marginals at the optimum — read them like any other attribute (`.name`), single-valued, joined to their entity by the back-pointer key. **LP/QP only**: a MIP returns empty marginals and fires a warning (an integer program has no meaningful duals); interior-point solvers (Ipopt) populate `reduced_cost` / `shadow_price` but **not** `basis_status`. There is **no coefficient or RHS ranging** — a marginal is the rate at the optimum, not the interval over which that rate holds.

### Reading marginals off the returned objects

```python
# A continuous variable per Activity, a resource-capacity constraint family named per Resource:
acts = problem.solve_for(Activity.level, name=Activity.name, lower=0)
cap = problem.satisfy(model.require(usage <= Resource.capacity), name=["cap", Resource.name])
problem.solve("highs", sensitivity=True)

model.select(acts.activity.name, acts.reduced_cost, acts.basis_status).inspect()
model.select(cap.resource.name, cap.resource.capacity, cap.shadow_price).inspect()
```

The **key-join idiom** — `cap.resource` is the constraint's entity back-pointer — pairs each marginal with the entity it grounds, so you never parse the constraint's name string. It depends on each constraint-family instance being named distinctly at formulation time (`name=["cap", Resource.name]`); see `rai-prescriptive-problem-formulation/references/constraint-formulation.md`.

### Shadow price economics

`con.shadow_price` is ∂(objective) / ∂(constraint RHS) — what one more unit of the constraint's right-hand side is worth at the optimum.

- A constraint with **slack** (not binding) has `shadow_price == 0` — *always*. Loosening a constraint that isn't binding changes nothing.
- A **binding** constraint **usually** has a non-zero shadow price, but **not always**: under degeneracy a binding constraint can price at zero. Don't encode "binding ⇒ non-zero shadow price" as a law.

### Reduced cost & complementary slackness

`var.reduced_cost` is the objective marginal on the variable's bound. Complementary slackness links it to whether the variable is in use, but **only some directions are safe to assert**:

- **Always true:** `in use (strictly between its bounds) ⇒ reduced_cost ≈ 0`, and `reduced_cost ≠ 0 ⇒ the variable sits at one of its bounds`. For the common case of **minimizing** with a non-negative variable at a zero lower bound, `reduced_cost > 0 ⇒ unused` (the shorthand the pitfall rows use); when **maximizing** the sign flips — there an unused option at its lower bound prices `reduced_cost < 0`.
- **Not always true:** the converse `unused ⇒ reduced_cost > 0` holds **only under a unique optimum**. Under alternate optima / degeneracy an unused option can have `reduced_cost ≈ 0`.

> **Caveat — the complementary-slackness converse is unsafe.** When turning these into integrity constraints, assert only the two always-true directions above. A model with a unique optimum may let you assert `unused ⇒ reduced_cost > 0`, but treat that as the special case, not the rule — a copied IC will fail on a degenerate model where an unused option is priced at zero.

### Basis status

`var.basis_status` / `con.basis_status` report the MOI basis (`"BASIC"`, `"NONBASIC_AT_LOWER"`, `"NONBASIC_AT_UPPER"`, …) — which variables / constraints define the current vertex. **Absent for interior-point solvers (Ipopt)**, which don't maintain a simplex basis; use `reduced_cost` / `shadow_price` for marginals there, or pick a simplex solver if you specifically need the basis.

### Strong-duality reconstruction

At an LP optimum, the *constraint* contribution to the objective is `Σ shadow_price × RHS` over the binding constraints (variable-bound duals — i.e. reduced costs on bounds — and any objective constant aside). When a model's duality is carried entirely by these constraints, you can reconstruct (and cross-check) the objective relationally by summing the priced RHS through the key:

```python
# Σ shadow_price × RHS over the constraint family, joined by the entity key:
model.select(sum(cap.shadow_price * cap.resource.capacity)).inspect()
```

> **Caveat — reconstruction needs a Float RHS.** This works when the RHS property is `Float`. A `Float` `shadow_price` multiplied by an **Integer** RHS can trip a typer mismatch (`Number(38,0)` vs `Float`). Treat the reconstruction as illustrative for Float-RHS models; for Integer-RHS data, keep integrity constraints additive / threshold-only rather than multiplying price × integer RHS.

### Sign convention & scope limits

- **Sign follows the objective sense** (min vs. max), uniform across `≤` / `≥` / `=` constraints — don't infer the sign from the constraint's direction or from which bound is active.
- **Local & first-order:** marginals describe the rate at the current optimum only. There is no ranging, so they don't tell you how far a change preserves the rate — past a basis change the marginal itself changes.
- **Degeneracy:** at a degenerate optimum duals need not be unique; two valid solves can report different (equally correct) marginals.
- For finite changes, structural shifts, or MIP models, use the scenario / what-if methods below instead — duals can't capture them.

---

## Sensitivity Analysis

For implementation patterns (Scenario Concept for parameter variations, Loop + `where=[]` for entity exclusion), see `rai-prescriptive-problem-formulation/references/scenario-analysis.md`. This reference focuses on **interpretation** of scenario results — comparison tables, critical-parameter identification, and Pareto frontier explanation. For *exact marginals at the optimum* (LP/QP duals), see Native Marginals above.

### What-If Framing for Stakeholders

Sensitivity analysis answers: "What happens if our assumptions change?" Present it as scenario comparison, not mathematical derivatives.

### Which Parameters to Vary

Prioritize parameters that are:
1. **Uncertain**: Demand forecasts, cost estimates, capacity projections.
2. **Controllable**: Budget limits, headcount caps, service level targets.
3. **High-impact**: Parameters where small changes cause large solution changes.

Common parameters to test:

| Category | Parameters | Why |
|----------|-----------|-----|
| Demand | Demand volumes (+/-10%, +/-25%) | Demand forecasts are inherently uncertain |
| Budget | Total budget, per-category limits | Budget is a policy lever stakeholders control |
| Capacity | Facility capacity, workforce availability | Capacity may change with investment decisions |
| Service levels | Minimum fill rate, max delivery time | Trade-off between cost and service quality |
| Costs | Unit costs, transport costs, fixed costs | Cost estimates may change with market conditions |

### Parameter Type Taxonomy

Each scenario parameter has a type that determines its required fields and how it is varied:

**Numeric parameters** — continuous values varied over a range:
- Required fields: `name`, `description`, `default`, `min`, `max`, `step`
- Example: `budget_limit` with min=50000, max=200000, step=25000
- Use for: budget limits, capacity percentages, penalty weights, service level targets

**Entity parameters** — selecting/excluding specific entities:
- Required fields: `name`, `description`, `concept`, `property`, `default`, `allow_none`
- Example: `excluded_supplier` from concept `Supplier`, property `name`, allow_none=true
- Use for: disruption scenarios ("what if Supplier X is unavailable?"), facility selection

**Categorical parameters** — discrete named options:
- Required fields: `name`, `description`, `options` (list of value/label pairs), `default`
- Example: `shipping_mode` with options ["standard", "express", "overnight"]
- Use for: policy choices, mode selection, strategy alternatives

**Selection criteria (in priority order):**
1. Parameters with clear business meaning that stakeholders understand
2. Parameters that would show interesting tradeoffs when varied
3. Parameters referenced (explicitly or implicitly) in constraints or objective
4. Parameters where small changes are likely to cause structural solution changes

### Presenting Scenario Results

Use a comparison table with business-friendly language. Describe what changes in terms stakeholders understand -- facilities, service levels, costs -- not variable values or constraint states.

| Scenario | What changes | Impact on cost | What happens differently |
|----------|-------------|---------------|--------------------------|
| Base case | Current assumptions | $1.2M total cost | 3 distribution centers active |
| High demand | Customer demand rises 20% | $1.5M (+25%) | A 4th distribution center is needed to keep up |
| Tight budget | Available budget reduced 15% | $1.35M | Service level drops from 98% to 92% |
| Lower transport rates | Shipping costs fall 10% | $1.1M (-8%) | Distribution shifts to fewer, larger hubs |

### Identifying Critical Parameters

A parameter is **critical** if small changes cause:
- Different facilities/assets selected (structural change)
- Significant objective change (>5% per 10% parameter change)
- Constraint status flips (binding becomes non-binding or vice versa)

Report critical parameters explicitly: "The solution is most sensitive to [demand at Region X] and [capacity at Site B]. A 10% increase in either changes which facilities are used."

### Strategic vs. Operational Framing

The context determines how to present scenario results:
- **Strategic decisions** (one-time planning): Show Pareto frontiers — the full tradeoff surface between competing objectives. Let stakeholders choose their preferred operating point.
- **Operational decisions** (recurring use): Show weighted objective sensitivity — how the solution changes as weights shift. Stakeholders set weights once, then run daily.

Detect context from problem characteristics: one-time capacity planning, facility location, network design → strategic. Daily scheduling, routing, allocation → operational.

---

## Pareto Frontier / Efficient Frontier Analysis

When results come from an epsilon constraint loop (bi-objective optimization), apply this standardized analysis structure. The Pareto frontier IS a sensitivity analysis — it shows how the primary objective responds to changes in the secondary objective's bound.

### Explaining the Frontier to Users

Frame in business terms: "Each point on the frontier is a valid solution representing a different balance between your two goals — [primary] and [secondary]. No point is strictly better than another. The frontier shows where improving one goal starts costing significantly more in the other."

### Quality Gates (before interpretation)

- All points OPTIMAL? If some INFEASIBLE, note which secondary targets are unachievable.
- Points show variation in the primary? If all same value, objectives aren't in tension.
- At least 3 non-anchor points? Fewer may miss the frontier shape.

### Standardized Analysis Structure

Produce all of these for any Pareto frontier result:

1. **Tradeoff table**: both objectives at each point + marginal rate between consecutive points. The secondary objective must be computed from the Variable.values() results (solver only reports the primary).

2. **Marginal rate + knee detection**: The marginal rate is Δprimary / Δsecondary between consecutive points. The **knee** is where the marginal rate RATIO jumps most: `rates[i+1] / rates[i]`. The knee is NOT where the absolute rate is highest — that's always the last point. The knee is where diminishing returns begin.

3. **Allocation shifts + regime detection**: Compare variable values between consecutive points. Look for structural phase transitions — entities that activate or deactivate, substitution patterns that change. These regime shifts are more valuable than raw numbers. Example: "Going from 70% to 80% coverage activates Warehouse_South and opens 3 new routes."

4. **Frontier visualization**: Table or scatter plot showing the tradeoff shape. Mark the knee point.

5. **Business narrative**: Characterize 2-3 regions of the frontier (e.g., "efficient zone", "premium zone", "saturation zone"). Frame the knee as a recommendation: "[secondary value] at [primary value] offers the best value — each additional unit of [secondary] beyond this costs [X]x more."

### Presenting as Operating Points

Present the frontier as a menu of operating points, not a single answer. The user picks their preferred balance. For each candidate operating point, show:
- Both objective values
- Key decisions at that point (what's active, what's not)
- What changes if they move one point up or down the frontier

### Export Patterns

- **Pareto summary**: one row per point (epsilon, primary_value, secondary_value, status)
- **Per-point variables**: full Variable.values() DataFrame for each point (user can compare allocations)
- Same pattern as scenario result export (one DataFrame per scenario → one DataFrame per Pareto point)
- To populate the chosen operating point back into the ontology, see `rai-prescriptive-problem-formulation` > [multi-objective-formulation.md](../../rai-prescriptive-problem-formulation/references/multi-objective-formulation.md) > Storing Results

### Key Metrics

- **Marginal rate of substitution**: cost of improving secondary by one unit, in primary units
- **Knee point**: where marginal rate ratio jumps most (diminishing returns threshold)
- **Anchor points**: the two extremes (pure primary-optimal and pure secondary-optimal)
- **Steep regions**: small secondary improvements cost a lot in primary
- **Flat regions**: secondary can be improved cheaply
