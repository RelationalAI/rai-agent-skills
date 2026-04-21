# Pattern: model.select() queries with aggregation, filtering, aliasing
# Key ideas: .alias() renames columns; sum/count with .per() for grouped aggregation;
# .where() filters rows; .to_df() materializes as pandas DataFrame.

from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.std import aggregates as aggs

model = Model("aggregation_queries")

# --- Ontology (abbreviated for query examples) ---
Site = model.Concept("Site", identify_by={"id": String})
Site.name = model.Property(f"{Site} has {String:name}")
Site.region = model.Property(f"{Site} has {String:region}")

Shipment = model.Concept("Shipment", identify_by={"id": String})
Shipment.origin = model.Relationship(f"{Shipment} from {Site}")
Shipment.destination = model.Relationship(f"{Shipment} to {Site}")
Shipment.quantity = model.Property(f"{Shipment} has {Integer:quantity}")
Shipment.delay_days = model.Property(f"{Shipment} has {Integer:delay_days}")
Shipment.status = model.Property(f"{Shipment} has {String:status}")

Business = model.Concept("Business", identify_by={"id": String})
Business.name = model.Property(f"{Business} has {String:name}")
Business.reliability_score = model.Property(f"{Business} has {Float:reliability_score}")
Shipment.supplier = model.Relationship(f"{Shipment} supplied by {Business}")


# --- Query 1: Simple select with filter ---
def delayed_shipments():
    """Shipments with delay > 0, showing origin and delay."""
    return model.select(
        Shipment.id.alias("shipment_id"),
        Shipment.origin.name.alias("origin_site"),
        Shipment.delay_days.alias("delay"),
    ).where(
        Shipment.delay_days > 0,
    ).to_df()


# --- Query 2: Grouped aggregation with .per() ---
def shipments_per_site():
    """Count and total quantity of shipments per origin site."""
    return model.select(
        Site.name.alias("site"),
        aggs.count(Shipment).per(Site).alias("shipment_count"),
        aggs.sum(Shipment.quantity).per(Site).alias("total_quantity"),
    ).where(
        Shipment.origin(Site),
    ).to_df()


# --- Query 3: Multi-hop join with filter ---
def supplier_delays_by_region():
    """Average delay per supplier, filtered to a specific region."""
    Dest = Site.ref()
    # distinct() required: grouping key includes Dest.region (property value, not entity)
    return model.select(
        distinct(
            Business.name.alias("supplier"),
            Dest.region.alias("dest_region"),
            aggs.count(Shipment).per(Business, Dest.region).alias("shipment_count"),
            aggs.sum(Shipment.delay_days).per(Business, Dest.region).alias("total_delay"),
        )
    ).where(
        Shipment.supplier(Business),
        Shipment.destination(Dest),
        Dest.region("North America"),
    ).to_df()


# --- Query 4: Relationship traversal with aliasing ---
def site_to_site_flows():
    """Total flow between origin-destination site pairs."""
    Origin = Site
    Dest = Site.ref()
    return model.select(
        Origin.name.alias("origin"),
        Dest.name.alias("destination"),
        aggs.sum(Shipment.quantity).per(Origin, Dest).alias("total_flow"),
    ).where(
        Shipment.origin(Origin),
        Shipment.destination(Dest),
    ).to_df()
