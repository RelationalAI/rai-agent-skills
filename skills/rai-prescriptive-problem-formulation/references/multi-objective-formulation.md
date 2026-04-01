# Multi-Objective Formulation (Bi-Objective via Epsilon Constraint)

<!-- TOC -->
- [Approach Selection](#approach-selection)
- [Recognizing Competing Objectives (Tension Heuristics)](#recognizing-competing-objectives-tension-heuristics)
- [Two Entry Points (Before/After Code)](#two-entry-points-beforeafter-code)
  - [Entry 1: Constraint to Epsilon Sweep](#entry-1-constraint-to-epsilon-sweep)
  - [Entry 2: Bundled Penalty to Unbundle](#entry-2-bundled-penalty-to-unbundle)
- [Epsilon Constraint Method](#epsilon-constraint-method)
  - [Anchor Solves](#anchor-solves)
  - [Loop Pattern](#loop-pattern)
  - [Direction Handling](#direction-handling)
  - [Epsilon Spacing](#epsilon-spacing)
- [Evaluating the Secondary Objective](#evaluating-the-secondary-objective)
- [Combining with Scenario Concept](#combining-with-scenario-concept)
- [Storing Results](#storing-results)
- [Pitfalls](#pitfalls)
- [References](#references)
<!-- /TOC -->

How to formulate problems with two competing objectives. Produces a Pareto frontier
showing the tradeoff between them.

## Approach Selection

Match the problem structure to the right method:

| Situation | Method | Why |
|-----------|--------|-----|
| Two goals in tension, user wants to see the tradeoff | Epsilon constraint loop | Produces Pareto frontier showing the full tradeoff curve |
| Secondary objective has a known acceptable bound | Primary + threshold (existing) | No need to explore — bound is fixed |
| User provides explicit weights for combining objectives | Weighted sum (existing) | Single-objective with weighted combination |

## Recognizing Competing Objectives (Tension Heuristics)

Not domain-specific. General patterns where objectives compete:

- Cost vs performance/quality/coverage -- improving one worsens the other given same constraints
- Risk vs return -- classic competing pair
- Speed/throughput vs fairness/balance
- Quantity vs quality

**Test**: if improving objective A naturally worsens B under the same constraints, they are in tension.
If both can improve simultaneously, they are not competing -- combine into a single objective.

## Two Entry Points (Before/After Code)

### Entry 1: Constraint to Epsilon Sweep

When the secondary objective is currently modeled as a constraint with a fixed bound.

```python
# BEFORE (single-objective): return is a fixed constraint
p.satisfy(model.require(sum(Stock.returns * x_qty).per(Scenario) >= min_return))
p.minimize(risk_expr)

# AFTER (bi-objective): return target becomes the loop parameter
for rate in epsilon_rates:
    p = Problem(model, Float)
    p.solve_for(..., populate=False)
    p.satisfy(model.require(sum(Stock.returns * x_qty).per(Scenario) >= rate * Scenario.budget))
    p.minimize(risk_expr)
    p.solve(...)
```

### Entry 2: Bundled Penalty to Unbundle

When two concerns are combined via penalty weight in a single objective.

```python
# BEFORE (single-objective): cost + penalty bundled
PENALTY = 10000
p.minimize(sum(Route.cost * Route.x_flow) + PENALTY * sum(Demand.x_unmet))

# AFTER (bi-objective): split into primary objective + epsilon constraint
for eps in epsilon_values:
    p = Problem(model, Float)
    p.solve_for(..., populate=False)
    p.satisfy(model.require(sum(Demand.x_unmet) <= eps))  # secondary as constraint
    p.minimize(sum(Route.cost * Route.x_flow))              # primary only
    p.solve(...)
```

## Epsilon Constraint Method

### Anchor Solves

Two independent single-objective solves to find the feasible range of the secondary objective:

1. Optimize primary only -- get secondary value at that solution (one bound of the range)
2. Optimize secondary only -- get the other extreme

Without anchors, epsilon values may be non-binding (wasted solves) or infeasible.

### Loop Pattern

```python
pareto = []
consecutive_infeasible = 0
for eps in epsilon_values:
    p = Problem(model, Float)
    p.solve_for(..., populate=False)      # fresh Problem each iteration
    p.satisfy(original_constraints)
    p.satisfy(model.require(secondary >= eps))   # epsilon constraint
    p.minimize(primary_objective)
    p.solve(solver, time_limit_sec=60)

    si = p.solve_info()
    if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"):
        consecutive_infeasible += 1
        if consecutive_infeasible >= 2:
            break  # two consecutive infeasible — past feasible range
        continue  # skip this point but try the next (non-convex gaps)
    consecutive_infeasible = 0

    pareto.append({
        "eps": eps,
        "primary": si.objective_value,
        "variables": p.variable_values().to_df(),
    })
```

Same infrastructure as the Loop + `populate=False` pattern from [scenario-analysis.md](scenario-analysis.md) Pattern 2.

### Direction Handling

| Primary direction | Secondary direction | Epsilon constraint |
|---|---|---|
| minimize | maximize | secondary >= eps |
| minimize | minimize | secondary <= eps |
| maximize | maximize | secondary >= eps |
| maximize | minimize | secondary <= eps |

### Epsilon Spacing

Default: 5 interior points + 2 anchors = 7 total Pareto points. Enough to identify the knee
and tradeoff shape.

```python
n_interior = 5
epsilon_values = [
    secondary_min + i * (secondary_max - secondary_min) / (n_interior + 1)
    for i in range(1, n_interior + 1)
]
```

## Evaluating the Secondary Objective

The solver only reports the primary (optimized) objective value. To get both objectives at each
Pareto point, evaluate the secondary expression on the `variable_values` DataFrame:

```python
import builtins  # RAI `sum` shadows Python's built-in

def evaluate_secondary(var_df, entity_data):
    """Compute secondary objective from variable values and entity coefficients.

    entity_data maps variable names (as they appear in var_df) to the secondary
    objective coefficient for that variable. Build this BEFORE the loop from model data.
    """
    total = 0.0
    for _, row in var_df.iterrows():
        name, val = str(row.iloc[0]), float(row.iloc[1])
        if name not in entity_data:
            raise KeyError(f"Variable '{name}' not found in entity_data — "
                           "check that name= pattern in solve_for matches the keys")
        total += entity_data[name] * val
    return total
```

**Building `entity_data`**: Variable names follow the `name=` pattern from `solve_for()`.
If `name=["qty", Scenario.name, Stock.index]`, variable names are `"qty_budget_500_1"`,
`"qty_budget_500_2"`, etc. Build the mapping to match:

```python
# Build entity_data keyed by the same name pattern used in solve_for
stock_df = model.select(Stock.index, Stock.returns).to_df()
stock_returns = dict(zip(stock_df["index"], stock_df["returns"]))

# For scenario-indexed variables, build per-scenario mappings
entity_data = {}
for scenario_name in ["budget_500", "budget_1000", "budget_2000"]:
    for idx, ret in stock_returns.items():
        entity_data[f"qty_{scenario_name}_{idx}"] = ret
```

**Pitfall**: `from relationalai.semantics import sum` shadows Python's built-in `sum`.
Use `builtins.sum` for Python-side aggregation over DataFrames.

## Combining with Scenario Concept

If the user also has parameter variations (different budgets, demand levels), Scenario Concept
can be used INSIDE the epsilon loop:

```python
for eps in epsilon_values:
    p = Problem(model, Float)
    # Scenario Concept handles parameter variations -- one solve, all scenarios
    p.solve_for(Entity.x_var(Scenario, x), ..., populate=False)
    p.satisfy(model.require(secondary >= eps).per(Scenario))
    p.minimize(primary_objective)  # aggregated across scenarios
    p.solve(...)
    # all scenarios solved at this epsilon level
```

N epsilon solves (not N x M). This is optional -- multi-objective does not require scenarios.

## Storing Results

**Phase 1 — Explore the frontier** using `populate=False` (results in Python DataFrames):

```python
pareto_points = []
for eps in epsilon_values:
    ...
    pareto_points.append({
        "eps": eps,
        "primary": si.objective_value,
        "secondary": evaluate_secondary(df, ...),
        "variables": p.variable_values().to_df(),
    })
```

**Phase 2 — Populate the chosen operating point** back into the ontology with `populate=True`:

```python
# User selects an operating point (e.g., the knee)
chosen_eps = pareto_points[knee_idx]["eps"]

# Re-solve with populate=True — results written to model properties
p_final = Problem(model, Float)
p_final.solve_for(Entity.x_var, populate=True)  # writes back to ontology
p_final.satisfy(original_constraints)
p_final.satisfy(model.require(secondary >= chosen_eps))
p_final.minimize(primary)
p_final.solve(solver, time_limit_sec=60)

# Results now queryable via model.select(), composable with other model queries
model.select(Entity.id, Entity.x_var).where(Entity.x_var > 0.001).inspect()
```

This two-phase approach uses the loop for frontier exploration (robust, handles infeasibility) and a final populate solve to bring the selected solution into the ontology for downstream queries and derived properties.

## Pitfalls

| Pitfall | Cause | Fix |
|---------|-------|-----|
| Non-binding epsilon (wasted solves) | Epsilon range starts below anchor 1's secondary value | Always derive range from anchor solutions |
| All points same primary value | Objectives not in tension | Verify tension heuristic; may just need single objective |
| Infeasible at first epsilon point | Range too aggressive | Widen range or add slack |
| `builtins.sum` vs RAI `sum` | `from relationalai.semantics import sum` shadows built-in | Use `builtins.sum` for Python-side aggregation |
| `Float.ref()` -- safe to reuse | Declared once, used across loop iterations | Works correctly; no need to recreate per iteration |
| Scale mismatch between objectives | Very different magnitudes | Normalize epsilon range; consider rates (per unit) rather than absolutes |

## References

- Epsilon loop pattern: same as Loop + `populate=False` in [scenario-analysis.md](scenario-analysis.md) Pattern 2
- Formulation example: [portfolio_risk_return.py](../examples/portfolio_risk_return.py) -- epsilon loop + Scenario Concept, QP
- Results analysis: see `rai-prescriptive-results-interpretation` > Pareto Frontier / Efficient Frontier Results
