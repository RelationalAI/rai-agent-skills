# Pattern: Multi-tier classification with typed sub-concepts and mutually exclusive conditions.
# Key ideas: Typed sub-concepts for categories (not string Properties); use < on upper bound
# and >= on lower bound to prevent overlap; string normalization for text-based classification;
# default catch-all for unclassified entities.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import strings
import relationalai.semantics as rai

model = Model("classification_example")

# --- Ontology ---

Customer = model.Concept("Customer", identify_by={"id": Integer})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.lifetime_spend = model.Property(f"{Customer} has {Float:lifetime_spend}")
Customer.account_type = model.Property(f"{Customer} has {String:account_type}")

# --- Classification Rule 1: Spend-based tiers ---
# NL: "Segment customers: VIP if spend >= 50K, Gold >= 10K, Silver >= 1K, Bronze otherwise"

# Define segment hierarchy
CustomerValueSegment = model.Concept("CustomerValueSegment")
ValueSegmentVIP = model.Concept("ValueSegmentVIP", extends=[CustomerValueSegment])
ValueSegmentGold = model.Concept("ValueSegmentGold", extends=[CustomerValueSegment])
ValueSegmentSilver = model.Concept("ValueSegmentSilver", extends=[CustomerValueSegment])
ValueSegmentBronze = model.Concept("ValueSegmentBronze", extends=[CustomerValueSegment])

# Create named instances
SegmentName = model.Concept("SegmentName", extends=[String])
model.define(ValueSegmentVIP.new(name=SegmentName("VIP")))
model.define(ValueSegmentGold.new(name=SegmentName("Gold")))
model.define(ValueSegmentSilver.new(name=SegmentName("Silver")))
model.define(ValueSegmentBronze.new(name=SegmentName("Bronze")))

# Assign based on score thresholds (mutually exclusive conditions)
Customer.value_segment = model.Relationship(f"{Customer} has value segment {CustomerValueSegment}")

model.where(Customer.lifetime_spend >= 50000).define(
    Customer.value_segment(ValueSegmentVIP)
)
model.where(
    Customer.lifetime_spend >= 10000,
    Customer.lifetime_spend < 50000,
).define(Customer.value_segment(ValueSegmentGold))
model.where(
    Customer.lifetime_spend >= 1000,
    Customer.lifetime_spend < 10000,
).define(Customer.value_segment(ValueSegmentSilver))
model.where(Customer.lifetime_spend < 1000).define(
    Customer.value_segment(ValueSegmentBronze)
)

# --- Classification Rule 2: Text-based category ---
# NL: "Classify account type as enterprise, startup, or individual based on name prefix"

# Define category hierarchy
AccountSegment = model.Concept("AccountSegment")
EnterpriseSegment = model.Concept("EnterpriseSegment", extends=[AccountSegment])
StartupSegment = model.Concept("StartupSegment", extends=[AccountSegment])
IndividualSegment = model.Concept("IndividualSegment", extends=[AccountSegment])

AccountSegmentName = model.Concept("AccountSegmentName", extends=[String])
model.define(EnterpriseSegment.new(name=AccountSegmentName("enterprise")))
model.define(StartupSegment.new(name=AccountSegmentName("startup")))
model.define(IndividualSegment.new(name=AccountSegmentName("individual")))

Customer.account_segment = model.Relationship(f"{Customer} has account segment {AccountSegment}")
name_lower = strings.lower(strings.strip(Customer.account_type))

model.where(strings.startswith(name_lower, "enterprise")).define(
    Customer.account_segment(EnterpriseSegment)
)
model.where(strings.startswith(name_lower, "startup")).define(
    Customer.account_segment(StartupSegment)
)
# Default catch-all for entities not matching specific conditions
model.where(
    Customer,
    model.not_(Customer.account_segment),
).define(Customer.account_segment(IndividualSegment))

# --- Query: distribution of tiers ---

from relationalai.semantics.std import aggregates

print("Value tier distribution:")
model.where(
    Customer.value_segment(CustomerValueSegment),
).select(
    CustomerValueSegment.name.alias("tier"),
    aggregates.count(Customer).per(CustomerValueSegment).alias("count"),
).inspect()

# --- Verify exhaustiveness: no customer should lack a segment ---

unclassified = model.where(
    Customer, model.not_(Customer.value_segment)
).select(Customer.id).to_df()
print(f"\nUnclassified customers: {len(unclassified)}")
