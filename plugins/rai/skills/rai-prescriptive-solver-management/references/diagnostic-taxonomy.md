# Diagnostic Taxonomy

## Root Cause Taxonomy

When diagnosing infeasibility or unboundedness, classify root causes using these named codes:

| Root Cause Code | Status | Description |
|----------------|--------|-------------|
| `unbounded_variable` | DUAL_INFEASIBLE | A variable can grow without limit, driving objective to infinity |
| `missing_upper_bound` | DUAL_INFEASIBLE | Variable has no upper bound and objective incentivizes increasing it |
| `penalty_structure` | DUAL_INFEASIBLE | Penalty term can go negative (e.g., `100 * (demand - fulfilled)` when fulfilled > demand) |
| `constraint_conflict` | INFEASIBLE | Two or more constraints cannot be satisfied simultaneously |
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
- **INFEASIBLE:** Omit or relax constraints to WIDEN the feasible region (since Problem is append-only, "omit" means rebuild the Problem without the offending `satisfy(...)`)
