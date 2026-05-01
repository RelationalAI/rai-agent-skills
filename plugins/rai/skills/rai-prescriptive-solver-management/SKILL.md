---
name: rai-prescriptive-solver-management
description: Covers solver lifecycle including problem type classification, solver selection and creation, global constraints, pre-solve validation, solve execution, and solver-level diagnostics. Use when configuring or running optimization solvers, not for interpreting post-solve results.
---

# Solver Management
<!-- v1-SENSITIVE -->

## Summary

**What:** Solver lifecycle — selection, creation, formulation inspection, execution, and diagnostics.

**When to use:**
- Choosing which solver to use for a problem (HiGHS vs Gurobi vs MiniZinc vs Ipopt)
- Setting up Problem and Solver instances
- Inspecting formulation before solving (problem.display(), variable/constraint counts)
- Tuning solver parameters (time limits, MIP gap, presolve)
- Diagnosing solver-level failures (crashes, numerical instability, Big-M sizing)
- Understanding solver performance (slow convergence, presolve tuning)
- Running parametric/scenario solves

**When NOT to use:**
- Post-solve result interpretation and communication — presenting OPTIMAL/INFEASIBLE/DUAL_INFEASIBLE/TIME_LIMIT status to users, solution quality assessment, trivial solution detection, sensitivity analysis, and root-cause diagnosis of infeasibility/unboundedness — see `rai-prescriptive-results-interpretation`.
- Variable/constraint/objective formulation patterns — see `rai-prescriptive-problem-formulation`
- PyRel syntax (imports, types, properties) — see `rai-pyrel-coding`

**Overview:**
1. Understand the optimization goal — what decisions are being made, what does success look like?
2. Classify the problem type (LP / MILP / QP / NLP / CSP)
3. Select a solver (decision rules based on variable types, nonlinearity, and license availability)
4. Create Problem and Solver instances
5. Validate formulation pre-solve (problem.display(), count checks)
6. Execute solve (parameters, time limits, warm starting)
7. Diagnose solver-level issues (crashes, numerical instability, performance)

---

## Quick Reference

```python
from relationalai.semantics import Float, Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

# 1. Create Problem (Float for LP/MILP/NLP, Integer for CP)
problem = Problem(model, Float)

# 2. Register variables (type: "cont", "int", "bin"; bounds; naming)
problem.solve_for(Route.x_flow, type="cont", lower=0, upper=Route.capacity,
            name=["flow", Route.origin, Route.dest])
problem.solve_for(Facility.x_open, type="bin", name=["open", Facility.id])

# 3. Add constraints (model.require inside problem.satisfy)
problem.satisfy(model.require(sum(Route.x_flow).per(Customer) >= Customer.demand))
problem.satisfy(model.require(Route.x_flow <= Route.capacity * Facility.x_open))

# 4. Set objective (exactly one minimize or maximize)
problem.minimize(sum(Route.cost * Route.x_flow))

# 5. Pre-solve check — always inspect before solving
problem.display()
model.require(problem.num_variables() > 0)
model.require(problem.num_constraints() > 0)

# 6. Solve — solver choice depends on problem type and user license
#    See "Solver Selection" section for decision rules
problem.solve(solver_name, time_limit_sec=120)
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()
# Solvers: "highs" (LP/MILP, open-source), "gurobi" (LP/MILP/QP/QCP, license required),
#          "minizinc" (CP, open-source), "ipopt" (NLP, open-source)
# Check: problem.termination_status() → "OPTIMAL" | "INFEASIBLE" | "DUAL_INFEASIBLE" | "TIME_LIMIT"
```

### Post-Solve API

`problem.solve()` returns `None` -- do NOT assign its return value. Access solve results through separate methods:

- **Status summary:** `problem.solve_info().display()` prints a human-readable solve summary.
- **Status properties:** `problem.solve_info().termination_status` (str), `problem.solve_info().objective_value` (float).
- **Solution values (populate=True):** Query via `model.select()` — solved values are written back into model properties.
- **Solution values (populate=False):** Use `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for()`.

```python
# CORRECT usage
problem.solve("highs", time_limit_sec=60)

si = problem.solve_info()
si.display()                    # Print status summary
print(si.termination_status)    # "OPTIMAL", "INFEASIBLE", etc.

# Always check termination_status before reading objective_value or extracting
# results — si.objective_value is None on infeasible / unbounded solves and will
# silently render as "None" in print() / math / comparisons otherwise.
if si.termination_status in ("OPTIMAL", "LOCALLY_SOLVED"):
    print(si.objective_value)   # Objective function value

# For populate=False workflows, use Variable.values() (gate the extraction on
# termination_status for the same reason):
assign_var = problem.solve_for(Assignment.x, type="bin", populate=False)
problem.solve("highs")
si = problem.solve_info()
if si.termination_status in ("OPTIMAL", "LOCALLY_SOLVED"):
    value_ref = Float.ref()
    df = model.select(
        assign_var.assignment.worker.name.alias("worker"),
        value_ref.alias("value"),
    ).where(assign_var.values(0, value_ref), value_ref > 0.5).to_df()
```

> **Warning:** `result = problem.solve(...); result.status` fails because `solve()` returns `None` regardless of solver. Accessing any attribute on `None` raises `AttributeError`. Always call `problem.solve()` on its own line, then use `problem.solve_info()` separately.

---

## Read the Formulation

Before classifying or configuring, read the existing formulation (built in `rai-prescriptive-problem-formulation`) to extract solver-relevant characteristics:

1. **Variable types** — Are there integer or binary variables? (determines solver compatibility)
2. **Objective direction** — Minimize or maximize? Is feasibility the primary concern or optimality? (determines parameter tuning)
3. **Problem structure** — Are there nonlinear terms? How many entities and constraints? (determines solver choice and time limits)

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
- No nonlinear functions (`math.exp`, `math.log`, `math.sqrt`, `x**n`) — use Gurobi (preferred when licensed) or Ipopt.

**Gurobi** (`solver="gurobi"`): Commercial (available via RAI). Best for large-scale MILP, QP, QCP, and nonlinear problems. Industry-leading MILP performance, discrete + continuous + quadratic + nonlinear (`math.exp`, `math.log`, `math.sqrt`, `x ** n`), excellent diagnostics, multi-objective support. Params: `TimeLimit`, `MIPGap`, `MIPFocus` (0=balanced, 1=feasibility, 2=optimality, 3=bound), `Presolve` (2 for aggressive), `Threads` (0 for auto). **License required:** Gurobi requires a named prescriptive engine with a Snowflake secret and external access integration configured in `raiconfig.yaml`. See [rai-setup](../rai-setup/SKILL.md) for setup. If unavailable, fall back to HiGHS (LP/MILP) or Ipopt (NLP). Large MIP problems may solve significantly faster with Gurobi than HiGHS.

**MiniZinc** (`solver="minizinc"`): Open-source (Chuffed backend). Best for CP, combinatorial, constraint satisfaction. Powerful propagation, global constraints (`all_different`, `circuit`), multiple solutions. Params: `time_limit_sec`, `solution_limit`. Cannot handle continuous variables, LP, QP, NLP.

**Ipopt** (`solver="ipopt"`): Open-source. Best for continuous nonlinear optimization. Interior-point for smooth NLP, handles nonlinear objectives AND constraints. Finds local optima only. Params: `max_iter`, `max_wall_time`, `tol` (e.g. 1e-8), `print_level`, `mu_strategy`. Cannot handle integer or binary variables -- will FAIL.

### Decision Rules

Use these rules in order to pick a solver. **Gurobi outperforms open-source solvers (HiGHS, Ipopt) on every problem type it supports** — faster solve times, tighter MIP gaps, better scaling. Always prefer Gurobi when the user has a license. Only recommend open-source when Gurobi is unavailable or the problem type requires it (CSP → MiniZinc, smooth NLP → Ipopt).

1. **Check variable types first.**
   - Any integer/binary variable? Ipopt is invalid. Gurobi preferred; HiGHS if no license.
   - MiniZinc only if the problem is pure constraint satisfaction with discrete variables.

2. **Check for nonlinearity.**
   - `math.exp(x)`, `math.log(x)`, `math.sqrt(x)`, or `x ** n`?
     HiGHS and MiniZinc are invalid.
   - Continuous-only NLP: Gurobi (preferred when licensed) or Ipopt (best for smooth local NLP).
   - Discrete + nonlinear: Gurobi only.
   - Trig (`math.sin`, `math.cos`, etc.) and division between two decision variables are not lowered to the solver by the prescriptive library — reformulate as piecewise-linear approximations or via auxiliary variables.

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
| Continuous + nonlinear (NLP) | **Gurobi** or Ipopt | Ipopt |
| Discrete + constraint satisfaction (CSP) | MiniZinc | MiniZinc |
| Need multiple solutions | MiniZinc (best) | MiniZinc |

Problem size guidelines (small/medium/large thresholds) and `Problem` initialization patterns (`Problem(model, Float)` vs `Integer`, solver string names) are in [solver-details.md](references/solver-details.md). Always select solver based on problem type and confirm license availability.

---

## Global Constraints

Global constraints (`all_different`, `implies`, SOS1, SOS2) provide solver-exploitable combinatorial structure. Each has specific solver requirements:

| Constraint | Requires | Alternatives |
|---|---|---|
| `all_different` | MiniZinc | O(n^2) pairwise inequalities in MIP |
| `implies` | Gurobi or MiniZinc | Big-M reformulation for HiGHS |
| `special_ordered_set_type_1` | Gurobi | Binary variables + sum constraints |
| `special_ordered_set_type_2` | Gurobi | Binary segment selection variables |

For syntax, code examples, and a CP vs MIP decision guide, see [global-constraints.md](../rai-prescriptive-problem-formulation/references/global-constraints.md).

---

## Formulation Display

Use `problem.display()` to inspect variables, objectives, and constraints before solving. Check `problem.num_variables()`, `problem.num_constraints()`, and `problem.num_min_objectives()` / `problem.num_max_objectives()` against expectations (these are Relationships — use in `model.require()` or `model.select()`). Use `problem.display(part)` for targeted inspection of a single variable group or constraint. Use `problem.printed_model()` (Relationship, with `print_format=` on `problem.solve()`) to get LP/MPS/LaTeX text representations. The same `Problem` can be re-solved multiple times — constraints accumulate across calls.

See [formulation-display.md](references/formulation-display.md) for display output structure, diagnostic tables, and targeted inspection patterns.

---

## Pre-Solve Validation

Run five checks before calling `problem.solve()`: (1) entity population — `problem.num_variables() > 0`; (2) constraint population — `problem.num_constraints() > 0` with at least one forcing constraint; (3) objective — exactly one `minimize`/`maximize`; (4) data integrity — no nulls, no negatives in costs/capacities, total capacity >= total demand; (5) formulation structure via `problem.display()`.

```python
# Minimum pre-solve checklist
problem.display()
model.require(problem.num_variables() > 0)
model.require(problem.num_constraints() > 0)
model.require(problem.num_min_objectives() + problem.num_max_objectives() == 1)
```

See [pre-solve-validation.md](references/pre-solve-validation.md) for full checks, diagnostic queries, and data integrity patterns.

---

## Common Compilation Errors

For prescriptive-context compile errors (entity reference passed as scalar, zero entities, type mismatch, undefined concept), see [compilation-errors.md](references/compilation-errors.md). General PyRel compile errors live in `rai-pyrel-coding/references/common-pitfalls.md`. For numerical stability categories and MIP formulation techniques (big-M, indicator constraints), see [numerical-and-mip.md](references/numerical-and-mip.md).

---

## Diagnosing Infeasibility and Unboundedness

Status interpretation and prose-level diagnosis live in `rai-prescriptive-results-interpretation` > Status Interpretation (the natural reading order is status → diagnose → fix). The structured diagnostic codes that map status to fix-action types — `unbounded_variable`, `missing_upper_bound`, `penalty_structure`, `constraint_conflict`, `capacity_mismatch` — live here in [diagnostic-taxonomy.md](references/diagnostic-taxonomy.md), since they're a solver-side classification used to drive automated fix routing.

For `si.error` and `print_format=` semantics, see Solve Execution and the solve-info table below in this skill. For solver-log patterns and numerical-error categorization, see [numerical-and-mip.md](references/numerical-and-mip.md).

---

## Solve Execution

```python
# Solver choice depends on problem type and license — see Decision Rules above
problem.solve(solver_name, time_limit_sec=60)

# Post-solve: engine-side status check + Python-side summary
model.require(problem.termination_status() == "OPTIMAL")
problem.solve_info().display()
```

**Termination status:** `problem.termination_status()` (Relationship) returns a status string. Common values: `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"` (unbounded), `"LOCALLY_SOLVED"` (NLP), `"TIME_LIMIT"`, `"SOLUTION_LIMIT"`. Use in `model.require()` for engine-side checks. For Python-side access: `si = problem.solve_info()` then `si.termination_status`.

**Debugging failed solves:** After a non-optimal solve, check `problem.error()` (Relationship) or `si.error` (Python tuple) for the solver-level error message:

```python
problem.solve("highs", time_limit_sec=60)
si = problem.solve_info()
if si.termination_status != "OPTIMAL":
    print(si.error)  # Solver-level error details
```

**Checking solver version:** Use `problem.solve_info().solver_version` after any solve to see the exact version that ran. Do not hardcode version numbers — they change with solver service updates.

**Post-solve constraint verification:** `problem.verify(*fragments)` checks that the solver's solution satisfies constraints — see `rai-prescriptive-results-interpretation` > Post-solve constraint verification.

For verifying what the solver actually sees before solving, see [formulation-display.md](references/formulation-display.md).

### First-class solve parameters

These parameters are solver-independent and work with any solver:

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_limit_sec` | float | Maximum solve time in seconds (Python kwarg defaults to `None`; if not provided, the solver service applies its own default — currently 300s) |
| `silent` | bool | Suppress solver output |
| `solution_limit` | int | Maximum number of solutions to find |
| `relative_gap_tolerance` | float | Relative optimality gap in [0, 1] (e.g., 0.01 = 1%) |
| `absolute_gap_tolerance` | float | Absolute optimality gap (>= 0) |
| `log_to_console` | bool | Stream solver logs to the console during solve |
| `print_only` | bool | Print the solver model without actually solving |
| `print_format` | str | Request text representation: `"moi"`, `"latex"`, `"mof"`, `"lp"`, `"mps"`, `"nl"` |

```python
# Solver-independent options (portable across all solvers)
problem.solve("highs", time_limit_sec=300, silent=True)
problem.solve("highs", relative_gap_tolerance=0.01)  # 1% MIP gap
problem.solve("minizinc", solution_limit=10)          # Multiple solutions

# Debugging: get LP format of the solver model
problem.solve("highs", print_format="lp", print_only=True)
print(problem.solve_info().printed_model)  # Access the text representation
```

Solver-specific parameters (HiGHS, Gurobi, Ipopt kwargs), tuning guidance, cloud pipeline details, re-solve behavior, warm starting, and scenario analysis patterns are in [solver-parameters.md](references/solver-parameters.md).

### Unsupported operators

The following operators are **not lowered to the solver** and will raise errors if used inside `solve_for`/`satisfy`/`minimize`/`maximize`: `%` (modulo), `//` (floor division), `math.floor`, `math.ceil`, `math.round`, `math.sign`, `math.clip`, trig (`math.sin`, `math.cos`, `math.tan` and their hyperbolic/inverse variants), `math.factorial`, `math.erf`. Note: `//` works on concrete data and property-constant combinations (e.g., `Player.p // group_size`), but fails when **both operands are decision variables**. There is no `if_then_else` operator in the prescriptive library — use `implies()` (Gurobi/MiniZinc) or Big-M reformulation (HiGHS) for conditional logic. Use piecewise-linear approximations or reformulations for unsupported operators.

> **See also:** Full operator/construct compatibility table by solver → `numerical-and-mip.md` > Operator and Construct Compatibility by Solver. Reformulation techniques (Big-M linearization, McCormick envelopes, epigraph, SOS2) → `numerical-and-mip.md` > Reformulation Techniques for Solver Compatibility.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Constraint has no decision variable | `problem.satisfy(model.require(Operation.cost >= 0.01))` is a data assertion | Constraints must reference `solve_for`-registered properties |
| Cannot remove a constraint | Every `problem.satisfy()` call accumulates | Create a new `Problem` for different constraint sets |
| Binary variable has no effect | Defined but not linked to quantities via big-M or capacity | Add `flow <= capacity * x_open` style linking constraints |
| Disconnected objective | Objective references variables with no constraints | Solver sets variables to bound values; add meaningful constraints |
| Numerical issues | Coefficients differing by >1e6 | Rescale data to similar magnitudes |
| `problem.termination_status == "OPTIMAL"` is always False | Missing parens — `problem.termination_status` returns a bound method, not a string | Use `problem.termination_status()` (with parens) in `model.require()`, or `problem.solve_info().termination_status` for Python-side |
| `AttributeError` on `problem.solve()` return value | Assigning `result = problem.solve()` and accessing `result.status` | `problem.solve()` returns `None`. Use `problem.solve_info()` for status. For solution values, use `model.select()` (populate=True) or `Variable.values()` (populate=False). |

For formulation-time pitfalls (wrong aggregation scope, loose Big-M, missing forcing requirement, unwired relationships, etc.), see `rai-prescriptive-problem-formulation` > Common Pitfalls.

Post-solve diagnosis (trivial all-zero solutions, infeasibility root causes, quality assessment) is covered in `rai-prescriptive-results-interpretation`. The unified lifecycle failure taxonomy (`generates` → `compiles` → `solves` → `optimal` → `non-trivial` → `meaningful`) lives at `rai-prescriptive-results-interpretation/references/failure-taxonomy.md` — consult it for the `solves` and `optimal` levels.

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Scenario Concept (parameter sweep) | Scenario as data concept, single solve, multi-arg variables, `model.select()` results | [examples/scenario_concept_parameter_sweep.py](examples/scenario_concept_parameter_sweep.py) |
| Scenario Concept (multi-binary MILP) | Two binary variable types indexed by Scenario, `.per(Entity, Scenario)` grouping, cross-variable budget | [examples/scenario_concept_milp.py](examples/scenario_concept_milp.py) |
| Entity exclusion (disruption) | Loop + `where=[]` with `!=` filter to exclude entities, `populate=False`, `Variable.values()` results | [examples/entity_exclusion_disruption.py](examples/entity_exclusion_disruption.py) |
| Partitioned sub-problems (loop) | Loop + `where=[]` filter per partition, `populate=False`, `Variable.values()` results | [examples/partitioned_iteration_scenarios.py](examples/partitioned_iteration_scenarios.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Numerical stability & MIP | Numerical stability categories, big-M, indicator constraints | [numerical-and-mip.md](references/numerical-and-mip.md) |
| Formulation display | `problem.display()` output structure and how to read it | [formulation-display.md](references/formulation-display.md) |
| Pre-solve validation | Entity population checks, data integrity queries, copy-paste checklist | [pre-solve-validation.md](references/pre-solve-validation.md) |
| Scenario analysis | Scenario Concept vs Loop + where= patterns, decision matrix, code examples | [scenario-analysis.md](../rai-prescriptive-problem-formulation/references/scenario-analysis.md) |
| Solver details | Problem size guidelines, Problem initialization patterns | [solver-details.md](references/solver-details.md) |
| Compilation errors | Entity reference errors, type mismatch, zero entities, fix taxonomy | [compilation-errors.md](references/compilation-errors.md) |
| Diagnostic taxonomy | Root cause codes, fix action types, status-specific fix direction | [diagnostic-taxonomy.md](references/diagnostic-taxonomy.md) |
| Solver parameters | Solver-specific kwargs, tuning, cloud pipeline, warm starting, scenario analysis | [solver-parameters.md](references/solver-parameters.md) |
