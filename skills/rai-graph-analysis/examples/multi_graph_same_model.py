# Pattern: multiple graph views on the same model — weighted and unweighted
# Key ideas: The same node concept can back multiple Graph instances with different
# configurations. Use weighted for eigenvector centrality (influence scales with edge
# weight), unweighted for betweenness centrality (which does not support weighted graphs).
# Each graph needs its own Edge definitions with fresh .ref() variables.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates, floats

model = Model("multi_graph_same_model")

# --- Ontology (inline) ---
Node = model.Concept("Node", identify_by={"id": String})
Node.name = model.Property(f"{Node} has {String:name}")

Link = model.Concept("Link", identify_by={"id": String})
Link.source = model.Relationship(f"{Link} from {Node}")
Link.target = model.Relationship(f"{Link} to {Node}")
Link.weight = model.Property(f"{Link} has {Float:weight}")

data = model.data([
    {"id": "A", "name": "Alpha"}, {"id": "B", "name": "Beta"},
    {"id": "C", "name": "Gamma"}, {"id": "D", "name": "Delta"},
], columns=["id", "name"])
model.define(Node.new(data.to_schema()))

link_data = model.data([
    {"id": "1", "src": "A", "dst": "B", "weight": 10.0},
    {"id": "2", "src": "B", "dst": "C", "weight": 5.0},
    {"id": "3", "src": "C", "dst": "D", "weight": 20.0},
    {"id": "4", "src": "A", "dst": "D", "weight": 1.0},
], columns=["id", "src", "dst", "weight"])
model.define(Link.new(
    id=link_data.id,
    source=Node.filter_by(id=link_data.src),
    target=Node.filter_by(id=link_data.dst),
    weight=link_data.weight,
))

# --- Graph 1: weighted (for eigenvector centrality) ---
w_graph = Graph(model, directed=False, weighted=True, node_concept=Node, aggregator="sum")
lnk1 = Link.ref()
n1, n2 = Node.ref(), Node.ref()
model.where(lnk1.source(n1), lnk1.target(n2)).define(
    w_graph.Edge.new(src=n1, dst=n2, weight=floats.float(lnk1.weight))
)
w_graph.Node.eigenvector = w_graph.eigenvector_centrality()

# --- Graph 2: unweighted (for betweenness centrality — incompatible with weighted) ---
uw_graph = Graph(model, directed=False, weighted=False, node_concept=Node, aggregator="sum")
lnk2 = Link.ref()
m1, m2 = Node.ref(), Node.ref()
model.where(lnk2.source(m1), lnk2.target(m2)).define(
    uw_graph.Edge.new(src=m1, dst=m2)
)
uw_graph.Node.betweenness = uw_graph.betweenness_centrality()

# --- Bind both metrics to the same concept ---
Node.eigenvector_centrality = model.Property(f"{Node} has {Float:eigenvector_centrality}")
Node.betweenness_centrality = model.Property(f"{Node} has {Float:betweenness_centrality}")

model.where(w_graph.Node == Node).define(
    Node.eigenvector_centrality(w_graph.Node.eigenvector)
)
model.where(uw_graph.Node == Node).define(
    Node.betweenness_centrality(uw_graph.Node.betweenness)
)

# Query: combined ranking
df = model.select(
    Node.name.alias("name"),
    Node.eigenvector_centrality.alias("eigenvector"),
    Node.betweenness_centrality.alias("betweenness"),
).to_df().sort_values("eigenvector", ascending=False)
