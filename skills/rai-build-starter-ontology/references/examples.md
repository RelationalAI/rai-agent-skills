# Real Model Examples

These are real base models from production RAI projects, showing different patterns for building starter ontologies. These examples focus on **build patterns** — data loading, Sources class setup, FK binding, and file organization. For advanced design patterns (enrichment, categorization, composition, time hierarchies), see the examples in `rai-ontology-design`.

## Example 1: TPC-H Supply Chain (Snowflake tables, hierarchy, compound identity)

A classic relational schema with 8 tables, FKs, and a junction table (PartSupply). Uses Sources class, `Property` for scalars, `Relationship` for concept-to-concept links, `filter_by()` for FK binding.

**Source:** `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` (available on every Snowflake account)

```python
from relationalai.semantics import Model, Date, Float, Integer, String

model = Model("TPC-H Supply Chain")

# Source tables — nested class mirrors database.schema.table hierarchy
class Sources:
    class snowflake_sample_data:
        class tpch_sf1:
            region = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.REGION")
            nation = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.NATION")
            supplier = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.SUPPLIER")
            customer = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER")
            orders = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS")
            lineitem = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM")
            part = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.PART")
            partsupp = model.Table("SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.PARTSUPP")

src = Sources.snowflake_sample_data.tpch_sf1

# --- Concepts with identity ---
Region = model.Concept("Region", identify_by={"id": Integer})
Region.name = model.Property(f"{Region} has {String:name}")
model.define(Region.new(id=src.region.R_REGIONKEY, name=src.region.R_NAME))

Nation = model.Concept("Nation", identify_by={"id": Integer})
Nation.name = model.Property(f"{Nation} has {String:name}")
# Concept-to-concept link → Relationship
Nation.region = model.Relationship(f"{Nation} is within {Region}", short_name="nation_region")
model.define(Nation.new(
    id=src.nation.N_NATIONKEY,
    name=src.nation.N_NAME,
    region=Region.filter_by(id=src.nation.N_REGIONKEY),
))

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.account_balance = model.Property(f"{Customer} has {Float:account_balance}")
# FK → Relationship
Customer.nation = model.Relationship(f"{Customer} is in {Nation}", short_name="customer_nation")
model.define(Customer.new(id=src.customer.C_CUSTKEY))
model.define(Customer.name(src.customer.C_NAME)).where(
    Customer.filter_by(id=src.customer.C_CUSTKEY))
model.define(Customer.account_balance(src.customer.C_ACCTBAL)).where(
    Customer.filter_by(id=src.customer.C_CUSTKEY))
model.define(Customer.nation(Nation.filter_by(id=src.customer.C_NATIONKEY))).where(
    Customer.filter_by(id=src.customer.C_CUSTKEY))

Order = model.Concept("Order", identify_by={"id": Integer})
Order.total_price = model.Property(f"{Order} has {Float:total_price}")
Order.order_date = model.Property(f"{Order} has {Date:order_date}")
Order.customer = model.Relationship(f"{Order} is placed by {Customer}", short_name="order_customer")
model.define(Order.new(id=src.orders.O_ORDERKEY))
model.define(Order.customer(Customer.filter_by(id=src.orders.O_CUSTKEY))).where(
    Order.filter_by(id=src.orders.O_ORDERKEY))

# Junction table with compound identity
PartSupply = model.Concept("PartSupply", identify_by={"part_id": Integer, "supplier_id": Integer})
PartSupply.available_quantity = model.Property(f"{PartSupply} has {Integer:available_quantity}")
PartSupply.cost = model.Property(f"{PartSupply} has {Float:cost}")
model.define(PartSupply.new(
    part_id=src.partsupp.PS_PARTKEY,
    supplier_id=src.partsupp.PS_SUPPKEY,
    available_quantity=src.partsupp.PS_AVAILQTY,
    cost=src.partsupp.PS_SUPPLYCOST,
))
```

**Patterns demonstrated:**
- Sources class for table organization
- `Property` for scalar values, `Relationship` for concept-to-concept links
- `filter_by()` for FK binding (maps FK column to referenced entity's identity)
- Inline property binding in `.new()` for compact entity creation
- Compound identity for junction table (PartSupply)
- Domain names (Customer, Order) not schema names (CUSTOMER, ORDERS)

---

## Example 2: Ad Spend Optimization (derived concepts, bridge entity)

A marketing model with two source tables that derives several concepts (Channel, Campaign, Country) from column values, and creates a bridge entity (PiecewiseLinearSegment) that joins AdPlacement to Segment through a PWL curve.

**Source:** `MARKETING_AD_SPEND.PUBLIC`

```python
from relationalai.semantics import Float, Integer, Model, String

model = Model("Marketing Ad Spend")

class Sources:
    class marketing_ad_spend:
        class public:
            ad_placements = model.Table("MARKETING_AD_SPEND.PUBLIC.AD_PLACEMENTS")
            ad_pwl_segments = model.Table("MARKETING_AD_SPEND.PUBLIC.AD_PWL_SEGMENTS")

placements = Sources.marketing_ad_spend.public.ad_placements
segments = Sources.marketing_ad_spend.public.ad_pwl_segments

# --- Derived concepts from column values ---
# These aren't their own tables — they're derived from unique values in a column
MarketingChannel = model.Concept("MarketingChannel", identify_by={"name": String})
model.define(MarketingChannel.new(name=placements.channel))

Country = model.Concept("Country", identify_by={"name": String})
model.define(Country.new(name=placements.country))

# --- Primary entity with scalar properties + concept relationships ---
AdPlacement = model.Concept("AdPlacement", identify_by={"pid": String})
AdPlacement.min_budget = model.Property(f"{AdPlacement} has {Float:min_budget}")
AdPlacement.max_budget = model.Property(f"{AdPlacement} has {Float:max_budget}")
AdPlacement.channel = model.Relationship(
    f"{AdPlacement} runs on {MarketingChannel}", short_name="ad_placement_channel")
AdPlacement.country = model.Relationship(
    f"{AdPlacement} is in {Country}", short_name="ad_placement_country")

# Create entities and bind scalars
model.define(
    ap := AdPlacement.new(pid=placements.placement_id),
    ap.min_budget(placements.min_budget),
    ap.max_budget(placements.max_budget),
)

# Bind concept relationships via filter_by
model.define(AdPlacement.channel(MarketingChannel)).where(
    AdPlacement.filter_by(pid=placements.placement_id),
    MarketingChannel.filter_by(name=placements.channel),
)

# --- Bridge entity (joins two concepts through a third) ---
PiecewiseLinearSegment = model.Concept("PiecewiseLinearSegment")
PiecewiseLinearSegment.to_ad_placement = model.Relationship(
    f"{PiecewiseLinearSegment} models {AdPlacement}", short_name="pls_placement")
PiecewiseLinearSegment.segment = model.Relationship(
    f"{PiecewiseLinearSegment} uses {Segment}", short_name="pls_segment")
PiecewiseLinearSegment.segment_length = model.Property(
    f"{PiecewiseLinearSegment} has {Float:segment_length}")
PiecewiseLinearSegment.marginal_return = model.Property(
    f"{PiecewiseLinearSegment} has {Float:marginal_return}")

# Create bridge entities by joining through PWL curve
model.define(
    PiecewiseLinearSegment.new(
        to_ad_placement=AdPlacement,
        segment=Segment,
        segment_length=segments.segment_length,
        marginal_return=segments.marginal_return,
    )
).where(
    AdPlacement.pwl(PWL),
    PWL.filter_by(pwl_id=segments.pwl_id),
    Segment.filter_by(sid=segments.segment),
)

# Reverse relationship via .alias()
AdPlacement.segments = PiecewiseLinearSegment.to_ad_placement.alias(
    f"{AdPlacement} has segment {PiecewiseLinearSegment}")
```

**Patterns demonstrated:**
- Derived concepts from column values (not their own table)
- `Property` for scalars, `Relationship` for concept links
- `:=` walrus operator for inline entity creation + property binding
- Bridge entity joining two concepts through a third (PWL)
- `.alias()` for reverse relationship navigation

---

## Example 3: Machine Maintenance (CSV data, cross-product concepts, derived properties)

A scheduling domain with CSV source data, multiple cross-product concepts for the decision space, and derived properties computed from joined data.

**Source:** Local CSV files

```python
from relationalai.semantics import Float, Integer, Model, String

model = Model("Machine Maintenance")

# --- Base entities from CSV ---
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.machine_type = model.Property(f"{Machine} has type {String:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.location = model.Property(f"{Machine} in {String:location}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.maintenance_duration_hours = model.Property(
    f"{Machine} requires {Integer:maintenance_duration_hours} hours")
model.define(Machine.new(model.data(machines_df).to_schema()))

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.base_location = model.Property(f"{Technician} based in {String:base_location}")
Technician.hourly_rate = model.Property(f"{Technician} has hourly rate {Float:hourly_rate}")
Technician.max_weekly_hours = model.Property(
    f"{Technician} has max weekly hours {Integer:max_weekly_hours}")
model.define(Technician.new(model.data(technicians_df).to_schema()))

# Qualification: compound identity linking technician to machine type
Qualification = model.Concept("Qualification",
    identify_by={"technician_id": String, "machine_type": String})
Qualification.technician = model.Property(f"{Qualification} for {Technician}")
model.define(Qualification.new(
    technician_id=qual_data["technician_id"],
    machine_type=qual_data["machine_type"],
))
model.define(Qualification.technician(Technician)).where(
    Qualification.technician_id == Technician.technician_id)

# Period: discrete planning horizon (no source table — generated)
Period = model.Concept("Period", identify_by={"pid": Integer})
model.define(Period.new(pid=model.data([{"pid": t} for t in range(1, 5)])["pid"]))

# --- Cross-product concepts for decision space ---

# TechnicianPeriod: availability per period (with derived capacity)
TechnicianPeriod = model.Concept("TechnicianPeriod",
    identify_by={"technician": Technician, "period": Period})
TechnicianPeriod.capacity_hours = model.Property(
    f"{TechnicianPeriod} has available hours {Float:capacity_hours}")

# Populate from availability data with derived property
TcInit = Technician.ref()
PrInit = Period.ref()
model.define(TechnicianPeriod.new(
    technician=TcInit, period=PrInit,
    capacity_hours=avail_data["available"] * TcInit.max_weekly_hours
)).where(
    TcInit.technician_id == avail_data["technician_id"],
    PrInit.pid == avail_data["period"],
)

# TechnicianMachinePeriod: restricted to qualified pairs only
TechnicianMachinePeriod = model.Concept("TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period})
TechnicianMachinePeriod.same_location = model.Property(
    f"{TechnicianMachinePeriod} same location flag {Integer:same_location}")

# Constrained cross-product — only qualified (tech, machine) pairs
QualRef = Qualification.ref()
model.define(TechnicianMachinePeriod.new(
    technician=Technician, machine=Machine, period=Period
)).where(
    QualRef.technician(Technician),
    QualRef.machine_type_str == Machine.machine_type,
)

# Derived property: co-location flag
TmpRef = TechnicianMachinePeriod.ref()
TmpTech = Technician.ref()
TmpMach = Machine.ref()
model.where(
    TmpRef.technician(TmpTech), TmpRef.machine(TmpMach),
    TmpTech.base_location == TmpMach.location
).define(TmpRef.same_location(1))
model.where(
    TmpRef.technician(TmpTech), TmpRef.machine(TmpMach),
    TmpTech.base_location != TmpMach.location
).define(TmpRef.same_location(0))
```

**Patterns demonstrated:**
- CSV data loading via `model.data(df).to_schema()`
- Generated concepts (Period) with no source table
- Compound identity for junction concepts (Qualification)
- Cross-product decision concepts (TechnicianMachinePeriod)
- **Constrained** cross-product (`.where()` restricts to qualified pairs — avoids full cartesian)
- `.ref()` for joining back to base concepts in derived property rules
- Derived properties computed from joined data (capacity_hours, same_location)

---

## Example 4: Supply Chain Network (many concepts, self-referential BOM, individual Properties)

A supply chain model with 7 source tables and 7+ concepts. Shows individual Property declarations for each scalar attribute, Relationship for concept-to-concept links, self-referential relationship (SKU → SKU for assembly), and identity fields limited to true natural keys.

**Source:** `SUPPLY_CHAIN.PUBLIC`

```python
from relationalai.semantics import Model, Date, Float, Integer, String

model = Model("Supply Chain Network")

# ── Source Tables ────────────────────────────────────────────────
class Sources:
    class supply_chain:
        class public:
            bill_of_materials = model.Table("SUPPLY_CHAIN.PUBLIC.BILL_OF_MATERIALS")
            business = model.Table("SUPPLY_CHAIN.PUBLIC.BUSINESS")
            demand = model.Table("SUPPLY_CHAIN.PUBLIC.DEMAND")
            operation = model.Table("SUPPLY_CHAIN.PUBLIC.OPERATION")
            shipment = model.Table("SUPPLY_CHAIN.PUBLIC.SHIPMENT")
            site = model.Table("SUPPLY_CHAIN.PUBLIC.SITE")
            sku = model.Table("SUPPLY_CHAIN.PUBLIC.SKU")

src = Sources.supply_chain.public

# ── Concepts (identity = true natural key only) ──────────────────
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has {String:site_type}")
Site.city = model.Property(f"{Site} has {String:city}")
Site.region = model.Property(f"{Site} has {String:region}")
Site.country = model.Property(f"{Site} has {String:country}")
model.define(Site.new(id=src.site["ID"]))

StockKeepingUnit = model.Concept("StockKeepingUnit", identify_by={"id": String})
StockKeepingUnit.name = model.Property(f"{StockKeepingUnit} has {String:name}")
StockKeepingUnit.sku_type = model.Property(f"{StockKeepingUnit} has {String:sku_type}")
StockKeepingUnit.category = model.Property(f"{StockKeepingUnit} has {String:category}")
StockKeepingUnit.unit_cost = model.Property(f"{StockKeepingUnit} has {Float:unit_cost}")
StockKeepingUnit.lead_time_days = model.Property(f"{StockKeepingUnit} has {Integer:lead_time_days}")
StockKeepingUnit.unit_of_measure = model.Property(f"{StockKeepingUnit} has {String:unit_of_measure}")
StockKeepingUnit.unit_price = model.Property(f"{StockKeepingUnit} has {Float:unit_price}")
model.define(StockKeepingUnit.new(id=src.sku["ID"]))

Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} has {String:name}")
Business.contact_email = model.Property(f"{Business} has {String:contact_email}")
Business.business_type = model.Property(f"{Business} has {String:business_type}")
Business.value_tier = model.Property(f"{Business} has {String:value_tier}")
Business.reliability_score = model.Property(f"{Business} has {Float:reliability_score}")
model.define(Business.new(id=src.business["ID"]))

Operation = model.Concept("Operation", identify_by={"id": String})
Operation.operation_type = model.Property(f"{Operation} has {String:operation_type}")
model.define(Operation.new(id=src.operation["ID"]))

Demand = model.Concept("Demand", identify_by={"id": String})
Demand.quantity = model.Property(f"{Demand} has {Integer:quantity}")
Demand.due_date = model.Property(f"{Demand} has {Date:due_date}")
Demand.priority = model.Property(f"{Demand} has {String:priority}")
model.define(Demand.new(id=src.demand["ID"]))

BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.input_quantity = model.Property(f"{BillOfMaterials} has {Integer:input_quantity}")
model.define(BillOfMaterials.new(id=src.bill_of_materials["ID"]))

Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")
Shipment.status = model.Property(f"{Shipment} has {String:status}")
model.define(Shipment.new(id=src.shipment["ID"]))

# ── Relationships (concept-to-concept links) ─────────────────────
Site.produces_sku = model.Relationship(
    f"{Site} produces {StockKeepingUnit}", short_name="site_produces_sku")
Operation.transformation = model.Relationship(
    f"{Operation} transforms at {Site}", short_name="operation_transformation")
Business.operates_site = model.Relationship(
    f"{Business} operates {Site}", short_name="business_operates_site")
# Self-referential: SKU → SKU for BOM assembly
StockKeepingUnit.bom_components = model.Relationship(
    f"{StockKeepingUnit} requires {StockKeepingUnit} for assembly",
    short_name="bom_components")
# BOM links to concepts
BillOfMaterials.output_sku = model.Relationship(
    f"{BillOfMaterials} outputs {StockKeepingUnit}", short_name="bom_output_sku")
BillOfMaterials.input_sku = model.Relationship(
    f"{BillOfMaterials} inputs {StockKeepingUnit}", short_name="bom_input_sku")
BillOfMaterials.at_site = model.Relationship(
    f"{BillOfMaterials} at {Site}", short_name="bom_at_site")
```

**Patterns demonstrated:**
- Identity limited to true natural key (`{"id": String}`) — other attributes as Properties
- Individual `Property` for each scalar attribute (not bundled)
- `Relationship` for all concept-to-concept links
- Self-referential relationship (SKU → SKU for BOM assembly)
- `short_name` on every relationship for query disambiguation
- Bracket syntax for column access (`src.site["ID"]`)

---

## Example 5: Telco Network (large-scale, 14 source tables, unary flags, self-referential)

A telecommunications knowledge graph with 14 source tables spanning subscribers, network infrastructure, billing, and marketing. Shows large-scale modeling patterns: unary flags from status columns, bidirectional relationships with inverses, role-named relationships (caller/callee on same concept), and walrus operator for compact binding.

**Source:** `TELCO_DATA.RAW`

```python
from relationalai.semantics import Date, DateTime, Float, Integer, Model, String

model = Model("Telco Network")

# ── Source Tables (14 tables across one schema) ──────────────────
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

# ── PostalArea (geographic entity) ────────────────────────────────
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

# ── Part (inventory entity with unary flag) ───────────────────────
Part = model.Concept("Part", identify_by={"id": String})
Part.name = model.Property(f"{Part} has {String:name}")
Part.quantity_on_hand = model.Property(f"{Part} has {Integer:quantity_on_hand}")
Part.reorder_point = model.Property(f"{Part} has {Integer:reorder_point}")
Part.unit_cost = model.Property(f"{Part} has {Float:unit_cost}")
Part.stock_status = model.Property(f"{Part} has {String:stock_status}")
# Unary flag — boolean status promoted to Relationship
Part.is_critical_shortage = model.Relationship(f"{Part} is critical shortage")

model.define(
    p := Part.new(id=raw.parts_inventory.PART_ID),
    p.name(raw.parts_inventory.PART_NAME),
    p.quantity_on_hand(raw.parts_inventory.QUANTITY_ON_HAND),
    p.reorder_point(raw.parts_inventory.REORDER_POINT),
    p.unit_cost(raw.parts_inventory.UNIT_COST_USD),
    p.stock_status(raw.parts_inventory.STOCK_STATUS),
)

# Unary flag binding — condition from column value
model.define(Part.is_critical_shortage()).where(
    Part.stock_status == "CRITICAL_SHORTAGE",
)

# ── Subscriber (with FK to PostalArea + bidirectional inverse) ────
Subscriber = model.Concept("Subscriber", identify_by={"id": String})
Subscriber.segment = model.Property(f"{Subscriber} has {String:segment}")
Subscriber.lifetime_value = model.Property(f"{Subscriber} has {Float:lifetime_value}")
Subscriber.churn_risk_score = model.Property(f"{Subscriber} has {Float:churn_risk_score}")
Subscriber.status = model.Property(f"{Subscriber} has {String:status}")
# Bidirectional relationships
Subscriber.located_in = model.Relationship(
    f"{Subscriber} located in {PostalArea}", short_name="subscriber_located_in")
PostalArea.has_subscriber = model.Relationship(
    f"{PostalArea} has subscriber {Subscriber}", short_name="postal_area_has_subscriber")

model.define(
    s := Subscriber.new(id=raw.subscribers.SUB_ID),
    s.segment(raw.subscribers.SEGMENT),
    s.lifetime_value(raw.subscribers.LIFETIME_VALUE_USD),
    s.churn_risk_score(raw.subscribers.CHURN_RISK_SCORE),
    s.status(raw.subscribers.STATUS),
)

# FK binding with filter_by — both directions
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
Contract.term_months = model.Property(f"{Contract} has {Integer:term_months}")
Contract.for_subscriber = model.Relationship(
    f"{Contract} for subscriber {Subscriber}", short_name="contract_for_subscriber")
Contract.is_auto_renew = model.Relationship(f"{Contract} is auto renew")

model.define(Contract.is_auto_renew()).where(
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
    raw.plans_contracts.AUTO_RENEW == "True",
)

# ── NetworkEquipment (multi-FK: tower + part) ─────────────────────
NetworkEquipment = model.Concept("NetworkEquipment", identify_by={"id": String})
NetworkEquipment.equipment_type = model.Property(f"{NetworkEquipment} has {String:equipment_type}")
NetworkEquipment.installed_at = model.Relationship(
    f"{NetworkEquipment} installed at {CellTower}", short_name="equipment_installed_at")
NetworkEquipment.uses_part = model.Relationship(
    f"{NetworkEquipment} uses part {Part}", short_name="equipment_uses_part")
NetworkEquipment.has_outdated_firmware = model.Relationship(
    f"{NetworkEquipment} has outdated firmware")
# Inverses
CellTower.has_equipment = model.Relationship(
    f"{CellTower} has equipment {NetworkEquipment}", short_name="cell_tower_has_equipment")
Part.used_in_equipment = model.Relationship(
    f"{Part} used in equipment {NetworkEquipment}", short_name="part_used_in_equipment")

# ── CallDetailRecord (self-referential: caller + callee both → Subscriber) ──
CallDetailRecord = model.Concept("CallDetailRecord", identify_by={"id": String})
CallDetailRecord.duration_seconds = model.Property(
    f"{CallDetailRecord} has {Integer:duration_seconds}")
CallDetailRecord.quality_score = model.Property(
    f"{CallDetailRecord} has {Float:quality_score}")
# Role-named relationships — same target concept, different roles
CallDetailRecord.caller = model.Relationship(
    f"{CallDetailRecord} has caller {Subscriber}", short_name="cdr_caller")
CallDetailRecord.callee = model.Relationship(
    f"{CallDetailRecord} has callee {Subscriber}", short_name="cdr_callee")
CallDetailRecord.routed_through = model.Relationship(
    f"{CallDetailRecord} routed through {CellTower}", short_name="cdr_routed_through")
CallDetailRecord.is_dropped = model.Relationship(f"{CallDetailRecord} is dropped")
# Inverses with role names
Subscriber.made_call = model.Relationship(
    f"{Subscriber} made call {CallDetailRecord}", short_name="subscriber_made_call")
Subscriber.received_call = model.Relationship(
    f"{Subscriber} received call {CallDetailRecord}", short_name="subscriber_received_call")

# FK binding — same concept referenced by two different columns
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
NetworkEvent.duration_minutes = model.Property(f"{NetworkEvent} has {Integer:duration_minutes}")
NetworkEvent.is_outage = model.Relationship(f"{NetworkEvent} is outage")

model.define(NetworkEvent.is_outage()).where(
    NetworkEvent.filter_by(id=raw.network_events.EVENT_ID),
    raw.network_events.EVENT_TYPE == "OUTAGE",
)

# ── RevenueForecast (standalone analytics entity) ─────────────────
RevenueForecast = model.Concept("RevenueForecast", identify_by={"id": String})
RevenueForecast.forecast_revenue = model.Property(
    f"{RevenueForecast} has {Float:forecast_revenue}")
RevenueForecast.actual_revenue = model.Property(
    f"{RevenueForecast} has {Float:actual_revenue}")
RevenueForecast.is_on_target = model.Relationship(f"{RevenueForecast} is on target")

model.define(RevenueForecast.is_on_target()).where(
    RevenueForecast.filter_by(id=raw.revenue_forecast.FORECAST_ID),
    raw.revenue_forecast.STATUS == "ON_TARGET",
)
```

**Patterns demonstrated:**
- Large-scale model: 14 source tables, 12+ concepts
- Walrus operator (`:=`) for compact entity creation + property binding
- Unary flags from status/boolean columns (`is_critical_shortage`, `is_auto_renew`, `is_outage`, `is_dropped`, `is_on_target`)
- Bidirectional relationships with explicit inverses (both directions defined)
- **Self-referential relationships**: caller and callee both reference Subscriber — disambiguated with `short_name`
- Multi-FK binding: NetworkEquipment references both CellTower and Part
- Standalone analytics entities (RevenueForecast) with no FK to other concepts

---

## Example 6: Engineering Analytics (multi-schema, individual Properties, cross-system linking)

A software engineering analytics model spanning multiple source schemas (GitHub, project management, infrastructure, platform API). Demonstrates modeling across organizational data silos with many concepts, individual Properties for each scalar, boolean flags as unary Relationships, and cross-system linking patterns.

**Source:** `ENG_ANALYTICS.GITHUB`, `ENG_ANALYTICS.PROJECT_MGMT`, `ENG_ANALYTICS.INFRA`, `ENG_ANALYTICS.PLATFORM_API`

```python
from relationalai.semantics import Model, Bool, Date, DateTime, Float, Integer, String

model = Model("Engineering Analytics")

# ── Source Tables (multi-schema: 4 domains, 30+ tables) ──────────
class Sources:
    class eng_analytics:
        class github:
            ci_jobs = model.Table("ENG_ANALYTICS.GITHUB.CI_JOBS")
            commit = model.Table("ENG_ANALYTICS.GITHUB.COMMIT")
            pull_request = model.Table("ENG_ANALYTICS.GITHUB.PULL_REQUEST")
            pull_request_review = model.Table("ENG_ANALYTICS.GITHUB.PULL_REQUEST_REVIEW")
            repository = model.Table("ENG_ANALYTICS.GITHUB.REPOSITORY")
            team = model.Table("ENG_ANALYTICS.GITHUB.TEAM")
            user = model.Table("ENG_ANALYTICS.GITHUB.USER")
            workflow = model.Table("ENG_ANALYTICS.GITHUB.WORKFLOW")
        class project_mgmt:
            epic = model.Table("ENG_ANALYTICS.PROJECT_MGMT.EPIC")
            issue = model.Table("ENG_ANALYTICS.PROJECT_MGMT.ISSUE")
            project = model.Table("ENG_ANALYTICS.PROJECT_MGMT.PROJECT")
            sprint = model.Table("ENG_ANALYTICS.PROJECT_MGMT.SPRINT")
            user = model.Table("ENG_ANALYTICS.PROJECT_MGMT.USER")

# ── Concepts ─────────────────────────────────────────────────────
# GitHub domain
GitHubUser = model.Concept("GitHubUser", identify_by={"id": Integer})
model.define(GitHubUser.new(id=Sources.eng_analytics.github.user.id))

GitHubRepository = model.Concept("GitHubRepository", identify_by={"id": Integer})
model.define(GitHubRepository.new(id=Sources.eng_analytics.github.repository.id))

GitHubPullRequest = model.Concept("GitHubPullRequest", identify_by={"id": Integer})
model.define(GitHubPullRequest.new(id=Sources.eng_analytics.github.pull_request.id))

GitHubCommit = model.Concept("GitHubCommit", identify_by={"sha": String})
model.define(GitHubCommit.new(sha=Sources.eng_analytics.github.commit.sha))

# Project management domain
PMProject = model.Concept("PMProject", identify_by={"id": Integer})
model.define(PMProject.new(id=Sources.eng_analytics.project_mgmt.project.id))

PMIssue = model.Concept("PMIssue", identify_by={"id": Integer})
model.define(PMIssue.new(id=Sources.eng_analytics.project_mgmt.issue.id))

PMSprint = model.Concept("PMSprint", identify_by={"id": Integer})
model.define(PMSprint.new(id=Sources.eng_analytics.project_mgmt.sprint.id))

PMUser = model.Concept("PMUser", identify_by={"id": String})
model.define(PMUser.new(id=Sources.eng_analytics.project_mgmt.user.id))

# ── Properties (individual scalar attributes) ────────────────────
# GitHub user — each attribute is its own Property
GitHubUser.login = model.Property(f"{GitHubUser} has {String:login}")
GitHubUser.name = model.Property(f"{GitHubUser} has {String:name}")
GitHubUser.company = model.Property(f"{GitHubUser} has {String:company}")
GitHubUser.location = model.Property(f"{GitHubUser} has {String:location}")
GitHubUser.created_at = model.Property(f"{GitHubUser} has {Integer:created_at}")
# Boolean flags → unary Relationship
GitHubUser.is_site_admin = model.Relationship(f"{GitHubUser} is site admin")

# GitHub repository
GitHubRepository.name = model.Property(f"{GitHubRepository} has {String:name}")
GitHubRepository.full_name = model.Property(f"{GitHubRepository} has {String:full_name}")
GitHubRepository.description = model.Property(f"{GitHubRepository} has {String:description}")
GitHubRepository.primary_language = model.Property(f"{GitHubRepository} has {String:primary_language}")
GitHubRepository.fork_count = model.Property(f"{GitHubRepository} has {Integer:fork_count}")
GitHubRepository.is_private = model.Relationship(f"{GitHubRepository} is private")
GitHubRepository.is_archived = model.Relationship(f"{GitHubRepository} is archived")

# GitHub pull request
GitHubPullRequest.created_at = model.Property(f"{GitHubPullRequest} has {Integer:created_at}")
GitHubPullRequest.closed_at = model.Property(f"{GitHubPullRequest} has {Integer:closed_at}")
GitHubPullRequest.head_ref = model.Property(f"{GitHubPullRequest} has {String:head_ref}")
GitHubPullRequest.base_ref = model.Property(f"{GitHubPullRequest} has {String:base_ref}")
GitHubPullRequest.is_draft = model.Relationship(f"{GitHubPullRequest} is draft")

# GitHub commit
GitHubCommit.message = model.Property(f"{GitHubCommit} has {String:message}")
GitHubCommit.timestamp = model.Property(f"{GitHubCommit} has {Integer:timestamp}")
GitHubCommit.author_name = model.Property(f"{GitHubCommit} has {String:author_name}")

# PM issue
PMIssue.summary = model.Property(f"{PMIssue} has {String:summary}")
PMIssue.original_estimate = model.Property(f"{PMIssue} has {Float:original_estimate}")
PMIssue.remaining_estimate = model.Property(f"{PMIssue} has {Float:remaining_estimate}")
PMIssue.time_spent = model.Property(f"{PMIssue} has {Float:time_spent}")

# PM sprint
PMSprint.start_date = model.Property(f"{PMSprint} has {Integer:start_date}")
PMSprint.end_date = model.Property(f"{PMSprint} has {Integer:end_date}")
PMSprint.state = model.Property(f"{PMSprint} has {String:state}")

# ── Relationships (concept-to-concept links) ─────────────────────
# Cross-system linking (different identity systems)
GitHubUser.pm_user_mapping = model.Relationship(
    f"{GitHubUser} links to {PMUser}", short_name="github_pm_user_mapping")
GitHubPullRequest.implements_issue = model.Relationship(
    f"{GitHubPullRequest} implements {PMIssue}",
    short_name="github_pr_to_pm_issue")

# Within GitHub
GitHubUser.created_pr = model.Relationship(
    f"{GitHubUser} created {GitHubPullRequest}", short_name="github_user_created_pr")
GitHubRepository.contains_pr = model.Relationship(
    f"{GitHubRepository} contains {GitHubPullRequest}", short_name="repository_pull_requests")
GitHubPullRequest.contains_commit = model.Relationship(
    f"{GitHubPullRequest} contains {GitHubCommit}", short_name="pull_request_commits")

# Within project management: hierarchy
PMIssue.assigned_to = model.Relationship(
    f"{PMIssue} assigned to {PMUser}", short_name="pm_issue_assignment")
PMIssue.in_sprint = model.Relationship(
    f"{PMIssue} assigned to {PMSprint}", short_name="pm_issue_sprint_assignment")
PMIssue.belongs_to_project = model.Relationship(
    f"{PMIssue} belongs to {PMProject}", short_name="pm_issue_project_membership")
```

**Patterns demonstrated:**
- Multi-schema sources: 4 schemas across different organizational domains
- Many concepts (8+) with simple identity patterns — one concept per source table
- Individual `Property` for each scalar attribute (not bundled)
- Boolean flags as unary `Relationship` (`is_site_admin`, `is_private`, `is_archived`, `is_draft`)
- **Cross-system linking**: GitHubUser ↔ PMUser, GitHubPullRequest → PMIssue (bridging identity systems)
- Prefixed concept names (PM*, GitHub*) to avoid collisions across domains
- Relationship hierarchy within domains (Issue → Sprint, Issue → Project)
