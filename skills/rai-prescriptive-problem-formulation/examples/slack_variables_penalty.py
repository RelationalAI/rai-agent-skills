# Pattern: slack variables with penalty — allow graceful infeasibility
# Key ideas: Slack (unmet) variables absorb shortfall when hard demand satisfaction
# is impossible. High penalty in the objective discourages unmet demand without making
# the problem infeasible. model.union() combines cost terms from different concept scopes.
# This pattern is essential for any minimize objective with forcing constraints — without
# slack, the solver returns INFEASIBLE when capacity < demand.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("slack_variables_penalty")

# --- Ontology (inline) ---
Route = model.Concept("Route", identify_by={"id": String})
Route.cost = model.Property(f"{Route} has {Float:cost}")
Route.capacity = model.Property(f"{Route} has {Integer:capacity}")
Route.destination = model.Property(f"{Route} has {String:destination}")
Route.product = model.Property(f"{Route} has {String:product}")

Demand = model.Concept("Demand", identify_by={"id": String})
Demand.quantity = model.Property(f"{Demand} has {Integer:quantity}")
Demand.location = model.Property(f"{Demand} has {String:location}")
Demand.product = model.Property(f"{Demand} has {String:product}")

# --- Data ---
route_data = model.data([
    {"id": "R1", "cost": 2.0, "capacity": 100, "destination": "NYC", "product": "A"},
    {"id": "R2", "cost": 3.5, "capacity": 80, "destination": "NYC", "product": "A"},
    {"id": "R3", "cost": 1.5, "capacity": 50, "destination": "LA", "product": "B"},
], columns=["id", "cost", "capacity", "destination", "product"])
model.define(Route.new(route_data.to_schema()))

demand_data = model.data([
    {"id": "D1", "quantity": 200, "location": "NYC", "product": "A"},  # exceeds capacity!
    {"id": "D2", "quantity": 30, "location": "LA", "product": "B"},
], columns=["id", "quantity", "location", "product"])
model.define(Demand.new(demand_data.to_schema()))

# --- Formulation ---
problem = Problem(model, Float)

# Decision: flow on each route
Route.x_flow = model.Property(f"{Route} has {Float:flow}")
x_flow_var = problem.solve_for(
    Route.x_flow, name=["flow", Route.id], lower=0, upper=Route.capacity
)

# Slack: unmet demand per demand order
Demand.x_unmet = model.Property(f"{Demand} has {Float:unmet}")
x_unmet_var = problem.solve_for(Demand.x_unmet, name=["unmet", Demand.id], lower=0)

# Forcing constraint: flow into location/product + slack >= demand
D, R = Demand.ref(), Route.ref()
problem.satisfy(
    model.require(sum(R.x_flow).per(D) + D.x_unmet >= D.quantity).where(
        R.destination == D.location,
        R.product == D.product,
    ),
    name=["demand_sat", D.id],
)

# Objective: minimize transport cost + heavy penalty for unmet demand
# model.union() combines per-Route costs and per-Demand penalties into one sum
UNMET_PENALTY = 10000.0
problem.minimize(
    sum(
        model.union(
            Route.cost * Route.x_flow,  # per-Route transport cost
            UNMET_PENALTY * Demand.x_unmet,  # per-Demand penalty
        )
    )
)

# Solve
problem.solve("highs", time_limit_sec=30)
problem.solve_info().display()
