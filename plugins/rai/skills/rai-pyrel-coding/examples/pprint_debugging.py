# Pattern: print() for structural debugging of PyRel expressions before execution
"""Example: Using print() for structural debugging of PyRel objects.

All PyRel types have readable repr. Use print() to verify
expression structure before executing queries. Distinct from .inspect()
which materializes data.

Targeted win: exploration and debugging of unfamiliar models — confirming
that expressions, aggregates, and fragments reference the expected concepts
before hitting the server.
"""
from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import aggregates as aggs

model = Model("pprint_debugging")

# -- Concepts --
Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.region = model.Property(f"{Customer} has {String:region}")

Order = model.Concept("Order", identify_by={"id": Integer})
Order.total = model.Property(f"{Order} has {Float:total}")
Order.status = model.Property(f"{Order} has {String:status}")
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")

# -- Concepts print as their name --
print(Customer)        # → Customer
print(Order)           # → Order

# -- Properties print as Concept.property --
print(Customer.name)   # → Customer.name
print(Order.total)     # → Order.total

# -- Expressions show the operation --
print(Order.total > 100)                   # → Order.total > 100
print(Order.total * 1.1)                   # → Order.total * 1.1

# -- Aggregates show grouping structure --
print(aggs.count(Order).per(Customer))     # → (count Order (per Customer))
print(aggs.sum(Order.total).per(Customer)) # → (sum Order.total (per Customer))

# -- Fragments show intent --
frag = model.where(Order.status == "active")
print(frag)                                # → (where Order.status == 'active')

frag2 = model.where(Customer).select(Customer.name, Customer.region)
print(frag2)                               # → (select
                                           #      Customer.name
                                           #      Customer.region
                                           #      (where Customer))

# -- Model shows its name --
print(model)                               # → Model('pprint_demo')

# -- Refs preserve user-supplied names --
c = Customer.ref("c")
print(c)                                   # → Customer.ref('c')

# -- Relationships --
print(Order.customer)                      # → Order.customer
