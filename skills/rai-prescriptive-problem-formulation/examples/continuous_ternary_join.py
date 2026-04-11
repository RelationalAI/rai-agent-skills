# Pattern: continuous variables + ternary property join for nutritional constraint
# Key ideas: Float.ref() binds the ternary property value; .where().per() scopes the sum
# to each Nutrient; a single constraint fragment handles all nutrients at once.

from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("continuous_ternary_join")

# --- Ontology ---
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")

Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
# Ternary property: (Food, Nutrient) → quantity — binding the third field gives the float value
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")

# --- Decision variable ---
# Continuous quantity of each food; lower=0 enforces non-negativity
Food.x_amount = model.Property(f"{Food} has {Float:amount}")
problem = Problem(model, Float)
problem.solve_for(Food.x_amount, name=Food.name, lower=0)

# --- Nutritional constraint ---
# qty binds the third field of the ternary property Food.contains(Nutrient, qty)
qty = Float.ref()
nutrient_total = sum(qty * Food.x_amount).where(Food.contains(Nutrient, qty)).per(Nutrient)
# One require() fragment covers all nutrients simultaneously; no Python loop needed
problem.satisfy(
    model.require(
        nutrient_total >= Nutrient.min,
        nutrient_total <= Nutrient.max,
    )
)

# --- Objective ---
total_cost = sum(Food.cost * Food.x_amount)
problem.minimize(total_cost)

# --- Solve ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()

# Extract solution — properties populated after solve (populate=True default)
model.select(Food.name.alias("food"), Food.x_amount.alias("amount")).where(Food.x_amount > 0.001).inspect()
