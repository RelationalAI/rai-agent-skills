# Pattern: Scenario Concept for demand multiplier sweep
# Key ideas: DemandLevel is a Scenario Concept with a demand_multiplier property;
# decision variables are indexed by (Facility, Customer, DemandLevel); demand
# constraint scales by multiplier; single solve produces all scenarios at once.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("scenario_concept_demand_scaling")

# --- Ontology ---
Facility = model.Concept("Facility", identify_by={"name": String})
Facility.capacity = model.Property(f"{Facility} has {Integer:capacity}")
Facility.cost_per_unit = model.Property(f"{Facility} has {Float:cost_per_unit}")

Customer = model.Concept("Customer", identify_by={"name": String})
Customer.base_demand = model.Property(f"{Customer} has {Integer:base_demand}")

# Scenario Concept: each level scales demand differently
DemandLevel = model.Concept("DemandLevel", identify_by={"name": String})
DemandLevel.demand_multiplier = model.Property(f"{DemandLevel} has {Float:demand_multiplier}")

# --- Data ---
fac_data = model.data(
    [("PlantA", 300, 3.0), ("PlantB", 150, 5.0), ("PlantC", 100, 2.0)],
    columns=["name", "capacity", "cost_per_unit"],
)
model.define(Facility.new(fac_data.to_schema()))

cust_data = model.data(
    [("North", 120), ("South", 80), ("East", 60)],
    columns=["name", "base_demand"],
)
model.define(Customer.new(cust_data.to_schema()))

scenario_data = model.data(
    [("low", 0.5), ("base", 1.0), ("high", 1.5), ("surge", 2.0)],
    columns=["name", "demand_multiplier"],
)
model.define(DemandLevel.new(scenario_data.to_schema()))

# --- Decision variable: allocation per (Facility, Customer, DemandLevel) ---
Facility.x_alloc = model.Property(f"{Facility} ships to {Customer} under {DemandLevel} quantity {Float:alloc}")
x_alloc = Float.ref()

problem = Problem(model, Float)
problem.solve_for(
    Facility.x_alloc(Customer, DemandLevel, x_alloc),
    lower=0,
    name=[DemandLevel.name, "alloc", Facility.name, Customer.name],
)

# --- Constraints ---
# Demand satisfaction: total shipped to each customer meets scaled demand per scenario
problem.satisfy(
    model.where(
        Facility.x_alloc(Customer, DemandLevel, x_alloc),
    ).require(sum(x_alloc).per(Customer, DemandLevel) >= Customer.base_demand * DemandLevel.demand_multiplier)
)

# Capacity: each facility's total shipments cannot exceed capacity (per scenario)
problem.satisfy(
    model.where(
        Facility.x_alloc(Customer, DemandLevel, x_alloc),
    ).require(sum(x_alloc).per(Facility, DemandLevel) <= Facility.capacity)
)

# --- Objective: minimize total cost across all scenarios ---
problem.minimize(sum(Facility.cost_per_unit * x_alloc).where(Facility.x_alloc(Customer, DemandLevel, x_alloc)))

# --- Solve all scenarios at once ---
problem.display()
problem.solve("highs", time_limit_sec=60)
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()

# --- Results: extract per scenario ---
print("\nAll allocations:")
model.select(DemandLevel.name, Facility.name, Customer.name, Facility.x_alloc).where(
    Facility.x_alloc(Customer, DemandLevel, x_alloc), x_alloc > 0.001
).inspect()

# Filter to a single scenario using model.select().where()
print("\nHigh-demand scenario only:")
model.select(Facility.name, Customer.name, Facility.x_alloc).where(
    Facility.x_alloc(Customer, DemandLevel, x_alloc),
    DemandLevel.name("high"),
    x_alloc > 0.001,
).inspect()

# Total cost per scenario
print("\nCost per scenario:")
cost_per_scenario = (
    sum(Facility.cost_per_unit * x_alloc).per(DemandLevel).where(Facility.x_alloc(Customer, DemandLevel, x_alloc))
)
model.select(DemandLevel.name, cost_per_scenario).inspect()
