# Pattern: partitioned iteration — fresh Problem per factory, populate=False, collect results
# Key ideas: each partition gets its own Problem for clean separation; where=[filter]
# scopes variables to one subset; Variable.values() structured query extracts per-partition results.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("partitioned_iteration_scenarios")

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
    problem = Problem(model, Float)

    # 3. solve_for with where= and populate=False
    qty_var = problem.solve_for(
        Product.x_quantity,
        lower=0, upper=Product.demand,
        where=[this_product],
        populate=False,
    )

    # 4. Formulation (objective + constraints)
    problem.maximize(sum(Product.profit * Product.x_quantity).where(this_product))
    problem.satisfy(
        model.require(sum(Product.x_quantity / Product.rate) <= Factory.avail).where(
            this_product, Factory.name(factory_name)
        )
    )

    # 5. Solve
    problem.solve("highs", time_limit_sec=60)

    # 6. Collect results — Variable.values() structured query (works with populate=False)
    si = problem.solve_info()
    value_ref = Float.ref()
    plan_df = (
        model.select(
            qty_var.product.name.alias("product"),
            value_ref.alias("value"),
        )
        .where(qty_var.values(0, value_ref), value_ref > 0.001)
        .to_df()
    )
    scenario_results.append(
        {
            "factory": factory_name,
            "status": si.termination_status,
            "profit": si.objective_value,
            "plan": plan_df,
        }
    )

# 7. Summary across all partitions
for r in scenario_results:
    print(f"{r['factory']}: {r['status']}, profit=${r['profit']:.2f}")
