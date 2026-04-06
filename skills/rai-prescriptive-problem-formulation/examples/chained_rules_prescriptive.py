# Pattern: Chained reasoner -- rules-derived boolean flags gating prescriptive optimization.
# Key ideas: rules stage defines Relationship flags (is_unreliable, is_at_risk) from
# threshold conditions on supplier properties; prescriptive stage uses those flags as
# hard constraints (block unreliable suppliers) and cost surcharges (penalize at-risk
# suppliers in the objective); the ontology carries enrichment forward -- no manual
# data transfer between stages.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("chained_rules_prescriptive")

# --- Ontology ---

Supplier = model.Concept("Supplier", identify_by={"id": Integer})
Supplier.name = model.Property(f"{Supplier} has name {String:name}")
Supplier.reliability = model.Property(f"{Supplier} has reliability {Float:reliability}")
Supplier.unit_cost = model.Property(f"{Supplier} has unit cost {Float:unit_cost}")
Supplier.capacity = model.Property(f"{Supplier} has capacity {Integer:capacity}")

# --- Inline data ---

supplier_data = model.data([
    {"id": 1, "name": "Alpha",   "reliability": 0.95, "unit_cost": 10.0, "capacity": 200},
    {"id": 2, "name": "Beta",    "reliability": 0.60, "unit_cost":  8.0, "capacity": 300},  # unreliable
    {"id": 3, "name": "Gamma",   "reliability": 0.78, "unit_cost": 12.0, "capacity": 150},  # at risk
    {"id": 4, "name": "Delta",   "reliability": 0.92, "unit_cost": 11.0, "capacity": 250},
    {"id": 5, "name": "Epsilon", "reliability": 0.55, "unit_cost":  7.0, "capacity": 400},  # unreliable
    {"id": 6, "name": "Zeta",    "reliability": 0.82, "unit_cost": 14.0, "capacity": 180},  # at risk
    {"id": 7, "name": "Eta",     "reliability": 0.97, "unit_cost": 13.0, "capacity": 220},
    {"id": 8, "name": "Theta",   "reliability": 0.88, "unit_cost":  9.0, "capacity": 350},
])
model.define(Supplier.new(supplier_data.to_schema()))

# =============================================================================
# Stage 1: Rules -- derive risk flags from reliability thresholds
# =============================================================================

UNRELIABLE_THRESHOLD = 0.70   # below this -> hard block
AT_RISK_THRESHOLD = 0.85      # below this (but above unreliable) -> cost surcharge

# Flag: unreliable suppliers are completely blocked from receiving flow.
Supplier.is_unreliable = model.Relationship(f"{Supplier} is unreliable")
model.where(Supplier.reliability < UNRELIABLE_THRESHOLD).define(Supplier.is_unreliable())

# Flag: at-risk suppliers get a cost surcharge but are not blocked.
Supplier.is_at_risk = model.Relationship(f"{Supplier} is at risk")
model.where(
    Supplier.reliability < AT_RISK_THRESHOLD,
    Supplier.reliability >= UNRELIABLE_THRESHOLD,
).define(Supplier.is_at_risk())

# Display flags
model.where(Supplier.is_unreliable()).select(
    Supplier.name.alias("supplier"), Supplier.reliability.alias("reliability"),
).inspect()
model.where(Supplier.is_at_risk()).select(
    Supplier.name.alias("supplier"), Supplier.reliability.alias("reliability"),
).inspect()

# =============================================================================
# Stage 2: Prescriptive -- sourcing optimization using rules flags
# =============================================================================
# Allocate a demand of TOTAL_DEMAND units across suppliers. Unreliable suppliers
# are hard-blocked (flow == 0). At-risk suppliers incur a RISK_SURCHARGE on
# top of their unit cost.

TOTAL_DEMAND = 500
RISK_SURCHARGE = 5.0

Supplier.x_flow = model.Property(f"{Supplier} has flow {Float:x}")

p = Problem(model, Float)
p.solve_for(Supplier.x_flow, lower=0, upper=Supplier.capacity, name=["flow", Supplier.name])

# Constraint: meet total demand
p.satisfy(model.require(sum(Supplier.x_flow) >= TOTAL_DEMAND))

# Constraint: hard block unreliable suppliers (flag from Stage 1)
p.satisfy(model.require(Supplier.x_flow == 0).where(Supplier.is_unreliable()))

# Objective: minimize cost with risk surcharge for at-risk suppliers.
# Base cost: unit_cost * flow for all suppliers.
base_cost = sum(Supplier.unit_cost * Supplier.x_flow)

# Surcharge: extra cost only for at-risk suppliers (flag from Stage 1).
s_risk = Supplier.ref()
risk_cost = RISK_SURCHARGE * sum(s_risk.x_flow).where(s_risk.is_at_risk())

p.minimize(sum(model.union(base_cost, risk_cost)))

# --- Solve ---
p.display()
p.solve("highs", time_limit_sec=60)
model.require(p.termination_status() == "OPTIMAL")
si = p.solve_info()
si.display()
print(f"Status: {si.termination_status}, Objective: {si.objective_value:.2f}")

# --- Results ---
model.select(
    Supplier.name.alias("supplier"),
    Supplier.reliability.alias("reliability"),
    Supplier.unit_cost.alias("unit_cost"),
    Supplier.x_flow.alias("flow"),
).where(Supplier.x_flow > 0.001).inspect()
