# Pattern: Graph algorithm (WCC) feeding rule-based classification.
# Key ideas: multi-concept co-occurrence edges (shared address, phone, email);
# WCC for identity graph communities; Relationship flags for layered rule
# application (is_in_large_group -> is_suspicious);
# rules combine graph results with domain conditions.


from relationalai.semantics import Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

model = Model("chained_graph_rules")

# --- Ontology ---

Address = model.Concept("Address", identify_by={"id": Integer})
Address.street = model.Property(f"{Address} has street {String:street}")
Address.city = model.Property(f"{Address} in city {String:city}")

User = model.Concept("User", identify_by={"id": Integer})
User.name = model.Property(f"{User} has name {String:name}")
User.phone = model.Property(f"{User} has phone {String:phone}")
User.email = model.Property(f"{User} has email {String:email}")
User.address = model.Relationship(f"{User} lives at {Address}")

# --- Sample data ---

address_data = model.data([
    {"id": 1, "street": "123 Fake St", "city": "Springfield"},
    {"id": 2, "street": "456 Elm St", "city": "Springfield"},
    {"id": 3, "street": "789 Oak St", "city": "Springfield"},
    {"id": 4, "street": "101 Pine St", "city": "Shelbyville"},
])
model.define(Address.new(address_data.to_schema()))

user_data = model.data([
    # Cluster 1: shared address + shared email across users
    {"id": 1, "name": "John Doe", "phone": "555-0101", "email": "john@example.com", "address_id": 1},
    {"id": 2, "name": "Jane Smith", "phone": "555-0102", "email": "shared@example.com", "address_id": 2},
    {"id": 3, "name": "Bob Brown", "phone": "555-0103", "email": "bob@example.com", "address_id": 1},
    {"id": 4, "name": "David Evans", "phone": "555-0102", "email": "shared@example.com", "address_id": 1},
    {"id": 5, "name": "Eva Green", "phone": "555-0104", "email": "eva@example.com", "address_id": 2},
    # Cluster 2: isolated pair
    {"id": 6, "name": "Frank White", "phone": "555-0201", "email": "frank@example.com", "address_id": 3},
    {"id": 7, "name": "Grace Lee", "phone": "555-0202", "email": "grace@example.com", "address_id": 3},
    # Isolated user
    {"id": 8, "name": "Henry Wilson", "phone": "555-0301", "email": "henry@example.com", "address_id": 4},
])
model.define(
    User.new(
        user_data.to_schema(exclude=["address_id"]),
        address=Address.filter_by(id=user_data.address_id),
    )
)

# --- Graph construction: multi-concept co-occurrence edges ---
# Users are connected if they share any identity attribute:
# same address, same phone, or same email.

graph = Graph(model, directed=False, weighted=False, node_concept=User, aggregator="sum")

u1, u2 = User.ref(), User.ref()

# Shared address
model.where(
    u1.address == u2.address,
    u1.id < u2.id,
).define(graph.Edge.new(src=u1, dst=u2))

# Shared phone
model.where(
    u1.phone == u2.phone,
    u1.id < u2.id,
).define(graph.Edge.new(src=u1, dst=u2))

# Shared email
model.where(
    u1.email == u2.email,
    u1.id < u2.id,
).define(graph.Edge.new(src=u1, dst=u2))

graph.num_nodes().inspect()
graph.num_edges().inspect()

# --- WCC: identity graph communities ---

graph.Node.community = graph.weakly_connected_component()

groups_df = model.select(User.name, User.community.alias("community")).to_df()

print("=== Identity Graph Communities ===")
for community_id in sorted(groups_df["community"].unique()):
    members = groups_df[groups_df["community"] == community_id]
    print(f"  Community {community_id} ({len(members)} users): {sorted(members['name'].tolist())}")

# --- Rule layer 1: Flag users in uncommonly large communities ---
# Uses Relationship flag — avoids recursion issues with extends[].

LARGE_GROUP_SIZE = 4

User.is_in_large_group = model.Relationship(f"{User} is in a large group")

users_per_community = aggregates.count(User).per(User.community)
model.define(User.is_in_large_group(User)).where(users_per_community >= LARGE_GROUP_SIZE)

large_group_df = (
    model.where(User.is_in_large_group())
    .select(User.name, User.community.alias("community"))
    .to_df()
)
print(f"\n=== Large Group Users ({len(large_group_df)} users) ===")
print(large_group_df.to_string(index=False))

# --- Rule layer 2: Flag suspicious users within large groups ---
# Suspicious = in large group AND (shares email or phone with another member
# at a different address). Layered rules: large group flag feeds suspicious flag.

User.is_suspicious = model.Relationship(f"{User} is suspicious")

u1, u2 = User.ref(), User.ref()
model.define(User.is_suspicious(u1)).where(
    u1.is_in_large_group(),
    u2.is_in_large_group(),
    u1 != u2,
    u1.community == u2.community,
    u1.address != u2.address,
    (u1.email == u2.email) | (u1.phone == u2.phone),
)

# --- Query results ---

suspicious_df = (
    model.where(User.is_suspicious())
    .select(
        User.id,
        User.name,
        User.email,
        User.phone,
        User.address.street.alias("street"),
    )
    .to_df()
    .sort_values("id")
    .reset_index(drop=True)
)

print("\n=== Suspicious Users ===")
print(suspicious_df.to_string(index=False))
