# Pattern: fixed-charge facility location via SiteUsage tracking concept
# Key ideas: SiteUsage concept tracks whether each Site is used (binary); linking constraint
# ties assignment quantity to Site capacity * usage binary; multi-component objective
# combines shipping cost + fixed facility costs.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("fixed_charge_facility")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")
Site.capacity = Property(f"{Site} has {Integer:capacity}")
Site.fixed_cost = Property(f"{Site} has {Float:fixed_cost}")

Order = Concept("Order", identify_by={"id": Integer})
Order.customer = Property(f"{Order} for {String:customer}")
Order.quantity = Property(f"{Order} has {Integer:quantity}")

ShippingCost = Concept("ShippingCost")
ShippingCost.site = Property(f"{ShippingCost} from {Site}", short_name="site")
ShippingCost.order = Property(f"{ShippingCost} for {Order}", short_name="order")
ShippingCost.cost_per_unit = Property(f"{ShippingCost} has {Float:cost_per_unit}")

# --- Decision concepts ---
Assignment = Concept("Assignment")
Assignment.shipping = Property(f"{Assignment} uses {ShippingCost}", short_name="shipping")
Assignment.x_qty = Property(f"{Assignment} has {Float:qty}")
model.define(Assignment.new(shipping=ShippingCost))

# SiteUsage: tracks whether each Site is activated (binary)
SiteUsage = Concept("SiteUsage")
SiteUsage.site = Property(f"{SiteUsage} for {Site}", short_name="site")
SiteUsage.x_used = Property(f"{SiteUsage} is {Float:used}")
model.define(SiteUsage.new(site=Site))

AssignmentRef = Assignment.ref()

problem = Problem(model, Float)
problem.solve_for(
    Assignment.x_qty,
    lower=0,
    name=["qty", Assignment.shipping.site.name, Assignment.shipping.order.customer],
)
problem.solve_for(SiteUsage.x_used, type="bin", name=["site_used", SiteUsage.site.name])

# Constraint: Site capacity
problem.satisfy(model.require(sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.site == Site).per(Site) <= Site.capacity))

# Constraint: linking — quantity only flows through used Sites
problem.satisfy(
    model.require(
        sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.site == SiteUsage.site).per(SiteUsage)
        <= SiteUsage.site.capacity * SiteUsage.x_used
    )
)

# Constraint: each order fully fulfilled (forcing constraint)
problem.satisfy(
    model.require(sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.order == Order).per(Order) == Order.quantity)
)

# Objective: minimize shipping + fixed facility costs
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(SiteUsage.x_used * SiteUsage.site.fixed_cost)
problem.minimize(shipping_cost + fixed_cost)

problem.solve("highs", time_limit_sec=60)
