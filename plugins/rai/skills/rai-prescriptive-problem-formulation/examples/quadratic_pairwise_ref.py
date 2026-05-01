# Pattern: pairwise/quadratic expression via Item.ref() + ternary interaction property
# Key ideas: Item.ref() gives a second independent iterator Item2; Float.ref() binds
# the interaction value from the ternary property; the product Item.x_allocation *
# Item2.x_allocation captures the quadratic interaction term. This pattern generalises
# to any pairwise interaction (covariance, distance, affinity, substitution cost, etc.).

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("quadratic_pairwise_ref")

# --- Ontology ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")

# Binary property: pairwise interaction between two items.
# FD key: (Item_i, Item_j) -> interaction value.
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")

# --- Inline data ---

item_data = model.data(
    [
        {"index": 1, "value": 5.0},
        {"index": 2, "value": 8.0},
        {"index": 3, "value": 6.0},
    ]
)
model.define(Item.new(item_data.to_schema()))

# Symmetric 3x3 interaction matrix
Item2 = Item.ref()
interaction_data = model.data(
    [
        {"i": 1, "j": 1, "w": 4.0},
        {"i": 1, "j": 2, "w": 1.5},
        {"i": 1, "j": 3, "w": 0.5},
        {"i": 2, "j": 1, "w": 1.5},
        {"i": 2, "j": 2, "w": 9.0},
        {"i": 2, "j": 3, "w": 2.0},
        {"i": 3, "j": 1, "w": 0.5},
        {"i": 3, "j": 2, "w": 2.0},
        {"i": 3, "j": 3, "w": 3.0},
    ],
    columns=["i", "j", "w"],
)
model.where(
    Item.index(interaction_data.i),
    Item2.index(interaction_data.j),
).define(Item.interaction(Item2, interaction_data.w))

# --- Decision variable ---
Item.x_allocation = model.Property(f"{Item} allocation is {Float:x}")
problem = Problem(model, Float)
problem.solve_for(Item.x_allocation, name=["alloc", Item.index])

# --- Constraints ---
# Non-negative allocations
problem.satisfy(model.require(Item.x_allocation >= 0))

total_budget = 1000
problem.satisfy(model.require(sum(Item.x_allocation) <= total_budget))

min_total_value = 20
problem.satisfy(model.require(sum(Item.value * Item.x_allocation) >= min_total_value))

# --- Quadratic objective: minimize pairwise interaction term ---
# Float.ref() binds the interaction value c from the ternary property Item.interaction(Item2, c)
# The product x_i * x_j * c_ij sums over all (i, j) pairs -- this is the quadratic term.
c = Float.ref()
cost = sum(c * Item.x_allocation * Item2.x_allocation).where(Item.interaction(Item2, c))
problem.minimize(cost)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
si = problem.solve_info()
si.display()
print(f"Status: {si.termination_status}, Objective: {si.objective_value:.6f}")
# Extract solution -- properties populated after solve (populate=True default)
model.select(Item.index.alias("item"), Item.x_allocation.alias("allocation")).where(Item.x_allocation > 0.001).inspect()
