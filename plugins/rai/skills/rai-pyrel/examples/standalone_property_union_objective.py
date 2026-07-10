# Pattern: standalone Property (not on concept), model.union() for multi-component objective
# Key ideas: Property(f"day {Integer:t} has {Float:val}") creates a concept-free variable;
# model.union() combines disjoint cost terms into one summable expression; self-join on
# LTLSegment refs for piecewise cost decomposition.

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("standalone_property_union_objective")

# --- Ontology (abbreviated) ---
ResourceGroup = model.Concept("ResourceGroup", identify_by={"name": String})
ResourceGroup.inv_start = model.Property(f"{ResourceGroup} has {Float:inv_start}")
ResourceGroup.inv_start_t = model.Property(f"{ResourceGroup} has {Integer:inv_start_t}")

Mode = model.Concept("Mode", identify_by={"name": String})
Mode.transit_time = model.Property(f"{Mode} has {Integer:transit_time}")

LTLSegment = model.Concept("LTLSegment", identify_by={"seg": Integer})
LTLSegment.limit = model.Property(f"{LTLSegment} has {Float:limit}")
LTLSegment.cost = model.Property(f"{LTLSegment} has {Float:cost}")

# --- Decision variables ---
problem = Problem(model, Float)
t = Integer.ref()
departure_days = std.common.range(1, 5)

# Inventory variable per resource group per day
ResourceGroup.x_inv = model.Property(f"{ResourceGroup} on day {Integer:t} has {Float:inv}")
x_inv = Float.ref()
problem.solve_for(
    ResourceGroup.x_inv(t, x_inv),
    type="cont",
    lower=0,
    name=["inv", ResourceGroup.name, t],
    where=[t == departure_days],
)

# Standalone Property (not attached to any concept) — per-day fast-mode indicator
bin_fast = model.Property(f"departure day {Integer:t} has {Float:bin_fast}")
y_bin_fast = Float.ref()
problem.solve_for(bin_fast(t, y_bin_fast), type="bin", name=["y_bin_fast", t], where=[t == departure_days])

# --- LTL piecewise cost with self-join on segment refs ---
LTLSegment.x_rem_ltl = model.Property(f"{LTLSegment} on day {Integer:t} has {Float:rem_ltl}")
LTLSegment.y_bin_ltl = model.Property(f"{LTLSegment} on day {Integer:t} has {Float:bin_ltl}")
x_rem_ltl = Float.ref()
y_bin_ltl_ref = Float.ref()

problem.solve_for(
    LTLSegment.x_rem_ltl(t, x_rem_ltl),
    type="cont",
    lower=0,
    name=["rem_ltl", LTLSegment.seg, t],
    where=[t == departure_days],
)
problem.solve_for(
    LTLSegment.y_bin_ltl(t, y_bin_ltl_ref),
    type="bin",
    name=["bin_ltl", LTLSegment.seg, t],
    where=[t == departure_days],
)

# Self-join refs for predecessor segment lookup
LTLSegment1 = LTLSegment.ref()
LTLSegment2 = LTLSegment.ref()

# --- model.union() for multi-component objective ---
inv_cost_rate = 0.001
fast_fixed_cost = 2000.0

total_inv_cost = inv_cost_rate * sum(x_inv).where(ResourceGroup.x_inv(t, x_inv), t > ResourceGroup.inv_start_t)

total_fast_cost = fast_fixed_cost * sum(y_bin_fast).where(bin_fast(Integer.ref(), y_bin_fast))

total_ltl_rem_cost = LTLSegment.cost * sum(x_rem_ltl).per(LTLSegment).where(
    LTLSegment.x_rem_ltl(Integer.ref(), x_rem_ltl)
)

# Self-join: previous segment's limit * current segment's binary
total_ltl_bin_cost = (LTLSegment1.cost * LTLSegment1.limit) * sum(y_bin_ltl_ref).per(LTLSegment1).where(
    LTLSegment2.y_bin_ltl(Integer.ref(), y_bin_ltl_ref),
    LTLSegment1.seg == LTLSegment2.seg - 1,
)

# model.union() combines all 4 disjoint cost terms into one summable expression
total_cost = sum(model.union(total_inv_cost, total_fast_cost, total_ltl_rem_cost, total_ltl_bin_cost))
problem.minimize(total_cost)

problem.solve("highs", time_limit_sec=60)
