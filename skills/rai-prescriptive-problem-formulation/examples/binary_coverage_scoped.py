# Pattern: binary variables scoped to availability + per-entity coverage constraints
# Key ideas: solve_for(..., type="bin", where=[Relationship]) restricts variables to
# feasible (Worker, Shift) pairs only; sum(...).per(Shift) and sum(...).per(Worker)
# enforce min-coverage and max-load without separate Python loops.

from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("binary_coverage_scoped")

# --- Ontology ---
Worker = model.Concept("Worker", identify_by={"id": Integer})
Worker.name = model.Property(f"{Worker} has {String:name}")

Shift = model.Concept("Shift", identify_by={"id": Integer})
Shift.name = model.Property(f"{Shift} has {String:name}")
Shift.capacity = model.Property(f"{Shift} has {Integer:capacity}")

# Relationship encodes feasible domain — only pairs where worker said "available"
Worker.available_for = model.Relationship(f"{Worker} is available for {Shift}")

# --- Decision variable ---
# Binary indicator for each feasible (Worker, Shift) pair
# where=[Worker.available_for(Shift)] restricts to availability pairs only
Worker.x_assign = model.Property(f"{Worker} has {Shift} if {Integer:assigned}")
x = Integer.ref()
problem = Problem(model, Integer)
x_assign_var = problem.solve_for(
    Worker.x_assign(Shift, x),
    type="bin",
    name=["x", Worker.name, Shift.name],
    where=[Worker.available_for(Shift)],
)

# Parameters
min_coverage = 2  # workers required per shift
max_shifts = 1  # shifts per worker

# --- Coverage constraint: each shift must have at least min_coverage workers ---
# sum(Worker, x).per(Shift) counts workers assigned to each shift
problem.satisfy(model.where(Worker.x_assign(Shift, x)).require(sum(Worker, x).per(Shift) >= min_coverage))

# --- Load constraint: each worker assigned to at most max_shifts shifts ---
# sum(Shift, x).per(Worker) counts shifts per worker
problem.satisfy(model.where(Worker.x_assign(Shift, x)).require(sum(Shift, x).per(Worker) <= max_shifts))

# --- Solve ---
problem.display()
problem.solve("minizinc", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}")
# Extract solution — properties populated after solve (populate=True default)
model.select(Worker.name.alias("worker"), Shift.name.alias("shift")).where(Worker.x_assign(Shift, x), x > 0.5).inspect()
