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
- Interpreting any solver status after solve completes (OPTIMAL, INFEASIBLE, DUAL_INFEASIBLE, TIME_LIMIT)
- Diagnosing why a solved-OPTIMAL result is trivial, wrong, or has coverage gaps (all zeros, all at bounds, concentrated on one entity)
- Diagnosing INFEASIBLE status (demand vs capacity, contradictory constraints, bound conflicts)
- Assessing TIME_LIMIT results (gap interpretation, whether to increase time or simplify model)
- Explaining results to stakeholders in business language
- Running sensitivity / what-if analysis

**When NOT to use:**
- Designing or fixing the formulation itself (adding constraints, changing variables) — see `rai-prescriptive-problem-formulation`. In particular, if the result is OPTIMAL and technically valid but the user rejects it on preference grounds ("that's too much X", "I don't like this allocation"), this indicates latent constraints, not a solver or formulation bug — route to `rai-prescriptive-problem-formulation` > Constraint Elicitation > Post-Solve: Iterative Refinement.
- Solver configuration, parameter tuning, or solver-level failures — see `rai-prescriptive-solver-management`
- Query syntax (select, aggregation, joins) — see `rai-querying`

**Overview:**
1. Recall the optimization goal captured in the problem's variables and objective — what decisions were being made, and what should success look like?
2. Check termination status
3. Extract solution values (query decision variable properties)
4. Assess solution quality against the original goal (trivial solution detection, reasonableness checks)
5. Explain results to stakeholders (what was decided, why, business impact)
6. Run sensitivity analysis (parameter sweeps, what-if scenarios)

---

## Interpretation Workflow

After a solve completes, interpret results in this order:

1. **Recall the goal** — Before inspecting solver output, review what the formulation was trying to achieve: what decisions were being made, what objective was set, and what constraints were imposed. This context is essential for judging whether results are meaningful or trivial — an OPTIMAL status means nothing if the solution doesn't address the original intent.
2. **Check status** (Status Interpretation) — Is the solve OPTIMAL, INFEASIBLE, DUAL_INFEASIBLE, or TIME_LIMIT?
   - If INFEASIBLE, DUAL_INFEASIBLE, or any error status: stop, diagnose root cause (Diagnosis Checklist), do not present results
   - If TIME_LIMIT with large gap (>10%): flag uncertainty, consider increasing time or simplifying
3. **Assess quality** (Quality Assessment) — Is the solution meaningful or trivially empty?
   - Check non-zero ratio, objective value plausibility, variable distribution
   - If trivial (all zeros, all at bounds): diagnose and fix before presenting
4. **Extract and filter** — Remove noise from raw solver output
   - Filter near-zero values (< 0.5 for binary, < 1e-6 for continuous)
   - Group by decision concept, map back to business entities
5. **Explain to stakeholders** (Result Explanation Guide) — Translate math to business language
   - Problem context → decisions made → key drivers → quality → business impact → next steps
6. **Explore what-if** (Sensitivity Analysis) — What happens if assumptions change?
   - Identify critical parameters (uncertain, controllable, high-impact)
   - Present as scenario comparison tables

---

## Quick Reference

```python
si = problem.solve_info()
if si.termination_status == "OPTIMAL":
    # With populate=True (default): query via model.select()
    # With populate=False: use Variable.values() — see Solution Extraction below
    print(f"Objective: {si.objective_value}")
```

---

## Solution Extraction

After a successful solve, extract results using result attributes and model queries.

### Result Attributes

After `problem.solve()`, result attributes are available via two interfaces:

**Engine-side (Relationships)** — usable in `model.require()`, `model.select()`, and solver expressions:

| Method | Return type | Description |
|--------|-------------|-------------|
| `problem.termination_status()` | Relationship | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `problem.objective_value()` | Relationship | Optimal objective value |
| `problem.num_points()` | Relationship | Number of solutions returned |
| `problem.error()` | Relationship | Error message tuple (if solve failed) |
| `problem.printed_model()` | Relationship | Text representation (with `print_format=`) |
| `problem.num_variables()` | Relationship | Total registered variables |
| `problem.num_constraints()` | Relationship | Total constraints |
| `problem.num_min_objectives()` | Relationship | Number of minimize objectives |
| `problem.num_max_objectives()` | Relationship | Number of maximize objectives |

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
problem.solve("highs", time_limit_sec=60)

# Engine-side: integrity constraint on status
model.require(problem.termination_status() == "OPTIMAL")

# Python-side: formatted output
si = problem.solve_info()
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
| `populate=False` | Solver-level only | `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for()` | Scenario loops, multi-solve workflows with shared variables |

**Primary approach: `model.select()` with `populate=True` (default, recommended)**

With `populate=True`, solved values are written back into the model as property values. Query them like any other model data — with entity context, aliases, and filtering:

```python
# Canonical extraction: filter active binary decisions, alias columns, display or convert to DataFrame
model.select(
    MachinePeriod.machine.machine_id.alias("machine_id"),
    MachinePeriod.period.pid.alias("period"),
    MachinePeriod.x_maintain.alias("maintained"),
).where(MachinePeriod.x_maintain > 0.5).inspect()   # or .to_df() for Python analysis
```

**`populate=False` approach: `Variable.values()` on ProblemVariable**

`solve_for()` returns a `ProblemVariable` — a Concept with **back-pointer attributes** for each non-value field in the Property's format string. Call `.values(sol_index, value_ref)` on it to extract solution values:

```python
# Property: f"{Assignment} has {Float:x}"  → back-pointer var.assignment, value field x
assign_var = problem.solve_for(Assignment.x, type="bin", populate=False)
problem.solve("highs")

value_ref = Float.ref()
df = model.select(
    assign_var.assignment.worker.name.alias("worker"),
    value_ref.alias("value"),
).where(assign_var.values(0, value_ref), value_ref > 0.5).to_df()
```

**Extraction principles:**
- **Binary variables:** Filter with `> 0.5`, not `== 1` (numeric tolerance in MIP solvers)
- **Continuous variables:** Filter with `> 1e-6` to remove near-zero solver noise
- **Scalar extraction:** `problem.solve_info().objective_value` for single values (no query needed)
- **Always alias:** Use `.alias()` on every output column for clean DataFrames
- **Int128 handling:** RAI may return `Int128Array` (nullable). Cast with `.astype(float)` before filtering or `.groupby().agg()`.

For per-pattern variations (multiple solutions, iterative solving, scenario/parametric extraction, full `Variable.values()` back-pointer naming rules with table of examples, silent-failure warnings, and Snowflake table export), see [references/solution-extraction-details.md](references/solution-extraction-details.md).

### Post-solve constraint verification

`problem.verify(*fragments)` checks that the solver's solution satisfies constraints post-solve. Particularly useful for exact solvers (HiGHS MIP, MiniZinc). See `rai-prescriptive-solver-management` for full `verify()` documentation and examples.

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
The objective can improve infinitely — the solver can keep making the solution "better" without limit. The termination status is `"DUAL_INFEASIBLE"` (not `"UNBOUNDED"`).

**Diagnosis steps:**
1. Check that all variables have appropriate bounds (especially upper bounds for maximize, lower bounds for minimize).
2. Verify budget/capacity/resource constraints are present.
3. Check objective direction: minimizing when should maximize, or vice versa?
4. Check coefficient signs in the objective.

**What to tell users:** "The model is missing limits that would bound the solution. Likely cause: [missing capacity constraint / missing budget limit / wrong objective direction]."
**Next steps:** Add missing bounds or constraints, verify objective direction and coefficient signs.

### Feasible (MIP)
For MIP problems, HiGHS may return `"Feasible"` instead of `"OPTIMAL"` when a solution is found but optimality is not proven within the default MIP gap tolerance. Check `si.relative_gap` (if available) or the solver log — a gap under 1% means the solution is effectively optimal. Treat `"Feasible"` the same as `"TIME_LIMIT"` for gap interpretation below.

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

### Re-Solve Behavior (SDK >= 1.0.3)

Re-solving the same `Problem` instance is safe (replace semantics). See `rai-prescriptive-solver-management` for details.

---

## Solvability Ladder

The solvability ladder defines progressive quality gates for an optimization formulation. Each level subsumes the previous — reaching "non-trivial" means all prior gates also passed. Use this to classify where a formulation stands and what to fix next.

| Level | Gate | What it proves | Check |
|-------|------|---------------|-------|
| **generates** | Code generates | LLM produced syntactically valid PyRel | Code parses without syntax errors |
| **compiles** | Compiles | `display()` succeeds — formulation converts to solver-ready form | `display()` returns without error; variables, constraints, objective all registered |
| **solves** | Solves | Solver accepts the problem and returns a result (any status, no crash/error) | `solve()` completes without exception; `problem.solve_info()` returns a status |
| **optimal** | OPTIMAL | Solver found a proven optimum (or TIME_LIMIT with acceptable gap <5%) | `problem.termination_status() == "OPTIMAL"` or `(status == "TIME_LIMIT" and gap < 0.05)` |
| **non-trivial** | Non-trivial | Solution has meaningful activity — not all zeros, not vacuous | `problem.objective_value() != 0`, `non_zero_ratio > 0.01`, not all variables at bounds |
| **meaningful** | Meaningful | Decisions are actionable — right scale, distribution, entity coverage | Domain-specific: quantities match demand scale, assignments cover tasks, flows balance |

**How to use the ladder:**
- **Formulation building**: After each formulation change, re-check — did you advance or regress?
- **Debugging**: Identify the highest level reached, then focus on the failure at the next level up.
- **Reporting**: "This formulation reaches optimal but fails non-trivial (all-zero solution — missing forcing constraints)."

### Failure Taxonomy and Diagnosis Protocol

For detailed root causes by level (generates, compiles, solves, optimal, non-trivial, meaningful) and the 5-step diagnosis protocol, see [references/failure-taxonomy.md](references/failure-taxonomy.md).

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

Prefer constraint fixes over variable fixes. All fixes must be grounded in actual model context (concept names, properties, relationships). See [references/fix-generation-guidelines.md](references/fix-generation-guidelines.md) for root cause taxonomy, grounding rules, and constraint fix requirements.

### Quality dimensions

- **Actionability**: Can decision makers act on this solution? Does it provide useful granularity? (e.g., "produce 150 units at Site A" is actionable; "total cost = 0" is not)
- **Interpretability**: Can the solution be explained in business terms? Decision variable attributes have an `x_` prefix (e.g., `x_quantity`, `x_assigned`) — always translate these to business language when presenting results:
  - `x_flow` → "shipment quantity" or "units shipped"
  - `x_assigned` → "assigned" or "selected"
  - `x_quantity` → "production quantity" or "units allocated"
  - `x_open` → "facility is open" or "selected for use"

### Join Path Fix Rules

When fixing trivial solutions, fix broken join paths in constraints — not aggregate workarounds. Navigate from bound concepts (e.g., `Demand.customer.site` not `Customer.site`), and always navigate FROM the `.per()` entity. See [references/fix-generation-guidelines.md](references/fix-generation-guidelines.md) for full diagnosis steps, examples, and navigation path rules.

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
   - "We optimized the allocation to minimize total cost while meeting all demand constraints."

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

- **"Why was X selected?"** → Identify which constraints and cost/value properties made X optimal. "Entity A gets 60% of allocation because it has the lowest unit cost while meeting the quality threshold."
- **"Why was Y excluded?"** → Identify which constraint or cost makes Y suboptimal. "Entity C isn't used because its fixed cost exceeds the savings from proximity despite available capacity."
- **"What's preventing Z?"** → Identify the binding constraint. "Site B can't produce more because its capacity constraint is binding at 500 units."

Frame every explanation in terms the decision maker already knows — their entities, their resources, their constraints — not variable indices or dual values.

### Translating Shadow Prices (Dual Values)

Shadow prices tell you the marginal value of relaxing a constraint. For the translation table and business-language framing, see [references/sensitivity-analysis.md](references/sensitivity-analysis.md).

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

**Pareto frontier / efficient frontier results:** When results come from an epsilon constraint loop (bi-objective optimization), each point on the frontier is a complete, valid solution — no point is strictly better than another. Explain to the user: "Each point represents a different balance between your two goals. The knee is where further improvement in one goal starts costing significantly more in the other." For the full analysis structure (tradeoff table, marginal rate analysis, knee detection, allocation shifts, regime characterization) and how to present results as a menu of operating points, see [references/sensitivity-analysis.md](references/sensitivity-analysis.md).

Parameter types: **numeric** (range with step), **entity** (select/exclude specific entities), **categorical** (discrete named options). A parameter is **critical** if small changes cause different facilities/assets to be selected, >5% objective change per 10% parameter variation, or constraint status flips.

For parameter sweep patterns, scenario comparison tables, and Pareto frontier construction, see [references/sensitivity-analysis.md](references/sensitivity-analysis.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Zero objective on minimize | Missing forcing constraints | Add `sum(x).per(Entity) >= Entity.demand` or equivalent |
| All-zero from join mismatch | Forcing constraints exist but `.where()` joins match zero rows | Verify constraint joins match actual data |
| Infeasible: demand > capacity | Total demand exceeds supply | Add slack/penalty variables or relax demand constraints |
| Silent: `problem.termination_status == "OPTIMAL"` (no parens) — always False | `termination_status` on the `Problem` object is a bound method, not a property; comparing a method to a string is never equal and the bug is silent | Read status Python-side: `problem.solve_info().termination_status == "OPTIMAL"` (no parens — `solve_info()` returns a dataclass-like value with a string field). Engine-side inside `model.require(...)`: `problem.termination_status() == "OPTIMAL"` (with parens — that's the engine-side Relationship) |
| Silent: non-OPTIMAL result extraction returns empty DataFrame / None objective | Loop / scenario workflows extract `Variable.values()` or read `si.objective_value` without checking status first. Infeasible / time-limited solves produce an empty query and `None` objective, silently propagated into downstream code | Always guard: `if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"): continue` (or raise) before touching `si.objective_value` or the extraction query |

For the full pitfalls table (14 entries covering numerical instability, degenerate solutions, wrong aggregation scope, and more), see [references/common-pitfalls.md](references/common-pitfalls.md).

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

**If checks fail:** Trivial solution (all zeros) → add forcing constraints first. Infeasible → relax or remove constraints first. See [references/fix-generation-guidelines.md](references/fix-generation-guidelines.md) for fix strategies.

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Scenario Concept results | Results in ontology via `model.select(Scenario.name, ...)`, per-scenario aggregation, comparison queries | [examples/scenario_concept_extraction.py](examples/scenario_concept_extraction.py) |
| Loop-based results | `Variable.values()`, `solve_info().display()`, status/objective access, scenario comparison table | [examples/loop_based_extraction.py](examples/loop_based_extraction.py) |
| Pareto frontier analysis | Tradeoff table, marginal rates + knee detection, allocation shifts + regime detection, ASCII frontier visualization | [examples/pareto_frontier_analysis.py](examples/pareto_frontier_analysis.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Solution extraction details | Query-pattern variations (`populate=True` vs `populate=False` — multiple solutions, iterative, scenario/parametric), `Variable.values()` back-pointer naming rules with examples table, silent-failure warnings, Snowflake export | [solution-extraction-details.md](references/solution-extraction-details.md) |
| Failure taxonomy | Detailed root causes by solvability level and 5-step diagnosis protocol | [failure-taxonomy.md](references/failure-taxonomy.md) |
| Fix generation guidelines | Root cause taxonomy, grounding rules, join path fixes, trivial/infeasible fix strategies | [fix-generation-guidelines.md](references/fix-generation-guidelines.md) |
| Common pitfalls | Full table of 14 common optimization result pitfalls with causes and fixes | [common-pitfalls.md](references/common-pitfalls.md) |
| Sensitivity analysis | Sensitivity analysis techniques and parameter sweeps | [sensitivity-analysis.md](references/sensitivity-analysis.md) |
