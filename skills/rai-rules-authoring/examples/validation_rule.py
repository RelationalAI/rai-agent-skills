# Pattern: Threshold validation rule — checks credit limit compliance across related entities.
# Key ideas: cross-entity condition using relationship navigation in .where();
# unary Relationship for boolean output; both "valid" and "exceeds" flags defined.

from relationalai.semantics import Float, Integer, Model, String

model = Model("validation_rule")

# --- Ontology ---

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.credit_limit = model.Property(f"{Customer} has {Float:credit_limit}")

Order = model.Concept("Order", identify_by={"id": Integer})
Order.amount = model.Property(f"{Order} has {Float:amount}")
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")

# --- Sample data ---
customer_source = model.data([
    {"ID": 1, "NAME": "Alice", "CREDIT_LIMIT": 5000.0},
    {"ID": 2, "NAME": "Bob", "CREDIT_LIMIT": 10000.0},
    {"ID": 3, "NAME": "Carol", "CREDIT_LIMIT": 2000.0},
])
order_source = model.data([
    {"ID": 101, "CUSTOMER_ID": 1, "AMOUNT": 3500.0},
    {"ID": 102, "CUSTOMER_ID": 1, "AMOUNT": 6000.0},   # exceeds Alice's 5000 limit
    {"ID": 103, "CUSTOMER_ID": 2, "AMOUNT": 8000.0},
    {"ID": 104, "CUSTOMER_ID": 3, "AMOUNT": 2500.0},   # exceeds Carol's 2000 limit
])
model.define(
    c := Customer.new(id=customer_source.ID),
    c.name(customer_source.NAME),
    c.credit_limit(customer_source.CREDIT_LIMIT),
)
model.define(
    o := Order.new(id=order_source.ID),
    o.amount(order_source.AMOUNT),
)
model.define(Order.customer(Customer)).where(
    Order.filter_by(id=order_source.ID),
    Customer.filter_by(id=order_source.CUSTOMER_ID),
)

# --- Validation Rule ---
# NL: "Flag orders that exceed their customer's credit limit"

# Output: boolean flags on Order (one for each outcome)
Order.exceeds_credit = model.Relationship(f"{Order} exceeds credit limit")
Order.within_credit = model.Relationship(f"{Order} within credit limit")

# Cross-entity validation: compare Order.amount to related Customer.credit_limit
model.where(
    Order.customer(Customer),
    Order.amount > Customer.credit_limit,
).define(Order.exceeds_credit())

model.where(
    Order.customer(Customer),
    Order.amount <= Customer.credit_limit,
).define(Order.within_credit())

# --- Query results ---

print("Orders exceeding credit limit:")
model.where(Order.exceeds_credit()).select(
    Order.id.alias("order_id"),
    Order.amount.alias("amount"),
).inspect()

# --- Coverage check ---

from relationalai.semantics.std import aggregates

total_orders = model.select((aggregates.count(Order) | 0).alias("count")).to_df().iloc[0, 0]
exceeding = model.where(Order.exceeds_credit()).select(
    (aggregates.count(Order) | 0).alias("count")
).to_df().iloc[0, 0]
print(f"\nViolations: {exceeding}/{total_orders}")
