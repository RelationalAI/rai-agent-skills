# Pattern: value-type IDs + FK-resolved relationships + computed properties over child entities
# Key ideas: value-type concepts (CustomerId, OrderId) extend primitives for type-safe
# identity; FK navigation uses filter_by(id=source.COL); boolean source columns become
# unary Relationships with conditional .where(); computed metrics are defined as
# expressions over child entities.
# Best practices: Property for scalars, Relationship for concept-to-concept links.
# Illustrated with a Jaffle Shop e-commerce model (customers, orders, line items).

from relationalai.semantics import Float, Integer, Model, String, sum

model = Model("Jaffle Shop")

# --- Sample Data ---
order_source = model.data([
    {"ORDER_ID": "O1", "CUSTOMER_ID": "C1", "ORDER_TOTAL": 42.0, "IS_DRINK_ORDER": True},
    {"ORDER_ID": "O2", "CUSTOMER_ID": "C2", "ORDER_TOTAL": 95.0, "IS_DRINK_ORDER": False},
    {"ORDER_ID": "O3", "CUSTOMER_ID": "C1", "ORDER_TOTAL": 18.5, "IS_DRINK_ORDER": True},
])
customer_source = model.data([
    {"CUSTOMER_ID": "C1", "CUSTOMER_NAME": "Alice", "LIFETIME_SPEND": 350.0},
    {"CUSTOMER_ID": "C2", "CUSTOMER_NAME": "Bob", "LIFETIME_SPEND": 200.0},
])
supply_source = model.data([
    {"ITEM_ID": "SI1", "PRODUCT_ID": "P1", "ITEM_COST": 3.50},
    {"ITEM_ID": "SI2", "PRODUCT_ID": "P1", "ITEM_COST": 1.25},
    {"ITEM_ID": "SI3", "PRODUCT_ID": "P2", "ITEM_COST": 7.00},
])

# --- Value-Type IDs ---
CustomerId = model.Concept("CustomerId", extends=[String])
OrderId = model.Concept("OrderId", extends=[String])
ProductId = model.Concept("ProductId", extends=[String])
SupplyItemId = model.Concept("SupplyItemId", extends=[String])

# --- Concepts ---
Customer = model.Concept("Customer", identify_by={"id": CustomerId})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.lifetime_spend = model.Property(f"{Customer} has {Float:lifetime_spend}")

Order = model.Concept("Order", identify_by={"id": OrderId})
Order.total = model.Property(f"{Order} has {Float:total}")

# --- Relationships ---
Order.ordered_by = model.Relationship(
    f"{Order} ordered by {Customer}", short_name="order_ordered_by")
Customer.placed_order = model.Relationship(
    f"{Customer} placed order {Order}", short_name="customer_placed_order")
Order.is_drink_order = model.Relationship(f"{Order} is drink order")

# --- Data Loading: Customer ---
model.define(Customer.new(id=customer_source.CUSTOMER_ID))
model.define(
    Customer.filter_by(id=customer_source.CUSTOMER_ID).name(customer_source.CUSTOMER_NAME),
    Customer.filter_by(id=customer_source.CUSTOMER_ID).lifetime_spend(customer_source.LIFETIME_SPEND),
)

# --- Data Loading: Order ---
model.define(Order.new(id=order_source.ORDER_ID))
model.define(
    Order.filter_by(id=order_source.ORDER_ID).total(order_source.ORDER_TOTAL),
    Order.filter_by(id=order_source.ORDER_ID).ordered_by(
        Customer.filter_by(id=order_source.CUSTOMER_ID)),
)

# Inverse binding
model.define(
    Customer.filter_by(id=order_source.CUSTOMER_ID).placed_order(
        Order.filter_by(id=order_source.ORDER_ID))
)

# Boolean source column → unary Relationship with conditional .where()
model.where(
    Order.filter_by(id=order_source.ORDER_ID),
    order_source.IS_DRINK_ORDER == True,
).define(Order.is_drink_order())

# --- Computed Properties ---

# Product.cost = sum of its SupplyItem costs
Product = model.Concept("Product", identify_by={"id": ProductId})
Product.cost = model.Property(f"{Product} has {Float:cost}")

SupplyItem = model.Concept("SupplyItem", identify_by={"id": SupplyItemId})
SupplyItem.cost = model.Property(f"{SupplyItem} has {Float:cost}")
SupplyItem.composes_product = model.Relationship(
    f"{SupplyItem} composes {Product}", short_name="supply_item_composes_product")

model.define(SupplyItem.new(id=supply_source.ITEM_ID))
supply_item = SupplyItem.filter_by(id=supply_source.ITEM_ID)
model.define(
    supply_item.cost(supply_source.ITEM_COST),
    supply_item.composes_product(
        Product.filter_by(id=supply_source.PRODUCT_ID)),
)

# Aggregate over child entities
model.where(SupplyItem.composes_product(Product)).define(
    Product.cost(sum(SupplyItem.cost).per(Product))
)

# --- Customer Value Segments ---
CustomerValueSegment = model.Concept("CustomerValueSegment")
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentHigh = model.Concept("ValueSegmentHigh", extends=[CustomerValueSegment])

Customer.value_segment = model.Property(
    f"{Customer} has value segment {CustomerValueSegment}")
Customer.customer_value_score = model.Property(
    f"{Customer} has {Float:customer_value_score}")

model.where(Customer.customer_value_score >= 300).define(
    Customer.value_segment(ValueSegmentVIP)
)
model.where(
    Customer.customer_value_score >= 150,
    Customer.customer_value_score < 300,
).define(Customer.value_segment(ValueSegmentHigh))
