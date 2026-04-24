# Pattern: Jaccard similarity on a co-purchase graph to find structurally similar products.
# Key ideas: undirected unweighted graph from shared-attribute edges (co-purchase);
# jaccard_similarity() for pairwise neighborhood overlap; filter to top-k most similar pairs.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph

model = Model("similarity_jaccard")

# --- Ontology ---

Product = model.Concept("Product", identify_by={"id": Integer})
Product.name = model.Property(f"{Product} has name {String:name}")
Product.category = model.Property(f"{Product} has category {String:category}")

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has name {String:name}")

Purchase = model.Concept("Purchase", identify_by={"id": Integer})
Purchase.customer = model.Relationship(f"{Purchase} made by {Customer}")
Purchase.product = model.Relationship(f"{Purchase} contains {Product}")

# --- Sample data ---

prod_data = model.data([
    {"id": 1, "name": "Laptop", "category": "electronics"},
    {"id": 2, "name": "Mouse", "category": "electronics"},
    {"id": 3, "name": "Keyboard", "category": "electronics"},
    {"id": 4, "name": "Monitor", "category": "electronics"},
    {"id": 5, "name": "Webcam", "category": "electronics"},
    {"id": 6, "name": "Headset", "category": "audio"},
    {"id": 7, "name": "Speakers", "category": "audio"},
    {"id": 8, "name": "Desk Lamp", "category": "office"},
    {"id": 9, "name": "Chair Mat", "category": "office"},
])
model.define(Product.new(prod_data.to_schema()))

cust_data = model.data([
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 3, "name": "Carol"},
    {"id": 4, "name": "Dave"},
    {"id": 5, "name": "Eve"},
    {"id": 6, "name": "Frank"},
])
model.define(Customer.new(cust_data.to_schema()))

purch_data = model.data([
    {"id": 1,  "cust_id": 1, "prod_id": 1},  # Alice: Laptop, Mouse, Keyboard, Monitor
    {"id": 2,  "cust_id": 1, "prod_id": 2},
    {"id": 3,  "cust_id": 1, "prod_id": 3},
    {"id": 4,  "cust_id": 1, "prod_id": 4},
    {"id": 5,  "cust_id": 2, "prod_id": 1},  # Bob: Laptop, Mouse, Headset
    {"id": 6,  "cust_id": 2, "prod_id": 2},
    {"id": 7,  "cust_id": 2, "prod_id": 6},
    {"id": 8,  "cust_id": 3, "prod_id": 1},  # Carol: Laptop, Keyboard, Monitor, Webcam
    {"id": 9,  "cust_id": 3, "prod_id": 3},
    {"id": 10, "cust_id": 3, "prod_id": 4},
    {"id": 11, "cust_id": 3, "prod_id": 5},
    {"id": 12, "cust_id": 4, "prod_id": 2},  # Dave: Mouse, Headset, Speakers
    {"id": 13, "cust_id": 4, "prod_id": 6},
    {"id": 14, "cust_id": 4, "prod_id": 7},
    {"id": 15, "cust_id": 5, "prod_id": 3},  # Eve: Keyboard, Desk Lamp, Chair Mat
    {"id": 16, "cust_id": 5, "prod_id": 8},
    {"id": 17, "cust_id": 5, "prod_id": 9},
    {"id": 18, "cust_id": 6, "prod_id": 4},  # Frank: Monitor, Webcam, Desk Lamp
    {"id": 19, "cust_id": 6, "prod_id": 5},
    {"id": 20, "cust_id": 6, "prod_id": 8},
])
model.define(
    Purchase.new(
        id=purch_data.id,
        customer=Customer.filter_by(id=purch_data.cust_id),
        product=Product.filter_by(id=purch_data.prod_id),
    )
)

# --- Graph construction: co-purchase undirected unweighted ---
# Two products share an edge when the same customer bought both.
# id < guard prevents duplicate/self-loop edges in co-occurrence pattern.
# aggregator="sum" collapses multi-edges from multiple shared customers.

graph = Graph(model, directed=False, weighted=False, node_concept=Product, aggregator="sum")

p1, p2 = Product.ref(), Product.ref()
left_purch, right_purch = Purchase.ref(), Purchase.ref()
model.where(
    left_purch.customer == right_purch.customer,
    left_purch.product(p1),
    right_purch.product(p2),
    p1.id < p2.id,
).define(graph.Edge.new(src=p1, dst=p2))

# --- Run Jaccard similarity ---

n1, n2, score = graph.Node.ref("a"), graph.Node.ref("b"), Float.ref("s")
similarity_df = (
    model.where(graph.jaccard_similarity(full=True)(n1, n2, score))
    .select(
        n1.name.alias("product_a"),
        n2.name.alias("product_b"),
        score.alias("jaccard_score"),
    )
    .to_df()
    .sort_values("jaccard_score", ascending=False)
    .reset_index(drop=True)
)

# --- Display top similar pairs ---

TOP_K = 8
print(f"Top {TOP_K} Most Similar Product Pairs (Jaccard)")
print(similarity_df.head(TOP_K).to_string(index=False))

top_pair = similarity_df.iloc[0]
print(f"\nMost similar: {top_pair['product_a']} <-> {top_pair['product_b']} "
      f"(jaccard={top_pair['jaccard_score']:.4f})")
