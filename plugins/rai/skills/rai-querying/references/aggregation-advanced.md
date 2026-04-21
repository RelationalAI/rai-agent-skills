# Advanced Aggregation Patterns

## Table of Contents
- [Conditional aggregation with .where()](#conditional-aggregation-with-where)
- [per().sum() standalone form](#persum-standalone-form)
- [Conditional counting with count(X, condition)](#conditional-counting-with-countx-condition)

---

## Conditional aggregation with .where()

Conditional aggregation with `.where()` on the aggregate acts as a subquery filter:

```python
# Count only orders where customer exists (loyalty orders)
total_loyalty = aggs.count(order).per(Truck).where(order.customer)

# Count only orders where customer does NOT exist
total_unknown = aggs.count(order).per(Truck).where(model.not_(order.customer))

# Count with boolean flag filter
high_priority = aggs.count(line_item).per(line_item.ship_mode).where(
    line_item.order(order),
    (order.priority == "1-URGENT") | (order.priority == "2-HIGH")
)

# Sum with time-window filter
from dateutil.relativedelta import relativedelta
import datetime as org_dt
target = org_dt.datetime(2025, 11, 1)
recent = model.where(Order.order_ts >= target - relativedelta(months=3), Order.order_ts < target)
aggs.sum(Order.total).per(Product).where(recent)
```

---

## per().sum() standalone form

```python
from relationalai.semantics import per

flow_out = per(Edge.source).sum(Edge.flow)
# Equivalent to: sum(Edge.flow).per(Edge.source)
```

`per()` is a standalone function import (`from relationalai.semantics import per`) that provides an alternative grouping syntax. Both `per(X).sum(Y)` and `sum(Y).per(X)` are valid and equivalent.

---

## Conditional counting with count(X, condition)

`count()` accepts a second argument as a condition expression. This works in both query and solver contexts:

```python
# Count how many players are assigned to each group
count(Player, x == group)  # counts players where x_group equals the target group
```

In query contexts, you can also use `.where()` on the aggregate for the same effect (see conditional aggregation above).
