# Pattern: Eigenvector centrality on a supply chain network to identify critical nodes.
# Key ideas: infrastructure-level undirected weighted graph from intermediary concept;
# eigenvector centrality for global importance; binding results to original concept.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates, floats

model = Model("centrality_weighted_undirected")

# --- Ontology ---

Site = model.Concept("Site", identify_by={"id": Integer})
Site.name = model.Property(f"{Site} has name {String:name}")
Site.site_type = model.Property(f"{Site} has type {String:site_type}")
Site.capacity = model.Property(f"{Site} has capacity {Integer:capacity}")

Operation = model.Concept("Operation", identify_by={"id": Integer})
Operation.shipment_count = model.Property(f"{Operation} has shipment count {Integer:shipment_count}")
Operation.source_site = model.Relationship(f"{Operation} originates at {Site}")
Operation.output_site = model.Relationship(f"{Operation} delivers to {Site}")

# --- Sample data ---

site_data = model.data([
    {"id": 1, "name": "Portland Hub", "site_type": "warehouse", "capacity": 5000},
    {"id": 2, "name": "Seattle Plant", "site_type": "factory", "capacity": 3000},
    {"id": 3, "name": "Denver DC", "site_type": "distribution", "capacity": 4000},
    {"id": 4, "name": "Phoenix Depot", "site_type": "warehouse", "capacity": 2000},
    {"id": 5, "name": "LA Terminal", "site_type": "distribution", "capacity": 6000},
    {"id": 6, "name": "SLC Warehouse", "site_type": "warehouse", "capacity": 1500},
    {"id": 7, "name": "Vegas Outlet", "site_type": "distribution", "capacity": 1000},
])
model.define(Site.new(site_data.to_schema()))

op_data = model.data([
    {"id": 1, "source_id": 1, "dest_id": 2, "shipment_count": 150},
    {"id": 2, "source_id": 1, "dest_id": 3, "shipment_count": 200},
    {"id": 3, "source_id": 2, "dest_id": 3, "shipment_count": 100},
    {"id": 4, "source_id": 3, "dest_id": 4, "shipment_count": 180},
    {"id": 5, "source_id": 3, "dest_id": 5, "shipment_count": 250},
    {"id": 6, "source_id": 4, "dest_id": 5, "shipment_count": 90},
    {"id": 7, "source_id": 5, "dest_id": 7, "shipment_count": 120},
    {"id": 8, "source_id": 6, "dest_id": 3, "shipment_count": 70},
    {"id": 9, "source_id": 6, "dest_id": 4, "shipment_count": 50},
])
model.define(
    Operation.new(
        id=op_data.id,
        shipment_count=op_data.shipment_count,
        source_site=Site.filter_by(id=op_data.source_id),
        output_site=Site.filter_by(id=op_data.dest_id),
    )
)

# --- Graph construction: infrastructure-level undirected weighted ---

graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

op = Operation.ref()
site1, site2 = Site.ref(), Site.ref()
model.where(
    op.source_site(site1),
    op.output_site(site2),
).define(
    graph.Edge.new(src=site1, dst=site2, weight=floats.float(op.shipment_count))
)

# --- Run eigenvector centrality and bind to concept ---
# When node_concept=Site, assigning to graph.Node creates the property on Site.
# The property is immediately queryable on Site — no separate model.Property() needed.

graph.Node.centrality_score = graph.eigenvector_centrality()

# --- Extract and display results ---

centrality_df = (
    model.select(
        Site.id.alias("site_id"),
        Site.name.alias("site_name"),
        Site.site_type.alias("type"),
        Site.centrality_score.alias("centrality"),
    )
    .to_df()
    .sort_values("centrality", ascending=False)
    .reset_index(drop=True)
)

print("Site Centrality Rankings (Eigenvector)")
print(centrality_df.to_string(index=False))

# --- Identify top connector ---

top_site = centrality_df.iloc[0]
print(f"\nMost critical node: {top_site['site_name']} (centrality={top_site['centrality']:.4f})")
