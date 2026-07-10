# Pattern: reified cardinality forcing all-or-nothing group placement
"""
Group placement: 4 groups, each with `replicas` members. Each member is assigned to at most one
of 5 slots. Constraint: every group is either fully placed (every member assigned) or fully
unplaced (no member assigned). No partial placements.

Demonstrates:
- Reified cardinality IC: `sum(Member.placed).per(Group) == Group.replicas * Group.placed`.
  Reads as "placed-replica count == replicas × group_placed_flag." Because both sides are
  bound to binary aggregates and `Group.placed` is itself a 0/1 decision, the IC forces:
    - `Group.placed == 0`: zero replicas placed.
    - `Group.placed == 1`: exactly `replicas` placed — all of them.
  Anything in between (e.g., 2 of 3 placed) is infeasible.
- 2D binary assignment matrix `Member.in_slot(Slot, x)` coupled to a per-member 0/1
  placement indicator `Member.placed` via `sum(x).per(Member) == Member.placed`.
- Per-group placement indicator `Group.placed` decision variable.
- Objective: maximize total groups placed (linear in `Group.placed`).

Triggering pattern: "all replicas of a deployment placed or none," "all parts of a kit
shipped together or not at all," "fleet assignment must be unanimous," "atomic group
commit." Whenever the IC reads "for each group, either ALL members satisfy condition X
or NONE do," reified cardinality is the linear-arithmetic form.

Cleaner than per-member implies cascades: `implies(Group.placed == 1, Member.placed == 1)`
× N members works but introduces N reified clauses; the reified-cardinality form is a
single arithmetic IC per group.

Distilled from `pod_placement` template (gang placement of pod replicas).
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_gang_atomicity_{time.time_ns()}")

N_GROUPS = 4
N_SLOTS = 5

# --- Concepts and inline data ---
Slot = model.Concept("Slot", identify_by={"id": Integer})
slot_data = pd.DataFrame(
    [(i, 2) for i in range(1, N_SLOTS + 1)],  # each slot has capacity 2
    columns=["id", "capacity"],
)
Slot.capacity = model.Property(f"{Slot} has {Integer:capacity}")
model.define(Slot.new(model.data(slot_data).to_schema()))

Group = model.Concept("Group", identify_by={"id": Integer})
Group.replicas = model.Property(f"{Group} has {Integer:replicas}")
group_data = pd.DataFrame(
    [(1, 2), (2, 3), (3, 2), (4, 1)],
    columns=["id", "replicas"],
)
model.define(Group.new(model.data(group_data).to_schema()))

Member = model.Concept("Member", identify_by={"id": Integer})
Member.group = model.Property(f"{Member} belongs to {Group}")
# 8 members total: group 1 has 2 (ids 1-2), group 2 has 3 (3-5), group 3 has 2 (6-7), group 4 has 1 (8).
member_df = pd.DataFrame(
    [(1, 1), (2, 1), (3, 2), (4, 2), (5, 2), (6, 3), (7, 3), (8, 4)],
    columns=["id", "group_id"],
)
member_data = model.data(member_df)
model.define(Member.new(id=member_data.id))
model.define(Member.group(Group)).where(
    Member.id == member_data.id, Group.id == member_data.group_id
)

# --- Decisions ---
Member.in_slot = model.Property(f"{Member} is in {Slot} if {Integer:assigned}")
Member.placed = model.Property(f"{Member} is {Integer:placed}")
Group.placed = model.Property(f"{Group} is {Integer:placed}")

problem = Problem(model, Integer)
x = Integer.ref()
problem.solve_for(Member.in_slot(Slot, x), type="bin", name=["assign", Member.id, Slot.id])
problem.solve_for(Member.placed, type="bin", name=["m_placed", Member.id])
problem.solve_for(Group.placed, type="bin", name=["g_placed", Group.id])

# --- Coupling: per-member assignment row sum == placement indicator ---
problem.satisfy(
    model.where(Member.in_slot(Slot, x)).require(sum(x).per(Member) == Member.placed)
)

# --- Slot capacity ---
problem.satisfy(
    model.where(Member.in_slot(Slot, x)).require(sum(x).per(Slot) <= Slot.capacity)
)

# --- Gang atomicity IC (the focal pattern) ---
# placed-replica count == replicas × group_placed_flag.
# Group.placed == 0 ⇒ zero replicas placed.  Group.placed == 1 ⇒ all `replicas` placed.
gang_atomicity_ic = model.where(Member.group == Group).require(
    sum(Member.placed).per(Group) == Group.replicas * Group.placed
)
problem.satisfy(gang_atomicity_ic)

# --- Objective: maximize placed groups ---
problem.maximize(sum(Group.placed))

problem.solve("minizinc", time_limit_sec=30)
problem.solve_info().display()

print("\nPlaced groups (Group.placed == 1):")
model.select(Group.id, Group.replicas, Group.placed).where(Group.placed > 0.5).inspect()

print("\nMember-to-slot assignments:")
model.select(Member.id, Slot.id, x).where(Member.in_slot(Slot, x), x > 0.5).inspect()
