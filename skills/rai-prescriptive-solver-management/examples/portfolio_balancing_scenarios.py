# Pattern: Scenario Concept — parameter variations solved in one pass
# Key ideas: Scenario is a Concept with parameter data; decision variables are
# multi-argument (Stock x Scenario); constraints use .per(Scenario); single solve.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --- Ontology ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")

# Scenario with min_return parameter
Scenario = model.Concept("Scenario", identify_by={"name": String})
Scenario.min_return = model.Property(f"{Scenario} has {Float:min_return}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_return"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable: quantity per stock per scenario
Stock.x_quantity = model.Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()
PairedStock = Stock.ref()
paired_qty = Float.ref()
covar_value = Float.ref()
budget = 1000

# --- Constraints ---
# Bounds: non-negative
bounds = model.where(Stock.x_quantity(Scenario, x_qty)).require(x_qty >= 0)

# Budget: total allocation per scenario
budget_ok = model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(sum(x_qty).per(Scenario) <= budget)

# Return: meets scenario-specific minimum
return_ok = model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(sum(x_qty * Stock.returns).per(Scenario) >= Scenario.min_return)

# Risk: quadratic portfolio risk per scenario
risk = sum(covar_value * x_qty * paired_qty).per(Scenario).where(
    Stock.x_quantity(Scenario, x_qty),
    PairedStock.x_quantity(Scenario, paired_qty),
    Stock.covar(PairedStock, covar_value),
)

# --- Solve all scenarios at once ---
p = Problem(model, Float)
p.solve_for(Stock.x_quantity(Scenario, x_qty),
            name=[Scenario.name, "qty", Stock.index])
p.satisfy(bounds)
p.satisfy(budget_ok)
p.satisfy(return_ok)
p.minimize(sum(risk))

p.display()
p.solve("highs", time_limit_sec=60)
model.require(p.termination_status() == "OPTIMAL")
p.solve_info().display()

# --- Results per scenario ---
print("\nPortfolio allocations:")
model.select(Scenario.name, Stock.index, Stock.x_quantity).where(
    Stock.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()

print("\nRisk by scenario:")
model.select(Scenario.name, risk).inspect()
