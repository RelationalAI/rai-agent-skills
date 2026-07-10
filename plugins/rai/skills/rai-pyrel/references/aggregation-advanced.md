# Advanced Aggregation Patterns

## Table of Contents
- [Conditional aggregation with .where()](#conditional-aggregation-with-where)
- [per().sum() standalone form](#persum-standalone-form)
- [Conditional counting with count(X, condition)](#conditional-counting-with-countx-condition)
- [product (multiplicative aggregate)](#product)
- [stddev_samp (sample standard deviation)](#stddev_samp)
- [Ranking aggregates](#ranking-aggregates)

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

---

## product

`product` (as of `relationalai>=1.12`) multiplies numeric values within a group, taking `.per(...)`, `.where(...)`, and `.alias(...)` like any other aggregate:

```python
# Compound factor per group — multiply each row's ratio within the group
aggs.product(Period.factor).per(Scenario).alias("compound_factor")
```

**It always returns `Float`** — integer inputs are cast before aggregation. The result is computed with an exp-log identity (`exp(sum(log|x|))`), so it is a floating-point *approximation*, not an exact product: round (or compare with a tolerance) when you need an integer, and expect rounding error to accumulate across many factors. Negative values are handled — the result's sign follows the parity of the negative-value count; a zero yields `0.0` and stays contained to its own group, leaving other groups unaffected.

**Query-only, like `avg`:** `product` raises `NotImplementedError` over decision variables in solver `satisfy/minimize/maximize` expressions (solver-supported aggregates are `sum, min, max, count`). A pure-data `product` used as a constant in an otherwise-symbolic solver expression still passes through.

---

## stddev_samp

`stddev_samp` (as of `relationalai>=1.12`) computes the **sample** standard deviation — the square root of the sample variance (an `n-1` denominator) — taking `.per(...)`, `.where(...)`, and `.alias(...)` like any other aggregate:

```python
# Sample standard deviation per group
aggs.stddev_samp(Measurement.value).per(Batch).alias("value_stddev")
```

**It always returns `Float`** (integer inputs are cast). The `_samp` suffix marks the sample estimator (divides by `n-1`); for population spread (divide by `n`), compute it manually.

**Query-only, like `avg`:** `stddev_samp` raises `NotImplementedError` over decision variables in solver `satisfy/minimize/maximize` expressions (solver-supported aggregates are `sum, min, max, count`).

---

## Ranking aggregates

Express ranking and top-N **in-query** (in `where()`/`select()`) — don't pull rows into pandas to sort or slice. Each takes `.per(group)` for per-group scope, with the group bound by an inner (or sibling) `.where(...)`.

**Top-N / bottom-N — filter rows in `where()`:**

```python
# Keep the 5 highest rows overall — no pandas slice
model.where(aggs.top(5, MachineRisk.failure_probability)).select(
    MachineRisk.machine_id.alias("machine_id"),
    MachineRisk.failure_probability.alias("p"),
).to_df()

# Top 3 per group: top(N, expr).per(Group), group bound inside .where()
model.where(aggs.top(3, Product.revenue).per(Store).where(Product.store == Store)).select(
    Store.name.alias("store"),
    Product.name.alias("product"),
).to_df()
```

`aggs.bottom(N, expr)` is the ascending counterpart; `aggs.limit(N, aggs.desc(expr))` / `aggs.limit(N, aggs.asc(expr))` is the general form that `top`/`bottom` shorthand.

**Rank — a rank value as a `select()` column:**

```python
# rank(asc(...)) for ascending; rank_asc / rank_desc are shorthands for rank(asc/desc(...))
model.where(Product.store == Store).select(
    Product.name.alias("product"),
    aggs.rank(aggs.desc(Product.revenue)).per(Store).alias("rank_in_store"),
).to_df()
```

**Running totals — not available on the SQL backend.** `cumsum_asc` exists in the aggregates API, but on the SQL backend (the `raiconfig` default) it errors at execution — it lowers to a `CUMSUM` call that no SQL dialect provides (verified on duckdb; `relationalai` 1.12–1.13). Don't reach for it there until that gap is fixed.
