# Pattern: variable-length path enumeration over a self-referencing concept.
# model.path(rel.repeat(min, max)).all_paths() enumerates; a native .where() on a
# node ref filters DURING enumeration (no pandas). all_paths() has WALK semantics
# and there is no native simple-path mode, so drop node-repeating walks with a
# PyRel post-filter -- a negated existential over positions, still in PyRel (not
# pandas). pandas is used only to string-join names for display.
# Requires relationalai>=1.15 (paths is PREVIEW / pre-GA).

from relationalai.semantics import Integer, Model, String, not_, where

model = Model("paths_variable_length_enumeration")

# --- Ontology: a generic self-referencing dependency concept ---
Component = model.Concept("Component", identify_by={"id": Integer})
Component.name = model.Property(f"{Component} has name {String:name}")
Component.depends_on = model.Relationship(
    f"{Component} depends on {Component}", short_name="depends_on"
)

# --- Sample data: a small dependency graph WITH a cycle (c4 <-> c5) ---
comp = model.data([
    {"id": 1, "name": "c1"},
    {"id": 2, "name": "c2"},
    {"id": 3, "name": "c3"},
    {"id": 4, "name": "c4"},
    {"id": 5, "name": "c5"},
])
model.define(Component.new(id=comp.id, name=comp.name))

edges = model.data([
    {"src": 1, "dst": 2},
    {"src": 1, "dst": 3},
    {"src": 2, "dst": 3},
    {"src": 2, "dst": 4},
    {"src": 4, "dst": 5},
    {"src": 5, "dst": 4},  # cycle: c4 <-> c5
])
model.define(
    Component.lookup(id=edges.src).depends_on(Component.lookup(id=edges.dst))
)


def reassemble(df):
    """Group (path, step, component) rows into ordered route tuples (display only)."""
    df["step"] = df["step"].astype(int)
    return sorted(
        {tuple(g.sort_values("step")["component"]) for _, g in df.groupby("path")},
        key=lambda t: (len(t), t),
    )


# --- Native per-node filter: enumerate only paths that START at "c1". The
#     .where() on the source ref is applied during enumeration (no pandas). ---
start = Component.ref()
rooted = model.where(
    p := model.path(start.depends_on.repeat(1, 4)).all_paths(),
    start.name == "c1",
).select(
    p.alias("path"),
    p.nodes["index"].alias("step"),
    Component(p.nodes).name.alias("component"),
).to_df()
print(f"{len(reassemble(rooted))} paths rooted at 'c1' (native .where() filter):")
for r in reassemble(rooted):
    print("  " + " -> ".join(r))

# --- Enumerate ALL 1..4-hop paths, keeping only SIMPLE paths via a PyRel
#     post-filter (no native simple-path mode): drop any path that revisits a
#     node -- a negated existential over positions. The filter runs in PyRel. ---
i, j = Integer.ref(), Integer.ref()
q = model.path(Component.depends_on.repeat(1, 4)).all_paths()
simple = model.where(
    q,
    not_(where(i < j, q.nodes(i) == q.nodes(j))),
).select(
    q.alias("path"),
    q.nodes["index"].alias("step"),
    Component(q.nodes).name.alias("component"),
).to_df()
routes = reassemble(simple)
print(f"\n{len(routes)} simple dependency paths (1-4 hops, PyRel simple-path filter):")
for r in routes:
    print(f"  L{len(r) - 1}: " + " -> ".join(r))
