# Pattern: derived scalar bounds via Relationship, MTZ subtour elimination, walrus aliasing
# Key ideas: count(Node) stored as Relationship for solver bounds; degree constraints via
# .per(Node) with edge-endpoint filter; MTZ big-M with walrus := for node aliasing.

from relationalai.semantics import Float, Integer, Model, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("subtour_elimination_mtz")

# --- Ontology ---
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.dist = model.Property(f"{Edge} has {Float:dist}")

Node = model.Concept("Node", identify_by={"v": Integer})
# --- Data: complete directed graph on 4 nodes with distances ---
edge_data = model.data(
    [
        (1, 2, 10.0),
        (1, 3, 15.0),
        (1, 4, 20.0),
        (2, 1, 10.0),
        (2, 3, 35.0),
        (2, 4, 25.0),
        (3, 1, 15.0),
        (3, 2, 35.0),
        (3, 4, 30.0),
        (4, 1, 20.0),
        (4, 2, 25.0),
        (4, 3, 30.0),
    ],
    columns=["i", "j", "dist"],
)
model.define(Edge.new(edge_data.to_schema()))

model.define(Node.new(v=Edge.i))  # derive nodes from edge endpoints

# Derived scalar: node count as Relationship (needed for solve_for upper= bound)
node_count = model.Relationship(f"node count is {Integer}")
model.define(node_count(count(Node)))

# --- Decision variables ---
problem = Problem(model, Float)

# Binary: x[i,j] = 1 if edge (i,j) is in the tour
Edge.x = model.Property(f"{Edge} is selected if {Float:x}")
x_var = problem.solve_for(Edge.x, type="bin", name=["x", Edge.i, Edge.j])

# Integer: u[v] = MTZ auxiliary ordering (upper bound from Relationship)
Node.u = model.Property(f"{Node} has auxiliary value {Float:u}")
u_var = problem.solve_for(Node.u, name=["u", Node.v], type="int", lower=1, upper=node_count)

# --- Objective ---
problem.minimize(sum(Edge.dist * Edge.x))

# --- Constraints ---
# Fix u[1] = 1 as symmetry-breaking anchor
problem.satisfy(model.require(Node.u == 1).where(Node.v(1)))

# Degree constraints: exactly one in-edge and one out-edge per node
node_flow = sum(Edge.x).per(Node)
problem.satisfy(
    model.require(
        node_flow.where(Edge.j == Node.v) == 1,
        node_flow.where(Edge.i == Node.v) == 1,
    )
)

# MTZ subtour elimination with walrus operator aliasing
# If edge (i,j) is in tour (x=1), then u[j] >= u[i]+1
# Big-M form: u[i] - u[j] + n*x <= n-1
problem.satisfy(
    model.where(
        Ni := Node,
        Nj := Node.ref(),
        Edge.i > 1,
        Edge.j > 1,
        Ni.v(Edge.i),
        Nj.v(Edge.j),
    ).require(Ni.u - Nj.u + node_count * Edge.x <= node_count - 1)
)

# --- Solve ---
problem.solve("highs", time_limit_sec=60)

# Extract tour edges
model.select(
    Edge.i.alias("from"),
    Edge.j.alias("to"),
).where(Edge.x > 0.5).inspect()
