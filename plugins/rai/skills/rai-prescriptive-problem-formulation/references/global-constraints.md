# Global Constraints

Global constraints provide high-level combinatorial structure that solvers can exploit for efficient propagation. Import from the prescriptive reasoner:

```python
from relationalai.semantics.reasoners.prescriptive import all_different, implies, special_ordered_set_type_1, special_ordered_set_type_2
```

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

## CP vs MIP Decision Guide

**When to prefer MiniZinc (CP):**
- Pure combinatorial / constraint satisfaction (Sudoku, N-Queens, scheduling)
- Heavy use of `all_different` — CP exploits it natively with arc consistency; MIP decomposes into O(n^2) pairwise inequalities
- Complex precedence / sequencing with many logical implications
- Finding ANY feasible solution matters more than proving optimality
- All variables are integer — no continuous relaxation benefit

**When to prefer HiGHS/Gurobi (MIP):**
- Mix of continuous and integer variables (allocation, flow, portfolio)
- LP relaxation provides useful quality signal (gap reporting on TIME_LIMIT)
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
