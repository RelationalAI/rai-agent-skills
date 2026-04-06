# Pattern: cross-entity alerting — flag entities based on conditions spanning multiple concepts
# Key ideas: Relationship traversal in .where() joins across concepts; conditions combine
# properties from the subject entity AND related entities; multiple define() calls yield
# OR semantics (entity flagged if ANY branch matches). Also shows proportional comparison
# (actual vs target ratio).

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates

model = Model("cross_entity_alerting")

# --- Ontology (inline) ---
Supplier = model.Concept("Supplier", identify_by={"id": String})
Supplier.name = model.Property(f"{Supplier} has {String:name}")
Supplier.reliability_score = model.Property(f"{Supplier} has {Float:reliability_score}")

Customer = model.Concept("Customer", identify_by={"id": String})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.tier = model.Property(f"{Customer} has {String:tier}")

Order = model.Concept("Order", identify_by={"id": String})
Order.quantity = model.Property(f"{Order} has {Integer:quantity}")
Order.fulfilled_quantity = model.Property(f"{Order} has {Integer:fulfilled_quantity}")
Order.status = model.Property(f"{Order} has {String:status}")
Order.supplier = model.Relationship(f"{Order} supplied by {Supplier}")
Order.customer = model.Relationship(f"{Order} placed by {Customer}")

# --- Rule 1: Cross-entity alert (join through relationship) ---
# Flag orders where the supplier has low reliability AND the customer is high-tier
Order.is_at_risk = model.Relationship(f"{Order} is at risk")
model.where(
    Order.status != "DELIVERED",
    Order.supplier(Supplier),
    Supplier.reliability_score < 0.8,
    Order.customer(Customer),
    Customer.tier == "PREMIUM",
).define(Order.is_at_risk())

# --- Rule 2: Disjunctive (OR) alert — multiple define() calls ---
# Also flag if fulfillment is below 50% of requested (proportional comparison)
model.where(
    Order.quantity > 0,
    Order.fulfilled_quantity < Order.quantity * 0.5,
).define(Order.is_at_risk())

# An order is at risk if EITHER condition holds (OR semantics from two define() calls)

# --- Query flagged orders with context from related entities ---
df = model.select(
    Order.id.alias("order_id"),
    Supplier.name.alias("supplier"),
    Customer.name.alias("customer"),
    Order.quantity.alias("qty"),
    Order.fulfilled_quantity.alias("fulfilled"),
).where(
    Order.is_at_risk(),
    Order.supplier(Supplier),
    Order.customer(Customer),
).to_df()
