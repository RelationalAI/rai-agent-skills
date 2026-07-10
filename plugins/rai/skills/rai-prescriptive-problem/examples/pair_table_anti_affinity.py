# Pattern: pairwise no-co-location via symmetric pair table
"""
Item-to-slot assignment with forbidden-pair constraints: 6 items assigned across 3 slots
(an item assigns to at most one slot; a slot can hold multiple items). A symmetric pair
table lists item pairs that cannot share a slot.

Demonstrates:
- Forbidden-pair table populated symmetrically (each forbidden pair stored once in data,
  expanded to both orientations in the relation) — see `chromatic_number.py` for the same
  symmetric-expansion mechanic on a graph adjacency.
- Anti-affinity IC: for every ordered pair (Ii, Ij) with `Ii.id < Ij.id` whose pair is
  in the forbidden table, at most one of (Ii, Ij) is in any given slot: `xi + xj <= 1`.
  The `Ii.id < Ij.id` half-pair filter prevents the solver from generating both
  (Ii, Ij) and (Ij, Ii) instances of the same constraint.
- Per-slot binary 2D assignment matrix `Item.in_slot(Slot, x)` with value-ref binding.
- CP-friendly shape: O(1) propagator per (pair, slot) tuple — no big-M required.

Triggering pattern: "X and Y cannot share a resource," "tenants A and B forbidden in same
zone," "two products can't occupy the same shelf," "anti-affinity / mutual exclusion over
a curated pair list." Whenever the IC reads "for every pair in this list, at most one
goes to each location," this is the form.

Distilled from `pod_placement` template (tenant anti-affinity over a symmetric pair table).
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_pair_table_anti_affinity_{time.time_ns()}")

N_ITEMS = 6
N_SLOTS = 3

# --- Concepts ---
Item = model.Concept("Item", identify_by={"id": Integer})
Slot = model.Concept("Slot", identify_by={"id": Integer})

item_data = pd.DataFrame([(i,) for i in range(1, N_ITEMS + 1)], columns=["id"])
slot_data = pd.DataFrame([(i,) for i in range(1, N_SLOTS + 1)], columns=["id"])
model.define(Item.new(model.data(item_data).to_schema()))
model.define(Slot.new(model.data(slot_data).to_schema()))

# Forbidden pairs: (1, 2), (1, 4), (3, 5). Stored once; the relation expands symmetrically.
forbidden_data = pd.DataFrame(
    [(1, 2), (1, 4), (3, 5)],
    columns=["a", "b"],
)
ForbiddenRaw = model.Concept("ForbiddenRaw", identify_by={"a": Integer, "b": Integer})
model.define(ForbiddenRaw.new(model.data(forbidden_data).to_schema()))

# --- Symmetric pair relation populated from the one-way raw data ---
Forbidden = model.Relationship(f"{Item:a} is forbidden with {Item:b}")
Ia = Item.ref()
Ib = Item.ref()
model.define(Forbidden(Ia, Ib)).where(Ia.id == ForbiddenRaw.a, Ib.id == ForbiddenRaw.b)
model.define(Forbidden(Ia, Ib)).where(Ia.id == ForbiddenRaw.b, Ib.id == ForbiddenRaw.a)

# --- Decision: 2D binary assignment matrix Item.in_slot(Slot, x) ---
Item.in_slot = model.Property(f"{Item} occupies {Slot} if {Integer:assigned}")

problem = Problem(model, Integer)
x = Integer.ref()
problem.solve_for(Item.in_slot(Slot, x), type="bin", name=["assign", Item.id, Slot.id])

# --- Constraint: each item is in at most one slot ---
problem.satisfy(
    model.where(Item.in_slot(Slot, x)).require(sum(x).per(Item) <= 1)
)

# --- Anti-affinity IC: forbidden pairs cannot co-locate on any slot ---
# For every (Ii, Ij) pair in Forbidden with Ii.id < Ij.id (half-pair filter), and every Slot:
# at most one of xi (Ii's bit for this slot) and xj (Ij's bit for this slot) is 1.
Ii = Item
Ij = Item.ref()
xi = Integer.ref()
xj = Integer.ref()
problem.satisfy(
    model.where(
        Ii.id < Ij.id,
        Forbidden(Ii, Ij),
        Ii.in_slot(Slot, xi),
        Ij.in_slot(Slot, xj),
    ).require(xi + xj <= 1)
)

# --- Objective: maximize number of items placed ---
problem.maximize(sum(x).where(Item.in_slot(Slot, x)))

problem.solve("minizinc", time_limit_sec=30)
problem.solve_info().display()

print("\nFinal placement:")
model.select(Item.id, Slot.id, x).where(Item.in_slot(Slot, x), x > 0.5).inspect()
