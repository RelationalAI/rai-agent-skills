# Pattern: Scenario Concept result extraction — results live in the ontology
# Key ideas: after a single solve with Scenario as a Concept, results are queryable
# via model.select() like any other property; per-scenario aggregation uses the same
# .where()/.per() patterns as constraints.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("scenario_concept_extraction")

# --- Ontology ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")

# Inline sample data: 4 items with value and pairwise interaction matrix
item_data = model.data(
    [(1, 5.0), (2, 8.0), (3, 3.0), (4, 6.0)],
    columns=["index", "value"],
)
model.define(Item.new(item_data.to_schema()))

# Interaction matrix (symmetric): interaction[i,j] contributes quadratic cost
interaction_data = model.data(
    [
        (1, 1, 4.0),
        (1, 2, 1.0),
        (1, 3, 0.5),
        (1, 4, 0.2),
        (2, 1, 1.0),
        (2, 2, 3.0),
        (2, 3, 0.8),
        (2, 4, 0.3),
        (3, 1, 0.5),
        (3, 2, 0.8),
        (3, 3, 2.0),
        (3, 4, 0.6),
        (4, 1, 0.2),
        (4, 2, 0.3),
        (4, 3, 0.6),
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

Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_benefit = model.Property(f"{Scenario} has {Float:min_benefit}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_benefit"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable indexed by Scenario
Item.x_allocation = model.Property(f"{Item} in {Scenario} has {Float:allocation}")
x_alloc = Float.ref()
PairedItem = Item.ref()
paired_alloc = Float.ref()
interaction_value = Float.ref()
total_budget = 1000

# --- Formulation ---
problem = Problem(model, Float)
x_allocation_var = problem.solve_for(Item.x_allocation(Scenario, x_alloc), name=[Scenario.name, "alloc", Item.index])
problem.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(x_alloc >= 0))
problem.satisfy(model.where(Item.x_allocation(Scenario, x_alloc)).require(sum(x_alloc).per(Scenario) <= total_budget))
problem.satisfy(
    model.where(Item.x_allocation(Scenario, x_alloc)).require(
        sum(x_alloc * Item.value).per(Scenario) >= Scenario.min_benefit
    )
)

quad_cost = (
    sum(interaction_value * x_alloc * paired_alloc)
    .per(Scenario)
    .where(
        Item.x_allocation(Scenario, x_alloc),
        PairedItem.x_allocation(Scenario, paired_alloc),
        Item.interaction(PairedItem, interaction_value),
    )
)
problem.minimize(sum(quad_cost))

problem.solve("highs", time_limit_sec=60)

# --- Result extraction: all queries use model.select() ---

# 1. Solve status
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}")
print(f"Objective (total quadratic cost): {si.objective_value}")

# 2. Per-scenario allocations — results are in the ontology, queryable like any property
print("\nAllocations per scenario:")
model.select(
    Scenario.name.alias("scenario"),
    Item.index.alias("item"),
    Item.value,
    x_alloc.alias("allocation"),
).where(Item.x_allocation(Scenario, x_alloc), x_alloc > 0.001).inspect()

# 3. Per-scenario aggregation — composable with other model queries
print("\nQuadratic cost by scenario:")
model.select(Scenario.name, quad_cost.alias("quad_cost")).inspect()

# 4. Per-scenario total allocation
print("\nTotal allocation by scenario:")
total_alloc = sum(x_alloc).per(Scenario).where(Item.x_allocation(Scenario, x_alloc))
model.select(Scenario.name, total_alloc.alias("total_allocated")).inspect()

# 5. Per-scenario achieved benefit
print("\nAchieved benefit by scenario:")
achieved_benefit = sum(x_alloc * Item.value).per(Scenario).where(Item.x_allocation(Scenario, x_alloc))
model.select(
    Scenario.name,
    Scenario.min_benefit.alias("target"),
    achieved_benefit.alias("achieved"),
).inspect()
