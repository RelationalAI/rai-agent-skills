<!-- TOC -->
- [Objective Principles](#objective-principles)
  - [Goal alignment](#goal-alignment)
  - [Avoiding trivial solutions](#avoiding-trivial-solutions)
  - [Multi-objective handling](#multi-objective-handling)
  - [Common objective misalignments](#common-objective-misalignments)
  - [Single-component objectives](#single-component-objectives)
  - [Multi-component objectives with addition](#multi-component-objectives-with-addition)
  - [Penalty terms for soft constraints](#penalty-terms-for-soft-constraints)
  - [Common objective patterns](#common-objective-patterns)
  - [Objective coefficient scaling](#objective-coefficient-scaling)
  - [Self-check: objectives](#self-check-objectives)
<!-- /TOC -->

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

Zero test and forcing patterns: [constraint-formulation.md](constraint-formulation.md) > Forcing constraints.

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

### Multi-component objectives with addition

Aggregate each component separately, then add the totals, not `sum(model.union(...))`: a union counts equal decision values once in PyRel while the solver counts every term. Default each potentially empty total with `| 0.0` (relationalai>=1.13.0; `| 0` in an `Integer` problem); one missing total drops the whole objective.

```python
total_inv_cost = inv_cost * sum(ResourceGroup, t, x_inv).where(
    ResourceGroup.inv(t, x_inv), t > ResourceGroup.inv_start_t)
total_fast_cost = fast_fixed_cost * sum(t, y_bin_fast).where(bin_fast(t, y_bin_fast))
total_ltl_rem_cost = LTLSegment.cost * sum(t, x_rem_ltl).per(LTLSegment).where(
    LTLSegment.rem_ltl(t, x_rem_ltl)
)

total_cost = ((total_inv_cost | 0.0) + (total_fast_cost | 0.0)
              + (sum(LTLSegment, total_ltl_rem_cost) | 0.0))
problem.minimize(total_cost)
```

Sums over bare refs name every identifying entity (`ResourceGroup, t`); a property expression such as `sum(Route.cost * Route.x_flow)` already carries its key. The outer sum names the inner group key (`LTLSegment`). Full rule, including per-entity defaults inside an aggregate: [known-limitations.md](known-limitations.md) § Decision-variable aggregate agreement.

### Penalty terms for soft constraints

Convert a soft constraint into a penalty variable added to the objective.

```python
# Shortfall variable for unmet demand
Order.shortfall = model.Property(f"{Order} has {Float:shortfall}")
problem.solve_for(Order.shortfall, lower=0, name=["slack", Order.id])

# Link shortfall to demand satisfaction
problem.satisfy(model.require(Order.fulfilled + Order.shortfall == Order.demand))

# Penalize shortfall in objective
penalty_weight = 1000  # above the cost of serving one more unit; see Slack penalty weight
total_cost = ((sum(Route.cost * Route.flow) | 0.0)
              + penalty_weight * (sum(Order.shortfall) | 0.0))
problem.minimize(total_cost)
```

### Common objective patterns

| Pattern | Business description | Expression | Key check |
|---------|---------------------|------------|-----------|
| Cost minimization | Minimize total operating cost | `sum(Item.unit_cost * Item.quantity)` | All cost coefficients positive, variables bounded |
| Profit maximization | Maximize total profit across all products | `(sum(Item.revenue * Item.qty) \| 0.0) - (sum(Item.cost * Item.qty) \| 0.0)` | No double-counting of costs |
| Penalty-based | Minimize cost while penalizing unmet demand | `primary_cost + penalty * violations` | Penalty large enough to discourage violations |
| Makespan minimization | Finish all tasks as early as possible | `minimize(max(completion_time))` | Linearize with auxiliary variable if needed |

### Objective coefficient scaling

When combining terms with very different magnitudes, scale coefficients so no single term dominates numerically: if cost totals 10000 and time totals 100, weight time by 100x.

**Slack penalty weight** is the exception. When unmet demand is only a feasibility fallback, the per-unit penalty must exceed the most that serving one more unit adds to the objective, or the solver leaves that unit unmet. That amount covers every per-unit cost on the unit's path, any fixed charge spread over the units the charge enables, and, where capacity is shared, the cost of rerouting the flow the unit displaces. Set the penalty well above that amount (e.g. 10x), not `1/total_demand` or `mean(cost)`, and within a factor of ~1e6 of the other coefficients.

If you cannot bound that amount, or shortfall must be minimized regardless of cost, minimize shortfall first and cost second (Hierarchical/Lexicographic under Multi-objective handling). If a shortfall has a real per-unit cost (lost margin, a contract penalty), use that cost as the penalty.

| Parameter Type | How to Derive Default |
|---------------|----------------------|
| Penalty weight for slack | Above the cost of serving one more unit, rerouting and fixed charges included, with a wide margin (e.g. 10x), or the real shortfall cost |
| Multi-term weights | Scale so terms are comparable (divide by total or mean) |
| Big-M values | Use max from relevant capacity attribute + buffer |
| Normalization | Divide by total or count to get per-unit values |

### Self-check: objectives

- Objective references at least one registered decision variable
- Objective is bounded (minimize has a lower bound, maximize has an upper bound)
- Objective is non-trivial (cannot be driven to zero without meaningful solution)
- Units and scales are consistent across combined terms
- Direction (min/max) matches the business goal

---
