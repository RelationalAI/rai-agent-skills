# NOTE: Extends beyond the starter build (see rai-build-starter-ontology examples)
# with derived metrics (revenue, late delivery) and layered composition on the base model.
# Pattern: multi-level hierarchy + compound-identity junction + derived metrics layered on a base model
# Key ideas: a chain of Relationships (A → B → C → D) encodes a multi-level hierarchy;
# compound identity (identify_by={"parent_a": ConceptA, "parent_b": ConceptB}) gives a natural
# many-to-many junction concept; `.new()` with inline FK kwargs loads identity + relationships
# in one call; derived properties layer on top of the base model.
# Best practices: Property for scalars and functional FKs; Relationship for multi-valued links.
# Illustrated with a supply chain (Region → Nation → Supplier/Customer, PartSupply junction,
# revenue and late-delivery derived metrics).

from relationalai.semantics import Date, Float, Integer, Model, String

model = Model("TPC-H")

# --- Sample Data ---
region_src = model.data([
    {"R_REGIONKEY": 0, "R_NAME": "AFRICA"},
    {"R_REGIONKEY": 1, "R_NAME": "AMERICA"},
])
nation_src = model.data([
    {"N_NATIONKEY": 0, "N_NAME": "ALGERIA", "N_REGIONKEY": 0},
    {"N_NATIONKEY": 1, "N_NAME": "ARGENTINA", "N_REGIONKEY": 1},
])
part_supply_src = model.data([
    {"PS_PARTKEY": 1, "PS_SUPPKEY": 10, "PS_AVAILQTY": 500, "PS_SUPPLYCOST": 12.50},
    {"PS_PARTKEY": 2, "PS_SUPPKEY": 10, "PS_AVAILQTY": 200, "PS_SUPPLYCOST": 8.75},
])
line_item_src = model.data([
    {"L_ORDERKEY": 1, "L_LINENUMBER": 1, "L_PARTKEY": 1, "L_SUPPKEY": 10,
     "L_QUANTITY": 17.0, "L_EXTENDEDPRICE": 212.50, "L_DISCOUNT": 0.04,
     "L_COMMITDATE": "1996-03-13", "L_RECEIPTDATE": "1996-03-22"},
    {"L_ORDERKEY": 1, "L_LINENUMBER": 2, "L_PARTKEY": 2, "L_SUPPKEY": 10,
     "L_QUANTITY": 36.0, "L_EXTENDEDPRICE": 315.00, "L_DISCOUNT": 0.09,
     "L_COMMITDATE": "1996-04-12", "L_RECEIPTDATE": "1996-04-01"},
])

# --- Value-Type IDs ---
RegionId = model.Concept("RegionId", extends=[Integer])
NationId = model.Concept("NationId", extends=[Integer])
PartId = model.Concept("PartId", extends=[Integer])
SupplierId = model.Concept("SupplierId", extends=[Integer])
OrderId = model.Concept("OrderId", extends=[Integer])

# --- Geographic Hierarchy: Region → Nation ---
Region = model.Concept("Region", identify_by={"id": RegionId})
Region.name = model.Property(f"{Region} has {String:name}")

Nation = model.Concept("Nation", identify_by={"id": NationId})
Nation.name = model.Property(f"{Nation} has {String:name}")
Nation.region = model.Relationship(
    f"{Nation} is within {Region}", short_name="nation_region")

model.define(Region.new(id=region_src.R_REGIONKEY, name=region_src.R_NAME))
model.define(Nation.new(
    id=nation_src.N_NATIONKEY,
    name=nation_src.N_NAME,
    region=Region.filter_by(id=nation_src.N_REGIONKEY),
))

# --- Core Concepts (referenced by PartSupply and LineItem) ---
Part = model.Concept("Part", identify_by={"id": PartId})
Supplier = model.Concept("Supplier", identify_by={"id": SupplierId})
Order = model.Concept("Order", identify_by={"id": OrderId})

# --- PartSupply: compound identity junction ---
PartSupply = model.Concept("PartSupply", identify_by={
    "part_id": PartId,
    "supplier_id": SupplierId,
})
PartSupply.part = model.Relationship(
    f"{PartSupply} supplies {Part}", short_name="part_supply_part")
PartSupply.supplier = model.Relationship(
    f"{PartSupply} is from {Supplier}", short_name="part_supply_supplier")
PartSupply.available_quantity = model.Property(
    f"{PartSupply} has {Integer:available_quantity}")
PartSupply.cost = model.Property(f"{PartSupply} has {Float:cost}")

model.define(PartSupply.new(
    part_id=part_supply_src.PS_PARTKEY,
    supplier_id=part_supply_src.PS_SUPPKEY,
    part=Part.filter_by(id=part_supply_src.PS_PARTKEY),
    supplier=Supplier.filter_by(id=part_supply_src.PS_SUPPKEY),
    available_quantity=part_supply_src.PS_AVAILQTY,
    cost=part_supply_src.PS_SUPPLYCOST,
))

# --- LineItem: compound identity + multi-FK relationships ---
LineItem = model.Concept("LineItem", identify_by={
    "order_id": OrderId,
    "line_number": Integer,
})
LineItem.order = model.Relationship(
    f"{LineItem} belongs to {Order}", short_name="line_item_order")
LineItem.part = model.Relationship(
    f"{LineItem} contains {Part}", short_name="line_item_part")
LineItem.supplier = model.Relationship(
    f"{LineItem} supplied by {Supplier}", short_name="line_item_supplier")
LineItem.quantity = model.Property(f"{LineItem} has {Float:quantity}")
LineItem.extended_price = model.Property(f"{LineItem} has {Float:extended_price}")
LineItem.discount = model.Property(f"{LineItem} has {Float:discount}")
LineItem.commit_date = model.Property(f"{LineItem} has {Date:commit_date}")
LineItem.receipt_date = model.Property(f"{LineItem} has {Date:receipt_date}")

model.define(LineItem.new(
    order_id=line_item_src.L_ORDERKEY,
    line_number=line_item_src.L_LINENUMBER,
    order=Order.filter_by(id=line_item_src.L_ORDERKEY),
    part=Part.filter_by(id=line_item_src.L_PARTKEY),
    supplier=Supplier.filter_by(id=line_item_src.L_SUPPKEY),
    quantity=line_item_src.L_QUANTITY,
    extended_price=line_item_src.L_EXTENDEDPRICE,
    discount=line_item_src.L_DISCOUNT,
))

# --- Derived: revenue = extended_price * (1 - discount) ---
LineItem.revenue = model.Property(f"{LineItem} has {Float:revenue}")
model.define(LineItem.revenue(
    LineItem.extended_price * (1 - LineItem.discount)
))

# --- Derived: conditional flag from date comparison ---
LineItem.delivered_late = model.Relationship(f"{LineItem} was delivered late")
model.where(
    Date(LineItem.commit_date) < Date(LineItem.receipt_date),
).define(LineItem.delivered_late())
