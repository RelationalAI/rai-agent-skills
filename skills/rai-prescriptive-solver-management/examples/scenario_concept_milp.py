# Pattern: Scenario Concept — multi-entity MILP with two binary variable types indexed by Scenario
# Key ideas: Project.x_approved and Upgrade.x_selected are both indexed by (Entity, Scenario);
# constraints use .per(Substation, Scenario) for two-level grouping; budget constraint spans
# both variable types per scenario; single solve for all budget levels.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("scenario_concept_milp")
Concept, Property = model.Concept, model.Property

# --- Ontology ---
Substation = Concept("Substation", identify_by={"id": Integer})
Substation.name = Property(f"{Substation} has {String:name}")
Substation.current_capacity = Property(f"{Substation} has {Integer:current_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.substation = Property(f"{Project} connects to {Substation}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")

Upgrade = Concept("Upgrade", identify_by={"id": Integer})
Upgrade.substation = Property(f"{Upgrade} for {Substation}")
Upgrade.capacity_added = Property(f"{Upgrade} adds {Integer:capacity_added}")
Upgrade.upgrade_cost = Property(f"{Upgrade} has {Float:upgrade_cost}")

# Scenario with budget parameter
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
scenario_data = model.data(
    [("budget_1B", 1e9), ("budget_2B", 2e9), ("budget_3B", 3e9)],
    columns=["name", "budget"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --- Decision variables — both indexed by Scenario ---
Project.x_approved = Property(f"{Project} in {Scenario} is {Float:approved}")
Upgrade.x_selected = Property(f"{Upgrade} in {Scenario} is {Float:selected}")

x_approved = Float.ref()
x_selected = Float.ref()
ProjectRef = Project.ref()
UpgradeRef = Upgrade.ref()

p = Problem(model, Float)
p.solve_for(Project.x_approved(Scenario, x_approved), type="bin",
            name=["proj", Scenario.name, Project.name])
p.solve_for(Upgrade.x_selected(Scenario, x_selected), type="bin",
            name=["upg", Scenario.name, Upgrade.substation.name, Upgrade.capacity_added])

# --- Constraint: capacity at substation (per Substation, per Scenario) ---
x_approved_ref = Float.ref()
x_selected_ref = Float.ref()
p.satisfy(model.where(
    Project.x_approved(Scenario, x_approved_ref),
    Upgrade.x_selected(Scenario, x_selected_ref),
    Project.substation(Substation),
    Upgrade.substation(Substation),
).require(
    Substation.current_capacity
    + sum(x_selected_ref * UpgradeRef.capacity_added).where(UpgradeRef.substation == Substation).per(Substation, Scenario)
    >= sum(x_approved_ref * ProjectRef.capacity_needed).where(ProjectRef.substation == Substation).per(Substation, Scenario)
))

# --- Constraint: at most one upgrade per substation (per Scenario) ---
p.satisfy(model.where(
    Upgrade.x_selected(Scenario, x_selected),
).require(
    sum(x_selected).where(Upgrade.substation == Substation).per(Substation, Scenario) <= 1
))

# --- Constraint: budget limit (per Scenario) — spans both variable types ---
p.satisfy(model.where(
    Project.x_approved(Scenario, x_approved),
    Upgrade.x_selected(Scenario, x_selected),
).require(
    sum(x_approved * Project.connection_cost).per(Scenario)
    + sum(x_selected * Upgrade.upgrade_cost).per(Scenario)
    <= Scenario.budget
))

# --- Objective: maximize net revenue ---
p.maximize(
    sum(x_approved * (Project.revenue - Project.connection_cost))
    .where(Project.x_approved(Scenario, x_approved))
)

# --- Solve all budget scenarios at once ---
p.display()
p.solve("highs", time_limit_sec=60)
p.solve_info().display()

# --- Results per scenario (in the ontology) ---
print("\nApproved projects per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Project.name.alias("project"),
    Project.revenue,
    Project.connection_cost,
).where(
    Project.x_approved(Scenario, x_approved), x_approved > 0.5
).inspect()

print("\nSelected upgrades per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Upgrade.substation.name.alias("substation"),
    Upgrade.capacity_added,
    Upgrade.upgrade_cost,
).where(
    Upgrade.x_selected(Scenario, x_selected), x_selected > 0.5
).inspect()
