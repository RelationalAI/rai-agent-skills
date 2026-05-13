<!-- TOC -->
- [Expression Rules](#expression-rules)
  - [.where() -- valid targets](#where----valid-targets)
  - [Server-Side vs Client-Side Filtering](#server-side-vs-client-side-filtering)
  - [.per() -- grouped aggregation](#per----grouped-aggregation)
  - [Combined .where().per() for Grouped Aggregation](#combined-whereper-for-grouped-aggregation)
  - [Property Chains in .where() Clauses](#property-chains-in-where-clauses)
  - [Operators: .in_(), model.not_(), |, &](#operators-in_-modelnot_--)
  - [model.union() -- set-style OR combinator](#modelunion----set-style-or-combinator)
  - [| operator -- ordered fallback / if-then-else](#-operator----ordered-fallback--if-then-else)
  - [Entity instance comparison](#entity-instance-comparison)
  - [Chain.ref() and .alt()](#chainref-and-alt)
<!-- /TOC -->

## Expression Rules

### `.where()` — valid targets

`.where()` is valid on:
- **Aggregation:** `sum(X.prop).where(...)` — filter contributing entities
- **Constraint:** `model.require(...).where(...)` — filter constraint scope
- **Definition:** `model.define(...).where(...)` — conditional entity creation
- **Query:** `select(...).where(...)` — filter query results

**INVALID targets:**
```python
Site.where(Site.type == 'warehouse')          # NotImplementedError
Entity.binary_var.where(Entity.id == other.id) # NotImplementedError
sum(Flow.x_qty).per(Site.where(Site.is_active))  # NotImplementedError
```

### Server-Side vs Client-Side Filtering

Prefer server-side `.where()` filtering over client-side DataFrame filtering:

```python
# PREFERRED: Server-side filtering (efficient, runs in RAI engine)
results = where(Food.x_amount > 0.001).select(Food.name, Food.x_amount).to_df()

# AVOID: Client-side filtering (fetches all rows, filters in Python)
df = select(Food.name, Food.x_amount).to_df()
results = df[df["amount"] > 0.001]
```

### `.per()` — grouped aggregation

Groups an aggregation by one or more concepts. Two equivalent forms:

- **Method chaining:** `sum(X).per(A, B)` — grouping declared after the aggregation
- **Standalone:** `per(A, B).sum(X)` — grouping declared before the aggregation

**Captured `per()` for reuse:** When multiple aggregations share the same grouping keys, capture the standalone `per()` in a variable to avoid repeating the keys:

```python
# Instead of repeating .per(LineItem.code, LineItem.status) on each aggregation:
group = per(LineItem.code, LineItem.status)
result = model.select(
    LineItem.code, LineItem.status,
    group.sum(LineItem.amount).alias("total"),
    group.count(LineItem).alias("cnt"),
)

# Also works in model.define():
model.define(LineItem.group_total(group.sum(LineItem.amount)))
```

For applied aggregation patterns, see `rai-querying`.

### Combined `.where().per()` for Grouped Aggregation

Use `.where()` to define the join condition and `.per()` to define the grouping granularity. This is the key pattern for per-entity aggregation across related concepts:

```python
# Sum of operation flows per SKU (join via shared SKU relationship)
inflow_per_sku = sum(Operation.x_flow).where(Operation.output_sku == UnmetDemand.sku).per(UnmetDemand.sku)
demand_per_sku = sum(Demand.quantity).where(Demand.sku == UnmetDemand.sku).per(UnmetDemand.sku)
```

**Key rules:**
- `.where(X.relationship == Y)` defines the join (which entities contribute to the sum)
- `.per(Y)` defines the grouping (one aggregated value per Y entity)
- Bare `Concept` references unify across the chain — repeated mentions of the same Concept refer to one shared free variable. Reach for `.ref()` only when you need two independent variables of the same Concept (pairwise / self-join). See SKILL.md > Free-Variable Scoping.

### Property Chains in `.where()` Clauses

Multi-hop chains (`Concept.fk.prop`) are valid inside `.where()` clauses and resolve to the chained value — the join is materialized in-engine. Both literal-eq (`Customer.site.name == "s1"`) and entity-eq (`Op.dest_site == Demand.customer.site`) forms work.

```python
# Both compile and produce the expected join:
sum(Op.x_flow).where(Op.dest_site == Demand.customer.site).per(Demand)
model.where(Customer.site.name == "s1").select(Customer.cid)
```

If a chained `.where()` returns empty results, the cause is usually the chain itself being unpopulated (an FK Property declared but never filled by `model.define(...)`), not the chaining mechanic. Aggregating at a shared dimension is sometimes simpler to reason about, but it is not required.

### Operators: `.in_()`, `model.not_()`, `|`, `&`

```python
X.field.in_(["A", "B"])                # Set membership
model.not_(order.customer)               # Negation (entities that DON'T match)
(X.a == 1) | (X.a == 2)               # OR
(X.a >= 10) & (X.a <= 50)             # AND
```

### `model.union()` — set-style OR combinator

`model.union()` combines results from ALL matching branches (set union). Three primary uses:

**1. OR-filtering in `where()` clauses:**

```python
# Match people who are young OR old (both branches contribute)
model.where(model.union(Person.age < 18, Person.age >= 65)).select(Person.name)
```

**2. Summing multi-component objectives across concept scopes:**

```python
total = sum(model.union(term_a, term_b, term_c))
problem.minimize(total)
```

Each term may involve different concepts and `.where()` conditions. Required when building multi-component objectives or aggregations that span concept boundaries.

**3. CASE WHEN — union of filtered fragments returning labels:**

```python
# All matching branches contribute (a person can have multiple rights)
rights = union(
    where(Person.age >= 60).select("CanRetire"),
    where(Person.age >= 18).select("CanVote"),
    where(Person.age >= 16).select("CanDrive"),
    select("RightToUniversalHealthcare"),  # default: everyone
)
select(Person.name, rights).to_df()
```

**Rule:** All branches in a `union()` must return the same number of values (same "shape"). A bare relation call (e.g., `a.parents(c)`) returns 1 value, while `where(...)` without `select()` returns 0 (a filter). Mixing these causes `[Inconsistent branches] All branches in a Union must have the same number of returned values`. Similarly, two Fragments with different numbers of `select()` columns are incompatible. Fix by making all branches return the same count: either chain relation calls so all branches return values, or wrap all branches in `where(...)` so all return Fragments with matching `select()` columns.

**Recursive rules with `union`:** You can write recursive `model.define()` rules using `union` in a single define. Wrap each branch in `where(...)` so both return Fragments:

```python
a, b, c = Person.ref(), Person.ref(), Person.ref()
model.define(a.ancestors(c)).where(
    union(
        where(a.parents(c)),                      # base case
        where(a.ancestors(b), b.parents(c))       # recursive case
    )
)
```

Both branches are Fragments, so the union is type-consistent. The two-`define` approach (one for base case, one for recursive case) is also valid and often clearer.

**Note:** When used inside an outer `select(Person.name, rights)`, entities that match NO branch still appear in the result with `NaN` for the union column. Filter with `.where()` or use `dropna()` if you need only matched rows.

### `|` operator — ordered fallback / if-then-else

The `|` operator evaluates branches left-to-right and picks the **FIRST that succeeds** (unlike `union()` which collects ALL). Use for defaults and conditional logic:

**Default values (COALESCE):**

```python
status = User.status | "missing"               # default if property absent
total = count(Person.age) | 0                    # default for empty aggregation
value = (Person.coolness + Person.age) | 0       # default for expression
```

**If-then-else chains (ordered priority):**

```python
# First matching branch wins — like CASE WHEN
age_group, coolness = (
    where(Person.age >= 65).select("Senior", 1000) |
    where(Person.age >= 18).select("Adult", 0) |
    select("Child", 10000000)  # default
)
select(Person.name, age_group, coolness).to_df()
```

When using `|` outside a `select()`, you must `define()` the result:

```python
res_n, res_v = model.where(Node(n)).select(n, model.where(Value(n, v)).select(v) | 0.0)
define(Result(res_n, res_v))  # Without define(), results will be empty!
```

### Self-Join with `.ref()` — Valid Patterns and Pitfalls

`.ref()` on the same concept IS valid and frequently needed for pairwise/flow constraints. The pattern creates independent entity variables:

```python
# CORRECT: Two independent Edge refs for flow conservation
Ei, Ej = Edge.ref(), Edge.ref()
flow_out = per(Ei.i).sum(Ei.flow)
flow_in = per(Ej.j).sum(Ej.flow)
balance = model.require(flow_in == flow_out).where(Ei.i == Ej.j)
```

**What DOES fail:** Using two refs of the same concept in an aggregation expression that tries to group by one while summing the other without a clear join condition:

```python
# WRONG: Two refs in a single aggregation without proper join
Op1 = Operation.ref()
Op2 = Operation.ref()
model.require(Op1.x_flow <= Op2.capacity).where(Op1.destination == Op2.source)

# WRONG: Undefined concept aliases in aggregation
sum(Op1.x_flow).where(Op1.output_site == Op2.source_site).per(Op2)

# RIGHT: Aggregate to a shared dimension using .where().per()
# Instead of comparing Operation-to-Operation, aggregate through a shared dimension:
Op = Operation.ref()
UD = UnmetDemand.ref()
D = Demand.ref()
inflow_per_sku = sum(Op.x_flow).where(Op.output_sku == UD.sku).per(UD.sku)
demand_per_sku = sum(D.quantity).where(D.sku == UD.sku).per(UD.sku)
problem.satisfy(model.require(inflow_per_sku + UD.x_slack >= demand_per_sku).where(UD))

# RIGHT: For flow conservation at a site, aggregate inflows and outflows separately:
inflow = sum(Op.x_flow).where(Op.output_site == Site).per(Site)
outflow = sum(Op.x_flow).where(Op.source_site == Site).per(Site)
problem.satisfy(model.require(inflow >= outflow).where(Site))
```

**Key rule:** If you need to relate entities of the SAME concept (e.g., flow conservation between operations), restructure the constraint to aggregate through a shared dimension (Site, SKU, Period) instead of self-joining.

**Exception:** `.ref()` with walrus `:=` IS valid for pairwise constraints (see `variable-formulation.md` > Pairwise constraints). The prohibition is on creating standalone aliases meant to represent two separate "roles" of the same concept in aggregation expressions.

### Entity instance comparison

Filter by property values, not by Python object references:

```python
# WRONG: Comparing to a Python object
total = sum(Pipeline.flow).where(Pipeline.source == my_source_obj)

# RIGHT: Filter by concept type + property value
total = sum(Pipeline.flow).where(
    Pipeline.source == WaterSource,
    WaterSource.name == "Reservoir"
)

# RIGHT: Filter by identifying property value
total_flow = sum(Edge.flow).where(Edge.i(1))
```

---

## V1 Semantics API Rules for Formulation

These rules apply when generating constraint expressions and objective expressions for the code generator.

### Expression Format

- **Constraints:** Provide ONLY the constraint condition — the code generator wraps it with `problem.satisfy(model.require(...))`
  - CORRECT: `sum(DecisionConcept.x_quantity) <= Entity.limit`
  - WRONG: `problem.satisfy(model.require(sum(DecisionConcept.x_quantity) <= Entity.limit))`
- **Objectives:** Provide JUST the expression — the code generator wraps it with `problem.minimize(...)` or `problem.maximize(...)`
  - CORRECT: `sum(Entity.cost * DecisionConcept.x_quantity)`
  - WRONG: `problem.minimize(sum(Entity.cost * DecisionConcept.x_quantity))`

### Operator Rules

- Use ASCII operators ONLY: `<=`, `>=`, `==`, `!=`, `*`, `+`, `-`, `/`
- Do NOT use Unicode operators (≤, ≥, ≠, ×, ÷) — they cause parse errors
- No `with model.rule():` or `with solvers.operators():` blocks (that's V0)

### Aggregation Rules

- Use `sum()` for aggregations, or `rai_sum` if `sum` is imported with that alias
- Use `+` to combine multiple `sum()` terms for multi-part objectives
- Aggregation scope must match constraint scope: use `.per(Entity)` on sums when constraining per-entity
- Subset constraints require filters: if the constraint applies to a SUBSET (e.g., "active resources"), the expression MUST filter using `.where()` with a property that identifies that subset

### Decision Variable Rules

- Every constraint must reference at least one decision variable (from `solve_for()`)
- Constraints on pure data properties fail at runtime with `ValueError: Cannot symbolify requirement`
  - WRONG: `Concept.data_property >= 0.01` (no decision variable — runtime error)
  - RIGHT: `sum(DecisionConcept.decision_var) >= TargetConcept.requirement` (references decision variable)

---

## Enums

`model.Enum` creates a concept-backed Python enum. Each member becomes an entity; members are usable in `where()` and `define()` as concept literals.

```python
class Status(model.Enum):
    PENDING = "pending"
    ACTIVE  = "active"
    CLOSED  = "closed"

# Use in filters
where(Order.status == Status.ACTIVE).select(Order.id)

# Define membership
define(Order.is_open()).where(
    model.union(Order.status == Status.PENDING, Order.status == Status.ACTIVE)
)
```

Members resolve to their string/int values when compared with `==`. Use `model.Enum` instead of bare string comparisons when values are a fixed controlled vocabulary.

---

## References and Aliasing

### `Concept.ref()` — self-reference for pairs

When you need two variables of the same concept (e.g., stock pairs, edge pairs, player pairs):

```python
Stock2 = Stock.ref()
# Now Stock and Stock2 iterate independently over Stock instances

Qi = Queen         # Direct alias (no .ref() needed for the "first" variable)
Qj = Queen.ref()   # Second variable
```

**Named refs** prevent variable collision in complex queries with multiple independent aggregation contexts:

```python
# Use separate named refs for each aggregation context
customer_t1 = Customer.ref("customer_t1")
total_1 = aggs.count(customer_t1).where(order.ordered_by(customer_t1))

customer_t2 = Customer.ref("customer_t2")
total_2 = aggs.count(customer_t2).where(order.ordered_by(customer_t2))
# Reusing the same ref variable across independent aggregations causes ValidationError
```

### `Float.ref()` / `Integer.ref()` — value binding

Used to bind multiarity property values for use in expressions:

```python
qty = Float.ref()
total = sum(qty * Food.amount).where(Food.contains(Nutrient, qty)).per(Nutrient)

c = Float.ref()
risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
```

### `.alias("name")` — naming refs for readability

```python
i = Integer.ref().alias("i")
j = Integer.ref().alias("j")
x = Integer.ref().alias("x")
```

### Walrus operator `:=` — inline ref creation in `where()`

```python
model.where(
    Ni := Node.ref(), Nj := Node.ref(),
    Ni.v == Edge.i,
    Nj.v == Edge.j,
).require(Ni.color != Nj.color)
```

### Multi-arity property invocation in `where()` as binder

A property declared with extra arities — e.g.
`Player.assign = model.Property(f"{Player} in {Integer:week} is in {Integer:group}")`
has signature `Player × Integer(week) → Integer(group)` — is invoked by name with refs as
positional arguments. Inside `where(...)`, the invocation **binds** each ref argument to the
relation's tuples; it is not a filter on a specific value.

```python
n_groups, group_size = ..., ...          # problem constants (group count, players per group)
w = Integer.ref().alias("w")
x = Integer.ref().alias("x")
group_val = std.common.range(n_groups)   # data range over group indices

# In an IC, `Player.assign(w, x)` in where() iterates (Player, w, x) tuples of the relation.
# Each iteration carries one (Player, week, group) binding for the body to constrain.
model.where(Player.assign(w, x)).require(
    count(Player, x == group_val).per(w, group_val) == group_size
)
```

Two consequences:

1. **The invocation is a binder, not a filter.** `where(Player.assign(w, x))` does NOT prune
   to a specific `(w, x)`; it iterates the whole relation. Adding `x == 2` as a separate
   condition turns it into a filter. When `x` is a decision-variable value, the binder/filter
   distinction is load-bearing — see
   `rai-prescriptive-problem-formulation/references/csp-formulation.md` § 3a.

2. **It composes naturally with pairwise self-joins.** For ICs over two distinct entities each
   carrying their own decision value, walrus-bind two `Concept.ref()` and two value-refs, then
   invoke the property on each:

   ```python
   w = Integer.ref()  # shared week-dimension ref
   model.where(
       p0 := Player.ref(),
       p1 := Player.ref(),
       p0.p < p1.p,           # data filter (Player.p is data) — symmetry-break half-pair
       x0 := Integer.ref(),
       x1 := Integer.ref(),
       p0.assign(w, x0),      # binds x0 to p0's decision value at week w
       p1.assign(w, x1),      # binds x1 to p1's decision value at week w
   ).require(...)
   ```

For a worked example combining both consequences, see
`rai-prescriptive-problem-formulation/examples/pairwise_no_repeat.py` (adapted from the
classic social golfer benchmark — CSPLib Problem 010).

### Bracket notation for relationships

```python
rel["field"]  # Access a named field of a relationship
```

---

## Undirected-edge expansion via reverse-define

PyRel relationships are directed. Any aggregate, query, or constraint over an *undirected* graph must either expand the edge relation at the Rules level so both orientations are present, or `.ref()`-pair both directions inline. Without one of these, the IC silently matches a single orientation and misses half the symmetric counterparts. Two patterns:

### Pattern 1 — Rules-level expansion (persistent symmetric relation)

Declare a relationship and populate it in **both directions** from a raw directed edge concept. Downstream queries / ICs reference the symmetric relation as a single source.

```python
RawEdge = model.Concept("RawEdge", identify_by={"a": Integer, "b": Integer})
# ... populate RawEdge from data

# Symmetric Edge relation — populated from RawEdge in both orientations
Edge = model.Relationship(f"{Node:a} adjacent to {Node:b}")
Na = Node.ref()
Nb = Node.ref()
model.define(Edge(Na, Nb)).where(Na.id == RawEdge.a, Nb.id == RawEdge.b)
model.define(Edge(Na, Nb)).where(Na.id == RawEdge.b, Nb.id == RawEdge.a)

# Downstream IC matches both orientations automatically
Pa, Pb = Node, Node.ref()
problem.satisfy(model.where(Edge(Pa, Pb), Pa.id < Pb.id).require(Pa.color != Pb.color))
```

The `Na.id < Nb.id` half-pair filter is a symmetry break — without it, each undirected edge is counted twice (as `(a,b)` and `(b,a)`).

### Pattern 2 — Inline `.ref()` pair (no persisted symmetric relation)

For single-IC undirected matching, pair two `Edge.ref()`s inline (or via walrus `:=` inside the `where`) and constrain the reverse direction. Use when the IC is one-off and a persistent symmetric relation is not needed elsewhere.

```python
# Standard assignment form — Ei and Ej must appear bare in the where() to
# anchor each ref to the Edge relation; field references alone don't bind.
Ei, Ej = Edge.ref(), Edge.ref()
problem.satisfy(
    model.where(Ei, Ej, Ej.i == Ei.j, Ej.j == Ei.i).require(...)
)

# Equivalent walrus form (operator-position only — walrus is valid inside an
# expression, not at module scope). The walrus expression itself anchors the ref.
problem.satisfy(
    model.where(Ei := Edge.ref(), Ej := Edge.ref(), Ej.i == Ei.j, Ej.j == Ei.i).require(...)
)
```

For a concrete worked example using Pattern 1, see `rai-prescriptive-problem-formulation/examples/chromatic_number.py`.

---

### Chain.ref() and .alt()

**`Chain.ref()`** — creates an independent occurrence of a chain path. Use when the same multi-hop path must appear twice in a query as two independent traversals (e.g., comparing two different values on the same relationship). Distinct from `Concept.ref()` (which creates a new entity variable):

```python
# Two independent traversals of the same relationship path
route_a = Order.ship_via.ref()   # Chain.ref() — same path, independent occurrence
route_b = Order.ship_via         # original
where(route_a.cost < route_b.cost).select(...)
```

**`.alt()`** — creates an inverse traversal from an existing Property without a separate `define()`:

```python
# Forward: Order -> Customer (from FK)
Order.ordered_by = model.Relationship(f"{Order} ordered by {Customer}")

# Inverse: Customer -> Orders (automatic from .alt())
Customer.orders = Order.ordered_by.alt(f"{Customer} has orders {Order}")
```

---
