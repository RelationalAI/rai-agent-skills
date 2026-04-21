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

# Negate a union (NOT OR) — people aged 20-30
model.where(model.not_(model.union(Person.age > 30, Person.age < 20)))

# Negate relationship existence (no siblings)
model.select(aggs.count(Person.name)).where(model.not_(Person.brother))
```

---

## OR-filtering with model.union()

```python
# Match entities satisfying ANY condition (set union, not first-match)
model.where(model.union(
    Person.age < 18,
    Person.age >= 65,
)).select(Person.name).to_df()

# Combine NOT with union
model.where(
    model.not_(model.union(Person.age > 30, Person.age < 20)) | (Person.name == "Cleve")
).select(Person.name, Person.age).to_df()
```

The `|` operator evaluates branches left-to-right and picks the first that succeeds (ordered fallback / if-then-else), while `model.union()` collects ALL matching branches (set union). Use `|` for defaults (`status | "missing"`) and case-when chains; use `model.union()` for multi-term objectives or OR-filtering. For full semantics, CASE-WHEN patterns, and multi-component objective use, see `rai-pyrel-coding/expression-rules.md`.

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
