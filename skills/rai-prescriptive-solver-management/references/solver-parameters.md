# Table of Contents

- [Solver-Specific Parameters](#solver-specific-parameters)
- [Solve Pipeline](#solve-pipeline)
- [Re-Solve Behavior](#re-solve-behavior-103)
- [Warm Starting](#warm-starting)
- [Scenario Analysis](#scenario-analysis-what-if)

---

# Solver Parameters and Advanced Solve Topics

## Solver-Specific Parameters

Any additional keyword arguments are passed as raw solver-specific options. A warning is emitted when these are used (they may not be portable). Values must be `int`, `float`, `str`, or `bool`.

```python
# HiGHS-specific
problem.solve("highs", time_limit_sec=120, presolve="on", threads=4)

# Gurobi-specific (note: CamelCase parameter names)
problem.solve("gurobi", time_limit_sec=120, MIPFocus=1, Presolve=2, Threads=0)

# Ipopt-specific
problem.solve("ipopt", time_limit_sec=60, max_iter=1000, tol=1e-8, mu_strategy="adaptive")
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
- Solver hits time limit -> increase `time_limit_sec`, or tighten formulation first
- MIP gap too wide -> tighten `relative_gap_tolerance` (costs more time)
- Solver struggles to find any feasible solution -> `MIPFocus=1` (Gurobi), or relax constraints
- Large LP is slow -> try `presolve="on"`, increase `threads`
- NLP converges to poor local optimum -> try different `start=` values, adjust `mu_strategy`

## Solve Pipeline

Solving requires network connectivity — `problem.solve()` dispatches to the RAI solver service, which runs the selected backend (HiGHS, Gurobi, Ipopt, MiniZinc) and returns results. There is no local solver.

## Re-Solve Behavior

Re-solving the same `Problem` instance is safe. Result import uses replace semantics — if a second solve's result import fails, previous results remain intact. No degraded state.

## Warm Starting

For nonlinear solvers like Ipopt, provide initial values via the `start=` parameter in `solve_for()` to guide convergence toward a good local optimum:

```python
# Standalone variable with warm start (Rosenbrock example)
x = model.Relationship(f"{Float:x}")
y = model.Relationship(f"{Float:y}")
problem.solve_for(x, name="x", lower=-100.0, upper=5.0, start=0.0)
problem.solve_for(y, name="y", lower=-100.0, upper=5.0, start=0.0)
problem.minimize((1 - x) ** 2 + 100 * (y - x**2) ** 2)
problem.solve("ipopt", log_to_console=True)
# termination_status: "LOCALLY_SOLVED" (Ipopt finds local optima, not global)
```

**Standalone (concept-free) variables** use `model.Relationship(f"{Float:name}")` instead of `model.Property`. This pattern is for scalar optimization variables not attached to any concept (e.g., Rosenbrock, single-variable NLP). For concept-attached variables, use `model.Property` as usual.

## Scenario Analysis (What-If)

Two patterns for exploring how solutions change under different assumptions:

- **Scenario Concept** — parameter variations (budget, demand, thresholds) solved in a single solve. Results live in the ontology.
- **Loop + where= filter** — entity exclusion or partitioned sub-problems. Each iteration is independent. Use `populate=False` + `Variable.values()`.

**Decision rule:** Only parameter values change -> Scenario Concept. Entities or constraint structure change -> Loop + where=.

For full patterns, code examples, and a decision matrix, see [scenario-analysis.md](../../rai-prescriptive-problem-formulation/references/scenario-analysis.md).
