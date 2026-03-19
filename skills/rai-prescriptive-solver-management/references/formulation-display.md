<!-- TOC -->
- [Formulation Display](#formulation-display)
  - [Display output structure](#display-output-structure)
  - [Diagnosing issues from display output](#diagnosing-issues-from-display-output)
- [Diagnostics](#diagnostics)
  - [Formulation Verification Checklist](#formulation-verification-checklist)
- [Problem-Type Verification](#problem-type-verification)
<!-- /TOC -->

## Formulation Display

Before solving, inspect the mathematical formulation:

```python
# Print the full formulation (variables, constraints, objectives)
p.display()

# Formulation metrics — these are Relationships (call with parens)
# Use in model.require() for engine-side validation, or query via model.select()
p.num_variables()        # Total registered variables
p.num_constraints()      # Total constraints
p.num_min_objectives()   # Number of minimize objectives
p.num_max_objectives()   # Number of maximize objectives
```

Use `p.display()` to verify the formulation looks correct before calling `p.solve()`. Check that variable counts, constraint counts, and objective counts match expectations.

```python
# Example: diet problem verification — engine-side ICs avoid querying data to the client
model.require(p.num_variables() == count(Food))
model.require(p.num_min_objectives() == 1)
model.require(p.num_constraints() == 2 * count(Nutrient))
p.display()
```

### Display output structure

`p.display()` prints a structured summary with three sections:

```
Solver model has:
• 6 variables: 6 continuous, 0 integer, 0 binary
• 1 minimization objectives, 0 maximization objectives, 14 constraints

Variables:
   name  type  lower
 beef_v  cont    0.0
 chick_v cont    0.0
 ...

Minimization objectives:
  name          expression
  cost          sum(cost_per_serving * amount)

Constraints:
  name          expression
  min_calories  sum(calories * amount) >= 1800
  max_calories  sum(calories * amount) <= 2200
  ...
```

**Sections:** Summary line (counts by type), Variables table (name, type, lower, upper bounds), then Objectives and Constraints (name + symbolic expression). Named expressions are sorted by name; unnamed expressions are sorted by their string representation.

### Diagnosing issues from display output

The display output is the primary diagnostic tool — it shows the **materialized** formulation (after entity creation, `.where()` filtering, and `.per()` grouping), not just what was declared in code.

**Variable count diagnostics:**

| Observed | Likely cause | What to check |
|----------|-------------|---------------|
| 0 variables (but code defines them) | Entity creation failed — `.where()` filters eliminated all entities, or the source concept has no data | Check that source concepts have loaded data; check `.where()` conditions aren't contradictory |
| Fewer variables than expected | `.where()` filters are more restrictive than intended, or cross-product join produced fewer pairs | Verify join paths match actual relationships; query the source concepts independently |
| More variables than expected | Cross-product is unconstrained (missing `.where()` filter), producing all-pairs | Add relationship filter to scope variable creation |

**Constraint count diagnostics:**

| Observed | Likely cause | What to check |
|----------|-------------|---------------|
| 0 constraints | `model.require()` or `p.satisfy()` calls produced empty constraint sets — typically a `.where()` that matches nothing | Verify join paths in constraint `.where()` clauses match loaded data |
| Fewer constraints than expected | `.per()` grouping produced fewer groups than expected, or `.where()` filtered out entities | Check that grouping concepts have the expected entity count |
| Missing forcing constraints | Minimize objective will return trivial zero solution | Verify at least one constraint forces positive activity (demand satisfaction, assignment completeness) |

**Objective diagnostics:**

| Observed | Likely cause | What to check |
|----------|-------------|---------------|
| 0 objectives | `p.minimize()` / `p.maximize()` not called, or expression evaluated to empty | Verify objective references at least one decision variable property |
| Objective expression references no variables | Expression uses only data properties, not `solve_for`-registered properties | Cross-check property names in objective against registered variables |

**Expression inspection:** Read the symbolic expressions in the Constraints section to verify:
- Aggregation scope (`.per()`) matches intent — e.g., capacity constraint should be `.per(Resource)`, not global
- Join paths connect the right concepts — e.g., `sum(Allocation.x_spend).where(Allocation.channel == Channel)` not `sum(Allocation.x_spend)` globally
- Coefficient signs are correct — e.g., `cost * qty` not `-cost * qty` for a cost minimization

**Pre-solve vs post-solve:** Always inspect `p.display()` output **before** calling `p.solve()`. After a failed solve (infeasible, unbounded), compare the display output against expected structure using the Problem-Specific Expected Components checklists below.

---

## Diagnostics

### Formulation Verification Checklist

Before solving, verify the formulation looks correct:

1. **Variable count** -- does `p.num_variables()` match expected? Missing variables often indicate `where=` conditions that filter too aggressively.
2. **Constraint count** -- does `p.num_constraints()` match expected? Fewer constraints may mean `model.require()` or `p.satisfy()` calls are silently producing empty constraint sets.
3. **Objective count** -- exactly one `p.minimize()` or `p.maximize()` call per Problem.
4. **Display inspection** -- `p.display()` shows the mathematical formulation. Look for variables that appear disconnected from the objective.

## Problem-Type Verification

After inspecting `p.display()`, compare the formulation against expected structural components for the problem type.

**Diagnostic process:**
1. Identify the problem type from semantic signals (problem statement) and structural signals (variable types, constraint patterns).
2. Compare `p.display()` counts and expressions against expected components for that type. For the full per-type component checklists (Resource Allocation, Network Flow, Routing, Scheduling, Inventory, Pricing), see `rai-prescriptive-problem-formulation/problem-patterns-and-validation.md` > Problem Type Classification & Structural Checklists.
3. Flag missing components as the likely root cause of solver failure.

---

## Targeted Inspection with `p.display(part)`

Pass the return value of `solve_for()`, `minimize()`, `maximize()`, or `satisfy()` to inspect just that part of the formulation:

```python
x_vars = p.solve_for(Route.x_flow, name=["flow", Route.origin, Route.dest], lower=0)
cap = p.satisfy(model.require(Route.x_flow <= Route.capacity), name="cap")

p.display(x_vars)  # just the flow variables
p.display(cap)     # just the capacity constraints
```

Useful for debugging specific parts of a large formulation without printing everything.

---

## `p.printed_model()` — Solver Model Text Representation

After calling `p.solve()` with `print_format=`, access the text representation via `p.printed_model()` (Relationship) or `p.solve_info().printed_model` (Python string):

```python
# Get LP format (useful for debugging)
p.solve("highs", print_format="lp", print_only=True)
print(p.solve_info().printed_model)

# Available formats: "moi" (MOI text), "latex", "mof" (MOI JSON), "lp", "mps", "nl" (AMPL)
```

Use `print_only=True` to inspect the formulation without actually solving. Works with or without `print_only`.

---

## Re-solving the Same Problem

The same `Problem` instance can be solved multiple times. Constraints accumulate (cannot be removed), but results are properly versioned. Each `solve()` call gets a fresh model ID and imports results with solve-counter offsets to avoid conflicts.

```python
# First solve
p.solve("highs", time_limit_sec=60)
print(p.solve_info().objective_value)  # Result from solve 1

# Add more constraints
p.satisfy(model.require(Route.x_flow >= min_flow))

# Re-solve — previous constraints + new constraint
p.solve("highs", time_limit_sec=60)
print(p.solve_info().objective_value)  # Result from solve 2
```

For different constraint sets (e.g., parametric solving), create a fresh `Problem` per scenario.

---
