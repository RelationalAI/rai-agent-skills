# Advanced Filtering Patterns

## Table of Contents
- [Extended not_() examples](#extended-not_-examples)
- [OR-filtering with model.union()](#or-filtering-with-modelunion)
- [HAVING equivalent](#having-equivalent)

---

## Extended not_() examples

```python
# Negate a comparison
model.not_(Person.age > 40)

# Negate relationship existence (no siblings)
model.select(aggs.count(Person.name)).where(model.not_(Person.brother))
```

### Negation inside an aggregation scope

When the aggregation needs to exclude entities matching some predicate, attach
the `not_()` to the aggregate's own `.where()` and bind the concepts with refs
so the predicate can reference them:

```python
order = Order.ref()
product = Product.ref()
orderitem = OrderItem.ref()

avg_without = aggs.avg(order.total).per(product).where(
    model.not_(order_has_product(order, orderitem, product))
)
```

The refs make the negated predicate a proper quantifier — "average order total,
per product, restricted to orders that do NOT contain that product".

---

## OR-filtering with model.union()

```python
# Match entities satisfying ANY condition (set union, not first-match)
model.where(model.union(
    Person.age < 18,
    Person.age >= 65,
)).select(Person.name).to_df()

# Combine NOT with union (and ordered fallback via |)
model.where(
    model.not_(model.union(Person.age > 30, Person.age < 20)) | (Person.name == "Cleve")
).select(Person.name, Person.age).to_df()
```

For `|` vs `union()` semantics, CASE-WHEN patterns, and multi-component objectives, see `rai-pyrel-coding/expression-rules.md`.

---

## HAVING equivalent

Filter on aggregated values by binding the aggregate in `where()`:

```python
model.where(
    Customer.placed_order(Order),
    Order.ordered_at_location(StoreLocation),
    total_per_store := aggs.sum(Order.total).per(StoreLocation),
    customer_count := aggs.count(Customer).per(StoreLocation),
    total_per_store / customer_count < 500  # HAVING clause equivalent
).select(
    StoreLocation.name.alias("store"),
    total_per_store.alias("total_revenue"),
)
```
