# Pattern: Co-occurrence graph with WCC clustering + betweenness for bottleneck detection.
# Key ideas: shared-attribute edge construction with id < guard to prevent duplicates;
# WCC for dependency clusters; betweenness centrality for bottleneck identification;
# hybrid risk assessment combining graph metric with domain attribute.


from relationalai.semantics import Float, Integer, Model, String, where
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates as aggs

model = Model("co_occurrence_wcc_bottleneck")

# --- Ontology ---

Machine = model.Concept("Machine", identify_by={"id": Integer})
Machine.name = model.Property(f"{Machine} has {String:name}")
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}"
)

Technician = model.Concept("Technician", identify_by={"id": Integer})
Technician.name = model.Property(f"{Technician} has {String:name}")

Qualification = model.Concept("Qualification", identify_by={"id": Integer})
Qualification.technician = model.Relationship(f"{Qualification} for {Technician}")
Qualification.machine = model.Relationship(f"{Qualification} covers {Machine}")

# --- Sample data ---

machine_data = model.data([
    {"id": 1, "name": "CNC Mill A", "machine_type": "milling", "facility": "Plant North", "failure_probability": 0.15},
    {"id": 2, "name": "CNC Mill B", "machine_type": "milling", "facility": "Plant North", "failure_probability": 0.45},
    {"id": 3, "name": "Lathe C", "machine_type": "turning", "facility": "Plant North", "failure_probability": 0.10},
    {"id": 4, "name": "Press D", "machine_type": "stamping", "facility": "Plant South", "failure_probability": 0.35},
    {"id": 5, "name": "Welder E", "machine_type": "welding", "facility": "Plant South", "failure_probability": 0.50},
    {"id": 6, "name": "Drill F", "machine_type": "drilling", "facility": "Plant South", "failure_probability": 0.20},
])
model.define(Machine.new(machine_data.to_schema()))

tech_data = model.data([
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 3, "name": "Carol"},
])
model.define(Technician.new(tech_data.to_schema()))

qual_data = model.data([
    # Alice: qualified for machines 1, 2, 3 (connects the milling+turning cluster)
    {"id": 1, "technician_id": 1, "machine_id": 1},
    {"id": 2, "technician_id": 1, "machine_id": 2},
    {"id": 3, "technician_id": 1, "machine_id": 3},
    # Bob: qualified for machines 2, 4 (bridges Plant North and Plant South)
    {"id": 4, "technician_id": 2, "machine_id": 2},
    {"id": 5, "technician_id": 2, "machine_id": 4},
    # Carol: qualified for machines 4, 5, 6 (connects the stamping+welding+drilling cluster)
    {"id": 6, "technician_id": 3, "machine_id": 4},
    {"id": 7, "technician_id": 3, "machine_id": 5},
    {"id": 8, "technician_id": 3, "machine_id": 6},
])
model.define(
    Qualification.new(
        id=qual_data.id,
        technician=Technician.filter_by(id=qual_data.technician_id),
        machine=Machine.filter_by(id=qual_data.machine_id),
    )
)

# --- Graph construction: co-occurrence edges via shared technician ---
# Two machines are connected if the same technician is qualified for both.
# The id < guard prevents self-loops and duplicate edges.

graph = Graph(model, directed=False, weighted=False, node_concept=Machine, aggregator="sum")

m1, m2 = Machine.ref(), Machine.ref()
q1, q2 = Qualification.ref(), Qualification.ref()
tech = Technician.ref()

model.where(
    q1.technician(tech),
    q2.technician(tech),
    q1.machine(m1),
    q2.machine(m2),
    m1.id < m2.id,  # prevent self-loops and duplicate edges
).define(
    graph.Edge.new(src=m1, dst=m2)
)

graph.num_nodes().inspect()
graph.num_edges().inspect()

# --- WCC: dependency clusters ---

graph.Node.component_id = graph.weakly_connected_component()

wcc_df = (
    model.select(
        Machine.id.alias("machine_id"),
        Machine.name.alias("machine_name"),
        Machine.facility.alias("facility"),
        Machine.component_id.alias("component_id"),
    )
    .to_df()
)
print("=== Dependency Clusters ===")
for comp_id in sorted(wcc_df["component_id"].unique()):
    comp_df = wcc_df[wcc_df["component_id"] == comp_id]
    print(f"\n  Cluster (size={len(comp_df)}):")
    for _, row in comp_df.sort_values("machine_name").iterrows():
        print(f"    - {row['machine_name']} ({row['facility']})")

# --- Betweenness centrality: bottleneck machines ---

betweenness = graph.betweenness_centrality()

node_b = graph.Node.ref("nb")
btwn_score = Float.ref("btwn")

betweenness_df = (
    model.where(betweenness(node_b, btwn_score))
    .select(
        node_b.name.alias("machine_name"),
        node_b.facility.alias("facility"),
        node_b.failure_probability.alias("failure_probability"),
        btwn_score.alias("betweenness"),
    )
    .to_df()
    .sort_values("betweenness", ascending=False)
    .reset_index(drop=True)
)

print("\n=== Betweenness Centrality ===")
print(betweenness_df.to_string(index=False))

# --- Hybrid risk: graph bottleneck + domain attribute ---
# Machines that are both dependency bottlenecks AND have high failure risk.

critical = betweenness_df[
    (betweenness_df["betweenness"] > 0) & (betweenness_df["failure_probability"] > 0.3)
]

print("\n=== Critical Machines (high betweenness + high failure probability) ===")
if len(critical) > 0:
    for _, row in critical.iterrows():
        print(f"  {row['machine_name']} ({row['facility']})")
        print(f"    betweenness={row['betweenness']:.4f}, failure_prob={row['failure_probability']:.2f}")
else:
    print("  No machines with both high betweenness and high failure probability.")
