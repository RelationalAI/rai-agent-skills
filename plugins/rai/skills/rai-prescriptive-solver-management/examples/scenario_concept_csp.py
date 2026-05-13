# Pattern: Scenario Concept — CSP-style analog of scenario_concept_milp.py
"""
Capacity allocation across 3 scenarios that each raise the capacity bound by an integer amount.
Scenario is modeled as a data concept indexing integer decisions; a single MiniZinc solve covers
all scenarios together (rather than re-solving once per scenario).

Demonstrates:
- Problem(model, Integer) + solver="minizinc" — integer-only decisions and data
- Scenario as a data concept (not a Python loop) — the parameter dimension lives in the model
- Multi-arity decision property indexed by (Project, Scenario)
- Per-scenario constraints via `.per(Site, Scenario)` two-level grouping
- Single solve replaces N solver invocations; the solver picks each scenario's best assignment jointly

Triggering pattern: "compare K parameter levels," "show the optimal plan under each scenario,"
"sweep the capacity bound and pick the best assignment for each level." When the parameter axis is
finite, well-defined, and shares the same constraint structure across levels, encode Scenario as a
data concept rather than a Python re-solve loop.

Mirrors `scenario_concept_milp.py` in this directory — same pattern with integer decisions and the
MiniZinc backend instead of HiGHS / Gurobi.
"""

import time

from relationalai.semantics import Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"scenario_concept_csp_{time.time_ns()}")
Concept, Property = model.Concept, model.Property

# --- Ontology ---
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.current_capacity = Property(f"{Site} has {Integer:current_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.site = Property(f"{Project} connects to {Site}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Integer:revenue}")

# Scenario with an integer capacity-bound parameter
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.bound = Property(f"{Scenario} has {Integer:bound}")
scenario_data = model.data(
    [("low_bound", 40), ("med_bound", 60), ("high_bound", 90)],
    columns=["name", "bound"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --- Data ---
site_data = model.data(
    [(1, "SiteA", 50), (2, "SiteB", 30)],
    columns=["id", "name", "current_capacity"],
)
model.define(Site.new(site_data.to_schema()))

proj_data = model.data(
    [
        (1, "ProjectAlpha", 1, 20, 500),
        (2, "ProjectBeta", 1, 15, 300),
        (3, "ProjectGamma", 2, 25, 600),
        (4, "ProjectDelta", 2, 10, 250),
    ],
    columns=["id", "name", "site_id", "capacity_needed", "revenue"],
)
model.define(
    Project.new(
        proj_data.to_schema(exclude=["site_id"]),
        site=Site.filter_by(id=proj_data.site_id),
    )
)

# --- Decision variable indexed by Scenario (binary, integer) ---
Project.x_approved = Property(f"{Project} in {Scenario} is {Integer:approved}")

x_approved = Integer.ref()
ProjectRef = Project.ref()

problem = Problem(model, Integer)
problem.solve_for(
    Project.x_approved(Scenario, x_approved),
    type="bin",
    name=["proj", Scenario.name, Project.name],
)

# --- Constraint: total capacity needed by approved projects per Site, per Scenario, stays under
# (Site.current_capacity + Scenario.bound — the scenario lifts the bound by an integer amount).
# Bind the decision value (x_ref) through ProjectRef inside the aggregate's where so the
# decision and the capacity belong to the SAME project row — see the coupled_binary_knapsack
# pattern in problem-formulation/examples/. Decoupling x_approved_ref from ProjectRef would
# multiply one project's decision by another's capacity. ---
x_ref = Integer.ref()
problem.satisfy(
    model.require(
        sum(x_ref * ProjectRef.capacity_needed)
        .where(ProjectRef.x_approved(Scenario, x_ref), ProjectRef.site == Site)
        .per(Site, Scenario)
        <= Site.current_capacity + Scenario.bound
    )
)

# --- Objective: maximize total revenue across all scenarios ---
problem.maximize(
    sum(x_approved * Project.revenue).where(Project.x_approved(Scenario, x_approved))
)

# --- Single MiniZinc solve covers all scenarios ---
problem.display()
problem.solve("minizinc", time_limit_sec=60)
problem.solve_info().display()

# --- Results per scenario ---
print("\nApproved projects per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Project.name.alias("project"),
    Project.revenue,
).where(Project.x_approved(Scenario, x_approved), x_approved > 0).inspect()
