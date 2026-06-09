# Pattern: standardized Pareto frontier analysis for bi-objective optimization results
# Key ideas:
#   - After an epsilon constraint loop produces multiple Pareto points, analyze the
#     frontier systematically: tradeoff table, marginal rates, knee detection,
#     allocation shifts, and regime characterization.
#   - Each Pareto point is a complete solution (Variable.values() df). No point is
#     strictly better than another — present as a menu of operating points.
#   - Parallels scenario_concept_extraction.py (multi-solution extraction)
#     but for epsilon loop output rather than Scenario Concept output.
#
# This example uses a generic pareto_points list structure. The same analysis
# pipeline applies regardless of problem type (QP, MILP, LP) or objective pair.
# Variable DataFrames come from Variable.values() structured queries (see
# epsilon_constraint_pareto.py for the extraction pattern).

# =============================================================================
# INPUT: pareto_points from epsilon loop
# =============================================================================
# Each point is a dict from the epsilon sweep (see epsilon_constraint_pareto.py):
#   pareto_points = [
#       {"label": "min_primary", "primary": 18704.12, "secondary": 137.25, "variables": df},
#       {"label": "eps_1",    "primary": 19906.79, "secondary": 147.71, "variables": df},
#       ...
#   ]
# "primary" = the optimized objective value (from solve_info)
# "secondary" = the constrained objective value (computed from variable df)
# "variables" = structured query df from Variable.values() for this point

# --- Example data (from a tested epsilon constraint sweep) ---
# "slope" = the epsilon-bound's shadow_price (sensitivity=True) — the EXACT tradeoff rate d(primary)/
# d(secondary) at that point. On a convex frontier each secant (Δprimary/Δsecondary, computed below)
# is bracketed by the two endpoints' exact slopes. A MIP returns no duals: omit "slope" and read the
# secant instead.
pareto_points = [
    {"label": "min_primary", "primary": 18704.12, "secondary": 137.25, "slope": 80.0},
    {"label": "eps_1", "primary": 19906.79, "secondary": 147.71, "slope": 180.0},
    {"label": "eps_2", "primary": 23514.78, "secondary": 158.17, "slope": 500.0},
    {"label": "eps_3", "primary": 30698.48, "secondary": 168.63, "slope": 950.0},
    {"label": "eps_4", "primary": 44122.28, "secondary": 179.08, "slope": 1550.0},
    {"label": "eps_5", "primary": 63889.45, "secondary": 189.54, "slope": 2150.0},
    {
        "label": "max_secondary",
        "primary": 90000.00,
        "secondary": 200.00,
        "slope": 2700.0,
    },
]
primary_name = "Primary objective (minimize)"
secondary_name = "Secondary objective (maximize)"

# =============================================================================
# 1. TRADEOFF TABLE: both objectives + marginal rate at each point
# =============================================================================
# "Secant" = finite-difference Δprimary/Δsecondary between points; "Tradeoff λ" = the exact
# shadow_price at the point (sensitivity=True). Showing both makes the secant-vs-tangent gap visible.
print(
    f"{'#':>3} {'Label':>10} {secondary_name:>16} {primary_name:>16} {'Secant':>12} {'Tradeoff λ':>12}"
)
print("-" * 76)

marginal_rates = []
for i, pt in enumerate(pareto_points):
    if i > 0:
        dp = pt["primary"] - pareto_points[i - 1]["primary"]
        ds = pt["secondary"] - pareto_points[i - 1]["secondary"]
        rate = dp / ds if abs(ds) > 1e-6 else float("inf")
        marginal_rates.append(rate)
        rate_str = f"{rate:.1f}"
    else:
        rate_str = "—"
    # Exact tradeoff rate = the eps-bound's shadow price; "n/a" for a MIP (no duals → use the secant).
    slope = pt.get("slope")
    slope_str = f"{slope:.1f}" if slope is not None else "n/a"
    print(
        f"{i + 1:>3} {pt['label']:>10} {pt['secondary']:>16.2f} {pt['primary']:>16.2f} {rate_str:>12} {slope_str:>12}"
    )

# =============================================================================
# 2. KNEE DETECTION: where the tradeoff rate RATIO jumps most
# =============================================================================
# Knee is NOT where the absolute rate is highest (that's always the last point). It is the
# last point BEFORE the rate accelerates most -- the largest ratio between consecutive rates,
# marked at the point just before the jump ("cost jumps beyond this point").
#
# PREFER THE EXACT DUAL SEQUENCE when every point carries a shadow_price: the secant is only a
# finite-difference approximation, so on a curved frontier its ratio peak can sit a point off
# from the exact dual's. Driving the knee off the secant while the exact slope sits unused in
# the data would contradict the dual-guided guidance (see sensitivity-analysis.md, "Knee from
# the exact dual sequence"). Fall back to the secant only for a MIP, which returns no duals.
# NOTE: both bases assume rates increase (minimize-primary / maximize-secondary); if they
# decrease (maximize-primary / minimize-secondary), invert the ratio.
knee_idx = None
max_jump = 0.0
knee_basis = ""
duals = [pt["slope"] for pt in pareto_points if pt.get("slope") is not None]
if len(duals) == len(
    pareto_points
):  # every point carries an exact dual (LP/QP, not MIP)
    knee_basis = "exact dual ratio"
    # Ratio of consecutive shadow prices. Start at j=2 so the knee is an interior point (never
    # the min-primary anchor at index 0); mark j-1, the point just before the largest jump.
    for j in range(2, len(duals)):
        if duals[j - 1] > 1e-9 and duals[j] / duals[j - 1] > max_jump:
            max_jump, knee_idx = duals[j] / duals[j - 1], j - 1
elif len(marginal_rates) >= 2:
    knee_basis = "secant ratio"
    # MIP fallback: finite-difference secants. marginal_rates[i] spans points (i, i+1).
    for i in range(len(marginal_rates) - 1):
        if marginal_rates[i] > 1e-6:
            jump = marginal_rates[i + 1] / marginal_rates[i]
        else:
            jump = marginal_rates[i + 1] if marginal_rates[i + 1] > 0 else 0
        if jump > max_jump:
            max_jump = jump
            knee_idx = i + 1

if knee_idx is not None:
    knee_pt = pareto_points[knee_idx]
    print(
        f"\nKnee: Point {knee_idx + 1} ({knee_pt['label']}) — marginal cost jumps {max_jump:.1f}x "
        f"beyond this point ({knee_basis})"
    )
    print(f"  {secondary_name}: {knee_pt['secondary']:.2f}")
    print(f"  {primary_name}: {knee_pt['primary']:.2f}")
else:
    print("\nKnee: not detected (flat frontier — rates do not accelerate)")

# =============================================================================
# 3. ALLOCATION SHIFTS + REGIME DETECTION
# =============================================================================
# Compare variable values between consecutive Pareto points to identify
# what decisions change along the frontier. Look for:
#   - Entities that activate (0 → non-zero) or deactivate (non-zero → 0)
#   - Phase transitions (structural regime changes, not just gradual shifts)
# These are more valuable than raw numbers for the user.

# (Requires actual variable DataFrames from the epsilon loop. Pseudocode below.)
#
# for i in range(len(pareto_points) - 1):
#     df_a = pareto_points[i]["variables"]
#     df_b = pareto_points[i+1]["variables"]
#     for _, row_b in df_b.iterrows():
#         name, val_b = str(row_b.iloc[0]), float(row_b.iloc[1])
#         val_a = lookup(df_a, name)
#         if val_a < 1e-6 and val_b > 1e-6:
#             print(f"  ACTIVATED: {name} = {val_b:.1f}")
#         elif val_a > 1e-6 and val_b < 1e-6:
#             print(f"  DEACTIVATED: {name}")
#         elif abs(val_b - val_a) / max(abs(val_a), 1) > 0.5:
#             print(f"  SHIFTED: {name} {val_a:.1f} → {val_b:.1f}")

# =============================================================================
# 4. FRONTIER VISUALIZATION
# =============================================================================
height, width = 12, 50
secondaries = [pt["secondary"] for pt in pareto_points]
primaries = [pt["primary"] for pt in pareto_points]

x_min, x_max = min(secondaries), max(secondaries)
y_min, y_max = min(primaries), max(primaries)
x_pad = (x_max - x_min) * 0.05 or 1
y_pad = (y_max - y_min) * 0.05 or 1
x_min -= x_pad
x_max += x_pad
y_min -= y_pad
y_max += y_pad

grid = [[" " for _ in range(width)] for _ in range(height)]
for i, (x, y) in enumerate(zip(secondaries, primaries)):
    col = int((x - x_min) / (x_max - x_min) * (width - 1))
    row = int((1 - (y - y_min) / (y_max - y_min)) * (height - 1))
    col = max(0, min(width - 1, col))
    row = max(0, min(height - 1, row))
    if i == 0:
        grid[row][col] = "A"  # first anchor
    elif i == len(pareto_points) - 1:
        grid[row][col] = "B"  # second anchor
    elif knee_idx is not None and i == knee_idx:
        grid[row][col] = "K"  # knee
    else:
        grid[row][col] = "*"

print(f"\n  {primary_name}")
for r in range(height):
    y_val = y_max - (r / (height - 1)) * (y_max - y_min)
    if r % 3 == 0:
        print(f"{y_val:>10.0f} | {''.join(grid[r])}")
    else:
        print(f"{'':>10} | {''.join(grid[r])}")
print(f"{'':>10} +{'—' * width}→")
print(f"{'':>12}{secondary_name}")
print("\n  A = anchor 1, B = anchor 2, K = knee, * = interior point")

# =============================================================================
# 5. BUSINESS NARRATIVE (template for agent to adapt to domain)
# =============================================================================
# The agent should produce a narrative like:
#
#   "The efficient frontier shows how [primary] increases as [secondary] is pushed
#    higher. The knee is at [secondary value] — below this, [secondary] improvements
#    come cheaply; above it, each additional unit of [secondary] costs [X]x more in
#    [primary]. We recommend targeting [knee secondary] as the best value operating
#    point. Beyond this, [describe what changes structurally in the allocation]."
