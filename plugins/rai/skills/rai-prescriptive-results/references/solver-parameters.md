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

### `solution_limit` semantics

`solution_limit=K` is a `solve(...)` kwarg, not a `solve_for(...)` kwarg. The service passes it to the solver (Ipopt refuses it with `OTHER_ERROR`) and returns at most K of the points the solver reports:

- **MiniZinc** (`Problem(model, Integer)`): up to K **distinct feasible** solutions, not top-K-optimal, ranked or diversity-maximized. `SOLUTION_LIMIT` = it found K (more may remain). `OPTIMAL` = it stopped with fewer: either the search finished, or `time_limit_sec` cut it off after at least one solution, since MiniZinc reports `TIME_LIMIT` only when it found none. If `si.solve_time_sec` reached the limit, the set may be incomplete, and the same holds for an optimization run: a 200-item knapsack cut off at 3 s reported `OPTIMAL` at 62741, against a true optimum of 65946 (relationalai 1.33.0).
- **HiGHS**: one point, and the limit can stop a MIP search early, once K improving solutions have been found. A 60-item knapsack that solves `OPTIMAL` at 1077 ends `SOLUTION_LIMIT` at 1074 with `solution_limit=1` (relationalai 1.33.0). To get alternatives from HiGHS, re-solve with the previous solution excluded instead.

**Sizing K for audit / witness enumeration:** size K **above** the expected feasible-set size, and `time_limit_sec` above the run time, so the search ends `OPTIMAL` because it finished. A `SOLUTION_LIMIT` cut-off returns a solver-dependent subset: fine for K-of-many sampling, wrong when downstream checks expect the full set. Extraction loop: [solution-extraction-details.md](solution-extraction-details.md) > Multiple Solutions.

**When to tune parameters:**
- Solver hits time limit -> increase `time_limit_sec`, or tighten formulation first
- MIP gap too wide -> tighten `relative_gap_tolerance` (costs more time)
- Solver struggles to find any feasible solution -> `MIPFocus=1` (Gurobi), or relax constraints
- Large LP is slow -> try `presolve="on"`, increase `threads`
- NLP converges to poor local optimum -> try different `start=` values, adjust `mu_strategy`

## Diagnostics by Solver (duals, basis, conflict / IIS)

`sensitivity=True` and `conflict=True` (see SKILL.md > First-class solve parameters) depend on what the chosen backend can produce:

| Capability | Available when | Not available when |
|---|---|---|
| Duals (`reduced_cost`, `shadow_price`) | LP / QP solve with an objective | MIP (integer models have no duals — empty + a warning) |
| `basis_status` | Simplex-based solve (HiGHS, Gurobi) | Interior-point (Ipopt) — no simplex basis |
| Conflict / IIS (`in_conflict`, `*_in_conflict`) | Solver supports a conflict / IIS routine | Unsupported solver → `solve_info().conflict_status == "NOT_SUPPORTED"` |

On a MIP use scenario sweeps instead of duals. A `"FAILED"` conflict carries its reason on `solve_info().error`; for `NOT_SUPPORTED` / `FAILED`, bisection is the fallback ([conflict-analysis.md](conflict-analysis.md)). Reading the populated attributes: SKILL.md > Sensitivity & conflict attributes.

## Solve Pipeline

Solving requires network connectivity — `problem.solve()` dispatches to the RAI solver service, which runs the selected backend (HiGHS, Gurobi, Ipopt, MiniZinc) and returns results. There is no local solver.

## Warm Starting

`start=` on `solve_for()` sets initial values: HiGHS, Gurobi and Ipopt use them as a warm start, and MiniZinc silently ignores them. For Ipopt they steer convergence toward a good local optimum:

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

For scenario analysis patterns (Scenario Concept, Loop + where=, Epsilon constraint loop), see [scenario-analysis.md](../../rai-prescriptive-problem/references/scenario-analysis.md).
