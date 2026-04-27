# Pattern: multi-concept coordination — inventory flow conservation + mode selection
# Key ideas: three variable types (continuous inv, continuous qty, binary indicator)
# across two concepts (ResourceGroup, Mode); inventory balance links them;
# model.union() combines heterogeneous cost components into a single objective.

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("multi_concept_union_objective")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
ResourceGroup = Concept("ResourceGroup", identify_by={"name": String})
ResourceGroup.inv_start_t = Property(f"{ResourceGroup} has {Integer:inv_start_t}")
ResourceGroup.inv_end_t = Property(f"{ResourceGroup} has {Integer:inv_end_t}")
ResourceGroup.mode_start_t = Property(f"{ResourceGroup} has {Integer:mode_start_t}")
ResourceGroup.mode_end_t = Property(f"{ResourceGroup} has {Integer:mode_end_t}")
ResourceGroup.inv_start = Property(f"{ResourceGroup} has {Float:inv_start}")

Mode = Concept("Mode", identify_by={"name": String})
Mode.transit_time = Property(f"{Mode} has {Integer:transit_time}")

# --- Inline data ---
rg_data = model.data(
    [
        ("RG_East", 1, 5, 1, 4, 100.0),
        ("RG_West", 1, 5, 1, 4, 80.0),
    ],
    columns=[
        "name",
        "inv_start_t",
        "inv_end_t",
        "mode_start_t",
        "mode_end_t",
        "inv_start",
    ],
)
model.define(ResourceGroup.new(rg_data.to_schema()))

mode_data = model.data(
    [("fast", 1), ("slow", 2)],
    columns=["name", "transit_time"],
)
model.define(Mode.new(mode_data.to_schema()))

# --- Decision variables ---
t = Integer.ref()
rg = ResourceGroup.ref()

problem = Problem(model, Float)

# Inventory level per (resource group, day)
ResourceGroup.x_inv = Property(f"{ResourceGroup} on day {Integer:t} has {Float:inv}")
x_inv = Float.ref()
problem.solve_for(
    ResourceGroup.x_inv(t, x_inv),
    lower=0,
    name=["x_inv", ResourceGroup.name, t],
    where=[t == std.common.range(ResourceGroup.inv_start_t, ResourceGroup.inv_end_t + 1)],
)

# Quantity moved per (mode, resource group, day)
Mode.x_qty_mode = Property(f"{Mode} for {ResourceGroup} on day {Integer:t} has {Float:qty_mode}")
Mode.y_bin_mode = Property(f"{Mode} for {ResourceGroup} on day {Integer:t} has {Float:bin_mode}")
x_qty_mode = Float.ref()
y_bin_mode = Float.ref()
problem.solve_for(
    Mode.x_qty_mode(rg, t, x_qty_mode),
    lower=0,
    name=["x_qty_mode", Mode.name, rg.name, t],
    where=[t == std.common.range(rg.mode_start_t, rg.mode_end_t + 1)],
)
problem.solve_for(
    Mode.y_bin_mode(rg, t, y_bin_mode),
    type="bin",
    name=["y_bin_mode", Mode.name, rg.name, t],
    where=[t == std.common.range(rg.mode_start_t, rg.mode_end_t + 1)],
)

# --- Inventory flow conservation: inv[t] = inv[t+1] + sum(qty_mode on day t) ---
# This is the core linking constraint between inventory variables and quantity variables.
problem.satisfy(
    model.where(
        x_inv1 := Float.ref(),
        x_inv2 := Float.ref(),
        ResourceGroup.x_inv(t, x_inv1),
        ResourceGroup.x_inv(t + 1, x_inv2),
        Mode.x_qty_mode(ResourceGroup, t, x_qty_mode),
    ).require(x_inv1 == x_inv2 + sum(x_qty_mode).per(ResourceGroup, t))
)

# --- Boundary conditions ---
# Initial inventory matches starting position; final inventory is zero
problem.satisfy(
    model.require(x_inv == ResourceGroup.inv_start).where(ResourceGroup.x_inv(ResourceGroup.inv_start_t, x_inv))
)
problem.satisfy(model.require(x_inv == 0).where(ResourceGroup.x_inv(ResourceGroup.inv_end_t, x_inv)))

# --- Linking: all-or-nothing activation (binary indicator scales quantity) ---
problem.satisfy(
    model.require(x_qty_mode == ResourceGroup.inv_start * y_bin_mode).where(
        Mode.x_qty_mode(ResourceGroup, t, x_qty_mode),
        Mode.y_bin_mode(ResourceGroup, t, y_bin_mode),
    )
)

# --- Objective: multi-component cost (use model.union() to combine heterogeneous terms) ---
inv_cost = 0.001 * sum(x_inv).where(ResourceGroup.x_inv(t, x_inv), t > ResourceGroup.inv_start_t)
fast_fixed_cost = 2000.0 * sum(y_bin_mode).where(
    Mode.name("fast"),
    Mode.y_bin_mode(ResourceGroup, t, y_bin_mode),
)
total_cost = sum(model.union(inv_cost, fast_fixed_cost))
problem.minimize(total_cost)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Cost: ${si.objective_value:.2f}")
