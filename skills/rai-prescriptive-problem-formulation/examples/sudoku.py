# Pattern: grid constraint satisfaction with block partitioning via MiniZinc
"""
Sudoku: fill a 9x9 grid so each row, column, and 3x3 box contains digits 1-9.

Demonstrates:
- Problem(model, Integer) for constraint satisfaction via MiniZinc
- all_different global constraint with .per() grouping
- Standalone multiarity properties as variables (cell grid)
- Integer.ref() for dimension references
- Fixing variables from external data
- std.common.range() for domain specification

Pattern: Standalone property variables + all_different per group.
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, std
from relationalai.semantics.reasoners.prescriptive import Problem, all_different

model = Model(f"prescriptive_sudoku_{time.time_ns()}")

side = 3  # Side length of each sub-square.
n = side**2  # Side length of board (9).

problem = Problem(model, Integer)

# --- Variable: cell[i,j] = value at row i, column j (1-9) ---
i, j, x = Integer.ref().alias("i"), Integer.ref().alias("j"), Integer.ref().alias("x")
cell = model.Property(f"cell {Integer:i} {Integer:j} is {Integer:x}")
cell_var = problem.solve_for(
    cell(i, j, x),
    type="int",
    lower=1,
    upper=n,
    name=["x", i, j],
    where=[i == std.common.range(1, n + 1), j == std.common.range(1, n + 1)],
)

# --- Constraint: fix known cell values from puzzle data ---
# Inline puzzle: a standard 9x9 Sudoku with 28 givens
fixed_csv = pd.DataFrame(
    [
        (1, 1, 5),
        (1, 2, 3),
        (1, 5, 7),
        (2, 1, 6),
        (2, 4, 1),
        (2, 5, 9),
        (2, 6, 5),
        (3, 2, 9),
        (3, 3, 8),
        (3, 8, 6),
        (4, 1, 8),
        (4, 5, 6),
        (4, 9, 3),
        (5, 1, 4),
        (5, 4, 8),
        (5, 6, 3),
        (5, 9, 1),
        (6, 1, 7),
        (6, 5, 2),
        (6, 9, 6),
        (7, 2, 6),
        (7, 7, 2),
        (7, 8, 8),
        (8, 4, 4),
        (8, 5, 1),
        (8, 6, 9),
        (8, 9, 5),
        (9, 5, 8),
        (9, 8, 7),
        (9, 9, 9),
    ],
    columns=["i", "j", "fix"],
)
fixed = model.data(fixed_csv)
fix_ic = model.where(cell(fixed.i, fixed.j, x)).require(x == fixed.fix)
problem.satisfy(fix_ic)

# --- Constraint: all_different per row, column, and 3x3 sub-square ---
alldiff_ic = model.where(cell(i, j, x)).require(
    all_different(x).per(i),
    all_different(x).per(j),
    all_different(x).per((i - 1) // side, (j - 1) // side),
)
problem.satisfy(alldiff_ic)

# --- Solve ---
problem.solve("minizinc", time_limit_sec=30)
model.select(i, j, x).where(cell(i, j, x)).inspect()
