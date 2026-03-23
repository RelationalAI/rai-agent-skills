# Pattern: supply chain network — modeler export, many concepts, self-referential BOM
# Key ideas: Sources class with Snowflake tables; single-field identify_by (ID only);
# Properties for scalar attributes; Relationships for concept-to-concept links;
# self-referential relationship (SKU → SKU for assembly); short_name for disambiguation.
# Best practices: Property for scalars, Relationship for concept-to-concept links,
# identity = true natural key only.

from relationalai.semantics import Model, Date, DateTime, Float, Integer, String

model = Model("Supply Chain Network")

# --- Source Tables ---
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

# --- Concepts (identity = true natural key only) ---
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.site_type = model.Property(f"{Site} has {String:site_type}")
Site.city = model.Property(f"{Site} has {String:city}")
Site.region = model.Property(f"{Site} has {String:region}")
Site.country = model.Property(f"{Site} has {String:country}")
model.define(Site.new(id=src.site.ID))

StockKeepingUnit = model.Concept("StockKeepingUnit", identify_by={"id": String})
StockKeepingUnit.name = model.Property(f"{StockKeepingUnit} has {String:name}")
StockKeepingUnit.sku_type = model.Property(f"{StockKeepingUnit} has {String:sku_type}")
StockKeepingUnit.category = model.Property(f"{StockKeepingUnit} has {String:category}")
StockKeepingUnit.unit_cost = model.Property(f"{StockKeepingUnit} has {Float:unit_cost}")
StockKeepingUnit.lead_time_days = model.Property(f"{StockKeepingUnit} has {Integer:lead_time_days}")
StockKeepingUnit.unit_of_measure = model.Property(f"{StockKeepingUnit} has {String:unit_of_measure}")
StockKeepingUnit.unit_price = model.Property(f"{StockKeepingUnit} has {Float:unit_price}")
model.define(StockKeepingUnit.new(id=src.sku.ID))

Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} has {String:name}")
Business.contact_email = model.Property(f"{Business} has {String:contact_email}")
Business.business_type = model.Property(f"{Business} has {String:business_type}")
Business.value_tier = model.Property(f"{Business} has {String:value_tier}")
Business.reliability_score = model.Property(f"{Business} has {Float:reliability_score}")
model.define(Business.new(id=src.business.ID))

Operation = model.Concept("Operation", identify_by={"id": String})
Operation.operation_type = model.Property(f"{Operation} has {String:operation_type}")
model.define(Operation.new(id=src.operation.ID))

Demand = model.Concept("Demand", identify_by={"id": String})
Demand.quantity = model.Property(f"{Demand} has {Integer:quantity}")
Demand.due_date = model.Property(f"{Demand} has {Date:due_date}")
Demand.priority = model.Property(f"{Demand} has {String:priority}")
model.define(Demand.new(id=src.demand.ID))

BillOfMaterials = model.Concept("BillOfMaterials", identify_by={"id": String})
BillOfMaterials.input_quantity = model.Property(f"{BillOfMaterials} has {Integer:input_quantity}")
model.define(BillOfMaterials.new(id=src.bill_of_materials.ID))

Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")
Shipment.status = model.Property(f"{Shipment} has {String:status}")
model.define(Shipment.new(id=src.shipment.ID))

# --- Relationships (concept-to-concept links) ---
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
