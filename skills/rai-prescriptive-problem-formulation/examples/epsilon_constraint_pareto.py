# Pattern: bi-objective epsilon constraint via Loop + populate=False
# with Scenario Concept inside the loop (N epsilon solves, not N x M).
#
# Key ideas:
#   - Two competing objectives: minimize quadratic cost (primary) AND
#     maximize linear benefit (secondary)
#   - Epsilon constraint converts secondary objective to a parameterized bound
#   - Loop sweeps epsilon targets; each solve is a standard single-objective problem
#   - Scenario Concept (capacity levels) inside loop: one solve handles all scenarios
#   - populate=False prevents cross-iteration collision; results via variable_values()
#
# TRANSFORMATION FROM SINGLE-OBJECTIVE:
#   Original: benefit is a fixed constraint (>= threshold), quadratic cost is minimized once
#     p.satisfy(model.require(sum(values * x).per(Scenario) >= Scenario.min_benefit))
#     p.minimize(quadratic_cost)
#   Bi-objective: benefit target becomes the loop parameter, swept across feasible range
#     for eps in epsilon_values:
#         p.satisfy(model.require(sum(values * x).per(Scenario) >= eps * Scenario.capacity))
#         p.minimize(quadratic_cost)
#   This exposes the full cost-benefit frontier instead of a single operating point.
#
# UNBUNDLE-THE-PENALTY pattern (alternative entry point, shown for reference):
#   Original: p.minimize(cost + PENALTY * sum(slack))
#   Bi-objective: p.minimize(cost) with p.satisfy(model.require(sum(slack) <= eps))
#   Same loop structure -- the epsilon constraint replaces the penalty term.

import builtins

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("epsilon_constraint_pareto")

# --- Ontology ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")

PairedItem = Item.ref()

# --- Inline sample data via model.data() ---
item_data = model.data([
    {"index": 1, "value": 0.08},
    {"index": 2, "value": 0.15},
    {"index": 3, "value": 0.05},
])
model.define(Item.new(item_data.to_schema()))

# Symmetric interaction matrix (3x3)
interaction_raw = model.data([
    {"i": 1, "j": 1, "w": 0.04},
    {"i": 1, "j": 2, "w": 0.01},
    {"i": 1, "j": 3, "w": 0.005},
    {"i": 2, "j": 1, "w": 0.01},
    {"i": 2, "j": 2, "w": 0.09},
    {"i": 2, "j": 3, "w": 0.02},
    {"i": 3, "j": 1, "w": 0.005},
    {"i": 3, "j": 2, "w": 0.02},
    {"i": 3, "j": 3, "w": 0.01},
], columns=["i", "j", "w"])
model.where(
    Item.index(interaction_raw.i),
    PairedItem.index(interaction_raw.j),
).define(Item.interaction(PairedItem, interaction_raw.w))

# --- Scenario Concept: capacity parameter variations ---
# Scenarios are INSIDE the epsilon loop -- each epsilon solve handles all capacities at once.
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.capacity = model.Property(f"{Scenario} has {Float:capacity}")

scenario_data = model.data([
    {"name": "capacity_50", "capacity": 50.0},
    {"name": "capacity_100", "capacity": 100.0},
])
model.define(Scenario.new(scenario_data.to_schema()))

# --- Decision variable indexed by Scenario ---
Item.x_allocation = model.Property(f"{Item} in {Scenario} has {Float:allocation}")
x_alloc = Float.ref()
interaction_val = Float.ref()
x_alloc_paired = Float.ref()

# Keep item value lookup for post-solve benefit computation
item_value_lookup = {1: 0.08, 2: 0.15, 3: 0.05}

# =============================================================================
# ANCHOR SOLVES: establish feasible benefit range
# =============================================================================
# Anchor 1: minimize quadratic cost only -> get benefit at min-cost allocation (per scenario)
# Anchor 2: maximize benefit only -> get max achievable benefit (per scenario)
# These define the epsilon sweep range. Without them, epsilon values may be
# non-binding (wasted solves) or infeasible.

p1 = Problem(model, Float)
p1.solve_for(Item.x_allocation(Scenario, x_alloc),
             name=["alloc", Scenario.name, Item.index], populate=False)
p1.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(x_alloc >= 0))
p1.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
    sum(x_alloc).per(Scenario) <= Scenario.capacity))
p1.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
    sum(x_alloc).per(Scenario) >= Scenario.capacity))
p1.minimize(sum(interaction_val * x_alloc * x_alloc_paired).where(
    Item.interaction(PairedItem, interaction_val),
    Item.x_allocation(Scenario, x_alloc),
    PairedItem.x_allocation(Scenario, x_alloc_paired)))
p1.solve("ipopt", time_limit_sec=60)
si1 = p1.solve_info()
assert si1.termination_status in ("OPTIMAL", "LOCALLY_SOLVED"), f"Anchor 1 failed: {si1.termination_status}"

# Evaluate benefit at min-cost solution (secondary value at anchor 1)
# variable_values() returns DataFrame with name/value columns;
# name format follows the name= pattern: "alloc_{scenario}_{item_index}"
df1 = p1.variable_values().to_df()
benefit_at_min_cost = builtins.sum(
    item_value_lookup.get(int(name.rsplit("_", 1)[-1]), 0) * val
    for name, val in zip(df1["name"], df1["value"])
)

# --- Anchor 2: maximize benefit only -> get max achievable benefit ---
p2 = Problem(model, Float)
p2.solve_for(Item.x_allocation(Scenario, x_alloc),
             name=["alloc", Scenario.name, Item.index], populate=False)
p2.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(x_alloc >= 0))
p2.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
    sum(x_alloc).per(Scenario) <= Scenario.capacity))
p2.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
    sum(x_alloc).per(Scenario) >= Scenario.capacity))
p2.maximize(sum(Item.value * x_alloc).where(Item.x_allocation(Scenario, x_alloc)))
p2.solve("ipopt", time_limit_sec=60)
si2 = p2.solve_info()
assert si2.termination_status in ("OPTIMAL", "LOCALLY_SOLVED"), f"Anchor 2 failed: {si2.termination_status}"

df2 = p2.variable_values().to_df()
benefit_at_max_benefit = builtins.sum(
    item_value_lookup.get(int(name.rsplit("_", 1)[-1]), 0) * val
    for name, val in zip(df2["name"], df2["value"])
)

# =============================================================================
# EPSILON SWEEP: minimize quadratic cost subject to linear benefit >= eps (per scenario)
# =============================================================================
# Compute epsilon grid from anchor-derived range (as benefit rates per unit capacity)
# Using a representative capacity to normalize; rates are capacity-independent
representative_capacity = 100  # any scenario capacity works for rate normalization
benefit_rate_min = benefit_at_min_cost / representative_capacity
benefit_rate_max = benefit_at_max_benefit / representative_capacity
n_interior = 5
epsilon_rates = [
    benefit_rate_min + i * (benefit_rate_max - benefit_rate_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]

pareto_points = []
consecutive_infeasible = 0
for rate in epsilon_rates:
    p = Problem(model, Float)
    p.solve_for(Item.x_allocation(Scenario, x_alloc),
                name=["alloc", Scenario.name, Item.index], populate=False)
    p.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(x_alloc >= 0))
    p.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
        sum(x_alloc).per(Scenario) <= Scenario.capacity))
    p.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
        sum(x_alloc).per(Scenario) >= Scenario.capacity))

    # EPSILON CONSTRAINT: benefit rate >= target (scaled by capacity per scenario)
    p.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(
        sum(Item.value * x_alloc).per(Scenario) >= rate * Scenario.capacity))

    # Primary objective: minimize quadratic cost
    p.minimize(sum(interaction_val * x_alloc * x_alloc_paired).where(
        Item.interaction(PairedItem, interaction_val),
        Item.x_allocation(Scenario, x_alloc),
        PairedItem.x_allocation(Scenario, x_alloc_paired)))

    p.solve("ipopt", time_limit_sec=60)
    si = p.solve_info()

    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        consecutive_infeasible += 1
        if consecutive_infeasible >= 2:
            break  # two consecutive infeasible -- past feasible range
        continue  # skip but try next point (non-convex gaps)
    consecutive_infeasible = 0

    pareto_points.append({
        "benefit_rate": rate,
        "quadratic_cost": si.objective_value,
        "variables": p.variable_values().to_df(),
    })
