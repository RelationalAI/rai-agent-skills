# Starter Ontology Examples

These examples illustrate **build patterns** for starter ontologies — data loading, Sources class setup, FK binding, and file organization. Concept names and schemas are illustrative, not customer data. For advanced design patterns (enrichment, categorization, composition, time hierarchies), see the examples in `rai-ontology-design`.

## Example 1: Snowflake tables with FK chains + junction concept

Binding a multi-table Snowflake schema into concepts with FK-linked associations and a compound-identity junction concept. Uses `Sources` class for table organization, `Property` for scalars and functional FKs (e.g., each Order has one Customer), `Relationship` for multi-valued links and junction patterns, and `filter_by()` for FK resolution. Illustrated with TPC-H sample data (8 tables, including a PartSupply junction).

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
# Functional FK (each Nation in exactly one Region) → Property
Nation.region = model.Property(f"{Nation} is within {Region:region}", short_name="nation_region")
model.define(Nation.new(
    id=src.nation.N_NATIONKEY,
    name=src.nation.N_NAME,
    region=Region.filter_by(id=src.nation.N_REGIONKEY),
))

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.account_balance = model.Property(f"{Customer} has {Float:account_balance}")
# Functional FK (each Customer in exactly one Nation) → Property
Customer.nation = model.Property(f"{Customer} is in {Nation:nation}", short_name="customer_nation")
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
Order.customer = model.Property(f"{Order} is placed by {Customer:customer}", short_name="order_customer")
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
- `Property` for scalars AND functional FKs (each Order has one Customer); `Relationship` for multi-valued links and junction patterns
- `filter_by()` for FK binding (maps FK column to referenced entity's identity)
- Inline property binding in `.new()` for compact entity creation
- Compound identity for junction table (PartSupply)
- Domain names (Customer, Order) not schema names (CUSTOMER, ORDERS)

---

## Example 2: Derived concepts from column values + bridge entity

Deriving new concepts from distinct column values (no dedicated source table), and creating a bridge entity that joins two concepts through a third. Illustrated with a piecewise-linear curve setup — Channel/Country concepts are derived from allocation columns, and PiecewiseLinearSegment bridges Allocation and Segment.

**Source:** `OPS_DB.PUBLIC`

```python
from relationalai.semantics import Float, Integer, Model, String

model = Model("Allocation Curves")

class Sources:
    class ops_db:
        class public:
            allocations = model.Table("OPS_DB.PUBLIC.ALLOCATIONS")
            allocation_pwl_segments = model.Table("OPS_DB.PUBLIC.ALLOCATION_PWL_SEGMENTS")

allocations = Sources.ops_db.public.allocations
segments = Sources.ops_db.public.allocation_pwl_segments

# --- Derived concepts from column values ---
# These aren't their own tables — they're derived from unique values in a column
Channel = model.Concept("Channel", identify_by={"name": String})
model.define(Channel.new(name=allocations.channel))

Country = model.Concept("Country", identify_by={"name": String})
model.define(Country.new(name=allocations.country))

# --- Primary entity with scalar properties + concept relationships ---
Allocation = model.Concept("Allocation", identify_by={"aid": String})
Allocation.min_budget = model.Property(f"{Allocation} has {Float:min_budget}")
Allocation.max_budget = model.Property(f"{Allocation} has {Float:max_budget}")
Allocation.channel = model.Property(
    f"{Allocation} runs on {Channel:channel}", short_name="allocation_channel")
Allocation.country = model.Property(
    f"{Allocation} is in {Country:country}", short_name="allocation_country")

# --- PWL curve and Segment concepts (declared so the bridge below can reference them) ---
PWL = model.Concept("PWL", identify_by={"pwl_id": String})
Segment = model.Concept("Segment", identify_by={"sid": String})
Allocation.pwl = model.Relationship(
    f"{Allocation} has pwl {PWL}", short_name="allocation_pwl")

# Create entities and bind scalars
model.define(
    al := Allocation.new(aid=allocations.allocation_id),
    al.min_budget(allocations.min_budget),
    al.max_budget(allocations.max_budget),
)

# Bind concept relationships via filter_by
model.define(Allocation.channel(Channel)).where(
    Allocation.filter_by(aid=allocations.allocation_id),
    Channel.filter_by(name=allocations.channel),
)

# --- Bridge entity (joins two concepts through a third) ---
PiecewiseLinearSegment = model.Concept("PiecewiseLinearSegment")
PiecewiseLinearSegment.to_allocation = model.Property(
    f"{PiecewiseLinearSegment} models {Allocation:to_allocation}", short_name="pls_allocation")
PiecewiseLinearSegment.segment = model.Property(
    f"{PiecewiseLinearSegment} uses {Segment:segment}", short_name="pls_segment")
PiecewiseLinearSegment.segment_length = model.Property(
    f"{PiecewiseLinearSegment} has {Float:segment_length}")
PiecewiseLinearSegment.marginal_return = model.Property(
    f"{PiecewiseLinearSegment} has {Float:marginal_return}")

# Create bridge entities by joining through PWL curve
model.define(
    PiecewiseLinearSegment.new(
        to_allocation=Allocation,
        segment=Segment,
        segment_length=segments.segment_length,
        marginal_return=segments.marginal_return,
    )
).where(
    Allocation.pwl(PWL),
    PWL.filter_by(pwl_id=segments.pwl_id),
    Segment.filter_by(sid=segments.segment),
)

# Reverse relationship via .alias()
Allocation.segments = PiecewiseLinearSegment.to_allocation.alias(
    f"{Allocation} has segment {PiecewiseLinearSegment}")
```

**Patterns demonstrated:**
- Derived concepts from column values (not their own table)
- `Property` for scalars, `Relationship` for concept links
- `:=` walrus operator for inline entity creation + property binding
- Bridge entity joining two concepts through a third (PWL)
- `.alias()` for reverse relationship navigation

---

## Example 3: CSV loading + cross-product decision concepts

Loading CSV source data, building cross-product decision concepts for a constrained cartesian, and computing derived properties from joined data. Illustrated with a machine-maintenance scheduling model.

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

## Example 4: Many concepts + self-referential hierarchy

Scaling to many concepts with a self-referential relationship (entity → entity of the same type). Shows individual `Property` declarations per scalar, `Relationship` for multi-valued concept-to-concept links, and identity fields limited to true natural keys. Illustrated with a supply chain where SKUs point to SKUs via a bill-of-materials pattern.

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

# ── Multi-valued concept-to-concept associations (Relationship) ──
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
- `Relationship` for multi-valued concept-to-concept links
- Self-referential relationship (SKU → SKU for BOM assembly)
- `short_name` on every relationship for query disambiguation
- Bracket syntax for column access (`src.site["ID"]`)

---

## Example 5: Large-scale model with bidirectional inverses, unary flags, and role-named relationships

Patterns for a large model (10+ source tables, 10+ concepts): unary `Relationship` flags derived from status columns, bidirectional relationships with explicit inverses, role-named relationships for self-referential cases (e.g., source/target both pointing to the same concept), and the walrus operator for compact entity-and-properties binding. Illustrated with a multi-entity operational knowledge graph.

**Source:** `OPS_DB.RAW`

```python
from relationalai.semantics import Date, DateTime, Float, Integer, Model, String

model = Model("Multi-Entity Network")

# ── Source Tables (14 tables across one schema) ──────────────────
class Sources:
    class ops_db:
        class raw:
            regional_risk = model.Table("OPS_DB.RAW.REGIONAL_RISK")
            customers = model.Table("OPS_DB.RAW.CUSTOMERS")
            plans_contracts = model.Table("OPS_DB.RAW.PLANS_CONTRACTS")
            billing_events = model.Table("OPS_DB.RAW.BILLING_EVENTS")
            facilities = model.Table("OPS_DB.RAW.FACILITIES")
            parts_inventory = model.Table("OPS_DB.RAW.PARTS_INVENTORY")
            equipment = model.Table("OPS_DB.RAW.EQUIPMENT")
            equipment_health = model.Table("OPS_DB.RAW.EQUIPMENT_HEALTH")
            incidents = model.Table("OPS_DB.RAW.INCIDENTS")
            transactions = model.Table("OPS_DB.RAW.TRANSACTIONS")
            supplier_orders = model.Table("OPS_DB.RAW.SUPPLIER_ORDERS")
            campaigns = model.Table("OPS_DB.RAW.CAMPAIGNS")
            promotion_redemptions = model.Table("OPS_DB.RAW.PROMOTION_REDEMPTIONS")
            revenue_forecast = model.Table("OPS_DB.RAW.REVENUE_FORECAST")

raw = Sources.ops_db.raw

# ── Location (geographic entity) ──────────────────────────────────
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

# ── Customer (with FK to Location + bidirectional inverse) ────────
Customer = model.Concept("Customer", identify_by={"id": String})
Customer.segment = model.Property(f"{Customer} has {String:segment}")
Customer.lifetime_value = model.Property(f"{Customer} has {Float:lifetime_value}")
Customer.churn_risk_score = model.Property(f"{Customer} has {Float:churn_risk_score}")
Customer.status = model.Property(f"{Customer} has {String:status}")
# Bidirectional relationships
Customer.located_in = model.Property(
    f"{Customer} located in {Location:located_in}", short_name="customer_located_in")
Location.has_customer = model.Relationship(
    f"{Location} has customer {Customer}", short_name="location_has_customer")

model.define(
    c := Customer.new(id=raw.customers.CUST_ID),
    c.segment(raw.customers.SEGMENT),
    c.lifetime_value(raw.customers.LIFETIME_VALUE_USD),
    c.churn_risk_score(raw.customers.CHURN_RISK_SCORE),
    c.status(raw.customers.STATUS),
)

# FK binding with filter_by — both directions
model.define(Customer.located_in(Location)).where(
    Customer.filter_by(id=raw.customers.CUST_ID),
    Location.filter_by(id=raw.customers.POSTAL_CODE),
)
model.define(Location.has_customer(Customer)).where(
    Location.filter_by(id=raw.customers.POSTAL_CODE),
    Customer.filter_by(id=raw.customers.CUST_ID),
)

# ── Contract (unary flag from boolean column) ─────────────────────
Contract = model.Concept("Contract", identify_by={"id": String})
Contract.monthly_rate = model.Property(f"{Contract} has {Float:monthly_rate}")
Contract.term_months = model.Property(f"{Contract} has {Integer:term_months}")
Contract.for_customer = model.Property(
    f"{Contract} for customer {Customer:for_customer}", short_name="contract_for_customer")
Contract.is_auto_renew = model.Relationship(f"{Contract} is auto renew")

model.define(Contract.is_auto_renew()).where(
    Contract.filter_by(id=raw.plans_contracts.CONTRACT_ID),
    raw.plans_contracts.AUTO_RENEW == "True",
)

# ── Facility ─────────────────────────────────────────────────────
Facility = model.Concept("Facility", identify_by={"id": String})
Facility.capacity = model.Property(f"{Facility} has {Integer:capacity}")
Facility.located_in = model.Property(
    f"{Facility} located in {Location:located_in}", short_name="facility_located_in")
model.define(
    f := Facility.new(id=raw.facilities.FACILITY_ID),
    f.capacity(raw.facilities.CAPACITY),
)
model.define(Facility.located_in(Location)).where(
    Facility.filter_by(id=raw.facilities.FACILITY_ID),
    Location.filter_by(id=raw.facilities.POSTAL_CODE),
)

# ── Equipment (multi-FK: facility + part) ─────────────────────────
Equipment = model.Concept("Equipment", identify_by={"id": String})
Equipment.equipment_type = model.Property(f"{Equipment} has {String:equipment_type}")
Equipment.installed_at = model.Property(
    f"{Equipment} installed at {Facility:installed_at}", short_name="equipment_installed_at")
Equipment.uses_part = model.Relationship(
    f"{Equipment} uses part {Part}", short_name="equipment_uses_part")
Equipment.has_outdated_firmware = model.Relationship(
    f"{Equipment} has outdated firmware")
# Inverses
Facility.has_equipment = model.Relationship(
    f"{Facility} has equipment {Equipment}", short_name="facility_has_equipment")
Part.used_in_equipment = model.Relationship(
    f"{Part} used in equipment {Equipment}", short_name="part_used_in_equipment")

# ── Transaction (self-referential: source + target both → Customer) ──
Transaction = model.Concept("Transaction", identify_by={"id": String})
Transaction.duration_seconds = model.Property(
    f"{Transaction} has {Integer:duration_seconds}")
Transaction.quality_score = model.Property(
    f"{Transaction} has {Float:quality_score}")
# Role-named relationships — same target concept, different roles
Transaction.source = model.Property(
    f"{Transaction} has source {Customer:source}", short_name="transaction_source")
Transaction.target = model.Property(
    f"{Transaction} has target {Customer:target}", short_name="transaction_target")
Transaction.routed_through = model.Property(
    f"{Transaction} routed through {Facility:routed_through}", short_name="transaction_routed_through")
Transaction.is_dropped = model.Relationship(f"{Transaction} is dropped")
# Inverses with role names
Customer.sent_transaction = model.Relationship(
    f"{Customer} sent transaction {Transaction}", short_name="customer_sent_transaction")
Customer.received_transaction = model.Relationship(
    f"{Customer} received transaction {Transaction}", short_name="customer_received_transaction")

# FK binding — same concept referenced by two different columns
model.define(Transaction.source(Customer)).where(
    Transaction.filter_by(id=raw.transactions.TXN_ID),
    Customer.filter_by(id=raw.transactions.SOURCE_CUST_ID),
)
model.define(Transaction.target(Customer)).where(
    Transaction.filter_by(id=raw.transactions.TXN_ID),
    Customer.filter_by(id=raw.transactions.TARGET_CUST_ID),
)
model.define(Transaction.is_dropped()).where(
    Transaction.filter_by(id=raw.transactions.TXN_ID),
    raw.transactions.TXN_STATUS == "DROPPED",
)

# ── Incident (unary flag from event type) ─────────────────────────
Incident = model.Concept("Incident", identify_by={"id": String})
Incident.severity = model.Property(f"{Incident} has {String:severity}")
Incident.duration_minutes = model.Property(f"{Incident} has {Integer:duration_minutes}")
Incident.is_outage = model.Relationship(f"{Incident} is outage")

model.define(Incident.is_outage()).where(
    Incident.filter_by(id=raw.incidents.EVENT_ID),
    raw.incidents.EVENT_TYPE == "OUTAGE",
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
- **Self-referential relationships**: source and target both reference Customer — disambiguated with `short_name`
- Multi-FK binding: Equipment references both Facility and Part
- Standalone analytics entities (RevenueForecast) with no FK to other concepts

---

## Example 6: Multi-schema sources with cross-system entity linking

Modeling across multiple source schemas where the same business entity lives in different systems (e.g., a user identified by one ID in one system and a different user ID in another). Shows prefixed concept names to avoid collisions, individual `Property` per scalar, boolean flags as unary `Relationship`, and linking patterns that bridge identity systems.

**Source:** `OPS_DB.SYSTEM_A`, `OPS_DB.SYSTEM_B`

```python
from relationalai.semantics import Model, Boolean, Date, DateTime, Float, Integer, String

model = Model("Cross-System Analytics")

# ── Source Tables (multi-schema: 2 domains, 13 tables) ──────────
class Sources:
    class ops_db:
        class system_a:
            ci_jobs = model.Table("OPS_DB.SYSTEM_A.CI_JOBS")
            activity = model.Table("OPS_DB.SYSTEM_A.ACTIVITY")
            work_item = model.Table("OPS_DB.SYSTEM_A.WORK_ITEM")
            work_item_review = model.Table("OPS_DB.SYSTEM_A.WORK_ITEM_REVIEW")
            project = model.Table("OPS_DB.SYSTEM_A.PROJECT")
            team = model.Table("OPS_DB.SYSTEM_A.TEAM")
            user = model.Table("OPS_DB.SYSTEM_A.USER")
            workflow = model.Table("OPS_DB.SYSTEM_A.WORKFLOW")
        class system_b:
            epic = model.Table("OPS_DB.SYSTEM_B.EPIC")
            task = model.Table("OPS_DB.SYSTEM_B.TASK")
            project = model.Table("OPS_DB.SYSTEM_B.PROJECT")
            iteration = model.Table("OPS_DB.SYSTEM_B.ITERATION")
            user = model.Table("OPS_DB.SYSTEM_B.USER")

# ── Concepts ─────────────────────────────────────────────────────
# System A domain
SystemAUser = model.Concept("SystemAUser", identify_by={"id": Integer})
model.define(SystemAUser.new(id=Sources.ops_db.system_a.user.id))

SystemAProject = model.Concept("SystemAProject", identify_by={"id": Integer})
model.define(SystemAProject.new(id=Sources.ops_db.system_a.project.id))

SystemAWorkItem = model.Concept("SystemAWorkItem", identify_by={"id": Integer})
model.define(SystemAWorkItem.new(id=Sources.ops_db.system_a.work_item.id))

SystemAActivity = model.Concept("SystemAActivity", identify_by={"sha": String})
model.define(SystemAActivity.new(sha=Sources.ops_db.system_a.activity.sha))

# System B domain
SystemBProject = model.Concept("SystemBProject", identify_by={"id": Integer})
model.define(SystemBProject.new(id=Sources.ops_db.system_b.project.id))

SystemBTask = model.Concept("SystemBTask", identify_by={"id": Integer})
model.define(SystemBTask.new(id=Sources.ops_db.system_b.task.id))

SystemBIteration = model.Concept("SystemBIteration", identify_by={"id": Integer})
model.define(SystemBIteration.new(id=Sources.ops_db.system_b.iteration.id))

SystemBUser = model.Concept("SystemBUser", identify_by={"id": String})
model.define(SystemBUser.new(id=Sources.ops_db.system_b.user.id))

# ── Properties (individual scalar attributes) ────────────────────
# System A user — each attribute is its own Property
SystemAUser.login = model.Property(f"{SystemAUser} has {String:login}")
SystemAUser.name = model.Property(f"{SystemAUser} has {String:name}")
SystemAUser.company = model.Property(f"{SystemAUser} has {String:company}")
SystemAUser.location = model.Property(f"{SystemAUser} has {String:location}")
SystemAUser.created_at = model.Property(f"{SystemAUser} has {Integer:created_at}")
# Boolean flags → unary Relationship
SystemAUser.is_site_admin = model.Relationship(f"{SystemAUser} is site admin")

# System A project
SystemAProject.name = model.Property(f"{SystemAProject} has {String:name}")
SystemAProject.full_name = model.Property(f"{SystemAProject} has {String:full_name}")
SystemAProject.description = model.Property(f"{SystemAProject} has {String:description}")
SystemAProject.primary_language = model.Property(f"{SystemAProject} has {String:primary_language}")
SystemAProject.fork_count = model.Property(f"{SystemAProject} has {Integer:fork_count}")
SystemAProject.is_private = model.Relationship(f"{SystemAProject} is private")
SystemAProject.is_archived = model.Relationship(f"{SystemAProject} is archived")

# System A work item
SystemAWorkItem.created_at = model.Property(f"{SystemAWorkItem} has {Integer:created_at}")
SystemAWorkItem.closed_at = model.Property(f"{SystemAWorkItem} has {Integer:closed_at}")
SystemAWorkItem.head_ref = model.Property(f"{SystemAWorkItem} has {String:head_ref}")
SystemAWorkItem.base_ref = model.Property(f"{SystemAWorkItem} has {String:base_ref}")
SystemAWorkItem.is_draft = model.Relationship(f"{SystemAWorkItem} is draft")

# System A activity
SystemAActivity.message = model.Property(f"{SystemAActivity} has {String:message}")
SystemAActivity.timestamp = model.Property(f"{SystemAActivity} has {Integer:timestamp}")
SystemAActivity.author_name = model.Property(f"{SystemAActivity} has {String:author_name}")

# System B task
SystemBTask.summary = model.Property(f"{SystemBTask} has {String:summary}")
SystemBTask.original_estimate = model.Property(f"{SystemBTask} has {Float:original_estimate}")
SystemBTask.remaining_estimate = model.Property(f"{SystemBTask} has {Float:remaining_estimate}")
SystemBTask.time_spent = model.Property(f"{SystemBTask} has {Float:time_spent}")

# System B iteration
SystemBIteration.start_date = model.Property(f"{SystemBIteration} has {Integer:start_date}")
SystemBIteration.end_date = model.Property(f"{SystemBIteration} has {Integer:end_date}")
SystemBIteration.state = model.Property(f"{SystemBIteration} has {String:state}")

# ── Concept-to-concept associations (Property for functional, Relationship for multi-valued) ──
# Cross-system linking (different identity systems)
SystemAUser.system_b_user_mapping = model.Property(
    f"{SystemAUser} links to {SystemBUser:system_b_user_mapping}", short_name="system_a_to_b_user_mapping")
SystemAWorkItem.implements_task = model.Property(
    f"{SystemAWorkItem} implements {SystemBTask:implements_task}",
    short_name="system_a_work_item_to_system_b_task")

# Within System A
SystemAUser.created_work_item = model.Relationship(
    f"{SystemAUser} created {SystemAWorkItem}", short_name="system_a_user_created_work_item")
SystemAProject.contains_work_item = model.Relationship(
    f"{SystemAProject} contains {SystemAWorkItem}", short_name="project_work_items")
SystemAWorkItem.contains_activity = model.Relationship(
    f"{SystemAWorkItem} contains {SystemAActivity}", short_name="work_item_activities")

# Within System B: hierarchy
SystemBTask.assigned_to = model.Property(
    f"{SystemBTask} assigned to {SystemBUser:assigned_to}", short_name="system_b_task_assignment")
SystemBTask.in_iteration = model.Property(
    f"{SystemBTask} assigned to {SystemBIteration:in_iteration}", short_name="system_b_task_iteration_assignment")
SystemBTask.belongs_to_project = model.Property(
    f"{SystemBTask} belongs to {SystemBProject:belongs_to_project}", short_name="system_b_task_project_membership")
```

**Patterns demonstrated:**
- Multi-schema sources: 2 schemas across different organizational domains
- Many concepts (8+) with simple identity patterns — one concept per source table
- Individual `Property` for each scalar attribute (not bundled)
- Boolean flags as unary `Relationship` (`is_site_admin`, `is_private`, `is_archived`, `is_draft`)
- **Cross-system linking**: SystemAUser <-> SystemBUser, SystemAWorkItem -> SystemBTask (bridging identity systems)
- Prefixed concept names (SystemA*, SystemB*) to avoid collisions across domains
- Relationship hierarchy within domains (Task -> Iteration, Task -> Project)

---

## Example 7: Pairwise Value Matrix (long-form relation table, two binding patterns)

Many source datasets encode pairwise quantities as a long-form `(entity_i, entity_j, value)` table — e.g., a distance or similarity matrix between entities. This example shows the two ways to bind such data and when each is preferred.

**Source:** an `INTERACTION` table with rows `(LEFT_ID, RIGHT_ID, STRENGTH)` referencing `Item.id`.

### Pattern A: Junction concept with compound identity

Use when pairs may carry multiple attributes, need explicit Relationships to both endpoints for downstream traversal, or feed a graph reasoner via `edge_concept`.

```python
from relationalai.semantics import Float, Integer, Model, String

model = Model("Pairwise Demo")

class Sources:
    class demo:
        class public:
            items = model.Table("DEMO.PUBLIC.ITEMS")
            interactions = model.Table("DEMO.PUBLIC.INTERACTIONS")

src = Sources.demo.public

Item = model.Concept("Item", identify_by={"id": Integer})
Item.name = model.Property(f"{Item} has {String:name}")
model.define(
    i := Item.new(id=src.items.ITEM_ID),
    i.name(src.items.NAME),
)

ItemPair = model.Concept(
    "ItemPair",
    identify_by={"left_id": Integer, "right_id": Integer},
)
ItemPair.strength = model.Property(f"{ItemPair} has {Float:strength}")
ItemPair.left = model.Property(
    f"{ItemPair} has left {Item:left}", short_name="pair_left"
)
ItemPair.right = model.Property(
    f"{ItemPair} has right {Item:right}", short_name="pair_right"
)

model.define(
    ip := ItemPair.new(
        left_id=src.interactions.LEFT_ID,
        right_id=src.interactions.RIGHT_ID,
    ),
    ip.strength(src.interactions.STRENGTH),
)

model.define(ItemPair.left(Item)).where(
    ItemPair.filter_by(
        left_id=src.interactions.LEFT_ID,
        right_id=src.interactions.RIGHT_ID,
    ),
    Item.filter_by(id=src.interactions.LEFT_ID),
)
model.define(ItemPair.right(Item)).where(
    ItemPair.filter_by(
        left_id=src.interactions.LEFT_ID,
        right_id=src.interactions.RIGHT_ID,
    ),
    Item.filter_by(id=src.interactions.RIGHT_ID),
)
```

### Pattern B: Same-type ternary Property

*Alternative to Pattern A — replaces the `ItemPair` junction concept with a single ternary Property on `Item`. Choose one pattern; do not combine.*

Use when pairs carry exactly one numeric value and no additional attributes. More compact; retains full queryability via `Item.ref()` for same-type joins.

```python
Item = model.Concept("Item", identify_by={"id": Integer})
Item.interaction = model.Property(
    f"{Item} and {Item} have {Float:strength}"
)

Other = Item.ref()
model.where(
    Item.id == src.interactions.LEFT_ID,
    Other.id == src.interactions.RIGHT_ID,
).define(Item.interaction(Other, src.interactions.STRENGTH))
```

### Choosing between them

| Signal | Pattern A (junction concept) | Pattern B (ternary Property) |
|--------|------------------------------|------------------------------|
| Pair has multiple attributes (e.g., cost + time + capacity) | Required | Not applicable |
| Pair has exactly one numeric value | Either works | Preferred — more compact |
| Need explicit named Relationships to both endpoints | Direct | Via `.ref()` |
| Pair feeds a Graph reasoner's `edge_concept` | Required | Not applicable |
| Pair is symmetric and source lists both `(i,j)` and `(j,i)` | Add `left_id < right_id` filter during binding | Add `Item.id < Other.id` filter during binding |

**Patterns demonstrated:**
- Compound identity for pair-keyed entities
- Same-type ternary `Property` for single-value pairwise data
- Role-named Relationships (left/right, from/to, src/dst) to make traversal directions explicit
- Symmetry handling via ordered-pair filter during binding

**Related guidance:** see `rai-ontology-design` § "Same-type multiarity detection" for the corresponding design-principle discussion.

---

## Example 8: Portable source paths (hoist database name to a constant)

Shared Snowflake databases are often imported under different account-local names (e.g., a publisher's share appears as `SHARED_A` on one consumer and `SHARED_B` on another). Ontologies that hardcode `DATABASE.SCHEMA.TABLE` in every `model.Table()` call break when the local alias differs from the publisher's.

**Pattern:** hoist the database (and optionally schema) to top-of-file constants. Retargeting is a one-line change.

```python
from relationalai.semantics import Model

DB = "PUBLISHER_NAME"     # override if imported under a different alias
SCHEMA = "RAW"

model = Model("my_domain")

class Sources:
    class src:
        entity_a = model.Table(f"{DB}.{SCHEMA}.ENTITY_A")
        entity_b = model.Table(f"{DB}.{SCHEMA}.ENTITY_B")
```

Applies equally to env-split retargeting (`DEV` vs `PROD`). When the DB name varies per deployment, parameterize via an environment variable or `raiconfig` value.

**Patterns demonstrated:**
- DB-as-constant for portable ontologies
- Sources class with f-string path interpolation
