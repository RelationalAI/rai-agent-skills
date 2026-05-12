# Pattern: integer slot in {1..K+1} with K+1 = "unpicked" sentinel + count over decision-dependent filter
"""
Book slate recommendation: K=4 slots, M=6 books. Each slot picks a book id 1..M, or the sentinel M+1
("no book"). Objective: maximize total slot revenue, computed by an implies cascade lookup.

Demonstrates:
- Integer slot in {1..M+1} where M+1 is the "unpicked" sentinel — one variable carries both
  the cardinality (how many slots picked book b) and the position (which slot)
- count(X, condition) with a decision-dependent filter as the second argument — the filter lives
  INSIDE the count, not in an outer where (would prune the search instead of counting)
- Symmetry break: slots are ordered (slot i's book id <= slot j's id when i < j) so distinct
  assignments aren't recounted as permutations
- Solver chooses to fill slots when revenue is positive — the sentinel falls out naturally

Triggering pattern: "choose K of these (or fewer)," "fill K positions with items from a catalog,"
"K cells each get one value from a domain." The K+1 sentinel keeps the variable integer rather
than introducing a separate binary "is-filled" flag per slot.

Distilled from book_slate_recommendation.
"""

import time

import pandas as pd

from relationalai.semantics import Float, Integer, Model, count, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

model = Model(f"prescriptive_integer_slot_with_sentinel_{time.time_ns()}")

K = 4  # number of slots
M = 6  # number of books in the catalog
SENTINEL = (
    M + 1
)  # "no book" — must be inside the decision domain so the solver can pick it

# --- Concepts ---
Slot = model.Concept("Slot", identify_by={"position": Integer})
model.define(Slot.new(position=std.common.range(1, K + 1)))

Book = model.Concept("Book", identify_by={"id": Integer})
Book.revenue = model.Property(f"{Book} has {Float:revenue}")

book_data = pd.DataFrame(
    [(1, 30.0), (2, 25.0), (3, 18.0), (4, 12.0), (5, 8.0), (6, 5.0)],
    columns=["id", "revenue"],
)
model.define(Book.new(model.data(book_data).to_schema()))

# --- Decision: which book id occupies each slot (or sentinel) ---
Slot.x_book = model.Property(f"{Slot} contains {Integer:book_id}")
Slot.x_revenue = model.Property(f"{Slot} earns {Float:slot_revenue}")

problem = Problem(model, Integer)
problem.solve_for(
    Slot.x_book,
    type="int",
    lower=1,
    upper=SENTINEL,
    name=["slot_book", Slot.position],
)
problem.solve_for(
    Slot.x_revenue,
    type="cont",
    lower=0.0,
    name=["slot_rev", Slot.position],
)

# --- Constraint: no book duplicated across slots ---
# count over decision-dependent filter: the filter is inside count's 2nd arg.
# An outer where(Slot.x_book == Book.id) would prune the feasible search rather than count it.
problem.satisfy(model.require(count(Slot, Slot.x_book == Book.id).per(Book) <= 1))

# --- Constraint: implies cascade binds revenue to chosen book ---
problem.satisfy(
    model.require(implies(Slot.x_book == Book.id, Slot.x_revenue == Book.revenue))
)
# Sentinel earns 0 revenue
problem.satisfy(model.require(implies(Slot.x_book == SENTINEL, Slot.x_revenue == 0.0)))

# --- Constraint: symmetry break — slot positions are ordered (no permutation re-counting) ---
Si, Sj = Slot, Slot.ref()
problem.satisfy(model.where(Si.position < Sj.position).require(Si.x_book <= Sj.x_book))

# --- Objective: maximize total slot revenue ---
problem.maximize(sum(Slot.x_revenue))

problem.solve("minizinc", time_limit_sec=30)
problem.solve_info().display()

print("\nFinal slate (sentinel = 'no book'):")
model.select(Slot.position, Slot.x_book, Slot.x_revenue).inspect()
