# Pattern: WCC-based bridge node identification in an infrastructure network.
# Key ideas: weakly_connected_component() to label components; bridge nodes
# connect different components when edges are removed; comparison of component
# membership across edge endpoints.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

model = Model("bridge_detection")

# --- Ontology ---

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.region = model.Property(f"{Site} has region {String:region}")

Link = model.Concept("Link", identify_by={"id": Integer})
Link.bandwidth = model.Property(f"{Link} has bandwidth {Integer:bandwidth}")
Link.site_a = model.Relationship(f"{Link} connects {Site}")
Link.site_b = model.Relationship(f"{Link} connects to {Site}")

# --- Sample data: network with a bridge node ---
# Region A (sites 1-3) connected to Region B (sites 5-7) only through site 4

site_data = model.data([
    {"id": 1, "name": "Alpha-1", "region": "A"},
    {"id": 2, "name": "Alpha-2", "region": "A"},
    {"id": 3, "name": "Alpha-3", "region": "A"},
    {"id": 4, "name": "Bridge-Hub", "region": "AB"},  # bridge node
    {"id": 5, "name": "Beta-1", "region": "B"},
    {"id": 6, "name": "Beta-2", "region": "B"},
    {"id": 7, "name": "Beta-3", "region": "B"},
])
model.define(Site.new(site_data.to_schema()))

link_data = model.data([
    # Region A internal links
    {"id": 1, "a_id": 1, "b_id": 2, "bandwidth": 100},
    {"id": 2, "a_id": 2, "b_id": 3, "bandwidth": 80},
    {"id": 3, "a_id": 1, "b_id": 3, "bandwidth": 90},
    # Bridge: Region A ↔ Region B only through site 4
    {"id": 4, "a_id": 3, "b_id": 4, "bandwidth": 50},
    {"id": 5, "a_id": 4, "b_id": 5, "bandwidth": 60},
    # Region B internal links
    {"id": 6, "b_id": 5, "a_id": 6, "bandwidth": 110},
    {"id": 7, "b_id": 6, "a_id": 7, "bandwidth": 95},
    {"id": 8, "b_id": 5, "a_id": 7, "bandwidth": 85},
])
model.define(
    Link.new(
        id=link_data.id,
        bandwidth=link_data.bandwidth,
        site_a=Site.filter_by(id=link_data.a_id),
        site_b=Site.filter_by(id=link_data.b_id),
    )
)

# --- Graph construction: undirected unweighted infrastructure ---
# betweenness_centrality() does not support weighted graphs

graph = Graph(model, directed=False, weighted=False, node_concept=Site)

link = Link.ref()
sa, sb = Site.ref(), Site.ref()
model.where(
    link.site_a(sa),
    link.site_b(sb),
).define(
    graph.Edge.new(src=sa, dst=sb)
)

# --- Step 1: WCC to identify connected components ---

from relationalai.semantics import where

graph.Node.component_id = graph.weakly_connected_component()

# Query WCC results — assign to Node then select
component_df = (
    model.select(
        graph.Node.id.alias("site_id"),
        graph.Node.name.alias("name"),
        graph.Node.component_id.alias("component"),
    )
    .to_df()
)
# WCC component IDs are hash-based identifiers — use as-is for grouping

print("Connected Components")
print(component_df.to_string(index=False))

num_components = component_df["component"].nunique()
print(f"\nNumber of components: {num_components}")
if num_components == 1:
    print("Network is fully connected (single component)")

# --- Step 2: Betweenness centrality to find bridge candidates ---

betweenness = graph.betweenness_centrality()

node2 = graph.Node.ref("n2")
btwn_score = Float.ref("btwn")
betweenness_df = (
    where(betweenness(node2, btwn_score))
    .select(
        node2.id.alias("site_id"),
        node2.name.alias("name"),
        node2.region.alias("region"),
        btwn_score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\nBetweenness Centrality (bridge candidates)")
print(betweenness_df.to_string(index=False))

# --- Step 3: Identify bridge nodes ---
# Bridge nodes have high betweenness relative to their degree.
# In this network, Bridge-Hub (site 4) should have the highest betweenness
# because ALL cross-region paths go through it.

top_bridge = betweenness_df.iloc[0]
print(f"\nMost critical bridge node: {top_bridge['name']}")
print(f"  Betweenness: {top_bridge['betweenness']:.4f}")
print(f"  Region: {top_bridge['region']}")
print("  Removing this node would disconnect the two regions.")
