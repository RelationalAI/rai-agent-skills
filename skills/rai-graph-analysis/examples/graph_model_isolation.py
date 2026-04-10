# Pattern: Separate Model() for graph analysis to avoid SDK UnsupportedRecursionError.
# NOTE: Fixed in SDK >= 1.0.13 — this pattern remains valid for defensive isolation.
# Key ideas: graph algorithms create recursive definitions internally; when combined
# with prescriptive post-solve queries (Variable.values() or model.select()) on the
# same model, older SDK versions raise UnsupportedRecursionError. The workaround: run
# graph on a dedicated graph_model = Model("graph_stage"), extract results to a
# DataFrame, then load them back into the main model via model.data() + model.define().
# The main model can then use graph-enriched properties in prescriptive or rules
# stages without conflict.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.reasoners.prescriptive import Problem

# =============================================================================
# Main model -- will hold all concepts and the prescriptive stage
# =============================================================================

model = Model("main_model")

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.operating_cost = model.Property(f"{Site} has operating cost {Float:operating_cost}")

Connection = model.Concept("Connection", identify_by={"id": Integer})
Connection.bandwidth = model.Property(f"{Connection} has bandwidth {Integer:bandwidth}")
Connection.origin = model.Relationship(f"{Connection} originates at {Site}")
Connection.destination = model.Relationship(f"{Connection} delivers to {Site}")

# --- Inline data ---

sites = [
    {"id": 1, "name": "Atlanta", "operating_cost": 10.0},
    {"id": 2, "name": "Boston", "operating_cost": 14.0},
    {"id": 3, "name": "Chicago", "operating_cost": 12.0},
    {"id": 4, "name": "Denver", "operating_cost": 9.0},
    {"id": 5, "name": "El Paso", "operating_cost": 8.0},
    {"id": 6, "name": "Fresno", "operating_cost": 11.0},
]

connections = [
    {"id": 1, "origin_id": 1, "dest_id": 2, "bandwidth": 100},
    {"id": 2, "origin_id": 1, "dest_id": 3, "bandwidth": 150},
    {"id": 3, "origin_id": 2, "dest_id": 3, "bandwidth": 120},
    {"id": 4, "origin_id": 3, "dest_id": 4, "bandwidth": 200},
    {"id": 5, "origin_id": 4, "dest_id": 5, "bandwidth": 80},
    {"id": 6, "origin_id": 4, "dest_id": 6, "bandwidth": 90},
    {"id": 7, "origin_id": 5, "dest_id": 6, "bandwidth": 110},
]

site_data = model.data(sites)
model.define(Site.new(site_data.to_schema()))

conn_data = model.data(connections)
model.define(
    Connection.new(
        id=conn_data.id,
        bandwidth=conn_data.bandwidth,
        origin=Site.filter_by(id=conn_data.origin_id),
        destination=Site.filter_by(id=conn_data.dest_id),
    )
)

# =============================================================================
# Stage 1: Graph analysis on a SEPARATE model
# =============================================================================
# WHY: The graph reasoner creates recursive internal definitions. If graph and
# prescriptive share the same Model, post-solve queries (Variable.values() or
# model.select()) trigger UnsupportedRecursionError. Using a dedicated graph_model
# avoids this.

graph_model = Model("graph_stage")

GSite = graph_model.Concept("Site", identify_by={"id": Integer})
GSite.name = graph_model.Property(f"{GSite} has name {String:name}")
graph_model.define(GSite.new(graph_model.data(sites).to_schema()))

# Build edges from connections (pre-compute in the graph model).
graph = Graph(graph_model, directed=False, weighted=True, node_concept=GSite, aggregator="sum")

edge_data = graph_model.data(connections)
gs1, gs2 = GSite.ref(), GSite.ref()
graph_model.where(
    gs1.id == edge_data["origin_id"],
    gs2.id == edge_data["dest_id"],
).define(graph.Edge.new(src=gs1, dst=gs2, weight=edge_data["bandwidth"]))

# Compute eigenvector centrality on graph_model.
GSite.centrality = graph.eigenvector_centrality()

# Extract results to a DataFrame.
centrality_df = graph_model.select(
    GSite.id.alias("id"),
    GSite.name.alias("name"),
    GSite.centrality.alias("centrality"),
).to_df()

print("=== Graph Centrality (from isolated graph_model) ===")
print(centrality_df.sort_values("centrality", ascending=False).to_string(index=False))

# =============================================================================
# Transfer results back to main model
# =============================================================================
# Load centrality scores as data on the main model and define as a Site property.

Site.centrality = model.Property(f"{Site} has centrality {Float:centrality}")
cent_data = model.data(centrality_df[["id", "centrality"]])
model.where(Site.id == cent_data["id"]).define(Site.centrality(cent_data["centrality"]))

# =============================================================================
# Stage 2: Prescriptive on the main model (safe -- no graph recursion here)
# =============================================================================

BUDGET = 300.0

Site.x_invest = model.Property(f"{Site} investment is {Float:x}")

problem = Problem(model, Float)
x_invest_var = problem.solve_for(Site.x_invest, lower=0, name=["invest", Site.name])

problem.satisfy(model.require(sum(Site.x_invest) <= BUDGET))
problem.satisfy(model.require(Site.x_invest <= 10 * Site.operating_cost))

# Objective: maximize centrality-weighted investment
problem.maximize(sum(Site.x_invest * Site.centrality))

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"\nStatus: {si.termination_status}, Objective: {si.objective_value:.4f}")

# --- Results (safe to call on main model -- no graph recursion) ---
model.select(
    Site.name.alias("site"),
    Site.centrality.alias("centrality"),
    Site.x_invest.alias("investment"),
    Site.operating_cost.alias("op_cost"),
).where(Site.x_invest > 0.001).inspect()
