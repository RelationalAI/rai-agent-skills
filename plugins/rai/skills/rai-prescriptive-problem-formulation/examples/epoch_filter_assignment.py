# Pattern: epoch filtering pipeline + skill-constrained assignment domain
# Key ideas: pre-filter event data by epoch timestamp BEFORE model.define();
# map epoch to categorical period (task → target sprint); build assignment
# domain with skill + temporal eligibility via .where(); weighted completion objective.

from datetime import datetime
from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("epoch_filter_assignment")
Concept, Property = model.Concept, model.Property

# --- Parameters ---
planning_start = "2024-10-01"
planning_end = "2024-11-26"
start_epoch = int(datetime.strptime(planning_start, "%Y-%m-%d").timestamp())
end_epoch = int(datetime.strptime(planning_end, "%Y-%m-%d").timestamp())

# --- Ontology (abbreviated) ---
Worker = Concept("Worker", identify_by={"id": Integer})
Worker.name = Property(f"{Worker} has {String:name}")
Worker.capacity_points_per_sprint = Property(f"{Worker} has {Integer:capacity_points_per_sprint}")

Sprint = Concept("Sprint", identify_by={"id": Integer})
Sprint.name = Property(f"{Sprint} has {String:name}")
Sprint.number = Property(f"{Sprint} has {Integer:number}")
Sprint.startdate = Property(f"{Sprint} has {Integer:startdate}")
Sprint.enddate = Property(f"{Sprint} has {Integer:enddate}")

Task = Concept("Task", identify_by={"id": Integer})
Task.key = Property(f"{Task} has {String:key}")
Task.story_points = Property(f"{Task} has {Integer:story_points}")
Task.created_at = Property(f"{Task} has {Integer:created_at}")
Task.priority = Property(f"{Task} has {Integer:priority}")
Task.team = Property(f"{Task} has {String:team}")
Task.target_sprint_number = Property(f"{Task} has target sprint {Integer:target_sprint_number}")

# NOTE: Epoch filtering happens in pandas BEFORE model.define():
#   filtered_tasks = tasks_df[tasks_df["created_at"] <= end_epoch].copy()
# Then epoch-to-period mapping assigns target_sprint_number per task.

Skill = Concept("Skill", identify_by={"id": Integer})
Skill.worker_id = Property(f"{Skill} has {Integer:worker_id}")
Skill.team = Property(f"{Skill} has {String:team}")

# --- Assignment domain: only valid (worker, task, sprint) triples ---
Assignment = Concept("Assignment")
Assignment.worker = Property(f"{Assignment} has {Worker}", short_name="worker")
Assignment.task = Property(f"{Assignment} has {Task}", short_name="task")
Assignment.sprint = Property(f"{Assignment} has {Sprint}", short_name="sprint")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")

# Build domain: worker has matching skill AND sprint >= target sprint
model.define(Assignment.new(worker=Worker, task=Task, sprint=Sprint)).where(
    Skill.worker_id == Worker.id,
    Skill.team == Task.team,
    Sprint.number >= Task.target_sprint_number,
)

# --- Problem ---
problem = Problem(model, Float)
problem.solve_for(
    Assignment.x_assigned,
    type="bin",
    name=[
        "assign",
        Assignment.task.key,
        Assignment.worker.name,
        Assignment.sprint.name,
    ],
)

# Constraint: each task assigned exactly once
problem.satisfy(model.require(sum(Assignment.x_assigned).per(Task) == 1).where(Assignment.task == Task))

# Constraint: worker capacity per sprint
capacity_multiplier = 1.0
problem.satisfy(
    model.require(
        sum(Assignment.x_assigned * Assignment.task.story_points).per(Worker, Sprint)
        <= Worker.capacity_points_per_sprint * capacity_multiplier
    ).where(Assignment.worker == Worker, Assignment.sprint == Sprint)
)

# Objective: minimize weighted completion time (higher priority = higher delay cost)
max_priority = 3
problem.minimize(sum(Assignment.x_assigned * (max_priority + 1 - Assignment.task.priority) * Assignment.sprint.number))

problem.solve("highs", time_limit_sec=60)
