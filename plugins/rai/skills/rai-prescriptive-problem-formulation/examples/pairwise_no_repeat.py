# Pattern: multi-arity decision property + binder-in-where + double-symbolic count for pairwise no-repeat
"""
Round-robin tournament: N=4 players, R=3 rounds, G=2 groups of S=2 players each.
Constraint: no pair of players is in the same group more than once across all rounds.

This is the social_golfer pattern distilled to its smallest pedagogically useful form. With
N=4 and group_size=2, the unordered pair count is C(4,2)=6, and the schedule contributes
R × C(S,2) × G = 3 × 1 × 2 = 6 pair-occurrences — so the "no-repeat" IC forces exactly one
meeting per pair across the schedule (a perfect round-robin).

Demonstrates:
- Multi-arity decision property — `Player.assign = model.Property(f"{Player} in {Integer:round}
  is in {Integer:group}")` has signature Player × Integer(round) → Integer(group). One decision
  variable per (Player, round) is declared via `solve_for(Player.assign(r, g))`.
- Binder-in-where: `where(Player.assign(r, g))` anchors `r` and `g` to the decision relation's
  tuples — it is a relational binder, not a value filter. The general PyRel mechanic is
  documented in `rai-pyrel-coding/references/expression-rules.md` (Multi-arity property
  invocation in where as binder). The CSP-specific consequence: a TRUE filter on the decision-var
  value (e.g., `where(g == 1)`) would prune the search space at compile time — see
  csp-formulation.md § 3a.
- Cardinality IC with single-symbolic count: `count(Player, g == group_val).per(r, group_val)
  == GROUP_SIZE`. The symbolic comparison `g == group_val` lives inside count's second arg, NOT
  in the outer where.
- Pairing IC with DOUBLE-SYMBOLIC count: `count(r, g0 == g1).per(p0, p1) <= 1`. Count's last arg
  compares TWO decision-variable refs (each player's group in round r). The pair iteration uses
  two Player.ref() with `p0.p < p1.p` as a data-only half-pair filter (Player.p is pre-defined
  integer data, not a decision-variable value).

Triggering pattern: "no pair X meets twice," "diversify co-occurrence," "round-robin no-repeat
scheduling," "tournament without rematches." Whenever the IC's shape is "for each PAIR of
entities, count co-occurrences in a data dimension ≤ N," this is the form.

Distilled from social_golfer.
"""

import time

from relationalai.semantics import Integer, Model, count, std
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_pairwise_no_repeat_{time.time_ns()}")

N_PLAYERS = 4
N_ROUNDS = 3
N_GROUPS = 2
GROUP_SIZE = 2  # 4 players / 2 groups = 2 players per group

# --- Concept: Players with an integer index property ---
Player = model.Concept("Player")
Player.p = model.Property(f"{Player} has {Integer:p}")
model.define(Player.new(p=std.common.range(N_PLAYERS)))

# --- Decision property: 3-arity (Player, round, group) ---
Player.assign = model.Property(f"{Player} in {Integer:round} is in {Integer:group}")

# --- Refs for the two extra arities ---
r = Integer.ref().alias("r")  # round index (data dimension)
g = Integer.ref().alias("g")  # group index (decision-variable value)

problem = Problem(model, Integer)
problem.solve_for(
    Player.assign(r, g),
    type="int",
    lower=0,
    upper=N_GROUPS - 1,
    name=["assign", Player.p, r],
    where=[r == std.common.range(N_ROUNDS)],
)

# --- Constraint A: each (round, group_value) contains exactly GROUP_SIZE players ---
# Outer where(Player.assign(r, g)) BINDS r and g to the decision relation. Inner count's last arg
# `g == group_val` compares decision value to a data range value — single-symbolic count idiom.
group_val = std.common.range(N_GROUPS)
cardinality_ic = model.where(Player.assign(r, g)).require(
    count(Player, g == group_val).per(r, group_val) == GROUP_SIZE
)
problem.satisfy(cardinality_ic)

# --- Constraint B: any two players share a group in at most one round (pairwise no-repeat) ---
# - p0, p1: pairwise Player refs. `p0.p < p1.p` is a DATA-only filter (Player.p is pre-set), so the
#   half-pair picks one orientation per unordered pair without re-counting.
# - g0, g1: Integer refs bound through p0.assign(r, g0) and p1.assign(r, g1) — multi-arity-property
#   invocation as BINDER. The binders anchor g0 and g1 to each player's decision value at round r.
# - count(r, g0 == g1) is the double-symbolic count: both operands are decision-variable refs that
#   vary with r. The count tallies rounds where the two players share a group.
pairing_ic = model.where(
    p0 := Player.ref(),
    p1 := Player.ref(),
    p0.p < p1.p,
    g0 := Integer.ref(),
    g1 := Integer.ref(),
    p0.assign(r, g0),
    p1.assign(r, g1),
).require(count(r, g0 == g1).per(p0, p1) <= 1)
problem.satisfy(pairing_ic)

# --- Solve as pure satisfaction (no objective) ---
problem.solve("minizinc", time_limit_sec=30)
si = problem.solve_info()
si.display()

if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT", "LOCALLY_SOLVED"):
    print(
        f"\nTournament schedule ({N_PLAYERS} players, {N_ROUNDS} rounds, "
        f"{N_GROUPS} groups of {GROUP_SIZE}):"
    )
    model.select(Player.p, r, g).where(Player.assign(r, g)).inspect()
elif si.termination_status == "INFEASIBLE":
    print(
        "\nNo schedule exists with these parameters. Check: (1) N_PLAYERS must equal "
        "N_GROUPS * GROUP_SIZE so each round partitions players exactly; (2) "
        "R * C(S, 2) * G must not exceed C(N, 2) so the pair-occurrence budget fits."
    )
else:
    print(f"\nSolver did not converge (status={si.termination_status}).")
