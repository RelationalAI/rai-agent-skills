# Pattern: enrichment table mapping — loading auxiliary data from a separate schema/table
# Key ideas: Enrichment tables live in a different schema from core data; composite key
# (site + sku) identifies each row; Relationships link enrichment to existing concepts
# via filter_by(); Properties carry the enrichment payload. Useful when base tables are
# read-only and derived/supplementary data lives in a separate schema.

from relationalai.semantics import Model, Date, Float, Integer, String

model = Model("Enrichment Mapping Example")

# --- Core concepts (simplified) ---
Warehouse = model.Concept("Warehouse", identify_by={"id": String})
Warehouse.name = model.Property(f"{Warehouse} has {String:name}")

Product = model.Concept("Product", identify_by={"id": String})
Product.name = model.Property(f"{Product} has {String:name}")

# --- Enrichment concept with composite key ---
# Inventory lives in a separate enrichment schema, keyed by warehouse + product
Inventory = model.Concept("Inventory", identify_by={
    "warehouse_id": String,
    "product_id": String,
})

# Link back to core concepts
Inventory.warehouse = model.Relationship(f"{Inventory} at {Warehouse}")
Inventory.product = model.Relationship(f"{Inventory} of {Product}")

# Enrichment payload
Inventory.quantity_on_hand = model.Property(f"{Inventory} has {Integer:quantity_on_hand}")
Inventory.reorder_point = model.Property(f"{Inventory} has {Integer:reorder_point}")
Inventory.holding_cost = model.Property(f"{Inventory} has {Float:holding_cost}")

# --- Data loading ---
# Core tables (one schema)
core_wh = model.Table("MYDB.CORE.WAREHOUSE")
model.define(Warehouse.new(id=core_wh.id, name=core_wh.name))

core_prod = model.Table("MYDB.CORE.PRODUCT")
model.define(Product.new(id=core_prod.id, name=core_prod.name))

# Enrichment table (different schema)
enrich_inv = model.Table("MYDB.ENRICHMENT.INVENTORY")
model.define(Inventory.new(
    warehouse_id=enrich_inv.warehouse_id,
    product_id=enrich_inv.product_id,
    warehouse=Warehouse.filter_by(id=enrich_inv.warehouse_id),
    product=Product.filter_by(id=enrich_inv.product_id),
    quantity_on_hand=enrich_inv.quantity_on_hand,
    reorder_point=enrich_inv.reorder_point,
    holding_cost=enrich_inv.holding_cost,
))
