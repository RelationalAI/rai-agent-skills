# Pattern: bi-objective epsilon constraint via Loop + populate=False
# with Scenario Concept inside the loop (N epsilon solves, not N × M).
#
# Key ideas:
#   - Two competing objectives: minimize risk (primary) AND maximize return (secondary)
#   - Epsilon constraint converts secondary objective to a parameterized bound
#   - Loop sweeps epsilon targets; each solve is a standard single-objective problem
#   - Scenario Concept (budget levels) inside loop: one solve handles all scenarios
#   - populate=False prevents cross-iteration collision; results via variable_values()
#
# TRANSFORMATION FROM SINGLE-OBJECTIVE:
#   Original: return is a fixed constraint (>= threshold), risk is minimized once
#     p.satisfy(require(sum(returns * x).per(Scenario) >= Scenario.min_return))
#     p.minimize(risk)
#   Bi-objective: return target becomes the loop parameter, swept across feasible range
#     for eps in epsilon_values:
#         p.satisfy(require(sum(returns * x).per(Scenario) >= eps * Scenario.budget))
#         p.minimize(risk)
#   This exposes the full risk-return frontier instead of a single operating point.
#
# UNBUNDLE-THE-PENALTY pattern (alternative entry point, shown for reference):
#   Original: p.minimize(cost + PENALTY * sum(slack))
#   Bi-objective: p.minimize(cost) with p.satisfy(require(sum(slack) <= eps))
#   Same loop structure — the epsilon constraint replaces the penalty term.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio_risk_return")

# --- Ontology ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
# (data loading omitted — follows model.where(Stock.index(data.i), PairedStock.index(data.j))
#  .define(Stock.covar(Stock, PairedStock, data.covar)) pattern)

PairedStock = Stock.ref()

# --- Scenario Concept: budget parameter variations ---
# Scenarios are INSIDE the epsilon loop — each epsilon solve handles all budgets at once.
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.budget = model.Property(f"{Scenario} has {Float:budget}")
# (data: [("budget_500", 500), ("budget_1000", 1000), ("budget_2000", 2000)])

# --- Decision variable indexed by Scenario ---
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
covar_value = Float.ref()
x_qty_paired = Float.ref()

# =============================================================================
# ANCHOR SOLVES: establish feasible return range
# =============================================================================
# Anchor 1: minimize risk only → get return at min-risk portfolio (per scenario)
# Anchor 2: maximize return only → get max achievable return (per scenario)
# These define the epsilon sweep range. Without them, epsilon values may be
# non-binding (wasted solves) or infeasible.

p1 = Problem(model, Float)
p1.solve_for(Stock.x_quantity(Scenario, x_qty),
             name=["qty", Scenario.name, Stock.index], populate=False)
p1.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(x_qty >= 0))
p1.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
    sum(x_qty).per(Scenario) <= Scenario.budget))
p1.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
    sum(x_qty).per(Scenario) >= Scenario.budget))
p1.minimize(sum(covar_value * x_qty * x_qty_paired).where(
    Stock.covar(PairedStock, covar_value),
    Stock.x_quantity(Scenario, x_qty),
    PairedStock.x_quantity(Scenario, x_qty_paired)))
p1.solve("ipopt", time_limit_sec=60)
# → evaluate return from variable_values df using builtins.sum (not RAI sum)

# =============================================================================
# EPSILON SWEEP: minimize risk subject to return >= eps (per scenario)
# =============================================================================
# return_rate_min, return_rate_max derived from anchor solutions
# epsilon_rates = linspace(return_rate_min, return_rate_max, n_interior + 2)[1:-1]

pareto_points = []
for rate in epsilon_rates:
    p = Problem(model, Float)
    p.solve_for(Stock.x_quantity(Scenario, x_qty),
                name=["qty", Scenario.name, Stock.index], populate=False)
    p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(x_qty >= 0))
    p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
        sum(x_qty).per(Scenario) <= Scenario.budget))
    p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
        sum(x_qty).per(Scenario) >= Scenario.budget))

    # EPSILON CONSTRAINT: return rate >= target (scaled by budget per scenario)
    p.satisfy(model.where(Stock.x_quantity(Scenario, x_qty)).require(
        sum(Stock.returns * x_qty).per(Scenario) >= rate * Scenario.budget))

    # Primary objective: minimize risk
    p.minimize(sum(covar_value * x_qty * x_qty_paired).where(
        Stock.covar(PairedStock, covar_value),
        Stock.x_quantity(Scenario, x_qty),
        PairedStock.x_quantity(Scenario, x_qty_paired)))

    p.solve("ipopt", time_limit_sec=60)
    si = p.solve_info()

    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        break  # past feasible range

    pareto_points.append({
        "return_rate": rate,
        "risk": si.objective_value,
        "variables": p.variable_values().to_df(),
    })
