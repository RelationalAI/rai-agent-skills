# Pattern: std.datetime arithmetic, enum-subconcept segmentation, argmax tiebreaker
# Key ideas: dt.date.period_days() for date differences; subconcept hierarchy with
# extends=[ParentConcept] for categorical segments; argmax via count().per() → max().per()
# → min(entity).where(count == max) for tiebreaking.

import relationalai.semantics as rai
from relationalai.semantics.std import datetime as dt

model = rai.Model("datetime_argmax_segmentation")

# NOTE: This is a pattern reference, not a standalone script. It assumes an existing
# ontology with Customer, Product, Order, OrderItem concepts already defined.
# Adapt the concept names and properties to your model.

# --- std.datetime arithmetic: customer longevity ---
CustomerLongevityDays = model.Concept("CustomerLongevityDays", extends=[rai.Integer])
Customer = model.Customer  # pre-existing concept
Customer.longevity_days = model.Property(
    f"{Customer} has longevity days {CustomerLongevityDays}")

model.define(
    Customer.longevity_days(
        CustomerLongevityDays(
            dt.date.period_days(
                dt.datetime.to_date(Customer.first_ordered_at),
                dt.datetime.to_date(Customer.last_ordered_at)
            )
        )
    )
)

# --- Enum-subconcept segmentation ---
# Parent concept for all segments
CustomerValueSegment = model.Concept("CustomerValueSegment")
CustomerValueSegmentName = model.Concept("CustomerValueSegmentName", extends=[rai.String])
CustomerValueSegment.name = model.Property(
    f"{CustomerValueSegment} has name {CustomerValueSegmentName}")

# Each segment is a subconcept extending the parent
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentHigh = model.Concept("ValueSegmentHigh", extends=[CustomerValueSegment])
ValueSegmentMedium = model.Concept("ValueSegmentMedium", extends=[CustomerValueSegment])
ValueSegmentLow = model.Concept("ValueSegmentLow", extends=[CustomerValueSegment])

# Create singleton instances
model.define(ValueSegmentVIP.new(name=CustomerValueSegmentName("VIP")))
model.define(ValueSegmentHigh.new(name=CustomerValueSegmentName("High Value")))
model.define(ValueSegmentMedium.new(name=CustomerValueSegmentName("Medium Value")))
model.define(ValueSegmentLow.new(name=CustomerValueSegmentName("Low Value")))

# Assign segments based on score ranges
Customer.value_segment = model.Property(
    f"{Customer} has value segment {CustomerValueSegment}")
model.where(Customer.customer_value_score >= 300).define(
    Customer.value_segment(ValueSegmentVIP))
model.where(
    Customer.customer_value_score >= 150,
    Customer.customer_value_score < 300,
).define(Customer.value_segment(ValueSegmentHigh))

# --- Argmax with tiebreaker: customer's favorite product ---
Customer.favorite_product = model.Relationship(
    f"{Customer} favorite product {model.Product}")

customer = Customer.ref()
product = model.Product.ref()
order = model.Order.ref()
orderitem = model.OrderItem.ref()

# Step 1: count orders per (customer, product) pair
order_count = rai.count(orderitem).per(customer, product).where(
    orderitem.composes_order(order),
    order.ordered_by(customer),
    orderitem.contains_product(product),
)

# Step 2: find the max count per customer
max_count = rai.max(order_count).per(customer)

# Step 3: tiebreak — pick the min-entity product among those with max count
min_entity = rai.min(product).per(customer).where(order_count == max_count)

# Step 4: define the relationship
model.define(customer.favorite_product(product)).where(product == min_entity)
