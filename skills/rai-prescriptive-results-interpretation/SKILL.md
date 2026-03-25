---
name: rai-prescriptive-results-interpretation
description: Interprets optimization solver output including solution extraction, status codes, quality assessment, result explanation, and sensitivity analysis. Use when analyzing solve results or communicating optimization outcomes.
---

# Solution Interpretation
<!-- v1-STABLE -->

## Summary

**What:** Post-solve activities — solution extraction, status interpretation, quality assessment, result explanation, and sensitivity analysis.

**When to use:**
- Extracting solution values after a successful solve
- Interpreting solver status (OPTIMAL, INFEASIBLE, DUAL_INFEASIBLE, TIME_LIMIT)
- Assessing whether an "optimal" solution is actually meaningful (trivial solution detection)
- Explaining results to stakeholders in business language
- Running sensitivity / what-if analysis
- Diagnosing why a solution looks wrong (all zeros, all at bounds, concentrated on one entity)

**When NOT to use:**
- Formulation patterns (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Solver configuration and execution — see `rai-prescriptive-solver-management`
- Query syntax (select, aggregation, joins) — see `rai-querying`

**Overview:**
1. Check termination status
2. Extract solution values (query decision variable properties)
3. Assess solution quality (trivial solution detection, reasonableness checks)
4. Explain results to stakeholders (what was decided, why, business impact)
5. Run sensitivity analysis (parameter sweeps, what-if scenarios)

---

## Interpretation Workflow

After a solve completes, interpret results in this order:

1. **Check status** (Status Interpretation) — Is the solve OPTIMAL, INFEASIBLE, DUAL_INFEASIBLE, or TIME_LIMIT?
   - If INFEASIBLE or ERROR: stop, diagnose root cause (Diagnosis Checklist), do not present results
   - If TIME_LIMIT with large gap (>10%): flag uncertainty, consider increasing time or simplifying
2. **Assess quality** (Quality Assessment) — Is the solution meaningful or trivially empty?
   - Check non-zero ratio, objective value plausibility, variable distribution
   - If trivial (all zeros, all at bounds): diagnose and fix before presenting
3. **Extract and filter** — Remove noise from raw solver output
   - Filter near-zero values (< 0.5 for binary, < 1e-6 for continuous)
   - Group by decision concept, map back to business entities
4. **Explain to stakeholders** (Result Explanation Guide) — Translate math to business language
   - Problem context → decisions made → key drivers → quality → business impact → next steps
5. **Explore what-if** (Sensitivity Analysis) — What happens if assumptions change?
   - Identify critical parameters (uncertain, controllable, high-impact)
   - Present as scenario comparison tables

---

## Solution Extraction

After a successful solve, extract results using result attributes and model queries.

### Result Attributes

After `p.solve()`, result attributes are available via two interfaces:

**Engine-side (Relationships)** — usable in `model.require()`, `model.select()`, and solver expressions:

| Method | Return type | Description |
|--------|-------------|-------------|
| `p.termination_status()` | Relationship | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `p.objective_value()` | Relationship | Optimal objective value |
| `p.num_points()` | Relationship | Number of solutions returned |
| `p.error()` | Relationship | Error message tuple (if solve failed) |
| `p.printed_model()` | Relationship | Text representation (with `print_format=`) |
| `p.num_variables()` | Relationship | Total registered variables |
| `p.num_constraints()` | Relationship | Total constraints |
| `p.num_min_objectives()` | Relationship | Number of minimize objectives |
| `p.num_max_objectives()` | Relationship | Number of maximize objectives |

**Python-side (`solve_info()`)** — for formatted output, scenario loops, and Python logic:

| Attribute | Type | Description |
|-----------|------|-------------|
| `si.termination_status` | `str` | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `si.objective_value` | `float` / `int` | Optimal objective value |
| `si.solve_time_sec` | `float` | Wall-clock solve time in seconds |
| `si.num_points` | `int` | Number of solutions returned |
| `si.error` | `tuple` | Error message (if solve failed) |
| `si.solver_version` | `str` | Version of the solver used |
| `si.printed_model` | `str` | Solver model text (if `print_format=` was set) |

```python
p.solve("highs", time_limit_sec=60)

# Engine-side: integrity constraint on status
model.require(p.termination_status() == "OPTIMAL")

# Python-side: formatted output
si = p.solve_info()
si.display()
print("status:", si.termination_status)
print("objective:", si.objective_value)
print("solve time:", si.solve_time_sec, "sec")
print("solutions:", si.num_points)
```

### Querying Solution Values

Where solved values appear depends on the `populate` parameter in `solve_for()`:

| `populate` setting | Where results live | How to access | When to use |
|---|---|---|---|
| `populate=True` (default) | Written back into model properties | `model.select()` queries | Standard single-solve workflows |
| `populate=False` | Solver-level only | `p.variable_values()` | Scenario loops, multi-solve workflows with shared variables |

**Primary approach: `model.select()` with `populate=True` (default, recommended)**

With `populate=True`, solved values are written back into the model as property values. Query them like any other model data — with entity context, aliases, and filtering:

```python
# Display results — .inspect() prints to stdout (preferred for display-only)
model.select(
    MachinePeriod.machine.machine_id.alias("machine_id"),
    MachinePeriod.period.pid.alias("period"),
    MachinePeriod.x_maintain.alias("maintained"),
).where(MachinePeriod.x_maintain > 0.5).inspect()

# Use .to_df() when you need the DataFrame for further Python analysis
assignments_df = model.select(
    TechnicianMachinePeriod.technician.technician_id.alias("technician"),
    TechnicianMachinePeriod.machine.machine_id.alias("machine"),
    TechnicianMachinePeriod.period.pid.alias("period"),
).where(TechnicianMachinePeriod.x_assigned > 0.5).to_df()

# Binary variable selection — filter active decisions
model.select(
    Edge.i.alias("from"), Edge.j.alias("to")
).where(Edge.x_edge > 0.5).inspect()
```

**Fallback approach: `p.variable_values()` with `populate=False`**

Use `populate=False` + `variable_values()` only for loop-based entity exclusion/partition scenarios. For Scenario Concept workflows, use `model.select()` — the scenario dimension is part of the variable identity. For loop workflows where multiple Problems share decision variables, `populate=False` prevents one solve from overwriting another's results:

```python
# Must use name=[] for meaningful labels (otherwise all names are "_")
p.solve_for(Worker.x_assign, type="bin", populate=False,
            name=["x_assign", Worker.id])

p.solve("highs")

# Solver-level summary
values_df = p.variable_values().to_df()
# Returns: name | value
#          x_assign_1 | 1.0
#          x_assign_2 | 0.0

# Multiple solutions (e.g., from MiniZinc with solution_limit)
all_df = p.variable_values(multiple=True).to_df()
# Returns: sol_index | name | value (0-based sol_index)
```

**Key rules:**
- Use `model.select()` by default — it gives entity-aware results with proper identity columns
- Use `variable_values()` only for scenario loops or when you need solver-level inspection
- With `variable_values()`, always provide `name=[]` using **primitive identity fields** (String/Integer), never relationship refs
- `name=[]` with relationship refs (e.g., `MachinePeriod.machine`) causes TyperError — use `MachinePeriod.machine.machine_id` or just a string label

**Extraction principles:**
- **Binary variables:** Filter with `> 0.5`, not `== 1` (numeric tolerance in MIP solvers)
- **Continuous variables:** Filter with `> 1e-6` to remove near-zero solver noise
- **Scalar extraction:** `p.solve_info().objective_value` for single values (no query needed)
- **Always alias:** Use `.alias()` on every output column for clean DataFrames

**Int128 handling:** RAI may return integer columns as `Int128Array` (nullable). Cast before pandas operations:
- `var_df["value"] = var_df["value"].astype(float)` before filtering (`> 0.5`, etc.)
- Cast integer columns before `.groupby().agg()` with sum/mean

### Exporting Solution Results to Tables

After extracting solution values, export them to a Snowflake table using `.into().exec()`:

```python
# Export optimal allocations to a results table
results_table = model.Table("DB.SCHEMA.OPTIMIZATION_RESULTS")
model.select(
    Route.origin.name.alias("FROM_SITE"),
    Route.dest.name.alias("TO_SITE"),
    Route.x_flow.alias("OPTIMAL_FLOW"),
).where(Route.x_flow > 1e-6).into(results_table).exec()
```

**Replace vs update:** Use `update=True` to merge into an existing table (e.g., appending scenario results):

```python
results_table = model.Table("DB.SCHEMA.SCENARIO_RESULTS")
model.select(
    Food.name.alias("FOOD"), Food.amount.alias("AMOUNT"),
).into(results_table, update=True).exec()
```

The `.into(table)` call writes query results to the specified Snowflake table. Use `update=True` to merge into an existing table rather than replacing it.

### Multiple Solutions

v1 supports multiple solutions natively:

- **Request multiple solutions:** `p.solve("minizinc", solution_limit=10)` — `solution_limit` is a first-class parameter
- **Check count:** `p.num_points()` (Relationship) or `p.solve_info().num_points` (Python)
- **Extract all solutions:** `p.variable_values(multiple=True).to_df()` returns a DataFrame with `sol_index` (0-based), `name`, `value`
- **Switch active solution:** `p.load_point(index)` loads solution at 0-based index (0 = first, up to `num_points - 1`). After loading, `model.select()` on populated properties reflects the selected solution. `load_point()` can also be used with `populate=False` to manually control when solution values are written to model properties.

```python
# Solve with multiple solutions
p.solve("minizinc", solution_limit=5)
si = p.solve_info()
print(f"Found {si.num_points} solutions")

# View all solutions
all_df = p.variable_values(multiple=True).to_df()

# Switch to solution 2 (0-based) and query
p.load_point(2)
sol2_df = model.select(Food.name, Food.amount).to_df()
```

**How many solutions to request:**

Keep `solution_limit` small (typically 3-10). The primary use case for multiple solutions is enabling human evaluation — like Google Maps showing a few route options — but humans are not effective at comparing hundreds of alternatives. If there is an analytical way to compare solutions, that comparison criterion belongs in the objective function, not in post-hoc filtering of a large solution set.

Requesting very large solution counts (e.g., 100,000) is almost never appropriate. The few specialized cases where large solution sets make sense include running downstream simulations over candidate solutions or feeding alternatives into a separate evaluation pipeline. For standard decision-support problems, a handful of near-optimal alternatives is far more useful than an exhaustive enumeration.

### Iterative solving

Constraints defined over concepts automatically apply to new data added between solves. Pattern:
1. Solve relaxed problem
2. Inspect solution (e.g., find subtours)
3. Add violated constraints as new data
4. Re-solve — existing `p.satisfy()` picks up new data

### Post-solve constraint verification

`p.verify(*fragments)` checks that the solver's solution satisfies constraints post-solve. Particularly useful for exact solvers (HiGHS MIP, MiniZinc). See `rai-prescriptive-solver-management` for full `verify()` documentation and examples.

### Scenario / parametric solving

**Scenario Concept (parameter variations):** Results from a single solve contain a scenario dimension. Query with `model.select(Scenario.name, ...).where(Entity.x_var(Scenario, x_ref), x_ref > threshold)`. Group by `Scenario.name` for comparison tables. Variables are multi-argument Properties indexed by (Entity, Scenario) — the scenario column is part of the variable identity.

**Loop + where= (entity exclusion):** Each iteration produces a separate `variable_values().to_df()`. Collect per-iteration results in a list, label by scenario. Use `populate=False` to prevent cross-iteration contamination.

---

## Status Interpretation

### Optimal
The solver found the best possible solution within its tolerance settings (typically 1e-6 for LP, 0.01% MIP gap for MIP).

**What to tell users:** "We found the best possible plan given your requirements. Here is what it recommends..."
**Next steps:** Proceed to quality assessment, then explain results.

### Infeasible
No solution satisfies all constraints simultaneously. The problem as stated is impossible.

**Diagnosis steps:**
1. Check demand vs. capacity: does total demand exceed total supply/capacity?
2. Look for contradictory constraints (e.g., x >= 10 AND x <= 5).
3. Check bound consistency: any variable with lower_bound > upper_bound?
4. Remove constraints one at a time to isolate the conflict.
5. Use IIS (Irreducible Inconsistent Subsystem) if the solver supports it.

**What to tell users:** "The requirements as stated cannot all be satisfied simultaneously. The most likely conflict is [specific conflict]. Options: relax [constraint], increase [capacity], or allow unmet demand with a penalty."
**Next steps:** Identify the binding conflict, present trade-off options, add slack/penalty variables. A common and valuable path is moving the conflicting hard constraint to the objective with a penalty — feasibility restoration through softening is often more useful than pure diagnosis.

### Unbounded (DUAL_INFEASIBLE)
The objective can improve infinitely — the solver can keep making the solution "better" without limit. The MOI status is `"DUAL_INFEASIBLE"` (not `"UNBOUNDED"`).

**Diagnosis steps:**
1. Check that all variables have appropriate bounds (especially upper bounds for maximize, lower bounds for minimize).
2. Verify budget/capacity/resource constraints are present.
3. Check objective direction: minimizing when should maximize, or vice versa?
4. Check coefficient signs in the objective.

**What to tell users:** "The model is missing limits that would bound the solution. Likely cause: [missing capacity constraint / missing budget limit / wrong objective direction]."
**Next steps:** Add missing bounds or constraints, verify objective direction and coefficient signs.

### Time Limit
The solver found a feasible solution but could not prove it is optimal within the time allowed.

**Gap interpretation:**
- Gap < 1%: Solution is very close to optimal; usually acceptable.
- Gap 1-5%: Solution is good but there may be modest room for improvement.
- Gap > 10%: Solution quality is uncertain; consider increasing time limit or simplifying the model.

**What to tell users:** "The solver found a solution within [X%] of the best possible. [If gap is small: This is likely very close to optimal.] [If gap is large: More time or a simpler model could improve this.]"
**Next steps:** For large gaps, increase time limit, tighten Big-M values, add symmetry-breaking constraints, or simplify the model.

### Status as Signal, Not Always Error

A non-optimal termination status is information about the problem structure, not necessarily a failure to fix.

**INFEASIBLE as diagnostic tool:**
- Intentionally solving with a proposed constraint set to test feasibility boundaries is a valid modeling technique. An infeasible result tells you the constraint set is too tight — which constraints to relax.
- **Constraint relaxation debugging:** Remove constraints one at a time and re-solve. The constraint whose removal makes the problem feasible is the binding conflict. This is faster than manual inspection for large formulations.

**TIME_LIMIT with acceptable gap:**
- A 2% gap after 60 seconds may be perfectly good for operational use. The "optimal" solution is at most 2% better — often indistinguishable in business terms.
- **Rule of thumb:** If the gap is under 5% and the solution values make business sense, present it as "near-optimal" and let the user decide whether to invest more solve time.
- Don't automatically increase time limits — ask: "Is a 2% improvement worth waiting 10 minutes?"

**Reframing for users:**
- Instead of "the solver failed to find an optimal solution," say: "The solver found a solution within X% of the theoretical best. Here's what it tells us about the problem..."
- INFEASIBLE + constraint analysis = "These requirements cannot all be satisfied simultaneously. Which one has the most flexibility?"
- TIME_LIMIT + good gap = "This is a strong solution. More time would give diminishing returns."

**When to iterate vs. accept:**
- **Iterate:** INFEASIBLE with no clear conflict, DUAL_INFEASIBLE, TIME_LIMIT with gap > 10%, trivial solution (all zeros)
- **Accept:** TIME_LIMIT with gap < 5%, OPTIMAL (always), INFEASIBLE when used as intentional feasibility probe

### Error / Unknown
Compilation or solver errors prevented a solution.

**Common causes:** Undefined properties referenced in formulation, type mismatches, syntax errors in expressions, solver license issues.
**What to tell users:** "The model could not be solved due to a technical error: [error message]. This needs to be fixed before we can get results."
**Next steps:** Check compilation output, fix expression syntax, verify all referenced properties exist.

### Re-Solve Behavior (1.0.3+)

Re-solving the same `Problem` instance is safe (replace semantics). See `rai-prescriptive-solver-management` for details.

---

## Solvability Ladder

The solvability ladder defines progressive quality gates for an optimization formulation. Each level subsumes the previous — reaching "non-trivial" means all prior gates also passed. Use this to classify where a formulation stands and what to fix next.

| Level | Gate | What it proves | Check |
|-------|------|---------------|-------|
| **generates** | Code generates | LLM produced syntactically valid PyRel | Code parses without syntax errors |
| **compiles** | Compiles | `display()` succeeds — formulation converts to solver-ready form | `display()` returns without error; variables, constraints, objective all registered |
| **solves** | Solves | Solver accepts the problem and returns a result (any status, no crash/error) | `p.termination_status()` is not ERROR/None; `solve()` completes |
| **optimal** | OPTIMAL | Solver found a proven optimum (or TIME_LIMIT with acceptable gap <5%) | `p.termination_status() == "OPTIMAL"` or `(status == "TIME_LIMIT" and gap < 0.05)` |
| **non-trivial** | Non-trivial | Solution has meaningful activity — not all zeros, not vacuous | `p.objective_value() != 0`, `non_zero_ratio > 0.01`, not all variables at bounds |
| **meaningful** | Meaningful | Decisions are actionable — right scale, distribution, entity coverage | Domain-specific: quantities match demand scale, assignments cover tasks, flows balance |

**How to use the ladder:**
- **Formulation building**: After each formulation change, re-check — did you advance or regress?
- **Debugging**: Identify the highest level reached, then focus on the failure at the next level up.
- **Reporting**: "This formulation reaches optimal but fails non-trivial (all-zero solution — missing forcing constraints)."

### Failure Taxonomy by Level

When a formulation fails at a level, the root cause falls into specific categories. Diagnose using the taxonomy for the **first failed level** — fixing upstream failures often resolves downstream ones.

| Failed Level | Root Cause | Description | Typical Fix |
|-------------|-----------|-------------|-------------|
| **generates** | `syntax_error` | Invalid Python / PyRel syntax | Fix indentation, missing imports, malformed expressions |
| **generates** | `undefined_reference` | References concept/property that doesn't exist | Check model introspection; use `enrich_ontology` if property is missing |
| **compiles** | `type_mismatch` | Wrong types in `solve_for`, `satisfy`, or `minimize`/`maximize` | Check that variable types match constraint operands (Float vs Integer) |
| **compiles** | `unresolved_overload` | `name=[]` traverses relationships or has multi-hop paths | Use primitive identity fields in `name=[]`; single-hop only |
| **compiles** | `missing_registration` | Variables/constraints defined but not registered with Problem | Ensure all `solve_for`, `satisfy`, `minimize`/`maximize` calls reference the Problem instance |
| **solves** | `solver_crash` | Solver errors out (license, memory, malformed problem) | Check solver logs; simplify problem size; verify solver availability |
| **solves** | `solve_error` | Solver returned error (license, timeout, numerical) | Check solver logs; re-solve is safe on same Problem instance (1.0.3+) |
| **optimal** | `infeasible` | No solution satisfies all constraints | Over-constrained — relax bounds, remove conflicting constraints, add slack |
| **optimal** | `dual_infeasible` | Objective can improve infinitely (unbounded) | Missing bounds or capacity constraints; check objective direction |
| **optimal** | `time_limit_large_gap` | Solver timed out with >5% gap | Increase time, tighten Big-M, add symmetry breaking, reduce problem size |
| **non-trivial** | `missing_forcing_constraint` | "Do nothing" satisfies all constraints — trivial zero solution | Add demand satisfaction, coverage, or assignment completeness constraints |
| **non-trivial** | `join_mismatch` | Forcing constraints exist but `.where()` joins match zero rows | Fix relationship paths in constraint joins; verify data alignment |
| **non-trivial** | `disconnected_variables` | Multiple variable sets but not all linked through constraints | Add conservation or linking constraints at shared entities |
| **non-trivial** | `all_at_bounds` | Variables pushed to lower/upper bounds uniformly | Check that constraint RHS values are populated (not null/zero); verify data loads |
| **meaningful** | `wrong_scale` | Values exist but are implausible (1e12 production, 0.001 assignments) | Check coefficient magnitudes; verify unit consistency in data |
| **meaningful** | `concentrated` | Solution uses only 1 entity when many expected | Add fairness/balance constraints or check cost differentials |
| **meaningful** | `wrong_direction` | Objective optimizes in wrong direction (minimizing revenue, maximizing cost) | Flip `minimize` ↔ `maximize`; check coefficient signs |
| **meaningful** | `missing_entity_coverage` | Some required entities (tasks, demands, regions) have no assigned activity | Check that entity creation covers all required instances; verify `.where()` filters |

**Diagnosis protocol:**
1. Determine the highest level reached on the ladder
2. Look up the failed level in the taxonomy
3. Check root causes in order (most common first)
4. Apply the typical fix, re-check the ladder
5. If fix causes regression (drops to lower level), revert and try alternative

---

## Quality Assessment

After reaching **optimal** on the solvability ladder, the solution still needs quality checks to reach **non-trivial** and **meaningful**. A solver can return "optimal" for a trivially empty or degenerate problem. Type-specific expectations: Resource Allocation should show non-zero allocations summing near budget/capacity; Network Flow should show balanced flows with non-zero arcs; Scheduling/Assignment should show each task/shift covered; Pricing should show differentiated prices across entities. For multi-period problems of any type, verify non-trivial quantities across periods.

### Quality Scoring Framework

| Status | Ladder Gate | Meaning | Action |
|--------|------------|---------|--------|
| **GOOD** | meaningful | No critical or warning issues; decisions are actionable | Proceed to explain results |
| **WARNING** | non-trivial | Solution has activity but minor concerns (some at bounds, objective outside expected range) | Review flagged items, proceed if acceptable |
| **POOR** | Below non-trivial | Critical issues (trivial solution, zero objective, all variables at bounds) | Diagnose root cause using failure taxonomy before presenting results |

### Trivial Solution Detection

A solution is **trivial** when the solver technically found an optimum, but the result is meaningless:

1. **All-zero solution** (non_zero_ratio < 1%): The solver set all decision variables to zero. For a minimize objective, this means "do nothing" is cheapest -- almost always indicates missing forcing constraints (demand satisfaction, coverage requirements).

2. **Objective value = 0 on minimize**: A zero-cost solution nearly always means the solver found that doing nothing satisfies all constraints. The forcing constraints that should require activity (demand fulfillment, assignments, coverage) are either missing or their joins matched zero rows.

3. **All binary variables = 0 or all = 1**: In assignment/selection problems, if every binary variable takes the same value, the problem likely has no meaningful differentiation between choices. Check that selection costs/values differ and that cardinality constraints are present.

4. **Only one entity selected when many expected**: If the problem should distribute across multiple entities but concentrates on one, check for missing balance/fairness constraints or extreme cost differentials.

5. **All variables at bounds (vacuous satisfaction)**:
   - **All at lower bound** (>= 90%): Constraints with joins likely matched zero rows. The solver had no forcing requirements, so it minimized by setting everything to the minimum.
   - **All at upper bound** (>= 90%): Either capacity is too tight relative to demand, or maximize objective with no upper-bound constraints.
   - **Clustered at same small value**: Variables near a minimum-bound constraint; demand satisfaction joins likely match no data.

### Forcing Constraint Identification

A **forcing constraint** is one that requires decision variables to take positive values. Without them, minimize objectives will produce all-zero solutions.

**Diagnosis:** If the objective is minimize and the solution is all zeros, look for which requirements from the data should force positive activity, and verify those constraints exist and their joins match actual data. For common forcing constraint patterns and code examples, see `rai-prescriptive-problem-formulation/constraint-formulation.md` > Forcing Constraints.

## Forcing Constraint Principles

Forcing constraints prevent the solver from finding a trivial "do nothing" solution (all variables = 0).

**For minimize objectives**, at least one constraint must FORCE positive activity:
- Demand satisfaction: `sum(Decision.x_qty).per(Demand) >= Demand.required`
- Assignment completeness: `sum(Assignment.x_assign).per(Task) >= 1`
- Coverage: `sum(Selection.x_selected).per(Region) >= Region.min_coverage`

**For maximize objectives**, natural upper bounds serve as forcing constraints:
- Capacity limits: `sum(Decision.x_qty).per(Resource) <= Resource.capacity`
- Budget: `sum(Decision.x_qty * Decision.cost) <= budget`

**Self-defeating constraints** (AVOID):
- `var == 0` or `var <= 0` without `.where()` — forces everything to zero
- Nested `require()` calls — causes syntax errors

**Evaluation process:**
1. List the decision variables and what they represent
2. List constraints that could force positive activity
3. Determine if "doing nothing" (all zeros) would violate any constraint
4. Check variable connectivity: If there are MULTIPLE variable sets, are they ALL linked? Can one variable set satisfy its constraints while another stays at zero?

### Reasonableness Checks

Beyond automated detection, apply domain judgment:
- Do production quantities match roughly the scale of demand?
- Are transportation flows consistent with known network capacity?
- Do assignment patterns make geographic/logical sense?
- Is the objective value in a plausible range for the business context?

### Structured diagnosis approach

When diagnosing solution quality issues, follow this sequence:

1. **Understand the domain**: Study the model context — what entities exist, their relationships, what properties represent requirements/capacities/costs
2. **Identify the gap**: For MINIMIZE objectives with zero solution, the most common cause is missing forcing constraints (constraints that REQUIRE positive variable values)
3. **Find requirements in the model**: Look for concepts/properties representing things that MUST be satisfied — demand quantities, assignments, coverage, resource allocations
4. **Link variables to requirements**: The fix should connect decision variable sums to actual requirement values from the model using correct relationship paths

### Fix Generation Guidelines

When generating fixes for trivial or poor-quality solutions, follow these rules:

**Root cause taxonomy:**

| Root Cause | Description | Typical Fix |
|------------|-------------|-------------|
| `missing_forcing_constraint` | No constraint requires positive variable values; "do nothing" is optimal | Add demand satisfaction or coverage constraint |
| `entity_creation_filter` | Cross-product entity creation has `.where()` joins that match zero rows | Fix join conditions to match actual data relationships |
| `disconnected_concepts` | Multiple variable sets exist but are not linked through constraints | Add conservation or linking constraints at shared entities |

**Fix priority rule:** Prefer constraint fixes (`add_constraint`, `modify_constraint`) over variable fixes (`add_variable`). Adding variables increases problem complexity; adding constraints focuses the existing formulation.

**Grounding rules — all fixes must use actual model context** (ungrounded fixes produce compile errors or silently match zero entities):
- Use actual concept and property names from the model — invented names cause compile errors
- Only reference relationships and properties that EXIST in the model
- Check data samples to understand what values are actually available
- Examine the current formulation to understand what is already defined
- Use `.per(<Entity>)` at the correct granularity based on model relationships
- Link decision variable sums to actual requirement values using correct relationship paths

**When suggesting `add_variable` (use sparingly):**
- Base the new variable's scope on existing concepts from the model — variables referencing non-existent concepts cause compile errors
- Use `.where()` filters based on actual property values from data samples
- Reference actual relationship paths that exist in the model
- For concept and variable creation syntax, see `rai-prescriptive-problem-formulation/variable-formulation.md`

**Constraint fix requirements** (constraints without decision variables cause `ValueError` at solve time):
- Reference at least one decision variable (`x_` prefix)
- Avoid self-defeating constraints (e.g., constraining a variable to equal a value that makes the objective worse while also requiring the objective to improve)
- Connect to real requirements in the data — the fix should force positive activity

### Quality dimensions

- **Actionability**: Can decision makers act on this solution? Does it provide useful granularity? (e.g., "produce 150 units at Site A" is actionable; "total cost = 0" is not)
- **Interpretability**: Can the solution be explained in business terms? Decision variable attributes have an `x_` prefix (e.g., `x_quantity`, `x_assigned`) — always translate these to business language when presenting results:
  - `x_flow` → "shipment quantity" or "units shipped"
  - `x_assigned` → "assigned" or "selected"
  - `x_quantity` → "production quantity" or "units allocated"
  - `x_open` → "facility is open" or "selected for use"

## Join Path Fix Rules

When fixing trivial solutions, the primary approach is to fix broken join paths in constraints — NOT to add aggregate workarounds.

**Diagnosis steps:**
1. Identify the join condition that should link decision variables to requirements (location, SKU, ID, etc.)
2. Check MODEL RELATIONSHIPS for valid paths from BOTH sides to that shared property
3. Both paths must reach the SAME underlying data — if not, find the correct navigation path
4. Common fix: Replace `UnboundConcept.property` with `BoundConcept.relationship.property`

**Example:** If `Flow.destination == Customer.site` matches nothing because `Customer` is unbound:
- Find how Customer relates to the requirement concept (e.g., `Demand.customer`)
- Fix: `Flow.destination == Demand.customer.site` (navigate from the bound concept `Demand`)

**Navigation path rules:**
- When using `.per(Entity)`, ALWAYS navigate FROM that entity
- Standalone concept references like `Customer.site` or `Site.id` create Cartesian products and match ZERO rows
- Instead use: `Demand.customer.site` (navigating from the `.per()` entity)

**Aggregate workarounds are NOT fixes:**
- Do NOT suggest constraints like `sum(X) >= 0.5 * sum(Y)` or `sum(X) >= some_fraction * total`
- These mask the real problem (broken joins) and don't properly link decisions to requirements
- If you cannot find a valid join path, report the model gap rather than working around it

**Per-entity vs aggregate constraint patterns:**
- WITHOUT `.per()` for per-entity minimums: `Decision.x_quantity >= Entity.demand` — creates one constraint per entity automatically
- WITH `.per()` for aggregation: `sum(Decision.x_quantity).per(Entity) >= Entity.required` — sums decision vars per entity

---

## Result Explanation Guide

Solution explanation is the return leg of bidirectional translation: the solver produced math, now translate it back into business language and actionable recommendations. Decision makers should never need to interpret solver output directly.

### Understanding decision variables

Solution results contain values for "decision concepts" — entities created to represent optimization choices.

- `x_` prefix → decision variables controlled by the solver. Translate `x_` prefixed names to business terms when presenting results — the prefix is an internal convention that confuses business users (e.g., `x_quantity = 150` → "produce 150 units", `x_assigned = 1` → "assigned")
- Extended concepts → cross-product entities linking two base concepts (the decision space). Map back to base entities when presenting (e.g., "SiteProduct.x_quantity" → "production of Product at Site")
- Present decision values with entity context, not as raw numbers. Use business labels in result tables: "Quantity Shipped" not "x_flow", "Assigned" not "x_assigned", "Units Produced" not "x_quantity"

### Structure for Stakeholders

Present results in this order (6-part template):

1. **Problem Context** (2-3 sentences): What problem was being solved and the business context.
   - "We optimized the distribution network to minimize total logistics cost while meeting all regional demand."

2. **What Was Decided**: The key allocations, assignments, or quantities. Lead with the actionable output. Include objective value and what it means in business terms.
   - "The model recommends producing 500 units at Site A and 300 at Site B. Total cost: $1.2M."

3. **Why These Decisions (Key Drivers)**: Which constraints and costs drove the solution. Answer: "Why was X selected?", "Why was Y excluded?", "What's preventing Z?" — using actual entity names from the solution.
   - "Site A is used heavily because it has the lowest unit cost and sufficient capacity."
   - "Site C was not selected because its fixed cost exceeds the savings from lower transport distance."

4. **Solution Quality Assessment**: Is the solution useful? Check for non-triviality, actionability, interpretability. Flag any red flags:
   - All-zero or near-zero solution
   - Objective value outside plausible range
   - Concentration on a single entity when distribution is expected
   - Variables clustered at bounds

5. **Business Impact**: Translate the objective value and key metrics into business language. What does this mean for the organization?
   - "Total cost: $1.2M, a 15% reduction from the current allocation."
   - "All customer demand is met. Two facilities operate at >90% capacity."

6. **Recommended Next Steps**: What should the user do with this solution?
   - Validate with domain experts?
   - Run sensitivity analysis on key parameters?
   - Implement directly?
   - Investigate specific entities that behave unexpectedly?

### Answering "Why This Decision?" (Explainability)

Decision makers need to understand not just what the solution recommends, but why. Use binding constraints and dual values to answer specific questions:

- **"Why was X selected?"** → Identify which constraints and cost/value properties made X optimal. "Supplier A gets 60% of orders because it has the lowest cost per unit while meeting the reliability threshold you set."
- **"Why was Y excluded?"** → Identify which constraint or cost makes Y suboptimal. "Warehouse 3 isn't used because transportation cost to Eastern customer segments makes it more expensive despite available capacity."
- **"What's preventing Z?"** → Identify the binding constraint. "Site B can't produce more because its capacity constraint is binding at 500 units."

Frame every explanation in terms the decision maker already knows — their suppliers, their warehouses, their customers — not constraint indices or dual values.

### Translating Shadow Prices

Shadow prices (dual values) tell you the marginal value of relaxing a constraint by one unit. Translate them as:

| Technical | Business Language |
|-----------|-------------------|
| "Shadow price of capacity constraint at Site A = $50" | "Adding one more unit of capacity at Site A would save $50 in total cost." |
| "Shadow price of budget constraint = 0.12" | "Each additional dollar of budget would generate $0.12 in objective improvement." |
| "Shadow price = 0 (non-binding)" | "This constraint has slack -- relaxing it would not change the solution." |

### Sensitivity Framing

Frame sensitivity results as conditional business statements:
- "If demand increases by 10%, total cost rises by $80K and Site B reaches full capacity."
- "The solution is robust to +/-5% cost variation -- the same facilities are selected."
- "The critical threshold is at 1,200 units of demand: beyond that, a fourth facility is needed."

---

## Sensitivity Analysis

Sensitivity analysis answers: "What happens if our assumptions change?" Present results as scenario comparison tables, not mathematical derivatives. Prioritize parameters that are uncertain (demand forecasts, cost estimates), controllable (budget limits, service level targets), or high-impact (small changes cause structural solution changes).

Scenarios should be treated as a default post-solve step, not an optional advanced feature. After every solve, proactively suggest 1-2 scenario variations based on binding constraints and parameter sensitivity.

**Strategic vs. operational context:** For strategic (one-time planning) decisions, Pareto frontiers showing the tradeoff surface are preferred — stakeholders choose from the frontier. For operational (recurring) decisions, weighted objectives with tunable weights are more practical — set once, run daily. Detect which context applies and frame scenario results accordingly.

Parameter types: **numeric** (range with step), **entity** (select/exclude specific entities), **categorical** (discrete named options). A parameter is **critical** if small changes cause different facilities/assets to be selected, >5% objective change per 10% parameter variation, or constraint status flips.

See full guidance: [references/sensitivity-analysis.md](references/sensitivity-analysis.md)

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Zero objective on minimize | Missing forcing constraints — "do nothing" is cheapest | Add `sum(x).per(Entity) >= Entity.demand` or equivalent |
| All-zero variables with non-zero objective | Decision variables not referenced in objective, or constant terms evaluate regardless | Verify decision variable properties appear in objective with meaningful coefficients |
| All-zero from join mismatch | Forcing constraints exist but `.where()` joins match zero rows | Verify constraint joins match actual data relationships |
| Infeasible: demand > capacity | Total demand exceeds total supply/capacity | Add slack/penalty variables, or relax demand constraints |
| Infeasible: contradictory constraints | Conflicting equality/inequality constraints or bounds | Organize into essential/full tiers; add incrementally to isolate conflict |
| Numerical instability | Coefficients differing by >1e9 | Scale data to similar magnitudes; tighten Big-M (<1e6); replace strict equalities with bounded slack |
| Cross-product entities mostly zero | Entities created but not linked to meaningful constraints | Add `.where()` filters to entity creation; restrict to valid combinations |
| Degenerate solutions (different on re-run) | Multiple optimal solutions with same objective | Add secondary objectives, symmetry-breaking constraints, or tie-breaking preferences |
| Wrong aggregation scope | `.per(Y)` but Y not joined to summed concept — constraint satisfied globally but violated locally | Add proper `.per()` grouping and relationship join in `.where()` |
| Missing constraint scope | Per-entity constraint applies globally | Add `.per()` grouping or iterate over entities |
| Incorrect relationship direction | `<=` when should be `==` or `>=` | Review business requirement — is this a limit, balance, or minimum? |
| Double counting in objective | Same quantity in both fixed and variable cost terms | Check for overlapping aggregation scope in objective terms |
| Missing/null data silently dropped | Null/NaN values cause variables or constraints to vanish | Verify all referenced properties have populated values |
| Wrong data type | String or boolean where number expected | Check that cost, capacity, demand columns are numeric |

## Diagnosis Checklist

Use this after every solve to ensure result quality:

- [ ] Status is OPTIMAL (or time-limit with acceptable gap)?
- [ ] Objective value is non-zero and in a plausible range?
- [ ] Non-zero ratio of decision variables is reasonable (not all zeros)?
- [ ] No variables at suspiciously large values (> 1e10)?
- [ ] Variables are not all clustered at bounds?
- [ ] Solution makes business sense (quantities match demand scale, assignments are logical)?
- [ ] Binding constraints align with known bottlenecks?
- [ ] Results are stable to minor parameter perturbations?

---

## Fix Strategy: Trivial Solution

Use this strategy when the solution is OPTIMAL but trivial (all zeros, zero objective, vacuous satisfaction).
The root cause is almost always **missing forcing constraints** — the solver found a "do nothing" shortcut.

**FORCING-FIRST APPROACH:**
The solver found a solution but it is trivial (all zeros or near-zero objective). This means the
formulation LACKS constraints that force meaningful activity. The solver found a "shortcut" that
satisfies all constraints by doing nothing.

Root cause is almost always: missing forcing constraints. For example:
- A minimize-cost problem with no demand satisfaction constraint: zero flow is cheapest
- An assignment problem with no coverage requirement: assigning nobody satisfies all constraints

**Fix priority order:**
1. Add FORCING constraints that require meaningful activity (demand satisfaction, coverage, minimum utilization)
2. Modify existing constraints to be tighter (lower bounds, equality instead of inequality)
3. Check if existing forcing constraints reference the wrong properties or have wrong direction (>= vs <=)
4. Add new variables only if the current variable set cannot express the forcing requirement

**Emphasis:** Focus on adding FORCING constraints — this is a TRIVIAL solution where the solver found a zero-activity shortcut.

---

## Fix Strategy: Infeasible Solution

Use this strategy when the solver returned INFEASIBLE or a previous fix caused infeasibility.
The root cause is **over-constraining** — conflicting or too-tight constraints make feasibility impossible.

**RELAXATION-FIRST APPROACH:**
This formulation was built with comprehensive constraint selection but the solver found NO feasible solution.
The constraints are mutually contradictory or over-restrictive. Before adding anything, REMOVE or RELAX:
- Are existing constraints too tight (equality where inequality would suffice)?
- Are there redundant constraints that conflict with each other?
- Can a constraint be softened (e.g., `== demand` to `>= demand * 0.9`)?
- Should a non-essential constraint be removed entirely?

**Fix priority order:**
1. Remove or relax conflicting/redundant constraints (least disruptive)
2. Modify existing constraints (soften bounds, widen ranges)
3. Add slack variables to absorb infeasibility
4. Add new variables (last resort)

**Emphasis:** PREFER removing or relaxing existing constraints — this is an INFEASIBLE solution caused by over-constraining.

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Scenario result extraction | `variable_values().to_df()`, `solve_info().display()`, status/objective access, scenario comparison table | [examples/portfolio_results.py](examples/portfolio_results.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Sensitivity analysis | Sensitivity analysis techniques and parameter sweeps | [sensitivity-analysis.md](references/sensitivity-analysis.md) |
