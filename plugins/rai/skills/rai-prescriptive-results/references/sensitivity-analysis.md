## Native Marginals (LP/QP Duals)

`solve(sensitivity=True)` populates LP/QP **dual** information directly on the objects `solve_for()` and `satisfy()` return. These are *exact* marginals at the optimum — read them like any other attribute (`.name`), single-valued, joined to their entity by the back-pointer key. **LP/QP only**: a MIP returns empty marginals and fires a warning (an integer program has no meaningful duals); interior-point solvers (Ipopt) populate `reduced_cost` / `shadow_price` but **not** `basis_status`. There is **no coefficient or RHS ranging** — a marginal is the rate at the optimum, not the interval over which that rate holds.

### Reading marginals off the returned objects

```python
# A continuous variable per Activity, a resource-capacity constraint family keyed per Resource:
acts = problem.solve_for(Activity.level, name=Activity.name, lower=0)
cap = problem.satisfy(model.require(usage <= Resource.capacity), keyed_by={"resource": Resource})
problem.maximize(sum(Activity.profit * Activity.level))  # duals need an objective
problem.solve("highs", sensitivity=True)

model.select(acts.activity.name, acts.reduced_cost, acts.basis_status).inspect()
model.select(cap.resource.name, cap.resource.capacity, cap.shadow_price).inspect()
```

The **key-join idiom** — `cap.resource` is the constraint's entity back-pointer — pairs each marginal with the entity it grounds, so you never parse the constraint's name string. It depends on the family declaring its grounding key at formulation time (`keyed_by={"resource": Resource}`); see `rai-prescriptive-problem/references/constraint-formulation.md`.

To add duals after a plain solve, re-solve the same `Problem` with `sensitivity=True` (relationalai>=1.26). A later re-solve without the flag empties the marginals (null) unless it raises.

### Shadow price economics

`con.shadow_price` is ∂(objective) / ∂(constraint RHS) — what one more unit of the constraint's right-hand side is worth at the optimum.

- A constraint with **slack** (not binding) has `shadow_price == 0` — *always*. Loosening a constraint that isn't binding changes nothing.
- A **binding** constraint **usually** has a non-zero shadow price, but **not always**: under degeneracy a binding constraint can price at zero. Don't encode "binding ⇒ non-zero shadow price" as a law.

### Reduced cost & complementary slackness

`var.reduced_cost` is the objective marginal on the variable's bound. Complementary slackness links it to whether the variable is in use, but **only some directions are safe to assert**:

- **Always true:** `in use (strictly between its bounds) ⇒ reduced_cost ≈ 0`, and `reduced_cost ≠ 0 ⇒ the variable sits at one of its bounds`.
- **Scoped shorthand — only under minimize with the variable at a zero lower bound:** `reduced_cost > 0 ⇒ unused` (the shorthand the pitfall rows use). Under **maximize** the sign flips — an unused option at its lower bound prices `reduced_cost < 0`. Don't generalize the shorthand across objective senses or to upper-bound cases.
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

- **Sign depends on the objective sense *and* the constraint direction** — `shadow_price = ∂obj/∂RHS`, so under **minimize** a binding `≤` prices `≤ 0` (loosening a binding upper limit can only lower cost) and a binding `≥` prices `≥ 0` (raising a lower requirement can only raise cost); under **maximize** both flip. An `=` constraint's dual is **unrestricted in sign** — an equality always binds and can push the optimum from either side, so read its dual straight off as `∂obj/∂RHS` rather than assuming a sign. **`reduced_cost` follows its own rule:** its sign depends on the objective sense **and which bound is active** — under minimize a variable nonbasic at its lower bound prices `≥ 0` and at its upper bound `≤ 0`; under maximize both flip. Read each marginal's sign from the objective sense together with its own geometry (constraint direction for `shadow_price`, active bound for `reduced_cost`) — never the objective sense alone.
- **Local & first-order:** marginals describe the rate at the current optimum only. There is no ranging, so they don't tell you how far a change preserves the rate — past a basis change the marginal itself changes.
- **Degeneracy:** at a degenerate optimum duals need not be unique; two valid solves can report different (equally correct) marginals.
- For finite changes, structural shifts, or MIP models, use the scenario / what-if methods below instead — duals can't capture them.

---

## Sensitivity Analysis

For implementation patterns (Scenario Concept for parameter variations, Loop + `where=[]` for entity exclusion), see `rai-prescriptive-problem/references/scenario-analysis.md`. Which parameters to vary, what makes one critical, and strategic vs operational framing are in SKILL.md > Sensitivity Analysis; this section covers presenting the results.

Present scenario results as a comparison table in business terms (what changes, its cost impact, what happens differently: "a 4th distribution center is needed"), not variable values or constraint states.

---

## Pareto Frontier / Efficient Frontier Analysis

When results come from an epsilon constraint loop (bi-objective optimization), apply this standardized analysis structure. The Pareto frontier IS a sensitivity analysis — it shows how the primary objective responds to changes in the secondary objective's bound.

### The Scalarization Dual is the Frontier Geometry

When the points come from a **dual-guided** epsilon sweep (`solve(sensitivity=True)` on an LP/QP),
the ε-bound's `shadow_price` **is** the tradeoff rate, exactly:

- **Exact slope.** `λ = shadow_price = ∂(primary)/∂ε` is the local frontier slope at that point
  (envelope theorem). The finite-difference rate `Δprimary/Δsecondary` between consecutive points
  (below) is a secant approximation of it. Read the sign off the objective sense × constraint
  direction (§ Sign convention & scope limits) — never assume `λ ≥ 0`.
- **Knee from the exact dual sequence.** Read the knee off the monotone `λ` sequence (largest jump
  in `λ`) rather than from finite-difference noise.
- **MIP fallback.** Integer models return empty duals; use the finite differencing below.

The weighted-sum reading of the same geometry, dual-driven sampling, and fix-and-relax duals for MIP
are in `rai-prescriptive-problem` > [multi-objective-formulation.md](../../rai-prescriptive-problem/references/multi-objective-formulation.md).
The exact-rate read is shown side by side with the secant estimate in `pareto_frontier_analysis.py`;
to validate a frontier relationally (non-dominance, convex/monotone-dual, slope-consistency integrity
constraints) see `frontier_relational_validation.py`.

### Quality Gates (before interpretation)

- All points OPTIMAL? If some INFEASIBLE, note which secondary targets are unachievable.
- Points show variation in the primary? If all same value, objectives aren't in tension.
- At least 3 non-anchor points? Fewer may miss the frontier shape.

### Standardized Analysis Structure

Produce all of these for any Pareto frontier result:

1. **Tradeoff table**: both objectives at each point + marginal rate between consecutive points. The secondary objective must be computed from the Variable.values() results (solver only reports the primary).

2. **Marginal rate + knee detection**: The marginal rate is Δprimary / Δsecondary between consecutive points (a secant estimate). **If the sweep was dual-guided** (`sensitivity=True` on an LP/QP), use the ε-bound's `shadow_price` as the *exact* rate at each point instead — see "The Scalarization Dual is the Frontier Geometry" above. The **knee** is where the marginal rate RATIO jumps most: `rates[i+1] / rates[i]`. The knee is NOT where the absolute rate is highest — that's always the last point. The knee is where diminishing returns begin.

3. **Allocation shifts + regime detection**: Compare variable values between consecutive points. Look for structural phase transitions — entities that activate or deactivate, substitution patterns that change. These regime shifts are more valuable than raw numbers. Example: "Going from 70% to 80% coverage activates Warehouse_South and opens 3 new routes."

4. **Frontier visualization**: Table or scatter plot showing the tradeoff shape. Mark the knee point.

5. **Business narrative**: Present the frontier as a menu of operating points, not one answer: for each candidate, both objective values and the key decisions. Characterize 2-3 regions (e.g., "efficient zone", "premium zone", "saturation zone") and frame the knee as a recommendation: "[secondary value] at [primary value] offers the best value — each additional unit of [secondary] beyond this costs [X]x more."

### Export Patterns

Export one summary row per point (epsilon, primary, secondary, status) plus each point's `Variable.values()` DataFrame, as for scenario results. To populate the chosen operating point back into the ontology, see `rai-prescriptive-problem` > [multi-objective-formulation.md](../../rai-prescriptive-problem/references/multi-objective-formulation.md) > Storing Results
