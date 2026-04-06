# Pattern: multiarity properties with refs, .where() joins, model.define() for derived values
# Key ideas: Float.ref() binds specific fields of multiarity properties; .where() joins
# multiple property bindings in a single fragment; count() stored via model.define().

from relationalai.semantics import Float, Integer, Model, String, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("one_hot_temporal_recurrence_code")

# --- Multiarity property declarations ---
Product = model.Concept("Product", identify_by={"name": String})
Product.initial_price = model.Property(f"{Product} has {Float:initial_price}")
Product.initial_inventory = model.Property(f"{Product} has {Integer:initial_inventory}")
Product.base_demand = model.Property(f"{Product} has {Float:base_demand}")

Discount = model.Concept("Discount", identify_by={"level": Integer})
Discount.discount_pct = model.Property(f"{Discount} has {Float:discount_pct}")
Discount.demand_lift = model.Property(f"{Discount} has {Float:demand_lift}")

Week = model.Concept("Week", identify_by={"num": Integer})
Week.demand_multiplier = model.Property(f"{Week} has {Float:demand_multiplier}")

# Derived scalar via model.define() — stores count as a Relationship
num_weeks = model.Relationship(f"{Integer}")
model.define(num_weeks(count(Week)))

# --- Refs: bind specific fields of multiarity properties ---
w = Week.ref()
d = Discount.ref()
x = Float.ref()   # bound to selection indicator
y = Float.ref()   # bound to sales quantity

# Multiarity decision variable: 4-arity (Product, Week, Discount, Float)
Product.x_select = model.Property(f"{Product} in {Week} has {Discount} if {Float:x}")
Product.x_sales = model.Property(f"{Product} in {Week} at {Discount} has {Float:y}")

# --- .where() joins binding multiple refs in one fragment ---
p = Problem(model, Float)
p.solve_for(Product.x_select(w, d, x), type="bin",
            name=["select", Product.name, w.num, d.discount_pct])
p.solve_for(Product.x_sales(w, d, y), type="cont", lower=0,
            name=["sales", Product.name, w.num, d.discount_pct])

# Constraint joining two multiarity property bindings in one .where()
p.satisfy(model.where(
    Product.x_select(w, d, x),   # binds w, d, x
    Product.x_sales(w, d, y),    # binds same w, d — equi-join on week and discount
).require(
    y <= Product.base_demand * d.demand_lift * w.demand_multiplier * x
))

# Second ref set for pairwise week comparison
d2, w2, x2 = Discount.ref(), Week.ref(), Float.ref()
p.satisfy(model.where(
    Product.x_select(w, d, x),
    Product.x_select(w2, d2, x2),
    w2.num == w.num + 1,          # temporal adjacency join
    d2.level < d.level,           # discount ordering filter
).require(x + x2 <= 1))

# --- Objective using .where() on multiarity properties ---
revenue = sum(
    Product.initial_price * (1 - d.discount_pct / 100) * x
).where(Product.x_sales(w, d, x))   # binds x to sales quantity here

p.maximize(revenue)
p.solve("highs", time_limit_sec=60)
