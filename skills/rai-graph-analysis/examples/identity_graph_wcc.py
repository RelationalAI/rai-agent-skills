# Pattern: Self-join edge construction for identity graphs + WCC community detection
# Key ideas: User.ref() creates a second variable over the same concept for self-join
# comparisons; shared-identifier edges (phone, email) are built without an explicit
# edge table; WCC groups users into identity clusters for ring/fraud detection.

from relationalai.semantics import Integer, Model, String
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates

model = Model("identity_graph_wcc")

# --- Ontology ---

User = model.Concept("User", identify_by={"id": Integer})
User.name = model.Property(f"{User} has name {String:name}")
User.phone = model.Property(f"{User} has phone {String:phone}")
User.email = model.Property(f"{User} has email {String:email}")
User.address = model.Property(f"{User} has address {String:address}")

# --- Sample data ---
# Three clusters of overlapping identifiers:
#   Cluster A (ids 1-4): shared phones/emails across different addresses
#   Cluster B (ids 5-7): shared phone + email pair
#   Cluster C (ids 8-9): single shared phone
#   Isolated  (id 10):   no overlap with anyone

user_data = model.data([
    # -- Cluster A: fraud ring sharing phone 555-0001 and email chains --
    {"id": 1, "name": "Alice Martin",   "phone": "555-0001", "email": "a.martin@mail.com",  "address": "100 Oak St"},
    {"id": 2, "name": "A. Martin",      "phone": "555-0001", "email": "amartin@webmail.com", "address": "200 Pine Ave"},
    {"id": 3, "name": "Alice M.",       "phone": "555-0099", "email": "amartin@webmail.com", "address": "300 Elm Dr"},
    {"id": 4, "name": "Al Martin",      "phone": "555-0099", "email": "al.m@mail.com",       "address": "100 Oak St"},
    # -- Cluster B: small ring --
    {"id": 5, "name": "Bob Jones",      "phone": "555-0002", "email": "bjones@mail.com",     "address": "400 Maple Ln"},
    {"id": 6, "name": "Robert Jones",   "phone": "555-0002", "email": "r.jones@mail.com",    "address": "500 Cedar Ct"},
    {"id": 7, "name": "R. Jones",       "phone": "555-0003", "email": "bjones@mail.com",     "address": "600 Birch Rd"},
    # -- Cluster C: pair --
    {"id": 8, "name": "Carol Smith",    "phone": "555-0004", "email": "carol@mail.com",      "address": "700 Spruce St"},
    {"id": 9, "name": "C. Smith",       "phone": "555-0004", "email": "csmith@mail.com",     "address": "800 Walnut Ave"},
    # -- Isolated user --
    {"id": 10, "name": "Dan Lee",       "phone": "555-0005", "email": "dan@mail.com",        "address": "900 Ash Blvd"},
])
model.define(User.new(user_data.to_schema()))

# --- Graph: self-join edge construction ---
# The key technique: User.ref() creates a second variable bound to the same
# concept. Comparing properties across User and Other, with User != Other,
# produces edges between distinct users sharing an identifier -- no separate
# edge table needed.

graph = Graph(model, directed=False, weighted=False)

Other = User.ref()

# Edge: users sharing the same phone number
model.where(User.phone == Other.phone, User != Other).define(
    graph.Edge.new(src=User, dst=Other),
)

# Edge: users sharing the same email
model.where(User.email == Other.email, User != Other).define(
    graph.Edge.new(src=User, dst=Other),
)

# --- WCC community detection ---

User.community = graph.weakly_connected_component()

# --- Flag large communities (3+ members) ---

LARGE_GROUP_SIZE = 3

LargeGroupUser = model.Concept("LargeGroupUser", extends=[User])
community_size = aggregates.count(User).per(User.community)
model.define(LargeGroupUser(User)).where(community_size >= LARGE_GROUP_SIZE)

# --- Suspicious users: same community, shared identifier, different address ---

SuspiciousUser = model.Concept("SuspiciousUser", extends=[User])

peer = LargeGroupUser.ref()
model.define(SuspiciousUser(LargeGroupUser)).where(
    LargeGroupUser(peer),
    LargeGroupUser != peer,
    LargeGroupUser.community == peer.community,
    LargeGroupUser.address != peer.address,
    (LargeGroupUser.email == peer.email) | (LargeGroupUser.phone == peer.phone),
)

# --- Query: all communities ---

print("=== Identity Communities (WCC) ===\n")

community_df = (
    model.select(
        User.name.alias("name"),
        User.phone.alias("phone"),
        User.email.alias("email"),
        User.address.alias("address"),
        User.community.alias("community"),
    )
    .to_df()
    .sort_values(["community", "name"])
    .reset_index(drop=True)
)

for cid, group in community_df.groupby("community"):
    members = group["name"].tolist()
    if len(members) >= 2:
        print(f"Community {cid} ({len(members)} members): {members}")

# --- Query: suspicious users in large communities ---

print("\n=== Suspicious Users (large community + shared id + different address) ===\n")

suspicious_df = (
    model.select(
        SuspiciousUser.id.alias("id"),
        SuspiciousUser.name.alias("name"),
        SuspiciousUser.phone.alias("phone"),
        SuspiciousUser.email.alias("email"),
        SuspiciousUser.address.alias("address"),
        SuspiciousUser.community.alias("community"),
    )
    .to_df()
    .sort_values(["community", "id"])
    .reset_index(drop=True)
)

print(suspicious_df.to_string(index=False))
print(f"\nTotal suspicious users: {len(suspicious_df)}")
