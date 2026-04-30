<!-- TOC -->
- [Objective Context Integration](#objective-context-integration)
- [Objective Principles](#objective-principles)
  - [Goal alignment](#goal-alignment)
  - [Avoiding trivial solutions](#avoiding-trivial-solutions)
  - [Objectives use existing model + defined variables](#objectives-use-existing-model--defined-variables)
  - [Multi-objective handling](#multi-objective-handling)
  - [Common objective misalignments](#common-objective-misalignments)
  - [Single-component objectives](#single-component-objectives)
  - [Multi-component objectives with model.union()](#multi-component-objectives-with-modelunion)
  - [Penalty terms for soft constraints](#penalty-terms-for-soft-constraints)
  - [Common objective patterns](#common-objective-patterns)
  - [Objective coefficient scaling](#objective-coefficient-scaling)
  - [Self-check: objectives](#self-check-objectives)
<!-- /TOC -->

## Objective Context Integration

**Natural language rule:** When describing objectives to the user (in `description`, `rationale`, and suggestion text), frame them as business goals, not technical expressions:
- "Minimize total transportation and handling cost across all routes" (not "minimize sum(Operation.cost_per_unit * Operation.x_flow)")
- "Maximize total profit from product sales" (not "maximize sum(Product.price * Product.x_quantity)")
- "Minimize unmet customer demand, penalizing shortfalls heavily" (not "minimize sum(UnmetDemand.x_slack) * PENALTY")

**Your suggestions should be inspired by BOTH the base model structure AND any user inputs.**

**1. Start with the Base Model:**
- Examine what metrics the model naturally supports (costs, quantities, revenues)
- Identify properties that represent values to optimize (cost, profit, quantity, efficiency)
- Consider typical objectives for this type of optimization problem

**2. Layer in User Goals (if provided):**
If the user provided how they measure success (look for HOW USER MEASURES SUCCESS section):
- Parse their input to understand what they want to optimize
- Identify specific metrics or values they mentioned
- Align the objective with both model capabilities AND user's stated goal

**3. Decision Criteria for Objective Selection:**
- User mentions cost, expense, waste, or risk -- minimize
- User mentions revenue, coverage, throughput, or profit -- maximize
- User's metric matches an existing model property -- use that property directly
- User's metric requires computation across properties -- note the model_gap
- No user input -- suggest the natural objective for the problem type (e.g., minimize cost for allocation, maximize coverage for selection)

---

## Objective Principles

### Goal alignment

The objective must reflect the actual business/operational goal. Test: "If this number improves, does the solution actually get better?"

**Minimize** (reduce something undesirable): cost, waste, unmet demand, risk, delay, violations.
**Maximize** (increase something desirable): revenue, profit, throughput, coverage, utilization, service level.

### Avoiding trivial solutions

A trivial solution means the solver found a "cheat" — typically all zeros or all at bounds.

**Common causes and fixes:**
- Minimizing with non-negative coefficients and no forcing constraint → add demand satisfaction or minimum coverage
- Slack variables without equality linking → use `slack == demand - actual_flow`, not `slack >= 0`
- Maximize with no upper bound → add capacity constraints
- Join paths matching zero entities → verify `.where()` paths connect to actual data

Before suggesting a MINIMIZE objective with non-negative cost coefficients, apply the zero test: "If all decision variables = 0, are all constraints satisfied?" If yes, add a forcing constraint.

**In your rationale**, state which constraint forces the solver to take action (e.g., "demand satisfaction constraint prevents trivial zero solution").

### Objectives use existing model + defined variables

Objectives should ONLY reference:
1. Properties from the BASE MODEL (shown in AVAILABLE CONCEPTS AND PROPERTIES)
2. Decision variables that have been DEFINED (shown in DEFINED VARIABLES)
3. Cross-product concepts created by variables (shown in variable context with concept_definition)

If a needed property doesn't exist, report it as a model_gap so enrichment can add it.

**Check property types before using as weights or coefficients.** Look up each property in ATTRIBUTE TYPES BY CONCEPT. Only use numeric properties (`Float`, `Integer`, rai_type `:float`/`:int`) in arithmetic expressions. String properties (rai_type `:str`) — including names like `criticality`, `priority`, `risk_level` that may sound numeric but contain text values like 'High', 'Critical' — can only be used in equality filters (`.where()`), not as multipliers or coefficients. If a numeric version of a string property is needed for weighting, report as a model_gap requiring enrichment (string-to-numeric mapping).

### Multi-objective handling

Only one `problem.minimize()` or `problem.maximize()` per problem. For multiple goals:

| Approach | Description | When to Use |
|----------|-------------|-------------|
| **Weighted sum** | `w1*obj1 + w2*obj2` | Goals on comparable scales |
| **Primary + threshold** | Optimize main goal; constrain secondary to a minimum | Clear priority between goals |
| **Penalty-based** | Add soft constraint penalties to main objective | Some goals are "nice to have" |

**Hierarchical/Lexicographic:** Optimize obj1 first, then obj2 within optimal obj1. Use when there is clear priority and the higher priority must not be compromised.

**Important:** When using multipliers to express priority (e.g., `w1 * Obj1 + Obj2` where `w1 >> 1`), assess whether the multiplier creates a range where the lower-priority term has no influence on the solution. 100x between similar-scale objectives is typically fine; flag when the combined range pushes the secondary term below solver tolerance influence.

### Bi-objective: Epsilon Constraint via Loop

When two objectives are genuinely competing (improving one worsens the other), the epsilon constraint method traces the full tradeoff frontier. Pick one as primary (optimize it), convert the other to a parameterized constraint, and sweep across the feasible range in a loop.

Uses the same Loop + `populate=False` pattern as scenario analysis Pattern 2. For approach selection, direction handling, anchor solves, epsilon spacing, and pitfalls, see [multi-objective-formulation.md](multi-objective-formulation.md).

### Common objective misalignments

Before finalizing the objective, check for these misalignments:
- Goal is "minimize cost" but objective minimizes quantity (wrong measure)
- Goal is "balance workload" but objective minimizes total work (not balance)
- Goal is "maximize coverage" but objective maximizes profit (different goal)

### Single-component objectives

```python
problem.minimize(sum(Food.cost * Food.amount))           # Minimize total cost
problem.maximize(sum(Edge.flow).where(Edge.i(1)))         # Maximize total flow
problem.minimize(max(Node.color), name="chromatic_number") # Minimize max (min-max)

# Quadratic objective (portfolio risk)
c = Float.ref()
risk = sum(c * Stock.quantity * Stock2.quantity).where(Stock.covar(Stock2, c))
problem.minimize(risk)
```

### Multi-component objectives with `model.union()`

Combine terms from different scopes using `model.union()`, then wrap in `sum()`.

```python
total_inv_cost = inv_cost * sum(x_inv).where(ResourceGroup.inv(t, x_inv), t > ResourceGroup.inv_start_t)
total_fast_cost = fast_fixed_cost * sum(y_bin_fast).where(bin_fast(Integer.ref(), y_bin_fast))
total_ltl_rem_cost = LTLSegment.cost * sum(x_rem_ltl).per(LTLSegment).where(
    LTLSegment.rem_ltl(Integer.ref(), x_rem_ltl)
)

total_cost = sum(model.union(total_inv_cost, total_fast_cost, total_ltl_rem_cost))
problem.minimize(total_cost)
```

**Why `model.union()`:** Each term may involve different concepts and scopes. `model.union()` collects them into a single summable set.

**ANTI-PATTERN WARNING: Scalar sums inside `model.union()`**

Each branch of `model.union()` must be a **per-entity expression** (bound to a concept), NOT a fully-aggregated scalar. Wrapping `sum()` around a branch collapses it to a scalar, which causes `AssertionError: Union outputs must be Vars`.

```python
# CORRECT: per-entity expressions inside union, outer sum() aggregates
total_cost = sum(model.union(
    Entity1.cost * Entity1.x_var,            # per-Entity1
    Entity2.cost * Entity2.x_var,            # per-Entity2
))

# WRONG: scalar sums inside union -- causes AssertionError: Union outputs must be Vars
total_cost = sum(model.union(
    sum(Entity1.cost * Entity1.x_var),       # scalar -- BREAKS
    sum(Entity2.cost * Entity2.x_var),       # scalar -- BREAKS
))
```

Keep costs at concept level inside `model.union()` and let the outer `sum()` handle aggregation. For time-indexed or grouped variables, use `sum(var).per(Concept).where(...)` to aggregate over one dimension while keeping the per-entity binding.

### Penalty terms for soft constraints

Convert a soft constraint into a penalty variable added to the objective.

```python
# Shortfall variable for unmet demand
Order.shortfall = model.Property(f"{Order} has {Float:shortfall}")
problem.solve_for(Order.shortfall, lower=0, name=["slack", Order.id])

# Link shortfall to demand satisfaction
problem.satisfy(model.require(Order.fulfilled + Order.shortfall == Order.demand))

# Penalize shortfall in objective
penalty_weight = 1000
total_cost = sum(model.union(
    sum(Route.cost * Route.flow),
    penalty_weight * sum(Order.shortfall)
))
problem.minimize(total_cost)
```

### Common objective patterns

| Pattern | Business description | Expression | Key check |
|---------|---------------------|------------|-----------|
| Cost minimization | Minimize total operating cost | `sum(unit_cost * quantity)` | All cost coefficients positive, variables bounded |
| Profit maximization | Maximize total profit across all products | `sum(revenue * qty) - sum(cost * qty)` | No double-counting of costs |
| Penalty-based | Minimize cost while penalizing unmet demand | `primary_cost + penalty * violations` | Penalty large enough to discourage violations |
| Makespan minimization | Finish all tasks as early as possible | `minimize(max(completion_time))` | Linearize with auxiliary variable if needed |

### Objective coefficient scaling

When combining terms with very different magnitudes, scale coefficients so no single term dominates numerically. This improves solver numerical stability.

**Multi-term scaling:** Normalize objective terms to similar magnitude using data statistics. If combining cost (total=10000) and time (total=100), weight time by 100x to balance influence.

**Penalty weight derivation:** Use max or mean of the penalized quantity. For unmet-demand penalties, use `penalty = mean(cost)` so violating demand costs roughly the same as one unit of shipping cost.

**Deriving defaults from data:**

| Parameter Type | How to Derive Default |
|---------------|----------------------|
| Penalty weight for slack | Use 1/total_demand or small fraction to avoid dominating objective |
| Multi-term weights | Scale so terms are comparable (divide by total or mean) |
| Big-M values | Use max from relevant capacity attribute + buffer |
| Normalization | Divide by total or count to get per-unit values |

**Always inspect data ranges before setting coefficients.** A penalty of 1000 means nothing without knowing that the quantities it penalizes range from 0-50 (huge penalty) vs 0-1000000 (negligible penalty).

### Self-check: objectives

- Objective references at least one registered decision variable
- Objective is bounded (minimize has a lower bound, maximize has an upper bound)
- Objective is non-trivial (cannot be driven to zero without meaningful solution)
- Units and scales are consistent across combined terms
- Direction (min/max) matches the business goal

---
