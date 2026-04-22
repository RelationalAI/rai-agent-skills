# Pattern: multi-level location hierarchy + menu structure + customer segmentation
# Key ideas: Country → Region → City → Location hierarchy chain using Relationship
# for concept-to-concept FK links; MenuItem → MenuType category hierarchy;
# customer segmentation shows conditional branching (multiple .where() rules for
# mutually exclusive segments).
# Best practices: Property for scalars and functional FKs; Relationship for multi-valued links.

from relationalai.semantics import Float, Integer, Model, String

model = Model("Tasty Bytes")

# --- Sample Data ---
location_source = model.data([
    {"LOCATION_ID": 1, "CITY_ID": 10},
    {"LOCATION_ID": 2, "CITY_ID": 10},
    {"LOCATION_ID": 3, "CITY_ID": 20},
])
menu_source = model.data([
    {"MENU_ITEM_ID": 1, "MENU_ITEM_NAME": "Lobster Mac", "SALE_PRICE_USD": 14.0,
     "COST_OF_GOODS_USD": 5.5, "MENU_TYPE_ID": 100},
    {"MENU_ITEM_ID": 2, "MENU_ITEM_NAME": "Hot Dog", "SALE_PRICE_USD": 6.0,
     "COST_OF_GOODS_USD": 1.5, "MENU_TYPE_ID": 100},
    {"MENU_ITEM_ID": 3, "MENU_ITEM_NAME": "Lemonade", "SALE_PRICE_USD": 4.0,
     "COST_OF_GOODS_USD": 0.8, "MENU_TYPE_ID": 200},
])
customer_source = model.data([
    {"CUSTOMER_ID": 1, "LIFETIME_SPEND": 6200.0},
    {"CUSTOMER_ID": 2, "LIFETIME_SPEND": 2500.0},
    {"CUSTOMER_ID": 3, "LIFETIME_SPEND": 450.0},
])

# --- Value-Type IDs ---
CountryId = model.Concept("CountryId", extends=[Integer])
RegionId = model.Concept("RegionId", extends=[Integer])
CityId = model.Concept("CityId", extends=[Integer])
LocationId = model.Concept("LocationId", extends=[Integer])
MenuTypeId = model.Concept("MenuTypeId", extends=[Integer])
MenuItemId = model.Concept("MenuItemId", extends=[Integer])
CustomerId = model.Concept("CustomerId", extends=[Integer])

# --- Location Hierarchy: Country → Region → City → Location ---
Country = model.Concept("Country", identify_by={"id": CountryId})
Country.name = model.Property(f"{Country} has {String:name}")

Region = model.Concept("Region", identify_by={"id": RegionId})
Region.name = model.Property(f"{Region} has {String:name}")
Region.country = model.Relationship(
    f"{Region} is in {Country}", short_name="region_country")

City = model.Concept("City", identify_by={"id": CityId})
City.name = model.Property(f"{City} has {String:name}")
City.region = model.Relationship(
    f"{City} is in {Region}", short_name="city_region")

Location = model.Concept("Location", identify_by={"id": LocationId})
Location.city = model.Relationship(
    f"{Location} is in {City}", short_name="location_city")

# Inline FK chain resolves the entire hierarchy during entity creation
model.define(Location.new(
    id=location_source.LOCATION_ID,
    city=City.filter_by(id=location_source.CITY_ID),
))

# --- Menu Hierarchy: MenuType → MenuItem ---
MenuType = model.Concept("MenuType", identify_by={"id": MenuTypeId})
MenuType.name = model.Property(f"{MenuType} has {String:name}")

MenuItem = model.Concept("MenuItem", identify_by={"id": MenuItemId})
MenuItem.name = model.Property(f"{MenuItem} has {String:name}")
MenuItem.price = model.Property(f"{MenuItem} has {Float:price}")
MenuItem.cost = model.Property(f"{MenuItem} has {Float:cost}")
MenuItem.menu_type = model.Relationship(
    f"{MenuItem} belongs to {MenuType}", short_name="menu_item_menu_type")

model.define(MenuItem.new(
    id=menu_source.MENU_ITEM_ID,
    name=menu_source.MENU_ITEM_NAME,
    price=menu_source.SALE_PRICE_USD,
    cost=menu_source.COST_OF_GOODS_USD,
    menu_type=MenuType.filter_by(id=menu_source.MENU_TYPE_ID),
))

# --- Customer Segmentation ---
Customer = model.Concept("Customer", identify_by={"id": CustomerId})
Customer.lifetime_spend = model.Property(f"{Customer} has {Float:lifetime_spend}")

model.define(Customer.new(id=customer_source.CUSTOMER_ID))
model.define(
    Customer.filter_by(id=customer_source.CUSTOMER_ID)
    .lifetime_spend(customer_source.LIFETIME_SPEND)
)

# Segment taxonomy: subconcepts of a common base
CustomerSegment = model.Concept("CustomerSegment")
SegmentVIP = model.Concept("SegmentVIP", extends=[CustomerSegment])
SegmentHigh = model.Concept("SegmentHigh", extends=[CustomerSegment])
SegmentLow = model.Concept("SegmentLow", extends=[CustomerSegment])

Customer.segment = model.Property(f"{Customer} has segment {CustomerSegment}")

# Each .where() block targets a non-overlapping spend band
model.where(Customer.lifetime_spend >= 5000).define(
    Customer.segment(SegmentVIP)
)
model.where(
    Customer.lifetime_spend >= 1000,
    Customer.lifetime_spend < 5000,
).define(Customer.segment(SegmentHigh))
model.where(Customer.lifetime_spend < 1000).define(
    Customer.segment(SegmentLow)
)
