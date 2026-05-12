# Pattern: minimize(max(...)) directly in objective + data-driven bounds + undirected-edge expansion + symmetry break
"""
Graph coloring: assign a color (integer) to each node so connected nodes have different colors.
Objective: minimize the maximum color used (= chromatic number).

This is the canonical example showing that CSP-style problems regularly have objectives.
The MIP form would introduce an auxiliary `t` with `t >= each_color` and `minimize(t)`;
MiniZinc accepts `minimize(max(Node.color))` directly. Both solve fine — the aggregate-as-
objective form is shorter to write. The structurally CSP-favorable side here is the
`Pa.color != Pb.color` adjacency constraint: the MIP wire does not take `!=` natively
(see csp-formulation.md § 1), so the MIP equivalent is pairwise binary indicators + big-M.
The symmetry break is a footnote, not the lesson.

Demonstrates:
- minimize(max(...)) directly in the objective — no MIP-style aux-variable rewrite needed
- Data-driven upper bound: Node.color in {1..num_nodes}; arbitrary bounds blow up search
- Undirected-edge expansion via reverse-define (Rules level) — without it, the graph constraints
  would match each edge in one direction only and miss the symmetric violations
- Symmetry break (fix Node 1's color to 1) — a one-line footnote, not the structural idea

Triggering pattern: "minimize the largest X," "minimize the worst case," "tightest band/spread"
under combinatorial constraints. CSP-style writes this directly; MIP-style introduces an aux
variable. Both work.

For undirected-edge expansion mechanics, see rai-pyrel-coding/references/expression-rules.md.
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, max
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_chromatic_number_{time.time_ns()}")

# --- Concepts and inline data ---
Node = model.Concept("Node", identify_by={"id": Integer})
RawEdge = model.Concept("RawEdge", identify_by={"a": Integer, "b": Integer})

# 6 nodes, 8 edges — a small graph with chromatic number 3
node_data = pd.DataFrame([(i,) for i in range(1, 7)], columns=["id"])
model.define(Node.new(model.data(node_data).to_schema()))

edge_data = pd.DataFrame(
    [(1, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5), (4, 6), (5, 6)],
    columns=["a", "b"],
)
model.define(RawEdge.new(model.data(edge_data).to_schema()))

# --- Undirected-edge expansion via reverse-define ---
# Persist a symmetric adjacency relation: every {a,b} raw pair appears in both orientations.
# Without this, constraints over (Adj.left, Adj.right) only match one direction of each raw edge.
Adj = model.Relationship(f"{Node:a} adjacent to {Node:b}")
Na = Node.ref()
Nb = Node.ref()
model.define(Adj(Na, Nb)).where(Na.id == RawEdge.a, Nb.id == RawEdge.b)
model.define(Adj(Na, Nb)).where(Na.id == RawEdge.b, Nb.id == RawEdge.a)

# --- Decision: color per node, bounded by node count (data-driven upper bound) ---
NUM_NODES = len(node_data)
Node.color = model.Property(f"{Node} has {Integer:color}")

problem = Problem(model, Integer)
problem.solve_for(
    Node.color,
    type="int",
    lower=1,
    upper=NUM_NODES,
    name=["color", Node.id],
)

# --- Constraint: adjacent nodes have different colors (over the symmetric Adj relation;
# Pa.id < Pb.id picks one orientation of each pair so the IC isn't double-counted) ---
Pa, Pb = Node, Node.ref()
problem.satisfy(model.where(Adj(Pa, Pb), Pa.id < Pb.id).require(Pa.color != Pb.color))

# --- Symmetry break (footnote): fix Node 1's color to 1.
# The chromatic number is invariant under permutations of color labels, so without this constraint
# the solver wastes search on relabelings of the same coloring. ---
problem.satisfy(model.where(Node.id == 1).require(Node.color == 1))

# --- Objective: minimize the largest color used ---
problem.minimize(max(Node.color))

problem.solve("minizinc", time_limit_sec=30)
problem.solve_info().display()

print("\nFinal coloring (max color = chromatic number):")
model.select(Node.id, Node.color).inspect()
