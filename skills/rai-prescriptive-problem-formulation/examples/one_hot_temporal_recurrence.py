# Pattern: one-hot selection variables, price ladder constraint, cumulative tracking
# Key ideas: multiarity binary select[product,week,discount]; pairwise week constraint
# enforces monotone discounts; recurrence relation tracks cumulative sales over time.

from relationalai.semantics import Float, Integer, Model, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("one_hot_temporal_recurrence")

# --- Ontology ---
Product = model.Concept("Product", identify_by={"name": String})
Product.initial_price = model.Property(f"{Product} has {Float:initial_price}")
Product.initial_inventory = model.Property(f"{Product} has {Integer:initial_inventory}")
Product.base_demand = model.Property(f"{Product} has {Float:base_demand}")
Product.salvage_rate = model.Property(f"{Product} has {Float:salvage_rate}")

Discount = model.Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")

Week = model.Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")

# count(Week) can be used directly in solver expressions (no workaround needed)

# --- Refs ---
w, d, x, y, z = Week.ref(), Discount.ref(), Float.ref(), Float.ref(), Float.ref()

# --- Decision variables ---
p = Problem(model, Float)

# Binary: select[product, week, discount] = 1 if that discount is active
Product.x_select = model.Property(f"{Product} in {Week} has {Discount} if {Float:x}")
p.solve_for(Product.x_select(w, d, x), type="bin",
            name=["select", Product.name, w.num, d.discount_pct])

# Continuous: sales[product, week, discount] = units sold at that discount level
Product.x_sales = model.Property(f"{Product} in {Week} at {Discount} has {Float:y}")
p.solve_for(Product.x_sales(w, d, y), type="cont", lower=0,
            name=["sales", Product.name, w.num, d.discount_pct])

# Continuous: cumulative sales[product, week]
Product.x_cuml = model.Property(f"{Product} up to {Week} has {Float:z}")
p.solve_for(Product.x_cuml(w, z), type="cont", lower=0,
            name=["cuml", Product.name, w.num])

# --- Constraints ---
# One-hot: exactly one discount level per product-week
p.satisfy(model.where(Product.x_select(w, d, x)).require(
    sum(d, x).per(Product, w) == 1
))

# Price ladder: discounts can only increase week-over-week
d2, w2, x2 = Discount.ref(), Week.ref(), Float.ref()
p.satisfy(model.where(
    Product.x_select(w, d, x), Product.x_select(w2, d2, x2),
    w2.num == w.num + 1, d2.level < d.level,
).require(x + x2 <= 1))

# Sales bounded by demand * lift * multiplier * selection indicator
p.satisfy(model.where(
    Product.x_select(w, d, x), Product.x_sales(w, d, y),
).require(y <= Product.base_demand * d.demand_lift * w.demand_multiplier * x))

# Cumulative sales — first week
p.satisfy(model.where(
    w.num == 1, Product.x_cuml(w, z), Product.x_sales(w, d, y),
).require(z == sum(d, y).per(Product, w)))

# Cumulative sales — subsequent weeks (recurrence)
w_prev, z_prev = Week.ref(), Float.ref()
p.satisfy(model.where(
    w.num > 1, w_prev.num == w.num - 1,
    Product.x_cuml(w, z), Product.x_cuml(w_prev, z_prev),
    Product.x_sales(w, d, y),
).require(z == z_prev + sum(d, y).per(Product, w)))

# Cumulative sales cannot exceed initial inventory
p.satisfy(model.where(Product.x_cuml(w, z)).require(z <= Product.initial_inventory))

# --- Objective ---
revenue = sum(
    Product.initial_price * (1 - d.discount_pct / 100) * x
).where(Product.x_sales(w, d, x))
salvage = sum(
    Product.initial_price * Product.salvage_rate * (Product.initial_inventory - z)
).where(Product.x_cuml(w, z), w.num == count(Week))
p.maximize(revenue + salvage)

# --- Solve ---
p.solve("highs", time_limit_sec=60)
