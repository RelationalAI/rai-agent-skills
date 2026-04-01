"""Telco Network — Large-scale model, 14 source tables, unary flags, self-referential.

NOTE: Large-scale reference (14 tables, 12+ concepts) showing unary flags, bidirectional
inverses, and role-named self-references — advanced patterns beyond the starter build.

Patterns: Large-scale modeling (14 tables, 12+ concepts), walrus operator for
compact binding, unary flags from status/boolean columns, bidirectional
relationships with explicit inverses, self-referential relationships
(caller/callee on same concept), multi-FK binding.
"""
from relationalai.semantics import Date, DateTime, Float, Integer, Model, String

model = Model("Telco Network")

class Sources:
    class telco_data:
        class raw:
            regional_risk = model.Table("TELCO_DATA.RAW.REGIONAL_RISK")
            subscribers = model.Table("TELCO_DATA.RAW.SUBSCRIBERS")
            plans_contracts = model.Table("TELCO_DATA.RAW.PLANS_CONTRACTS")
            billing_events = model.Table("TELCO_DATA.RAW.BILLING_EVENTS")
            cell_towers = model.Table("TELCO_DATA.RAW.CELL_TOWERS")
            parts_inventory = model.Table("TELCO_DATA.RAW.PARTS_INVENTORY")
            network_equipment = model.Table("TELCO_DATA.RAW.NETWORK_EQUIPMENT")
            equipment_health = model.Table("TELCO_DATA.RAW.EQUIPMENT_HEALTH")
            network_events = model.Table("TELCO_DATA.RAW.NETWORK_EVENTS")
            call_detail_records = model.Table("TELCO_DATA.RAW.CALL_DETAIL_RECORDS")
            supplier_orders = model.Table("TELCO_DATA.RAW.SUPPLIER_ORDERS")
            campaigns = model.Table("TELCO_DATA.RAW.CAMPAIGNS")
            promotion_redemptions = model.Table("TELCO_DATA.RAW.PROMOTION_REDEMPTIONS")
            revenue_forecast = model.Table("TELCO_DATA.RAW.REVENUE_FORECAST")

raw = Sources.telco_data.raw

# ── PostalArea ────────────────────────────────────────────────────
PostalArea = model.Concept("PostalArea", identify_by={"id": Integer})
PostalArea.region = model.Property(f"{PostalArea} has {String:region}")
PostalArea.flood_risk_index = model.Property(f"{PostalArea} has {Float:flood_risk_index}")
PostalArea.population_density = model.Property(f"{PostalArea} has {Integer:population_density}")

model.define(
    pa := PostalArea.new(id=raw.regional_risk.POSTAL_CODE),
    pa.region(raw.regional_risk.REGION),
    pa.flood_risk_index(raw.regional_risk.FLOOD_RISK_INDEX),
    pa.population_density(raw.regional_risk.POPULATION_DENSITY),
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

# ── Subscriber (bidirectional FK to PostalArea) ───────────────────
Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.segment = model.Property(f"{Subscriber} has {String:segment}")
Subscriber.lifetime_value = model.Property(f"{Subscriber} has {Float:lifetime_value}")
Subscriber.churn_risk_score = model.Property(f"{Subscriber} has {Float:churn_risk_score}")
Subscriber.located_in = model.Relationship(
    f"{Subscriber} located in {PostalArea}", short_name="subscriber_located_in")
PostalArea.has_subscriber = model.Relationship(
    f"{PostalArea} has subscriber {Subscriber}", short_name="postal_area_has_subscriber")

model.define(
    s := Subscriber.new(id=raw.subscribers.SUB_ID),
    s.segment(raw.subscribers.SEGMENT),
    s.lifetime_value(raw.subscribers.LIFETIME_VALUE_USD),
    s.churn_risk_score(raw.subscribers.CHURN_RISK_SCORE),
)
model.define(Subscriber.located_in(PostalArea)).where(
    Subscriber.filter_by(id=raw.subscribers.SUB_ID),
    PostalArea.filter_by(id=raw.subscribers.POSTAL_CODE),
)
model.define(PostalArea.has_subscriber(Subscriber)).where(
    PostalArea.filter_by(id=raw.subscribers.POSTAL_CODE),
    Subscriber.filter_by(id=raw.subscribers.SUB_ID),
)

# ── Contract (unary flag from boolean column) ─────────────────────
Contract = model.Concept("Contract", identify_by={"id": String})
Contract.monthly_rate = model.Property(f"{Contract} has {Float:monthly_rate}")
Contract.for_subscriber = model.Relationship(
    f"{Contract} for subscriber {Subscriber}", short_name="contract_for_subscriber")
Contract.is_auto_renew = model.Relationship(f"{Contract} is auto renew")

model.define(Contract.is_auto_renew()).where(
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
    raw.plans_contracts.AUTO_RENEW == "True",
)

# ── CellTower ─────────────────────────────────────────────────────
CellTower = model.Concept("CellTower", identify_by={"id": String})
CellTower.capacity_gbps = model.Property(f"{CellTower} has {Integer:capacity_gbps}")
CellTower.located_in = model.Relationship(
    f"{CellTower} located in {PostalArea}", short_name="cell_tower_located_in")

# ── CallDetailRecord (self-referential: caller + callee → Subscriber) ──
CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.duration_seconds = model.Property(
    f"{CallDetailRecord} has {Integer:duration_seconds}")
CallDetailRecord.caller = model.Relationship(
    f"{CallDetailRecord} has caller {Subscriber}", short_name="cdr_caller")
CallDetailRecord.callee = model.Relationship(
    f"{CallDetailRecord} has callee {Subscriber}", short_name="cdr_callee")
CallDetailRecord.routed_through = model.Relationship(
    f"{CallDetailRecord} routed through {CellTower}", short_name="cdr_routed_through")
CallDetailRecord.is_dropped = model.Relationship(f"{CallDetailRecord} is dropped")
Subscriber.made_call = model.Relationship(
    f"{Subscriber} made call {CallDetailRecord}", short_name="subscriber_made_call")
Subscriber.received_call = model.Relationship(
    f"{Subscriber} received call {CallDetailRecord}", short_name="subscriber_received_call")

model.define(CallDetailRecord.caller(Subscriber)).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    Subscriber.filter_by(id=raw.call_detail_records.CALLER_SUB_ID),
)
model.define(CallDetailRecord.callee(Subscriber)).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    Subscriber.filter_by(id=raw.call_detail_records.CALLEE_SUB_ID),
)
model.define(CallDetailRecord.is_dropped()).where(
    CallDetailRecord.filter_by(id=raw.call_detail_records.CDR_ID),
    raw.call_detail_records.CALL_STATUS == "DROPPED",
)

# ── NetworkEvent (unary flag from event type) ─────────────────────
NetworkEvent = model.Concept("NetworkEvent", identify_by={"id": String})
NetworkEvent.severity = model.Property(f"{NetworkEvent} has {String:severity}")
NetworkEvent.is_outage = model.Relationship(f"{NetworkEvent} is outage")

model.define(NetworkEvent.is_outage()).where(
    NetworkEvent.filter_by(id=raw.network_events.EVENT_ID),
    raw.network_events.EVENT_TYPE == "OUTAGE",
)
