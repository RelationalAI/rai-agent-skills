# Pattern: model.union() for combining costs from different concept scopes
# Key ideas: two concept types each have their own cost variables;
# sum(ConceptA.cost) and sum(ConceptB.cost) live in different scopes
# and CANNOT be added with +. model.union() merges them into a single objective.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("union_heterogeneous_objective")

# --- Ontology ---
Warehouse = model.Concept("Warehouse", identify_by={"name": String})
Warehouse.capacity = model.Property(f"{Warehouse} has {Integer:capacity}")
Warehouse.fixed_cost = model.Property(f"{Warehouse} has {Float:fixed_cost}")

Transport = model.Concept("Transport", identify_by={"origin": String, "dest": String})
Transport.cost_per_unit = model.Property(f"{Transport} has {Float:cost_per_unit}")
Transport.demand = model.Property(f"{Transport} has {Integer:demand}")
Transport.warehouse = model.Property(f"{Transport} comes from {Warehouse}")

# --- Data ---
wh_data = model.data(
    [("W1", 100, 500.0), ("W2", 80, 300.0), ("W3", 60, 200.0)],
    columns=["name", "capacity", "fixed_cost"],
)
model.define(Warehouse.new(wh_data.to_schema()))

tr_data = model.data(
    [
        ("W1", "CustA", 4.0, 40),
        ("W1", "CustB", 6.0, 30),
        ("W2", "CustA", 5.0, 40),
        ("W2", "CustB", 3.0, 30),
        ("W3", "CustA", 7.0, 40),
        ("W3", "CustB", 2.0, 30),
    ],
    columns=["origin", "dest", "cost_per_unit", "demand"],
)
model.define(Transport.new(tr_data.to_schema()))
model.define(Transport.warehouse(Warehouse)).where(Transport.origin == Warehouse.name)

# --- Decision variables ---
Warehouse.x_open = model.Property(f"{Warehouse} has {Float:x_open}")
Transport.x_ship = model.Property(f"{Transport} has {Float:x_ship}")

problem = Problem(model, Float)
x_open = Float.ref()
x_ship = Float.ref()

x_open_var = problem.solve_for(Warehouse.x_open(x_open), type="bin", name=["open", Warehouse.name])
x_ship_var = problem.solve_for(Transport.x_ship(x_ship), lower=0, name=["ship", Transport.origin, Transport.dest])

# --- Constraints ---
# Demand satisfaction: each route must ship exactly its demand
problem.satisfy(model.require(x_ship == Transport.demand).where(Transport.x_ship(x_ship)))

# Capacity: total shipped from a warehouse cannot exceed its capacity (if open)
problem.satisfy(
    model.where(
        Transport.x_ship(x_ship),
        Transport.warehouse(Warehouse),
        Warehouse.x_open(x_open),
    ).require(sum(x_ship).per(Warehouse) <= Warehouse.capacity * x_open)
)

# --- Objective: model.union() combines costs from TWO different concept scopes ---
# WHY union is needed: Warehouse.fixed_cost * x_open is scoped to Warehouse;
# Transport.cost_per_unit * x_ship is scoped to Transport. These are different
# concept groups -- using + would cause AssertionError. model.union() merges them
# so the outer sum() can aggregate across both.
warehouse_cost = Warehouse.fixed_cost * x_open  # per-Warehouse expression
transport_cost = Transport.cost_per_unit * x_ship  # per-Transport expression

problem.minimize(
    sum(
        model.union(
            warehouse_cost.where(Warehouse.x_open(x_open)),
            transport_cost.where(Transport.x_ship(x_ship)),
        )
    )
)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Total cost: ${si.objective_value:.2f}")

# --- Results ---
print("\nWarehouse decisions:")
model.select(Warehouse.name, Warehouse.x_open).inspect()
print("\nShipments:")
model.select(Transport.origin, Transport.dest, Transport.x_ship).inspect()
