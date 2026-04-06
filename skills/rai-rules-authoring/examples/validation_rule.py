# Pattern: Threshold validation rule — checks credit limit compliance across related entities.
# Key ideas: cross-entity condition using relationship navigation in .where();
# unary Relationship for boolean output; both "valid" and "exceeds" flags defined.

from relationalai.semantics import Float, Integer, Model, String
import relationalai.semantics as rai

model = Model("validation_rule")

# --- Ontology ---

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.credit_limit = model.Property(f"{Customer} has {Float:credit_limit}")

Order = model.Concept("Order", identify_by={"id": Integer})
Order.amount = model.Property(f"{Order} has {Float:amount}")
Order.customer = model.Relationship(f"{Order} placed by {Customer}")

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

total_orders = model.select(aggregates.count(Order)).to_df().iloc[0, 0]
exceeding = model.where(Order.exceeds_credit()).select(
    aggregates.count(Order)
).to_df().iloc[0, 0]
print(f"\nViolations: {exceeding}/{total_orders}")
