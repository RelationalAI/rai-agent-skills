# Pattern: Loop + where= filter — entity exclusion scenarios
# Key ideas: each disruption scenario excludes a supplier via != filter in where=[];
# fresh Problem per iteration; populate=False prevents cross-iteration contamination;
# results extracted via Variable.values() structured query (outside the model).

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("entity_exclusion_disruption")
Concept, Property = model.Concept, model.Property

# --- Ontology ---
Supplier = Concept("Supplier", identify_by={"id": Integer})
Supplier.name = Property(f"{Supplier} has {String:name}")
Supplier.capacity = Property(f"{Supplier} has {Integer:capacity}")

Product = Concept("Product", identify_by={"id": Integer})
Product.name = Property(f"{Product} has {String:name}")
Product.demand = Property(f"{Product} has {Integer:demand}")

SupplyOption = Concept("SupplyOption", identify_by={"id": Integer})
SupplyOption.supplier = Property(f"{SupplyOption} from {Supplier}", short_name="supplier")
SupplyOption.product = Property(f"{SupplyOption} for {Product}", short_name="product")
SupplyOption.cost_per_unit = Property(f"{SupplyOption} has {Float:cost_per_unit}")

SupplyOrder = Concept("SupplyOrder")
SupplyOrder.option = Property(f"{SupplyOrder} uses {SupplyOption}", short_name="option")
SupplyOrder.x_quantity = Property(f"{SupplyOrder} has {Float:quantity}")
model.define(SupplyOrder.new(option=SupplyOption))

# Derived relationships for direct access
SupplyOrder.supplier = Property(f"{SupplyOrder} has {Supplier}", short_name="supplier")
model.define(SupplyOrder.supplier(Supplier)).where(SupplyOrder.option(SupplyOption), SupplyOption.supplier(Supplier))
SupplyOrder.product = Property(f"{SupplyOrder} has {Product}", short_name="product")
model.define(SupplyOrder.product(Product)).where(SupplyOrder.option(SupplyOption), SupplyOption.product(Product))
SupplyOrder.cost_per_unit = Property(f"{SupplyOrder} has {Float:cost_per_unit}")
model.define(SupplyOrder.cost_per_unit(SupplyOption.cost_per_unit)).where(SupplyOrder.option(SupplyOption))

# --- Disruption scenarios: exclude suppliers one at a time ---
excluded_suppliers = [None, "SupplierC", "SupplierB"]
scenario_results = []

for excluded in excluded_suppliers:
    label = "baseline" if excluded is None else f"without_{excluded}"

    problem = Problem(model, Float)

    # where= filter excludes the supplier's orders
    if excluded is not None:
        active_orders = SupplyOrder.supplier.name != excluded
        qty_var = problem.solve_for(
            SupplyOrder.x_quantity,
            name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
            lower=0,
            where=[active_orders],
            populate=False,
        )
    else:
        qty_var = problem.solve_for(
            SupplyOrder.x_quantity,
            name=["qty", SupplyOrder.supplier.name, SupplyOrder.product.name],
            lower=0,
            populate=False,
        )

    # Constraints
    problem.satisfy(
        model.require(
            sum(SupplyOrder.x_quantity).where(SupplyOrder.supplier == Supplier).per(Supplier) <= Supplier.capacity
        )
    )
    problem.satisfy(
        model.require(sum(SupplyOrder.x_quantity).where(SupplyOrder.product == Product).per(Product) >= Product.demand)
    )

    # Objective
    problem.minimize(sum(SupplyOrder.x_quantity * SupplyOrder.cost_per_unit))

    problem.solve("highs", time_limit_sec=60)

    # Collect results per iteration (outside the model)
    si = problem.solve_info()
    scenario_results.append(
        {
            "scenario": label,
            "status": si.termination_status,
            "objective": si.objective_value,
        }
    )

    # Variable.values() structured query via ProblemVariable back-pointers
    value_ref = Float.ref()
    qty_df = (
        model.select(
            qty_var.supplyorder.supplier.name.alias("supplier"),
            qty_var.supplyorder.product.name.alias("product"),
            value_ref.alias("value"),
        )
        .where(qty_var.values(0, value_ref), value_ref > 0.001)
        .to_df()
    )
    print(f"\n{label}: {si.termination_status}, cost={si.objective_value}")
    print(qty_df.to_string(index=False))

# Summary
print("\n" + "=" * 50)
print("Scenario Analysis Summary")
for r in scenario_results:
    print(f"  {r['scenario']}: {r['status']}, obj={r['objective']}")
