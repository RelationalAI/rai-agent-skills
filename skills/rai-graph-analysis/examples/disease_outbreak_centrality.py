# Pattern: Directed weighted graph with edge_concept for disease outbreak network.
# Key ideas: edge_concept from FacilityConnection with computed risk_weight;
# degree_centrality + indegree/outdegree for prioritizing facilities;
# Int128Array casting for integer results.
# Based on: RelationalAI/templates/v1/disease-outbreak-prevention

from relationalai.semantics import Model, String, Integer, Float
from relationalai.semantics.reasoners.graph import Graph

model = Model("disease_outbreak_prevention")

# --- Ontology ---

Facility = model.Concept("Facility", identify_by={"id": Integer})
Facility.name = model.Property(f"{Facility} has {String:name}")
Facility.facility_type = model.Property(f"{Facility} has {String:facility_type}")
Facility.region = model.Property(f"{Facility} has {String:region}")

FacilityConnection = model.Concept(
    "FacilityConnection",
    identify_by={"from_facility": Facility, "to_facility": Facility},
)
FacilityConnection.transfer_volume = model.Property(f"{FacilityConnection} has {Float:transfer_volume}")
FacilityConnection.contact_intensity = model.Property(f"{FacilityConnection} has {Float:contact_intensity}")
FacilityConnection.risk_weight = model.Property(f"{FacilityConnection} has {Float:risk_weight}")

# --- Sample data ---

facility_data = model.data([
    {"id": 1, "name": "Central Hospital", "facility_type": "hospital", "region": "North"},
    {"id": 2, "name": "Community Clinic A", "facility_type": "clinic", "region": "North"},
    {"id": 3, "name": "Testing Center", "facility_type": "testing", "region": "East"},
    {"id": 4, "name": "Emergency Ward", "facility_type": "hospital", "region": "South"},
    {"id": 5, "name": "Community Clinic B", "facility_type": "clinic", "region": "West"},
])
model.define(Facility.new(facility_data.to_schema()))

conn_data = model.data([
    {"from_id": 1, "to_id": 2, "transfer_volume": 50.0, "contact_intensity": 0.8},
    {"from_id": 1, "to_id": 3, "transfer_volume": 30.0, "contact_intensity": 0.6},
    {"from_id": 2, "to_id": 4, "transfer_volume": 20.0, "contact_intensity": 0.9},
    {"from_id": 3, "to_id": 4, "transfer_volume": 40.0, "contact_intensity": 0.7},
    {"from_id": 4, "to_id": 5, "transfer_volume": 25.0, "contact_intensity": 0.5},
    {"from_id": 2, "to_id": 1, "transfer_volume": 15.0, "contact_intensity": 0.4},
])
f_from, f_to = Facility.ref("from_facility"), Facility.ref("to_facility")
model.define(
    FacilityConnection.new(
        from_facility=f_from.filter_by(id=conn_data.from_id),
        to_facility=f_to.filter_by(id=conn_data.to_id),
        transfer_volume=conn_data.transfer_volume,
        contact_intensity=conn_data.contact_intensity,
    )
)

# Computed edge weight: risk = transfer_volume * contact_intensity
model.define(
    FacilityConnection.risk_weight(
        FacilityConnection.transfer_volume * FacilityConnection.contact_intensity
    )
)

# --- Graph construction: directed weighted with edge_concept ---

graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=Facility,
    edge_concept=FacilityConnection,
    edge_src_relationship=FacilityConnection.from_facility,
    edge_dst_relationship=FacilityConnection.to_facility,
    edge_weight_relationship=FacilityConnection.risk_weight,
)

# --- Run algorithms ---

degree_centrality = graph.degree_centrality()
incoming_edges = graph.indegree()
outgoing_edges = graph.outdegree()

# --- Query results ---

from relationalai.semantics import where

facility = graph.Node.ref("facility")
centr_score = Float.ref("centr_score")
in_edges = Integer.ref("in_edges")
out_edges = Integer.ref("out_edges")

results = (
    where(
        degree_centrality(facility, centr_score),
        incoming_edges(facility, in_edges),
        outgoing_edges(facility, out_edges),
    )
    .select(
        facility.id,
        facility.name,
        facility.facility_type,
        facility.region,
        centr_score.alias("degree_centrality"),
        in_edges.alias("incoming"),
        out_edges.alias("outgoing"),
    )
    .to_df()
)

results["incoming"] = results["incoming"].astype(int)
results["outgoing"] = results["outgoing"].astype(int)
results = results.sort_values("degree_centrality", ascending=False)

print("Facility Centrality Rankings (Disease Outbreak Network)")
print(results.to_string(index=False))
