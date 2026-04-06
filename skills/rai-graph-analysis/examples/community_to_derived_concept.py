# Pattern: Louvain community detection with community labels turned into ontology entities.
# Key ideas: co-occurrence graph via shared attribute; id < guard for deduplication;
# community labels become a derived Segment concept; hub identification per community
# via degree centrality; per-segment value aggregation.
# Merged from: community_detection_customers + wildlife_conservation_communities examples

from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

model = Model("community_to_derived_concept")

# --- Ontology ---

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has name {String:name}")
Customer.region = model.Property(f"{Customer} has region {String:region}")

Product = model.Concept("Product", identify_by={"id": Integer})
Product.name = model.Property(f"{Product} has name {String:name}")
Product.category = model.Property(f"{Product} in category {String:category}")

Order = model.Concept("Order", identify_by={"id": Integer})
Order.amount = model.Property(f"{Order} has amount {Float:amount}")
Order.customer = model.Relationship(f"{Order} placed by {Customer}")
Order.product = model.Relationship(f"{Order} contains {Product}")

# Derived concept: community labels become ontology entities
CustomerSegment = model.Concept("CustomerSegment", identify_by={"id": Integer})
Customer.segment = model.Relationship(f"{Customer} belongs to {CustomerSegment}")

# --- Sample data ---

customer_data = model.data([
    {"id": 1, "name": "Alice", "region": "North"},
    {"id": 2, "name": "Bob", "region": "North"},
    {"id": 3, "name": "Carol", "region": "South"},
    {"id": 4, "name": "Dan", "region": "South"},
    {"id": 5, "name": "Eve", "region": "West"},
    {"id": 6, "name": "Frank", "region": "West"},
])
model.define(Customer.new(customer_data.to_schema()))

product_data = model.data([
    {"id": 101, "name": "Protein Powder", "category": "Fitness"},
    {"id": 102, "name": "Yoga Mat", "category": "Fitness"},
    {"id": 103, "name": "Wireless Earbuds", "category": "Electronics"},
    {"id": 104, "name": "Smart Watch", "category": "Electronics"},
    {"id": 105, "name": "Espresso Beans", "category": "Food"},
    {"id": 106, "name": "Coffee Grinder", "category": "Food"},
])
model.define(Product.new(product_data.to_schema()))

order_data = model.data([
    # Fitness cluster: Alice + Bob
    {"id": 1001, "customer_id": 1, "product_id": 101, "amount": 95.0},
    {"id": 1002, "customer_id": 1, "product_id": 102, "amount": 40.0},
    {"id": 1003, "customer_id": 2, "product_id": 101, "amount": 90.0},
    {"id": 1004, "customer_id": 2, "product_id": 102, "amount": 42.0},
    # Electronics cluster: Carol + Dan
    {"id": 1005, "customer_id": 3, "product_id": 103, "amount": 160.0},
    {"id": 1006, "customer_id": 3, "product_id": 104, "amount": 240.0},
    {"id": 1007, "customer_id": 4, "product_id": 103, "amount": 155.0},
    {"id": 1008, "customer_id": 4, "product_id": 104, "amount": 235.0},
    # Food cluster: Eve + Frank
    {"id": 1009, "customer_id": 5, "product_id": 105, "amount": 24.0},
    {"id": 1010, "customer_id": 5, "product_id": 106, "amount": 130.0},
    {"id": 1011, "customer_id": 6, "product_id": 105, "amount": 28.0},
    {"id": 1012, "customer_id": 6, "product_id": 106, "amount": 125.0},
    # Cross-cluster noise
    {"id": 1013, "customer_id": 2, "product_id": 103, "amount": 145.0},
    {"id": 1014, "customer_id": 4, "product_id": 106, "amount": 120.0},
    {"id": 1015, "customer_id": 6, "product_id": 102, "amount": 39.0},
])
model.define(
    Order.new(
        order_data.to_schema(exclude=["customer_id", "product_id"]),
        customer=Customer.filter_by(id=order_data.customer_id),
        product=Product.filter_by(id=order_data.product_id),
    )
)

# --- Graph construction: co-purchase undirected weighted ---

graph = Graph(model, directed=False, weighted=True, node_concept=Customer, aggregator="sum")

left_order, right_order = Order.ref(), Order.ref()
model.where(
    left_order.product == right_order.product,
    left_order.customer.id < right_order.customer.id,  # prevent duplicates + self-loops
).define(
    graph.Edge.new(
        src=left_order.customer,
        dst=right_order.customer,
        weight=1.0,  # each shared product = 1 edge weight unit
    )
)

# --- Run Louvain community detection + degree centrality ---

graph.Node.community_label = graph.louvain()
degree_centrality = graph.degree_centrality()

# --- Turn community labels into segment entities ---

model.define(CustomerSegment.new(id=graph.Node.community_label))

model.where(graph.Node == Customer).define(
    Customer.segment(CustomerSegment.filter_by(id=graph.Node.community_label))
)

# --- Query: customer-segment assignments with hub identification ---

node = graph.Node.ref("node")
dc_score = Float.ref("dc_score")

membership_df = (
    model.where(
        Customer.segment(CustomerSegment),
        degree_centrality(node, dc_score),
        node == Customer,
    )
    .select(
        Customer.id.alias("customer_id"),
        Customer.name.alias("name"),
        Customer.region.alias("region"),
        CustomerSegment.id.alias("segment_id"),
        dc_score.alias("degree_centrality"),
    )
    .to_df()
    .sort_values(["segment_id", "degree_centrality"], ascending=[True, False])
)
membership_df["segment_id"] = membership_df["segment_id"].astype(int)

print("Customer -> Segment Assignments (with degree centrality)")
print(membership_df.to_string(index=False))

# Hub identification per community
for seg_id in sorted(membership_df["segment_id"].unique()):
    seg_df = membership_df[membership_df["segment_id"] == seg_id]
    hub = seg_df.iloc[0]  # highest centrality after sort
    print(f"\nSegment {seg_id}: hub = {hub['name']} (centrality={hub['degree_centrality']:.4f})")
    print(f"  Members: {', '.join(seg_df['name'].tolist())}")

# --- Query: per-segment value analysis ---

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
        aggregates.avg(Order.amount).per(CustomerSegment).alias("avg_order"),
    )
    .to_df()
    .sort_values("revenue", ascending=False)
    .reset_index(drop=True)
)
segment_value["segment_id"] = segment_value["segment_id"].astype(int)

print("\nSegment Value Analysis")
print(segment_value.to_string(index=False))
