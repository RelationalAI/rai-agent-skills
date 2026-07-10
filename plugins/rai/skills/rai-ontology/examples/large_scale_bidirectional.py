"""Large-scale bidirectional — 14 source tables, unary flags, self-referential.

NOTE: Design-only example (requires Snowflake tables). Large-scale reference (14 tables,
12+ concepts) showing unary flags, bidirectional inverses, and role-named self-references.

Patterns: Large-scale modeling (14 tables, 12+ concepts), walrus operator for
compact binding, unary flags from status/boolean columns, bidirectional
relationships with explicit inverses, self-referential relationships
(source/target on same concept), multi-FK binding.
"""
from relationalai.semantics import Date, DateTime, Float, Integer, Model, String

model = Model("Multi-Entity Network")

class Sources:
    class ops_db:
        class raw:
            regional_risk = model.Table("OPS_DB.RAW.REGIONAL_RISK")
            customers = model.Table("OPS_DB.RAW.CUSTOMERS")
            plans_contracts = model.Table("OPS_DB.RAW.PLANS_CONTRACTS")
            billing_events = model.Table("OPS_DB.RAW.BILLING_EVENTS")
            facilities = model.Table("OPS_DB.RAW.FACILITIES")
            parts_inventory = model.Table("OPS_DB.RAW.PARTS_INVENTORY")
            network_equipment = model.Table("OPS_DB.RAW.NETWORK_EQUIPMENT")
            equipment_health = model.Table("OPS_DB.RAW.EQUIPMENT_HEALTH")
            incidents = model.Table("OPS_DB.RAW.INCIDENTS")
            transactions = model.Table("OPS_DB.RAW.TRANSACTIONS")
            supplier_orders = model.Table("OPS_DB.RAW.SUPPLIER_ORDERS")
            campaigns = model.Table("OPS_DB.RAW.CAMPAIGNS")
            promotion_redemptions = model.Table("OPS_DB.RAW.PROMOTION_REDEMPTIONS")
            revenue_forecast = model.Table("OPS_DB.RAW.REVENUE_FORECAST")

raw = Sources.ops_db.raw

# ── Location ────────────────────────────────────────────────────
Location = model.Concept("Location", identify_by={"id": Integer})
Location.region = model.Property(f"{Location} has {String:region}")
Location.flood_risk_index = model.Property(f"{Location} has {Float:flood_risk_index}")
Location.population_density = model.Property(f"{Location} has {Integer:population_density}")

model.define(
    loc := Location.new(id=raw.regional_risk.POSTAL_CODE),
    loc.region(raw.regional_risk.REGION),
    loc.flood_risk_index(raw.regional_risk.FLOOD_RISK_INDEX),
    loc.population_density(raw.regional_risk.POPULATION_DENSITY),
)

# ── Part (with unary flag) ────────────────────────────────────────
Part = model.Concept("Part", identify_by={"id": String})
Part.name = model.Property(f"{Part} has {String:name}")
Part.quantity_on_hand = model.Property(f"{Part} has {Integer:quantity_on_hand}")
Part.unit_cost = model.Property(f"{Part} has {Float:unit_cost}")
Part.stock_status = model.Property(f"{Part} has {String:stock_status}")
Part.is_critical_shortage = model.Relationship(f"{Part} is critical shortage")

model.define(
    p := Part.new(id=raw.parts_inventory.PART_ID),
    p.name(raw.parts_inventory.PART_NAME),
    p.quantity_on_hand(raw.parts_inventory.QUANTITY_ON_HAND),
    p.unit_cost(raw.parts_inventory.UNIT_COST_USD),
    p.stock_status(raw.parts_inventory.STOCK_STATUS),
)
model.define(Part.is_critical_shortage()).where(Part.stock_status == "CRITICAL_SHORTAGE")

# ── Customer (bidirectional FK to Location) ───────────────────
Customer = model.Concept("Customer", identify_by={"id": String})
Customer.segment = model.Property(f"{Customer} has {String:segment}")
Customer.lifetime_value = model.Property(f"{Customer} has {Float:lifetime_value}")
Customer.churn_risk_score = model.Property(f"{Customer} has {Float:churn_risk_score}")
Customer.located_in = model.Relationship(
    f"{Customer} located in {Location}")
Location.has_customer = model.Relationship(
    f"{Location} has customer {Customer}")

model.define(
    s := Customer.new(id=raw.customers.CUST_ID),
    s.segment(raw.customers.SEGMENT),
    s.lifetime_value(raw.customers.LIFETIME_VALUE_USD),
    s.churn_risk_score(raw.customers.CHURN_RISK_SCORE),
)
customer = Customer.ref()
location = Location.ref()
model.define(customer.located_in(location)).where(
    customer.lookup(id=raw.customers.CUST_ID),
    location.lookup(id=raw.customers.POSTAL_CODE),
)
location = Location.ref()
customer = Customer.ref()
model.define(location.has_customer(customer)).where(
    location.lookup(id=raw.customers.POSTAL_CODE),
    customer.lookup(id=raw.customers.CUST_ID),
)

# ── Contract (unary flag from boolean column) ─────────────────────
Contract = model.Concept("Contract", identify_by={"id": String})
Contract.monthly_rate = model.Property(f"{Contract} has {Float:monthly_rate}")
Contract.for_customer = model.Relationship(
    f"{Contract} for customer {Customer}")
Contract.is_auto_renew = model.Relationship(f"{Contract} is auto renew")

model.define(
    c := Contract.new(id=raw.plans_contracts.CONTRACT_ID),
    c.monthly_rate(raw.plans_contracts.MONTHLY_RATE),
)
contract = Contract.ref()
customer = Customer.ref()
model.define(contract.for_customer(customer)).where(
    contract.lookup(id=raw.plans_contracts.CONTRACT_ID),
    customer.lookup(id=raw.plans_contracts.CUST_ID),
)
contract = Contract.ref()
model.define(contract.is_auto_renew()).where(
    contract.lookup(id=raw.plans_contracts.CONTRACT_ID),
    raw.plans_contracts.AUTO_RENEW == "True",
)

# ── Facility ─────────────────────────────────────────────────────
Facility = model.Concept("Facility", identify_by={"id": String})
Facility.capacity_gbps = model.Property(f"{Facility} has {Integer:capacity_gbps}")
Facility.located_in = model.Relationship(
    f"{Facility} located in {Location}")

model.define(
    ct := Facility.new(id=raw.facilities.FACILITY_ID),
    ct.capacity_gbps(raw.facilities.CAPACITY_GBPS),
)
facility = Facility.ref()
location = Location.ref()
model.define(facility.located_in(location)).where(
    facility.lookup(id=raw.facilities.FACILITY_ID),
    location.lookup(id=raw.facilities.POSTAL_CODE),
)

# ── Transaction (self-referential: source + target → Customer) ──
Transaction = model.Concept("Transaction", identify_by={"id": String})
Transaction.duration_seconds = model.Property(
    f"{Transaction} has {Integer:duration_seconds}")
Transaction.source = model.Relationship(
    f"{Transaction} has source {Customer}")
Transaction.target = model.Relationship(
    f"{Transaction} has target {Customer}")
Transaction.routed_through = model.Relationship(
    f"{Transaction} routed through {Facility}")
Transaction.is_failed = model.Relationship(f"{Transaction} is failed")
Customer.sent_transaction = model.Relationship(
    f"{Customer} sent transaction {Transaction}")
Customer.received_transaction = model.Relationship(
    f"{Customer} received transaction {Transaction}")

model.define(
    txn := Transaction.new(id=raw.transactions.TXN_ID),
    txn.duration_seconds(raw.transactions.DURATION_SECONDS),
)
transaction = Transaction.ref()
customer = Customer.ref()
model.define(transaction.source(customer)).where(
    transaction.lookup(id=raw.transactions.TXN_ID),
    customer.lookup(id=raw.transactions.SOURCE_CUST_ID),
)
transaction = Transaction.ref()
customer = Customer.ref()
model.define(transaction.target(customer)).where(
    transaction.lookup(id=raw.transactions.TXN_ID),
    customer.lookup(id=raw.transactions.TARGET_CUST_ID),
)
transaction = Transaction.ref()
model.define(transaction.is_failed()).where(
    transaction.lookup(id=raw.transactions.TXN_ID),
    raw.transactions.STATUS == "FAILED",
)

# ── Incident (unary flag from event type) ─────────────────────
Incident = model.Concept("Incident", identify_by={"id": String})
Incident.severity = model.Property(f"{Incident} has {String:severity}")
Incident.is_outage = model.Relationship(f"{Incident} is outage")

model.define(
    ne := Incident.new(id=raw.incidents.EVENT_ID),
    ne.severity(raw.incidents.SEVERITY),
)
incident = Incident.ref()
model.define(incident.is_outage()).where(
    incident.lookup(id=raw.incidents.EVENT_ID),
    raw.incidents.EVENT_TYPE == "OUTAGE",
)
