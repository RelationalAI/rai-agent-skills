# Pattern: all-different constraint satisfaction via MiniZinc integer solver
"""
N-Queens: place n queens on an n*n chessboard such that no two queens attack each other.

Demonstrates:
- Problem(model, Integer) for pure combinatorial search via MiniZinc
- Pairwise inequality constraints with .ref() for queen pairs
- std.math.abs() for diagonal attack detection
- Symmetry breaking is optional (not shown here for simplicity)

Pattern: One integer variable per entity, pairwise constraints between entity pairs.
"""

import time

from relationalai.semantics import Integer, Model, std
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_n_queens_{time.time_ns()}")

n = 4  # Number of queens.

# --- Concepts ---
Queen = model.Concept("Queen")
Queen.row = model.Property(f"{Queen} has {Integer:row}")
model.define(Queen.new(row=std.common.range(n)))

# --- Variable: column position for each queen ---
Queen.column = model.Property(f"{Queen} is in {Integer:column}")

# --- Constraints: no two queens share column or diagonal ---
Qi = Queen
Qj = Queen.ref()
no_attacks = model.where(Qi.row < Qj.row).require(
    Qi.column != Qj.column,
    std.math.abs(Qi.column - Qj.column) != Qj.row - Qi.row,
)

# --- Problem setup ---
problem = Problem(model, Integer)
column_var = problem.solve_for(Queen.column, name=["x", Queen.row], type="int", lower=0, upper=n - 1)
problem.satisfy(no_attacks, name=["no_attack", Qi.row, Qj.row])

# --- Solve ---
problem.solve("minizinc", time_limit_sec=30)
model.select(Queen.row, Queen.column).inspect()
