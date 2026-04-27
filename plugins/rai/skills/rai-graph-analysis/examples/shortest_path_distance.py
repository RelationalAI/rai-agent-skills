# Pattern: Shortest path distances on a weighted directed network.
# Key ideas: directed weighted graph from intermediary concept (Route);
# distance() for pairwise shortest paths;
# filter distances to specific source/target pairs.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph

model = Model("shortest_path_distance")

# --- Ontology ---

City = model.Concept("City", identify_by={"id": Integer})
City.name = model.Property(f"{City} has name {String:name}")
City.region = model.Property(f"{City} has region {String:region}")

Route = model.Concept("Route", identify_by={"id": Integer})
Route.origin = model.Relationship(f"{Route} departs from {City}")
Route.destination = model.Relationship(f"{Route} arrives at {City}")
Route.cost = model.Property(f"{Route} has cost {Float:cost}")

# --- Sample data ---

city_data = model.data([
    {"id": 1, "name": "Seattle", "region": "west"},
    {"id": 2, "name": "Portland", "region": "west"},
    {"id": 3, "name": "Denver", "region": "central"},
    {"id": 4, "name": "Dallas", "region": "central"},
    {"id": 5, "name": "Chicago", "region": "central"},
    {"id": 6, "name": "Atlanta", "region": "east"},
    {"id": 7, "name": "New York", "region": "east"},
])
model.define(City.new(city_data.to_schema()))

route_data = model.data([
    {"id": 1, "orig_id": 1, "dest_id": 2, "cost": 3.0},   # Seattle -> Portland
    {"id": 2, "orig_id": 1, "dest_id": 3, "cost": 12.0},  # Seattle -> Denver
    {"id": 3, "orig_id": 2, "dest_id": 3, "cost": 10.0},  # Portland -> Denver
    {"id": 4, "orig_id": 3, "dest_id": 4, "cost": 7.0},   # Denver -> Dallas
    {"id": 5, "orig_id": 3, "dest_id": 5, "cost": 9.0},   # Denver -> Chicago
    {"id": 6, "orig_id": 4, "dest_id": 6, "cost": 8.0},   # Dallas -> Atlanta
    {"id": 7, "orig_id": 5, "dest_id": 7, "cost": 6.0},   # Chicago -> New York
    {"id": 8, "orig_id": 6, "dest_id": 7, "cost": 5.0},   # Atlanta -> New York
    {"id": 9, "orig_id": 4, "dest_id": 5, "cost": 4.0},   # Dallas -> Chicago
])
model.define(
    Route.new(
        id=route_data.id,
        cost=route_data.cost,
        origin=City.filter_by(id=route_data.orig_id),
        destination=City.filter_by(id=route_data.dest_id),
    )
)

# --- Graph construction: directed weighted via edge_concept ---

graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=City,
    edge_concept=Route,
    edge_src_relationship=Route.origin,
    edge_dst_relationship=Route.destination,
    edge_weight_relationship=Route.cost,
)

# --- Run distance() for all-pairs shortest paths ---

src, dst, length = graph.Node.ref("s"), graph.Node.ref("d"), Float.ref("len")
dist_df = (
    model.where(graph.distance(full=True)(src, dst, length))
    .select(
        src.name.alias("from_city"),
        dst.name.alias("to_city"),
        length.alias("distance"),
    )
    .to_df()
    .sort_values("distance", ascending=True)
    .reset_index(drop=True)
)

print("All-Pairs Shortest Path Distances")
print(dist_df.to_string(index=False))

# --- Filter to paths from Seattle ---

seattle_paths = dist_df[dist_df["from_city"] == "Seattle"].sort_values("distance")
print("\nShortest paths from Seattle:")
print(seattle_paths.to_string(index=False))

# Note: diameter_range() requires undirected, unweighted graphs — see
# algorithm-selection.md § diameter_range() for the compatibility constraint.
