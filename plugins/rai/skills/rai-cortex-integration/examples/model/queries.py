import relationalai.semantics as rai
from .core import model, Customer, Order


def segment_summary() -> rai.Fragment:
    """Topline metrics per customer value segment"""

    customer = Customer.ref()
    segment = Customer.ValueSegment.ref()
    order = Order.ref()
    g = rai.per(segment)
    return model.select(
        segment.name
        .alias("segment"),
        g.sum(customer.ltv)
        .alias("revenue"),
        g.sum(order.profit)
        .where(customer.order(order))
        .alias("profit")
    ).where(
        customer.value_segment(segment)
    )

#  python -m example.cortex.model.queries
if __name__ == "__main__":
    q = segment_summary()
    q.inspect()
