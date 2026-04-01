<!-- TOC -->
- [Multi-Entity Subtype Rules (Cross-Entity Joins)](#multi-entity-subtype-rules-cross-entity-joins)
- [Rule Dependency Building Blocks](#rule-dependency-building-blocks)
<!-- /TOC -->

## Multi-Entity Subtype Rules (Cross-Entity Joins)

Complex rules can span multiple entities via relationship traversal in `.where()`. When PyRel joins
through relationships, it acts as an **existential check** — "there exists a related entity where
this condition is true."

```python
# Subtype spanning 3 entities: flag orders where
#   1. Order is overdue (boolean flag)
#   2. Customer is high-risk (existing subtype)
#   3. Warehouse has low stock on the ordered product
RiskyOverdueOrder = model.Concept("RiskyOverdueOrder", extends=[Order])

model.define(RiskyOverdueOrder(Order)).where(
    Order.is_overdue(),                    # boolean flag filter
    Order.customer(Customer),              # join to Customer
    HighRiskCustomer(Customer),            # existing subtype check
    Order.product(Product),                # join to Product
    Product.stocked_at(Warehouse),         # join to Warehouse
    Warehouse.stock_level < 10,            # threshold on related entity
)
```

**Key patterns in complex rules:**
- **OR conditions** → separate `model.define()` calls (never use `|` operator in subtype `where()`)
- **Existential joins** → relationship traversal in `where()` acts as "there exists"
- **Mixing subtypes** → reference existing subtypes (e.g., `HighRiskCustomer(Customer)`) as conditions
- **Boolean flags as filters** → use `Entity.is_flag()` in `where()`, not in `select()`
- **Multi-hop traversal** → chain relationships: `Entity_A → Entity_B → Entity_C` via multiple `where()` conditions

For a real-world 5-entity example with OR branches, see
[complex-rule-example.md](complex-rule-example.md).

---

## Rule Dependency Building Blocks

Build complex rules by layering simpler components:

```python
# Layer 1: Computed property
Order.fulfillment_ratio = model.Property(...)
model.define(Order.fulfillment_ratio(
    Order.shipped_qty / Order.ordered_qty
)).where(Order.ordered_qty > 0)

# Layer 2: Boolean flag (OR via multiple define calls)
Order.is_delayed = model.Relationship(...)
model.define(Order.is_delayed()).where(Order.status == "backordered")
model.define(Order.is_delayed()).where(Order.status == "on_hold")

# Layer 3: Subtype combining layers 1 + 2
CriticallyDelayedOrder = model.Concept("CriticallyDelayedOrder", extends=[Order])
model.define(CriticallyDelayedOrder(Order)).where(
    Order.is_delayed(),
    Order.fulfillment_ratio < 0.5,
)
```
