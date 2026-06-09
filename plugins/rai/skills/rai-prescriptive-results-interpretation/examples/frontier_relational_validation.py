# Pattern: validate a Pareto frontier RELATIONALLY — materialize the swept points into a
# FrontierPoint concept and assert non-dominance, convexity (monotone dual), and slope-consistency
# as integrity constraints. "The marginals drove the search; the model checks the result."
#
# Key ideas:
#   - FrontierPoint(idx) carries f1 (primary, minimized), f2 (secondary, maximized), and
#     lam (the eps-bound's shadow_price = the EXACT local slope d(f1)/d(f2) >= 0 for min+>=).
#   - Adjacency is a consecutive-index pair (Q.idx == P.idx + 1); the ICs relate neighbors.
#   - Slope-consistency is the secant bracketed by the two duals, in PRODUCT form (no division):
#       lam_i * (f2_{i+1} - f2_i) <= f1_{i+1} - f1_i <= lam_{i+1} * (f2_{i+1} - f2_i).
#   - Every IC is asserted NON-STRICT / margined. Under degeneracy duals are non-unique and a binding
#     constraint can price at zero, so a STRICT bracket would reject a VALID frontier. Margin, don't
#     strict-compare.
#   - The points come from a dual-guided epsilon sweep — see
#     rai-prescriptive-problem-formulation/examples/dual_guided_pareto_sweep.py.
#   - Integrity-constraint mechanics (model.where(scope).require(...), two refs, keyed_by): see
#     rai-prescriptive-problem-formulation/references/constraint-formulation.md.

from relationalai.semantics import Float, Integer, Model

model = Model("frontier_relational_validation")

# --- FrontierPoint: one row per swept Pareto point ---
FrontierPoint = model.Concept("FrontierPoint", identify_by={"idx": Integer})
FrontierPoint.f1 = model.Property(
    f"{FrontierPoint} has {Float:f1}"
)  # primary (minimized)
FrontierPoint.f2 = model.Property(
    f"{FrontierPoint} has {Float:f2}"
)  # secondary (maximized)
FrontierPoint.lam = model.Property(
    f"{FrontierPoint} has {Float:lam}"
)  # shadow_price = exact slope

# Materialize the swept points (a valid convex frontier: f1 ↑, f2 ↑, lambda ↑, secants bracketed).
frontier_data = model.data(
    [
        {"idx": 0, "f1": 0.0100, "f2": 0.060, "lam": 0.05},
        {"idx": 1, "f1": 0.0140, "f2": 0.090, "lam": 0.18},
        {"idx": 2, "f1": 0.0220, "f2": 0.120, "lam": 0.40},
        {"idx": 3, "f1": 0.0400, "f2": 0.150, "lam": 0.85},
    ]
)
model.define(FrontierPoint.new(frontier_data.to_schema()))

# Two refs over FrontierPoint; Q is P's consecutive neighbor. Property navigation (P.idx, P.f1, …)
# grounds each ref over the concept's instances — the same two-ref adjacency idiom as a recurrence.
P, Q = FrontierPoint.ref(), FrontierPoint.ref()
MARGIN = 1e-6  # non-strict tolerance — see header (degeneracy makes a strict bracket reject valid data)

# --- IC 1: NON-DOMINANCE ---
# Ordered by idx (increasing f2), f1 must be non-decreasing: no point beats another on both objectives.
model.where(Q.idx == P.idx + 1).require(Q.f1 >= P.f1 - MARGIN)

# --- IC 2: CONVEXITY (monotone dual) ---
# On a convex frontier the slope lambda is non-decreasing as f2 rises.
model.where(Q.idx == P.idx + 1).require(Q.lam >= P.lam - MARGIN)

# --- IC 3: SLOPE-CONSISTENCY (secant bracketed by the consecutive duals), product form ---
# lambda_i <= secant <= lambda_{i+1}, written as products to avoid dividing by (f2_{i+1} - f2_i).
model.where(Q.idx == P.idx + 1).require(Q.f1 - P.f1 >= P.lam * (Q.f2 - P.f2) - MARGIN)
model.where(Q.idx == P.idx + 1).require(Q.f1 - P.f1 <= Q.lam * (Q.f2 - P.f2) + MARGIN)

# The ICs above make the engine REJECT a frontier that violates them. To INSPECT rather than reject,
# read the offending pairs relationally instead — this query is empty for a valid convex frontier:
convexity_violations = (
    model.select(
        P.idx.alias("i"), Q.idx.alias("j"), P.lam.alias("lam_i"), Q.lam.alias("lam_j")
    )
    .where(
        Q.idx == P.idx + 1, Q.lam < P.lam - MARGIN
    )  # slope went DOWN ⇒ non-convex / mis-swept
    .to_df()
)
assert convexity_violations.empty, (
    f"convexity violated at pairs: {convexity_violations.to_dict('records')}"
)
print(
    "frontier validated: non-dominance, convexity (monotone dual), slope-consistency all hold"
)
