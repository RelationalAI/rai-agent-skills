# Diagnostic Taxonomy

## Root Cause Taxonomy

When diagnosing infeasibility or unboundedness, classify root causes using these named codes:

| Root Cause Code | Status | Description |
|----------------|--------|-------------|
| `unbounded_variable` | DUAL_INFEASIBLE | A variable can grow without limit, driving objective to infinity |
| `missing_upper_bound` | DUAL_INFEASIBLE | Variable has no upper bound and objective incentivizes increasing it |
| `penalty_structure` | DUAL_INFEASIBLE | Penalty term can go negative (e.g., `100 * (demand - fulfilled)` when fulfilled > demand) |
| `constraint_conflict` | INFEASIBLE | Two or more constraints cannot be satisfied simultaneously — `solve(conflict=True)` localizes the minimal conflicting subset as `con.in_conflict` / `var.*_in_conflict` membership |
| `capacity_mismatch` | INFEASIBLE | Total demand exceeds total capacity — no feasible allocation exists |

## Fix Action Types

| Action | When to Use |
|--------|-------------|
| `add_constraint` | Missing bounds or linking constraints; add capacity limits, conservation |
| `omit_constraint` | Conflicting or over-specified constraint causing infeasibility — Problem accumulates `satisfy(...)` calls, so "omit" means rebuild the Problem without that constraint |
| `relax_constraint` | Constraint too tight — change `==` to `<=`/`>=`, widen bounds, add slack |
| `modify_variable` | Variable needs bounds adjusted, type changed, or expression corrected |

## Status-Specific Fix Direction

- **DUAL_INFEASIBLE (unbounded):** Add bounds and constraints to LIMIT unbounded variables
- **INFEASIBLE:** First localize the offender with `solve(conflict=True)` — the IIS is the minimal conflicting subset of constraints / bounds, read via `con.in_conflict` and `var.*_in_conflict` and joined to the entity by key (see `rai-prescriptive-results-interpretation/references/conflict-analysis.md`). Request `conflict=True` up front or on a fresh rebuild — a `Problem` already solved plain can't add it on a re-solve. Then WIDEN the feasible region by acting on the flagged members — omit/relax a flagged constraint (since Problem is append-only, "omit" means rebuilding without the offending `satisfy(...)`), or widen a flagged variable bound/type; re-solve to confirm — independent conflicts may remain. Bisection is the fallback when the solver reports `conflict_status == "NOT_SUPPORTED"` / `"FAILED"`.
