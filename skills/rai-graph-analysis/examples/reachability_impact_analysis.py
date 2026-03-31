# Pattern: Reachability analysis on a directed graph for dependency and impact tracing.
# Key ideas: edge_concept for directed unweighted graph; four reachability modes
#   (full, upstream to=, downstream from_=, enriched with non-graph relationships);
# betweenness centrality for structural bottlenecks;
# target filtering via model.Relationship + define.
# Merged from: reachability_impact_analysis example + bom-reachability + supplier-impact templates

from relationalai.semantics import Integer, Model, String, Float, distinct
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.reasoners.graph import Graph

model = Model("reachability_supply_chain")

# --- Ontology ---

Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has name {String:name}")
Facility.facility_type = model.Property(f"{Facility} has type {String:facility_type}")

# Product concept — for enriching graph results with non-graph relationships
Product = model.Concept("Product", identify_by={"id": Integer})
Product.name = model.Property(f"{Product} has name {String:name}")
Product.quantity = model.Property(f"{Product} has quantity {Integer:quantity}")
Product.facility = model.Relationship(f"{Product} produced at {Facility}")

# SupplyLink as edge concept
SupplyLink = model.Concept(
    "SupplyLink",
    identify_by={"from_facility": Facility, "to_facility": Facility},
)

# --- Sample data: directed supply chain ---
# Raw material suppliers -> processors -> assemblers -> distributors

facility_data = model.data([
    {"id": 1, "name": "Iron Mine", "facility_type": "raw_material"},
    {"id": 2, "name": "Coal Mine", "facility_type": "raw_material"},
    {"id": 3, "name": "Steel Mill", "facility_type": "processor"},
    {"id": 4, "name": "Plastics Plant", "facility_type": "processor"},
    {"id": 5, "name": "Engine Factory", "facility_type": "assembler"},
    {"id": 6, "name": "Body Shop", "facility_type": "assembler"},
    {"id": 7, "name": "Final Assembly", "facility_type": "assembler"},
    {"id": 8, "name": "East Coast DC", "facility_type": "distributor"},
    {"id": 9, "name": "West Coast DC", "facility_type": "distributor"},
])
model.define(Facility.new(facility_data.to_schema()))

product_data = model.data([
    {"id": 1, "name": "Engine Block", "quantity": 500, "facility_id": 5},
    {"id": 2, "name": "Steel Frame", "quantity": 300, "facility_id": 6},
    {"id": 3, "name": "Vehicle", "quantity": 200, "facility_id": 7},
    {"id": 4, "name": "Bumper Kit", "quantity": 150, "facility_id": 6},
])
model.define(
    Product.new(
        id=product_data.id,
        name=product_data.name,
        quantity=product_data.quantity,
        facility=Facility.filter_by(id=product_data.facility_id),
    )
)

link_data = model.data([
    {"src_id": 1, "dst_id": 3},  # Iron Mine -> Steel Mill
    {"src_id": 2, "dst_id": 3},  # Coal Mine -> Steel Mill
    {"src_id": 3, "dst_id": 5},  # Steel Mill -> Engine Factory
    {"src_id": 3, "dst_id": 6},  # Steel Mill -> Body Shop
    {"src_id": 4, "dst_id": 6},  # Plastics Plant -> Body Shop
    {"src_id": 5, "dst_id": 7},  # Engine Factory -> Final Assembly
    {"src_id": 6, "dst_id": 7},  # Body Shop -> Final Assembly
    {"src_id": 7, "dst_id": 8},  # Final Assembly -> East Coast DC
    {"src_id": 7, "dst_id": 9},  # Final Assembly -> West Coast DC
])
f_from, f_to = Facility.ref("from_facility"), Facility.ref("to_facility")
model.define(
    SupplyLink.new(
        from_facility=f_from.filter_by(id=link_data.src_id),
        to_facility=f_to.filter_by(id=link_data.dst_id),
    )
)

# --- Graph construction: directed unweighted with edge_concept ---

graph = Graph(
    model,
    directed=True,
    weighted=False,
    node_concept=Facility,
    edge_concept=SupplyLink,
    edge_src_relationship=SupplyLink.from_facility,
    edge_dst_relationship=SupplyLink.to_facility,
)

graph.num_nodes().inspect()
graph.num_edges().inspect()

# --- Mode 1: Full reachability (all pairs) ---

reachable = graph.reachable(full=True)

src, dst = graph.Node.ref("s"), graph.Node.ref("d")
all_reachable_df = (
    model.where(reachable(src, dst))
    .select(
        src.id.alias("from_id"),
        src.name.alias("from_name"),
        dst.id.alias("to_id"),
        dst.name.alias("to_name"),
    )
    .to_df()
)

print("All reachable pairs in the supply chain:")
print(all_reachable_df.to_string(index=False))

# --- Mode 2: Parameterized upstream — reachable(to=target) ---
# "Which raw materials does East Coast DC depend on?"

target_dc = model.Relationship(f"Target DC: {Facility}")
model.define(target_dc(Facility)).where(Facility.name == "East Coast DC")

reachable_to = graph.reachable(to=target_dc)

upstream_node = graph.Node.ref()
upstream_df = (
    model.where(
        reachable_to(upstream_node, target_dc),
        upstream_node.facility_type == "raw_material",
    )
    .select(
        upstream_node.name.alias("supplier_name"),
        upstream_node.facility_type.alias("type"),
    )
    .to_df()
)

print(f"\nUpstream raw material suppliers for East Coast DC:")
print(upstream_df.to_string(index=False))

# --- Mode 3: Parameterized downstream — reachable(from_=target) ---
# "If Steel Mill goes offline, what is affected?"

target_mill = model.Relationship(f"Target Mill: {Facility}")
model.define(target_mill(Facility)).where(Facility.name == "Steel Mill")

reachable_from = graph.reachable(from_=target_mill)

downstream_node = graph.Node.ref()
downstream_df = (
    model.where(reachable_from(target_mill, downstream_node))
    .select(distinct(
        downstream_node.name.alias("affected_facility"),
        downstream_node.facility_type.alias("type"),
    ))
    .to_df()
)
downstream_df = downstream_df[downstream_df["affected_facility"] != "Steel Mill"]

print(f"\nDownstream impact if Steel Mill goes offline:")
print(f"  {len(downstream_df)} facilities affected")
print(downstream_df.to_string(index=False))

# --- Mode 4: Graph results enriched with non-graph ontology relationships ---
# "If Steel Mill goes offline, which products (and how many units) are at risk?"
# Combines downstream reachability with Product data in a single query.

downstream = graph.Node.ref()
impact_df = (
    model.where(
        reachable_from(target_mill, downstream),
        Product.facility(downstream),  # join: reachable facility has products
    )
    .select(distinct(
        downstream.name.alias("facility"),
        downstream.facility_type.alias("type"),
        Product.name.alias("product_at_risk"),
        aggs.sum(Product.quantity).per(downstream, Product).alias("units_at_risk"),
    ))
    .to_df()
)
impact_df = impact_df[impact_df["facility"] != "Steel Mill"]

print(f"\nProduct impact if Steel Mill goes offline:")
for facility in sorted(impact_df["facility"].unique()):
    fac_df = impact_df[impact_df["facility"] == facility]
    print(f"\n  {facility} ({fac_df['type'].iloc[0]}):")
    for _, row in fac_df.iterrows():
        print(f"    - {row['product_at_risk']}: {int(row['units_at_risk']):,} units at risk")

# --- Betweenness centrality: structural bottlenecks ---
# Complements reachability — identifies nodes that sit on the most dependency paths.

betweenness = graph.betweenness_centrality()

node = graph.Node.ref("n")
score = Float.ref("s")
btw_df = (
    model.where(betweenness(node, score))
    .select(
        node.name.alias("facility_name"),
        node.facility_type.alias("type"),
        score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Betweenness Centrality (structural bottlenecks) ===")
print(btw_df.to_string(index=False))

bottlenecks = btw_df[btw_df["betweenness"] > 0]
if len(bottlenecks) > 0:
    top = bottlenecks.iloc[0]
    print(f"\nTop bottleneck: {top['facility_name']} (betweenness={top['betweenness']:.4f})")
