# Pattern: loop-based result extraction — results live in Python DataFrames (outside the model)
# Key ideas: variable_values().to_df() extracts solution when populate=False;
# solve_info().display() shows solver diagnostics; collect scenario results for comparison.
# For Scenario Concept result extraction (results in the ontology via model.select()),
# see scenario_concept_extraction.py.

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("loop_based_extraction")

# --- Ontology ---
Item = model.Concept("Item", identify_by={"index": Integer})
Item.value = model.Property(f"{Item} has {Float:value}")
Item.interaction = model.Property(f"{Item} and {Item} have {Float:interaction}")
Item.x_allocation = model.Property(f"{Item} allocation is {Float:x}")

# --- Sample data (3 items with value and interaction matrix) ---
item_data = model.data([
    {"index": 1, "value": 5.0},
    {"index": 2, "value": 8.0},
    {"index": 3, "value": 3.0},
])
model.define(Item.new(item_data.to_schema()))

# Symmetric interaction matrix (quadratic cost coefficients)
PairedItem = Item.ref()
interaction_raw = model.data([
    {"i": 1, "j": 1, "w": 2.0}, {"i": 1, "j": 2, "w": 0.5}, {"i": 1, "j": 3, "w": 0.3},
    {"i": 2, "j": 1, "w": 0.5}, {"i": 2, "j": 2, "w": 3.0}, {"i": 2, "j": 3, "w": 0.7},
    {"i": 3, "j": 1, "w": 0.3}, {"i": 3, "j": 2, "w": 0.7}, {"i": 3, "j": 3, "w": 1.5},
], columns=["i", "j", "w"])
model.where(
    Item.index(interaction_raw.i),
    PairedItem.index(interaction_raw.j),
).define(Item.interaction(PairedItem, interaction_raw.w))

Item2 = Item.ref()
c = Float.ref()
total_budget = 1000


def build_and_solve(min_benefit):
    """Build formulation, solve, and return results dict."""
    p = Problem(model, Float)

    # Variables with populate=False — solution extracted via variable_values()
    p.solve_for(Item.x_allocation, name=["alloc", Item.index], populate=False)

    # Constraints and objective
    p.satisfy(model.require(Item.x_allocation >= 0))
    p.satisfy(model.require(sum(Item.x_allocation) <= total_budget))
    p.satisfy(model.require(sum(Item.value * Item.x_allocation) >= min_benefit))
    quad_cost = sum(c * Item.x_allocation * Item2.x_allocation).where(
        Item.interaction(Item2, c)
    )
    p.minimize(quad_cost)

    # --- Solve and inspect ---
    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()
    si.display()  # prints solver stats: status, objective, gap, time

    # --- Result extraction ---
    # termination_status: "OPTIMAL", "INFEASIBLE", "TIME_LIMIT", etc.
    # objective_value: best objective found (None if infeasible)
    print(f"Status: {si.termination_status}")
    print(
        f"Objective (quadratic cost): {si.objective_value:.6f}"
        if si.objective_value is not None
        else "Objective: N/A"
    )

    # variable_values().to_df() returns DataFrame with columns: name, value
    var_df = p.variable_values().to_df()
    allocation = var_df[var_df["value"] > 0.001]
    print(f"Allocation:\n{allocation.to_string(index=False)}")

    return {
        "min_benefit": min_benefit,
        "status": si.termination_status,
        "quad_cost": si.objective_value,
        "allocation": allocation,
    }


# --- Run scenarios and build comparison table ---
scenario_results = [build_and_solve(mb) for mb in [10, 20, 30]]

print("\n=== Scenario Comparison ===")
print(f"{'Min Benefit':>12} {'Status':>10} {'Quad Cost':>14}")
print("-" * 40)
for r in scenario_results:
    print(f"{r['min_benefit']:>12} {r['status']:>10} {r['quad_cost']:>14.6f}")
