# Pattern: fixed-charge facility location via FCUsage tracking concept
# Key ideas: FCUsage concept tracks whether each FC is used (binary); linking constraint
# ties assignment quantity to FC capacity * usage binary; multi-component objective
# combines shipping cost + fixed facility costs.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("order_fulfillment")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
FC = Concept("FulfillmentCenter", identify_by={"id": Integer})
FC.name = Property(f"{FC} has {String:name}")
FC.capacity = Property(f"{FC} has {Integer:capacity}")
FC.fixed_cost = Property(f"{FC} has {Float:fixed_cost}")

Order = Concept("Order", identify_by={"id": Integer})
Order.customer = Property(f"{Order} for {String:customer}")
Order.quantity = Property(f"{Order} has {Integer:quantity}")

ShippingCost = Concept("ShippingCost")
ShippingCost.fc = Property(f"{ShippingCost} from {FC}", short_name="fc")
ShippingCost.order = Property(f"{ShippingCost} for {Order}", short_name="order")
ShippingCost.cost_per_unit = Property(f"{ShippingCost} has {Float:cost_per_unit}")

# --- Decision concepts ---
Assignment = Concept("Assignment")
Assignment.shipping = Property(f"{Assignment} uses {ShippingCost}", short_name="shipping")
Assignment.x_qty = Property(f"{Assignment} has {Float:qty}")
model.define(Assignment.new(shipping=ShippingCost))

# FCUsage: tracks whether each FC is activated (binary)
FCUsage = Concept("FCUsage")
FCUsage.fc = Property(f"{FCUsage} for {FC}", short_name="fc")
FCUsage.x_used = Property(f"{FCUsage} is {Float:used}")
model.define(FCUsage.new(fc=FC))

AssignmentRef = Assignment.ref()

p = Problem(model, Float)
p.solve_for(Assignment.x_qty, lower=0,
            name=["qty", Assignment.shipping.fc.name, Assignment.shipping.order.customer])
p.solve_for(FCUsage.x_used, type="bin", name=["fc_used", FCUsage.fc.name])

# Constraint: FC capacity
p.satisfy(model.require(
    sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FC).per(FC)
    <= FC.capacity
))

# Constraint: linking — quantity only flows through used FCs
p.satisfy(model.require(
    sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.fc == FCUsage.fc).per(FCUsage)
    <= FCUsage.fc.capacity * FCUsage.x_used
))

# Constraint: each order fully fulfilled (forcing constraint)
p.satisfy(model.require(
    sum(AssignmentRef.x_qty).where(AssignmentRef.shipping.order == Order).per(Order)
    == Order.quantity
))

# Objective: minimize shipping + fixed facility costs
shipping_cost = sum(Assignment.x_qty * Assignment.shipping.cost_per_unit)
fixed_cost = sum(FCUsage.x_used * FCUsage.fc.fixed_cost)
p.minimize(shipping_cost + fixed_cost)

p.solve("highs", time_limit_sec=60)
