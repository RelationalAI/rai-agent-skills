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

HiGHS does not support SOS as a solver feature — passing SOS to HiGHS raises `"SOS not supported by HiGHS"`. If MIP-side SOS is required, use Gurobi or reformulate with explicit binary variables (see `numerical-and-mip.md` > Reformulation Techniques).

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

## `verify()` caveat for solver-only IC bodies

`verify()` silently returns OK on ICs whose body is a solver-only construct (`implies`-bodied or `all_different`-bodied), even when the IC is violated by the returned solution. The verify engine cannot ground these wire-format constraint relations at check time. The companion silent-failure mode is the empty-aggregate silent-drop (`sum` / `count` over an empty relation drops the IC at compile time).

See [csp-formulation.md](csp-formulation.md) § 6 for the three regimes (mixed; all solver-only; `populate=False`) and the post-solve-assertion pattern.

## MIP-style vs CSP-style — when to choose which

Many problems can be formulated either way. A Scheduling/Assignment problem with integer slot IDs and a linear cost objective can be solved either as MIP (`Problem(model, Float)` + HiGHS — bigger LP but standard solver) or CSP-style (`Problem(model, Integer)` + MiniZinc — globals + propagation, no LP gap). Filter 1 (continuity) is a hard rule; the other filters surface the dominant signal for each style, but most problems land in the gray zone where both styles work and the choice is a modeling preference.

### Filter 1: Continuity (hard rule)

Any continuous decision variable or continuous numeric data participating in a constraint → **MIP-style** (`Problem(model, Float)` + HiGHS/Gurobi/Ipopt). MiniZinc requires `Problem(model, Integer)`; mixing in a Float coerces the problem to MIP.

Template precedents: continuous-quantity Resource Allocation, Network Flow, and Pricing problems (e.g., `ad_spend_allocation`, `portfolio_balancing`, `production_planning`, `supply_chain_transport`). **Verify each template's `Problem(model, ...)` signature at write time before citing it** rather than trust the directory name — several CSP-shaped templates (`shift_assignment`, `book_slate_recommendation`) use `Problem(model, Integer)` and are CSP-style despite the resource-allocation framing.

### Filter 2: Expression surface

MiniZinc accepts these expressions directly; MIP requires linearization:

- `minimize(max(x_i))` → introduce `t`, constrain `t >= x_i` for each `i`, then `minimize(t)`. Template precedent: `chromatic_number` (minimizes max color directly under MiniZinc).
- bilinear `x * y` → McCormick envelope, or accept a non-convex QP (Gurobi only; HiGHS rejects). Template precedent: AML motif detection (products of role flags).
- `count(X, cond)` over decision variables → sum of `1{cond}` indicators with big-M.
- `all_different` and `!=` / `==` between decision variables → the MIP wire does not consume `!=` natively as a linear inequality (the wire bridge treats it as nonlinear/logical). Pairwise binary indicators with big-M are required. The same root cause makes pairwise `count(r, g0 == g1) <= 1` over two decision-variable refs (the social-golfer shape) tedious in MIP.
- `implies(decision == v, body)` → big-M reformulation in MIP. Gurobi indicator constraints require the antecedent to compare a variable to `0` or `1`; binary-antecedent `implies(x == 0, body)` / `implies(x == 1, body)` uses the native indicator path (typically faster than big-M), but `implies(decision_id == k, body)` with `k ∉ {0, 1}` lowers to big-M even on Gurobi. HiGHS lowers all `implies` to big-M via the wire's bridge mechanism.

Either style works for these expressions. CSP-style writes them directly; MIP-style produces a more standard form. `all_different` and pairwise decision-variable equality are the cases where CSP-style is markedly easier to write — for the other expressions the wire applies the linearization automatically, so the choice is shorter source vs. more standard form.

`//` (floor division) and `%` (modulo) on two decision variables are **not accepted by either solver wire** — both raise compile-time errors. They are not a MIP-vs-MiniZinc differentiator.

### Filter 3: Problem mode

- Multi-solution enumeration via `solution_limit=K` + `Variable.values(sol_index, val)` → **CSP-style** (only exposed on the MiniZinc path in PyRel today; theoretical alternatives like Gurobi solution pools or re-solve with no-good cuts exist but aren't surfaced). Template precedents: `multi_solution_enumeration` (K-of-feasible), AML motif (enumerate witnesses).
- Audit / witness / counterexample search → CSP-style API is the natural match (status set, `Variable.values` extraction). MIP can express the same logic via `minimize(0)` and INFEASIBLE/OPTIMAL semantics for single witnesses. Template precedents: `underwriting_audit` (INFEASIBLE = PASS), `patient_cohort_recruitment` (find K satisfying).
- Optimization where an LP-relaxation gap on `TIME_LIMIT` is useful → **MIP-style** (LP relaxation gives the gap). MiniZinc reports best-incumbent + search progress without an LP-style gap. Both families prove optimality when the search completes.

### Filter 4: Global constraints

- Any use of the `all_different` callable → **CSP-style**. Per the per-solver matrix, only MiniZinc supports `all_different`; the same semantics can be hand-modeled in MIP via pairwise binary indicators + big-M (`!=` not native in the MIP wire — see Filter 2).
- Any use of `special_ordered_set_type_1` / `special_ordered_set_type_2` → **MIP-style with Gurobi**. Per the matrix, only Gurobi supports SOS; HiGHS and MiniZinc do not. For HiGHS, hand-model with explicit binary indicators (see SOS1/SOS2 sections above).
- Many `implies` cascades with non-binary antecedents (`decision_id == k` for `k ∉ {0, 1}`) → both styles big-M; CSP-style writes shorter. Binary-antecedent `implies(x == 0, body)` / `implies(x == 1, body)` with Gurobi uses native indicator constraints.

Template precedents: `chromatic_number` (per-edge `!=`), `sudoku` (`all_different` per row/column/box), `planogram_optimization` (`implies` cascade lookup).

### Filter 5: Data shape

- Sparse, structural, combinatorial / all-integer IDs → **CSP-style** is a natural fit.
- Dense continuous flows, network-flow with volumes, portfolio with continuous weights → forced to **MIP-style** by Filter 1 anyway.
- Convex QP objective → **HiGHS** or **Gurobi** (MiniZinc has no QP).

### Performance rules of thumb

- Both families can prove optimality — CP by completing the search tree on bounded discrete domains (tight bounds matter for CP performance), MIP by closing the gap via branch-and-bound.
- MIP tends to win when the LP relaxation is tight (small integrality gap).
- CP tends to win on heavily logical / global-constraint structure (`all_different`, pairwise equality counts).
- Gurobi is typically faster than HiGHS where both apply.
- For problems with both `all_different` and continuous variables, the continuity filter (1) forces MIP; the `all_different` then needs manual reformulation per Filter 2.
- If performance matters on a specific instance, try both styles and measure.

For the condensed form of these filters used at formulation time, see [csp-formulation.md](csp-formulation.md) § 1. This file holds the expanded reference table; csp-formulation.md holds the writing-time signal map.
