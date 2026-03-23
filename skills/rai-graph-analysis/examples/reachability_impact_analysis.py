# Pattern: Reachability analysis on a directed supply chain graph.
# Key ideas: edge_concept for directed unweighted graph; reachable(full=True) for
# all-pairs reachability; pandas post-processing for upstream/downstream filtering.

from relationalai.semantics import Integer, Model, String, where, define, data
from relationalai.semantics.reasoners.graph import Graph

model = Model("reachability_supply_chain")

# --- Ontology ---

Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has name {String:name}")
Facility.facility_type = model.Property(f"{Facility} has type {String:facility_type}")

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

# --- Validate graph ---

graph.num_nodes().inspect()
graph.num_edges().inspect()

# --- Full reachability (all pairs) ---

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

# --- Filter to downstream from Steel Mill ---

steel_mill_id = 3
downstream = all_reachable_df[all_reachable_df["from_id"] == steel_mill_id]
# Exclude self-reachability
downstream = downstream[downstream["to_id"] != steel_mill_id]
print(f"\nDownstream impact of Steel Mill disruption:")
print(f"  {len(downstream)} facilities affected")
if len(downstream) > 0:
    print(downstream[["to_id", "to_name"]].to_string(index=False))

# --- Filter to upstream of Steel Mill ---

upstream = all_reachable_df[all_reachable_df["to_id"] == steel_mill_id]
upstream = upstream[upstream["from_id"] != steel_mill_id]
print(f"\nUpstream dependencies of Steel Mill:")
print(f"  {len(upstream)} supplier facilities")
if len(upstream) > 0:
    print(upstream[["from_id", "from_name"]].to_string(index=False))

# --- Per-facility downstream reach count (excluding self) ---

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
