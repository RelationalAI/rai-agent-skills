<!-- TOC -->
- [Constraint Principles](#constraint-principles)
  - [Constraint type classification](#constraint-type-classification)
  - [Two constraint styles](#two-constraint-styles)
  - [Forcing constraints](#forcing-constraints)
  - [Self-defeating constraints](#self-defeating-constraints)
- [Constraint Modeling Patterns](#constraint-modeling-patterns)
  - [Balance constraints](#balance-constraints)
  - [Concept-variable matching in constraints](#concept-variable-matching-in-constraints)
  - [Declaring constraint keys for post-solve readback](#declaring-constraint-keys-for-post-solve-readback)
  - [Capacity limits and binary activation (big-M)](#capacity-limits-and-binary-activation-big-m)
  - [Historical comparison / tolerance band constraints](#historical-comparison--tolerance-band-constraints)
  - [Proportional / fair-share constraints](#proportional--fair-share-constraints)
- [Constraint Join Patterns](#constraint-join-patterns)
  - [Constraint pattern examples (DO / DON'T)](#constraint-pattern-examples-do--dont)
- [Constraint Selection Guidance](#constraint-selection-guidance)
  - [Constraint interaction check (avoid conflicts)](#constraint-interaction-check-avoid-conflicts)
- [Parameter Derivation from Data](#parameter-derivation-from-data)
  - [Value extraction priority](#value-extraction-priority)
<!-- /TOC -->

## Constraint Principles

### RAI Expression Restrictions

Python boolean keywords (`and`, `or`, `not`, `if/else`) are invalid inside RAI expressions — use the operator overloads (`&`, `|`, `model.not_()`) and `.where()` scoping. This rule applies to all PyRel expressions, not just constraints. For the full table and `|` vs `model.union()` semantics, see `rai-pyrel` > Expressions > Boolean logic.

### Constraint type classification

Classify each constraint using one of these types:

| Type | Use When | Business meaning | Examples |
|------|----------|-----------------|----------|
| **forcing** | Requires positive activity (demand satisfaction, coverage). Essential for minimize objectives — without it, solver returns zeros. | Every customer order must be fulfilled; every shift must be covered | `sum(Decision.qty) >= demand`, `sum(Assignment.assigned) == 1` |
| **capacity** | Limits maximum values (resource limits, budgets, physical constraints) | Don't exceed warehouse storage, budget ceiling, or machine hours | `sum(Decision.usage) <= capacity`, `qty <= max_available` |
| **balance** | Enforces conservation/flow balance at nodes or over time | What enters a warehouse must leave or be stored | `inflow == outflow`, `start + produced - consumed == end` |
| **linking** | Connects multiple variables or enforces conditional relationships | Only ship through a facility if it is open | `qty <= M * is_active`, `var_A == f(var_B)` |
| **logical** | Cardinality constraints, either/or, at-most-one | Each task assigned to exactly one worker; select at most 3 suppliers | `sum(Assignment.binary) == 1`, `sum(Supplier.selected) <= K` |

### Two constraint styles

**Style 1: `model.where(scope).require(conditions)`** -- Define scope first, then state requirements.

```python
# Pairwise: for each queen pair where row_i < row_j, columns must differ
model.where(Qi.row < Qj.row).require(
    Qi.column != Qj.column,
    std.math.abs(Qi.column - Qj.column) != Qj.row - Qi.row,
)

# Adjacent nodes must have different colors
model.where(
    Ni := Node.ref(), Nj := Node.ref(),
    Ni.v == Edge.i, Nj.v == Edge.j, Ni.v < Nj.v
).require(Ni.color != Nj.color)
```

**Style 2: `model.require(conditions).where(scope)`** -- State requirements first, then restrict scope.

```python
# Fix initial inventory where time matches start
model.require(x_inv == ResourceGroup.inv_start).where(
    ResourceGroup.inv(ResourceGroup.inv_start_t, x_inv)
)

# Capacity constraint for a specific mode
model.require(x_weight <= fast_cap * y_bin_fast).where(
    Mode.name("fast"), Mode.weight(t, x_weight), bin_fast(t, y_bin_fast),
)
```

**When to use which:** Style 1 reads naturally when the scope defines entity relationships (pairwise, adjacency). Style 2 reads naturally when the requirement is the primary statement and scope is a filter.

### Forcing constraints

#### For minimize objectives

When the objective is to MINIMIZE with non-negative cost coefficients and no forcing constraints, the solver may achieve cost=0 by setting all decision variables to zero. This is the most common trivial-solution trap.

**However, all-zeros is NOT always optimal for minimize problems.** If the objective has negative coefficients (e.g., minimize `-x` is effectively maximize `x`), the solver pushes variables to their upper bounds, not zero. Similarly, if equality constraints or lower-bound requirements force positive values, zero is infeasible. The zero test below catches the common case but is not universal.

**The zero test (for non-negative cost coefficients):** "If the solver sets everything to 0, would all constraints be satisfied?" If YES, add a forcing constraint.

**How to identify the right one:** What must happen in the real world?
- Demands/requirements must be satisfied → `sum(Decision.x_quantity).per(Target) >= Target.required`
- Tasks/orders must be assigned → `sum(Assignment.is_assigned).per(Item) == 1`
- Resources must flow through the system → flow conservation at nodes
- Weights/allocations must total a fixed amount → `sum(Decision.x_weight) == 1`

**Choose the right aggregation level for forcing constraints.** When the model has cross-product concepts (e.g., ItemPeriod = Item × Period), match the forcing constraint scope to the business requirement:

| Business requirement | Forcing constraint scope | Example |
|---------------------|------------------------|---------|
| Each item served **at least once** across the horizon | Aggregate cross-product to base concept | `sum(ItemPeriod.x_active).per(Item) >= 1` |
| Each item served **every period** | Per cross-product entity | `ItemPeriod.x_active >= 1` (or use slack) |
| At least N items served **per period** | Aggregate cross-product to period | `sum(ItemPeriod.x_active).per(Period) >= N` |

Common mistake: applying a per-cross-product forcing constraint (every item in every period) when the business only requires per-base-concept (each item at least once). This over-constrains the problem, makes capacity constraints non-binding, and produces unrealistic "do everything everywhere" solutions.

**Ask:** "Does the requirement apply once per [base entity], or once per [base entity × period/resource]?" The answer determines the `.per()` scope.

#### For maximize objectives

When the objective is to MAXIMIZE (profit, revenue, value) with positive coefficients, the optimizer naturally drives variables up — trivial all-zero solutions are not a risk. However, maximize problems still need:
- **Capacity/resource constraints** to bound the solution
- **Demand satisfaction constraints** to ensure balanced fulfillment — without these, the optimizer concentrates all resources on the highest-margin items, starving lower-margin ones even when shared resources connect them

#### Code patterns (demand satisfaction, assignment completeness)

```python
# Each shift must have minimum coverage
problem.satisfy(model.where(Worker.x_assign(Shift, x)).require(
    sum(Worker, x).per(Shift) >= min_coverage
))

# Degree constraints: exactly one in-edge and one out-edge per node
node_flow = sum(Edge.x).per(Node)
problem.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))
```

### One-hot selection (exactly-one-of-N)

When choosing exactly one option from a discrete set per entity (e.g., one discount level per product-week), use binary variables with a sum-to-one constraint:

```python
# Binary: Product x Week x Discount selection
problem.solve_for(Product.x_select(w, d, x), type="bin")

# Exactly one discount per (Product, Week)
problem.satisfy(model.where(Product.x_select(w, d, x)).require(
    sum(d, x).per(Product, w) == 1
))
```

The `sum(d, x)` aggregates over the Discount dimension only; `.per(Product, w)` groups by the remaining dimensions. This is the standard one-hot encoding for discrete choice. See `../examples/one_hot_temporal_recurrence.py`.

Together the leading args and `.per()` keys must identify every term: without them PyRel counts equal values of `x` once, so a grand total is `sum(Product, w, d, x)`, not `sum(x)`. Full rule: [known-limitations.md](known-limitations.md) § Decision-variable aggregate agreement.

### Temporal recurrence (running totals / inventory balance)

For state that accumulates over time, use separate constraints for the base case and the recurrence:

```python
# Base case: first period
problem.satisfy(model.where(w.num == 1, Product.x_cuml(w, z), Product.x_sales(w, d, y)).require(
    z == sum(d, y).per(Product, w)))

# Recurrence: subsequent periods
problem.satisfy(model.where(
    w.num > 1, w_prev.num == w.num - 1,
    Product.x_cuml(w, z), Product.x_cuml(w_prev, z_prev),
    Product.x_sales(w, d, y),
).require(z == z_prev + sum(d, y).per(Product, w)))
```

The `w_prev.num == w.num - 1` join creates a two-period self-join on the time concept. This is the canonical pattern for inventory-style accumulation. See `../examples/one_hot_temporal_recurrence.py`.

### Monotone ordering (price ladder / non-decreasing sequence)

To enforce that a selected option cannot decrease over consecutive periods, use mutual exclusion between lower values in the next period:

```python
problem.satisfy(model.where(
    Product.x_select(w, d, x), Product.x_select(w2, d2, x2),
    w2.num == w.num + 1, d2.level < d.level,
).require(x + x2 <= 1))
```

This says: if discount `d` is selected in week `w`, then no strictly lower discount `d2` can be selected in week `w+1`. See `../examples/one_hot_temporal_recurrence.py`.

### Self-defeating constraints

Self-defeating constraints force decision variables to zero universally, making the problem trivially solvable but meaningless. The solver will happily satisfy them by doing nothing.

**Never do these (blocks all activity):**
- `require(Decision.x_quantity == 0)` — forces ALL quantities to zero
- `require(Decision.x_quantity <= 0)` without `.where()` — same effect
- Constraints named "No X" or "Block X" containing `== 0`
- Upper bounds set to 0

**Make zero-forcing conditional with `.where()`:**
```python
# WRONG (self-defeating - blocks ALL production):
problem.satisfy(model.require(SiteProduction.x_quantity == 0))

# CORRECT (conditional - only zero where no BOM exists):
problem.satisfy(model.require(SiteProduction.x_quantity == 0).where(~SiteProduction.site.has_bom))

# CORRECT (upper bound, not forcing to zero):
problem.satisfy(model.require(SiteProduction.x_quantity <= SiteProduction.capacity))
```

Conditional zero-forcing is also how to rule out combinations the data makes impossible — `qty == 0` where `transit_days > due_day` (delivery can't arrive in time), `assigned == 0` where `worker.skill != task.required_skill`, `flow == 0` where `distance > max_range`. Ask which combinations of decision variables the data rules out: these are feasibility filters, not optimization trade-offs, so always include them.

**Never nest `require()` calls:**
```python
# WRONG:
problem.satisfy(model.require(model.require(x == 0).where(...)))

# CORRECT:
problem.satisfy(model.require(x == 0).where(...))
```

---

## Constraint Modeling Patterns

### Balance constraints

```python
# Flow conservation: inflow == outflow at interior nodes
Ei, Ej = Edge.ref(), Edge.ref()
flow_out = per(Ei.i).sum(Ei.flow)
flow_in = per(Ej.j).sum(Ej.flow)
balance = model.require(flow_in == flow_out).where(Ei.i == Ej.j)
```

For inventory balance (linking consecutive time steps), see Temporal recurrence above.

### Concept-variable matching in constraints

Decision variables must be referenced on the concept where they were defined. `BaseConcept.x_assigned` creates a new, empty `x_assigned` relationship on `BaseConcept` instead of reaching the solver variable, so a constraint whose only variable reference is on the wrong concept raises `ValueError: Expression does not reference any decision variables` at `satisfy()`.

**Rule:** If a variable is defined as `ConceptA.x_quantity`, constraints must use `ConceptA.x_quantity` — not `ConceptB.x_quantity`, even if ConceptB is related.

```python
# Variable defined on DecisionConcept:
DecisionConcept.x_assigned = Property(...)
problem.solve_for(DecisionConcept.x_assigned, ...)

# WRONG - references x_assigned on wrong concept:
problem.satisfy(model.require(sum(BaseConcept.x_assigned) >= 1))

# RIGHT - references x_assigned on defining concept:
problem.satisfy(model.require(sum(DecisionConcept.x_assigned).per(BaseConcept) >= 1))
```

**To link to base model entities**, navigate via relationships defined on the decision concept (e.g., `DecisionConcept.entity_a`, `DecisionConcept.entity_b`), not by referencing the variable on the base concept.

### Declaring constraint keys for post-solve readback

A **constraint family** is one logical constraint instantiated per entity — a capacity limit per Resource, a coverage floor per Shift, a nutrient bound per Nutrient. Declaring the family's grounding key(s) at formulation time — `keyed_by=` on `satisfy()` — determines whether you can read each instance's post-solve marginal (`shadow_price`) or conflict membership (`in_conflict`) back **paired with the entity it grounds**.

This is what keeps a solved model's output *ontology-native*: declare the key, and each marginal or conflict flag reads back as `cap.resource.capacity` — attached to the entity it describes and queryable like any other property, ready to join, filter, and present in your domain's own terms.

Each `keyed_by` entry becomes an **identifying back-pointer Property** on the returned `ProblemConstraint`, named by the dict key you choose — `keyed_by={"resource": Resource}` reads back as `cap.resource`. The instance is identified by its key tuple, and the back-pointer joins a marginal or IIS flag to entity data by key (`cap.resource.capacity`) instead of parsing a constraint name string. A *variable's* back-pointer (`var.food`) is derived automatically from its Property's format-string fields; a *constraint's* must be **declared** — there is no automatic constraint back-pointer.

```python
# Declare the family's grounding key so each instance reads back by entity:
cap = problem.satisfy(
    model.require(usage <= Resource.capacity),
    name=["cap", Resource.name],        # readable display label only
    keyed_by={"resource": Resource},    # identifying key -> cap.resource back-pointer
)
# Post-solve, marginals and IIS flags read back joined by this key (cap.resource.name,
# cap.shadow_price) — readback patterns live in rai-prescriptive-results.
```

Rules of the declaration:

- **The keys must uniquely determine the constraint instance** (1:1). A key set that doesn't — a family wider than its key, or two conjuncts of a single `require(A, B)` sharing the same keys — forces two constraint expressions onto one identity and **raises at solve** (an `FDError`: the relationship violates functional dependency guarantees). Add the missing key, or split a multi-conjunct `require` into one `satisfy` per conjunct.
- **A constraint grounded over several entities takes several keys** — `keyed_by={"worker": Worker, "shift": Shift}` — and exposes one back-pointer per key.
- **A key need not be an entity.** A value reference such as an identifier — `keyed_by={"i": X.i}` — keys by that scalar (`con.i`), the natural form when the grounding domain is a bare index with no richer entity to join to. A bare primitive type (`Integer`) is rejected — it carries no per-instance value.
- **Key names** must be valid identifiers and must not clash with the constraint's managed properties, compared case-insensitively: `basis_status`, `display_string`, `id`, `in_conflict`, `name`, `root`, `shadow_price`, `type`. The raised `ValueError` lists the full set, so read that rather than this line if they diverge.
- **Omit `keyed_by`** for constraints you never read back by key — they are still valid solver constraints.

`name=` plays no part in identifying instances or naming the back-pointer, but it is not cosmetic: it keeps `problem.display()` rows readable (`name=["cap", Entity.id]`), and from `relationalai>=1.29` it is what `aggs.limit` caps a `display_string` read on: an unnamed constraint drops out of a capped read entirely while still appearing in the uncapped one. A `keyed_by` back-pointer stays available as a `where` filter on the same read.

This is the formulation-time bridge for the post-solve readback patterns in `rai-prescriptive-results` (Sensitivity & conflict attributes, plus its sensitivity-analysis.md and conflict-analysis.md references).

### Capacity limits and binary activation (big-M)

```python
# Total resource usage <= factory availability
problem.satisfy(model.require(
    sum(Product.quantity / Product.rate) <= Factory.avail
).where(this_product, Factory.name(factory_name)))

# Fast-mode weight <= capacity (big-M with binary activation)
problem.satisfy(model.require(x_weight <= fast_cap * y_bin_fast).where(
    Mode.name("fast"), Mode.weight(t, x_weight), bin_fast(t, y_bin_fast),
))

# Ship all-or-nothing: quantity = capacity * binary
problem.satisfy(model.require(x_qty_mode == ResourceGroup.inv_start * y_bin_mode).where(
    Mode.qty_mode(ResourceGroup, t, x_qty_mode),
    Mode.bin_mode(ResourceGroup, t, y_bin_mode),
))
```

---

## Unwired Relationships (Detailed)

A declared `model.Relationship()` without a corresponding `model.define()` rule has NO DATA at solve time. The relationship exists in the schema but has zero bindings.

**Symptoms:**
- No constraint rows are generated — joins on the unwired relationship match zero entities, and under PyRel relational semantics a body with no tuples produces no row.
- `.per(Concept)` aggregations return nothing.
- The solver returns OPTIMAL with a vacuous objective (typically zero on minimize), masking the absent constraint.

**Check:** For every relationship in a constraint `.where()` clause, verify a `model.define()` rule populates it. If no define rule exists, the relationship is unwired — do not use it in constraints.

**Example:**
```python
# WRONG: constraint uses unwired relationship (no define() rule)
sum(Operation.x_flow).where(Operation.transformation == Site).per(Site) >= Site.demand

# CORRECT: use a relationship with define() data binding, or join via shared identity properties
sum(Operation.x_flow).where(Operation.output_sku == UnmetDemand.sku).per(UnmetDemand.sku)
```

### Historical comparison / tolerance band constraints

Constrain current decisions to stay within a percentage band of historical values. Always paired (upper AND lower), and both sides must use the same `.per()` dimensions.

```python
# Current allocation must stay within +/- tolerance of historical
model.require(
    sum(Allocation.x_spend).per(Channel) <= (1 + tolerance) * Channel.historical_spend,
    sum(Allocation.x_spend).per(Channel) >= (1 - tolerance) * Channel.historical_spend,
)
```

Both current and historical expressions must join to the same grouping concepts in `.where()` when the comparison spans multi-key groups:

```python
model.where(
    Allocation.campaign(Campaign), Allocation.channel(Channel)
).require(
    sum(Allocation.x_spend).per(Channel, Campaign) <= (1 + tol) * HistoricalSpend.amount
)
```

### Proportional / fair-share constraints

Ensure sub-groups receive at least a minimum share of the group total. Compares aggregations at different granularity levels using nested `.per()`.

```python
# Each campaign gets at least min_pct of its country's total spend
model.require(
    sum(Allocation.x_spend).per(Country, Campaign) >= min_pct * sum(Allocation.x_spend).per(Country)
).where(Allocation.country(Country), Allocation.campaign(Campaign))
```

This ensures balanced allocation across sub-groups rather than concentrating resources on the highest-return sub-group.

---

## Constraint Join Patterns

**DIRECT joins** — concepts linked by a relationship:
```python
# A.rel -> B (direct link): aggregate A's variable per B, compare to B's threshold
problem.satisfy(model.require(
    sum(A.x_var).where(A.rel(B)).per(B) >= B.threshold
))
```

**SHARED DIMENSION joins** — concepts share a common target but aren't directly linked:
Create an aggregation concept keyed by the shared dimension, then aggregate separately:
```python
# Define junction keyed by shared dimension
model.define(AggConcept.new(dim_key=B.dim_link))

# Aggregate each side per the shared dimension
supply = sum(A.x_var).where(A.dim_link(AggConcept.dim_key)).per(AggConcept)
demand = sum(B.quantity).where(B.dim_link(AggConcept.dim_key)).per(AggConcept)
problem.satisfy(model.require(supply + AggConcept.x_slack >= demand))
```

**LINKING TWO CROSS-PRODUCT CONCEPTS through shared dimensions:**

When two cross-product concepts share dimensions (e.g., `TechnicianMachinePeriod` and `MachinePeriod` both have machine and period), join them on the shared dimensions inside the aggregate's `.where()` and group with `.per(GroupingConcept)`:

```python
sum(TMP.x_assigned).where(TMP.machine == MP.machine, TMP.period == MP.period).per(MP) <= MP.cap
```

Bare references unify within the require chain — no `.ref()` aliasing is needed for this pattern. For when `.ref()` is and isn't required, see `rai-pyrel` § Free-Variable Scoping.

**COMPLETE EXAMPLE: Demand satisfaction with slack via shared dimension**

This is the canonical pattern for network flow and supply chain problems where supply and demand connect through a shared dimension (SKU, region, product type):

```python
# 1. Variables: flow on edge concept + slack on aggregation dimension
Operation.x_flow = model.Property(f"{Operation} has {Float:flow}")
problem.solve_for(Operation.x_flow, lower=0, upper=Operation.capacity_per_day,
            name=["flow", Operation.id])

UnmetDemand = model.Concept("UnmetDemand")
UnmetDemand.sku = model.Property(f"{UnmetDemand} for {SKU:sku}")
UnmetDemand.x_slack = model.Property(f"{UnmetDemand} of {Float:slack}")
model.define(UnmetDemand.new(sku=Demand.sku))  # One per unique demanded SKU
problem.solve_for(UnmetDemand.x_slack, lower=0, name=["unmet", UnmetDemand.sku.id])

# 2. Constraint: supply + slack >= demand, per shared dimension
inflow_per_sku = sum(Operation.x_flow).where(Operation.output_sku == UnmetDemand.sku).per(UnmetDemand.sku)
demand_per_sku = sum(Demand.quantity).where(Demand.sku == UnmetDemand.sku).per(UnmetDemand.sku)
problem.satisfy(model.require(inflow_per_sku + UnmetDemand.x_slack >= demand_per_sku))

# 3. Objective: minimize cost + penalty for unmet demand
PENALTY = 1000.0
problem.minimize((sum(Operation.x_flow * Operation.cost_per_unit) | 0.0)
                 + PENALTY * (sum(UnmetDemand.x_slack) | 0.0))
```

**Why this works:** Both sides aggregate `.per(UD.sku)` — the shared dimension. The slack variable ensures feasibility when supply < demand. The penalty in the objective drives the solver to satisfy demand when possible.

### Cross-Concept Join Rules

These rules cover patterns that frequently cause code generation issues — engine errors, empty results, or unintended cross products.

**Rule 1: Prefer the shared dimension Concept on the RHS in `.where()` joins**
```python
# Common pattern: Group flow by the shared dimension concept directly
sum(Operation.x_flow).where(
    Operation.destination_site(Site),                   # RHS is concept Site
    Operation.output_sku(SKU)                            # RHS is concept SKU
).per(Site)

# Alternative: traversing through an extended concept (SiteProduction has .site, .sku)
# also resolves, but routes the join through SiteProduction's cross-product —
# easy to introduce unintended row blow-up. Prefer the dimension concepts when
# they carry enough identity for the grouping you want.
sum(Operation.x_flow).where(
    Operation.destination_site(SiteProduction.site),
    Operation.output_sku(SiteProduction.sku)
).per(SiteProduction)
```

**Rule 2: Multi-hop chains in `.where()` are valid**
```python
# Both forms resolve correctly when the chain is populated:
sum(X.x_var).where(X.rel(Y.other_rel.nested_prop))  # OK: relation arg with 2-hop chain
sum(X.x_var).where(X.rel == Y.other_rel.nested_prop)  # OK: equality with 2-hop chain
```

If a chained `.where()` returns empty results, the cause is usually the chain itself being unpopulated (an FK Property declared but never filled by `model.define(...)`), not the chaining mechanic. Pre-materializing as an enrichment property is an ergonomic/reuse choice, not a correctness requirement.

**Rule 3: Avoid cross-product entity concepts in `.where()` joins**
When using extended concepts (e.g., SiteProduction with `.site` and `.sku` relationships):
- Do NOT compare their relationships with other concepts' relationships
- Instead, group by the underlying dimension concepts directly (Site, SKU)
- If you need the cross-product entity, aggregate each side separately per the shared dimension

**Rule 4: Valid RHS types in `.where()` equality**
The RHS of a `.where()` equality may be:
- A **Concept type**: `.where(A.rel(ConceptName))` — groups by that concept
- A **property reference**: `.where(A.prop(B.prop))` — matches on shared values; multi-hop chains (`B.rel.nested_prop`) are also valid when populated
- A **literal value**: `.where(A.prop("value"))` or `.where(A.prop(42))`

Avoid: nested `.where()` calls.

**Rule 5: `.per()` on extended concepts — group via the extended concept's relationship, not the base concept**

When grouping a sum on an extended (cross-product) concept by one of its base concepts, use `.per(AB.a)` (the relationship through the extended concept), not `.per(A)` (the bare base concept):

```python
# Setup: AB is a cross-product of A x B
# defined as: model.define(AB.new(a=A, b=B))

# WRONG: .per(A) — solver returns OPTIMAL but constraints are silently mis-scoped.
# The inner sum does NOT filter to AB rows where AB.a == A; it sums all AB
# globally and replicates that constraint once per A entity.
model.require(sum(AB.x_active).per(A) == 1)
# Generates: sum(all_AB) == 1, sum(all_AB) == 1   (one per A — wrong)

# CORRECT: .per(AB.a) — generates one constraint per A with the correctly
# filtered sum.
model.require(sum(AB.x_active).per(AB.a) == 1)
# Generates: sum(AB where a==A1) == 1, sum(AB where a==A2) == 1   (right)
```

The failure is silent — solver returns OPTIMAL with the wrong feasibility region. Verify with `problem.display()` that per-group constraints have the expected disaggregated sums.

Per-group constraints also produce no row for entities whose bound property is unpopulated (a related but distinct mode — the `.per()` scope is correct, the *data* is sparse, so under PyRel relational semantics the body grounds only where the bound has tuples). Check grounding counts before solving: [pre-solve-validation.md](pre-solve-validation.md) > Cardinality checks.

**Rule 6: Access data properties on extended concepts via relationship traversal**
Extended/cross-product concepts only have their own declared properties (relationships + decision variables). To access data properties from the base concept they reference, traverse the relationship.
```python
# Setup: AB is an extended concept with relationship to B
# AB.b -> B (relationship), AB.x_var (decision variable)
# B.quantity, B.category (data properties on the base concept)

# WRONG: quantity is on B, not AB
AB.quantity  # Property does not exist

# CORRECT: traverse via the relationship
AB.b.quantity  # Accesses B.quantity through the relationship

# WRONG: category is on B, not AB
sum(...).where(AB.category == ...)

# CORRECT: traverse via the relationship
sum(...).where(AB.b.category == ...)
```

### Constraint pattern examples (DO / DON'T)

**Forcing constraint (requires positive activity):**
Business description: "Ensure every target receives at least its required amount."
```
GOOD: sum(Decision.x_var).where(Decision.target == Target).per(Target) >= Target.requirement
Why:  Aggregates per target entity using .per(), references existing requirement property.

BAD:  Decision.x_var >= Target.requirement
Why:  Missing aggregation. Compares each individual decision to the full requirement.
      Use sum(...).per(Target) to aggregate all decisions serving each target first.
```

**Capacity constraint (limits shared resources):**
Business description: "Total usage at each resource must not exceed its available capacity."
```
GOOD: sum(Decision.x_var).where(Decision.resource == Resource).per(Resource) <= Resource.limit
Why:  Aggregates total usage per resource, then bounds by that resource's limit property.

BAD:  Decision.x_var <= Resource.limit
Why:  Missing aggregation. Each individual decision bounded by the full resource limit,
      allowing total usage to far exceed the limit.
```

---

## Constraint Selection Guidance

### Constraint interaction check (avoid conflicts)
Before finalizing selection, verify the selected constraints work together:

5. **Refinement replaces simpler version**:
   When two constraints address the same business logic but one includes a data-driven factor (loss_rate, yield, efficiency):
   - KEEP the refined version (with the transformation factor)
   - DROP the simpler version (it's a special case where the factor = 1)
   - Example: "sum(Flow.x * (1 - Flow.loss_rate)) >= demand" replaces "sum(Flow.x) >= demand"

### Slack variable and soft constraint patterns

6. **Slack variable triads**: For each variable in a minimize objective, trace its constraint linkage:
   - If a variable appears in the objective AND in at least one constraint (== or >=), it is properly linked.
   - If a variable appears in the objective but in NO constraint, the solver sets it to its lower bound (trivial zero).
   - Under minimization, `slack >= rhs` is equivalent to `slack == rhs` at optimality (solver drives slack to minimum), so `>=` is valid here — no need to require syntactic `==`.

7. **Coverage + slack + penalty patterns**: A common valid pattern is:
   - `sum(Assignment.x_assigned) + x_unmet >= 1` (coverage with slack)
   - `minimize(... + M * x_unmet)` (penalty drives slack to zero when possible)
   This is correct — the slack absorbs infeasibility. When slack is present on the LHS, `>= 1` is a coverage-with-fallback pattern, not a hard per-entity minimum.

8. **Hard per-entity minimums**: `sum(Decision.x).per(entity) >= N` WITHOUT a slack variable on the LHS imposes a hard minimum of N per entity. If N * (number of entities) exceeds total capacity, the problem is INFEASIBLE. Flag as WARNING with the arithmetic.

---

## Parameter Derivation from Data

**Embed parameter values DIRECTLY in constraint expressions, not as separate inputs.**

Instead of: `sum(Allocation.x) <= total_budget` with user_input_needed
Use: `sum(Allocation.x) <= 2000000` (with the actual value in the expression AND in parameters for editing)

### Value extraction priority

**Step 1: Use existing model properties via relationship traversals (always check first)**

Before hardcoding ANY numeric value, check whether the data already exists in the model on a related concept reachable by relationship traversal.

- If a property exists on a related concept and is reachable via a relationship traversal, use the traversal in the expression. Hardcoding a default value means the constraint won't reflect actual data and will silently produce wrong results.
- Only use hardcoded parameters when no matching data property exists anywhere in the model.

**Step 2: Check user input**
1. Check user requirements for specific values they mentioned — these override data-derived defaults
