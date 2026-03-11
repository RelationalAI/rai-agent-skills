# Pattern: inline formulation + fresh Problem per scenario for what-if analysis
# Key ideas: formulation code placed directly inside scenario loop; fresh Problem
# avoids degraded state; populate=False keeps scenarios independent.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --- Ontology (abbreviated) ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")

PairedStock = Stock.ref()
covar_value = Float.ref()
budget = 1000

# Shared constraint fragments (defined once, reused across scenarios)
bounds = model.require(Stock.x_quantity >= 0)
budget_constraint = model.require(sum(Stock.x_quantity) <= budget)
risk = sum(covar_value * Stock.x_quantity * PairedStock.x_quantity).where(Stock.covar(PairedStock, covar_value))

# --- Parametric what-if: sweep over minimum return targets ---
SCENARIO_PARAM = "min_return"
SCENARIO_VALUES = [10, 20, 30]
scenario_results = []

for scenario_value in SCENARIO_VALUES:
    print(f"\nRunning scenario: {SCENARIO_PARAM} = {scenario_value}")

    # Set scenario parameter value
    min_return = scenario_value

    # Create fresh Problem for each scenario
    s = Problem(model, Float)
    s.solve_for(Stock.x_quantity, name=["qty", Stock.index], populate=False)

    # Static constraints
    s.satisfy(bounds)
    s.satisfy(budget_constraint)

    # Parameterized constraint: minimum return target (depends on scenario param)
    return_constraint = model.require(sum(Stock.returns * Stock.x_quantity) >= min_return)
    s.satisfy(return_constraint)

    # Objective: minimize portfolio risk
    s.minimize(risk)

    s.display()
    s.solve("highs", time_limit_sec=60, _server_side_import=False)
    s.display_solve_info()

    scenario_results.append({
        "scenario": scenario_value,
        "status": str(s.termination_status),
        "risk": s.objective_value,
    })
    print(f"  Status: {s.termination_status}, Risk: {s.objective_value:.6f}")

    # Extract solution via variable_values() — populate=False avoids overwriting between scenarios
    var_df = s.variable_values().to_df()
    alloc = var_df[var_df["value"] > 0.001]
    print(f"  Portfolio allocation:\n{alloc.to_string(index=False)}")

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
print("=" * 50)
for r in scenario_results:
    print(f"  min_return={r['scenario']}: {r['status']}, risk={r['risk']:.6f}")
