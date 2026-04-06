# Pattern: Scenario Concept — scaling constraint bounds by a scenario parameter
# Key ideas: Scenario.nutrient_scaling multiplies existing Nutrient.min/max bounds;
# decision variables are multi-argument (Food x Scenario); one solve for all scaling levels.

from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("diet")

# --- Ontology ---
Nutrient = model.Concept("Nutrient", identify_by={"name": String})
Nutrient.min = model.Property(f"{Nutrient} has {Float:min}")
Nutrient.max = model.Property(f"{Nutrient} has {Float:max}")

Food = model.Concept("Food", identify_by={"name": String})
Food.cost = model.Property(f"{Food} has {Float:cost}")
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")

# Scenario with nutrient_scaling parameter
Scenario = model.Concept("Scenario", identify_by={"scenario_name": String})
Scenario.nutrient_scaling = model.Property(f"{Scenario} has {Float:nutrient_scaling}")
scenario_data = model.data(
    [("scaling_80pct", 0.8), ("baseline", 1.0), ("scaling_120pct", 1.2)],
    columns=["scenario_name", "nutrient_scaling"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# --- Decision variable indexed by Scenario ---
Food.x_amount = model.Property(f"{Food} in {Scenario} has {Float:amount}")
x_amt = Float.ref()

p = Problem(model, Float)
p.solve_for(
    Food.x_amount(Scenario, x_amt),
    name=["amt", Scenario.scenario_name, Food.name],
    lower=0,
)

# --- Constraint: nutrient bounds scaled by scenario parameter ---
# Nutrient.min * Scenario.nutrient_scaling <= total intake <= Nutrient.max * Scenario.nutrient_scaling
nutrient_qty = Float.ref()
p.satisfy(model.where(
    Food.x_amount(Scenario, x_amt),
    Food.contains(Nutrient, nutrient_qty),
).require(
    sum(nutrient_qty * x_amt).per(Nutrient, Scenario) >= Nutrient.min * Scenario.nutrient_scaling,
    sum(nutrient_qty * x_amt).per(Nutrient, Scenario) <= Nutrient.max * Scenario.nutrient_scaling,
))

# --- Objective: minimize total cost ---
p.minimize(sum(Food.cost * x_amt).where(Food.x_amount(Scenario, x_amt)))

# --- Solve all scenarios at once ---
p.display()
p.solve("highs", time_limit_sec=60)
p.solve_info().display()

# --- Results per scenario (in the ontology) ---
print("\nDiet plan per scenario:")
model.select(
    Scenario.scenario_name.alias("scenario"),
    Food.name.alias("food"),
    Food.cost,
    x_amt.alias("amount"),
).where(
    Food.x_amount(Scenario, x_amt), x_amt > 0.001
).inspect()
