import relationalai.semantics as rai
from .core import model, Customer, Order

Customer.ltv = model.Property(f"{Customer} has lifetime value {rai.Float}")
model.define(
    Customer.ltv(
        rai.sum(Order.price)
        .per(Customer)
        .where(Order.customer(Customer))))

Customer.ValueSegment = model.Concept("CustomerValueSegment", identify_by={"name": rai.String})
CVS = Customer.ValueSegment
CVS.Low = model.Concept("CustomerValueSegmentLow", extends=[CVS])  # type: ignore[reportAttributeAccessIssue, reportArgumentType]
model.define(CVS.Low.new(name="low"))
CVS.Medium = model.Concept("CustomerValueSegmentMedium", extends=[CVS])  # type: ignore[reportAttributeAccessIssue, reportArgumentType]
model.define(CVS.Medium.new(name="medium"))
CVS.High = model.Concept("CustomerValueSegmentHigh", extends=[CVS])  # type: ignore[reportAttributeAccessIssue, reportArgumentType]
model.define(CVS.High.new(name="high"))
Customer.value_segment = model.Property(f"{Customer} comprises {CVS}")
model.define(
    Customer.value_segment(CVS.Low)
).where(
    Customer.ltv < 5)
model.define(
    Customer.value_segment(CVS.Medium)
).where(
    Customer.ltv >= 5,
    Customer.ltv < 8)
model.define(
    Customer.value_segment(CVS.High)
).where(
    Customer.ltv >= 8)

Order.profit = model.Property(f"{Order} yields profit {rai.Float}")
model.define(
    Order.profit(Order.price - Order.cogs))
