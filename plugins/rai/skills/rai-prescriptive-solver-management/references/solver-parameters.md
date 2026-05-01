# Table of Contents

- [Solver-Specific Parameters](#solver-specific-parameters)
- [Solve Pipeline](#solve-pipeline)
- [Re-Solve Behavior](#re-solve-behavior-sdk--103)
- [Warm Starting](#warm-starting)

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

### Complexity and time estimates

Rough heuristics for estimating solve time based on problem size and type:

| Problem class | Variable count | Estimated time | Confidence |
|---|---|---|---|
| LP (no integers) | < 1,000 | ~1s | High |
| LP | 1,000–10,000 | ~5s | Medium |
| LP | 10,000+ | ~30s | Low |
| MIP/IP | < 100 | ~2s | Medium |
| MIP/IP | 100–1,000 | ~30s | Medium |
| MIP/IP | 1,000–10,000 | ~5 min | Low |
| MIP/IP | 10,000+ | ~30 min | Very low |

**Key insight:** MIP solve time depends heavily on problem structure (LP relaxation tightness, symmetry, constraint topology), not just size. A 500-variable TSP can take longer than a 5,000-variable LP. These are rough lower bounds — actual times can vary 10x or more.

**When to recommend time limit increases:**
- Default 60s is appropriate for most problems under 5,000 variables
- For 5,000+ variable MIPs, suggest 300–600s
- If solver hits time limit with gap > 5%, suggest increasing limit or simplifying the formulation

## Solve Pipeline

Solving requires network connectivity — `problem.solve()` dispatches to the RAI solver service, which runs the selected backend (HiGHS, Gurobi, Ipopt, MiniZinc) and returns results. There is no local solver.

## Re-Solve Behavior (SDK >= 1.0.3)

Re-solving the same `Problem` instance is safe. After adding more constraints / variables / objective terms, calling `problem.solve()` again re-runs the solver and updates variable values. If the second solve fails, previous results remain intact — no degraded state.

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

For scenario analysis patterns (Scenario Concept, Loop + where=, Epsilon constraint loop), see [scenario-analysis.md](../../rai-prescriptive-problem-formulation/references/scenario-analysis.md).
