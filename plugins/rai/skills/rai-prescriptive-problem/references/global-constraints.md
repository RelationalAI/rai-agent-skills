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
| `implies` | ✓ | bounded vars | ✓ | ✓ | — |
| `special_ordered_set_type_1` | ✓ | bounded vars | ✓ | bounded vars | — |
| `special_ordered_set_type_2` | ✓ | bounded vars | ✓ | bounded vars | — |

"bounded vars": the solver has no native form of the constraint, so the solver service rewrites it into binaries, which needs finite `lower=`/`upper=` on the variables involved. Without them the solve raises `RuntimeError: ... backend.failed`.

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

**Gurobi** (indicator constraints) **or MiniZinc**, or **HiGHS on bounded variables**: HiGHS has no indicator constraints, so the solver service rewrites `implies` to big-M, which needs finite `lower=`/`upper=` on the variables in the consequent (without them the solve raises `RuntimeError: ... backend.failed`). Writing the big-M yourself: [numerical-and-mip.md](numerical-and-mip.md) > Logical implication in MIP.

Creates `left => right` constraint. Returns an `Expression` (not an Aggregate — no `.per()`).

Every solver but MiniZinc rejects an antecedent other than `x == 0` / `x == 1` on a single variable `x`, and a consequent that is not a single (in)equality: `The implies condition must compare to 0 or 1.` (or `The implies consequent must be an (in)equality with two arguments.`). MiniZinc takes general antecedents such as `implies(Position.x_assort == Assortment.id, ...)` ([csp-formulation.md](csp-formulation.md) § 3d).

```python
# If x = 1, then y must = 1
problem.satisfy(model.require(implies(x == 1, y == 1)))

# If facility is open, production must be positive
problem.satisfy(model.require(implies(Facility.x_open == 1, Facility.x_production >= 1)))
```

## `special_ordered_set_type_1` — SOS1 at most one non-zero

Gurobi, or HiGHS / MiniZinc on bounded variables (see the matrix).

At most one variable in the set can be non-zero. Used for selecting exactly one option from a group.

```python
# At most one facility in a region can be open
problem.satisfy(model.require(special_ordered_set_type_1(Facility.index, Facility.x_open).per(Region)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

## `special_ordered_set_type_2` — SOS2 for piecewise linear

Gurobi, or HiGHS / MiniZinc on bounded variables (see the matrix).

At most 2 variables can be non-zero, and they must be consecutive in the given order. Used for piecewise-linear approximations.

```python
# PWL: at most 2 consecutive weights non-zero
problem.satisfy(model.require(special_ordered_set_type_2(Point.i, Point.w)))
```

Arguments: `(index_expression, variable_expression)` where `index` defines the ordering.

## `verify()` caveat for solver-only IC bodies

`verify()` silently returns OK on `implies`- and `all_different`-bodied ICs even when the solution violates them; how to check them instead: [csp-formulation.md](csp-formulation.md) § 6.

## MIP-style vs CSP-style — when to choose which

[SKILL.md](../SKILL.md) > MIP-style vs CSP-style, plus the CSP-specific signals in [csp-formulation.md](csp-formulation.md) § 1.
