import sys

import pandas
import relationalai.semantics as rai

# Note: this file uses inline data loading, which is suitable for
# examples and small tests, but not for real workloads.
# Use rai.Model.Table() for most programs.

# =============================================================================
# SECTION 1: BASIC QUERY PATTERNS
# =============================================================================


def simple_select(m: rai.Model) -> rai.Fragment:
    """Basic select with property access from inline data."""
    products = m.data([
        {"product_id": 1, "name": "Widget", "price": 29.99},
        {"product_id": 2, "name": "Gadget", "price": 49.99},
        {"product_id": 3, "name": "Doohickey", "price": 19.99},
    ])

    return m.select(
        products.product_id,
        products.name,
        products.price,
    )
    # Output:
    #    product_id       name  price
    # 0           1     Widget  29.99
    # 1           2     Gadget  49.99
    # 2           3  Doohickey  19.99


def select_with_filter(m: rai.Model) -> rai.Fragment:
    """Using m.where() to filter entities before selecting."""
    products = m.data([
        {"product_id": 1, "name": "Widget", "price": 29.99},
        {"product_id": 2, "name": "Gadget", "price": 49.99},
        {"product_id": 3, "name": "Doohickey", "price": 19.99},
        {"product_id": 4, "name": "Thingamajig", "price": 99.99},
    ])

    return m.where(
        products.price > 20,
    ).select(
        products.product_id,
        products.name,
        products.price,
    )
    # Output:
    #    product_id         name  price
    # 0           1       Widget  29.99
    # 1           2       Gadget  49.99
    # 2           4  Thingamajig  99.99


def one_to_many_join(m: rai.Model) -> rai.Fragment:
    """Navigate one-to-many relationships (Customer → Orders)."""
    customers = m.data([
        {"customer_id": 1, "name": "Alice"},
        {"customer_id": 2, "name": "Bob"},
    ])

    orders = m.data([
        {"order_id": 101, "customer_id": 1, "total": 150.00},
        {"order_id": 102, "customer_id": 1, "total": 200.00},
        {"order_id": 103, "customer_id": 2, "total": 75.00},
    ])

    return m.where(
        customers.customer_id == orders.customer_id,
    ).select(
        customers.customer_id,
        customers.name,
        orders.order_id,
        orders.total,
    )
    # Output:
    #    customer_id   name  order_id  total
    # 0            1  Alice       101  150.0
    # 1            1  Alice       102  200.0
    # 2            2    Bob       103   75.0


def multi_level_join(m: rai.Model) -> rai.Fragment:
    """Chain through multiple relationships (Customer → Order → OrderItem → Product)."""
    customers = m.data([
        {"customer_id": 1, "customer_name": "Alice"},
        {"customer_id": 2, "customer_name": "Bob"},
    ])

    orders = m.data([
        {"order_id": 101, "customer_id": 1},
        {"order_id": 102, "customer_id": 2},
    ])

    order_items = m.data([
        {"order_id": 101, "product_id": 1, "quantity": 2},
        {"order_id": 101, "product_id": 2, "quantity": 1},
        {"order_id": 102, "product_id": 1, "quantity": 1},
    ])

    products = m.data([
        {"product_id": 1, "product_name": "Widget"},
        {"product_id": 2, "product_name": "Gadget"},
    ])

    return m.where(
        customers.customer_id == orders.customer_id,
        orders.order_id == order_items.order_id,
        order_items.product_id == products.product_id,
    ).select(
        customers.customer_name,
        orders.order_id,
        products.product_name,
        order_items.quantity,
    )
    # Output:
    #   customer_name  order_id product_name  quantity
    # 0         Alice       101       Gadget         1
    # 1         Alice       101       Widget         2
    # 2           Bob       102       Widget         1


def computed_property(m: rai.Model) -> rai.Fragment:
    """Inline calculations in queries (price * quantity = line_total)."""
    order_items = m.data([
        {"order_id": 101, "product": "Widget", "price": 29.99, "quantity": 2},
        {"order_id": 101, "product": "Gadget", "price": 49.99, "quantity": 1},
        {"order_id": 102, "product": "Widget", "price": 29.99, "quantity": 3},
    ])

    line_total = order_items.price * order_items.quantity

    return m.select(
        order_items.order_id,
        order_items.product,
        order_items.price,
        order_items.quantity,
        line_total.alias("line_total"),
    )
    # Output:
    #    order_id product  price  quantity  line_total
    # 0       101  Gadget  49.99         1       49.99
    # 1       101  Widget  29.99         2       59.98
    # 2       102  Widget  29.99         3       89.97

def pandas_dates(m: rai.Model) -> rai.Fragment:
    orders = m.data(pandas.DataFrame({
        "order_id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "customer_id": [101, 102, 101, 103, 102, 104, 103, 101, 104, 105],
        "order_date": pandas.to_datetime([
            "2024-12-01", "2024-11-15", "2024-12-20", "2024-10-05",
            "2024-12-18", "2024-09-01", "2024-11-30", "2025-01-02",
            "2024-12-25", "2024-08-10",
        ]),
        "amount": [150.0, 200.0, 75.0, 300.0, 120.0, 50.0, 180.0, 90.0, 400.0, 60.0],
    }))
    Order = m.Concept("Order", identify_by={"order_id": rai.Integer})
    m.define(Order.new(orders.to_schema()))

    return m.select(
        Order.order_id,
        Order.order_date,
    )
    #   order_id order_date
    # 0        1 2024-12-01
    # 1        2 2024-11-15
    # 2        3 2024-12-20
    # 3        4 2024-10-05
    # 4        5 2024-12-18
    # 5        6 2024-09-01
    # 6        7 2024-11-30
    # 7        8 2025-01-02
    # 8        9 2024-12-25
    # 9       10 2024-08-10

# =============================================================================
# SECTION 2: AGGREGATION PATTERNS
# =============================================================================


def aggregate_per_group(m: rai.Model) -> rai.Fragment:
    """Multiple aggregates per group using group = rai.per(...) with multiple columns."""
    orders = m.data([
        {"order_id": 101, "customer_id": 1, "product": "Widget", "quantity": 2, "price": 29.99},
        {"order_id": 102, "customer_id": 1, "product": "Widget", "quantity": 3, "price": 29.99},
        {"order_id": 103, "customer_id": 1, "product": "Gadget", "quantity": 1, "price": 49.99},
        {"order_id": 104, "customer_id": 2, "product": "Widget", "quantity": 1, "price": 29.99},
        {"order_id": 105, "customer_id": 2, "product": "Gadget", "quantity": 2, "price": 49.99},
        {"order_id": 106, "customer_id": 2, "product": "Gadget", "quantity": 1, "price": 49.99},
    ])

    group = rai.per(orders.customer_id, orders.product)

    return m.select(m.distinct(
        orders.customer_id,
        orders.product,
        group.count(orders).alias("order_count"),
        group.sum(orders.quantity).alias("total_quantity"),
        group.avg(orders.price).alias("avg_price"),
        group.min(orders.quantity).alias("min_qty"),
        group.max(orders.quantity).alias("max_qty"),
    ))
    # Output:
    #    customer_id product  order_count  total_quantity  avg_price  min_qty  max_qty
    # 0            1  Gadget            1               1      49.99        1        1
    # 1            1  Widget            2               5      29.99        2        3
    # 2            2  Gadget            2               3      49.99        1        2
    # 3            2  Widget            1               1      29.99        1        1


def aggregate_with_conditions(m: rai.Model) -> rai.Fragment:
    """Conditional aggregates using .where() after .per()."""
    orders = m.data([
        {"order_id": 101, "customer_id": 1, "status": "completed", "total": 150.00},
        {"order_id": 102, "customer_id": 1, "status": "completed", "total": 200.00},
        {"order_id": 103, "customer_id": 1, "status": "cancelled", "total": 75.00},
        {"order_id": 104, "customer_id": 2, "status": "completed", "total": 125.00},
        {"order_id": 105, "customer_id": 2, "status": "pending", "total": 100.00},
        {"order_id": 106, "customer_id": 2, "status": "completed", "total": 175.00},
    ])

    total_orders = rai.count(orders).per(orders.customer_id)
    total_amount = rai.sum(orders.total).per(orders.customer_id)
    avg_amount = rai.avg(orders.total).per(orders.customer_id)
    return m.select(m.distinct(
        orders.customer_id,
        total_orders.alias("total_orders"),
        total_orders.where(orders.status == "completed").alias("completed_orders"),
        total_amount.alias("total_amount"),
        total_amount.where(orders.status == "completed").alias("completed_amount"),
        avg_amount.where(orders.total > 100).alias("avg_large_orders"),
    ))
    # Output:
    #    customer_id  total_orders  completed_orders  total_amount  completed_amount  avg_large_orders
    # 0            1             3                 2         425.0             350.0             175.0
    # 1            2             3                 2         400.0             300.0             150.0


def aggregate_with_having(m: rai.Model) -> rai.Fragment:
    """Filter groups based on aggregate results (HAVING clause equivalent)."""
    orders = m.data([
        {"order_id": 101, "customer_id": 1, "total": 150.00},
        {"order_id": 102, "customer_id": 1, "total": 200.00},
        {"order_id": 103, "customer_id": 1, "total": 175.00},
        {"order_id": 104, "customer_id": 2, "total": 75.00},
        {"order_id": 105, "customer_id": 2, "total": 125.00},
        {"order_id": 106, "customer_id": 3, "total": 300.00},
    ])

    order_count = rai.count(orders).per(orders.customer_id)
    total_spent = rai.sum(orders.total).per(orders.customer_id)

    return m.where(
        order_count >= 2,
        total_spent > 200,
    ).select(m.distinct(
        orders.customer_id,
        order_count.alias("order_count"),
        total_spent.alias("total_spent"),
    ))
    # Output:
    #    customer_id  order_count  total_spent
    # 0            1            3        525.0


def aggregate_nested(m: rai.Model) -> rai.Fragment:
    """Nested aggregations - aggregates of aggregates."""
    orders = m.data([
        {"order_id": 101, "customer_id": 1, "total": 150.00},
        {"order_id": 102, "customer_id": 1, "total": 200.00},
        {"order_id": 103, "customer_id": 2, "total": 75.00},
        {"order_id": 104, "customer_id": 2, "total": 125.00},
        {"order_id": 105, "customer_id": 3, "total": 300.00},
        {"order_id": 106, "customer_id": 3, "total": 250.00},
        {"order_id": 107, "customer_id": 3, "total": 275.00},
    ])

    order_count = rai.count(orders).per(orders.customer_id)
    total_spent = rai.sum(orders.total).per(orders.customer_id)

    return m.select(
        rai.max(order_count).alias("max_orders_by_any_customer"),
        rai.min(order_count).alias("min_orders_by_any_customer"),
        rai.avg(order_count).alias("avg_orders_per_customer"),
        rai.max(total_spent).alias("highest_customer_spend"),
        rai.avg(total_spent).alias("avg_customer_spend"),
    )
    # Output:
    #    max_orders_by_any_customer  min_orders_by_any_customer  avg_orders_per_customer  highest_customer_spend  avg_customer_spend
    # 0                           3                           2                 2.333333                   825.0          458.333333


# =============================================================================
# SECTION 3: MODEL DEFINITION PATTERNS
# =============================================================================


def define_entity_with_to_schema(m: rai.Model) -> rai.Fragment:
    """Define a concept and bind data using .to_schema() - the simplest model pattern."""
    products = m.data([
        {"product_id": 1, "name": "Widget", "price": 29.99, "category": "hardware"},
        {"product_id": 2, "name": "Gadget", "price": 49.99, "category": "electronics"},
        {"product_id": 3, "name": "Doohickey", "price": 19.99, "category": "hardware"},
    ])

    # Define a concept and bind data in one step
    # .to_schema() creates entities and populates properties from column names
    Product = m.Concept("Product")
    m.define(Product.new(products.to_schema()))

    # Query uses concept properties (auto-created from column names)
    return m.where(
        Product.price > 20,
    ).select(
        Product.name.alias("name"),
        Product.price.alias("price"),
        Product.category.alias("category"),
    )
    # Output:
    #     name  price    category
    # 0  Gadget  49.99 electronics
    # 1  Widget  29.99    hardware


def define_model_semantics(m: rai.Model) -> rai.Fragment:
    """Define entities, properties, relationships, and computed properties."""
    customers = m.data([
        {"customer_id": 1, "name": "Alice"},
        {"customer_id": 2, "name": "Bob"},
    ])
    orders = m.data([
        {"order_id": 101, "customer_id": 1, "total": 150.00},
        {"order_id": 102, "customer_id": 1, "total": 200.00},
        {"order_id": 103, "customer_id": 2, "total": 75.00},
    ])

    # Define & populate entities
    CustomerID = m.Concept("CustomerID", extends=[rai.Integer])
    Customer = m.Concept("Customer", identify_by={"id": CustomerID})
    rai.define(Customer.new(id=customers.customer_id))

    OrderID = m.Concept("OrderID", extends=[rai.Integer])
    Order = m.Concept("Order", identify_by={"id": OrderID})
    rai.define(Order.new(id=orders.order_id))

    # Define & populate base relationships
    Customer.name = m.Property(f"{Customer} has name {rai.String}")
    rai.define(
        Customer.name(customers.name)
    ).where(
        Customer.id == customers.customer_id
    )

    Order.total = m.Property(f"{Order} has total {rai.Float}")
    rai.define(
        Order.total(orders.total)
    ).where(
        Order.id == orders.order_id
    )

    Customer.placed_order = m.Relationship(f"{Customer} placed order {Order}")
    rai.define(
        Customer.placed_order(Order)
    ).where(
        Customer.id == orders.customer_id,
        Order.id == orders.order_id,
    )

    # Define & populate derived relationships
    Customer.order_count = m.Property(f"{Customer} has order count {rai.Integer}")
    rai.define(
        Customer.order_count(rai.count(Order).per(Customer))
    ).where(
        Customer.placed_order(Order)
    )

    Customer.lifetime_spend = m.Property(f"{Customer} has lifetime spend {rai.Float}")
    rai.define(
        Customer.lifetime_spend(rai.sum(Order.total).per(Customer))
    ).where(
        Customer.placed_order(Order)
    )

    # Query
    return m.select(
        Customer.name.alias("name"),
        Customer.order_count.alias("order_count"),
        Customer.lifetime_spend.alias("lifetime_spend"),
    )
    # Output:
    #    name  order_count  lifetime_spend
    # 0  Alice            2           350.0
    # 1    Bob            1            75.0


def define_entity_subtypes(m: rai.Model) -> rai.Fragment:
    """Define different types of customers"""
    customers = m.data([
        {"customer_id": 1, "name": "Alice", "kind": "online"},
        {"customer_id": 2, "name": "Bob", "kind": "inperson"},
    ])

    # Define & populate entities
    CustomerID = m.Concept("CustomerID", extends=[rai.Integer])
    Customer = m.Concept("Customer", identify_by={"id": CustomerID})
    rai.define(Customer.new(id=customers.customer_id))

    # Define & populate base relationships
    Customer.name = m.Property(f"{Customer} has name {rai.String}")
    rai.define(
        Customer.name(customers.name)
    ).where(
        Customer.id == customers.customer_id
    )

    OnlineCustomer = m.Concept("OnlineCustomer", extends=[Customer])
    rai.define(OnlineCustomer(Customer)).where(
        Customer.id == customers.customer_id,
        "online" == customers.kind,
    )

    # Query
    return m.select(
        OnlineCustomer.name.alias("name"),
    )
    # Output:
    #    name
    # 0  Alice


# =============================================================================
# SECTION 4: Derived RELATIONSHIPS (Business Logic)
# =============================================================================


def derived_classification(m: rai.Model) -> rai.Fragment:
    """Classify entities based on multiple conditions (at-risk customers)."""
    customers = m.data([
        {"customer_id": 1, "name": "Alice", "days_since_order": 45, "order_count": 5, "lifetime_spend": 500.0},
        {"customer_id": 2, "name": "Bob", "days_since_order": 10, "order_count": 2, "lifetime_spend": 150.0},
        {"customer_id": 3, "name": "Carol", "days_since_order": 60, "order_count": 8, "lifetime_spend": 1200.0},
        {"customer_id": 4, "name": "Dave", "days_since_order": 90, "order_count": 1, "lifetime_spend": 50.0},
    ])

    # Define Customer entity
    Customer = m.Concept("Customer")
    m.define(Customer.new(customers.to_schema()))

    # Define AtRiskCustomer entity
    AtRiskCustomer = m.Concept("AtRiskCustomer", extends=[Customer])
    rai.define(AtRiskCustomer(Customer)).where(
        Customer.days_since_order >= 30,
        (Customer.order_count < 3) | (Customer.lifetime_spend < 200),
    )

    return m.select(
        AtRiskCustomer.name,
        AtRiskCustomer.days_since_order,
        AtRiskCustomer.order_count,
        AtRiskCustomer.lifetime_spend,
    )
    # Output:
    #    name  days_since_order  order_count  lifetime_spend
    # 0  Dave                90            1            50.0


def derived_transitive_closure(m: rai.Model) -> rai.Fragment:
    """Derive indirect relationships via transitive closure (task dependencies)."""
    tasks = m.data([
        {"task_id": 1, "name": "Setup DB"},
        {"task_id": 2, "name": "Create Schema"},
        {"task_id": 3, "name": "Load Data"},
        {"task_id": 4, "name": "Build API"},
        {"task_id": 5, "name": "Build UI"},
    ])
    dependencies = m.data([
        {"task_id": 2, "depends_on": 1},  # Schema depends on DB
        {"task_id": 3, "depends_on": 2},  # Load depends on Schema
        {"task_id": 4, "depends_on": 3},  # API depends on Load
        {"task_id": 5, "depends_on": 4},  # UI depends on API
    ])

    # Define Task entity
    Task = m.Concept("Task")
    m.define(Task.new(tasks.to_schema()))

    # Define Task refs to express rules
    task = Task.ref()
    dep = Task.ref()
    intermediate = Task.ref()

    # Direct dependency relationship
    Task.depends_on = m.Relationship(f"{Task} depends on {Task}")
    rai.define(
        task.depends_on(dep)
    ).where(
        task.task_id == dependencies.task_id,
        dep.task_id == dependencies.depends_on,
    )

    # Derived: Transitive closure - all dependencies (direct + indirect)
    Task.all_dependencies = m.Relationship(f"{Task} has dependency {Task}")

    # Base case: direct dependencies
    rai.define(task.all_dependencies(dep)).where(task.depends_on(dep))

    # Recursive case: A depends on B, B has dependency C => A has dependency C
    rai.define(task.all_dependencies(dep)).where(
        task.depends_on(intermediate),
        intermediate.all_dependencies(dep),
    )

    # Query: All dependencies for "Build UI" (task 5)
    return m.select(
        task.name.alias("task"),
        dep.name.alias("dependency"),
    ).where(
        task.task_id == 5,
        task.all_dependencies(dep),
    )
    # Output:
    #       task     dependency
    # 0  Build UI      Build API
    # 1  Build UI  Create Schema
    # 2  Build UI      Load Data
    # 3  Build UI       Setup DB


def derived_frequently_bought_together(m: rai.Model) -> rai.Fragment:
    """Derive product affinity from co-occurrence in orders, using refs to write logic with multiple instances of the same entity."""
    orders = m.data([
        {"order_id": 1}, {"order_id": 2}, {"order_id": 3}, {"order_id": 4},
    ])
    products = m.data([
        {"product_id": 1, "name": "Coffee"},
        {"product_id": 2, "name": "Croissant"},
        {"product_id": 3, "name": "Muffin"},
        {"product_id": 4, "name": "Tea"},
    ])
    order_items = m.data([
        {"order_id": 1, "product_id": 1}, {"order_id": 1, "product_id": 2},  # Coffee + Croissant
        {"order_id": 2, "product_id": 1}, {"order_id": 2, "product_id": 2},  # Coffee + Croissant
        {"order_id": 3, "product_id": 1}, {"order_id": 3, "product_id": 3},  # Coffee + Muffin
        {"order_id": 4, "product_id": 4}, {"order_id": 4, "product_id": 2},  # Tea + Croissant
    ])

    # Define entities
    Order = m.Concept("Order")
    m.define(Order.new(orders.to_schema()))

    Product = m.Concept("Product")
    m.define(Product.new(products.to_schema()))

    # Define refs
    order = Order.ref()
    product_a = Product.ref()
    product_b = Product.ref()

    # Order contains product relationship
    Order.contains = m.Relationship(f"{Order} contains {Product}")
    rai.define(order.contains(product_a)).where(
        order.order_id == order_items.order_id,
        product_a.product_id == order_items.product_id,
    )

    # Derived: Co-occurrence count (products ordered together)
    cooccurrence_count = rai.count(order).per(product_a, product_b).where(
        order.contains(product_a),
        order.contains(product_b),
        product_a < product_b,  # Avoid duplicates and self-pairs
    )

    # Query: Product pairs ordered together 2+ times
    return m.select(
        product_a.name.alias("product_a"),
        product_b.name.alias("product_b"),
        cooccurrence_count.alias("times_together"),
    ).where(
        cooccurrence_count >= 2,
    )
    # Output:
    #   product_a  product_b  times_together
    # 0 Croissant     Coffee               2


def derived_rank_based_property(m: rai.Model) -> rai.Fragment:
    """Derive classification based on relative ranking (top N performers)."""
    salespeople = m.data([
        {"rep_id": 1, "name": "Alice", "revenue": 150000},
        {"rep_id": 2, "name": "Bob", "revenue": 120000},
        {"rep_id": 3, "name": "Carol", "revenue": 180000},
        {"rep_id": 4, "name": "Dave", "revenue": 90000},
        {"rep_id": 5, "name": "Eve", "revenue": 200000},
    ])

    # Define SalesRep entity
    SalesRep = m.Concept("SalesRep")
    m.define(SalesRep.new(salespeople.to_schema()))

    # Define refs
    rep = SalesRep.ref()

    # Derived: Top performer if rank <= 2
    TopPerformer = m.Concept("TopPerformer", extends=[SalesRep])
    rai.define(
        TopPerformer(rep)
    ).where(
        rai.rank(rai.desc(rep.revenue)) <= 2
    )

    # Query: Show top performers
    return m.select(
        TopPerformer.revenue,
        TopPerformer.name,
    )
    # Output:
    #   revenue   name
    # 0  180000  Carol
    # 1  200000    Eve


QUERIES = {
    "simple_select": simple_select,
    "select_with_filter": select_with_filter,
    "one_to_many_join": one_to_many_join,
    "multi_level_join": multi_level_join,
    "computed_property": computed_property,
    "aggregate_per_group": aggregate_per_group,
    "aggregate_with_conditions": aggregate_with_conditions,
    "aggregate_with_having": aggregate_with_having,
    "aggregate_nested": aggregate_nested,
    "define_entity_with_to_schema": define_entity_with_to_schema,
    "define_model_semantics": define_model_semantics,
    "define_entity_subtypes": define_entity_subtypes,
    "derived_classification": derived_classification,
    "derived_transitive_closure": derived_transitive_closure,
    "derived_frequently_bought_together": derived_frequently_bought_together,
    "derived_rank_based_property": derived_rank_based_property,
    "pandas_dates": pandas_dates,
}


if __name__ == "__main__":
    query_name = sys.argv[1] if len(sys.argv) > 1 else "q1"

    if query_name not in QUERIES:
        print(f"Unknown query: {query_name}")
        print(f"Available queries: {', '.join(QUERIES.keys())}")
        sys.exit(1)

    m = rai.Model("cheat_sheet")
    query = QUERIES[query_name]
    result = query(m).to_df()
    print(result)
