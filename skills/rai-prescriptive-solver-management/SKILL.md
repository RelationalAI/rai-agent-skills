---
name: rai-prescriptive-solver-management
description: Covers solver lifecycle including problem type classification, solver selection and creation, global constraints, pre-solve validation, solve execution, and diagnostics. Use when configuring or running optimization solvers.
---

# Solver Management
<!-- v1-SENSITIVE -->

## Summary

**What:** Solver lifecycle — selection, creation, formulation inspection, execution, and diagnostics.

**When to use:**
- Choosing which solver to use for a problem (HiGHS vs Gurobi vs MiniZinc vs Ipopt)
- Setting up Problem and Solver instances
- Inspecting formulation before solving (p.display(), variable/constraint counts)
- Tuning solver parameters (time limits, MIP gap, presolve)
- Diagnosing solver failures (infeasible, unbounded, slow convergence)
- Understanding numerical stability issues or Big-M sizing
- Running parametric/scenario solves

**When NOT to use:**
- Variable/constraint/objective formulation patterns — see `rai-prescriptive-problem-formulation/SKILL.md`
- Post-solve solution extraction or interpretation — see `rai-prescriptive-results-interpretation/SKILL.md`
- PyRel syntax (imports, types, properties) — see `pyrel_coding/SKILL.md`

**Overview:**
1. Classify the problem type (LP / MILP / QP / NLP / CSP)
2. Select a solver (decision rules based on variable types and nonlinearity)
3. Create Problem and Solver instances
4. Validate formulation pre-solve (p.display(), count checks)
5. Execute solve (parameters, time limits, warm starting)
6. Diagnose issues if solve fails or produces poor results

---

## Quick Reference

```python
from relationalai.semantics import Model, Float, Integer
from relationalai.semantics import where, select, define, require
from relationalai.semantics.std import aggregates as aggs
from relationalai.semantics.reasoners.prescriptive import Problem

# 1. Create Problem (Float for LP/MILP/NLP, Integer for CP)
p = Problem(model, Float)

# 2. Register variables (type: "cont", "int", "bin"; bounds; naming)
p.solve_for(Route.x_flow, type="cont", lower=0, upper=Route.capacity,
            name=["flow", Route.origin, Route.dest])
p.solve_for(Facility.x_open, type="bin", name=["open", Facility.id])

# 3. Add constraints (model.require inside p.satisfy)
p.satisfy(model.require(aggs.sum(Route.x_flow).per(Customer) >= Customer.demand))
p.satisfy(model.require(Route.x_flow <= Route.capacity * Facility.x_open))

# 4. Set objective (exactly one minimize or maximize)
p.minimize(aggs.sum(Route.cost * Route.x_flow))

# 5. Pre-solve check — always inspect before solving
p.display()
model.require(p.num_variables() > 0)
model.require(p.num_constraints() > 0)

# 6. Solve — solver choice depends on problem type and user license
#    See "Solver Selection" section for decision rules
p.solve(solver_name, time_limit_sec=120)
p.solve_info().display()
# Solvers: "highs" (LP/MILP, open-source), "gurobi" (LP/MILP/QP/QCP, license required),
#          "minizinc" (CP, open-source), "ipopt" (NLP, open-source)
# Check: p.termination_status() → "OPTIMAL" | "INFEASIBLE" | "UNBOUNDED" | "TIME_LIMIT"
```

---

## Problem Type Classification

Identify the problem type before choosing a solver:

**Linear Programming (LP):** All variables continuous, objective and constraints all linear. No products of variables, no nonlinear functions.

**Mixed-Integer Linear Programming (MILP):** Some variables integer or binary, but objective and constraints remain linear. No products of integer variables (that makes it nonlinear). Keep Big-M tight.

**Quadratic Programming (QP):** Quadratic terms in objective only (e.g., risk minimization with covariance). Constraints remain linear. Check convexity (Q matrix positive semi-definite) for global optimum.

**Quadratically Constrained Programming (QCP):** Quadratic terms in constraints (e.g., norm constraints). More restrictive solver requirements than QP. Check if constraints are convex.

**Nonlinear Programming (NLP):** Nonlinear functions (exp, log, sqrt, sin, cos). Integer + NLP is very difficult (MINLP). May have local optima -- solution may not be global.

**Constraint Satisfaction Problem (CSP):** No meaningful objective function. Goal is finding any feasible solution. Often discrete variables with combinatorial constraints. Benefits from global constraints.

---

## Solver Selection

Choose the solver based on variable types and objective/constraint structure:

### Support Matrix

| Problem Type | Gurobi | HiGHS | Ipopt | MiniZinc |
|---|---|---|---|---|
| Linear Programs (LP) | YES | YES | YES | NO |
| Mixed-Integer Linear (MILP) | YES | YES | NO | NO |
| Quadratic Programs (QP) | YES (convex obj only) | YES | YES | NO |
| Quadratically Constrained (QCP) | YES | NO | YES | NO |
| Nonlinear Programs (NLP) | YES | NO | YES | NO |
| Constraint Programming (CP) | NO | NO | NO | YES |
| Discrete Variables (int/bin) | YES | YES | NO | YES |
| Continuous Variables | YES | YES | YES | NO |

### Solver Profiles

**HiGHS** (`solver="highs"`): Open-source. Best for LP, MILP, convex QP objectives. Fast simplex/IPM LP solver, good MILP for moderate problems. Params: `time_limit`, `mip_rel_gap`, `presolve` ("choose"/"on"/"off"), `threads`.

**HiGHS limitations (specific):**
- No indicator constraints — `implies()` will fail. Use Big-M reformulation instead.
- No SOS constraints — `special_ordered_set_type_1()` / `special_ordered_set_type_2()` will fail. Use explicit binary variable formulations instead.
- No quadratic constraints (QCP) — quadratic terms in constraints will fail. Only convex quadratic *objectives* (QP) are supported.
- No nonlinear functions (`exp`, `log`, `sqrt`, trig) — use Ipopt or Gurobi.

**Gurobi** (`solver="gurobi"`): Commercial (available via RAI). Best for large-scale MILP, QP, QCP. Industry-leading MILP performance, discrete + continuous + quadratic + some NLP, excellent diagnostics, multi-objective support. Params: `TimeLimit`, `MIPGap`, `MIPFocus` (0=balanced, 1=feasibility, 2=optimality, 3=bound), `Presolve` (2 for aggressive), `Threads` (0 for auto). **License required:** Gurobi requires a valid license configured in the RAI environment. If unavailable, fall back to HiGHS (LP/MILP) or Ipopt (NLP). Large MIP problems may solve significantly faster with Gurobi than HiGHS.

**MiniZinc** (`solver="minizinc"`): Open-source (Chuffed backend). Best for CP, combinatorial, constraint satisfaction. Powerful propagation, global constraints (`all_different`, `circuit`), multiple solutions. Params: `time_limit_sec`, `solution_limit`. Cannot handle continuous variables, LP, QP, NLP.

**Ipopt** (`solver="ipopt"`): Open-source. Best for continuous nonlinear optimization. Interior-point for smooth NLP, handles nonlinear objectives AND constraints. Finds local optima only. Params: `max_iter`, `max_wall_time`, `tol` (e.g. 1e-8), `print_level`, `mu_strategy`. Cannot handle integer or binary variables -- will FAIL.

### Decision Rules

Use these rules in order to pick a solver. **Gurobi outperforms open-source solvers (HiGHS, Ipopt) on every problem type it supports** — faster solve times, tighter MIP gaps, better scaling. Always prefer Gurobi when the user has a license. Only recommend open-source when Gurobi is unavailable or the problem type requires it (CSP → MiniZinc, smooth NLP → Ipopt).

1. **Check variable types first.**
   - Any integer/binary variable? Ipopt is invalid. Gurobi preferred; HiGHS if no license.
   - MiniZinc only if the problem is pure constraint satisfaction with discrete variables.

2. **Check for nonlinearity.**
   - `exp()`, `log()`, `sqrt()`, `sin()`, `cos()`, division by variables?
     HiGHS and MiniZinc are invalid.
   - Continuous-only NLP: Ipopt (best for smooth NLP) or Gurobi.
   - Discrete + nonlinear: Gurobi only.

3. **Check for quadratic constraints.**
   - Quadratic terms in constraints (not just objective): HiGHS is invalid.
   - Gurobi preferred; Ipopt if continuous-only and no Gurobi license.

4. **No objective (constraint satisfaction)?**
   - Discrete: MiniZinc (purpose-built for CSP).
   - Otherwise Gurobi or HiGHS can find feasibility.

**Quick reference:**

| Your problem has... | Gurobi available | No Gurobi license |
|---|---|---|
| Binary/integer + linear (MILP) | **Gurobi** | HiGHS |
| Binary/integer + quadratic (MIQP) | **Gurobi** | (no open-source alternative) |
| Continuous + linear (LP) | **Gurobi** | HiGHS |
| Continuous + quadratic objective (QP) | **Gurobi** | HiGHS |
| Continuous + quadratic constraints (QCP) | **Gurobi** | Ipopt |
| Continuous + nonlinear (NLP) | Ipopt | Ipopt |
| Discrete + constraint satisfaction (CSP) | MiniZinc | MiniZinc |
| Need multiple solutions | MiniZinc (best) | MiniZinc |

### Problem Size Guidelines

| Size | Variables | Constraints | Notes |
|------|-----------|-------------|-------|
| Small | < 1,000 | < 1,000 | Any formulation usually tractable |
| Medium | 1K - 100K | 1K - 100K | Formulation quality matters |
| Large | > 100K | > 100K | May need decomposition |

Each binary variable can double the search space. Tight bounds on integers reduce branching. Always ask: is integer truly required, or is rounding acceptable?

### Problem Initialization

In v1, pass the solver name as a string directly to `p.solve()` — no separate `Solver` object needed. `Problem` initialization uses type references, not strings:

```python
from relationalai.semantics import Float, Integer

p = Problem(model, Float)    # LP, NLP, MIP with continuous relaxation
p = Problem(model, Integer)  # Pure integer / constraint programming

# Solver choice depends on problem type AND user license:
p.solve("highs", time_limit_sec=60)    # LP/MIP (open-source)
p.solve("gurobi", time_limit_sec=60)   # LP/MIP/QP/QCP (license required)
p.solve("minizinc", time_limit_sec=60) # CP (open-source)
p.solve("ipopt", time_limit_sec=60)    # NLP (open-source)
```

**Do not default to any single solver.** Always select based on the problem type (see Decision Rules above) and confirm the user has the required license (Gurobi is commercial). The second argument (`Float` or `Integer`) sets the default numeric type. Variables can override with `type="bin"`, `type="int"`, or `type="cont"` in `solve_for()`.

---

## Global Constraints

Global constraints provide high-level combinatorial structure that solvers can exploit for efficient propagation. Import from the prescriptive reasoner:

```python
from relationalai.semantics.reasoners.prescriptive import all_different, implies, special_ordered_set_type_1, special_ordered_set_type_2
```

### `all_different` — pairwise distinct values

**Requires MiniZinc.** Not supported by HiGHS, Gurobi, or Ipopt. MiniZinc exploits `all_different` natively with arc consistency propagation.

Requires all variables in the group to take pairwise distinct values. Returns an `Aggregate` — use `.per()` for grouping.

```python
# Sudoku: all different per row, per column, per box
p.satisfy(
    model.require(
        all_different(x).per(i),                              # each row
        all_different(x).per(j),                              # each column
        all_different(x).per((i - 1) // side, (j - 1) // side),  # each box
    ).where(cell(i, j, x))
)
```

### `implies` — logical implication

**Requires Gurobi** (indicator constraints) **or MiniZinc.** HiGHS does not support indicator constraints — use Big-M reformulation instead (see [numerical-and-mip.md](references/numerical-and-mip.md) > Logical implication in MIP).

Creates `left => right` constraint. Returns an `Expression` (not an Aggregate — no `.per()`).

```python
# If x = 1, then y must = 1
p.satisfy(model.require(implies(x == 1, y == 1)))

# If facility is open, production must be positive
p.satisfy(model.require(implies(Facility.x_open == 1, Facility.x_production >= 1)))
```

### `special_ordered_set_type_1` — SOS1 at most one non-zero

**Requires Gurobi.** HiGHS and MiniZinc do not support SOS constraints. For HiGHS, reformulate using explicit binary variables and sum constraints instead.

At most one variable in the set can be non-zero. Used for selecting exactly one option from a group.

```python
# At most one facility in a region can be open
p.satisfy(model.require(special_ordered_set_type_1(Facility.index, Facility.x_open).per(Region)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

### `special_ordered_set_type_2` — SOS2 for piecewise linear

**Requires Gurobi.** HiGHS and MiniZinc do not support SOS constraints. For HiGHS, reformulate piecewise-linear functions using explicit binary variables for segment selection.

At most 2 variables can be non-zero, and they must be consecutive in the given order. Used for piecewise-linear approximations.

```python
# PWL: at most 2 consecutive weights non-zero
p.satisfy(model.require(special_ordered_set_type_2(Point.i, Point.w)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

### CP vs MIP Decision Guide

**When to prefer MiniZinc (CP):**
- Pure combinatorial / constraint satisfaction (Sudoku, N-Queens, scheduling)
- Heavy use of `all_different` — CP exploits it natively with arc consistency; MIP decomposes into O(n^2) pairwise inequalities
- Complex precedence / sequencing with many logical implications
- Finding ANY feasible solution matters more than proving optimality
- All variables are integer — no continuous relaxation benefit

**When to prefer HiGHS/Gurobi (MIP):**
- Mix of continuous and integer variables (allocation, flow, portfolio)
- LP relaxation provides useful quality metrics (gap, dual values, sensitivity)
- Need dual values or reduced costs for sensitivity analysis
- Large-scale problems where LP relaxation tightness drives performance
- Quadratic objectives (convex QP) — HiGHS supports convex QP objectives; MiniZinc does not

**When to prefer Ipopt (NLP):**
- Continuous nonlinear objectives or constraints (no integer variables)
- Local optimality is acceptable (Ipopt finds local optima, not global)
- Smooth differentiable functions only

**Performance rules of thumb:**
- CP scales well with tight logical constraints but poorly with loose continuous bounds
- MIP scales well when LP relaxation is tight (small integrality gap)
- For problems with both `all_different` and continuous variables, try MIP first — the continuous structure usually dominates

---

## Formulation Display

Use `p.display()` to inspect variables, objectives, and constraints before solving. Check `p.num_variables()`, `p.num_constraints()`, and `p.num_min_objectives()` / `p.num_max_objectives()` against expectations — these are now Relationships (call with parens), usable in `model.require()` engine-side ICs or queried via `model.select()`. Use `p.display(part)` for targeted inspection of a single variable group or constraint. Use `p.printed_model()` (with `print_format=` on `p.solve()`) to get LP/MPS/LaTeX text representations. The same `Problem` can be re-solved multiple times — constraints accumulate across calls.

See [formulation-display.md](references/formulation-display.md) for display output structure, diagnostic tables, and targeted inspection patterns.

---

## Pre-Solve Validation

Run five checks before calling `p.solve()`: (1) entity population — `p.num_variables() > 0`; (2) constraint population — `p.num_constraints() > 0` with at least one forcing constraint; (3) objective — exactly one `minimize`/`maximize`; (4) data integrity — no nulls, no negatives in costs/capacities, total capacity >= total demand; (5) formulation structure via `p.display()`.

```python
# Minimum pre-solve checklist — engine-side ICs fire on the next query
model.require(p.num_variables() > 0)
model.require(p.num_constraints() > 0)
model.require(p.num_min_objectives() + p.num_max_objectives() == 1)
p.display()
```

See [pre-solve-validation.md](references/pre-solve-validation.md) for full checks, diagnostic queries, and data integrity patterns.

---

## Common Compilation Errors

### Entity reference error
**Error:** "Source X.y is an entity reference to Z, not a scalar value"

The entity_creation is copying an entity reference where a scalar is expected. You must update BOTH concept_definition AND entity_creation together.

**Option A (simpler — remove the problematic property):** Remove the property from concept_definition and entity_creation entirely. Only keep properties needed for optimization.

**Option B (if you need the ID for constraints):** In concept_definition, keep Property with string type. In entity_creation, use `.id` to extract scalar: `sku_id=Demand.sku.id`.

### Type mismatch
**Error:** "declared as 'int' but source is DATE"

Property type doesn't match source column type. Fix: change the property type to match (DATE columns should use `:str` or `:date`).

### Undefined concept/property
**Error:** "Concept X not found"

Referenced concept doesn't exist in base model. Fix: use correct concept name from available concepts, or create via concept_definition.

### Zero entities created
**Symptom:** "Variables (0)" in formulation display

The entity_creation expression produced no entities — likely a join mismatch. Fix: verify join conditions match actual data relationships.

### Simplest Fix Principle

If a property is causing entity reference errors and isn't needed for the optimization constraints/objective, just REMOVE IT from both concept_definition and entity_creation. Generate a fix_action with type "modify_variable" targeting the affected variable definition, including BOTH corrected concept_definition AND entity_creation.

For numerical stability categories and MIP formulation techniques (big-M, indicator constraints), see [numerical-and-mip.md](references/numerical-and-mip.md).

---

## Diagnosing Infeasibility and Unboundedness

### Infeasibility (INFEASIBLE status)

No solution exists that satisfies all constraints simultaneously.

**Common root causes:**
1. **Minimum-per-entity vs total capacity**: N entities each requiring minimum M units, but total available is less than N*M
2. **Conflicting equality constraints**: Two constraints that cannot be satisfied simultaneously
3. **Conflicting bounds**: Variable bounds or constraints that create an empty feasible region
4. **Recently added constraints**: Focus on recently added constraints as the likely cause

**Fix strategies:** Remove or relax constraints — change `>=` to `<=`, relax bounds, convert hard constraints to soft (penalty-based).

### Unboundedness (DUAL_INFEASIBLE status)

The objective can go to +/-infinity. This is NOT about conflicting constraints — it's about missing bounds.

**Common root causes:**
1. **Missing variable upper bounds**: A variable can grow without limit, driving objective to infinity
2. **Penalty term structure**: Penalty terms like `100 * (demand - fulfilled)` can go negative if `fulfilled` exceeds `demand`. Fix: add `fulfilled <= demand`
3. **Missing capacity constraints**: Flow or production variables without upper bounds
4. **Removed constraints left gaps**: If a demand satisfaction constraint was removed, variables may now be unbounded

**Fix strategies:** Add bounds or constraints — add upper bounds to variables, add capacity limits, fix penalty term structure.

### Root Cause Taxonomy

When diagnosing infeasibility or unboundedness, classify root causes using these named codes:

| Root Cause Code | Status | Description |
|----------------|--------|-------------|
| `unbounded_variable` | DUAL_INFEASIBLE | A variable can grow without limit, driving objective to infinity |
| `missing_upper_bound` | DUAL_INFEASIBLE | Variable has no upper bound and objective incentivizes increasing it |
| `penalty_structure` | DUAL_INFEASIBLE | Penalty term can go negative (e.g., `100 * (demand - fulfilled)` when fulfilled > demand) |
| `constraint_conflict` | INFEASIBLE | Two or more constraints cannot be satisfied simultaneously |
| `capacity_mismatch` | INFEASIBLE | Total demand exceeds total capacity — no feasible allocation exists |

**Fix action types:**

| Action | When to Use |
|--------|-------------|
| `add_constraint` | Missing bounds or linking constraints; add capacity limits, conservation |
| `remove_constraint` | Conflicting or over-specified constraint causing infeasibility |
| `relax_constraint` | Constraint too tight — change `==` to `<=`/`>=`, widen bounds, add slack |
| `modify_variable` | Variable needs bounds adjusted, type changed, or expression corrected |

**Status-specific fix direction:**
- **DUAL_INFEASIBLE (unbounded):** Add bounds and constraints to LIMIT unbounded variables
- **INFEASIBLE:** Remove or relax constraints to WIDEN the feasible region

---

## Solve Execution

```python
# Solver choice depends on problem type and license — see Decision Rules above
p.solve(solver_name, time_limit_sec=60)

# Post-solve: engine-side IC validates status without querying data to the client
model.require(p.termination_status() == "OPTIMAL")

# Post-solve summary (Python-side — all metadata in one query)
si = p.solve_info()
si.display()
```

**Termination status:** `p.termination_status()` is a Relationship returning `"OPTIMAL"`, `"INFEASIBLE"`, `"UNBOUNDED"`, or `"TIME_LIMIT"`. Use in `model.require()` for engine-side validation. For Python-side access, use `p.solve_info().termination_status`.

**Python-side solve info:** `p.solve_info()` returns a `SolveInfoData` frozen dataclass with typed fields: `termination_status`, `objective_value`, `solve_time_sec`, `num_points`, `solver_version`, `printed_model`, `error`. Fetches all metadata in one query and caches it. Use for formatted output, scenario comparison, or any Python-side logic.

**Debugging failed solves:** After a non-optimal solve, check `p.error()` (Relationship) or `p.solve_info().error` (Python tuple) for the solver-level error message:

```python
p.solve("highs", time_limit_sec=60)
si = p.solve_info()
if si.termination_status != "OPTIMAL":
    print(si.error)  # Solver-level error details
```

**Checking solver version:** Use `p.solve_info().solver_version` after any solve to see the exact version that ran. Do not hardcode version numbers — they change with solver service updates.

**Post-solve constraint verification:** `p.verify(*fragments)` temporarily installs constraint ICs, triggers a query to evaluate them, and removes them. Useful for checking that the solver's solution satisfies constraints — particularly for exact solvers (HiGHS MIP, MiniZinc):

```python
coverage_ic = model.where(...).require(...)
p.satisfy(coverage_ic)
p.solve("minizinc", time_limit_sec=60)
p.verify(coverage_ic)  # Warns if any constraint is violated
```

For verifying what the solver actually sees before solving, see [formulation-display.md](references/formulation-display.md).

### First-class solve parameters

These parameters are solver-independent and work with any solver:

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_limit_sec` | float | Maximum solve time in seconds (default: 300s) |
| `silent` | bool | Suppress solver output |
| `solution_limit` | int | Maximum number of solutions to find |
| `relative_gap_tolerance` | float | Relative optimality gap in [0, 1] (e.g., 0.01 = 1%) |
| `absolute_gap_tolerance` | float | Absolute optimality gap (>= 0) |
| `log_to_console` | bool | Stream solver logs to the console during solve |
| `print_only` | bool | Print the solver model without actually solving |
| `print_format` | str | Request text representation: `"moi"`, `"latex"`, `"mof"`, `"lp"`, `"mps"`, `"nl"` |

```python
# Solver-independent options (portable across all solvers)
p.solve("highs", time_limit_sec=300, silent=True)
p.solve("highs", relative_gap_tolerance=0.01)  # 1% MIP gap
p.solve("minizinc", solution_limit=10)          # Multiple solutions

# Debugging: get LP format of the solver model
p.solve("highs", print_format="lp", print_only=True)
print(s.printed_model)  # Access the text representation
```

### Solver-specific parameters

Any additional keyword arguments are passed as raw solver-specific options. A warning is emitted when these are used (they may not be portable). Values must be `int`, `float`, `str`, or `bool`.

```python
# HiGHS-specific
p.solve("highs", time_limit_sec=120, presolve="on", threads=4)

# Gurobi-specific (note: CamelCase parameter names)
p.solve("gurobi", time_limit_sec=120, MIPFocus=1, Presolve=2, Threads=0)

# Ipopt-specific
p.solve("ipopt", time_limit_sec=60, max_iter=1000, tol=1e-8, mu_strategy="adaptive")
```

**Key solver-specific parameters:**

| Solver | Parameter | Type | Description |
|--------|-----------|------|-------------|
| HiGHS | `presolve` | str | `"choose"`, `"on"`, `"off"` |
| HiGHS | `threads` | int | Number of threads |
| Gurobi | `MIPFocus` | int | 0=balanced, 1=feasibility, 2=optimality, 3=bound |
| Gurobi | `Presolve` | int | 0=off, 1=conservative, 2=aggressive |
| Gurobi | `Threads` | int | 0=auto |
| Ipopt | `max_iter` | int | Maximum iterations |
| Ipopt | `tol` | float | Convergence tolerance (e.g., 1e-8) |
| Ipopt | `mu_strategy` | str | Barrier strategy (`"monotone"`, `"adaptive"`) |

**Prefer first-class parameters** over solver-specific equivalents: use `time_limit_sec` (not HiGHS `time_limit` or Gurobi `TimeLimit`), `relative_gap_tolerance` (not `mip_rel_gap` or `MIPGap`), `solution_limit` (not MiniZinc-specific kwargs).

**When to tune parameters:**
- Solver hits time limit → increase `time_limit_sec`, or tighten formulation first
- MIP gap too wide → tighten `relative_gap_tolerance` (costs more time)
- Solver struggles to find any feasible solution → `MIPFocus=1` (Gurobi), or relax constraints
- Large LP is slow → try `presolve="on"`, increase `threads`
- NLP converges to poor local optimum → try different `start=` values, adjust `mu_strategy`

### Unsupported operators

The following operators are **not supported by any solver backend** and will raise errors if used in solver expressions: `%` (modulo), `//` (floor division), `floor`, `ceil`, `trunc`, `round`. Note: `//` works on concrete data and property-constant combinations (e.g., `Player.p // group_size`), but fails when **both operands are decision variables**. There is no `if_then_else` operator in the prescriptive library — use `implies()` (Gurobi/MiniZinc) or Big-M reformulation (HiGHS) for conditional logic. Use piecewise-linear approximations or reformulations for unsupported operators.

> **See also:** Full operator/construct compatibility table by solver → `numerical-and-mip.md` > Operator and Construct Compatibility by Solver. Reformulation techniques (Big-M linearization, McCormick envelopes, epigraph, SOS2) → `numerical-and-mip.md` > Reformulation Techniques for Solver Compatibility.

### Cloud-based solve pipeline

v1 solve is cloud-based: the Problem serializes variable/constraint/objective data as CSV, uploads to the solver service, which reconstructs the problem in MathOptInterface (MOI) form, dispatches to the selected backend (HiGHS, Gurobi, Ipopt, MiniZinc), and returns results as CSV for import back into the model. There is no local solver — all solve calls require network connectivity to the RAI solver service.

### Re-Solve Behavior (1.0.3+)

Re-solving the same `Problem` instance is safe. Result import uses `experimental.load_data` with replace semantics — if a second solve's result import fails, previous results remain intact. No degraded state.

### Warm starting

For nonlinear solvers like Ipopt, provide initial values via the `start=` parameter in `solve_for()` to guide convergence toward a good local optimum:

```python
# Standalone variable with warm start (Rosenbrock example)
x = model.Relationship(f"{Float:x}")
y = model.Relationship(f"{Float:y}")
p.solve_for(x, name="x", lower=-100.0, upper=5.0, start=0.0)
p.solve_for(y, name="y", lower=-100.0, upper=5.0, start=0.0)
p.minimize((1 - x) ** 2 + 100 * (y - x**2) ** 2)
p.solve("ipopt", log_to_console=True)
# termination_status: "LOCALLY_SOLVED" (Ipopt finds local optima, not global)
```

**Standalone (concept-free) variables** use `model.Relationship(f"{Float:name}")` instead of `model.Property`. This pattern is for scalar optimization variables not attached to any concept (e.g., Rosenbrock, single-variable NLP). For concept-attached variables, use `model.Property` as usual.

### Scenario analysis (what-if)

Two patterns for exploring how solutions change under different assumptions:

**Pattern 1: Scenario Concept — parameter variations (preferred)**

When the same problem structure is solved with different parameter values (budget, demand,
service levels), model scenarios as a first-class Concept. One solve handles all scenarios:

```python
# Scenario with parameter data
Scenario = Concept("Scenario", identify_by={"name": String})
Scenario.min_return = Property(f"{Scenario} has {Float:min_return}")
scenario_data = model.data(
    [("conservative", 10), ("moderate", 20), ("aggressive", 30)],
    columns=["name", "min_return"],
)
model.define(Scenario.new(scenario_data.to_schema()))

# Decision variable indexed by Scenario
Stock.x_quantity = Property(f"{Stock} in {Scenario} has {Float:quantity}")
x_qty = Float.ref()

# Constraint references Scenario property
return_ok = model.where(
    Stock.x_quantity(Scenario, x_qty),
).require(
    sum(x_qty * Stock.returns).per(Scenario) >= Scenario.min_return
)

# Single solve — all scenarios simultaneously
p = Problem(model, Float)
p.solve_for(Stock.x_quantity(Scenario, x_qty), name=[Scenario.name, "qty", Stock.index])
p.satisfy(return_ok)
p.minimize(sum(risk))
p.solve("highs", time_limit_sec=60)

# Results: query with scenario filter
model.select(Scenario.name, Stock.index, Stock.x_quantity).where(
    Stock.x_quantity(Scenario, x_qty), x_qty > 0.001
).inspect()
```

**Pattern 2: Loop + where= filter — entity selection/exclusion**

When different entity subsets are tested (exclude a supplier, solve per region),
loop with `where=[]` scoping. Each iteration is an independent sub-problem:

```python
for excluded in [None, "SupplierC", "SupplierB"]:
    p = Problem(model, Float)
    if excluded:
        active = Order.supplier.name != excluded
        p.solve_for(Order.x_qty, where=[active], populate=False, ...)
    else:
        p.solve_for(Order.x_qty, populate=False, ...)
    p.maximize(...)
    p.solve("highs", time_limit_sec=60)
    # variable_values().to_df() for per-iteration results
```

**When to use which:**
- Parameter varies (budget, threshold, multiplier) → Scenario Concept (single solve)
- Entity excluded/selected → Loop + where= (multiple solves)
- Independent sub-problems (per-factory) → Loop + where= (multiple solves)

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Constraint has no decision variable | `p.satisfy(model.require(Operation.cost >= 0.01))` is a data assertion | Constraints must reference `solve_for`-registered properties |
| Cannot remove a constraint | Every `p.satisfy()` call accumulates | Create a new `Problem` for different constraint sets |
| Binary variable has no effect | Defined but not linked to quantities via big-M or capacity | Add `flow <= capacity * x_open` style linking constraints |
| Disconnected objective | Objective references variables with no constraints | Solver sets variables to bound values; add meaningful constraints |
| Wrong aggregation scope | `sum(X).per(Y)` where Y not joined to X | Add explicit relationship join in `.where()` |
| Big-M too loose → slow solve | Using arbitrary `999999` | Use tightest data-driven bound (`M = capacity`) |
| Numerical issues | Coefficients differing by >1e6 | Rescale data to similar magnitudes |

Post-solve diagnosis (trivial all-zero solutions, infeasibility root causes, quality assessment) is covered in the `solution_interpretation` skill.

## Entity Creation Diagnosis

When entity creation produces ZERO entities (cross-product or filtered concept has no instances), diagnose using this taxonomy:

**1. Non-existent concept reference:** The `entity_creation` uses a concept name that doesn't exist in the model.
- Look for typos or incorrect concept names (e.g., references "Stock2" when only "Stock" exists)
- Check against the AVAILABLE CONCEPTS list

**2. Join condition mismatch:** The `.where()` condition matches nothing.
- Check if relationship paths are valid in the model
- Check if property values actually exist in data (e.g., filtering by a status that has no matching rows)

**3. Missing relationship:** The `concept_definition` creates relationships that don't connect to data.
- Verify relationship targets exist and have entities loaded
- Check if the relationship is defined in the model schema

**4. Over-filtering:** The `.where()` clause is too restrictive.
- Multiple filter conditions that together match nothing
- Each condition alone might match rows, but the intersection is empty

**Fix requirements:**
- Use ONLY concepts from the available concepts list
- Reference actual relationships and properties from the model context
- The fix must produce entities (join/filter must match some data)
- Prefer relaxing filters over completely restructuring the entity creation

---

## Migration from v0.13

Key v0.13 to v1 migration changes: `SolverModel(model, "cont")` becomes `Problem(model, Float)`; `Solver("highs", resources=...)` / `p.solve(solver, ...)` becomes `p.solve("highs", ...)` (pass string directly); `p.variable_values().to_df()` still works (returns `name`/`value` columns), and `model.select()` also works for richer queries; `s.print()` becomes `p.display()` with optional `display(part)` for targeted inspection; `mip_rel_gap` becomes first-class `relative_gap_tolerance`; `solution_limit` is now first-class (not solver-specific); import path changes from `reasoners.optimization` to `reasoners.prescriptive`; `raiconfig.yaml` replaces TOML config. Result accessors (`termination_status`, `objective_value`, `num_variables`, etc.) changed from properties to Relationship methods — use `p.termination_status()` in `model.require()` or `p.solve_info()` for Python-side access.

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Scenario Concept | Scenario as data concept, single solve, multi-arg variables, `model.select()` results | [examples/portfolio_balancing_scenarios.py](examples/portfolio_balancing_scenarios.py) |
| Entity exclusion / partitioned | Loop + `where=[]` filter, `populate=False`, `variable_values()` results | [examples/factory_production_scenarios.py](examples/factory_production_scenarios.py) |

---

## Reference files

- Debugging numerical instability or formulating MIP problems (big-M, indicator constraints)? See [numerical-and-mip.md](references/numerical-and-mip.md) for numerical stability categories and MIP formulation techniques
- Understanding `p.display()` output or verifying what the solver actually sees? See [formulation-display.md](references/formulation-display.md) for display output structure and how to read it
- Pre-solve validation details (entity population checks, data integrity queries, copy-paste checklist)? See [pre-solve-validation.md](references/pre-solve-validation.md)
