# Pattern: Chained reasoner -- graph centrality enrichment feeding prescriptive optimization
# Key ideas: graph reasoner writes centrality as a property on the node concept; prescriptive
# reasoner references that property directly in its objective -- no manual data transfer;
# the ontology carries enrichment forward across reasoning stages.
#
# Requires PyRel SDK >= 1.0.13 — graph and prescriptive run on the same Model here.
# On older SDKs, this combination raises UnsupportedRecursionError; use the legacy
# separate-model workaround in rai-graph-analysis/examples/graph_model_isolation.py.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("chained_graph_prescriptive")

# --- Ontology ---

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.operating_cost = model.Property(f"{Site} has operating cost {Float:operating_cost}")

Route = model.Concept("Route", identify_by={"id": Integer})
Route.volume = model.Property(f"{Route} has volume {Integer:volume}")
Route.origin = model.Relationship(f"{Route} originates at {Site}")
Route.destination = model.Relationship(f"{Route} delivers to {Site}")

# --- Inline data ---

site_data = model.data(
    [
        {"id": 1, "name": "Portland", "operating_cost": 12.0},
        {"id": 2, "name": "Seattle", "operating_cost": 15.0},
        {"id": 3, "name": "Denver", "operating_cost": 10.0},
        {"id": 4, "name": "Phoenix", "operating_cost": 8.0},
        {"id": 5, "name": "LA", "operating_cost": 18.0},
        {"id": 6, "name": "SLC", "operating_cost": 9.0},
        {"id": 7, "name": "Dallas", "operating_cost": 11.0},
    ]
)
model.define(Site.new(site_data.to_schema()))

route_data = model.data(
    [
        {"id": 1, "origin_id": 1, "dest_id": 2, "volume": 150},
        {"id": 2, "origin_id": 1, "dest_id": 3, "volume": 200},
        {"id": 3, "origin_id": 2, "dest_id": 3, "volume": 120},
        {"id": 4, "origin_id": 3, "dest_id": 4, "volume": 180},
        {"id": 5, "origin_id": 3, "dest_id": 5, "volume": 250},
        {"id": 6, "origin_id": 4, "dest_id": 7, "volume": 90},
        {"id": 7, "origin_id": 5, "dest_id": 7, "volume": 160},
        {"id": 8, "origin_id": 6, "dest_id": 3, "volume": 100},
        {"id": 9, "origin_id": 6, "dest_id": 4, "volume": 70},
        {"id": 10, "origin_id": 2, "dest_id": 6, "volume": 80},
    ]
)
model.define(
    Route.new(
        id=route_data.id,
        volume=route_data.volume,
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
model.where(r.origin(s1), r.destination(s2)).define(graph.Edge.new(src=s1, dst=s2, weight=r.volume))

# Centrality is stored directly on Site (because node_concept=Site).
Site.centrality = graph.eigenvector_centrality()

# =============================================================================
# Stage 2: Prescriptive reasoner -- budget allocation weighted by centrality
# =============================================================================
# Allocate an investment budget across sites. The objective maximizes the
# centrality-weighted allocation: high-centrality sites yield more network
# value per dollar invested.

Site.x_invest = model.Property(f"{Site} investment is {Float:x}")

problem = Problem(model, Float)
x_invest_var = problem.solve_for(Site.x_invest, lower=0, name=["invest", Site.name])

# Total budget constraint
budget = 500.0
problem.satisfy(model.require(sum(Site.x_invest) <= budget))

# Per-site cap: investment cannot exceed 10x the operating cost
problem.satisfy(model.require(Site.x_invest <= 10 * Site.operating_cost))

# Objective: maximize centrality-weighted investment
problem.maximize(sum(Site.x_invest * Site.centrality))

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Objective: {si.objective_value:.4f}")

# --- Results ---
model.select(
    Site.name.alias("site"),
    Site.centrality.alias("centrality"),
    Site.x_invest.alias("investment"),
    Site.operating_cost.alias("op_cost"),
).where(Site.x_invest > 0.001).inspect()
