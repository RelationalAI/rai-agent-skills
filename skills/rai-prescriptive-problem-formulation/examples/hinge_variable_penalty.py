# Pattern: hinge variable + qualification-filtered aggregation + unmet demand penalty
# Key ideas: excess >= total_hours - standard_hours (hinge/max-with-zero);
# qualification-filtered coverage uses .where() condition on resource qualification level;
# unmet demand as penalty term creates soft constraint for infeasible demand.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("hinge_variable_penalty")
Concept, Property = model.Concept, model.Property

# --- Ontology ---
Worker = Concept("Worker", identify_by={"id": Integer})
Worker.name = Property(f"{Worker} has {String:name}")
Worker.qualification_level = Property(f"{Worker} has {Integer:qualification_level}")
Worker.unit_cost = Property(f"{Worker} has {Float:unit_cost}")
Worker.standard_hours = Property(f"{Worker} has {Integer:standard_hours}")
Worker.excess_cost_multiplier = Property(f"{Worker} has {Float:excess_cost_multiplier}")
Worker.x_excess_hours = Property(f"{Worker} has {Float:excess_hours}")

Task = Concept("Task", identify_by={"id": Integer})
Task.name = Property(f"{Task} has {String:name}")
Task.duration = Property(f"{Task} has {Integer:duration}")
Task.min_resources = Property(f"{Task} has {Integer:min_resources}")
Task.min_qualification = Property(f"{Task} has {Integer:min_qualification}")
Task.workload = Property(f"{Task} has {Integer:workload}")
Task.x_served = Property(f"{Task} has {Float:served}")
Task.x_unmet = Property(f"{Task} has {Float:unmet}")

Slot = Concept("Slot", identify_by={"worker_id": Integer, "task_id": Integer})
Slot.worker = Property(f"{Slot} for {Worker}")
Slot.task = Property(f"{Slot} in {Task}")
Slot.available = Property(f"{Slot} is {Integer:available}")

# --- Decision concept ---
Selection = Concept("Selection", identify_by={"slot": Slot})
Selection.x_assigned = Property(f"{Selection} is {Float:assigned}")
model.define(Selection.new(slot=Slot))

SelectionRef = Selection.ref()
penalty_per_unmet = 20

# --- Sample data ---
worker_data = model.data(
    [
        {
            "id": 1,
            "name": "W1",
            "qualification_level": 3,
            "unit_cost": 25.0,
            "standard_hours": 8,
            "excess_cost_multiplier": 1.5,
        },
        {
            "id": 2,
            "name": "W2",
            "qualification_level": 2,
            "unit_cost": 20.0,
            "standard_hours": 8,
            "excess_cost_multiplier": 1.5,
        },
        {
            "id": 3,
            "name": "W3",
            "qualification_level": 1,
            "unit_cost": 18.0,
            "standard_hours": 6,
            "excess_cost_multiplier": 2.0,
        },
        {
            "id": 4,
            "name": "W4",
            "qualification_level": 3,
            "unit_cost": 28.0,
            "standard_hours": 8,
            "excess_cost_multiplier": 1.5,
        },
    ]
)
model.define(Worker.new(worker_data.to_schema()))

task_data = model.data(
    [
        {"id": 1, "name": "T1", "duration": 4, "min_resources": 2, "min_qualification": 2, "workload": 30},
        {"id": 2, "name": "T2", "duration": 6, "min_resources": 1, "min_qualification": 3, "workload": 20},
        {"id": 3, "name": "T3", "duration": 3, "min_resources": 2, "min_qualification": 1, "workload": 15},
    ]
)
model.define(Task.new(task_data.to_schema()))

# Availability matrix: which workers can work which tasks
# Slot has FK relationships to Worker and Task, resolved via filter_by
slot_data = model.data(
    [
        {"worker_id": 1, "task_id": 1, "available": 1},
        {"worker_id": 1, "task_id": 2, "available": 1},
        {"worker_id": 1, "task_id": 3, "available": 0},
        {"worker_id": 2, "task_id": 1, "available": 1},
        {"worker_id": 2, "task_id": 2, "available": 0},
        {"worker_id": 2, "task_id": 3, "available": 1},
        {"worker_id": 3, "task_id": 1, "available": 1},
        {"worker_id": 3, "task_id": 2, "available": 0},
        {"worker_id": 3, "task_id": 3, "available": 1},
        {"worker_id": 4, "task_id": 1, "available": 0},
        {"worker_id": 4, "task_id": 2, "available": 1},
        {"worker_id": 4, "task_id": 3, "available": 1},
    ]
)
model.define(
    Slot.new(
        worker_id=slot_data.worker_id,
        task_id=slot_data.task_id,
        worker=Worker.filter_by(id=slot_data.worker_id),
        task=Task.filter_by(id=slot_data.task_id),
        available=slot_data.available,
    )
)

# --- Problem setup ---
problem = Problem(model, Float)
problem.solve_for(
    Selection.x_assigned,
    type="bin",
    name=["assigned", Selection.slot.worker.name, Selection.slot.task.name],
)
problem.solve_for(Worker.x_excess_hours, type="cont", name=["excess", Worker.name], lower=0)
problem.solve_for(Task.x_served, type="cont", name=["served", Task.name], lower=0)
problem.solve_for(Task.x_unmet, type="cont", name=["unmet", Task.name], lower=0)

# Constraint: only assign available workers
problem.satisfy(model.require(Selection.x_assigned <= Selection.slot.available))

# Constraint: minimum resources per task
task_staff = sum(SelectionRef.x_assigned).where(SelectionRef.slot.task == Task).per(Task)
problem.satisfy(model.require(task_staff >= Task.min_resources))

# Constraint: qualification-filtered coverage — at least one worker meeting qualification threshold
qualified_coverage = (
    sum(SelectionRef.x_assigned)
    .where(
        SelectionRef.slot.task == Task,
        SelectionRef.slot.worker.qualification_level >= Task.min_qualification,
    )
    .per(Task)
)
problem.satisfy(model.require(qualified_coverage >= 1))

# Constraint: excess hours = hinge(total_hours - standard_hours)
total_hours = (
    sum(SelectionRef.x_assigned * SelectionRef.slot.task.duration).where(SelectionRef.slot.worker == Worker).per(Worker)
)
problem.satisfy(model.require(Worker.x_excess_hours >= total_hours - Worker.standard_hours))

# Constraint: unmet demand >= workload - served (soft constraint via penalty)
problem.satisfy(model.require(Task.x_unmet >= Task.workload - Task.x_served))

# Objective: minimize excess-hours cost + unmet-demand penalty
excess_cost = sum(Worker.x_excess_hours * Worker.unit_cost * Worker.excess_cost_multiplier)
unmet_penalty = penalty_per_unmet * sum(Task.x_unmet)
problem.minimize(excess_cost + unmet_penalty)

problem.solve("highs", time_limit_sec=60)
