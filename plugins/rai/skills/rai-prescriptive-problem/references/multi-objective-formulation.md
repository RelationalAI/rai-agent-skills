# Multi-Objective via Dual-Guided Scalarization

<!-- TOC -->
- [The Unifying Principle](#the-unifying-principle)
- [Approach Selection](#approach-selection)
- [Recognizing Competing Objectives (Tension Heuristics)](#recognizing-competing-objectives-tension-heuristics)
- [Scalarization Menu](#scalarization-menu)
  - [Epsilon Constraint (primary worked path)](#epsilon-constraint-primary-worked-path)
  - [Weighted Sum + Dichotomy (skeleton)](#weighted-sum--dichotomy-skeleton)
- [Two Entry Points (Before/After Code)](#two-entry-points-beforeafter-code)
  - [Entry 1: Constraint to Epsilon Sweep](#entry-1-constraint-to-epsilon-sweep)
  - [Entry 2: Bundled Penalty to Unbundle](#entry-2-bundled-penalty-to-unbundle)
- [Epsilon Constraint Method](#epsilon-constraint-method)
  - [Anchor Solves](#anchor-solves)
  - [Loop Pattern](#loop-pattern)
  - [Direction Handling](#direction-handling)
  - [Sampling Policies (blind / pointwise / global)](#sampling-policies-blind--pointwise--global)
- [Applicability Guard](#applicability-guard)
- [Evaluating the Secondary Objective](#evaluating-the-secondary-objective)
- [Combining with Scenario Concept](#combining-with-scenario-concept)
- [Storing Results](#storing-results)
- [Pitfalls](#pitfalls)
- [References](#references)
<!-- /TOC -->

How to formulate problems with two (or more) competing objectives. A **scalarization** turns the
vector objective into one scalar problem you solve normally; sweeping the scalarization traces the
**Pareto frontier** — the set of solutions where no objective improves without another worsening.

## The Unifying Principle

At a scalarized optimum, the solver's **sensitivity output is the local geometry of the Pareto
frontier** — the supporting hyperplane, i.e. the local tradeoff rates among the objectives. There
are two interchangeable *views* of that same hyperplane:

| View | Scalarization | Where the hyperplane comes from |
|---|---|---|
| **Epsilon-constraint** | `min f₁ s.t. f₂ ≥ ε` | the ε-bound's **solver `shadow_price`** `λ = ∂f₁/∂ε` — the exact local frontier slope (envelope theorem), one rate per solve, no finite differencing |
| **Weighted-sum** | `min w·f` | the **weight vector `w` you set** — it *is* the supporting-hyperplane normal; the weight ratio is the local tradeoff rate |

> **Terminology (kept distinct throughout):** *dual* / *shadow price* = the value the **solver
> returns** for a constraint; *weight* = the hyperplane normal **you choose** for a weighted sum.
> You *read* the first and *set* the second. Only the ε-constraint view consumes the new
> `sensitivity=True` dual; the weighted-sum view needs only objective *values*.

**The two views coincide at supported points.** The equivalent scalarization of
`min f₁ s.t. f₂ ≥ ε` is `min f₁ − λ·f₂` — weights `(1, −λ)` on the **mixed-sense** vector
`(min f₁, max f₂)`, or equivalently the standard **non-negative** weights `(1, λ)` on the
**both-min** vector `(f₁, −f₂)` (never put a negative weight on a both-min objective). The reproducing
weights are `(1, λ)` *by construction*, so the non-trivial fact is geometric: those weights are the
**supporting hyperplane** at the point — equivalently, the ε-point is the optimum of `min(f₁ − λ·f₂)`
over the frontier. That supporting-hyperplane property is a **supported-point / convex-frontier**
property — it can fail at unsupported points on integer or non-convex frontiers.

**Sign is formulation-specific.** `λ = shadow_price = ∂f₁/∂ε`, so its sign is set by objective
sense **and** constraint direction (`min`+`≥` and `max`+`≤` give `λ ≥ 0`; `min`+`≤` and `max`+`≥`
give `λ ≤ 0`; an `=` bound is sign-unrestricted). Never state `λ = ∂f₁/∂ε` sense-free — read the
sign off the formulation. Full sign rules: `rai-prescriptive-results` >
[sensitivity-analysis.md](../../rai-prescriptive-results/references/sensitivity-analysis.md)
§ Sign convention & scope limits.

**Why it's a capability, not a trick:** once you can read that hyperplane, you can (a) place the
next scalarization where it helps most and (b) *bound* the unresolved part of the frontier —
converging in far fewer solves than blind sampling. Each prescriptive solve carries fixed
orchestration overhead, so "fewer, better-placed solves" is the whole game for iterative
multi-objective workflows.

## Approach Selection

Match the problem structure to the right method:

| Situation | Method | Why |
|-----------|--------|-----|
| Two goals in tension, user wants the tradeoff curve | Epsilon constraint loop (dual-guided) | Produces the Pareto frontier; the ε-bound's shadow price gives the exact slope at each point |
| Secondary objective has a known acceptable bound | Primary + threshold (existing) | No need to explore — bound is fixed |
| User provides explicit weights for combining objectives | Weighted sum (existing) | Single-objective with weighted combination; weights = the hyperplane you've chosen |
| More than two objectives | Weighted sum / sandwiching (supported set) | A uniform ε-grid blows up combinatorially past 2 objectives; see [Applicability Guard](#applicability-guard) |
| Only the local tradeoff rate at one operating point | Single solve with `sensitivity=True` | Read the threshold constraint's shadow price; no sweep needed |

## Recognizing Competing Objectives (Tension Heuristics)

**Test**: if improving objective A naturally worsens B under the same constraints, they are in tension.
If both can improve simultaneously, they are not competing -- combine into a single objective.

## Scalarization Menu

### Epsilon Constraint (primary worked path)

`min f₁ s.t. f₂ ≥ ε`. Sweep ε across the feasible range; each solve is a standard single-objective
problem. With `sensitivity=True`, the ε-bound's `shadow_price` is the exact frontier slope at that
point — the basis for the adaptive and dichotomic sampling below. Full mechanics in [Epsilon
Constraint Method](#epsilon-constraint-method); worked code in
[dual_guided_pareto_sweep.py](../examples/dual_guided_pareto_sweep.py).

### Weighted Sum + Dichotomy (skeleton)

`min(w·f)` — a single weighted objective. The weight vector `w` **is** the supporting-hyperplane
normal; the ratio of weights is the local tradeoff rate you are pricing in. No dual to read — the
hyperplane is the input.

```python
# Weighted-sum scalarization: one solve per weight (w1, w2 >= 0 on a both-min vector).
problem.minimize(w1 * f1_expr + w2 * f2_expr)   # f2_expr already in min-sense (negate a max objective)
```

**Dichotomy / NISE:** from two adjacent supported points `a`, `b` in `(f1, f2)` space, the next
weight is `w = (f2_a − f2_b, f1_b − f1_a)`; solve `min(w·f)`; a point off the chord is a new
supported vertex, otherwise the segment is exact.

Weighted sum reaches only **supported** (convex-hull) points; on integer or non-convex frontiers it
skips unsupported nondominated points, so for the full efficient set use ε-constraint or augmented
Tchebychev.

## Two Entry Points (Before/After Code)

### Entry 1: Constraint to Epsilon Sweep

When the secondary objective is currently modeled as a constraint with a fixed bound.

```python
# BEFORE (single-objective): return is a fixed constraint
problem.satisfy(model.require(sum(Stock.returns * x_qty).per(Scenario) >= min_return))
problem.minimize(risk_expr)

# AFTER (bi-objective): return target becomes the loop parameter
for rate in epsilon_rates:
    problem = Problem(model, Float)
    problem.solve_for(..., populate=False)
    problem.satisfy(model.require(sum(Stock.returns * x_qty).per(Scenario) >= rate * Scenario.budget))
    problem.minimize(risk_expr)
    problem.solve(...)
```

### Entry 2: Bundled Penalty to Unbundle

When two concerns are combined via penalty weight in a single objective.

```python
# BEFORE (single-objective): cost + penalty bundled
PENALTY = 10000
problem.minimize((sum(Route.cost * Route.x_flow) | 0.0) + PENALTY * (sum(Demand.x_unmet) | 0.0))

# AFTER (bi-objective): split into primary objective + epsilon constraint
for eps in epsilon_values:
    problem = Problem(model, Float)
    problem.solve_for(..., populate=False)
    problem.satisfy(model.require(sum(Demand.x_unmet) <= eps))  # secondary as constraint
    problem.minimize(sum(Route.cost * Route.x_flow))              # primary only
    problem.solve(...)
```

## Epsilon Constraint Method

### Anchor Solves

Two independent single-objective solves to find the feasible range of the secondary objective:

1. Optimize primary only -- get secondary value at that solution (one bound of the range)
2. Optimize secondary only -- get the other extreme

Without anchors, epsilon values may be non-binding (wasted solves) or infeasible.

### Loop Pattern

```python
pareto = []
consecutive_infeasible = 0
for eps in epsilon_values:
    problem = Problem(model, Float)
    var = problem.solve_for(..., populate=False)  # capture ProblemVariable
    problem.satisfy(original_constraints)
    # Capture the epsilon constraint so its dual is readable (keyed_by for families):
    floor = problem.satisfy(model.require(secondary >= eps), keyed_by={...})  # epsilon constraint
    problem.minimize(primary_objective)
    problem.solve(solver, sensitivity=True, time_limit_sec=60)   # highs for LP/QP duals

    si = problem.solve_info()
    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        consecutive_infeasible += 1
        if consecutive_infeasible >= 2:
            break  # two consecutive infeasible — past feasible range
        continue  # skip this point but try the next (non-convex gaps)
    consecutive_infeasible = 0

    # Exact frontier slope at this point — the ε-bound's shadow price (no finite differencing).
    # Take the SCALAR off the constraint object (downstream analysis divides consecutive slopes,
    # so a DataFrame would break it); for keyed families read one value per key. See
    # dual_guided_pareto_sweep.py.
    slope_df = model.select(floor.shadow_price.alias("lam")).to_df()
    # None (not NaN) when the solve returns no dual (MIP / unsupported): the analysis treats a
    # present non-None slope as exact-dual mode, so None makes it fall back to the secant.
    slope = float(slope_df["lam"].iloc[0]) if not slope_df.empty else None  # λ = ∂primary/∂ε

    # Extract solution via Variable.values() structured query
    # Back-pointer name = lowercased concept from the format string (see rai-prescriptive-results SKILL.md)
    value_ref = Float.ref()
    variables_df = model.select(
        var.stock.name.alias("entity"),  # back-pointer to Stock concept
        value_ref.alias("value"),
    ).where(var.values(0, value_ref)).to_df()

    pareto.append({"eps": eps, "primary": si.objective_value, "slope": slope, "variables": variables_df})
```

Same infrastructure as the Loop + `populate=False` pattern from [scenario-analysis.md](scenario-analysis.md) Pattern 2.
`sensitivity=True` needs an objective and an LP/QP-capable solver (`highs`); a MIP returns empty
duals (see [Applicability Guard](#applicability-guard)). For reading the slope off the constraint
and the `keyed_by` join, see `rai-prescriptive-results` >
[sensitivity-analysis.md](../../rai-prescriptive-results/references/sensitivity-analysis.md).

### Direction Handling

| Primary direction | Secondary direction | Epsilon constraint |
|---|---|---|
| minimize | maximize | secondary >= eps |
| minimize | minimize | secondary <= eps |
| maximize | maximize | secondary >= eps |
| maximize | minimize | secondary <= eps |

The shadow-price **sign** follows from the objective sense × the constraint direction in this table;
never assume `λ ≥ 0` (rules in [The Unifying Principle](#the-unifying-principle)).

### Sampling Policies (blind / pointwise / global)

How much you *use* the dual is an axis orthogonal to the scalarization — the "grid → adaptive →
dichotomic" progression. Each step places solves more deliberately than the last:

1. **Blind** (uniform ε-grid / fixed weights) — ignores the dual. The control / baseline.
   ```python
   n_interior = 5
   epsilon_values = [
       secondary_min + i * (secondary_max - secondary_min) / (n_interior + 1)
       for i in range(1, n_interior + 1)
   ]
   ```
2. **Pointwise** (adaptive) — size the next step from the current dual:
   `Δε = target_Δf₁ / λ`, where `f₁` is the *minimized* objective and `λ = shadow_price = ∂f₁/∂ε`
   (divide an `f₁`-target by `λ` to get the ε-step). Samples then land evenly in **f₁** space —
   denser in ε wherever the frontier bends (`λ` is large). Clamp to `[min_step, max_step]`.
3. **Global** (dichotomic / sandwiching) — keep an **inner** approximation (chords through found
   points) and an **outer** one (supporting hyperplanes — the ε-bound shadow prices, or equivalently
   the weights you set); sample where the inner–outer gap is largest; stop when the gap is within
   tolerance. **Exact (finite)** for a bi-objective LP — one solve per supported vertex. For a smooth
   convex frontier it places markedly fewer, better-positioned solves than a blind grid at equal
   tolerance.

All three drive the **same** `solve_at(eps)` kernel; only the choice of the next ε differs. Worked
side-by-side in [dual_guided_pareto_sweep.py](../examples/dual_guided_pareto_sweep.py).

## Applicability Guard

| Model class | Duals? | What to do |
|---|---|---|
| **Convex** LP/QP (PSD Hessian) | yes | Full dual-guided class — read `shadow_price` off the ε-bound (`highs`, `sensitivity=True`). |
| Non-convex QP under a local solver | local only | KKT multipliers are *locally* valid; don't assert global sensitivity. |
| MIP (integer) | empty (warning) | No duals. Fall back to objective-space decomposition (Kirlik-Sayin-style) or **fix-and-relax**: fix integers at the MIP optimum, re-solve the continuous relaxation to recover a *local* dual (valid while the integer pattern stays optimal). |
| >2 objectives | n/a | Weighted-sum / sandwiching for the **supported set on convex problems**; for the *complete* efficient set (unsupported points, non-convex / discrete) use augmented ε-constraint / Tchebychev or objective-space bound-set methods. A uniform ε-grid blows up combinatorially. |

## Evaluating the Secondary Objective

The solver only reports the primary (optimized) objective value. To get both objectives at each
Pareto point, evaluate the secondary expression using the `Variable.values()` results. Since
`solve_for()` returns a `ProblemVariable` with back-pointers to entity properties, you can
include the secondary coefficient directly in the structured query:

```python
import builtins  # RAI `sum` shadows Python's built-in

# Extract variable values with entity coefficients via back-pointers
value_ref = Float.ref()
point_df = model.select(
    var.stock.index.alias("stock"),
    var.stock.returns.alias("returns"),   # secondary coefficient via back-pointer
    var.scenario.name.alias("scenario"),
    value_ref.alias("quantity"),
).where(var.values(0, value_ref)).to_df()

# Compute secondary objective in Python
secondary_value = builtins.sum(point_df["returns"] * point_df["quantity"])
```

## Combining with Scenario Concept

If the user also has parameter variations (different budgets, demand levels), Scenario Concept
can be used INSIDE the epsilon loop:

```python
for eps in epsilon_values:
    problem = Problem(model, Float)
    # Scenario Concept handles parameter variations -- one solve, all scenarios
    problem.solve_for(Entity.x_var(Scenario, x), ..., populate=False)
    problem.satisfy(model.where(Entity.x_var(Scenario, x)).require(sum(Entity.coef * x).per(Scenario) >= eps))
    problem.minimize(primary_objective)  # aggregated across scenarios
    problem.solve(...)
    # all scenarios solved at this epsilon level
```

N epsilon solves (not N x M). This is optional -- multi-objective does not require scenarios. With a
per-scenario ε-bound, declare `keyed_by={"scenario": Scenario}` to read one shadow price per scenario.

## Storing Results

**Phase 1 — Explore the frontier** with `populate=False`, as in the [Loop Pattern](#loop-pattern):
append each point's `eps`, primary (`si.objective_value`), secondary (computed as in [Evaluating the
Secondary Objective](#evaluating-the-secondary-objective)) and variables frame to `pareto_points`.

**Phase 2 — Populate the chosen operating point** back into the ontology with `populate=True`:

```python
# User selects an operating point (e.g., the knee)
chosen_eps = pareto_points[knee_idx]["eps"]

# Re-solve with populate=True — results written to model properties
problem_final = Problem(model, Float)
problem_final.solve_for(Entity.x_var, populate=True)  # writes back to ontology
problem_final.satisfy(original_constraints)
problem_final.satisfy(model.require(secondary >= chosen_eps))
problem_final.minimize(primary)
problem_final.solve(solver, time_limit_sec=60)

# Results now queryable via model.select(), composable with other model queries
model.select(Entity.id, Entity.x_var).where(Entity.x_var > 0.001).inspect()
```

## Pitfalls

| Pitfall | Cause | Fix |
|---------|-------|-----|
| Non-binding epsilon (wasted solves) | Epsilon range starts below anchor 1's secondary value | Always derive range from anchor solutions |
| All points same primary value | Objectives not in tension | Verify tension heuristic; may just need single objective |
| Infeasible at first epsilon point | Range too aggressive | Widen range or add slack |
| Empty `shadow_price` on the ε-bound | MIP (no duals), or `sensitivity=True` / an LP/QP solver not requested | Use `highs` + `sensitivity=True` on a convex LP/QP; for MIP, fix-and-relax or objective-space decomposition ([Applicability Guard](#applicability-guard)) |
| Assuming `λ ≥ 0` | Sign depends on objective sense × constraint direction | Read the sign off the formulation; cross-ref the sign rules in `rai-prescriptive-results/references/sensitivity-analysis.md` |
| Negative weight in a both-min weighted sum | Confusing the mixed-sense `(1, −λ)` with the both-min form | Use non-negative `(1, λ)` on `(f₁, −f₂)`; `(1, −λ)` is the mixed-sense `(min f₁, max f₂)` reading |
| Weighted sum misses Pareto points | Weighted sum reaches only supported (convex-hull) points | For the full efficient set use ε-constraint or augmented Tchebychev |
| `builtins.sum` vs RAI `sum` | `from relationalai.semantics import sum` shadows built-in | Use `builtins.sum` for Python-side aggregation |
| Scale mismatch between objectives | Very different magnitudes | Normalize epsilon range; consider rates (per unit) rather than absolutes |

## References

- Dual-guided worked example: [dual_guided_pareto_sweep.py](../examples/dual_guided_pareto_sweep.py) — shared `solve_at(eps)` kernel, uniform grid vs adaptive vs dichotomic, in-place weighted-sum equivalence check (supporting hyperplane), QP
- Baseline epsilon example: [epsilon_constraint_pareto.py](../examples/epsilon_constraint_pareto.py) -- epsilon loop + Scenario Concept, QP (uniform grid)
- Reading duals off the returned objects (key-join idiom, sign rules): `rai-prescriptive-results` > [sensitivity-analysis.md](../../rai-prescriptive-results/references/sensitivity-analysis.md)
- Results analysis: `rai-prescriptive-results` > [sensitivity-analysis.md](../../rai-prescriptive-results/references/sensitivity-analysis.md) > Pareto Frontier / Efficient Frontier Analysis
- Runnable public precedent: the `portfolio_balancing` template (bi-objective Markowitz, dual-guided frontier)
