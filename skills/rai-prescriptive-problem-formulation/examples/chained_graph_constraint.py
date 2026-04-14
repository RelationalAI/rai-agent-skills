# Pattern: Chained reasoner -- graph centrality as a prescriptive CONSTRAINT lower bound.
# Key ideas: graph eigenvector centrality drives a minimum allocation constraint
# (x_allocation >= centrality * MIN_FACTOR) rather than an objective weight;
# this guarantees critical hubs receive proportional allocation regardless of
# cost tradeoffs. Contrasts with chained_graph_prescriptive.py which
# uses centrality in the objective only.
#
# Requires PyRel SDK >= 1.0.13.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("chained_graph_constraint")

# --- Ontology ---

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.holding_cost = model.Property(f"{Site} has holding cost {Float:holding_cost}")
Site.demand = model.Property(f"{Site} has demand {Integer:demand}")

Route = model.Concept("Route", identify_by={"id": Integer})
Route.capacity = model.Property(f"{Route} has capacity {Integer:capacity}")
Route.origin = model.Relationship(f"{Route} originates at {Site}")
Route.destination = model.Relationship(f"{Route} delivers to {Site}")

# --- Inline data ---

site_data = model.data(
    [
        {"id": 1, "name": "Hub-West", "holding_cost": 2.0, "demand": 80},
        {"id": 2, "name": "Hub-Central", "holding_cost": 3.0, "demand": 120},
        {"id": 3, "name": "Hub-East", "holding_cost": 2.5, "demand": 100},
        {"id": 4, "name": "Depot-NW", "holding_cost": 4.0, "demand": 40},
        {"id": 5, "name": "Depot-SW", "holding_cost": 3.5, "demand": 60},
        {"id": 6, "name": "Depot-NE", "holding_cost": 4.5, "demand": 50},
        {"id": 7, "name": "Depot-SE", "holding_cost": 3.0, "demand": 70},
    ]
)
model.define(Site.new(site_data.to_schema()))

route_data = model.data(
    [
        {"id": 1, "origin_id": 1, "dest_id": 2, "capacity": 200},
        {"id": 2, "origin_id": 2, "dest_id": 3, "capacity": 180},
        {"id": 3, "origin_id": 1, "dest_id": 4, "capacity": 100},
        {"id": 4, "origin_id": 1, "dest_id": 5, "capacity": 120},
        {"id": 5, "origin_id": 2, "dest_id": 4, "capacity": 90},
        {"id": 6, "origin_id": 2, "dest_id": 6, "capacity": 110},
        {"id": 7, "origin_id": 3, "dest_id": 6, "capacity": 80},
        {"id": 8, "origin_id": 3, "dest_id": 7, "capacity": 150},
        {"id": 9, "origin_id": 5, "dest_id": 7, "capacity": 70},
    ]
)
model.define(
    Route.new(
        id=route_data.id,
        capacity=route_data.capacity,
        origin=Site.filter_by(id=route_data.origin_id),
        destination=Site.filter_by(id=route_data.dest_id),
    )
)

# =============================================================================
# Stage 1: Graph reasoner -- eigenvector centrality
# =============================================================================

graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

r = Route.ref()
s1, s2 = Site.ref(), Site.ref()
model.where(r.origin(s1), r.destination(s2)).define(graph.Edge.new(src=s1, dst=s2, weight=r.capacity))

# Centrality is stored directly on Site (because node_concept=Site).
Site.centrality = graph.eigenvector_centrality()

# =============================================================================
# Stage 2: Prescriptive -- inventory allocation with centrality constraint
# =============================================================================
# Allocate inventory across sites minimizing holding cost. Graph centrality
# enforces a CONSTRAINT: critical hubs must receive at least
# centrality * MIN_CENTRALITY_FACTOR units.

TOTAL_BUDGET = 800
MIN_CENTRALITY_FACTOR = 150  # minimum allocation = centrality * this factor

Site.x_alloc = model.Property(f"{Site} has allocation {Float:x}")

problem = Problem(model, Float)
problem.solve_for(Site.x_alloc, lower=0, name=["alloc", Site.name])

# Constraint: total allocation within budget
problem.satisfy(model.require(sum(Site.x_alloc) <= TOTAL_BUDGET))

# Constraint: meet demand at each site
problem.satisfy(model.require(Site.x_alloc >= Site.demand))

# Constraint (from graph): critical hubs get minimum proportional to centrality.
# This is the key pattern -- centrality drives a hard lower bound, not a soft
# objective weight. High-centrality sites MUST carry proportional inventory.
problem.satisfy(model.require(Site.x_alloc >= Site.centrality * MIN_CENTRALITY_FACTOR))

# Objective: minimize total holding cost
problem.minimize(sum(Site.x_alloc * Site.holding_cost))

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Objective: {si.objective_value:.2f}")

# --- Results ---
model.select(
    Site.name.alias("site"),
    Site.centrality.alias("centrality"),
    Site.demand.alias("demand"),
    Site.x_alloc.alias("allocated"),
    Site.holding_cost.alias("unit_cost"),
).where(Site.x_alloc > 0.001).inspect()
