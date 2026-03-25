# Pattern: Reachability analysis on a directed supply chain graph.
# Key ideas: edge_concept for directed unweighted graph; four reachability modes:
#   1. reachable(full=True) — all-pairs reachability
#   2. reachable(to=target) — upstream: who can reach the target?
#   3. reachable(from_=target) — downstream: who does the target reach?
#   4. reachable + ontology join — downstream reach enriched with non-graph relationships
# Target filtering via model.Relationship + define (hero-journey Q5/Q6 pattern).

from relationalai.semantics import Integer, Model, String, where, define, data, distinct
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

# SupplyLink as edge concept (proven pattern from official templates)
SupplyLink = model.Concept(
    "SupplyLink",
    identify_by={"from_facility": Facility, "to_facility": Facility},
)

# --- Sample data: directed supply chain ---
# Raw material suppliers -> processors -> assemblers -> distributors

facility_data = data([
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
define(Facility.new(facility_data.to_schema()))

product_data = data([
    {"id": 1, "name": "Engine Block", "quantity": 500, "facility_id": 5},
    {"id": 2, "name": "Steel Frame",  "quantity": 300, "facility_id": 6},
    {"id": 3, "name": "Vehicle",      "quantity": 200, "facility_id": 7},
    {"id": 4, "name": "Bumper Kit",   "quantity": 150, "facility_id": 6},
])
define(
    Product.new(
        id=product_data.id,
        name=product_data.name,
        quantity=product_data.quantity,
        facility=Facility.filter_by(id=product_data.facility_id),
    )
)

link_data = data([
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
define(
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
    where(reachable(src, dst))
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
# Define a target relationship, then query who can reach it.

target_dc = model.Relationship(f"Target DC: {Facility}")
define(target_dc(Facility)).where(Facility.name == "East Coast DC")

reachable_to = graph.reachable(to=target_dc)

upstream_node = graph.Node.ref()
upstream_df = (
    where(
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
define(target_mill(Facility)).where(Facility.name == "Steel Mill")

reachable_from = graph.reachable(from_=target_mill)

downstream_node = graph.Node.ref()
downstream_df = (
    where(reachable_from(target_mill, downstream_node))
    .select(distinct(
        downstream_node.name.alias("affected_facility"),
        downstream_node.facility_type.alias("type"),
    ))
    .to_df()
)
# Exclude the target itself
downstream_df = downstream_df[downstream_df["affected_facility"] != "Steel Mill"]

print(f"\nDownstream impact if Steel Mill goes offline:")
print(f"  {len(downstream_df)} facilities affected")
print(downstream_df.to_string(index=False))

# --- Per-facility downstream reach count ---

non_self = all_reachable_df[all_reachable_df["from_id"] != all_reachable_df["to_id"]]
if len(non_self) > 0:
    reach_counts = (
        non_self.groupby(["from_id", "from_name"])
        .size()
        .reset_index(name="downstream_reach")
        .sort_values("downstream_reach", ascending=False)
    )
    print("\nDownstream Reach per Facility")
    print(reach_counts.to_string(index=False))

# --- Mode 4: Graph results joined with non-graph ontology relationships ---
# "If Steel Mill goes offline, which products (and how many units) are at risk?"
# Combines downstream reachability with Product data in a single query.
# Key pattern: where() clause mixes graph result (reachable_from) with ontology
# relationship (Product.facility) to enrich graph output with domain context.

downstream = graph.Node.ref()
impact_df = (
    where(
        reachable_from(target_mill, downstream),
        Product.facility(downstream),          # join: reachable facility has products
    )
    .select(distinct(
        downstream.name.alias("facility"),
        downstream.facility_type.alias("type"),
        Product.name.alias("product_at_risk"),
        aggs.sum(Product.quantity).per(downstream, Product).alias("units_at_risk"),
    ))
    .to_df()
)
# Exclude the target itself
impact_df = impact_df[impact_df["facility"] != "Steel Mill"]

print(f"\nProduct impact if Steel Mill goes offline:")
if impact_df.empty:
    print("  No product impact found.")
else:
    for facility in sorted(impact_df["facility"].unique()):
        fac_df = impact_df[impact_df["facility"] == facility]
        fac_type = fac_df["type"].iloc[0]
        print(f"\n  {facility} ({fac_type}):")
        for _, row in fac_df.iterrows():
            print(f"    - {row['product_at_risk']}: {int(row['units_at_risk']):,} units at risk")
