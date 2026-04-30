# Pattern: Aggregation-based derived property — order total computed from line items.
# Key ideas: sum().per() for grouped aggregation; relationship navigation in
# aggregate-local .where(); property materialization; fallback with | 0 for
# groups with no matches.

from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.std import aggregates
import relationalai.semantics as rai

model = Model("derivation_rule")

# --- Ontology ---

Order = model.Concept("Order", identify_by={"id": Integer})
Order.status = model.Property(f"{Order} has {String:status}")

LineItem = model.Concept("LineItem", identify_by={"id": Integer})
LineItem.quantity = model.Property(f"{LineItem} has {Integer:quantity}")
LineItem.unit_price = model.Property(f"{LineItem} has {Float:unit_price}")
LineItem.order = model.Property(f"{LineItem} belongs to {Order:order}")

# --- Derivation Rule 1: Line item total ---
# NL: "Each line item's total equals quantity times unit price"

LineItem.line_total = model.Property(f"{LineItem} has {Float:line_total}")
model.define(LineItem.line_total(LineItem.quantity * LineItem.unit_price))

# --- Derivation Rule 2: Order total via aggregation ---
# NL: "Order total equals sum of its line item totals"

Order.total_value = model.Property(f"{Order} has {Float:total_value}")
total = aggregates.sum(LineItem.line_total).per(Order).where(LineItem.order(Order))
model.define(Order.total_value(total))

# --- Derivation Rule 3: Line item count with fallback ---
# NL: "Count of line items per order (0 if none)"

Order.item_count = model.Property(f"{Order} has {Integer:item_count}")
count = aggregates.count(LineItem).per(Order).where(LineItem.order(Order)) | 0
model.define(Order.item_count(count))

# --- Chained Rule: Flag high-value orders ---
# NL: "Order is high value if total exceeds 1000"

Order.is_high_value = model.Relationship(f"{Order} is high value")
model.where(Order.total_value > 1000).define(Order.is_high_value())

# --- Query ---

print("High-value orders:")
model.where(Order.is_high_value()).select(
    Order.id.alias("order_id"),
    Order.total_value.alias("total"),
    Order.item_count.alias("items"),
).inspect()
