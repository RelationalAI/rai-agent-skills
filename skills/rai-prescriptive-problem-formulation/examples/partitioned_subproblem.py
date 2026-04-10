# Pattern: partitioned sub-problem solving with populate=False and where=[filter]
# Key ideas: fresh Problem per partition; where= restricts variable scope to one factory;
# populate=False prevents cross-scenario overwrites; results collected via Variable.values()
# structured query.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("partitioned_subproblem")

# --- Ontology ---
Factory = model.Concept("Factory", identify_by={"name": String})
Factory.avail = model.Property(f"{Factory} has {Float:avail}")

Product = model.Concept("Product", identify_by={"name": String, "factory_name": String})
Product.factory = model.Property(f"{Product} is produced by {Factory}")
Product.rate = model.Property(f"{Product} has {Float:rate}")
Product.profit = model.Property(f"{Product} has {Float:profit}")
Product.demand = model.Property(f"{Product} has {Integer:demand}")

# --- Decision variable (declared once, scoped per iteration) ---
Product.x_quantity = model.Property(f"{Product} has {Float:quantity}")

# --- Partitioned solve: one sub-problem per factory ---
factory_names = ["Factory_A", "Factory_B"]
results = []

for factory_name in factory_names:
    # Filter: only products belonging to this factory
    this_product = Product.factory.name(factory_name)

    # Fresh Problem for each partition (clean separation)
    problem = Problem(model, Float)

    # Variable: quantity per product, bounded by demand, scoped by where=
    qty_var = problem.solve_for(
        Product.x_quantity,
        lower=0,
        upper=Product.demand,
        name=Product.name,
        where=[this_product],  # restricts to this factory's products
        populate=False,  # don't write back — avoids cross-partition collision
    )

    # Objective: maximize profit
    problem.maximize(sum(Product.profit * Product.x_quantity).where(this_product))

    # Constraint: total resource usage <= factory availability
    problem.satisfy(
        model.require(sum(Product.x_quantity / Product.rate) <= Factory.avail).where(
            this_product, Factory.name(factory_name)
        )
    )

    problem.solve("highs", time_limit_sec=60)

    # Extract results via Variable.values() structured query (not model.select — populate=False)
    si = problem.solve_info()
    value_ref = Float.ref()
    plan_df = (
        model.select(
            qty_var.product.name.alias("product"),
            value_ref.alias("value"),
        )
        .where(qty_var.values(0, value_ref))
        .to_df()
    )
    results.append(
        {
            "factory": factory_name,
            "status": si.termination_status,
            "profit": si.objective_value,
            "plan": plan_df,
        }
    )
