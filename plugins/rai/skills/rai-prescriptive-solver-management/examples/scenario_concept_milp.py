# Pattern: Scenario Concept — multi-entity MILP with two binary variable types indexed by Scenario
# Key ideas: Project.x_approved and Investment.x_selected are both indexed by (Entity, Scenario);
# constraints use .per(Site, Scenario) for two-level grouping; budget constraint spans
# both variable types per scenario; single solve for all budget levels.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("scenario_concept_milp")
Concept, Property = model.Concept, model.Property

# --- Ontology ---
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.current_capacity = Property(f"{Site} has {Integer:current_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.site = Property(f"{Project} connects to {Site}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")

Investment = Concept("Investment", identify_by={"id": Integer})
Investment.site = Property(f"{Investment} for {Site}")
Investment.capacity_added = Property(f"{Investment} adds {Integer:capacity_added}")
Investment.investment_cost = Property(f"{Investment} has {Float:investment_cost}")

# Scenario with budget parameter
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_1B", 1e9), ("budget_2B", 2e9), ("budget_3B", 3e9)],
    columns=["name", "budget"],
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
        (1, "ProjectAlpha", 1, 40, 5e8, 1e8),
        (2, "ProjectBeta", 1, 20, 3e8, 0.5e8),
        (3, "ProjectGamma", 2, 25, 6e8, 2e8),
        (4, "ProjectDelta", 2, 15, 2e8, 0.8e8),
    ],
    columns=[
        "id",
        "name",
        "site_id",
        "capacity_needed",
        "revenue",
        "connection_cost",
    ],
)
model.define(
    Project.new(
        proj_data.to_schema(exclude=["site_id"]),
        site=Site.filter_by(id=proj_data.site_id),
    )
)

inv_data = model.data(
    [(1, 1, 30, 4e8), (2, 1, 60, 7e8), (3, 2, 20, 3e8), (4, 2, 40, 5e8)],
    columns=["id", "site_id", "capacity_added", "investment_cost"],
)
model.define(
    Investment.new(
        inv_data.to_schema(exclude=["site_id"]),
        site=Site.filter_by(id=inv_data.site_id),
    )
)

# --- Decision variables — both indexed by Scenario ---
Project.x_approved = Property(f"{Project} in {Scenario} is {Float:approved}")
Investment.x_selected = Property(f"{Investment} in {Scenario} is {Float:selected}")

x_approved = Float.ref()
x_selected = Float.ref()
ProjectRef = Project.ref()
InvestmentRef = Investment.ref()

problem = Problem(model, Float)
problem.solve_for(
    Project.x_approved(Scenario, x_approved),
    type="bin",
    name=["proj", Scenario.name, Project.name],
)
problem.solve_for(
    Investment.x_selected(Scenario, x_selected),
    type="bin",
    name=["inv", Scenario.name, Investment.site.name, Investment.capacity_added],
)

# --- Constraint: capacity at site (per Site, per Scenario) ---
x_approved_ref = Float.ref()
x_selected_ref = Float.ref()
problem.satisfy(
    model.where(
        Project.x_approved(Scenario, x_approved_ref),
        Investment.x_selected(Scenario, x_selected_ref),
        Project.site(Site),
        Investment.site(Site),
    ).require(
        Site.current_capacity
        + sum(x_selected_ref * InvestmentRef.capacity_added)
        .where(InvestmentRef.site == Site)
        .per(Site, Scenario)
        >= sum(x_approved_ref * ProjectRef.capacity_needed)
        .where(ProjectRef.site == Site)
        .per(Site, Scenario)
    )
)

# --- Constraint: at most one investment per site (per Scenario) ---
problem.satisfy(
    model.where(
        Investment.x_selected(Scenario, x_selected),
    ).require(sum(x_selected).where(Investment.site == Site).per(Site, Scenario) <= 1)
)

# --- Constraint: budget limit (per Scenario) — spans both variable types ---
problem.satisfy(
    model.where(
        Project.x_approved(Scenario, x_approved),
        Investment.x_selected(Scenario, x_selected),
    ).require(
        sum(x_approved * Project.connection_cost).per(Scenario) + sum(x_selected * Investment.investment_cost).per(Scenario)
        <= Scenario.budget
    )
)

# --- Objective: maximize net revenue ---
problem.maximize(
    sum(x_approved * (Project.revenue - Project.connection_cost)).where(Project.x_approved(Scenario, x_approved))
)

# --- Solve all budget scenarios at once ---
problem.display()
problem.solve("highs", time_limit_sec=60)
problem.solve_info().display()

# --- Results per scenario (in the ontology) ---
print("\nApproved projects per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Project.name.alias("project"),
    Project.revenue,
    Project.connection_cost,
).where(Project.x_approved(Scenario, x_approved), x_approved > 0.5).inspect()

print("\nSelected investments per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Investment.site.name.alias("site"),
    Investment.capacity_added,
    Investment.investment_cost,
).where(Investment.x_selected(Scenario, x_selected), x_selected > 0.5).inspect()
