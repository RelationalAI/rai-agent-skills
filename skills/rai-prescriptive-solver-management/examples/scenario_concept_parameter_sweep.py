# Pattern: Scenario Concept — parameter variations solved in one pass
# Key ideas: Scenario is a Concept with parameter data; decision variables are
# multi-argument (Item x Scenario); constraints use .per(Scenario); single solve.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("scenario_concept_parameter_sweep")

# --- Ontology ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")

# Sample item data: values and pairwise interaction matrix
item_data = model.data(
    [(1, 5.0), (2, 8.0), (3, 3.0), (4, 6.0)],
    columns=["index", "value"],
)
model.define(Item.new(item_data.to_schema()))

interaction_data = model.data(
    [
        (1, 1, 4.0),
        (1, 2, 1.0),
        (1, 3, 0.5),
        (1, 4, 0.2),
        (2, 1, 1.0),
        (2, 2, 6.0),
        (2, 3, 1.5),
        (2, 4, 0.8),
        (3, 1, 0.5),
        (3, 2, 1.5),
        (3, 3, 3.0),
        (3, 4, 0.4),
        (4, 1, 0.2),
        (4, 2, 0.8),
        (4, 3, 0.4),
        (4, 4, 5.0),
    ],
    columns=["item_a", "item_b", "interaction"],
)
ItemA = Item.ref()
ItemB = Item.ref()
model.where(
    ItemA.index == interaction_data.item_a,
    ItemB.index == interaction_data.item_b,
).define(ItemA.interaction(ItemB, interaction_data.interaction))

# Scenario with min_benefit parameter
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_benefit = model.Property(f"{Scenario} has {Float:min_benefit}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_benefit"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable: allocation per item per scenario
Item.x_allocation = model.Property(f"{Item} in {Scenario} has {Float:allocation}")
x_alloc = Float.ref()
PairedItem = Item.ref()
paired_alloc = Float.ref()
interaction_value = Float.ref()
total_budget = 1000

# --- Constraints ---
# Bounds: non-negative
bounds = model.where(Item.x_allocation(Scenario, x_alloc)).require(x_alloc >= 0)

# Budget: total allocation per scenario
budget_ok = model.where(
    Item.x_allocation(Scenario, x_alloc),
).require(sum(x_alloc).per(Scenario) <= total_budget)

# Benefit: meets scenario-specific minimum
benefit_ok = model.where(
    Item.x_allocation(Scenario, x_alloc),
).require(sum(x_alloc * Item.value).per(Scenario) >= Scenario.min_benefit)

# Quadratic cost: pairwise interaction cost per scenario
quad_cost = (
    sum(interaction_value * x_alloc * paired_alloc)
    .per(Scenario)
    .where(
        Item.x_allocation(Scenario, x_alloc),
        PairedItem.x_allocation(Scenario, paired_alloc),
        Item.interaction(PairedItem, interaction_value),
    )
)

# --- Solve all scenarios at once ---
problem = Problem(model, Float)
x_allocation_var = problem.solve_for(Item.x_allocation(Scenario, x_alloc), name=[Scenario.name, "alloc", Item.index])
problem.satisfy(bounds)
problem.satisfy(budget_ok)
problem.satisfy(benefit_ok)
problem.minimize(sum(quad_cost))

problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()

# --- Results per scenario ---
print("\nAllocations per scenario:")
model.select(Scenario.name, Item.index, x_alloc.alias("allocation")).where(
    Item.x_allocation(Scenario, x_alloc), x_alloc > 0.001
).inspect()

print("\nQuadratic cost by scenario:")
model.select(Scenario.name, quad_cost).inspect()
