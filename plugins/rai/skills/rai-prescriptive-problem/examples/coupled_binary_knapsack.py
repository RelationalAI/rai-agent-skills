# Pattern: two coupled binary decision sets sharing a resource constraint + budget knapsack
# Key ideas: two independent binary decisions (approve-Project, select-Investment) are coupled
# through a shared capacity constraint — selecting an Investment at a Site relaxes the
# capacity constraint on approved Projects there; a budget knapsack ties both decision sets
# together; at-most-one investment per site.
# Illustrated with a capacity-expansion model (approve projects, select site investments).

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("coupled_binary_knapsack")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.current_capacity = Property(f"{Site} has {Integer:current_capacity}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.site = Property(f"{Project} connects to {Site}")
Project.capacity_needed = Property(f"{Project} needs {Integer:capacity_needed}")
Project.revenue = Property(f"{Project} has {Float:revenue}")
Project.connection_cost = Property(f"{Project} has {Float:connection_cost}")
Project.x_approved = Property(f"{Project} is {Float:approved}")

Investment = Concept("Investment", identify_by={"id": Integer})
Investment.site = Property(f"{Investment} for {Site}")
Investment.capacity_added = Property(f"{Investment} adds {Integer:capacity_added}")
Investment.investment_cost = Property(f"{Investment} has {Float:investment_cost}")
Investment.x_selected = Property(f"{Investment} is {Float:selected}")

ProjectRef = Project.ref()
InvestmentRef = Investment.ref()
budget = 2_000_000_000

problem = Problem(model, Float)
problem.solve_for(Project.x_approved, type="bin", name=Project.name)
problem.solve_for(Investment.x_selected, type="bin", name=["inv", Investment.id])

# --- Capacity expansion constraint ---
# Approved project demand at each site <= existing capacity + investment capacity.
# Capture the constraint ref + name=[Site.id] so display rows are identifiable.
# A site with no Project or no Investment rows reads 0 for that sum (`| 0`). A site with no
# current_capacity gets no row on releases through 2.0.0 and an always-false row on later ones, so the
# gate below checks the data.
project_demand = (
    sum(ProjectRef.x_approved * ProjectRef.capacity_needed).where(ProjectRef.site == Site).per(Site) | 0
)
investment_cap = (
    sum(InvestmentRef.x_selected * InvestmentRef.capacity_added).where(InvestmentRef.site == Site).per(Site) | 0
)
cap_constr = problem.satisfy(
    model.where(Site).require(project_demand <= Site.current_capacity + investment_cap),
    name=["cap", Site.id],
)

# At most one investment per site, for each site reached through its investments
investments_per_site = sum(InvestmentRef.x_selected).where(InvestmentRef.site == Site).per(Site)
one_inv_constr = problem.satisfy(
    model.where(Investment.site(Site)).require(investments_per_site <= 1),
    name=["one_inv", Site.id],
)

# Budget knapsack: total investment across both decision sets
total_invest = (sum(Project.x_approved * Project.connection_cost) | 0) + (sum(Investment.x_selected * Investment.investment_cost) | 0)
budget_constr = problem.satisfy(model.require(total_invest <= budget), name="budget")

# Objective: maximize net revenue from approved projects
problem.maximize(sum(Project.x_approved * (Project.revenue - Project.connection_cost)))

# Pre-solve validation: every site must have the current_capacity the capacity body reads.
# This file declares the schema only; the gate fires once Site/Project/Investment
# data is loaded — with the data-less ontology above, both counts are 0.
n_ready = len(model.select(Site).where(Site.current_capacity).to_df())
n_sites = len(model.select(Site).to_df())
if n_ready != n_sites:
    raise AssertionError(f"cap_constr has a current_capacity for {n_ready}/{n_sites} sites")

problem.solve("highs", time_limit_sec=60)
