# Pattern: score/rank routes by a per-node value aggregated ALONG the path, and
# filter routes by per-node / endpoint predicates -- the core paths-only
# operations (reachable/distance discard the sequence). All done IN PyRel:
#   - binary edge derived from an intermediary concept (default form)
#   - typed endpoints (Source -> Sink)
#   - aggregates.sum(Node(p.nodes).weight).per(p) sums a per-node value per route
#   - per-node filter via p.nodes(idx); native nested-segment filter via .where()
# The per-node value is a stand-in for an upstream reasoner output (e.g. a
# centrality score). Requires relationalai>=1.15 (paths is PREVIEW / pre-GA).

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

model = Model("paths_scored_routes")

# --- Ontology: Node carries `weight` (stand-in for a reasoner output);
#     Link is an intermediary connecting two Nodes. ---
Node = model.Concept("Node", identify_by={"id": Integer})
Node.name = model.Property(f"{Node} has name {String:name}")
Node.weight = model.Property(f"{Node} has weight {Float:weight}")
Node.flagged = model.Property(f"{Node} is flagged {String:flagged}")

Link = model.Concept("Link", identify_by={"id": Integer})
Link.source = model.Relationship(f"{Link} from {Node}", short_name="source")
Link.target = model.Relationship(f"{Link} to {Node}", short_name="target")

# Typed endpoint subconcepts
Source = model.Concept("Source", extends=[Node])
Sink = model.Concept("Sink", extends=[Node])

# --- Sample data ---
nodes = model.data([
    {"id": 1, "name": "in",  "weight": 0.1, "flagged": "no"},
    {"id": 2, "name": "a",   "weight": 0.9, "flagged": "yes"},
    {"id": 3, "name": "b",   "weight": 0.4, "flagged": "no"},
    {"id": 4, "name": "c",   "weight": 0.7, "flagged": "no"},
    {"id": 5, "name": "out", "weight": 0.2, "flagged": "no"},
])
model.define(Node.new(id=nodes.id, name=nodes.name, weight=nodes.weight, flagged=nodes.flagged))
model.define(Source(Node)).where(Node.name == "in")
model.define(Sink(Node)).where(Node.name == "out")

links = model.data([
    {"id": 1, "src": 1, "dst": 2},
    {"id": 2, "src": 2, "dst": 5},
    {"id": 3, "src": 1, "dst": 3},
    {"id": 4, "src": 3, "dst": 4},
    {"id": 5, "src": 4, "dst": 5},
])
model.define(Link.new(
    id=links.id,
    source=Node.lookup(id=links.src),
    target=Node.lookup(id=links.dst),
))

# --- Derive the binary edge from the Link intermediary (default constructor) ---
Node.flows_to = model.Relationship(f"{Node} flows to {Node}", short_name="flows_to")
lk = Link.ref()
a, b = Node.ref(), Node.ref()
model.where(lk.source(a), lk.target(b)).define(a.flows_to(b))

# --- Rank Source -> Sink routes by total node-weight ALONG the route, IN PYREL.
#     aggregates.sum(Node(p.nodes).weight).per(p) sums the per-node value over
#     each path's node sequence -- the core paths-only operation. ---
src, dst = Source.ref(), Sink.ref()
p = model.path(src, Node.flows_to.repeat(1, 5), dst).all_paths()
totals = model.where(
    p, total := aggs.sum(Node(p.nodes).weight).per(p),
).select(p.alias("path"), total.alias("total_weight")).to_df()

# Reassemble each route's node names into a label (string-joining is a pandas job).
seq = model.where(p).select(
    p.alias("path"),
    p.nodes["index"].alias("step"),
    Node(p.nodes).name.alias("node"),
).to_df()
seq["step"] = seq["step"].astype(int)
labels = (seq.sort_values(["path", "step"]).groupby("path")["node"]
          .apply(lambda s: " -> ".join(s)))
ranked = totals.assign(route=totals["path"].map(labels)).sort_values(
    "total_weight", ascending=False)

print("Source -> Sink routes, ranked by total node-weight (in-PyRel aggregate):")
for _, r in ranked.iterrows():
    print(f"  weight={round(float(r.total_weight), 3)}  {r.route}")

# --- Per-node filter: routes that pass through a flagged node. A free `idx`
#     ranges over ALL positions (endpoints included), so this is a per-node
#     (not interior-only) existential predicate. ---
idx = Integer.ref()
through_flagged = model.where(
    q := model.path(src, Node.flows_to.repeat(1, 5), dst).all_paths(),
    Node(q.nodes(idx)).flagged == "yes",
).select(q.alias("path")).to_df()
print(f"\n{through_flagged['path'].nunique()} route(s) pass through a flagged node "
      "(per-node filter via q.nodes(idx)).")

# --- Native universal filter: routes through ONLY un-flagged nodes. Nest the
#     repeated segment and filter it -- the nested path(...).where(...).repeat(...)
#     constrains every interior node, while the endpoints are filtered in the
#     outer where. No pandas needed. ---
clean = model.where(
    u := model.path(
        src,
        model.path(Node.flows_to).where(Node.flagged == "no").repeat(1, 5),
        dst,
    ).where(src.flagged == "no", dst.flagged == "no").all_paths(),
).select(
    u.alias("path"),
    u.nodes["index"].alias("step"),
    Node(u.nodes).name.alias("node"),
).to_df()
clean["step"] = clean["step"].astype(int)
clean_routes = (clean.sort_values(["path", "step"]).groupby("path")["node"]
                .apply(lambda s: " -> ".join(s)))
print(f"\n{len(clean_routes)} route(s) through only un-flagged nodes "
      "(native nested-segment filter):")
for route in clean_routes:
    print(f"  {route}")
