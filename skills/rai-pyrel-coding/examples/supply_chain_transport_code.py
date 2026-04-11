# Pattern: standalone Property (not on concept), model.union() for multi-component objective
# Key ideas: Property(f"day {Integer:t} has {Float:val}") creates a concept-free variable;
# model.union() combines disjoint cost terms into one summable expression; self-join on
# LTLSegment refs for piecewise cost decomposition.

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("supply_chain_transport_code")

# --- Ontology (abbreviated) ---
FreightGroup = model.Concept("FreightGroup", identify_by={"name": String})
FreightGroup.inv_start = model.Property(f"{FreightGroup} has {Float:inv_start}")
FreightGroup.inv_start_t = model.Property(f"{FreightGroup} has {Integer:inv_start_t}")

TransportType = model.Concept("TransportType", identify_by={"name": String})
TransportType.transit_time = model.Property(f"{TransportType} has {Integer:transit_time}")

LTLSegment = model.Concept("LTLSegment", identify_by={"seg": Integer})
LTLSegment.limit = model.Property(f"{LTLSegment} has {Float:limit}")
LTLSegment.cost = model.Property(f"{LTLSegment} has {Float:cost}")

# --- Decision variables ---
problem = Problem(model, Float)
t = Integer.ref()
departure_days = std.common.range(1, 5)

# Inventory variable per freight group per day
FreightGroup.x_inv = model.Property(f"{FreightGroup} on day {Integer:t} has {Float:inv}")
x_inv = Float.ref()
problem.solve_for(
    FreightGroup.x_inv(t, x_inv),
    type="cont",
    lower=0,
    name=["inv", FreightGroup.name, t],
    where=[t == departure_days],
)

# Standalone Property (not attached to any concept) — per-day TL indicator
bin_tl = model.Property(f"departure day {Integer:t} has {Float:bin_tl}")
y_bin_tl = Float.ref()
problem.solve_for(bin_tl(t, y_bin_tl), type="bin", name=["y_bin_tl", t], where=[t == departure_days])

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
tl_fixed_cost = 2000.0

total_inv_cost = inv_cost_rate * sum(x_inv).where(FreightGroup.x_inv(t, x_inv), t > FreightGroup.inv_start_t)

total_tl_cost = tl_fixed_cost * sum(y_bin_tl).where(bin_tl(Integer.ref(), y_bin_tl))

total_ltl_rem_cost = LTLSegment.cost * sum(x_rem_ltl).per(LTLSegment).where(
    LTLSegment.x_rem_ltl(Integer.ref(), x_rem_ltl)
)

# Self-join: previous segment's limit * current segment's binary
total_ltl_bin_cost = (LTLSegment1.cost * LTLSegment1.limit) * sum(y_bin_ltl_ref).per(LTLSegment1).where(
    LTLSegment2.y_bin_ltl(Integer.ref(), y_bin_ltl_ref),
    LTLSegment1.seg == LTLSegment2.seg - 1,
)

# model.union() combines all 4 disjoint cost terms into one summable expression
total_cost = sum(model.union(total_inv_cost, total_tl_cost, total_ltl_rem_cost, total_ltl_bin_cost))
problem.minimize(total_cost)

problem.solve("highs", time_limit_sec=60)
