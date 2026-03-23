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
from pathlib import Path

from pandas import read_csv

from relationalai.semantics import Integer, Model, std
from relationalai.semantics.reasoners.prescriptive import Problem, all_different

model = Model(f"prescriptive_sudoku_{time.time_ns()}")

side = 3  # Side length of each sub-square.
n = side**2  # Side length of board (9).

p = Problem(model, Integer)

# --- Variable: cell[i,j] = value at row i, column j (1-9) ---
i, j, x = Integer.ref().alias("i"), Integer.ref().alias("j"), Integer.ref().alias("x")
cell = model.Property(f"cell {Integer:i} {Integer:j} is {Integer:x}")
p.solve_for(
    cell(i, j, x),
    type="int",
    lower=1,
    upper=n,
    name=["x", i, j],
    where=[i == std.common.range(1, n + 1), j == std.common.range(1, n + 1)],
)

# --- Constraint: fix known cell values from puzzle data ---
fixed_csv = read_csv(Path(__file__).with_name("fixed.csv"))
fixed = model.data(fixed_csv)
fix_ic = model.where(cell(fixed.i, fixed.j, x)).require(x == fixed.fix)
p.satisfy(fix_ic)

# --- Constraint: all_different per row, column, and 3x3 sub-square ---
alldiff_ic = model.where(cell(i, j, x)).require(
    all_different(x).per(i),
    all_different(x).per(j),
    all_different(x).per((i - 1) // side, (j - 1) // side),
)
p.satisfy(alldiff_ic)

# --- Solve ---
p.solve("minizinc", time_limit_sec=30)
model.select(i, j, x).where(cell(i, j, x)).inspect()
