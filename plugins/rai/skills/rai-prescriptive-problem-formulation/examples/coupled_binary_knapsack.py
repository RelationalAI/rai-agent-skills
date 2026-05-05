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
problem.solve_for(Investment.x_selected, type="bin", name=["inv", Investment.site.name])

# --- Capacity expansion constraint ---
# Approved project demand at each site <= existing capacity + investment capacity.
# Capture the constraint ref + name=[Site.id] so display rows are identifiable
# and we can check per-site cardinality before solving — any RHS aggregate or
# property that's empty for a site (Site.current_capacity unpopulated, or no
# Investment rows at the site) would silently drop that site's constraint.
project_demand = (
    sum(ProjectRef.x_approved * ProjectRef.capacity_needed).where(ProjectRef.site == Site).per(Site)
)
investment_cap = (
    sum(InvestmentRef.x_selected * InvestmentRef.capacity_added).where(InvestmentRef.site == Site).per(Site)
)
cap_constr = problem.satisfy(
    model.require(project_demand <= Site.current_capacity + investment_cap),
    name=["cap", Site.id],
)

# At most one investment per site
investments_per_site = sum(InvestmentRef.x_selected).where(InvestmentRef.site == Site).per(Site)
one_inv_constr = problem.satisfy(
    model.require(investments_per_site <= 1),
    name=["one_inv", Site.id],
)

# Budget knapsack: total investment across both decision sets
total_invest = sum(Project.x_approved * Project.connection_cost) + sum(Investment.x_selected * Investment.investment_cost)
budget_constr = problem.satisfy(model.require(total_invest <= budget), name="budget")

# Objective: maximize net revenue from approved projects
problem.maximize(sum(Project.x_approved * (Project.revenue - Project.connection_cost)))

# Pre-solve validation: per-constraint cardinality first (cheap), then targeted
# display only when a count is off. n_grounded < n_sites means at least one
# RHS aggregate or property was empty for that site (Site.current_capacity
# unpopulated, or no Investment rows at the site so investment_cap is empty)
# and PyRel relational semantics dropped the constraint body for that site.
n_grounded = len(model.select(cap_constr).to_df())
n_sites = len(model.select(Site).to_df())
if n_grounded != n_sites:
    problem.display(cap_constr, limit=10)  # human-readable view of survivors
    raise AssertionError(f"cap_constr fired {n_grounded}/{n_sites}")

problem.solve("highs", time_limit_sec=60)
