<!-- TOC -->
- [Constraint Context Integration](#constraint-context-integration)
- [Constraint Principles](#constraint-principles)
  - [Constraint categories](#constraint-categories)
  - [Constraint type classification](#constraint-type-classification)
  - [Two constraint styles](#two-constraint-styles)
  - [Tightness and contradictions](#tightness-and-contradictions)
  - [Forcing constraints](#forcing-constraints)
  - [Demand modeling: context determines direction](#demand-modeling-context-determines-direction)
  - [Self-defeating constraints](#self-defeating-constraints)
- [Constraint Modeling Patterns](#constraint-modeling-patterns)
  - [Balance constraints](#balance-constraints)
  - [Concept-variable matching in constraints](#concept-variable-matching-in-constraints)
  - [Capacity limits and binary activation (big-M)](#capacity-limits-and-binary-activation-big-m)
  - [Historical comparison / tolerance band constraints](#historical-comparison--tolerance-band-constraints)
  - [Proportional / fair-share constraints](#proportional--fair-share-constraints)
- [Constraint Join Patterns](#constraint-join-patterns)
  - [Constraint pattern examples (DO / DON'T)](#constraint-pattern-examples-do--dont)
  - [Addressing user requirements](#addressing-user-requirements)
- [Constraint Verification](#constraint-verification)
  - [Pre-generation verification](#pre-generation-verification)
  - [Self-check: constraints](#self-check-constraints)
- [Constraint Selection Guidance](#constraint-selection-guidance)
  - [Completeness checklist](#completeness-checklist)
  - [Constraint interaction check (avoid conflicts)](#constraint-interaction-check-avoid-conflicts)
- [Parameter Derivation from Data](#parameter-derivation-from-data)
  - [Value extraction priority](#value-extraction-priority)
<!-- /TOC -->

## Constraint Context Integration

**Natural language rule:** When describing constraints to the user (in `description`, `rationale`, and suggestion text), use business language, not property names. Translate technical references into domain-natural phrases:
- "Ensure total shipments to each customer meet their demand" (not "sum(Operation.x_flow).per(Demand.sku) >= Demand.quantity")
- "Don't exceed the daily processing capacity at any facility" (not "Operation.x_flow <= Operation.capacity_per_day")
- "Each worker can be assigned to at most 5 shifts per week" (not "sum(Assignment.x_assigned).per(Worker) <= 5")

**Your suggestions should be inspired by BOTH the base model structure AND any user inputs.**

**1. Start with the Base Model:**
- Examine what natural limits/rules the model implies (capacities, demands, flow balances)
- Identify properties that represent limits (capacity, budget, min_quantity, max_quantity)
- Consider typical constraints for this type of optimization problem

**2. Layer in User Goals (if provided):**
If the user provided constraints goals (look for USER'S REQUIREMENTS AND LIMITS section):
- Parse their input to identify specific limits, rules, or requirements
- Extract specific values they mentioned (e.g., "budget is $10K", "must serve 80%")
- Align your constraints with both model structure AND user's stated requirements

**3. Check for Data-Driven Incompatibilities:**
When entity attributes create combinations that are infeasible by data (not by optimization), add conditional zero-forcing constraints. These reduce the feasible space to only valid combinations:
- Time incompatibility: `qty == 0 where transit_days > due_day` (delivery can't arrive in time)
- Skill mismatch: `assigned == 0 where worker.skill != task.required_skill`
- Range exceeded: `flow == 0 where distance > max_range`

Ask: "Which combinations of decision variables are impossible given the data properties?" These are not optimization trade-offs — they are feasibility filters that should always be included.

**4. Decision Criteria (when user hasn't specified constraints):**
- If user mentions limits that match model properties -- use those properties directly
- If user needs constraints not supported by model -- note what extension would be needed
- If no user input provided, derive constraints from the model structure:
  - If model has capacity/limit properties -- add capacity constraints
  - If model has demand/requirement properties -- add demand satisfaction (forcing) constraints
  - If model has network structure (source/destination relationships) -- add flow conservation/balance constraints
  - If multiple decision concepts share a base entity -- consider linking/conservation constraints (flag if missing, but not always required)
  - If objective minimizes cost/time/risk -- ensure at least one forcing constraint exists (see Forcing Constraints for Minimize Objectives)
  - If continuous variables have no explicit upper bounds -- add capacity constraints from data

**5. Check for Temporal Context:**
If the problem specifies a time scope or granularity, and concepts have date columns:
- Add `.where()` filters on date columns to scope constraints to the relevant time window
- If granularity is specified ("weekly", "monthly"), use aggregation in constraints
- Surface time boundaries as editable parameters so users can adjust the planning horizon
- For large event tables (>1000 entities) without explicit time scope, suggest a reasonable default time window

## Constraint Discovery Patterns

After identifying variables, use these prompts to systematically discover missing constraints. Each question targets a specific constraint category.

**Boundary probes (apply to every formulation):**
- "What prevents setting all variables to zero?" → Surfaces forcing/demand constraints. If the answer is "nothing," you need a forcing constraint or the objective direction is wrong.
- "What prevents setting all variables to their maximum?" → Surfaces capacity/budget constraints. If the answer is "nothing" for a minimization problem, the formulation is likely correct. If for maximization, you need upper bounds.

**Iterative discovery (after adding first constraints):**
- "Are there other limits on [concept]?" → Surfaces additional capacity constraints on the same entity (e.g., both weight and volume limits on a truck).
- "What happens if we violate this limit?" → Distinguishes hard constraints (infeasible/illegal) from soft goals (penalize in objective). If the answer is "it's bad but not impossible," consider moving to objective.

**Objective-driven probes:**
- For **minimize** objectives: "What capacity, budget, or resource limits apply?" → Without these, the solver sets everything to zero (trivial).
- For **maximize** objectives: "What demand, coverage, or throughput requirements exist?" → Without these, the solver may over-allocate.

**Structural probes:**
- "Can the same [resource] be assigned to multiple [tasks] simultaneously?" → Surfaces mutual exclusivity or capacity constraints.
- "Does [entity] have a natural ordering or precedence?" → Surfaces sequencing/precedence constraints.
- "Are there combinations that are physically or logically impossible?" → Surfaces infeasibility filters (`.where()` conditions).

**Multi-concept probes (when variables span 2+ decision concepts):**
- "How does [detail concept] aggregate to [summary concept]?" → Surfaces aggregation/linking constraints (e.g., sum of assignment hours == total hours).
- "Which pairs of decision concepts share a dimension but have no constraint connecting them?" → Surfaces missing linking constraints. Every shared-dimension pair needs at least one link.
- "Does the objective reach all decision concept groups, directly or via linking constraints?" → Surfaces disconnected variable groups that the solver can set to arbitrary values.

---

## Constraint Principles

### RAI Expression Restrictions

Python boolean keywords (`and`, `or`, `not`, `if/else`) are invalid inside RAI expressions — use the operator overloads (`&`, `|`, `model.not_()`) and `.where()` scoping. This rule applies to all PyRel expressions, not just constraints. For the full table and `|` vs `model.union()` semantics, see `rai-pyrel-coding` > Boolean Logic in Expressions.

### Constraint categories

| Category | Business meaning | Pattern |
|----------|-----------------|---------|
| **Conservation/Balance** | What flows in must flow out (or be accounted for as inventory) | `inflow == outflow` or `inv_t == inv_{t-1} + in - out` |
| **Capacity/Limit** | Don't exceed available resources, budget, or physical limits | `usage <= capacity` |
| **Requirement/Minimum** | Meet minimum service levels, demand, or coverage thresholds | `provided >= required` |
| **Logical/Business Rules** | Enforce business policies like mutual exclusivity or dependencies | Conditional expressions, counting |
| **Linking/Definition** | Connect decision quantities to tracked totals or derived measures | `derived_var == f(decision_vars)` |

**Linking constraints warning:** Only works when both sides contain solver variables. "Definition" constraints where you define a property as a function of pure data properties do NOT work. For quadratic/bilinear terms, use `Float.ref()` directly in the objective/constraint.

### Constraint type classification

Classify each constraint using one of these types:

| Type | Use When | Business meaning | Examples |
|------|----------|-----------------|----------|
| **forcing** | Requires positive activity (demand satisfaction, coverage). Essential for minimize objectives — without it, solver returns zeros. | Every customer order must be fulfilled; every shift must be covered | `sum(qty) >= demand`, `sum(assigned) == 1` |
| **capacity** | Limits maximum values (resource limits, budgets, physical constraints) | Don't exceed warehouse storage, budget ceiling, or machine hours | `sum(usage) <= capacity`, `qty <= max_available` |
| **balance** | Enforces conservation/flow balance at nodes or over time | What enters a warehouse must leave or be stored | `inflow == outflow`, `start + produced - consumed == end` |
| **linking** | Connects multiple variables or enforces conditional relationships | Only ship through a facility if it is open | `qty <= M * is_active`, `var_A == f(var_B)` |
| **logical** | Cardinality constraints, either/or, at-most-one | Each task assigned to exactly one worker; select at most 3 suppliers | `sum(binary) == 1`, `sum(selected) <= K` |

**Type selection matters for validation**: forcing constraints are checked when objective is minimize, linking constraints are checked when multiple decision concepts exist.

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

### Tightness and contradictions

- A constraint is **binding** when the solution sits exactly at its boundary. Start with essential constraints, add more if solution quality is poor.
- Check that upper bounds do not conflict with lower bounds across related variables. Verify demand satisfaction is compatible with supply/capacity.
- When in doubt, use soft constraints (slack variables with penalties) instead of hard constraints.

**Too tight:** Feasible region is very small or empty. Minor data changes cause infeasibility. Consider relaxing some constraints to inequalities, adding slack variables with penalties, or using soft constraints.

**Too loose:** Solver returns degenerate or extreme solutions. Variables at bounds that shouldn't be. Add missing business rules, tighten bounds, verify coefficients are correct.

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

# Nutritional bounds: total intake within [min, max]
qty = Float.ref()
total = sum(qty * Food.amount).where(Food.contains(Nutrient, qty)).per(Nutrient)
problem.satisfy(model.require(total >= Nutrient.min, total <= Nutrient.max))

# Degree constraints: exactly one in-edge and one out-edge per node
node_flow = sum(Edge.x).per(Node)
problem.satisfy(model.require(
    node_flow.where(Edge.j == Node.v) == 1,
    node_flow.where(Edge.i == Node.v) == 1
))
```

### Demand modeling: context determines direction

Demand is NOT simply "upper bound for maximize, lower bound for minimize." The correct modeling depends on the business relationship and real-world consequences:

| Business Context | Constraint | User-facing description | Rationale |
|-----------------|------------|------------------------|-----------|
| **Market opportunity** (can sell up to demand) | `qty <= demand` | Don't produce more than customers will buy | Can't sell more than the market wants |
| **Contractual obligation** (must fulfill orders) | `qty >= demand` | Fulfill every customer order in full | Penalties or contract breach for shortfall |
| **Forced acceptance** (must take delivery) | `qty >= demand` | Accept all incoming deliveries from suppliers | Supplier pushes product; you must absorb it |
| **Flexible fulfillment** (partial OK) | Soft constraint with penalty | Meet as much demand as possible, penalizing shortfalls | Penalize shortfall in objective rather than hard constraint |

**Rule:** Ask "What happens in the real world if we go above/below this quantity?" The answer determines the constraint direction, not the objective direction.

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

For inventory balance (linking consecutive time steps), see Multi-period models in Common Problem Patterns.

### Concept-variable matching in constraints

Decision variables must be referenced on the concept where they were defined. Mismatched concept names cause "undefined variable" compile errors.

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

**Big-M guidelines:**
- Use the tightest possible M value (data-driven, not arbitrary large numbers)
- `M = capacity` or `M = max_demand` is preferred over `M = 999999`
- Big-M too loose degrades LP relaxation quality and solver performance

```python
# GOOD: M = actual capacity            | BAD: arbitrary M
x_weight <= fast_cap * y_bin_fast      # x_weight <= 999999 * y_bin_fast
```

---

## Unwired Relationships (Detailed)

A declared `model.Relationship()` without a corresponding `model.define()` rule has NO DATA at solve time. The relationship exists in the schema but has zero bindings.

**Symptoms:**
- The constraint is silently dropped — joins on the unwired relationship match zero entities, so no constraint rows are generated.
- `.per(Concept)` aggregations return nothing.
- The solver returns OPTIMAL with a vacuous objective (typically zero on minimize), masking the missing constraint.

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

Before writing any constraint, check the CONCEPT JOINABILITY section in the model context.

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

Bare references unify within the require chain — no `.ref()` aliasing is needed for this pattern. For when `.ref()` is and isn't required, see `rai-pyrel-coding` § Free-Variable Scoping.

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
problem.minimize(sum(Operation.x_flow * Operation.cost_per_unit) + PENALTY * sum(UnmetDemand.x_slack))
```

**Why this works:** Both sides aggregate `.per(UD.sku)` — the shared dimension. The slack variable ensures feasibility when supply < demand. The penalty in the objective drives the solver to satisfy demand when possible.

See templates for complete working examples.

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

**Rule 4: Always verify relationship names exist**
Before using `Concept.some_relationship` in a constraint:
- Check the RELATIONSHIPS section in context for available names
- Do NOT invent relationship names — use only what the model provides
- Common mistake: guessing names like `reviewer_githubpullrequest` when the actual name is `pull_request`

**Rule 5: Valid RHS types in `.where()` equality**
The RHS of a `.where()` equality may be:
- A **Concept type**: `.where(A.rel(ConceptName))` — groups by that concept
- A **property reference**: `.where(A.prop(B.prop))` — matches on shared values; multi-hop chains (`B.rel.nested_prop`) are also valid when populated
- A **literal value**: `.where(A.prop("value"))` or `.where(A.prop(42))`

Avoid: nested `.where()` calls.

**Rule 6: `.per()` on extended concepts — group via the extended concept's relationship, not the base concept**

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

The failure is silent — solver returns OPTIMAL with the wrong feasibility region. Verify by capturing the constraint's ref and inspecting just that constraint's grounded form:

```python
c = problem.satisfy(model.require(sum(AB.x_active).per(AB.a) == 1))
problem.display(c)  # expanded sums per A; confirm each row filters to its AB slice
```

See [diagnostic-workflow.md](diagnostic-workflow.md) for the full capture-and-inspect pattern.

**Rule 7: Access data properties on extended concepts via relationship traversal**
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
The extended concept's available properties are listed in its concept_definition; everything else lives on the base concept and must be accessed through a relationship.

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

**Balance/conservation constraint (flow preservation):**
Business description: "Everything that enters an intermediate location must also leave it."
```
GOOD (transshipment): sum(Edge.x_flow).where(Edge.dest == Node) == sum(Edge.x_flow).where(Edge.src == Node)
Why:  Strict equality prevents "leakage" at intermediate nodes.

GOOD (buffer/storage): inventory_t == inventory_{t-1} + inflow_t - outflow_t
Why:  Nodes that hold inventory use inventory balance linking periods.

BAD:  sum(Edge.x_flow).where(Edge.dest == Node) >= sum(Edge.x_flow).where(Edge.src == Node)
Why:  Bare inequality without inventory tracking allows uncontrolled accumulation.
```

**Linking constraint (Big-M, connects binary to continuous):**
Business description: "A facility can only process goods if it is open, and only up to its capacity."
```
GOOD: Entity.x_qty <= Entity.capacity * Entity.x_open
      Entity.x_qty >= Entity.min_prod * Entity.x_open
Why:  Both bounds needed. Upper: if not selected, forced to 0. Lower: if selected, must meet minimum.

BAD:  Entity.x_qty <= 999999 * Entity.x_open
Why:  Arbitrary Big-M weakens LP relaxation. Use actual data property for tight bound.
```

### Addressing user requirements

If user requirements are provided, address the underlying intent while following optimization best practices. Implementing requests verbatim often produces over-constrained or infeasible formulations.

**Principles:**
1. **Prefer static parameters over dynamic calculations** -- Easier to adjust and understand
2. **Use entity groups when available** -- Simpler than pairwise combinations
3. **Distinguish requirements from goals** -- Requirements (non-negotiable) --> constraints; Goals (can trade off) --> objective
4. **Constraints are for**: limits, capacities, budgets, rules, maximums
5. **Performance targets/goals belong in objective**, not constraints

---

## Constraint Verification

### Pre-generation verification

Before writing any constraint expression:
1. List the concepts and properties you will reference
2. Verify each one appears in AVAILABLE CONCEPTS AND PROPERTIES or DEFINED DECISION VARIABLES
3. Verify join paths: if using `.where(A.x == B)`, confirm A has a relationship to B in the model
4. If a needed property doesn't exist in the schema, skip that constraint (do not invent property names)
5. **Check variable bounds before suggesting constraints.** If a variable already has `lower_bound` or `upper_bound` defined, the bound is already enforced — only suggest constraints that add new business logic beyond existing bounds.
6. **Only reference properties that exist in the model.** If a constraint needs a property that isn't available, skip the constraint and report it as a model_gap so enrichment can add it.
7. **Check property types before using in expressions.** Look up each property in ATTRIBUTE TYPES BY CONCEPT. Only use numeric properties (`Float`, `Integer`, rai_type `:float`/`:int`) in arithmetic (`+`, `-`, `*`, `/`) and numeric comparisons (`>=`, `<=`, `>`, `<`). String properties (rai_type `:str`) — including names like `criticality`, `priority`, `risk_level` that may sound numeric but contain text values like 'High', 'Critical' — must be used only in equality filters (`.where(Concept.prop == "value")`). If a numeric version of a string property is needed, report as a model_gap requiring enrichment (string-to-numeric mapping).

### Self-check: constraints

- Every constraint references at least one registered solver variable
- Aggregation scope (`.per()`) matches constraint scope
- No contradictions between constraints (e.g., `x >= 100` and `x <= 50`)
- Join paths in `.where()` clauses match actual model relationships
- Slack variables have equality linking constraints, not just bounds

---

## Constraint Selection Guidance

For constraints: select constraints that enforce real business rules without being overly restrictive.

### Completeness checklist
1. Every decision variable appears in at least one constraint
2. If multiple decision concepts exist, every pair sharing a dimension MUST have a linking or balance constraint connecting them (not just one link total — one per shared-dimension pair)
3. Aggregation constraints link detail-level variables to summary-level variables (e.g., sum of assignment-level hours == technician-period total hours)
4. Continuous variables have effective upper bounds (via "capacity" constraints or variable bounds)
5. If the problem has a MINIMIZE objective, at least one "forcing" type constraint exists
6. Binary/indicator variables must have forcing constraints that drive related continuous variables to zero when inactive (big-M or equivalent)
7. The objective must reference variables from all relevant decision concepts — directly or indirectly via linking constraints

### Constraint interaction check (avoid conflicts)
Before finalizing selection, verify the selected constraints work together:

1. **No direct conflicts**: Check for same variables with incompatible bounds
   - Example conflict: "capacity >= 100" AND "capacity <= 50" (impossible)
   - Example conflict: Two equality constraints on same expression with different RHS

2. **No implicit conflicts**: Check if total requirements exceed total capacity
   - Example: sum(demand) > sum(supply) makes demand satisfaction infeasible
   - Example: minimum utilization per-operation conflicts with limited total demand

3. **Balance/flow constraints need exceptions for sources and sinks**:
   - "inflow == outflow" at EVERY node blocks all flow (no sources or sinks)
   - Must exclude source nodes from inflow requirement
   - Must exclude sink nodes from outflow requirement

4. **Minimum requirements must not conflict with capacity limits**:
   - "each operation ships >= 1" with "total shipped <= demand" can conflict
   - If #operations > total demand, minimum requirements are infeasible

5. **Refinement replaces simpler version**:
   When two constraints address the same business logic but one includes a data-driven factor (loss_rate, yield, efficiency):
   - KEEP the refined version (with the transformation factor)
   - DROP the simpler version (it's a special case where the factor = 1)
   - Example: "sum(flow * (1 - loss_rate)) >= demand" replaces "sum(flow) >= demand"

If conflicts detected: EXCLUDE one conflicting constraint OR note needed modification in rationale.

### Slack variable and soft constraint patterns

6. **Slack variable triads**: For each variable in a minimize objective, trace its constraint linkage:
   - If a variable appears in the objective AND in at least one constraint (== or >=), it is properly linked.
   - If a variable appears in the objective but in NO constraint, flag CRITICAL: solver will set it to lower bound (trivial zero).
   - Under minimization, `slack >= rhs` is equivalent to `slack == rhs` at optimality (solver drives slack to minimum), so `>=` is valid here — no need to require syntactic `==`.

7. **Coverage + slack + penalty patterns**: A common valid pattern is:
   - `sum(x_assigned) + x_unmet >= 1` (coverage with slack)
   - `minimize(... + M * x_unmet)` (penalty drives slack to zero when possible)
   This is correct — the slack absorbs infeasibility. When slack is present on the LHS, `>= 1` is a coverage-with-fallback pattern, not a hard per-entity minimum.

8. **Hard per-entity minimums**: `sum(x).per(entity) >= N` WITHOUT a slack variable on the LHS imposes a hard minimum of N per entity. If N * (number of entities) exceeds total capacity, the problem is INFEASIBLE. Flag as WARNING with the arithmetic.

### Forcing constraint adequacy

9. **Trivial zero risk**: Under minimization, if ALL terms have non-negative coefficients and NO constraint forces positive activity, the solver can set everything to zero. Check that at least one constraint or bound forces meaningful activity (e.g., demand satisfaction, coverage requirements, or lower bounds > 0).

---

## Parameter Derivation from Data

**Embed parameter values DIRECTLY in constraint expressions, not as separate inputs.**

Instead of: `sum(allocations) <= total_budget` with user_input_needed
Use: `sum(allocations) <= 2000000` (with the actual value in the expression AND in parameters for editing)

### Value extraction priority

**Step 1: Use existing model properties via relationship traversals (always check first)**

Before hardcoding ANY numeric value, check whether the data already exists in the model on a related concept reachable via NAVIGATION PATHS.

- If a property exists on a related concept and is reachable via a relationship traversal, use the traversal in the expression. Hardcoding a default value means the constraint won't reflect actual data and will silently produce wrong results.
- If the property exists in the model but is NOT reachable from the constraint's scope concept (no navigation path), suggest using `enrich_ontology` to denormalize it — and use a parameter as a temporary fallback.
- Only use hardcoded parameters when no matching data property exists anywhere in the model.

**model_gaps rule**: A property reachable via relationship traversal is NOT a model gap. Only report `model_gaps` for properties that truly do not exist anywhere in the model. If a property exists on a related concept but needs denormalization for performance or clarity, note it as an optimization suggestion, not a gap.

**Step 2: Check user input**
1. Check user requirements for specific values they mentioned — these override data-derived defaults
2. If user says "budget is $2M" -- use 2000000 as the default in both expression AND parameters
3. If user says "at least 80% coverage" -- use 0.8 as the threshold
4. If user says "maximum 5 items" -- use 5 as the limit

**Step 3: Derive from DATA STATISTICS (when available in context)**
For materialized models, data statistics (min, max, mean, total) are included in the DATA SUMMARY section. Use them to set sensible defaults:

| Constraint Type | How to Derive Default |
|----------------|----------------------|
| Budget/capacity limit | Use `total` from relevant attribute (e.g., total demand, total capacity) |
| Minimum requirement | Use `total` from requirement attribute (e.g., total Demand.quantity) |
| Coverage percentage | Default to 0.8-1.0 (80-100% coverage) of the total |
| Per-entity minimum | Use `mean` or `min` from the attribute |
| Per-entity maximum | Use `max` from the attribute or entity's capacity property |
| Return/profit target | Use `mean` from returns/profit attribute as baseline |

**Step 4: Last resort -- use conservative generic defaults**
Only if no user input AND no relevant data statistics:
- Minimum thresholds: use small positive value (0.01, 1, etc.)
- Maximum limits: leave unbounded or use large value
- Coverage: default to 100% (full requirement satisfaction)

The `parameters` array lets users edit values BEFORE adding the constraint.

---

## Constraints in Bi-Objective Formulations

When two objectives exist, evaluate forcing constraints against BOTH:

- **Forcing for primary:** Ensures primary objective is non-trivial (e.g., demand satisfaction forces cost > 0 when minimizing cost).
- **Forcing for secondary:** Ensures secondary has a meaningful range (e.g., minimum activity constraint ensures coverage > 0 even when primary pushes toward zero activity).
- **Cross-objective interaction:** A constraint that's non-binding for the primary may become binding as the secondary is pushed toward its extreme via the epsilon parameter. The epsilon constraint itself is generated by the loop — it's a regular `problem.satisfy(model.require(...))` call, same syntax as any other constraint.
