# Pattern: dual-guided Pareto frontier sweep — one solve_at(eps) kernel, three drivers
# (uniform grid vs adaptive vs dichotomic), each placing solves more deliberately by
# reading the epsilon-bound's shadow price as the EXACT local frontier slope.
#
# Key ideas:
#   - Bi-objective convex QP: minimize variance (f1, primary) s.t. return >= eps (f2, secondary).
#   - solve("highs", sensitivity=True) returns LP/QP duals. The return-floor constraint's
#     shadow_price is lambda = d(variance)/d(eps) — the frontier slope at that point, with NO
#     finite differencing (envelope theorem). highs (not ipopt) is the dual-bearing solver for LP/QP.
#   - Sampling policy is an axis orthogonal to the scalarization — "how much you use the dual":
#       * BLIND    (uniform grid)    — ignores the dual; the control/baseline.
#       * POINTWISE (adaptive)       — next step Δε = target_Δvariance / lambda, so points land
#                                      evenly in variance (f1) space; denser in eps where lambda is large.
#       * GLOBAL   (dichotomic)      — next eps at the tangent crossover of two endpoints' shadow
#                                      prices; exact (finite) for a bi-objective LP. This is the
#                                      epsilon-constraint, dual-guided ANALOGUE of NISE — classical
#                                      NISE (Aneja–Nair 1979) is weighted-sum (picks the next WEIGHT
#                                      as the chord normal); here we pick the next EPS from the duals.
#                                      Same supported set on a convex bi-objective frontier, different
#                                      mechanism (epsilon-constraint + duals, not weighted sum).
#   - In-place weighted-sum equivalence: at a supported point the ε-optimum of
#     `min f1 s.t. f2 >= eps` equals the weighted-sum optimum of `min f1 - lambda*f2` — weights
#     (1, -lambda) on the mixed-sense (min f1, max f2), equivalently non-negative (1, lambda) on the
#     both-min (f1, -f2). Cross-check: the weights (1, lambda) make this point the weighted-sum
#     optimum over the frontier (a supporting hyperplane — supported / convex only).
#
# Runnable public precedent: the `portfolio_balancing` template (bi-objective Markowitz, dual-guided
# frontier). This example is self-contained and domain-generic (Item / value / interaction QP).

import builtins  # RAI `sum` shadows Python's built-in; use builtins.sum for DataFrame aggregation
import warnings

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# A frontier sweep builds one Problem per point in a Python loop, so two advisories are
# expected and benign here: the per-iteration re-solve notice, and "Rules created in a loop"
# (each solve_at re-declares the budget/floor constraints from the same call site). Suppress both.
warnings.filterwarnings("ignore", message=".*re-solv.*")
warnings.filterwarnings("ignore", message=".*Rules created in a loop.*")

model = Model("dual_guided_pareto_sweep")

# --- Ontology: items with a return coefficient (value), a covariance (interaction), an allocation ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")
Item.x_alloc = model.Property(
    f"{Item} has {Float:x_alloc}"
)  # continuous decision variable
PairedItem = Item.ref()

BUDGET = 1.0  # total allocation (sum of x == BUDGET)

item_data = model.data(
    [
        {"index": 1, "value": 0.08},
        {"index": 2, "value": 0.15},
        {"index": 3, "value": 0.05},
    ]
)
model.define(Item.new(item_data.to_schema()))

# Symmetric, diagonally-dominant (hence PSD ⇒ convex QP that HiGHS accepts) covariance.
interaction_raw = model.data(
    [
        {"i": 1, "j": 1, "w": 0.040},
        {"i": 1, "j": 2, "w": 0.010},
        {"i": 1, "j": 3, "w": 0.005},
        {"i": 2, "j": 1, "w": 0.010},
        {"i": 2, "j": 2, "w": 0.090},
        {"i": 2, "j": 3, "w": 0.020},
        {"i": 3, "j": 1, "w": 0.005},
        {"i": 3, "j": 2, "w": 0.020},
        {"i": 3, "j": 3, "w": 0.040},
    ],
    columns=["i", "j", "w"],
)
model.where(
    Item.index(interaction_raw.i),
    PairedItem.index(interaction_raw.j),
).define(Item.interaction(PairedItem, interaction_raw.w))


def solve_at(eps):
    """One scalarized solve: minimize variance s.t. return >= eps. Returns the point plus the
    EXACT frontier slope (the return-floor's shadow price). The shared kernel every driver calls."""
    problem = Problem(model, Float)
    x = Float.ref()
    # populate=False: solve_at runs once per swept point, so writing the solution back into
    # Item.x_alloc every call would have many Problems populate the same relationship (a
    # functional-dependency violation). Read this solve's values via x_qty.values(0, ...) below.
    x_qty = problem.solve_for(Item.x_alloc, name=Item.index, lower=0, populate=False)

    # Budget: total allocation fixed at BUDGET.
    problem.satisfy(model.where(Item.x_alloc(x)).require(sum(x) == BUDGET))

    # EPSILON CONSTRAINT (return floor). Capture it so its dual is readable. Scalar constraint →
    # shadow_price reads straight off the returned object (no keyed_by needed for a single bound).
    floor = problem.satisfy(
        model.where(Item.x_alloc(x)).require(sum(Item.value * x) >= eps),
        name="return_floor",
    )

    # Primary objective: minimize variance xᵀQx (convex QP).
    w = Float.ref()
    x_paired = Float.ref()
    problem.minimize(
        sum(w * x * x_paired).where(
            Item.interaction(PairedItem, w),
            Item.x_alloc(x),
            PairedItem.x_alloc(x_paired),
        )
    )

    problem.solve("highs", sensitivity=True, time_limit_sec=60)
    si = problem.solve_info()
    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        return {"eps": eps, "status": si.termination_status, "feasible": False}

    # Exact slope λ = ∂variance/∂eps — the return-floor's shadow price (no finite differencing).
    # Sign: min + `>=` ⇒ λ ≥ 0 (raising the return floor can only raise variance).
    slope_df = model.select(floor.shadow_price.alias("lam")).to_df()
    lam = float(slope_df["lam"].iloc[0]) if not slope_df.empty else float("nan")

    # Realized return (f2) and allocation, from the variable values via the back-pointer key.
    val_ref = Float.ref()
    x_df = (
        model.select(
            x_qty.item.index.alias("item"),
            x_qty.item.value.alias("value"),
            val_ref.alias("x"),
        )
        .where(x_qty.values(0, val_ref))
        .to_df()
    )
    realized_return = builtins.sum(x_df["value"] * x_df["x"])

    return {
        "eps": eps,
        "status": si.termination_status,
        "feasible": True,
        "variance": si.objective_value,  # f1
        "return": realized_return,  # f2
        "slope": lam,  # λ = ∂f1/∂eps = exact frontier slope
        "variables": x_df,
    }


# =============================================================================
# ANCHORS: feasible return range = [min-variance return, max return].
# =============================================================================
# Anchor low: a non-binding floor → the unconstrained-min-variance return.
anchor_lo = solve_at(eps=-1e9)
return_min = anchor_lo["return"] if anchor_lo["feasible"] else 0.0

# Anchor high: maximize return alone (a separate single-objective solve).
problem_hi = Problem(model, Float)
x_hi = Float.ref()
problem_hi.solve_for(Item.x_alloc, name=Item.index, lower=0, populate=False)
problem_hi.satisfy(model.where(Item.x_alloc(x_hi)).require(sum(x_hi) == BUDGET))
problem_hi.maximize(sum(Item.value * x_hi).where(Item.x_alloc(x_hi)))
problem_hi.solve("highs", time_limit_sec=60)
return_max = problem_hi.solve_info().objective_value
span = return_max - return_min

# =============================================================================
# DRIVER A — BLIND (uniform grid): ignores the dual. The control.
# =============================================================================
n_interior = 5
uniform_eps = [
    return_min + i * span / (n_interior + 1) for i in range(1, n_interior + 1)
]
uniform_points = [p for e in uniform_eps if (p := solve_at(e))["feasible"]]
print("\n-- uniform grid (blind) --")
for p in uniform_points:
    print(
        f"  eps={p['eps']:.4f}  variance={p['variance']:.5f}  return={p['return']:.4f}  slope λ={p['slope']:.4f}"
    )

# =============================================================================
# DRIVER B — POINTWISE (adaptive): size the next step from the current dual.
# =============================================================================
# Δε = target_Δvariance / λ  (variance = f1, the minimized objective; divide an f1-target by λ to get
# the ε-step). Points then land evenly in variance space — denser in eps where λ is large.
target_dvar = 0.01  # target variance step per point
min_step, max_step = span / 40.0, span / 4.0
adaptive_points = []
eps = return_min + min_step
while eps < return_max:
    p = solve_at(eps)
    if not p["feasible"]:
        break
    adaptive_points.append(p)
    lam = p["slope"] if p["slope"] and p["slope"] > 1e-9 else 1e-9
    step = builtins.min(builtins.max(target_dvar / lam, min_step), max_step)
    eps += step
print("\n-- adaptive (pointwise, dual-sized steps) --")
for p in adaptive_points:
    print(
        f"  eps={p['eps']:.4f}  variance={p['variance']:.5f}  slope λ={p['slope']:.4f}"
    )


# =============================================================================
# DRIVER C — GLOBAL (dichotomic; epsilon-space dual-guided analogue of NISE): next eps at crossover.
# =============================================================================
# Between two found points a, b the two shadow-price tangents cross at the eps that maximizes the
# chord-vs-tangent gap. Exact (finite) for a bi-objective LP; for a smooth convex QP it places
# markedly fewer, better-positioned solves than a blind grid at equal tolerance.
def dichotomic(a, b, depth=0, tol=1e-4, max_depth=6):
    points = []
    if depth >= max_depth or (b["return"] - a["return"]) < tol:
        return points
    la, lb = a["slope"], b["slope"]
    if abs(lb - la) < 1e-9:  # equal slopes ⇒ the segment is already exact
        return points
    eps_star = (a["variance"] - la * a["return"] - b["variance"] + lb * b["return"]) / (
        lb - la
    )
    if not (a["return"] < eps_star < b["return"]):
        return points
    mid = solve_at(eps_star)
    if not mid["feasible"]:
        return points
    points.append(mid)
    points += dichotomic(a, mid, depth + 1, tol, max_depth)
    points += dichotomic(mid, b, depth + 1, tol, max_depth)
    return points


if anchor_lo["feasible"]:
    hi_point = solve_at(return_max)
    if hi_point["feasible"]:
        dich_points = [anchor_lo, hi_point] + dichotomic(anchor_lo, hi_point)
        print(
            f"\n-- dichotomic (global): {len(dich_points)} points to resolve the frontier --"
        )

# =============================================================================
# WEIGHTED-SUM EQUIVALENCE (in place — teaches "two interchangeable views" without a 2nd generator).
# =============================================================================
# At a supported point with dual λ, the weights (1, λ) on the both-min vector (variance, -return)
# define the SUPPORTING HYPERPLANE: the weighted-sum objective g(q) = variance(q) − λ·return(q) is
# minimized at THIS point over the whole convex frontier. That is the equivalence
# `min variance s.t. return ≥ ε`  ==  `min (variance − λ·return)`. We check it against the already-
# solved grid points — no second solve, and not a tautology: g uses each point's REALIZED variance
# and return, so a wrong λ (or a wrong sign) would let some other point score lower and trip it.
if len(uniform_points) >= 2:
    pt = uniform_points[len(uniform_points) // 2]  # a supported interior point
    lam = pt["slope"]  # weights (1, λ) on (variance, -return); λ ≥ 0 here (min + ≥)

    def weighted_sum(q):
        return q["variance"] - lam * q["return"]

    g_pt = weighted_sum(pt)
    # max over the grid of how much any point UNDERCUTS pt; ≤ 0 (up to solver noise) iff pt is the
    # weighted-sum optimum. A real equivalence break (wrong dual/sign) lands well above the tolerance.
    worst_undercut = max(g_pt - weighted_sum(q) for q in uniform_points)
    assert worst_undercut <= 1e-6, (
        "weights (1, λ) must make this ε-point the weighted-sum optimum over the frontier "
        f"(another point undercuts it by {worst_undercut:.2e}) — the ε ↔ weighted-sum equivalence "
        "fails; check the dual's sign and value"
    )
    print(
        f"\nweighted-sum view: weights (1, {lam:.4f}) on (variance, -return) make this ε-point the "
        f"weighted-sum optimum over all sampled points ✓ (supporting hyperplane, supported point)"
    )
