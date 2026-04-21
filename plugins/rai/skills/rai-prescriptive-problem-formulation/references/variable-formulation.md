<!-- TOC -->
- [Variable Context Integration](#variable-context-integration)
- [Variable Principles](#variable-principles)
  - [Choosing variable type](#choosing-variable-type)
  - [solve_for parameter reference](#solve_for-parameter-reference)
  - [Bounds guidance](#bounds-guidance)
  - [Deriving bounds from data](#deriving-bounds-from-data)
  - [Variable bounds from data vs literals](#variable-bounds-from-data-vs-literals)
  - [Granularity](#granularity)
  - [Sparse variable creation with where=[]](#sparse-variable-creation-with-where)
  - [Decision variable x_ prefix convention](#decision-variable-x_-prefix-convention)
  - [Naming conventions](#naming-conventions)
  - [Self-check: variables](#self-check-variables)
- [Advanced Variable Patterns](#advanced-variable-patterns)
  - [Multi-argument properties as variables](#multi-argument-properties-as-variables)
  - [Standalone properties as variables](#standalone-properties-as-variables)
  - [Pairwise constraints with .ref() and walrus :=](#pairwise-constraints-with-ref-and-walrus-)
  - [Symmetry breaking](#symmetry-breaking)
  - [Conditional fixing from data](#conditional-fixing-from-data)
  - [Piecewise-linear (PWL) modeling](#piecewise-linear-pwl-modeling)
  - [Derived properties for intermediate computations](#derived-properties-for-intermediate-computations)
  - [Config-driven parameterization and constraint tiers](#config-driven-parameterization-and-constraint-tiers)
- [Scenario and Parameterization Patterns](#scenario-and-parameterization-patterns)
<!-- /TOC -->

## Variable Context Integration

**Your suggestions should be inspired by BOTH the base model structure AND any user inputs.**

**1. Start with the Base Model:**
- Examine the concepts, properties, and relationships in the model
- Identify which properties naturally represent decisions (quantity, assigned, amount, etc.)
- Understand what optimization problems this model is designed to support

**2. Layer in User Goals (if provided):**
If the user provided goals (look for WHAT USER IS SOLVING FOR, USER'S REQUIREMENTS AND LIMITS, HOW USER MEASURES SUCCESS):
- Parse their input to understand their specific needs
- Identify values, options, or limits they mentioned (e.g., "budget is $10K", "options are A, B, C")
- Align your suggestions with both the model's capabilities AND the user's stated goals

**3. Identify the Primary Decision Variable FIRST:**

Before suggesting auxiliary or aggregation variables, identify the **primary decision entity** — the concept where the core decision actually lives. Always suggest the primary variable on that entity first. Aggregation or tracking variables on parent dimensions are secondary.

**How to find the primary decision entity in any model:**
- **Finest-grain entity**: Look for the concept with the highest entity count relative to its parent dimensions — it is typically the cross-product of grouping dimensions and carries per-entity bounds or response data
- **Per-entity bounds**: Concepts with min/max properties (spend bounds, capacity limits, quantity ranges) are where individual allocation or sizing decisions happen
- **Response/cost data**: Concepts with outcome coefficients (slopes, unit costs, returns, weights) signal where the objective is evaluated — the decision variable belongs here
- **Hierarchy leaf**: If the model has a dimensional hierarchy (e.g., Region > Country > Site > Route), the leaf level is almost always the primary decision entity
- **Existing decision-ready properties**: Look for properties already named for decisions (allocation, flow, quantity, assignment) — these were designed as decision variable targets

**Why this matters:** Suggesting only aggregation-level variables (e.g., total per channel, total per campaign) without the leaf-level variable makes the formulation incomplete — the solver needs individual decisions to optimize, and aggregate constraints reference sums of those individual decisions.

**4. Decision Criteria for Variable Pattern Selection:**

**Choose the simplest pattern that works.** Extended property is the default; cross-product is the exception. Unnecessary cross-products explode entity counts and slow solves.

```
WHICH PATTERN TO USE:
├── Does the model have an entity concept that naturally represents your decision?
│   │   (e.g., Operation for "how much to ship", Product for "how much to produce")
│   ├── YES → Add x_ property to that existing concept
│   │         Example: Operation.x_flow = model.Property(f"{Operation} has {Float:flow}")
│   └── NO  → Does your decision span TWO entity types with no existing link?
│       │     (e.g., "assign Worker to Shift" when no WorkerShift concept exists)
│       ├── YES → Create cross-product concept (use model.query() for table-backed)
│       │         Example: model.define(Assignment.new(worker=Worker, shift=Shift))
│       └── NO  → Do you need to track aggregated quantities per dimension?
│           │     (e.g., "unmet demand per SKU", "surplus per region")
│           ├── YES → Create concept from existing relationship
│           │         Example: model.define(UnmetDemand.new(sku=Demand.sku))
│           └── NO  → Use existing property with solve_for
```

**Key heuristic:** If the model has Operation/Pipeline/Route/Edge concepts connecting entities, put flow/quantity variables directly on those concepts. Do NOT create a new FlowDecision concept — the existing concept already has the right entity granularity.

**v1 constraint — table-backed concepts:** Variables CANNOT be added directly to table-backed (`identify_by`) concepts in v1. `Problem.solve()` raises `TyperError (UnresolvedOverload)` when solving for properties on these concepts. The code generator automatically wraps such variables in decision concepts (e.g., `Operation` → `OperationDecision` with a Relationship back to `Operation`). Prefer the `extended_concept` pattern explicitly for table-backed concepts when writing templates or formulations by hand.

**5. Entity Creation Strategy (Problem-Type Dependent):**

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

**Decision rule:**
- If the problem asks "which pairings to select/assign" → full cross-product (assignment)
- If the problem asks "how much to flow along existing paths" → relationship-grounded (flow)
- If the problem aggregates by a dimension → shared dimension grounding
- If no relationship exists between A and B → full cross-product (no choice)

```python
# ASSIGNMENT: Full cross-product (all possible pairings)
model.define(WorkerShift.new(worker=Worker, shift=Shift))

# FLOW/TOPOLOGY: Grounded by relationship (only existing routes)
model.define(IssueAssignment.new(issue=JiraIssue, sprint=JiraSprint)).where(
    JiraIssue.sprint == JiraSprint
)

# AGGREGATION: Grounded via shared dimension
model.define(UnmetDemand.new(sku=Demand.sku))  # One per unique SKU
```

**Warning:** Full cross-product of table-backed concepts can produce N*M entities. For large entity counts (>100 on each side), consider if the problem truly requires all pairings or if a relationship filter is appropriate.

**6. Slack Variables for Feasibility:**

When the problem involves **minimizing cost/distance/time subject to demand or requirement constraints**, you MUST suggest a slack/unmet-demand variable. Without it, if supply < demand the solver returns INFEASIBLE instead of a useful partial solution.

Pattern: Create a slack concept from the demand/requirement dimension with a continuous variable (lower=0). Include in both the demand constraint (supply + slack >= demand) and the objective (original_cost + PENALTY * sum(slack)).

```python
UnmetDemand = model.Concept("UnmetDemand")
UnmetDemand.sku = model.Property(f"{UnmetDemand} for {SKU:sku}")
UnmetDemand.x_quantity = model.Property(f"{UnmetDemand} of {Float:quantity}")
model.define(UnmetDemand.new(sku=Demand.sku))
# Include in constraint: inflow + slack >= demand
# Include in objective: cost + PENALTY * sum(slack)
```

**Entity Creation Rules (check context before choosing):**
1. **Check if concepts are TABLE-BACKED**: If so, bare `model.define(X.new(a=A, b=B))` produces 0 entities — a junction table or filtered `.where()` is required.
2. **Bare cross-product** (`model.define(X.new(a=A, b=B))`) only works for inline (non-table-backed) concepts with small entity counts.

For v1 entity creation syntax (junction table patterns, filtered cross-products, `.where()` vs `.new()` kwargs), see `rai-pyrel-coding` > Data Loading Patterns and templates for complete working examples.

**7. Multi-Index Variables on Existing Concepts (Prefer Over Cross-Product Concepts):**

When a decision variable is naturally indexed by an existing concept plus one or more dimensions, use a **multi-argument property** on the existing concept. Do NOT create a cross-product concept just to carry a variable.

**Common hallucination to avoid:** Given concepts `TransportType` and `FreightGroup`, do NOT invent `TransportFreightDecision` as a cross-product concept. Instead, add a multi-index property to the concept that naturally carries the decision:

```python
# WRONG — hallucinated cross-product concept:
TransportFreightDecision = model.Concept("TransportFreightDecision")
TransportFreightDecision.transport = model.Relationship(...)
TransportFreightDecision.freight = model.Relationship(...)
# This creates unnecessary entities and complexity

# CORRECT — multi-index property on existing concept:
TransportType.qty_tra = model.Property(
    f"{TransportType} ships {FreightGroup} quantity {Float:qty_tra}"
)
fg = FreightGroup.ref()
x = Float.ref()
problem.solve_for(
    TransportType.qty_tra(fg, x), lower=0,
    name=["qty_tra", TransportType.name, fg.name],
    where=[TransportType.available_for(fg)],  # Grounded by existing relationship
)
```

**Decision rule for multi-index vs cross-product:**
- If the decision naturally belongs on one concept but is indexed by another → **multi-index property** (e.g., "how much TransportType ships per FreightGroup")
- If the decision is inherently about a pairing with no natural owner → **cross-product concept** (e.g., "assign Worker to Shift")
- If the model already has a relationship between the concepts → **always prefer multi-index** using `where=[]` to ground variables on the relationship

**Grounding multi-index variables with `where=[]`:**

```python
# Ground by existing relationship (only create variables where relationship exists)
problem.solve_for(
    Worker.hours(Shift, x), lower=0,
    where=[Worker.available_for(Shift)],  # Uses existing availability relationship
)

# Ground by data range (parametric/time-indexed)
problem.solve_for(
    FreightGroup.inv(t, x_inv), lower=0,
    where=[t == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)],
)
```

---

## Concept Name Exactness

When defining extended_concept variables, reference base model concepts using their
EXACT names as listed in the "Entity Types" line of the model context. Extended concept
Relationship definitions and `.new()` entity creation args must use these precise
PascalCase names. Do not abbreviate or paraphrase — the validation will reject
suggestions that reference concepts not in the model.

---

## Variable Principles

### Choosing variable type

| Type | When to use | Business meaning | Examples | `type=` | Num type |
|------|-------------|-----------------|----------|---------|----------|
| **Continuous** | Quantities, amounts, flows, weights, fractions | How much? | Gallons shipped, dollars allocated, percentage weight | `"cont"` (default) | `Float` |
| **Integer** | Counts, schedules, indices, ordering values | How many? | Number of workers, units produced, trucks dispatched | `"int"` | `Integer` |
| **Binary** | Yes/no decisions, selection, activation | Should we or not? | Open this facility, assign this worker, select this supplier | `"bin"` | `Float` (for MILP with binary + continuous vars); `Integer` only for pure CP |

Use the most restrictive type that fits. Binary is a special case of integer. Continuous problems solve faster than integer/mixed-integer.

**Decision rule:** Ask "What can I adjust to improve the outcome?" If the answer is a quantity, use continuous. If it is a count, use integer. If it is a yes/no choice, use binary.

**Problem numeric type — the key implementation axis:**

| Numeric Type | Solver Stack | When to Use | Examples |
|-------------|-------------|-------------|----------|
| `Float` | HiGHS (LP/MIP), Gurobi, Ipopt (NLP) | Any problem with continuous variables; MIP with `type="int"` | Diet, portfolio, flow, scheduling with binary vars |
| `Integer` | MiniZinc (combinatorial) | Pure integer/combinatorial problems; satisfaction problems | Sudoku, n-queens, graph coloring, social golfer |

**Important:** `Float` with `type="int"` variables (MIP) is NOT the same as `Integer`. MIP uses branch-and-bound on continuous relaxation (HiGHS/Gurobi). Integer uses pure combinatorial search (MiniZinc). Different solver stacks, different expression support.

**Use `Integer` when:**
- All variables have finite discrete domains
- You need global constraints (`all_different`, cardinality)
- The problem is pure satisfaction (no objective)
- Pairwise inequality or combinatorial structure dominates

**Use `Float` when:**
- Any variable is continuous (quantities, flows, weights)
- You mix continuous + integer variables (MIP)
- Linear/quadratic expressions dominate

```python
problem = Problem(model, Float)    # Continuous/MIP (diet, portfolio, flow, scheduling)
problem = Problem(model, Integer)  # Pure combinatorial (sudoku, n-queens, graph coloring)
```

### `solve_for` parameter reference

```python
var = problem.solve_for(
    property_or_binding,   # Property or multiarity binding like Prop(ref1, ref2, x)
    type="cont",           # "cont" (default), "int", or "bin"
    name=...,              # String or list for variable naming
    lower=...,             # Lower bound: literal or Property
    upper=...,             # Upper bound: literal or Property
    where=[...],           # List of conditions restricting variable creation
    start=...,             # Warm start value (for nonlinear solvers like Ipopt)
    populate=True,         # If False, solution values not written back to model (for parametric solving)
)
# var is a ProblemVariable concept — usable with model.select(), .ref(), Variable.values()
```

### Bounds guidance

**Lower bounds:**
- Physical minimums (cannot be negative if quantity) -- use 0 for most decision variables
- Business rules (minimum order size, minimum allocation)
- Use entity attributes when available: `Entity.min_value`

**Upper bounds:**
- Capacity limits (cannot exceed physical capacity)
- Budget constraints (cannot spend more than available)
- Use entity attributes when available: `Entity.capacity`
- Omit for unbounded (rarely needed -- unbounded variables risk solver issues)

**Rule:** Always set a lower bound. Derive upper bounds from data when possible.

**Common bounds mistakes:**
- Missing lower bound on non-negative quantities leads to unbounded solutions
- Bounds too tight causes artificial infeasibility
- Conflicting bounds (lower > upper) guarantees infeasibility
- Upper bound that is data-dependent but not linked to actual data

### Deriving bounds from data

Use the ATTRIBUTES & STATISTICS section to set meaningful bounds:

| Variable Type | Lower Bound | Upper Bound |
|--------------|-------------|-------------|
| Quantity/Flow | 0 | Use `max` from capacity property, or `None` if uncapped |
| Allocation weight | 0 | 1.0 (or capacity property if available) |
| Binary decision | 0 | 1 (automatic for type="bin") |
| Integer count | 0 | Use entity count or capacity property |

### Variable naming (`name=[]`)

The `name=[]` parameter labels variables in solver output. Use **primitive identity fields** (String, Integer) only — relationship refs cause TyperError. With `Variable.values()` (see below), structured access via back-pointers is preferred for result extraction; `name=[]` remains useful for solver-output labeling and debugging.

```python
# CORRECT — primitive identity fields:
problem.solve_for(Food.x_amount, lower=0, name=["x_amount", Food.name])
problem.solve_for(Edge.x_edge, type="bin", name=["x", Edge.i, Edge.j])

# WRONG — relationship refs (cause TyperError):
problem.solve_for(MachinePeriod.x_maintain, type="bin",
            name=["x_maintain", MachinePeriod.machine])  # machine is a relationship!

# SAFE for cross-product concepts — use just the variable name:
problem.solve_for(MachinePeriod.x_maintain, type="bin", name=["x_maintain"])
```

With `populate=True` (default), results are accessible via `model.select()` which provides entity-aware output regardless of `name=[]`. The preferred approach for result extraction is `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for()`, which provides structured access via back-pointers to the original entity. Use `name=[]` primarily for solver-output labeling and when `populate=False` (scenario/loop workflows).

### Variable bounds from data vs literals

Prefer data-driven bounds over hardcoded literals. Bounds from properties automatically apply per-entity.

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
bin_tl = model.Property(f"departure day {Integer:t} has {Float:bin_tl}")
problem.solve_for(bin_tl(t, y_bin_tl), type="bin", name=["y_bin_tl", t],
            where=[t == departure_days])
```

Use this when no appropriate concept exists as a carrier, or when a variable is purely parametric (indexed only by Integer, String, etc.). See `../examples/multi_concept_union_objective.py`.

### Granularity

Match variable scope to decision scope:
- If you decide **per entity** (how much each site produces), variable lives on that entity
- If you decide **per pair** (how much flows from site A to site B), variable lives on a cross-product or edge concept
- If you decide **per entity per time** (inventory per day), use multiarity properties or cross-product concepts

### Sparse variable creation with `where=[]`

Create variables only where they are meaningful. This reduces problem size and prevents infeasibility from missing data.

```python
# Only create assignment variables for available worker-shift pairs
problem.solve_for(
    Worker.x_assign(Shift, x), type="bin",
    name=["x", Worker.name, Shift.name],
    where=[Worker.available_for(Shift)]
)

# Only create inventory variables for valid time windows per freight group
problem.solve_for(
    FreightGroup.inv(t, x_inv), lower=0,
    name=["x_inv", FreightGroup.name, t],
    where=[t == std.common.range(FreightGroup.inv_start_t, FreightGroup.inv_end_t + 1)]
)

# Scope to a specific factory's products
problem.solve_for(
    Product.quantity, lower=0, upper=Product.demand,
    name=Product.name, where=[Product.factory.name("steel_factory")],
)
```

### Decision variable `x_` prefix convention

Decision variable attributes use `x_` prefix on the concept attribute (`Concept.x_prop`) to distinguish solver-controlled quantities from fixed data.

**V1 Madlib syntax — TYPE FIRST, then colon, then field name:**
```python
# CORRECT v1 syntax — Type object first, field name as format spec:
Food.x_amount = model.Property(f"{Food} has {Float:amount}")
Edge.x_flow = model.Property(f"{Edge} has {Float:flow}")

# WRONG — reversed order causes "Invalid format specifier" compile error:
Food.x_amount = model.Property(f"{Food} has {amount:Float}")  # ERROR!
```

The same pattern applies to Relationships (concept type first):
```python
# CORRECT:
Assignment.worker = model.Relationship(f"{Assignment} assigns {Worker:worker}")
# WRONG:
Assignment.worker = model.Relationship(f"{Assignment} assigns {worker:Worker}")  # ERROR!
```

**Property names must be valid Python identifiers** — no spaces, no special characters:
```python
# CORRECT:
AdPlacement.min_budget = model.Property(f"{AdPlacement} has {Float:min_budget}")
# WRONG — spaces in names cause syntax errors:
AdPlacement.min budget = model.Property(...)  # ERROR!
```

When accessing decision variables through `.ref()` aliases, use the Python attribute name (with `x_` prefix), not the semantic slot name. The solver resolves variables by attribute name:

```python
OpRef = Operation.ref()
sum(OpRef.x_flow)      # Correct -- Python attribute name
sum(OpRef.flow)        # Wrong -- semantic slot name, solver can't resolve
```

### Naming conventions

Variable names are lists of components that produce readable solver output. Use a descriptive prefix (`"qty_"`, `"sel_"`, `"x_"`, `"inv_"`) so post-solve DataFrames can be filtered by `name.str.startswith("prefix")`.

`name=[]` parts must be single-hop only (`Concept.property`). Multi-hop chains (`Concept.rel.property`) fail at solve time because `Column._compile_lookup` cannot resolve relationship traversals. Use the concept's own identifier property or the relationship directly (e.g., `PlacementSegment.placement` not `PlacementSegment.placement.pid`).

```python
# Single-index: property name as identifier
problem.solve_for(Food.amount, name=Food.name, lower=0)

# Multi-index: prefix + identifiers
problem.solve_for(Edge.flow, name=["x", Edge.i, Edge.j], lower=0, upper=Edge.cap)
problem.solve_for(FreightGroup.inv(t, x_inv), name=["x_inv", FreightGroup.name, t])

# Named constraints and objectives
problem.satisfy(fix_node, name="fix0")
problem.satisfy(diff_colors, name=["diff", Edge.i, Edge.j])
problem.minimize(chromatic_number, name="chromatic_number")
```

### Self-check: variables

- Every variable has a type (cont/int/bin) matching the decision
- Every variable has a lower bound (at minimum 0 for physical quantities)
- Upper bounds are derived from data or capacity, not arbitrary large numbers
- Every variable is used in at least one constraint or the objective
- Variable property is declared as `float` even for integer/binary (solver enforces integrality)

### Variable suggestion response patterns

**Natural language in user-facing fields:** The `rationale` and `business_mapping` fields are shown directly to the user. Write them in domain language, not technical references. For example:
- **rationale:** "Determines how many units to ship along each route, balancing cost against demand" (not "Continuous variable on Operation concept for flow optimization")
- **business_mapping:** "Quantity shipped per transportation route" (not "Operation.x_flow continuous variable")

**existing pattern** (variable on existing concept):
```json
{
  "name": "quantity",
  "scope": "Entity",
  "type": "cont",
  "lower": "0",
  "upper": "None",
  "pattern": "existing",
  "property_definition": "USE_EXISTING",
  "solver_registration": "problem.solve_for(Entity.x_quantity, name=['qty', Entity.name], lower=0, type='cont')",
  "rationale": "Determines how many units to allocate per entity, letting the optimizer balance cost and coverage",
  "business_mapping": "Quantity allocated per entity",
  "parameters": []
}
```

**extended_concept pattern** (cross-product decision entity):
```json
{
  "name": "active",
  "scope": "Decision",
  "type": "bin",
  "lower": "0",
  "upper": "1",
  "pattern": "extended_concept",
  "concept_definition": "Decision = model.Concept('Decision')\nDecision.source = model.Relationship(f'{Decision} from {ConceptA:source}')\nDecision.target = model.Relationship(f'{Decision} to {ConceptB:target}')\nDecision.x_active = model.Property(f'{Decision} is {Float:active}')",
  "property_definition": "Decision.x_active = model.Property(f'{Decision} is {Float:active}')",
  "entity_creation": "model.define(Decision.new(source=ConceptA, target=ConceptB))",
  "solver_registration": "problem.solve_for(Decision.x_active, type='bin', name=['active', Decision.source.id, Decision.target.id])",
  "rationale": "Decides whether each source-target pairing is active, enabling the optimizer to select the best combinations",
  "business_mapping": "Whether each source-target pairing is selected",
  "parameters": []
}
```

Note: In `concept_definition` and `property_definition`, use v1 madlib syntax — TYPE FIRST: `f"{Concept} has {Float:field}"`. Reversed `{field:Float}` causes "Invalid format specifier" errors.

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

`.ref()` creates an alias so you can reference two distinct instances of the same concept. Walrus `:=` binds a ref inline.

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
model.where(Node.v(0)).require(Node.color == 1)                      # Fix node 0 to color 1
model.where(Player.assign(0, x)).require(x == Player.p // group_size) # Fix week 0 assignment
model.require(Node.u == 1).where(Node.v(1))                          # Fix TSP ordering u[1] = 1
```

### Conditional fixing from data

```python
problem.satisfy(model.require(x == fixed.fix).where(cell(fixed.i, fixed.j, x)))  # Sudoku known cells
problem.satisfy(model.require(x_inv == 0).where(FreightGroup.inv(FreightGroup.inv_end_t, x_inv)))  # End inventory
problem.satisfy(model.require(x_inv == FreightGroup.inv_start).where(
    FreightGroup.inv(FreightGroup.inv_start_t, x_inv)
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

### Config-driven parameterization and constraint tiers

Externalize business thresholds (budgets, tolerances, minimum shares) as parameters rather than hardcoding in constraints. For debugging infeasible models, organize constraints into two tiers:

- **Essential**: Core physics/accounting constraints (balance, capacity, non-negativity)
- **Full**: Business rules (tolerance bands, fair-share, service levels)

Start with essential constraints only. If feasible, add full constraints incrementally to identify which business rule causes infeasibility.

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

# Constraint with .per(Scenario)
model.where(Route.x_flow(Scenario, x_flow)).require(
    sum(x_flow * Route.cost).per(Scenario) <= Scenario.budget
)

# solve_for with Scenario binding
problem.solve_for(Route.x_flow(Scenario, x_flow), name=[Scenario.name, Route.origin, Route.dest])
```

**Key rules:**
- Variable Property uses `f"{Entity} in {Scenario} is {Float:var}"` pattern
- All constraints/objectives that reference the variable must bind Scenario via `model.where(Entity.x_var(Scenario, ref))`
- Use `.per(Scenario)` for aggregations that should be per-scenario
- Reference `Scenario.param` instead of literal values in constraints
- `name=[]` in solve_for should include `Scenario.name` for labeling
- Single solve — no loop needed

**Scenario types:**

| Type | What varies | Example |
|------|------------|---------|
| **Parameter sweep** | One parameter across a range | Budget: $1M, $2M, $5M |
| **What-if** | A specific assumption changes | "What if demand increases 20%?" |
| **Objective trade-off** | Weights between competing goals | Cost-focused vs coverage-focused |
| **Multi-parameter** | Two+ parameters varied simultaneously | Budget × demand multiplier matrix |

**Why prefer Scenario Concept when possible:** Results are incorporated into the ontology — queryable via `model.select()` like any other property, composable with other model queries, and available for downstream derived properties. Loop results live outside the model in Python DataFrames. Use Loop only when the problem *structure* changes between scenarios (entities added/removed, constraint graph differs).

See `rai-prescriptive-solver-management/examples/scenario_concept_parameter_sweep.py`, `scenario_concept_bound_scaling.py`, `scenario_concept_milp.py`.

### Loop + where= filter — entity exclusion and partitioned sub-problems

When excluding entities or solving independent partitions:

```python
for excluded in [None, "SupplierC", "SupplierB"]:
    problem = Problem(model, Float)
    if excluded:
        problem.solve_for(Order.x_qty, where=[Order.supplier.name != excluded], populate=False)
    else:
        problem.solve_for(Order.x_qty, populate=False)
    problem.maximize(sum(Order.x_qty * Order.profit))
    problem.solve("highs", time_limit_sec=60)
```

Key flags: `where=[]` scopes variables; `populate=False` prevents cross-iteration contamination.

**Partitioned sub-problems** (independent groups like factories with separate products):

```python
for factory_name in factory_names:
    this_product = Product.factory.name(factory_name)
    problem = Problem(model, Float)
    problem.solve_for(Product.x_quantity, lower=0, upper=Product.demand,
                name=Product.name, where=[this_product], populate=False)
    problem.maximize(sum(Product.profit * Product.x_quantity).where(this_product))
    problem.solve("highs", time_limit_sec=60)
```

See `rai-prescriptive-solver-management/examples/partitioned_iteration_scenarios.py`.

---
