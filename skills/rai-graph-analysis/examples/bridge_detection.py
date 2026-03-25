# Pattern: WCC + Bridge concept for identifying critical network connectors.
# Key ideas: weakly_connected_component() for cluster identification;
# extends=[] to define Bridge as a derived subconcept of Site;
# cross-region relationship detection via where() conditions;
# cross-region connection analysis (which regions each bridge links to);
# betweenness_centrality() for structural bottleneck ranking.

from relationalai.semantics import Float, Integer, Model, String, select, distinct, where
from relationalai.semantics.reasoners.graph import Graph

model = Model("bridge_detection")

# --- Ontology ---

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.region = model.Property(f"{Site} has region {String:region}")

Link = model.Concept("Link", identify_by={"id": Integer})
Link.bandwidth = model.Property(f"{Link} has bandwidth {Integer:bandwidth}")
Link.site_a = model.Relationship(f"{Link} connects {Site}")
Link.site_b = model.Relationship(f"{Link} connects to {Site}")

# --- Sample data: network with bridge nodes between regions ---

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
    # Bridge: Region A <-> Region B only through site 4
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

# --- Derived concept: Bridge (extends Site) ---
# A bridge site has links that cross region boundaries.
# Uses extends=[] to make Bridge a subconcept of Site — inherits all Site properties.

site1, site2 = Site.ref(), Site.ref()
link_ref = Link.ref()

Bridge = model.Concept("Bridge", extends=[Site])
model.define(Bridge(site1)).where(
    link_ref.site_a(site1),
    link_ref.site_b(site2),
    site1.region != site2.region,
)

# --- Graph construction: undirected unweighted ---

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
# Uses relation-based query pattern with inline per-component aggregation
# to get membership and component sizes in a single query.

graph.Node.component_id = graph.weakly_connected_component()

component_df = (
    model.select(
        graph.Node.id.alias("site_id"),
        graph.Node.name.alias("name"),
        graph.Node.region.alias("region"),
        graph.Node.component_id.alias("component"),
    )
    .to_df()
)

print("Connected Components")
print(component_df.to_string(index=False))

num_components = component_df["component"].nunique()
print(f"\nNumber of components: {num_components}")
if num_components == 1:
    print("Network is fully connected (single component)")

# --- Step 2: Bridge concept query with connected regions ---
# Query bridges — Bridge extends Site, so all Site properties are available.

bridge_df = (
    select(distinct(
        Bridge.id.alias("bridge_site_id"),
        Bridge.name.alias("bridge_site_name"),
        Bridge.region.alias("bridge_region"),
    ))
    .to_df()
)

# Derive which regions each bridge connects to by joining bridge list with link data.
import pandas as pd
link_df = (
    select(Link.id.alias("link_id"),
           Link.site_a.id.alias("a_id"), Link.site_a.region.alias("a_region"),
           Link.site_b.id.alias("b_id"), Link.site_b.region.alias("b_region"))
    .to_df()
)
bridge_ids = set(bridge_df["bridge_site_id"])
connects_rows = []
for _, lk in link_df.iterrows():
    if lk["a_region"] != lk["b_region"]:
        if lk["a_id"] in bridge_ids:
            connects_rows.append({"bridge_site_id": lk["a_id"], "connects_to": lk["b_region"]})
        if lk["b_id"] in bridge_ids:
            connects_rows.append({"bridge_site_id": lk["b_id"], "connects_to": lk["a_region"]})
connects_df = pd.DataFrame(connects_rows).drop_duplicates() if connects_rows else pd.DataFrame(columns=["bridge_site_id", "connects_to"])

print("\nBridge Sites (cross-region connectors)")
if len(bridge_df) > 0:
    for _, row in bridge_df.sort_values("bridge_site_id").iterrows():
        bid = row["bridge_site_id"]
        regions = connects_df[connects_df["bridge_site_id"] == bid]["connects_to"]
        connects = ", ".join(sorted(regions.unique())) if len(regions) > 0 else "none"
        print(f"  {row['bridge_site_name']} (id={bid}, region={row['bridge_region']}) -> connects to: {connects}")
else:
    print("  No bridge sites found")

# --- Step 3: Betweenness centrality for structural ranking ---

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

print("\nBetweenness Centrality (structural ranking)")
print(betweenness_df.to_string(index=False))

top_bridge = betweenness_df.iloc[0]
print(f"\nMost critical bridge node: {top_bridge['name']}")
print(f"  Betweenness: {top_bridge['betweenness']:.4f}")
print(f"  Region: {top_bridge['region']}")
print("  Removing this node would disconnect the two regions.")
