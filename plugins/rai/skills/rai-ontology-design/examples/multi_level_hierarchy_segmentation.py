# Pattern: multi-level location hierarchy + product catalog structure + customer segmentation
# Key ideas: Country → Region → City → Location hierarchy chain using Relationship
# for concept-to-concept FK links; Product → Category classification hierarchy;
# customer segmentation shows conditional branching (multiple .where() rules for
# mutually exclusive segments).
# Best practices: Property for scalars and functional FKs; Relationship for multi-valued links.

from relationalai.semantics import Float, Integer, Model, String

model = Model("retail_hierarchy")

# --- Sample Data ---
location_source = model.data([
    {"LOCATION_ID": 1, "CITY_ID": 10},
    {"LOCATION_ID": 2, "CITY_ID": 10},
    {"LOCATION_ID": 3, "CITY_ID": 20},
])
product_source = model.data([
    {"PRODUCT_ID": 1, "PRODUCT_NAME": "Wireless Headphones", "SALE_PRICE_USD": 149.0,
     "COST_OF_GOODS_USD": 55.0, "CATEGORY_ID": 100},
    {"PRODUCT_ID": 2, "PRODUCT_NAME": "USB-C Cable", "SALE_PRICE_USD": 12.0,
     "COST_OF_GOODS_USD": 3.0, "CATEGORY_ID": 100},
    {"PRODUCT_ID": 3, "PRODUCT_NAME": "Desk Lamp", "SALE_PRICE_USD": 40.0,
     "COST_OF_GOODS_USD": 9.0, "CATEGORY_ID": 200},
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
CategoryId = model.Concept("CategoryId", extends=[Integer])
ProductId = model.Concept("ProductId", extends=[Integer])
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

# --- Product Hierarchy: Category → Product ---
Category = model.Concept("Category", identify_by={"id": CategoryId})
Category.name = model.Property(f"{Category} has {String:name}")

Product = model.Concept("Product", identify_by={"id": ProductId})
Product.name = model.Property(f"{Product} has {String:name}")
Product.price = model.Property(f"{Product} has {Float:price}")
Product.cost = model.Property(f"{Product} has {Float:cost}")
Product.category = model.Relationship(
    f"{Product} belongs to {Category}", short_name="product_category")

model.define(Product.new(
    id=product_source.PRODUCT_ID,
    name=product_source.PRODUCT_NAME,
    price=product_source.SALE_PRICE_USD,
    cost=product_source.COST_OF_GOODS_USD,
    category=Category.filter_by(id=product_source.CATEGORY_ID),
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
