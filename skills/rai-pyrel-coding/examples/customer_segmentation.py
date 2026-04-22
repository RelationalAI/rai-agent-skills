# Pattern: graph-based entity segmentation with community detection and derived subtypes
"""Example: Entity segmentation using graph analysis. Suggested reading: https://docs.relational.ai/build/tutorials/meet-pyrel"""
from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

model = Model("customer_segmentation")

# Declare Customer, Product, and Order concepts and their properties
Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has name {String:name}")
Customer.region = model.Property(f"{Customer} has region {String:region}")

Product = model.Concept("Product", identify_by={"id": Integer})
Product.name = model.Property(f"{Product} has name {String:name}")
Product.category = model.Property(f"{Product} in category {String:category}")

Order = model.Concept("Order", identify_by={"id": Integer})
Order.amount = model.Property(f"{Order} has amount {Float:amount}")

# Declare relationships between orders, customers, and products
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")
Order.product = model.Relationship(f"{Order} contains {Product}")

# Declare CustomerSegment and attach segments to customers
CustomerSegment = model.Concept("CustomerSegment", identify_by={"id": Integer})
Customer.segment = model.Property(f"{Customer} belongs to {CustomerSegment:segment}")

# Define sample data (only suitable for small examples)
customer_rows = [
    {"id": 1, "name": "Alice", "region": "North"},
    {"id": 2, "name": "Bob", "region": "North"},
    {"id": 3, "name": "Carol", "region": "South"},
    {"id": 4, "name": "Dan", "region": "South"},
    {"id": 5, "name": "Eve", "region": "West"},
    {"id": 6, "name": "Frank", "region": "West"},
]
product_rows = [
    {"id": 101, "name": "Protein Powder", "category": "Fitness"},
    {"id": 102, "name": "Yoga Mat", "category": "Fitness"},
    {"id": 103, "name": "Wireless Earbuds", "category": "Electronics"},
    {"id": 104, "name": "Smart Watch", "category": "Electronics"},
    {"id": 105, "name": "Espresso Beans", "category": "Food"},
    {"id": 106, "name": "Coffee Grinder", "category": "Food"},
]
order_rows = [
    # Fitness-oriented cluster
    {"id": 1001, "customer_id": 1, "product_id": 101, "amount": 95.0},
    {"id": 1002, "customer_id": 1, "product_id": 102, "amount": 40.0},
    {"id": 1003, "customer_id": 2, "product_id": 101, "amount": 90.0},
    {"id": 1004, "customer_id": 2, "product_id": 102, "amount": 42.0},
    # Electronics-oriented cluster
    {"id": 1005, "customer_id": 3, "product_id": 103, "amount": 160.0},
    {"id": 1006, "customer_id": 3, "product_id": 104, "amount": 240.0},
    {"id": 1007, "customer_id": 4, "product_id": 103, "amount": 155.0},
    {"id": 1008, "customer_id": 4, "product_id": 104, "amount": 235.0},
    # Food-oriented cluster
    {"id": 1009, "customer_id": 5, "product_id": 105, "amount": 24.0},
    {"id": 1010, "customer_id": 5, "product_id": 106, "amount": 130.0},
    {"id": 1011, "customer_id": 6, "product_id": 105, "amount": 28.0},
    {"id": 1012, "customer_id": 6, "product_id": 106, "amount": 125.0},
    # A few cross-cluster purchases to make segmentation realistic
    {"id": 1013, "customer_id": 2, "product_id": 103, "amount": 145.0},
    {"id": 1014, "customer_id": 4, "product_id": 106, "amount": 120.0},
    {"id": 1015, "customer_id": 6, "product_id": 102, "amount": 39.0},
 ]

# Wrap raw rows in model.data() to get table-like objects PyRel can work with
customer_data = model.data(customer_rows)
product_data = model.data(product_rows)
order_data = model.data(order_rows)

# Explicitly map columns to concept properties with keyword arguments
model.define(
    Customer.new(
        id=customer_data.id,
        name=customer_data.name,
        region=customer_data.region,
    )
)

# Implicitly map columns to concept properties with .to_schema()
model.define(Product.new(product_data.to_schema()))

# Define orders with foreign-key style references
model.define(
    Order.new(
        order_data.to_schema(exclude=["customer_id", "product_id"]),
        customer=Customer.filter_by(id=order_data.customer_id),
        product=Product.filter_by(id=order_data.product_id),
    )
)

# Requirement: Every customer and product must have a name.
Customer.require(Customer.name)
Product.require(Product.name)

# Requirement: Every order must have a positive amount.
Order.require(Order.amount > 0.0)

# Create a graph object
graph = Graph(
    model,
    directed=False,
    weighted=True,
    node_concept=Customer,
    aggregator="sum",
)

# Define Edges
left_order = Order.ref()
right_order = Order.ref()

model.where(
    left_order.product == right_order.product,
    left_order.customer.id < right_order.customer.id,
).define(
    graph.Edge.new(
        src=left_order.customer,
        dst=right_order.customer,
        weight=1.0,
    )
)

# Run Louvain and store the label on nodes
graph.Node.community_label = graph.louvain()

# Turn labels into segment entities
model.define(CustomerSegment.new(id=graph.Node.community_label))

# Attach the segment to each customer
model.where(graph.Node == Customer).define(
    Customer.segment(CustomerSegment.filter_by(id=graph.Node.community_label))
)

segment_value = (
    model.where(
        Customer.segment == CustomerSegment,
        Order.customer == Customer,
    )
    .select(
        CustomerSegment.id.alias("segment_id"),
        aggregates.count(distinct(Customer)).per(CustomerSegment).alias("customers"),
        aggregates.count(Order).per(CustomerSegment).alias("orders"),
        aggregates.sum(Order.amount).per(CustomerSegment).alias("revenue"),
        aggregates.avg(Order.amount).per(CustomerSegment).alias("avg_order_value"),
    )
    .to_df()
    .sort_values("revenue", ascending=False)
    .reset_index(drop=True)
)

customer_segment_membership = (
    model.where(Customer.segment(CustomerSegment))
    .select(
        Customer.id.alias("customer_id"),
        Customer.name.alias("customer_name"),
        Customer.region,
        CustomerSegment.id.alias("segment_id"),
    )
    .to_df()
    .sort_values(["segment_id", "customer_id"])
)

print("\nCustomer -> Segment assignments")
print(customer_segment_membership.to_string(index=False))

print("\nSegment value analysis")
print(segment_value.to_string(index=False))