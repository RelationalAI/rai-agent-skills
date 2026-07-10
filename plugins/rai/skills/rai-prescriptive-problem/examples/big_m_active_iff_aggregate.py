# Pattern: big-M form of active-iff with aggregate body — preferred over half-reified implies in multi-solution mode
"""
Network role assignment: choose 2 hubs from a candidate pool of 5; each chosen hub must have
balanced in-flow vs out-flow over a decision-selected edge subset (|in - out| <= tolerance).
Inactive (non-hub) accounts have no balance constraint.

This is the canonical "active-iff" shape: an IC binds only when a Boolean decision (`is_hub`)
is 1. Two encodings are possible — pick the right one or multi-solution enumeration breaks.

Demonstrates:
- Big-M form `body + M * active <= tolerance + M`:
    - When active == 1: body <= tolerance (constraint binds)
    - When active == 0: body <= tolerance + M (vacuous if M sized above body's range)
- No auxiliary Boolean introduced — the inequality is a single linear constraint per active row.
- Why NOT `implies(is_hub == 1, body <= tolerance)`:
    - Half-reification introduces a free Boolean auxiliary per inactive row.
    - In multi-solution mode (`solution_limit=K`), MiniZinc treats each auxiliary as part of
      the search space and returns thousands of trivially-distinct solutions that differ only
      in those free auxiliaries' values — same role/hub assignment, different aux bits.
    - With big-M there is no auxiliary; the solver exhausts after the data's actual feasible
      configurations.

Two-sided absolute-value: CSP backends don't consume `abs(...)` over decision-variable
expressions, so the `|in - out| <= TOL` constraint is two one-sided big-M inequalities.

Triggering pattern: "constraint X applies only when decision Y is on," "balance / threshold /
tolerance constraint that should be vacuous for inactive rows," combined with enumeration
or multi-solution mode. If you see `implies(active == 1, aggregate_over_decisions <= bound)`
and the use case is enumeration, switch to big-M.

For decision-indexed TABLE LOOKUP (body references a single Ref row's value, not an aggregate
over decision variables), `implies` is still the right shape — see `implies_table_lookup.py`.
The pitfall is specific to aggregate-body active-iff in enumeration mode.

Distilled from `motif_butterfly.py` in the `money_laundering_motif_detection` template.
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_big_m_active_iff_{time.time_ns()}")

K = 2  # number of hubs to select
N = 5  # candidate pool size
TOL = 5  # balance tolerance (units of edge weight)
# BIG_M sized above the body's maximum absolute range. With 4 edges per direction × max weight 10,
# in-out spread is at most 40 in absolute value; pick BIG_M = 100 for comfortable headroom.
BIG_M = 100

# --- Concepts and inline data: candidate accounts + directed edges between them ---
Account = model.Concept("Account", identify_by={"id": Integer})
account_data = pd.DataFrame([(i,) for i in range(1, N + 1)], columns=["id"])
model.define(Account.new(model.data(account_data).to_schema()))

Edge = model.Concept("Edge", identify_by={"src_id": Integer, "dst_id": Integer})
Edge.weight = model.Property(f"{Edge} has {Integer:weight}")
edge_data = pd.DataFrame(
    [
        (1, 2, 10),
        (1, 3, 8),
        (3, 2, 7),
        (4, 3, 9),
        (4, 5, 6),
        (5, 1, 4),
        (2, 5, 5),
        (3, 5, 3),
    ],
    columns=["src_id", "dst_id", "weight"],
)
model.define(Edge.new(model.data(edge_data).to_schema()))

# --- Decisions: which accounts are hubs (binary) + which edges count toward the motif (binary) ---
Account.is_hub = model.Property(f"{Account} is {Integer:hub_flag}")
Edge.in_subset = model.Property(f"{Edge} is {Integer:subset_flag}")

problem = Problem(model, Integer)
hub_var = problem.solve_for(
    Account.is_hub, type="bin", name=["hub", Account.id], populate=False
)
subset_var = problem.solve_for(
    Edge.in_subset,
    type="bin",
    name=["subset", Edge.src_id, Edge.dst_id],
    populate=False,
)

# --- Cardinality: exactly K hubs ---
problem.satisfy(model.require(sum(Account.is_hub) == K))

# --- Big-M active-iff balance constraints (the focal pattern) ---
# Per-hub flow balance: at every hub account, sum(in-edge weights in motif) - sum(out-edge weights
# in motif) is within +/- TOL. Two one-sided inequalities (CSP wire rejects abs(decision_expr)).
#
# Read each IC as:
#   body + BIG_M * is_hub <= TOL + BIG_M
#   ⇒ body <= TOL when is_hub == 1   (active: balance enforced)
#   ⇒ body <= TOL + BIG_M when is_hub == 0  (vacuous: any feasible flow is allowed)
in_weight = sum(Edge.weight * Edge.in_subset).where(Edge.dst_id == Account.id).per(Account)
out_weight = sum(Edge.weight * Edge.in_subset).where(Edge.src_id == Account.id).per(Account)

balance_upper_ic = model.require(
    in_weight - out_weight + BIG_M * Account.is_hub <= TOL + BIG_M
)
balance_lower_ic = model.require(
    out_weight - in_weight + BIG_M * Account.is_hub <= TOL + BIG_M
)
problem.satisfy(balance_upper_ic)
problem.satisfy(balance_lower_ic)

# --- Pure satisfaction: no objective; enumerate hub configurations ---
# populate=False above so re-extracting per-solution via Variable.values works without
# the first-solution write-back contaminating the relational layer (see csp-formulation.md § 4).
MAX_CONFIGS = 10
problem.solve("minizinc", solution_limit=MAX_CONFIGS, time_limit_sec=30)
si = problem.solve_info()
si.display()

if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):
    n = si.num_points or 0
    print(
        f"\nFound {n} feasible hub configurations"
        f" (status={si.termination_status}; OPTIMAL = search exhausted, SOLUTION_LIMIT = stopped at K):"
    )
    val = Integer.ref()
    for sol_idx in range(n):
        print(f"\n  Configuration {sol_idx}:")
        model.select(hub_var.account.id).where(
            hub_var.values(sol_idx, val), val > 0.5
        ).inspect()
elif si.termination_status == "INFEASIBLE":
    print("\nNo K-hub assignment satisfies the balance tolerance.")
else:
    print(f"\nSolver did not converge (status={si.termination_status}).")
