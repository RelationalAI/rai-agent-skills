# Pattern: edge_concept with computed weight on directed graph; PageRank + degree centrality.
# Key ideas: edge_concept derives edges from an existing interaction concept;
# computed edge weight from multiple properties; combining PageRank (global influence)
# with degree centrality (local connectivity) for multi-algorithm classification;
# Int128Array casting for integer results.
# Merged from: humanitarian_aid_pagerank + disease_outbreak_centrality examples

from relationalai.semantics import Model, String, Integer, Float
from relationalai.semantics.reasoners.graph import Graph

model = Model("edge_concept_multi_algorithm")

# --- Ontology ---

Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has {String:name}")
Facility.facility_type = model.Property(f"{Facility} has {String:facility_type}")
Facility.region = model.Property(f"{Facility} has {String:region}")
Facility.capacity = model.Property(f"{Facility} has {Integer:capacity}")

# Connection concept — each instance becomes a graph edge via edge_concept
Connection = model.Concept(
    "Connection",
    identify_by={"from_facility": Facility, "to_facility": Facility},
)
Connection.volume = model.Property(f"{Connection} has {Float:volume}")
Connection.reliability = model.Property(f"{Connection} has {Float:reliability}")
Connection.distance = model.Property(f"{Connection} has {Float:distance}")
Connection.flow_weight = model.Property(f"{Connection} has {Float:flow_weight}")

# --- Sample data ---

facility_data = model.data([
    {"id": 1, "name": "Airport Hub", "facility_type": "hub", "region": "North", "capacity": 5000},
    {"id": 2, "name": "Warehouse Alpha", "facility_type": "warehouse", "region": "North", "capacity": 3000},
    {"id": 3, "name": "Border Crossing", "facility_type": "transit", "region": "East", "capacity": 1500},
    {"id": 4, "name": "Distribution Center A", "facility_type": "distribution", "region": "East", "capacity": 2000},
    {"id": 5, "name": "Distribution Center B", "facility_type": "distribution", "region": "South", "capacity": 1000},
    {"id": 6, "name": "Regional Depot", "facility_type": "warehouse", "region": "South", "capacity": 4000},
])
model.define(Facility.new(facility_data.to_schema()))

conn_data = model.data([
    {"from_id": 1, "to_id": 2, "volume": 800.0, "reliability": 0.95, "distance": 50.0},
    {"from_id": 1, "to_id": 3, "volume": 500.0, "reliability": 0.80, "distance": 200.0},
    {"from_id": 2, "to_id": 4, "volume": 600.0, "reliability": 0.90, "distance": 80.0},
    {"from_id": 3, "to_id": 4, "volume": 400.0, "reliability": 0.70, "distance": 120.0},
    {"from_id": 2, "to_id": 6, "volume": 700.0, "reliability": 0.85, "distance": 150.0},
    {"from_id": 6, "to_id": 5, "volume": 300.0, "reliability": 0.75, "distance": 60.0},
    {"from_id": 4, "to_id": 5, "volume": 200.0, "reliability": 0.65, "distance": 90.0},
])
f_from, f_to = Facility.ref("from_facility"), Facility.ref("to_facility")
model.define(
    Connection.new(
        from_facility=f_from.filter_by(id=conn_data.from_id),
        to_facility=f_to.filter_by(id=conn_data.to_id),
        volume=conn_data.volume,
        reliability=conn_data.reliability,
        distance=conn_data.distance,
    )
)

# Computed edge weight: flow = (volume * reliability) / distance
model.define(
    Connection.flow_weight(
        (Connection.volume * Connection.reliability) / Connection.distance
    )
)

# --- Graph construction: directed weighted with edge_concept ---
# Each Connection instance automatically becomes an edge — no Edge.new() needed.

graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=Facility,
    edge_concept=Connection,
    edge_src_relationship=Connection.from_facility,
    edge_dst_relationship=Connection.to_facility,
    edge_weight_relationship=Connection.flow_weight,
)

# --- Run algorithms ---

pagerank = graph.pagerank()
degree_centrality = graph.degree_centrality()
incoming = graph.indegree()
outgoing = graph.outdegree()

# --- Query results: combine multiple algorithms in one query ---

node = graph.Node.ref("node")
pr_score = Float.ref("pr_score")
dc_score = Float.ref("dc_score")
in_count = Integer.ref("in_count")
out_count = Integer.ref("out_count")

results = (
    model.where(
        pagerank(node, pr_score),
        degree_centrality(node, dc_score),
        incoming(node, in_count),
        outgoing(node, out_count),
    )
    .select(
        node.name,
        node.facility_type,
        node.region,
        pr_score.alias("pagerank"),
        dc_score.alias("degree_centrality"),
        in_count.alias("incoming"),
        out_count.alias("outgoing"),
    )
    .to_df()
)

# Cast Int128Array columns
results["incoming"] = results["incoming"].astype(int)
results["outgoing"] = results["outgoing"].astype(int)
results = results.sort_values("pagerank", ascending=False).reset_index(drop=True)

print("Facility Rankings (PageRank + Degree Centrality)")
print(results.to_string(index=False))

# --- Multi-algorithm classification ---
# Combine PageRank (global influence) with degree centrality (local connectivity)
# to categorize nodes into strategic tiers.

pr_median = results["pagerank"].median()
dc_median = results["degree_centrality"].median()

print(f"\nStrategic classification (PR median={pr_median:.4f}, DC median={dc_median:.4f}):")
critical = results[(results["pagerank"] >= pr_median) & (results["degree_centrality"] >= dc_median)]
for _, row in critical.iterrows():
    print(f"  Critical hub: {row['name']} — PR={row['pagerank']:.4f}, DC={row['degree_centrality']:.4f}")
    print(f"    incoming={row['incoming']}, outgoing={row['outgoing']}")
