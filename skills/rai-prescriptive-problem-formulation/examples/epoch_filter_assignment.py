# Pattern: epoch filtering pipeline + skill-constrained assignment domain
# Key ideas: pre-filter event data by epoch timestamp BEFORE model.define();
# map epoch to categorical period (issue → target sprint); build assignment
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
Developer = Concept("Developer", identify_by={"id": Integer})
Developer.name = Property(f"{Developer} has {String:name}")
Developer.capacity_points_per_sprint = Property(f"{Developer} has {Integer:capacity_points_per_sprint}")

Sprint = Concept("Sprint", identify_by={"id": Integer})
Sprint.name = Property(f"{Sprint} has {String:name}")
Sprint.number = Property(f"{Sprint} has {Integer:number}")
Sprint.startdate = Property(f"{Sprint} has {Integer:startdate}")
Sprint.enddate = Property(f"{Sprint} has {Integer:enddate}")

Issue = Concept("Issue", identify_by={"id": Integer})
Issue.key = Property(f"{Issue} has {String:key}")
Issue.story_points = Property(f"{Issue} has {Integer:story_points}")
Issue.created_at = Property(f"{Issue} has {Integer:created_at}")
Issue.priority = Property(f"{Issue} has {Integer:priority}")
Issue.team = Property(f"{Issue} has {String:team}")
Issue.target_sprint_number = Property(f"{Issue} has target sprint {Integer:target_sprint_number}")

# NOTE: Epoch filtering happens in pandas BEFORE model.define():
#   filtered_issues = issues_df[issues_df["created_at"] <= end_epoch].copy()
# Then epoch-to-period mapping assigns target_sprint_number per issue.

Skill = Concept("Skill", identify_by={"id": Integer})
Skill.developer_id = Property(f"{Skill} has {Integer:developer_id}")
Skill.team = Property(f"{Skill} has {String:team}")

# --- Assignment domain: only valid (developer, issue, sprint) triples ---
Assignment = Concept("Assignment")
Assignment.developer = Property(f"{Assignment} has {Developer}", short_name="developer")
Assignment.issue = Property(f"{Assignment} has {Issue}", short_name="issue")
Assignment.sprint = Property(f"{Assignment} has {Sprint}", short_name="sprint")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")

# Build domain: developer has matching skill AND sprint >= target sprint
model.define(
    Assignment.new(developer=Developer, issue=Issue, sprint=Sprint)
).where(
    Skill.developer_id == Developer.id,
    Skill.team == Issue.team,
    Sprint.number >= Issue.target_sprint_number,
)

# --- Problem ---
p = Problem(model, Float)
p.solve_for(Assignment.x_assigned, type="bin",
            name=["assign", Assignment.issue.key, Assignment.developer.name, Assignment.sprint.name])

# Constraint: each issue assigned exactly once
p.satisfy(model.require(
    sum(Assignment.x_assigned).per(Issue) == 1
).where(Assignment.issue == Issue))

# Constraint: developer capacity per sprint
capacity_multiplier = 1.0
p.satisfy(model.require(
    sum(Assignment.x_assigned * Assignment.issue.story_points).per(Developer, Sprint)
    <= Developer.capacity_points_per_sprint * capacity_multiplier
).where(Assignment.developer == Developer, Assignment.sprint == Sprint))

# Objective: minimize weighted completion time (higher priority = higher delay cost)
max_priority = 3
p.minimize(
    sum(Assignment.x_assigned * (max_priority + 1 - Assignment.issue.priority) * Assignment.sprint.number)
)

p.solve("highs", time_limit_sec=60)
