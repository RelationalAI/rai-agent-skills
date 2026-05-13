# Common Pitfalls

## Table of Contents
- [Common Pitfalls Table](#common-pitfalls-table)

---

## Common Pitfalls Table

> The most common rows (zero objective on minimize, all-zero from join mismatch, infeasible: demand > capacity) live in the parent SKILL.md > Common Pitfalls. The rows below cover *additional* result-interpretation pitfalls.

| Mistake | Cause | Fix |
|---------|-------|-----|
| All-zero variables with non-zero objective | Decision variables not referenced in objective, or constant terms evaluate regardless | Verify decision variable properties appear in objective with meaningful coefficients |
| Infeasible: contradictory constraints | Conflicting equality/inequality constraints or bounds | Organize into essential/full tiers; add incrementally to isolate conflict |
| Numerical instability | Coefficients differing by >1e9 | Scale data to similar magnitudes; tighten Big-M (<1e6); replace strict equalities with bounded slack |
| Cross-product entities mostly zero | Entities created but not linked to meaningful constraints | Add `.where()` filters to entity creation; restrict to valid combinations |
| Degenerate solutions (different on re-run) | Multiple optimal solutions with same objective | Add secondary objectives, symmetry-breaking constraints, or tie-breaking preferences |
| Wrong aggregation scope | `.per(Y)` but Y not joined to summed concept — constraint satisfied globally but violated locally | Add proper `.per()` grouping and relationship join in `.where()` |
| Missing constraint scope | Per-entity constraint applies globally | Add `.per()` grouping or iterate over entities |
| Incorrect relationship direction | `<=` when should be `==` or `>=` | Review business requirement — is this a limit, balance, or minimum? |
| Double counting in objective | Same quantity in both fixed and variable cost terms | Check for overlapping aggregation scope in objective terms |
| Missing/null data leaves variables/constraints ungrounded | Null/NaN values produce no tuple in the underlying relation, so under PyRel relational semantics the variable or constraint grounds no row | Run completeness checks before solve — see `rai-prescriptive-solver-management/references/pre-solve-validation.md` § Data integrity for the `model.select(...).to_df().notna().all()` pattern |
| Wrong data type | String or boolean where number expected | Check that cost, capacity, demand columns are numeric |
| Multi-solution overclaim: presenting `solution_limit=K` results as top-K-optimal, ranked by objective, or diversity-maximized | MiniZinc returns up to K **distinct feasible** solutions with no ordering guarantee — neither ranked by objective nor maximally diverse | Document semantics to consumers: up to K distinct feasible, no ordering. For top-K by objective, resolve K times with the previous-best as an additional constraint. See `rai-prescriptive-problem-formulation/references/csp-formulation.md` § 4. |
| Silent: `verify()` returns OK on solver-only-IC bodies (`implies`-bodied or `all_different`-bodied), even when violated | The verify engine cannot ground these wire-format constraint relations at check time, so it silently returns OK. Documented engine limitation, not a solver bug | Pick the regime that matches the constraint mix (`rai-prescriptive-problem-formulation/references/csp-formulation.md` § 6): mixed → call `verify()` + post-solve assertions on solver-only ICs; all-solver-only → skip `verify()` entirely; `populate=False` → skip `verify()` (no relational-layer values to ground) |
| Audit verdict misread: `num_points() == 0` interpreted as "property holds" | In status-aware audit problems (`INFEASIBLE` = PASS, `OPTIMAL`/`SOLUTION_LIMIT` = FAIL), a zero `num_points` can also result from a crash, time-limit, or any non-success status — NOT proof that the property holds | Always check `termination_status` first. Only `INFEASIBLE` proves the property holds. `TIME_LIMIT`, solver errors, and `LOCALLY_SOLVED` on a CSP are INCONCLUSIVE; do not interpret as PASS. See SKILL.md > Audit / witness mode. |
