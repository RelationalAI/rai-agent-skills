# Pattern: multi-solution enumeration via MiniZinc — solution_limit + Variable.values + status-gated extraction + populate=False
"""
Product configurator: K=3 slots, each filled with a feature ID 1..5.

Demonstrates:
- Problem(model, Integer) + solver="minizinc" with solution_limit=MAX_WITNESSES
- populate=False to avoid first-solution write-back and FDError on re-solve
- Variable.values(sol_index, value_ref) for per-solution extraction
- Status-gated extraction (OPTIMAL or SOLUTION_LIMIT only)
- MAX_WITNESSES sized > expected feasible-set size so termination is OPTIMAL with a stable enumeration

Triggering pattern: "find K distinct valid configurations," "enumerate all builds satisfying," "show
multiple options" — the question is "give me K feasible solutions," not "give me the best one."

Distilled from product_configurator and synthetic_eligibility_records.
"""

import time

from relationalai.semantics import Integer, Model, count, std
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_multi_solution_enumeration_{time.time_ns()}")

K = 3  # number of slots in the configuration
N_FEAT = 5  # feature IDs 1..N_FEAT
MAX_WITNESSES = (
    25  # > feasible-set size so termination is OPTIMAL with stable enumeration
)

# --- Concepts ---
Slot = model.Concept("Slot", identify_by={"position": Integer})
model.define(Slot.new(position=std.common.range(1, K + 1)))

# --- Decision: which feature occupies each slot ---
Slot.feature = model.Property(f"{Slot} has {Integer:feature}")

problem = Problem(model, Integer)
slot_var = problem.solve_for(
    Slot.feature,
    type="int",
    lower=1,
    upper=N_FEAT,
    name=["feat", Slot.position],
    populate=False,
)

# --- Constraint: feature 1 and feature 5 cannot both appear (incompatibility rule) ---
has_1 = count(Slot, Slot.feature == 1)
has_5 = count(Slot, Slot.feature == 5)
problem.satisfy(model.require(has_1 + has_5 <= 1))

# --- Constraint: slots are an ordered sequence — feature in slot 1 <= slot 2 <= slot 3
# (symmetry break to make enumeration return canonical orderings, not permutations) ---
Si, Sj = Slot, Slot.ref()
problem.satisfy(
    model.where(Si.position < Sj.position).require(Si.feature <= Sj.feature)
)

# --- Solve in enumeration mode ---
problem.solve("minizinc", solution_limit=MAX_WITNESSES, time_limit_sec=30)
si = problem.solve_info()
si.display()

# --- Status-gated extraction ---
if si.termination_status not in ("OPTIMAL", "SOLUTION_LIMIT"):
    print(
        f"Solver did not enumerate solutions (status={si.termination_status}). No witnesses to extract."
    )
else:
    n_points = si.num_points or 0
    print(f"\nEnumerated {n_points} configuration(s):")
    val = Integer.ref()
    for sol_idx in range(n_points):
        df = (
            model.select(Slot.position.alias("slot"), val.alias("feature"))
            .where(slot_var.values(sol_idx, val))
            .to_df()
        )
        print(f"\n  Configuration {sol_idx}:")
        print(df.to_string(index=False))
