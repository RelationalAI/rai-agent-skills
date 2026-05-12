# Pattern: implies cascade as decision-indexed table lookup + integer-ID membership IC + lookup-totality check
"""
Planogram-style placement: P=4 shelf positions, each picks an assortment id from a reference table.
An implies cascade looks up revenue per chosen assortment; objective maximizes total revenue.

This example demonstrates the safe form of a common silent-failure pattern: when an integer decision
variable is bounded only by `lower=min(id), upper=max(id)`, the solver is free to pick any integer
in that range — INCLUDING ids not present in the reference data. If the implies cascade is
non-total over the decision's domain, the bound aux variable stays silently unconstrained for the
uncovered values, and verify() does NOT catch this (see § 6 of csp-formulation.md).

Demonstrates:
- Explicit integer-ID membership IC (Form A in § 2c of csp-formulation.md)
- Pre-solve lookup-totality assertion (Form B option — verifies decision domain matches reference set)
- implies cascade binding an auxiliary revenue variable to the chosen row's value
- verify() limitation on implies-bodied ICs (warning in the docstring; documented in csp-formulation.md § 6)
- Post-solve assertion in Python that re-evaluates the implies-body against extracted values

Triggering pattern: "predict-then-optimize over a tabular lookup," "decision selects a row,
properties are looked up from that row." Without the membership IC + totality check, the failure mode
is: solver picks an uncovered id, lookup never fires for it, objective uses an unconstrained variable
that takes whatever value optimizes — typically the bound, producing a confident wrong answer.

Distilled from planogram_optimization. Cross-references underwriting_audit for the integer-ID membership IC.
"""

import time

import pandas as pd

from relationalai.semantics import Float, Integer, Model, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem, implies

model = Model(f"prescriptive_implies_table_lookup_{time.time_ns()}")

P = 4  # number of shelf positions

# --- Concepts ---
Position = model.Concept("Position", identify_by={"index": Integer})
model.define(Position.new(index=std.common.range(1, P + 1)))

Assortment = model.Concept("Assortment", identify_by={"id": Integer})
Assortment.revenue = model.Property(f"{Assortment} has {Float:revenue}")

# Reference table — note ids are 10..14 (dense, no gaps). The decision variable's bounds below match
# this dense range; we still add the explicit membership IC defensively.
assort_data = pd.DataFrame(
    [(10, 200.0), (11, 150.0), (12, 175.0), (13, 90.0), (14, 240.0)],
    columns=["id", "revenue"],
)
model.define(Assortment.new(model.data(assort_data).to_schema()))

MIN_ID, MAX_ID = 10, 14

# --- Pre-solve lookup-totality check (Form B in § 2c) ---
# Verify the decision's [MIN_ID..MAX_ID] range matches the reference rows exactly.
decision_domain_size = MAX_ID - MIN_ID + 1
ref_id_count = len(model.select(Assortment.id).to_df())
assert decision_domain_size == ref_id_count, (
    f"implies-cascade lookup is non-total: decision domain has {decision_domain_size} values "
    f"but reference table has {ref_id_count} rows. Either restrict the decision domain or expand the reference table."
)

# --- Decision variables ---
Position.x_assort = model.Property(f"{Position} carries {Integer:assort_id}")
Position.x_rev = model.Property(f"{Position} earns {Float:position_revenue}")

problem = Problem(model, Integer)
problem.solve_for(
    Position.x_assort,
    type="int",
    lower=MIN_ID,
    upper=MAX_ID,
    name=["assort", Position.index],
)
problem.solve_for(
    Position.x_rev,
    type="cont",
    lower=0.0,
    name=["rev", Position.index],
)

# --- Constraint: explicit membership IC (Form A in § 2c) — decision id must equal some reference id ---
# Even though MIN_ID..MAX_ID is dense here, this IC defends against silent failure if the reference
# table changes (rows added/removed) and the bounds aren't updated in lockstep.
problem.satisfy(
    model.where(Position.x_assort == Integer).require(
        sum(1).where(Assortment.id == Position.x_assort).per(Position) == 1
    )
)

# --- Constraint: implies cascade — revenue at position is the chosen assortment's revenue ---
# WARNING: verify() does not re-evaluate implies-bodied ICs (see csp-formulation.md § 6). The
# post-solve assertion below re-checks this cascade against the extracted values.
problem.satisfy(
    model.require(
        implies(
            Position.x_assort == Assortment.id, Position.x_rev == Assortment.revenue
        )
    )
)

# --- Constraint: each assortment appears at most once across positions (no duplication) ---
Pi, Pj = Position, Position.ref()
problem.satisfy(model.where(Pi.index < Pj.index).require(Pi.x_assort != Pj.x_assort))

# --- Objective: maximize total revenue ---
problem.maximize(sum(Position.x_rev))

problem.solve("minizinc", time_limit_sec=30)
si = problem.solve_info()
si.display()

# --- Post-solve assertion: re-evaluate the implies cascade against extracted values ---
# This is the workaround for verify()'s silent-OK behavior on implies-bodied ICs.
if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):
    rev_lookup = dict(zip(assort_data["id"], assort_data["revenue"]))
    rows = model.select(
        Position.index.alias("position"),
        Position.x_assort.alias("x_assort"),
        Position.x_rev.alias("x_rev"),
    ).to_df()
    print("\nFinal placement:")
    print(rows.to_string(index=False))
    positions = rows["position"].astype(int).tolist()
    assorts = rows["x_assort"].astype(int).tolist()
    revs = rows["x_rev"].astype(float).tolist()
    for pos, aid, rev in zip(positions, assorts, revs):
        expected = rev_lookup[aid]
        assert abs(expected - rev) < 1e-6, (
            f"implies cascade violated at position {pos}: "
            f"x_assort={aid}, x_rev={rev}, expected={expected}"
        )
    print("\nPost-solve assertion passed: implies cascade holds for all positions.")
