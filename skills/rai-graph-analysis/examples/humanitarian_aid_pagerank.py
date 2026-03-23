# Pattern: PageRank + degree centrality on directed weighted supply chain.
# Key ideas: edge_concept with computed flow_weight; combining PageRank (influence)
# with degree centrality (connectivity) for strategic categorization;
# directed=True for supply flow direction.
# Based on: RelationalAI/templates/v1/humanitarian-aid-supply-chain

from relationalai.semantics import Model, String, Integer, Float, where
from relationalai.semantics.reasoners.graph import Graph

model = Model("humanitarian_aid_supply_chain")

# --- Ontology ---

DistributionPoint = model.Concept("DistributionPoint", identify_by={"id": Integer})
DistributionPoint.name = model.Property(f"{DistributionPoint} has {String:name}")
DistributionPoint.point_type = model.Property(f"{DistributionPoint} has {String:point_type}")
DistributionPoint.region = model.Property(f"{DistributionPoint} has {String:region}")
DistributionPoint.capacity = model.Property(f"{DistributionPoint} has {Integer:capacity}")

SupplyRoute = model.Concept(
    "SupplyRoute",
    identify_by={"from_point": DistributionPoint, "to_point": DistributionPoint},
)
SupplyRoute.route_capacity = model.Property(f"{SupplyRoute} has {Integer:route_capacity}")
SupplyRoute.reliability_score = model.Property(f"{SupplyRoute} has {Float:reliability_score}")
SupplyRoute.distance_km = model.Property(f"{SupplyRoute} has {Float:distance_km}")
SupplyRoute.flow_weight = model.Property(f"{SupplyRoute} has {Float:flow_weight}")

# --- Sample data ---

point_data = model.data([
    {"id": 1, "name": "Airport Hub", "point_type": "airport", "region": "North", "capacity": 5000},
    {"id": 2, "name": "Warehouse Alpha", "point_type": "warehouse", "region": "North", "capacity": 3000},
    {"id": 3, "name": "Border Crossing", "point_type": "border", "region": "East", "capacity": 1500},
    {"id": 4, "name": "Relief Camp A", "point_type": "camp", "region": "East", "capacity": 2000},
    {"id": 5, "name": "Relief Camp B", "point_type": "camp", "region": "South", "capacity": 1000},
    {"id": 6, "name": "Regional Depot", "point_type": "warehouse", "region": "South", "capacity": 4000},
])
model.define(DistributionPoint.new(point_data.to_schema()))

route_data = model.data([
    {"from_id": 1, "to_id": 2, "route_capacity": 800, "reliability": 0.95, "distance": 50.0},
    {"from_id": 1, "to_id": 3, "route_capacity": 500, "reliability": 0.80, "distance": 200.0},
    {"from_id": 2, "to_id": 4, "route_capacity": 600, "reliability": 0.90, "distance": 80.0},
    {"from_id": 3, "to_id": 4, "route_capacity": 400, "reliability": 0.70, "distance": 120.0},
    {"from_id": 2, "to_id": 6, "route_capacity": 700, "reliability": 0.85, "distance": 150.0},
    {"from_id": 6, "to_id": 5, "route_capacity": 300, "reliability": 0.75, "distance": 60.0},
    {"from_id": 4, "to_id": 5, "route_capacity": 200, "reliability": 0.65, "distance": 90.0},
])
from_pt, to_pt = DistributionPoint.ref("from_point"), DistributionPoint.ref("to_point")
model.define(
    SupplyRoute.new(
        from_point=from_pt.filter_by(id=route_data.from_id),
        to_point=to_pt.filter_by(id=route_data.to_id),
        route_capacity=route_data.route_capacity,
        reliability_score=route_data.reliability,
        distance_km=route_data.distance,
    )
)

# Computed edge weight: flow = (capacity * reliability) / distance
model.define(
    SupplyRoute.flow_weight(
        (SupplyRoute.route_capacity * SupplyRoute.reliability_score) / SupplyRoute.distance_km
    )
)

# --- Graph construction: directed weighted with edge_concept ---

graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=DistributionPoint,
    edge_concept=SupplyRoute,
    edge_src_relationship=SupplyRoute.from_point,
    edge_dst_relationship=SupplyRoute.to_point,
    edge_weight_relationship=SupplyRoute.flow_weight,
)

# --- Run algorithms ---

pagerank = graph.pagerank()
degree_centrality = graph.degree_centrality()

# --- Query results ---

point = graph.Node.ref("point")
pr_score = Float.ref("pr_score")
dc_score = Float.ref("dc_score")

results = (
    where(
        pagerank(point, pr_score),
        degree_centrality(point, dc_score),
    )
    .select(
        point.id,
        point.name,
        point.point_type,
        point.region,
        point.capacity,
        pr_score.alias("pagerank"),
        dc_score.alias("degree_centrality"),
    )
    .to_df()
)

results = results.sort_values("pagerank", ascending=False).reset_index(drop=True)

print("Distribution Point Rankings (PageRank + Degree Centrality)")
print(results.to_string(index=False))

# Strategic categorization
pr_median = results["pagerank"].median()
dc_median = results["degree_centrality"].median()
print(f"\nHigh influence + high connectivity (critical hubs):")
critical = results[(results["pagerank"] >= pr_median) & (results["degree_centrality"] >= dc_median)]
for _, row in critical.iterrows():
    print(f"  {row['name']} — PR={row['pagerank']:.4f}, DC={row['degree_centrality']:.4f}")
