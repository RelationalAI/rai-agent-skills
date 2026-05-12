# Global Constraints

Global constraints provide high-level combinatorial structure that solvers can exploit for efficient propagation. Import from the prescriptive reasoner:

```python
from relationalai.semantics.reasoners.prescriptive import all_different, implies, special_ordered_set_type_1, special_ordered_set_type_2
```

**Only 4 globals are callable from PyRel today:** `all_different`, `implies`, `special_ordered_set_type_1`, `special_ordered_set_type_2`. MiniZinc's native library is far richer (`circuit`, `cumulative`, `element`, `table`, `no_overlap`, `inverse`, `lex_lesseq`, ...) but those are not yet exposed.

## Per-solver coverage matrix

This table is the single source of truth for which solver supports which global. Other docs link here rather than restating.

| Constraint | PyRel-exposed | HiGHS | Gurobi | MiniZinc (Chuffed) | Ipopt |
|------------|:-:|:-:|:-:|:-:|:-:|
| `all_different` | ✓ | — | — | ✓ | — |
| `implies` | ✓ | — | ✓ | ✓ | — |
| `special_ordered_set_type_1` | ✓ | — | ✓ | — | — |
| `special_ordered_set_type_2` | ✓ | — | ✓ | — | — |

HiGHS does not support SOS as a solver feature (`highs/io/FilereaderLp.cpp:31-34` parses SOS but hard-errors with `"SOS not supported by HiGHS"`). The HiGHS.jl issue tracking SOS was closed in 2022. If MIP-side SOS is required, use Gurobi or reformulate with explicit binary variables (see `numerical-and-mip.md` > Reformulation Techniques).

## `all_different` — pairwise distinct values

**Requires MiniZinc.** Not supported by HiGHS, Gurobi, or Ipopt. MiniZinc exploits `all_different` natively with arc consistency propagation.

Requires all variables in the group to take pairwise distinct values. Returns an `Aggregate` — use `.per()` for grouping.

```python
# Sudoku: all different per row, per column, per box
problem.satisfy(
    model.require(
        all_different(x).per(i),                              # each row
        all_different(x).per(j),                              # each column
        all_different(x).per((i - 1) // side, (j - 1) // side),  # each box
    ).where(cell(i, j, x))
)
```

## `implies` — logical implication

**Requires Gurobi** (indicator constraints) **or MiniZinc.** HiGHS does not support indicator constraints — use Big-M reformulation instead (see [numerical-and-mip.md](../../rai-prescriptive-solver-management/references/numerical-and-mip.md) > Logical implication in MIP).

Creates `left => right` constraint. Returns an `Expression` (not an Aggregate — no `.per()`).

```python
# If x = 1, then y must = 1
problem.satisfy(model.require(implies(x == 1, y == 1)))

# If facility is open, production must be positive
problem.satisfy(model.require(implies(Facility.x_open == 1, Facility.x_production >= 1)))
```

## `special_ordered_set_type_1` — SOS1 at most one non-zero

**Requires Gurobi.** HiGHS and MiniZinc do not support SOS constraints. For HiGHS, reformulate using explicit binary variables and sum constraints instead.

At most one variable in the set can be non-zero. Used for selecting exactly one option from a group.

```python
# At most one facility in a region can be open
problem.satisfy(model.require(special_ordered_set_type_1(Facility.index, Facility.x_open).per(Region)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

## `special_ordered_set_type_2` — SOS2 for piecewise linear

**Requires Gurobi.** HiGHS and MiniZinc do not support SOS constraints. For HiGHS, reformulate piecewise-linear functions using explicit binary variables for segment selection.

At most 2 variables can be non-zero, and they must be consecutive in the given order. Used for piecewise-linear approximations.

```python
# PWL: at most 2 consecutive weights non-zero
problem.satisfy(model.require(special_ordered_set_type_2(Point.i, Point.w)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

## Multi-solution mode

`solution_limit=K` is a `solve(...)` kwarg, not a `solve_for(...)` kwarg. Semantics:

- **`OPTIMAL`** = the search exhausted the feasible space with at most K solutions found.
- **`SOLUTION_LIMIT`** = the search stopped at K with more feasible solutions remaining.
- The returned set is **up to K distinct feasible** solutions — NOT top-K-optimal, NOT ranked, NOT diversity-maximized.
- For a stable enumeration with `OPTIMAL` termination, size K above the expected feasible-set size.

Extract via `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for`. Pair with `populate=False` to avoid first-solution write-back errors on re-solve.

See [csp-formulation.md](csp-formulation.md) § 4 for the worked-out pattern, and `examples/multi_solution_enumeration.py` for an end-to-end example.

## `verify()` caveat for `implies`-bodied integrity constraints

> **`verify()` does not re-evaluate `implies`-bodied integrity constraints.** When an IC's body is wrapped in `implies(condition, body)`, the verify engine has no way to ground the antecedent at check time and silently returns OK — even when the IC is violated by the returned solution. This is **not** a bug in the solver; it is a documented engine limitation. For any IC whose body uses `implies` (decision-indexed table lookups in particular), add an explicit post-solve assertion in Python that re-evaluates the constraint against the extracted values. Templates that demonstrate this skip: `planogram_optimization` (planogram_optimization.py:306), `synthetic_order_lifecycle` (242-243), `synthetic_eligibility_records` (213-214).

The companion silent-failure mode is the empty-aggregate silent-drop: `sum` / `count` over an empty relation drops the IC at compile time. Detect both classes by diffing `num_constraints` / `num_min_objectives` before and after a model edit.

## MIP-style vs CSP-style — when to choose which

Many problems can be formulated either way. A Scheduling/Assignment problem with integer slot IDs and a linear cost objective can be solved either as MIP (`Problem(model, Float)` + HiGHS — bigger LP but standard solver) or CSP-style (`Problem(model, Integer)` + MiniZinc — globals + propagation, no LP gap). Choose by which solver's strengths the problem leans on. The five filters below pick the dominant strength; apply in order, first hard rule that fires decides.

### Filter 1: Continuity (hard rule)

Any continuous decision variable or continuous numeric data participating in a constraint → **MIP-style** (`Problem(model, Float)` + HiGHS/Gurobi/Ipopt). MiniZinc requires `Problem(model, Integer)`; mixing in a Float coerces the problem to MIP.

Template precedents: continuous-quantity Resource Allocation, Network Flow, and Pricing problems (e.g., `ad_spend_allocation`, `portfolio_balancing`, `production_planning`, `supply_chain_transport`). **Verify each template's `Problem(model, ...)` signature at write time before citing it** rather than trust the directory name — several CSP-shaped templates (`shift_assignment`, `book_slate_recommendation`) use `Problem(model, Integer)` and are CSP-style despite the resource-allocation framing.

### Filter 2: Expression surface (MIP is the more restrictive standard form)

MIP's standard form forbids many natural expressions: `min`/`max` in the objective or constraints, `*` on two decision variables (bilinear), `count` / `all_different` as primitives, `implies` as a direct indicator. MiniZinc accepts all of these directly. MIP requires manual reformulation:

- `minimize(max(x_i))` → introduce `t`, constrain `t >= x_i` for each `i`, then `minimize(t)`. Template precedent: `chromatic_number` (minimizes max color directly under MiniZinc).
- bilinear `x * y` → McCormick envelope, or accept a non-convex QP (Gurobi only; HiGHS rejects). Template precedent: AML motif detection (products of role flags).
- `count(X, cond)` over decision variables → sum of `1{cond}` indicators with big-M.
- `all_different` → **manual binary/disjunctive reformulation** (HiGHS) or indicator constraints (Gurobi only). MIP solvers do not consume `!=` natively as a linear inequality — the wire bridge treats it as nonlinear/logical (`Solvers.jl/src/model.jl:564`).
- `implies(decision == v, body)` → big-M reformulation in MIP. Gurobi indicator constraints require the antecedent to compare a variable to `0` or `1` (`Solvers.jl/src/model.jl:581`), so an `implies(decision_id == k, body)` with `k ∉ {0, 1}` cannot use the native Gurobi indicator path — it lowers via big-M too.

If the natural formulation uses any of these expressions, **CSP-style** saves the linearization work and produces a smaller, more readable model. Use **MIP-style** only when you've already done (or want) the linearization — e.g., the linearized form has better LP relaxation, or you need gap reporting.

`//` (floor division) and `%` (modulo) on two decision variables are **not accepted by either solver wire** — both raise compile-time errors. They are not a MIP-vs-MiniZinc differentiator.

### Filter 3: Problem mode

- Pure feasibility / "find K feasible" / property-check (counterexample search) / audit-witness / multi-solution enumeration → **CSP-style** is the natural fit (status set, `solution_limit`, `Variable.values`). Template precedents: `underwriting_audit` (INFEASIBLE = PASS), AML motif (enumerate witnesses), `patient_cohort_recruitment` (find K satisfying).
- Optimization with gap-reporting on TIME_LIMIT or provable optimality → **MIP-style** (LP relaxation gives the gap).

### Filter 4: Global constraints

Heavy use of `all_different` or many `implies` cascades → **CSP-style** exploits these natively via propagation. MIP requires manual binary/disjunctive reformulation of `all_different` (`!=` is not native in HiGHS / Solvers.jl wire — see Filter 2). Template precedents: `chromatic_number` (all_different per edge), `planogram_optimization` (implies cascade lookup).

### Filter 5: Data shape

- Sparse, structural, combinatorial / all-integer IDs → **CSP-style**.
- Dense continuous flows, network-flow with volumes, portfolio with continuous weights → **MIP-style**.
- Convex QP objective → **HiGHS** (MiniZinc has no QP).

### Performance rules of thumb

- CP/MiniZinc scales well with tight logical constraints but poorly with loose continuous bounds (which it can't take anyway).
- MIP scales well when LP relaxation is tight (small integrality gap).
- For problems with both `all_different` and continuous variables, the continuity filter (1) forces MIP; the `all_different` then needs manual reformulation per Filter 2.

For the condensed form of these filters (decision flowchart + style triggers) used at formulation time, see [csp-formulation.md](csp-formulation.md) § 1. This file holds the expanded reference table; csp-formulation.md holds the writing-time signal map.
