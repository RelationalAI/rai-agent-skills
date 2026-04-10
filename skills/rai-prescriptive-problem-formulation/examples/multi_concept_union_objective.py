# Pattern: multi-concept coordination — inventory flow conservation + mode selection
# Key ideas: three variable types (continuous inv, continuous qty, binary indicator)
# across two concepts (FreightGroup, TransportType); inventory balance links them;
# model.union() combines heterogeneous cost components into a single objective.

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("multi_concept_union_objective")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
FreightGroup = Concept("FreightGroup", identify_by={"name": String})
FreightGroup.inv_start_t = Property(f"{FreightGroup} has {Integer:inv_start_t}")
FreightGroup.inv_end_t = Property(f"{FreightGroup} has {Integer:inv_end_t}")
FreightGroup.tra_start_t = Property(f"{FreightGroup} has {Integer:tra_start_t}")
FreightGroup.tra_end_t = Property(f"{FreightGroup} has {Integer:tra_end_t}")
FreightGroup.inv_start = Property(f"{FreightGroup} has {Float:inv_start}")

TransportType = Concept("TransportType", identify_by={"name": String})
TransportType.transit_time = Property(f"{TransportType} has {Integer:transit_time}")

# --- Decision variables ---
t = Integer.ref()
fg = FreightGroup.ref()

problem = Problem(model, Float)

# Inventory level per (freight group, day)
FreightGroup.x_inv = Property(f"{FreightGroup} on day {Integer:t} has {Float:inv}")
x_inv = Float.ref()
x_inv_var = problem.solve_for(
    FreightGroup.x_inv(t, x_inv),
    lower=0,
    name=["x_inv", FreightGroup.name, t],
    where=[t == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)],
)

# Quantity shipped per (transport type, freight group, day)
TransportType.x_qty_tra = Property(f"{TransportType} for {FreightGroup} on day {Integer:t} has {Float:qty_tra}")
TransportType.y_bin_tra = Property(f"{TransportType} for {FreightGroup} on day {Integer:t} has {Float:bin_tra}")
x_qty_tra = Float.ref()
y_bin_tra = Float.ref()
x_qty_tra_var = problem.solve_for(
    TransportType.x_qty_tra(fg, t, x_qty_tra),
    lower=0,
    name=["x_qty_tra", TransportType.name, fg.name, t],
    where=[t == std.common.range(fg.tra_start_t, fg.tra_end_t + 1)],
)
y_bin_tra_var = problem.solve_for(
    TransportType.y_bin_tra(fg, t, y_bin_tra),
    type="bin",
    name=["y_bin_tra", TransportType.name, fg.name, t],
    where=[t == std.common.range(fg.tra_start_t, fg.tra_end_t + 1)],
)

# --- Inventory flow conservation: inv[t] = inv[t+1] + sum(shipped on day t) ---
# This is the core linking constraint between inventory variables and shipping variables.
problem.satisfy(
    model.where(
        x_inv1 := Float.ref(),
        x_inv2 := Float.ref(),
        FreightGroup.x_inv(t, x_inv1),
        FreightGroup.x_inv(t + 1, x_inv2),
        TransportType.x_qty_tra(FreightGroup, t, x_qty_tra),
    ).require(x_inv1 == x_inv2 + sum(x_qty_tra).per(FreightGroup, t))
)

# --- Boundary conditions ---
# Initial inventory matches starting position; final inventory is zero
problem.satisfy(
    model.require(x_inv == FreightGroup.inv_start).where(FreightGroup.x_inv(FreightGroup.inv_start_t, x_inv))
)
problem.satisfy(model.require(x_inv == 0).where(FreightGroup.x_inv(FreightGroup.inv_end_t, x_inv)))

# --- Linking: all-or-nothing shipping (binary indicator scales quantity) ---
problem.satisfy(
    model.require(x_qty_tra == FreightGroup.inv_start * y_bin_tra).where(
        TransportType.x_qty_tra(FreightGroup, t, x_qty_tra),
        TransportType.y_bin_tra(FreightGroup, t, y_bin_tra),
    )
)

# --- Objective: multi-component cost (use model.union() to combine heterogeneous terms) ---
inv_cost = 0.001 * sum(x_inv).where(FreightGroup.x_inv(t, x_inv), t > FreightGroup.inv_start_t)
tl_fixed_cost = 2000.0 * sum(y_bin_tra).where(
    TransportType.name("tl"),
    TransportType.y_bin_tra(FreightGroup, t, y_bin_tra),
)
total_cost = sum(model.union(inv_cost, tl_fixed_cost))
problem.minimize(total_cost)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Cost: ${si.objective_value:.2f}")
