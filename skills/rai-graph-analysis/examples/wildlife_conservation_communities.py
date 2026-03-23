# Pattern: Louvain community detection on undirected conservation partnership network.
# Key ideas: edge_concept for undirected unweighted graph; louvain() + degree_centrality()
# to find communities and hub organizations; Int128Array casting for community labels.
# Based on: RelationalAI/templates/v1/wildlife-conservation-network

from relationalai.semantics import Model, String, Integer, Float, where
from relationalai.semantics.reasoners.graph import Graph

model = Model("wildlife_conservation")

# --- Ontology ---

Organization = model.Concept("Organization", identify_by={"id": Integer})
Organization.name = model.Property(f"{Organization} has {String:name}")
Organization.org_type = model.Property(f"{Organization} has {String:org_type}")
Organization.region = model.Property(f"{Organization} has {String:region}")
Organization.focus_species = model.Property(f"{Organization} has {String:focus_species}")

Partnership = model.Concept(
    "Partnership",
    identify_by={"org1": Organization, "org2": Organization},
)

# --- Sample data ---

org_data = model.data([
    {"id": 1, "name": "Wildlife Trust", "org_type": "NGO", "region": "Savanna", "focus_species": "Elephant"},
    {"id": 2, "name": "Safari Research", "org_type": "Research", "region": "Savanna", "focus_species": "Elephant"},
    {"id": 3, "name": "Savanna Rangers", "org_type": "Reserve", "region": "Savanna", "focus_species": "Lion"},
    {"id": 4, "name": "Marine Lab", "org_type": "Research", "region": "Coast", "focus_species": "Turtle"},
    {"id": 5, "name": "Ocean Guardians", "org_type": "NGO", "region": "Coast", "focus_species": "Turtle"},
    {"id": 6, "name": "Reef Protectors", "org_type": "Reserve", "region": "Coast", "focus_species": "Coral"},
    {"id": 7, "name": "Vet Services", "org_type": "Veterinary", "region": "Central", "focus_species": "All"},
])
model.define(Organization.new(org_data.to_schema()))

partnership_data = model.data([
    # Savanna cluster
    {"from_id": 1, "to_id": 2},
    {"from_id": 1, "to_id": 3},
    {"from_id": 2, "to_id": 3},
    # Coast cluster
    {"from_id": 4, "to_id": 5},
    {"from_id": 4, "to_id": 6},
    {"from_id": 5, "to_id": 6},
    # Cross-cluster bridges (Vet Services connects both)
    {"from_id": 7, "to_id": 1},
    {"from_id": 7, "to_id": 4},
])
org_from, org_to = Organization.ref("org1"), Organization.ref("org2")
model.define(
    Partnership.new(
        org1=org_from.filter_by(id=partnership_data.from_id),
        org2=org_to.filter_by(id=partnership_data.to_id),
    )
)

# --- Graph construction: undirected unweighted with edge_concept ---

graph = Graph(
    model,
    directed=False,
    weighted=False,
    node_concept=Organization,
    edge_concept=Partnership,
    edge_src_relationship=Partnership.org1,
    edge_dst_relationship=Partnership.org2,
)

# --- Run algorithms ---

louvain_communities = graph.louvain()
degree_centrality = graph.degree_centrality()
degree = graph.degree()

# --- Query results ---

org = graph.Node.ref("org")
community_id = Integer.ref("community_id")
centr_score = Float.ref("centr_score")
partner_count = Integer.ref("partner_count")

results = (
    where(
        louvain_communities(org, community_id),
        degree_centrality(org, centr_score),
        degree(org, partner_count),
    )
    .select(
        org.id,
        org.name,
        org.org_type,
        org.region,
        org.focus_species,
        community_id.alias("community"),
        centr_score.alias("degree_centrality"),
        partner_count.alias("partnerships"),
    )
    .to_df()
)

# Cast Int128Array columns
results["community"] = results["community"].astype(int)
results["partnerships"] = results["partnerships"].astype(int)
results = results.sort_values(["community", "degree_centrality"], ascending=[True, False])

print("Conservation Network — Community Detection (Louvain)")
print(results.to_string(index=False))

# Per-community analysis
for comm_id in sorted(results["community"].unique()):
    community = results[results["community"] == comm_id]
    hub = community.iloc[0]
    print(f"\nCommunity {comm_id}: {len(community)} organizations")
    print(f"  Hub: {hub['name']} (centrality={hub['degree_centrality']:.4f})")
    print(f"  Members: {', '.join(community['name'].tolist())}")
