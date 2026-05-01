# Common Pitfalls

## Table of Contents
- [Common Pitfalls Table](#common-pitfalls-table)

---

## Common Pitfalls Table

| Mistake | Cause | Fix |
|---------|-------|-----|
| Zero objective on minimize | Missing forcing constraints — "do nothing" is cheapest | Add `sum(x).per(Entity) >= Entity.demand` or equivalent |
| All-zero variables with non-zero objective | Decision variables not referenced in objective, or constant terms evaluate regardless | Verify decision variable properties appear in objective with meaningful coefficients |
| All-zero from join mismatch | Forcing constraints exist but `.where()` joins match zero rows | Verify constraint joins match actual data relationships |
| Infeasible: demand > capacity | Total demand exceeds total supply/capacity | Add slack/penalty variables, or relax demand constraints |
| Infeasible: contradictory constraints | Conflicting equality/inequality constraints or bounds | Organize into essential/full tiers; add incrementally to isolate conflict |
| Numerical instability | Coefficients differing by >1e9 | Scale data to similar magnitudes; tighten Big-M (<1e6); replace strict equalities with bounded slack |
| Cross-product entities mostly zero | Entities created but not linked to meaningful constraints | Add `.where()` filters to entity creation; restrict to valid combinations |
| Degenerate solutions (different on re-run) | Multiple optimal solutions with same objective | Add secondary objectives, symmetry-breaking constraints, or tie-breaking preferences |
| Wrong aggregation scope | `.per(Y)` but Y not joined to summed concept — constraint satisfied globally but violated locally | Add proper `.per()` grouping and relationship join in `.where()` |
| Missing constraint scope | Per-entity constraint applies globally | Add `.per()` grouping or iterate over entities |
| Incorrect relationship direction | `<=` when should be `==` or `>=` | Review business requirement — is this a limit, balance, or minimum? |
| Double counting in objective | Same quantity in both fixed and variable cost terms | Check for overlapping aggregation scope in objective terms |
| Missing/null data silently dropped | Null/NaN values cause variables or constraints to vanish | Run completeness checks before solve — see `rai-prescriptive-solver-management/references/pre-solve-validation.md` § Data integrity for the `model.select(...).to_df().notna().all()` pattern |
| Wrong data type | String or boolean where number expected | Check that cost, capacity, demand columns are numeric |
