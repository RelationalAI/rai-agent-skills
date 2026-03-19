# Pattern: partitioned iteration — fresh Problem per factory, populate=False, collect results
# Key ideas: each partition gets its own Problem for clean separation; where=[filter]
# scopes variables to one subset; variable_values().to_df() extracts per-partition results.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("factory_production")

# --- Ontology (abbreviated) ---
Factory = model.Concept("Factory", identify_by={"name": String})
Factory.avail = model.Property(f"{Factory} has {Float:avail}")

Product = model.Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = model.Property(f"{Product} is produced by {Factory}")
Product.rate = model.Property(f"{Product} has {Float:rate}")
Product.profit = model.Property(f"{Product} has {Float:profit}")
Product.demand = model.Property(f"{Product} has {Integer:demand}")
Product.x_quantity = model.Property(f"{Product} has {Float:quantity}")

# --- Iteration pattern: one sub-problem per factory ---
factory_names = ["Factory_A", "Factory_B"]
scenario_results = []

for factory_name in factory_names:
    # 1. Scope filter — restricts to this factory's products
    this_product = Product.factory.name(factory_name)

    # 2. Fresh Problem — clean separation per partition
    p = Problem(model, Float)

    # 3. solve_for with where= and populate=False
    p.solve_for(
        Product.x_quantity,
        lower=0, upper=Product.demand,
        name=Product.name,
        where=[this_product],
        populate=False,
    )

    # 4. Formulation (objective + constraints)
    p.maximize(sum(Product.profit * Product.x_quantity).where(this_product))
    p.satisfy(model.require(
        sum(Product.x_quantity / Product.rate) <= Factory.avail
    ).where(this_product, Factory.name(factory_name)))

    # 5. Solve
    p.solve("highs", time_limit_sec=60)

    # 6. Collect results — solve_info() batches all metadata in one query
    si = p.solve_info()
    var_df = p.variable_values().to_df()
    scenario_results.append(
        {
            "factory": factory_name,
            "status": str(si.termination_status),
            "profit": si.objective_value,
            "plan": var_df[var_df["value"] > 0.001],
        }
    )

# 7. Summary across all partitions
for r in scenario_results:
    profit = r["profit"]
    profit_str = f"${profit:.2f}" if profit is not None else "N/A"
    print(f"{r['factory']}: {r['status']}, profit={profit_str}")
