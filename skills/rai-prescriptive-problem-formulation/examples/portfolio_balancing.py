# Pattern: pairwise/quadratic expression via Stock.ref() + ternary covariance property
# Key ideas: Stock.ref() gives a second independent iterator Stock2; Float.ref() binds
# the covariance value from the binary property; the product Stock.x_qty * Stock2.x_qty
# captures the quadratic risk term. This pattern generalises to any pairwise interaction.

from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("portfolio")

# --- Ontology ---
Stock = model.Concept("Stock", identify_by={"index": Integer})
Stock.returns = model.Property(f"{Stock} has {Float:returns}")

# Binary property: covariance between two stocks.
# FD key: (Stock_i, Stock_j) → covar value.
Stock.covar = model.Property(f"{Stock} and {Stock} have {Float:covar}")

# Load covariance matrix: for each (i, j) pair define Stock.covar(Stock2, value)
Stock2 = Stock.ref()
# (data loading omitted — follows model.where(Stock.index(data.i), Stock2.index(data.j))
#  .define(Stock.covar(Stock, Stock2, data.covar)) pattern from the full template)

# --- Decision variable ---
Stock.x_quantity = model.Property(f"{Stock} quantity is {Float:x}")
p = Problem(model, Float)
p.solve_for(Stock.x_quantity, name=["qty", Stock.index])

# --- Constraints ---
# Non-negative quantities (no short selling)
p.satisfy(model.require(Stock.x_quantity >= 0))

budget = 1000
p.satisfy(model.require(sum(Stock.x_quantity) <= budget))

min_return = 20
p.satisfy(model.require(sum(Stock.returns * Stock.x_quantity) >= min_return))

# --- Quadratic objective: minimize portfolio variance ---
# Float.ref() binds the covariance value c from the ternary property Stock.covar(Stock2, c)
# The product x_i * x_j * c_ij sums over all (i, j) pairs — this is the quadratic risk term.
c = Float.ref()
risk = sum(c * Stock.x_quantity * Stock2.x_quantity).where(Stock.covar(Stock2, c))
p.minimize(risk)

# --- Solve ---
p.display()
p.solve("highs", time_limit_sec=60)
model.require(p.termination_status() == "OPTIMAL")
si = p.solve_info()
si.display()
print(f"Status: {si.termination_status}, Risk: {si.objective_value:.6f}")
# Extract solution — properties populated after solve (populate=True default)
model.select(Stock.index.alias("stock"), Stock.x_quantity.alias("quantity")).where(
    Stock.x_quantity > 0.001
).inspect()
