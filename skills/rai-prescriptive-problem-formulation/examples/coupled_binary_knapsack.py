# Pattern: capacity expansion — two coupled binary decision sets sharing a resource constraint
# Key ideas: approve-Project and select-Upgrade are independent binary decisions; an Upgrade
# adds capacity at a Substation, relaxing the constraint on approved Projects there; budget
# knapsack ties both decision sets together; at-most-one upgrade per substation.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("coupled_binary_knapsack")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Substation = Concept("Substation", identify_by={"id": Integer})
Substation.name = Property(f"{Substation} has {String:name}")
Substation.current_capacity = Property(f"{Substation} has {Integer:current_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.substation = Property(f"{Project} connects to {Substation}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")
Project.x_approved = Property(f"{Project} is {Float:approved}")

Upgrade = Concept("Upgrade", identify_by={"id": Integer})
Upgrade.substation = Property(f"{Upgrade} for {Substation}")
Upgrade.capacity_added = Property(f"{Upgrade} adds {Integer:capacity_added}")
Upgrade.upgrade_cost = Property(f"{Upgrade} has {Float:upgrade_cost}")
Upgrade.x_selected = Property(f"{Upgrade} is {Float:selected}")

ProjectRef = Project.ref()
UpgradeRef = Upgrade.ref()
budget = 2_000_000_000

problem = Problem(model, Float)
x_approved_var = problem.solve_for(Project.x_approved, type="bin", name=Project.name)
x_selected_var = problem.solve_for(Upgrade.x_selected, type="bin", name=["upg", Upgrade.substation.name])

# --- Capacity expansion constraint ---
# Approved project demand at each substation <= existing capacity + upgrade capacity
project_demand = (
    sum(ProjectRef.x_approved * ProjectRef.capacity_needed).where(ProjectRef.substation == Substation).per(Substation)
)
upgrade_cap = (
    sum(UpgradeRef.x_selected * UpgradeRef.capacity_added).where(UpgradeRef.substation == Substation).per(Substation)
)
problem.satisfy(model.require(project_demand <= Substation.current_capacity + upgrade_cap))

# At most one upgrade per substation
upgrades_per_sub = sum(UpgradeRef.x_selected).where(UpgradeRef.substation == Substation).per(Substation)
problem.satisfy(model.require(upgrades_per_sub <= 1))

# Budget knapsack: total investment across both decision sets
total_invest = sum(Project.x_approved * Project.connection_cost) + sum(Upgrade.x_selected * Upgrade.upgrade_cost)
problem.satisfy(model.require(total_invest <= budget))

# Objective: maximize net revenue from approved projects
problem.maximize(sum(Project.x_approved * (Project.revenue - Project.connection_cost)))

problem.solve("highs", time_limit_sec=60)
