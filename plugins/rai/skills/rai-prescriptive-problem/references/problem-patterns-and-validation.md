<!-- TOC -->
- [Common Problem Patterns](#common-problem-patterns)
  - [Assignment / scheduling](#assignment--scheduling)
  - [Network flow](#network-flow)
  - [Diet / blending](#diet--blending)
  - [Facility location](#facility-location)
  - [TSP / vehicle routing](#tsp--vehicle-routing)
  - [Multi-period / time-indexed models](#multi-period--time-indexed-models)
- [Temporal Filtering](#temporal-filtering)
  - [Date column filtering](#date-column-filtering)
  - [Epoch timestamp filtering](#epoch-timestamp-filtering)
- [Problem Type Classification](#problem-type-classification)
<!-- /TOC -->

## Common Problem Patterns

Each pattern shows the minimal skeleton. Key heuristic in bold.

From `relationalai>=1.29`, `problem.display()` raises `ValueError` unless **every** decision variable in the Problem carries a `name=`, not just the ones you read, and it checks once at least one variable has grounded. Pass a discriminating `name=["x", Entity.id]` on each `solve_for`. The skeletons below omit it where it would obscure the pattern.

### Assignment / scheduling

**Key:** Binary variables scoped to valid pairs only (`where=[availability_relationship]`). Needs both per-slot coverage AND per-resource limits.

```python
problem.solve_for(Worker.x_assign(Shift, x), type="bin",
            where=[Worker.available_for(Shift)])
problem.satisfy(model.require(sum(Worker, x).per(Shift) >= min_coverage))   # forcing
problem.satisfy(model.require(sum(Shift, x).per(Worker) <= max_shifts))     # capacity
```

### Network flow

**Key:** Flow conservation (inflow == outflow at interior nodes) via `.ref()` on Edge concept. Two refs iterate independently.

```python
problem.solve_for(Edge.flow, lower=0, upper=Edge.cap)
Ei, Ej = Edge.ref(), Edge.ref()
problem.satisfy(model.require(per(Ej.j).sum(Ej.flow) == per(Ei.i).sum(Ei.flow)).where(Ei.i == Ej.j))
```

**Anti-pattern: Item x Edge cross-product.**

When the model has EDGE concepts (with source/destination) and ITEM concepts (with origin/destination), you must choose the correct formulation pattern:

**WRONG (causes INFEASIBLE or trivial solutions):**
```python
# Creating Item x Edge cross-product
model.define(ShipmentRouting.new(shipment=Shipment, operation=Operation))
# Then adding site matching constraints in .where()
# PROBLEM: Most combinations are INVALID because edges don't connect to item locations
```

**RIGHT (use flow-on-edges):**
```python
# Put flow variable directly on the edge concept
problem.solve_for(Operation.flow_quantity, type='cont', lower=0, upper=Operation.capacity)
# Add conservation constraints at nodes via model.require()
# Add source/sink constraints for supply/demand
```

**When to use each pattern:**
- **Flow-on-edges:** When you do NOT need to track individual items through the network (aggregate flow, water allocation, general network design)
- **Filtered Item x Edge:** ONLY if edges actually connect item origins to destinations — **verify with a data query first** before assuming the cross-product is valid

**Data verification requirement:** Before creating any cross-product entity, query the actual data to confirm the join conditions will produce valid (non-empty) entity sets. A cross-product where most entities are filtered out by `.where()` is a sign the wrong pattern was chosen.

### Diet / blending

**Key:** Multiarity property binding (`Food.contains(Nutrient, qty)`) for ternary data. Constraints are per-nutrient bounds.

```python
problem.solve_for(Food.amount, lower=0)
qty = Float.ref()
total = sum(qty * Food.amount).where(Food.contains(Nutrient, qty)).per(Nutrient)
problem.satisfy(model.require(total >= Nutrient.min, total <= Nutrient.max))
```

### Facility location

**Key:** Binary open/close variable linked to flow via capacity constraint (`flow <= capacity * x_open`). Multi-component objective adds separately defaulted totals.

```python
problem.solve_for(Facility.x_open, type="bin")
problem.solve_for(Route.x_flow, lower=0)
problem.satisfy(model.require(sum(Route.x_flow).per(Facility) <= Facility.capacity * Facility.x_open))
problem.satisfy(model.require(sum(Route.x_flow).per(Customer) >= Customer.demand))  # forcing
problem.minimize((sum(Facility.fixed_cost * Facility.x_open) | 0.0)
                 + (sum(Route.transport_cost * Route.x_flow) | 0.0))
```

### TSP / vehicle routing

**Key:** Degree constraints (exactly 1 in-edge, 1 out-edge per node). MTZ subtour elimination with auxiliary ordering variable `u`. Symmetry breaking fixes one node.

```python
problem.solve_for(Edge.x, type="bin")
problem.solve_for(Node.u, type="int", lower=1, upper=node_count)
# Degree: sum(Edge.x).per(Node) == 1 for both in-edges and out-edges
# MTZ: Ni.u - Nj.u + node_count * Edge.x <= node_count - 1 (for non-depot nodes)
# Symmetry: model.require(Node.u == 1).where(Node.v(1))
```

### Multi-period / time-indexed models

**Key:** Two approaches -- (1) cross-product concept (`MachinePeriod`) for entity-per-period decisions, or (2) multiarity property (`ResourceGroup.inv(t, x_inv)`) for time-indexed variables with `where=[t == range(...)]`.

**Inventory balance** links consecutive time steps:

```python
problem.satisfy(model.where(
    x_inv1 := Float.ref(), x_inv2 := Float.ref(),
    ResourceGroup.inv(t, x_inv1), ResourceGroup.inv(t + 1, x_inv2),
    Mode.qty_mode(ResourceGroup, t, x_qty_mode),
).require(x_inv1 == x_inv2 + sum(Mode, x_qty_mode).per(ResourceGroup, t)))
```

**Cumulative / running-sum** uses two refs with time-ordering. This `define()` is derived data, not a solver expression: `satisfy()` on `cumulative_production` raises `ValueError: Expression does not reference any decision variables`. To constrain a running total, use a cumulative variable with a recurrence: [constraint-formulation.md](constraint-formulation.md) > Temporal recurrence.

```python
Tx, Ty = Period.ref(), Period.ref()
model.where(Tx.pid <= Ty.pid).define(
    MachinePeriod.cumulative_production(sum(MachinePeriod.x_production).where(
        MachinePeriod.period(Tx)).per(Machine, Ty)))
```

### Pricing / markdown optimization

**Key:** One-hot binary selection from a discrete price/discount set per entity per period. Monotone price ladder via consecutive-period mutual exclusion. Cumulative tracking with temporal recurrence.

Code: [constraint-formulation.md](constraint-formulation.md) > One-hot selection, Temporal recurrence, and Monotone ordering. See `../examples/one_hot_temporal_recurrence.py`.

### Piecewise linear (PWL) cost approximation

**Key:** Reify cost segments as concept instances. Each segment gets a continuous remainder variable capped by its limit, and a binary active indicator. Exactly one segment active. Total = remainder of active segment + full capacity of lower segments.

```python
# Segment activation: exactly one active
problem.satisfy(model.require(sum(Segment, y_bin).per(t) == 1).where(...))
# Remainder within limit
problem.satisfy(model.require(x_rem <= Segment.limit * y_bin).where(...))
# Weight decomposition: active remainder + lower segments' full capacities
problem.satisfy(model.where(...).require(
    x_weight == sum(Segment, x_rem).per(t) +
    sum(Seg2, Seg1.limit * y_bin).where(Seg1.seg == Seg2.seg - 1).per(t)))
```

See `../examples/multi_concept_added_objective.py`.

---

## Temporal Filtering

Time-scoped constraints restrict optimization to a specific time window by applying `.where()` filters on date or epoch timestamp columns.

### Date column filtering

```python
from datetime import date
problem.satisfy(model.require(
    sum(Demand.x_fulfilled).per(Product) >= sum(Demand.quantity).per(Product)
).where(Demand.due_date >= date(2025, 11, 1), Demand.due_date <= date(2025, 11, 30)))
```

Compare a `Date` property with a `datetime.date`: a string literal fails at compile with `TypeMismatch: Expected 'Date', got 'String'`.

### Epoch timestamp filtering

```python
problem.satisfy(model.require(
    sum(PullRequest.x_selected).per(Repo) <= max_reviews
).where(PullRequest.created_at >= 1759302000, PullRequest.created_at <= 1761894000))
```

Apply temporal filters on the **aggregation concept** (the one being summed/counted), not the grouping concept. Prefer filtering at the constraint level rather than creating separate filtered concepts.

---

## Problem Type Classification

Problem-type signatures and solver choice: `SKILL.md` > Problem Type Classification and Solver Selection. Business problem types (allocation, network, routing, scheduling, pricing), their structural signals and disambiguation: `rai-discovery/references/prescriptive.md` > Optimization Problem Types.

---

## Multi-Objective Validation

Validating two-objective (epsilon-constraint) formulations — tension, scale, anchors, pitfalls: [multi-objective-formulation.md](multi-objective-formulation.md).
