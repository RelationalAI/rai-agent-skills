# Pattern: multi-relationship sequence -- a route that alternates between two
# DIFFERENT relationships (two distinct edge types between the same node type),
# passed as separate edge arguments to model.path(). Key idea:
# path(a.rel_a, b.rel_b).all_paths() -- consecutive edges share the node between
# them; p.relationships[idx] reads the edge label (which relationship) at each hop.
# This is the >=1.15 replacement for the old "fold it into one composite edge"
# workaround. Requires relationalai>=1.15 (paths is PREVIEW / pre-GA).

from relationalai.semantics import Integer, Model, String

model = Model("paths_multi_relationship_sequence")

# --- Ontology: one node type with two distinct edge types between nodes ---
Node = model.Concept("Node", identify_by={"id": Integer})
Node.name = model.Property(f"{Node} has name {String:name}")
Node.rel_a = model.Relationship(f"{Node} rel_a to {Node}", short_name="rel_a")
Node.rel_b = model.Relationship(f"{Node} rel_b to {Node}", short_name="rel_b")

# --- Sample data ---
nodes = model.data([
    {"id": 1, "name": "A"},
    {"id": 2, "name": "B"},
    {"id": 3, "name": "C"},
    {"id": 4, "name": "D"},
])
model.define(Node.new(id=nodes.id, name=nodes.name))

a_edges = model.data([{"src": 1, "dst": 2}, {"src": 2, "dst": 3}])   # A->B, B->C
b_edges = model.data([{"src": 2, "dst": 4}, {"src": 3, "dst": 4}])   # B->D, C->D
model.define(Node.lookup(id=a_edges.src).rel_a(Node.lookup(id=a_edges.dst)))
model.define(Node.lookup(id=b_edges.src).rel_b(Node.lookup(id=b_edges.dst)))

# --- Routes: one rel_a hop THEN one rel_b hop (distinct edges in series) ---
a, b = Node.ref(), Node.ref()
seq = model.path(a.rel_a, b.rel_b).all_paths()

# Node sequence per route.
nodes_df = model.where(seq).select(
    seq.alias("path"),
    seq.nodes["index"].alias("step"),
    Node(seq.nodes).name.alias("node"),
).to_df()

# Edge label at each hop: p.relationships gives which relationship (rel_a / rel_b)
# was traversed, so each hop of the route can be annotated by its edge type.
edges_df = model.where(seq).select(
    seq.alias("path"),
    seq.relationships["index"].alias("hop"),
    seq.relationships["relationship"].alias("edge_type"),
).to_df()

# --- Reassemble each route, annotating each hop with the edge type it used ---
nodes_df["step"] = nodes_df["step"].astype(int)
nodes_df = nodes_df.drop_duplicates(["path", "step"]).sort_values(["path", "step"])
edges_df["hop"] = edges_df["hop"].astype(int)
edges_df = edges_df.drop_duplicates(["path", "hop"]).sort_values(["path", "hop"])


def edge_type_label(raw):
    # On >=1.15 the per-hop label is decorated, e.g. "-⟨rel_a⟩→"; strip to the
    # stem. (An upcoming release returns the bare name, making this a no-op.)
    return raw.strip("-<>⟨⟩→ ")


routes = []
for path_id, g in nodes_df.groupby("path"):
    names = list(g.sort_values("step")["node"])
    types = [edge_type_label(t) for t in
             edges_df[edges_df["path"] == path_id].sort_values("hop")["edge_type"]]
    label = names[0]
    for name, etype in zip(names[1:], types):
        label += f"  --[{etype}]-->  {name}"
    routes.append(label)

print(f"{len(routes)} rel_a-then-rel_b routes (edge type per hop via p.relationships):")
for r in sorted(routes):
    print(f"  {r}")
