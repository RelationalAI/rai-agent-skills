import relationalai.semantics as rai

model = rai.Model("customers_orders")

customer_source = model.Table("EXAMPLE.SOURCES.CUSTOMERS")
order_source = model.Table("EXAMPLE.SOURCES.ORDERS")

# -- Customer
# ref scheme
Customer = model.Concept("Customer", identify_by={"id": rai.Integer})
model.define(Customer.new(id=customer_source.id))

# -- Order
# ref scheme
Order = model.Concept("Order", identify_by={"id": rai.Integer})
model.define(Order.new(id=order_source.id))
o = Order.ref()
order = model.where(o.lookup(id=order_source.id))

# -> Customer
Order.customer = model.Property(f"{Order} was placed by {Customer}")
Customer.order = Order.customer.alt(f"{Customer} placed {Order}")
order.define(
    o.customer(
        Customer.lookup(id=order_source.customer_id)))

# facts
Order.price = model.Property(f"{Order} had total price {rai.Float}")
order.define(
    o.price(order_source.total))
Order.cogs = model.Property(f"{Order} had total cost of goods sold {rai.Float}")
order.define(
    o.cogs(order_source.cogs))
