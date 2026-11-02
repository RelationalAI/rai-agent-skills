<!-- TOC -->
- [Variable Context Integration](#variable-context-integration)
- [Variable Principles](#variable-principles)
  - [Choosing variable type](#choosing-variable-type)
  - [solve_for parameter reference](#solve_for-parameter-reference)
  - [Variable bounds from data vs literals](#variable-bounds-from-data-vs-literals)
  - [Sparse variable creation with where=[]](#sparse-variable-creation-with-where)
  - [Decision variable x_ prefix convention](#decision-variable-x_-prefix-convention)
  - [Naming conventions](#naming-conventions)
- [Advanced Variable Patterns](#advanced-variable-patterns)
  - [Multi-argument properties as variables](#multi-argument-properties-as-variables)
  - [Standalone properties as variables](#standalone-properties-as-variables)
  - [Pairwise constraints with .ref() and walrus :=](#pairwise-constraints-with-ref-and-walrus-)
  - [Symmetry breaking](#symmetry-breaking)
  - [Conditional fixing from data](#conditional-fixing-from-data)
  - [Piecewise-linear (PWL) modeling](#piecewise-linear-pwl-modeling)
  - [Derived properties for intermediate computations](#derived-properties-for-intermediate-computations)
  - [Config-driven parameterization](#config-driven-parameterization)
- [Scenario and Parameterization Patterns](#scenario-and-parameterization-patterns)
<!-- /TOC -->

## Variable Context Integration

**1. Identify the Primary Decision Variable FIRST:**

Before suggesting auxiliary or aggregation variables, identify the **primary decision entity** — the concept where the core decision actually lives. Always suggest the primary variable on that entity first. Aggregation or tracking variables on parent dimensions are secondary.

**How to find the primary decision entity in any model:**
- **Finest-grain entity**: Look for the concept with the highest entity count relative to its parent dimensions — it is typically the cross-product of grouping dimensions and carries per-entity bounds or response data
- **Per-entity bounds**: Concepts with min/max properties (spend bounds, capacity limits, quantity ranges) are where individual allocation or sizing decisions happen
- **Response/cost data**: Concepts with outcome coefficients (slopes, unit costs, returns, weights) signal where the objective is evaluated — the decision variable belongs here
- **Hierarchy leaf**: If the model has a dimensional hierarchy (e.g., Region > Country > Site > Route), the leaf level is almost always the primary decision entity
- **Existing decision-ready properties**: Look for properties already named for decisions (allocation, flow, quantity, assignment) — these were designed as decision variable targets

**Why this matters:** Suggesting only aggregation-level variables (e.g., total per channel, total per campaign) without the leaf-level variable makes the formulation incomplete — the solver needs individual decisions to optimize, and aggregate constraints reference sums of those individual decisions.

**2. Decision Criteria for Variable Pattern Selection:**

**Choose the simplest pattern that works.** Extended property is the default; cross-product is the exception. Unnecessary cross-products explode entity counts and slow solves.

```
WHICH PATTERN TO USE:
├── Does the model have an entity concept that naturally represents your decision?
│   │   (e.g., Operation for "how much to ship", Product for "how much to produce")
│   ├── YES → Add x_ property to that existing concept
│   │         Example: Operation.x_flow = model.Property(f"{Operation} has {Float:flow}")
│   └── NO  → Does your decision span TWO entity types with no existing link?
│       │     (e.g., "assign Worker to Shift" when no WorkerShift concept exists)
│       ├── YES → Create cross-product concept (use `model.define(...)` + `.new()` for table-backed)
│       │         Example: model.define(Assignment.new(worker=Worker, shift=Shift))
│       └── NO  → Do you need to track aggregated quantities per dimension?
│           │     (e.g., "unmet demand per SKU", "surplus per region")
│           ├── YES → Create concept from existing relationship
│           │         Example: model.define(UnmetDemand.new(sku=Demand.sku))
│           └── NO  → Use existing property with solve_for
```

**Key heuristic:** If the model has Operation/Pipeline/Route/Edge concepts connecting entities, put flow/quantity variables directly on those concepts. Do NOT create a new FlowDecision concept — the existing concept already has the right entity granularity.

**3. Entity Creation Strategy (Problem-Type Dependent):**

The entity creation strategy for cross-product concepts depends on the **problem type**:

**Assignment/allocation problems** (assigning workers to shifts, machines to jobs, suppliers to orders):
- Use **full cross-product** — the solver must consider ALL possible pairings
- `model.define(Assignment.new(worker=Worker, shift=Shift))` — no `.where()` filter
- Constraints (not entity creation) determine which assignments are selected
- Filtering by existing relationships would exclude valid assignment options

**Flow/network problems** (routing, transportation, supply chain flow):
- Use **relationship-grounded** entity creation — only existing edges carry flow
- `model.define(Flow.new(operation=Operation)).where(Operation.site == Site)` — `.where()` restricts to valid routes
- The network topology defines which flows are possible

**Aggregation concepts** (slack/unmet demand, summary variables):
- Use **shared dimension grounding** — one entity per unique dimension value
- `model.define(UnmetDemand.new(sku=Demand.sku))` — one per unique demanded SKU

```python
# ASSIGNMENT: Full cross-product (all possible pairings)
model.define(WorkerShift.new(worker=Worker, shift=Shift))

# FLOW/TOPOLOGY: Grounded by relationship (only existing routes)
model.define(TaskAssignment.new(task=Task, sprint=Sprint)).where(
    Task.sprint == Sprint
)

# AGGREGATION: Grounded via shared dimension
model.define(UnmetDemand.new(sku=Demand.sku))  # One per unique SKU
```

**Warning:** A bare cross-product `model.define(X.new(a=A, b=B))` produces N*M entities, whether A and B are populated from tables or from `model.data(...)`. For large entity counts (>100 on each side), consider if the problem truly requires all pairings or if a relationship filter is appropriate.

**4. Slack Variables for Feasibility:**

When the problem involves **minimizing cost/distance/time subject to demand or requirement constraints**, add a slack/unmet-demand variable. Without it, if supply < demand the solver returns INFEASIBLE instead of a useful partial solution. Complete example (variable, constraint and penalty): "Demand satisfaction with slack via shared dimension" in [constraint-formulation.md](constraint-formulation.md).

Pattern: Create a slack concept from the demand/requirement dimension with a continuous variable (lower=0). Include in both the demand constraint (supply + slack >= demand) and the objective (original_cost + PENALTY * (sum(UnmetDemand.x_quantity) | 0.0)).

```python
UnmetDemand = model.Concept("UnmetDemand")
UnmetDemand.sku = model.Property(f"{UnmetDemand} for {SKU:sku}")
UnmetDemand.x_quantity = model.Property(f"{UnmetDemand} of {Float:quantity}")
model.define(UnmetDemand.new(sku=Demand.sku))
# Include in constraint: inflow + slack >= demand
# Include in objective: cost + PENALTY * (sum(UnmetDemand.x_quantity) | 0.0)
```

For v1 entity creation syntax (junction table patterns, filtered cross-products, `.where()` vs `.new()` kwargs), see `rai-pyrel` > Data Loading Patterns and templates for complete working examples.

**5. Multi-Index Variables on Existing Concepts (Prefer Over Cross-Product Concepts):**

When a decision variable is naturally indexed by an existing concept plus one or more dimensions, use a **multi-argument property** on the existing concept. Do NOT create a cross-product concept just to carry a variable.

**Common hallucination to avoid:** Given concepts `Mode` and `ResourceGroup`, do NOT invent `ModeResourceDecision` as a cross-product concept. Instead, add a multi-index property to the concept that naturally carries the decision:

```python
# WRONG — hallucinated cross-product concept:
ModeResourceDecision = model.Concept("ModeResourceDecision")
ModeResourceDecision.mode = model.Relationship(...)
ModeResourceDecision.resource = model.Relationship(...)
# This creates unnecessary entities and complexity

# CORRECT — multi-index property on existing concept:
Mode.qty_mode = model.Property(
    f"{Mode} ships {ResourceGroup} quantity {Float:qty_mode}"
)
rg = ResourceGroup.ref()
x = Float.ref()
problem.solve_for(
    Mode.qty_mode(rg, x), lower=0,
    name=["qty_mode", Mode.name, rg.name],
    where=[Mode.available_for(rg)],  # Grounded by existing relationship
)
```

**Decision rule for multi-index vs cross-product:**
- If the decision naturally belongs on one concept but is indexed by another → **multi-index property** (e.g., "how much Mode ships per ResourceGroup")
- If the decision is inherently about a pairing with no natural owner → **cross-product concept** (e.g., "assign Worker to Shift")
- If the model already has a relationship between the concepts → **always prefer multi-index** using `where=[]` to ground variables on the relationship (examples: [Sparse variable creation with `where=[]`](#sparse-variable-creation-with-where))

---

## Variable Principles

### Choosing variable type

| Type | When to use | Business meaning | Examples | `type=` | Num type |
|------|-------------|-----------------|----------|---------|----------|
| **Continuous** | Quantities, amounts, flows, weights, fractions | How much? | Gallons shipped, dollars allocated, percentage weight | `"cont"` (default) | `Float` |
| **Integer** | Counts, schedules, indices, ordering values | How many? | Number of workers, units produced, trucks dispatched | `"int"` | `Float` (MIP); `Integer` only for pure CP |
| **Binary** | Yes/no decisions, selection, activation | Should we or not? | Open this facility, assign this worker, select this supplier | `"bin"` | `Float` (for MILP with binary + continuous vars); `Integer` only for pure CP |

Use the most restrictive type that fits. Binary is a special case of integer. Continuous problems solve faster than integer/mixed-integer.

**Problem numeric type:** `Problem(model, Float)` runs on HiGHS, Gurobi or Ipopt, including MIPs through `type="int"`/`"bin"`; `Problem(model, Integer)` runs on MiniZinc. `Float` with `type="int"` variables (MIP) is NOT the same as `Integer`: different solver stacks, different expression support. The variable property's value type must match the Problem's numeric type — a `Float` property in `Problem(model, Float)` even for `type="int"`/`"bin"`, an `Integer` property in `Problem(model, Integer)` — or `solve_for` raises `ValueError`. Which to pick: `SKILL.md` > Problem Type Classification and Solver Selection.

### `solve_for` parameter reference

```python
var = problem.solve_for(
    property_or_binding,   # Property or multiarity binding like Prop(ref1, ref2, x)
    type="cont",           # "cont" (default), "int", or "bin"
    name=...,              # String or list for variable naming
    lower=...,             # Lower bound: literal or Property
    upper=...,             # Upper bound: literal or Property
    where=[...],           # List of conditions restricting variable creation
    start=...,             # Initial value, literal or Property: a warm start on HiGHS/Gurobi/Ipopt, ignored by MiniZinc
    populate=True,         # If False, solution values not written back to model (for parametric solving)
)
# var is a ProblemVariable concept — usable with model.select(), .ref(), Variable.values()
```

`start=` details: [solver-parameters.md](../../rai-prescriptive-results/references/solver-parameters.md) > Warm Starting.

### Reserved field names (v1.0.14+)

A non-value field name in the relationship that shadows a `ProblemVariable` attribute (`name`, `type`, `lower`, `upper`, `start`, `values`, `alias`, `select`, `where`, ...) raises `ValueError` at `solve_for()`; the message lists the full reserved set. Use domain names instead: `{String:customer_name}`, not `{String:name}`.

### Variable naming (`name=[]`)

The `name=[]` parameter labels variables in solver output. Each part must resolve to a **scalar** — a primitive Property, an Integer/String ref, or a multi-hop chain ending in a primitive (e.g. `Concept.rel.id`). A bare Concept-typed Relationship ref errors because it resolves to an entity. List elements are joined with underscores.

```python
# CORRECT — primitive identity fields and multi-hop chains:
problem.solve_for(Food.x_amount, lower=0, name=["x_amount", Food.name])
problem.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])
problem.solve_for(PlacementSegment.x_alloc, lower=0,
            name=["seg", PlacementSegment.placement.pid, PlacementSegment.seg_idx])

# WRONG — Concept-typed Relationship refs (cause TyperError):
problem.solve_for(MachinePeriod.x_maintain, type="bin",
            name=["x_maintain", MachinePeriod.machine])  # machine is a Concept ref!

# CORRECT for cross-product concepts — navigate one hop to a primitive, and cover
# both dimensions. A bare name=["x_maintain"] compiles but names every row the same,
# which `display()` cannot disambiguate (see Naming conventions below):
problem.solve_for(MachinePeriod.x_maintain, type="bin",
            name=["x_maintain", MachinePeriod.machine.id, MachinePeriod.period])
```

With `populate=True` (default), values write back to the Property and are queryable via `model.select(Concept.name, Concept.x_var)`. With `populate=False` (parametric/loop workflows), read results via `var.values(sol_index, val_ref)` paired with the back-pointer attribute on the returned `ProblemVariable` — see `rai-prescriptive-results` > Solution Extraction for the back-pointer naming rule.

### Variable bounds from data vs literals

Prefer data-driven bounds over hardcoded literals. Bounds from properties automatically apply per-entity. There is no implicit `lower=0`: a variable without `lower=` is free, so set it on every non-negative quantity.

```python
# Data-driven bounds (preferred)
problem.solve_for(Product.quantity, lower=0, upper=Product.demand, name=["x_qty", Product.name])
problem.solve_for(Node.u, type="int", lower=1, upper=node_count, name=["u", Node.v])

# Literal bounds
problem.solve_for(Food.amount, lower=0, name=["x_amount", Food.name])  # No upper bound
problem.solve_for(Queen.column, type="int", lower=0, upper=n - 1, name=["x", Queen.row])
```

### Derived scalar bounds via stored Relationship

When a bound depends on a derived value (e.g., count of entities), store it as a standalone `Relationship` and reference it in `solve_for(upper=...)`:

```python
# count() in solver bounds requires a stored Relationship
node_count = model.Relationship(f"node count is {Integer}")
model.define(node_count(count(Node)))
problem.solve_for(Node.u, type="int", lower=1, upper=node_count)
```

This pattern applies whenever a bound is computed from data (counts, max values, sums) rather than a property on the variable's concept. See `../examples/subtour_elimination_mtz.py`.

### Standalone variables (not attached to a named concept)

For variables indexed by a primitive type rather than a named concept, use a standalone `Property`:

```python
# Standalone property — created via model.Property(), not attached to a concept
bin_fast = model.Property(f"departure day {Integer:t} has {Float:bin_fast}")
problem.solve_for(bin_fast(t, y_bin_fast), type="bin", name=["y_bin_fast", t],
            where=[t == departure_days])
```

Use this when no appropriate concept exists as a carrier, or when a variable is purely parametric (indexed only by Integer, String, etc.). See `../examples/multi_concept_added_objective.py`.

### Sparse variable creation with `where=[]`

Create variables only where they are meaningful. This reduces problem size and prevents infeasibility from missing data.

```python
# Only create assignment variables for available worker-shift pairs
problem.solve_for(
    Worker.x_assign(Shift, x), type="bin",
    name=["x", Worker.name, Shift.name],
    where=[Worker.available_for(Shift)]
)

# Only create inventory variables for valid time windows per resource group
problem.solve_for(
    ResourceGroup.inv(t, x_inv), lower=0,
    name=["x_inv", ResourceGroup.name, t],
    where=[t == std.common.range(ResourceGroup.inv_start_t, ResourceGroup.inv_end_t + 1)]
)

# Scope to a specific factory's products
problem.solve_for(
    Product.quantity, lower=0, upper=Product.demand,
    name=Product.name, where=[Product.factory.name("steel_factory")],
)
```

### Decision variable `x_` prefix convention

Decision variable attributes use `x_` prefix on the concept attribute (`Concept.x_prop`) to distinguish solver-controlled quantities from fixed data:

```python
Food.x_amount = model.Property(f"{Food} has {Float:amount}")
Edge.x_flow = model.Property(f"{Edge} has {Float:flow}")
```

For the underlying Property f-string rules (TYPE FIRST, then field name; valid Python identifiers; same pattern for Relationships), see `rai-pyrel` > Property f-strings. Those rules are general PyRel grammar, not prescriptive-specific.

When accessing decision variables through `.ref()` aliases, use the Python attribute name (with `x_` prefix), not the semantic slot name. The solver resolves variables by attribute name:

```python
OpRef = Operation.ref()
sum(OpRef.x_flow)      # Correct -- Python attribute name
sum(OpRef.flow)        # Wrong -- semantic slot name, solver can't resolve
```

### Naming conventions

Use a descriptive prefix (`"qty_"`, `"sel_"`, `"x_"`, `"inv_"`) so post-solve DataFrames can be filtered by `name.str.startswith("prefix")`. Naming is not only a readback convenience: from `relationalai>=1.29`, `problem.display()` raises `ValueError` unless every decision variable in the Problem carries a `name=`, checked once at least one has grounded. The name must also discriminate, since a constant name on a per-entity variable makes rows indistinguishable wherever their remaining terms match too. For the scalar-resolution rule on `name=[]` parts, see [Variable naming (`name=[]`)](#variable-naming-name) above.

```python
# Single-index: property name as identifier
problem.solve_for(Food.amount, name=Food.name, lower=0)

# Multi-index: prefix + identifiers
problem.solve_for(Edge.flow, name=["x", Edge.i, Edge.j], lower=0, upper=Edge.cap)
problem.solve_for(ResourceGroup.inv(t, x_inv), name=["x_inv", ResourceGroup.name, t])

# Named constraints and objectives
problem.satisfy(fix_node, name="fix0")
problem.satisfy(diff_colors, name=["diff", Edge.i, Edge.j])
problem.minimize(chromatic_number, name="chromatic_number")
```

---

## Advanced Variable Patterns

### Multi-argument properties as variables

For variables indexed by multiple dimensions, define a multiarity property and bind with refs.

```python
# Assignment: player -> week -> group
Player.assign = model.Property(f"{Player} in {Integer:week} is in {Integer:group}")
problem.solve_for(
    Player.assign(w, x), type="int", lower=0, upper=n_groups - 1,
    name=["x", Player.p, w], where=[w == std.common.range(n_weeks)],
)
```

For time-indexed multiarity variables (inventory, production), see Multi-period models in Common Problem Patterns.

### Standalone properties as variables

For variables not attached to any concept (e.g., grid cells), use `model.Property` directly.

```python
i, j, x = Integer.ref().alias("i"), Integer.ref().alias("j"), Integer.ref().alias("x")
cell = model.Property(f"cell {Integer:i} {Integer:j} is {Integer:x}")
problem.solve_for(
    cell(i, j, x), type="int", lower=1, upper=n,
    name=["x", i, j],
    where=[i == std.common.range(1, n + 1), j == std.common.range(1, n + 1)],
)
```

### Pairwise constraints with `.ref()` and walrus `:=`

For pairwise / quadratic constraints over the same concept, `.ref()` creates a second independent instance and walrus `:=` binds it inline. (For when refs are and aren't needed in general, see `rai-pyrel` § Free-Variable Scoping — pairwise is the canonical correct case.)

```python
# Two players: limit shared groups across weeks
problem.satisfy(model.where(
    p0 := Player.ref(), p1 := Player.ref(), p0.p < p1.p,
    x0 := Integer.ref(), x1 := Integer.ref(),
    p0.assign(w, x0), p1.assign(w, x1),
).require(count(w, x0 == x1).per(p0, p1) <= 1))

# Two stocks for covariance (quadratic)
Stock2 = Stock.ref()
risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
```

For MTZ subtour elimination, see TSP in Common Problem Patterns. For time-indexed inventory balance, see Multi-period models.

### Symmetry breaking

Reduce the search space by fixing arbitrary choices.

```python
problem.satisfy(model.where(Node.v(0)).require(Node.color == 1))                      # Fix node 0 to color 1
problem.satisfy(model.where(Player.assign(0, x)).require(x == Player.p // group_size)) # Fix week 0 assignment
problem.satisfy(model.require(Node.u == 1).where(Node.v(1)))                          # Fix TSP ordering u[1] = 1
```

### Conditional fixing from data

```python
problem.satisfy(model.require(x == fixed.fix).where(cell(fixed.i, fixed.j, x)))  # Sudoku known cells
problem.satisfy(model.require(x_inv == 0).where(ResourceGroup.inv(ResourceGroup.inv_end_t, x_inv)))  # End inventory
problem.satisfy(model.require(x_inv == ResourceGroup.inv_start).where(
    ResourceGroup.inv(ResourceGroup.inv_start_t, x_inv)
))  # Start inventory
```

### Piecewise-linear (PWL) modeling

Model diminishing returns, tiered pricing, or nonlinear functions as a set of linear segments. Each segment has a slope and length; the solver allocates within segments. Because slopes decrease, the LP relaxation naturally fills higher-slope segments first — no integer variables needed for concave objectives.

```python
# Junction concept: one segment per (placement, segment_index)
PlacementSegment = model.Concept("PlacementSegment",
    identify_by={"placement": Placement, "seg_idx": Integer})

# Segment data: slope and length from breakpoint analysis
PlacementSegment.slope = model.Property(f"{PlacementSegment} has {Float:slope}")
PlacementSegment.seg_len = model.Property(f"{PlacementSegment} has {Float:seg_len}")

# Segment-level variable: allocation within each segment
problem.solve_for(PlacementSegment.x_alloc, lower=0, upper=PlacementSegment.seg_len,
            name=["seg", PlacementSegment.placement.id, PlacementSegment.seg_idx])

# Link: total allocation = sum of segment allocations
problem.satisfy(model.require(
    Placement.x_total == sum(PlacementSegment.x_alloc)
        .where(PlacementSegment.placement(Placement)).per(Placement)
))

# Objective: sum of slope * segment_allocation (concave -> LP-solvable)
problem.maximize(sum(PlacementSegment.slope * PlacementSegment.x_alloc))
```

### Derived properties for intermediate computations

Use `model.where(...).define(...)` to create reusable intermediate values that simplify constraint expressions. Useful when the same aggregation appears in multiple constraints.

```python
# Compute total inbound flow per node (reused in balance and capacity constraints)
model.where(Edge.target(Node)).define(
    Node.total_inflow(sum(Edge.x_flow).per(Node))
)

# Conditional derivation: different sources for the same property
model.where(Edge2 := Edge.ref()).define(
    Edge.new(i=Edge2.j, j=Edge2.i)  # Reverse edges
)
```

### Config-driven parameterization

Externalize business thresholds (budgets, tolerances, minimum shares) as parameters rather than hardcoding in constraints. To find which constraint makes a model INFEASIBLE, request the conflict first rather than dropping constraints one at a time: [diagnostic-workflow.md](diagnostic-workflow.md) > INFEASIBLE: localizing the conflict.

---

## Scenario and Parameterization Patterns

### Scenario Concept — parameter variations (preferred)

Model scenarios as a Concept when varying numeric parameters. Decision variables become
multi-argument Properties indexed by (Entity, Scenario):

```python
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.budget = Property(f"{Scenario} has {Float:budget}")
model.define(Scenario.new(model.data(
    [("low", 1e6), ("high", 5e6)], columns=["name", "budget"]
).to_schema()))

# Variable indexed by Scenario
Route.x_flow = Property(f"{Route} in {Scenario} has {Float:flow}")
x_flow = Float.ref()

# solve_for with Scenario binding
problem.solve_for(Route.x_flow(Scenario, x_flow), name=[Scenario.name, Route.origin, Route.dest])

# Constraint with .per(Scenario)
problem.satisfy(model.where(Route.x_flow(Scenario, x_flow)).require(
    sum(x_flow * Route.cost).per(Scenario) <= Scenario.budget
))
```

**Key rules:**
- Variable Property uses `f"{Entity} in {Scenario} is {Float:var}"` pattern
- All constraints/objectives that reference the variable must bind Scenario via `model.where(Entity.x_var(Scenario, ref))`
- Use `.per(Scenario)` for aggregations that should be per-scenario
- Reference `Scenario.param` instead of literal values in constraints
- `name=[]` in solve_for should include `Scenario.name` for labeling
- Single solve — no loop needed

See `rai-prescriptive-results/examples/scenario_concept_parameter_sweep.py` and `scenario_concept_milp.py`. When to prefer the Scenario Concept, and the Loop + `where=` pattern for entity exclusion and partitioned sub-problems (`rai-prescriptive-results/examples/partitioned_iteration_scenarios.py`): [scenario-analysis.md](scenario-analysis.md).

---
