# Pattern: flow conservation constraint with per-node balance using two independent refs
# Key ideas: Edge.ref() creates two independent Edge iterators (Ei, Ej); per() aggregates
# flow per node; the .where(Ei.i == Ej.j) join selects only interior nodes.

from relationalai.semantics import Float, Integer, Model, per, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("flow_conservation")

# --- Ontology ---
# Edge identified by (i, j) integer node indices; cap bounds the flow
Edge = model.Concept("Edge", identify_by={"i": Integer, "j": Integer})
Edge.cap = model.Property(f"{Edge} has {Float:cap}")

# --- Decision variable ---
# Flow on each edge, non-negative and bounded by capacity
Edge.x_flow = model.Property(f"{Edge} has {Float:flow}")
problem = Problem(model, Float)
x_flow_var = problem.solve_for(
    Edge.x_flow, name=["x", Edge.i, Edge.j], lower=0, upper=Edge.cap
)

# --- Flow conservation constraint ---
# Two independent refs scan all edges: Ei for outflow, Ej for inflow
Ei, Ej = Edge.ref(), Edge.ref()
# per(Ei.i): total flow leaving node Ei.i
flow_out = per(Ei.i).sum(Ei.x_flow)
# per(Ej.j): total flow arriving at node Ej.j
flow_in = per(Ej.j).sum(Ej.x_flow)
# Join on Ei.i == Ej.j selects nodes that appear as both source and destination (interior nodes)
balance = model.require(flow_in == flow_out).where(Ei.i == Ej.j)
problem.satisfy(balance)

# --- Objective: maximize total flow leaving the source node ---
total_flow = sum(Edge.x_flow).where(Edge.i(1))
problem.maximize(total_flow)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Max flow: {si.objective_value:.2f}")
# Extract solution — properties populated after solve (populate=True default)
model.select(Edge.i.alias("from"), Edge.j.alias("to"), Edge.x_flow.alias("flow")).where(
    Edge.x_flow > 0.001
).inspect()
