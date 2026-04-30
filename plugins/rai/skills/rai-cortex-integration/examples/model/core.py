import relationalai.semantics as rai

model = rai.Model("customers_orders")

customer_source = model.data([
    {"id": 1},
    {"id": 2},
    {"id": 3},
    {"id": 4},
])

order_source = model.data([
    {"id": 1, "customer_id": 1, "total": 1.0, "cogs": 0.1},
    {"id": 2, "customer_id": 1, "total": 2.0, "cogs": 0.2},
    {"id": 3, "customer_id": 2, "total": 3.0, "cogs": 0.3},
    {"id": 4, "customer_id": 3, "total": 4.0, "cogs": 0.4},
    {"id": 5, "customer_id": 1, "total": 5.0, "cogs": 0.5},
])

# -- Customer
# ref scheme
Customer = model.Concept("Customer", identify_by={"id": rai.Integer})
model.define(Customer.new(id=customer_source.id))

# -- Order
# ref scheme
Order = model.Concept("Order", identify_by={"id": rai.Integer})
model.define(Order.new(id=order_source.id))
order = model.where(Order.filter_by(id=order_source.id))

# -> Customer
Order.customer = model.Property(f"{Order} was placed by {Customer}")
Customer.order = Order.customer.alt(f"{Customer} placed {Order}")
order.define(
    Order.customer(
        Customer.filter_by(id=order_source.customer_id)))

# facts
Order.price = model.Property(f"{Order} had total price {rai.Float}")
order.define(
    Order.price(order_source.total))
Order.cogs = model.Property(f"{Order} had total cost of goods sold {rai.Float}")
order.define(
    Order.cogs(order_source.cogs))

