# Pattern: post-solve result extraction across multiple scenarios
# Key ideas: variable_values().to_df() extracts solution when populate=False;
# solve_info().display() shows solver diagnostics; collect scenario results for comparison.

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --- Ontology (abbreviated) ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")

Stock2 = Stock.ref()
c = Float.ref()
budget = 1000


def build_and_solve(min_ret):
    """Build formulation, solve, and return results dict."""
    p = Problem(model, Float)

    # Variables with populate=False — solution extracted via variable_values()
    p.solve_for(Stock.x_quantity, name=["qty", Stock.index], populate=False)

    # Constraints and objective
    p.satisfy(model.require(Stock.x_quantity >= 0))
    p.satisfy(model.require(sum(Stock.x_quantity) <= budget))
    p.satisfy(model.require(sum(Stock.returns * Stock.x_quantity) >= min_ret))
    risk = sum(c * Stock.x_quantity * Stock2.x_quantity).where(Stock.covar(Stock2, c))
    p.minimize(risk)

    # --- Solve and inspect ---
    p.solve("highs", time_limit_sec=60)
    si = p.solve_info()
    si.display()  # prints solver stats: status, objective, gap, time

    # --- Result extraction ---
    # termination_status: "OPTIMAL", "INFEASIBLE", "TIME_LIMIT", etc.
    # objective_value: best objective found (None if infeasible)
    print(f"Status: {si.termination_status}")
    print(
        f"Objective (risk): {si.objective_value:.6f}"
        if si.objective_value is not None
        else "Objective: N/A"
    )

    # variable_values().to_df() returns DataFrame with columns: name, value
    var_df = p.variable_values().to_df()
    allocation = var_df[var_df["value"] > 0.001]
    print(f"Allocation:\n{allocation.to_string(index=False)}")

    return {
        "min_return": min_ret,
        "status": si.termination_status,
        "risk": si.objective_value,
        "allocation": allocation,
    }


# --- Run scenarios and build comparison table ---
scenario_results = [build_and_solve(mr) for mr in [10, 20, 30]]

print("\n=== Scenario Comparison ===")
print(f"{'Min Return':>12} {'Status':>10} {'Risk':>14}")
print("-" * 40)
for r in scenario_results:
    print(f"{r['min_return']:>12} {r['status']:>10} {r['risk']:>14.6f}")
