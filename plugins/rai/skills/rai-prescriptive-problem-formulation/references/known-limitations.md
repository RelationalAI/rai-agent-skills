# Known Limitations (Secondary)

Additional known limitations for the prescriptive problem formulation skill. For critical limitations (`model.union()` and PyRel additive semantics), see the main skill.md.

---

## Constraint naming with lists

Name constraints with list expressions for readable debug output:

```python
problem.satisfy(model.require(
    Edge.x_flow <= Edge.capacity
), name=["capacity", Edge.i, Edge.j])
# Produces names like: "capacity_1_3", "capacity_2_5"
```

List elements are joined with underscores. Use entity identifiers (IDs, names) in the list for per-entity constraint names.

## Re-Solve Behavior (SDK >= 1.0.3)

Re-solving the same `Problem` instance is safe. Result import uses replace semantics — previous results remain intact if a subsequent solve fails. The inline formulation pattern (fresh `Problem` per scenario loop iteration) is still useful for clean separation of scenarios, but is no longer required for error recovery.

**Multi-scenario re-solve pattern:**

When solving multiple scenarios in a loop (e.g., varying parameters, what-if analysis), create a **fresh `Problem` per iteration**, use `populate=False` on `solve_for`, and extract results via `var.values(sol_idx, val)`. This avoids `Duplicate relationship` / `FDError` caused by writing conflicting results back to the graph on each iteration.

`var.values` is an arity-2 read-only Property mapping `(sol_index, value)` populated after `solve()`. Read it through the back-pointer attribute (lowercased Concept name from the format string — see `rai-prescriptive-results-interpretation` > Solution Extraction for the naming rule):

```python
results = []
for scenario in scenarios:
    problem = Problem(model, Float)               # fresh Problem each iteration
    var = problem.solve_for(Entity.x_var, populate=False, ...)
    problem.satisfy(...)
    problem.minimize(...)
    problem.solve(solver, ...)
    val = Float.ref()
    df = (
        model.select(var.entity.name.alias("entity"), val.alias("value"))
        .where(var.values(0, val))
        .to_df()
    )
    df["scenario"] = scenario
    results.append(df)
all_results = pd.concat(results)
```

See [examples/partitioned_subproblem.py](../examples/partitioned_subproblem.py) for a complete working example of this pattern.

## `| <literal>` Fallback in Solver Constraints (RAI-49989)

A `| <literal>` (default-value) fallback on a decision-variable-bearing aggregate inside `problem.satisfy(model.require(...))` raises a `NotImplementedError` from the prescriptive rewriter — it requires homogeneous Match arm types, but the symbolic arm gets lifted to a node-Hash reference while the literal arm stays at its original numeric type, so the two arms can't be unified.

```python
# BROKEN — | 0 fallback on a decision-variable aggregate
problem.satisfy(model.require(
    Entity.supply >= sum(Flow.x_qty).per(Entity).where(Flow.dest(Entity)) | 0
))
```

**Two workarounds:**

1. **Aggregate-default form** (in-engine, both arms symbolic): replace the literal arm with another aggregate over the same decision-variable Property — e.g. `sum(Flow.x_qty).where(Flow.dest(Entity)) | sum(Flow.x_qty)`. Both arms are then symbolic and the rewriter handles it.
2. **Pre-compute in pandas** (out-of-engine): aggregate in Python and load the result as a flat denormalized property on the decision concept.

```python
# CORRECT — pre-compute aggregation, load as flat property
combos = pd.merge(entity_df, flow_df, how="left", on="entity_id")
combos["inflow"] = combos.groupby("entity_id")["qty"].transform("sum").fillna(0)
model.define(Entity.filter_by(id=entity_data.entity_id).inflow(entity_data.inflow))
problem.satisfy(model.require(Entity.supply >= Entity.inflow))
```

## numpy Types as Solver Literals

`numpy.float64`, `numpy.int64`, and other numpy scalar types are not accepted as literals in solver constraints. Extracting a value from a DataFrame (e.g., `df["col"].iloc[0]`) returns a numpy scalar, and passing it directly to `model.require()` causes `NotImplementedError: Literal type not implemented for value type: numpy.float64`.

**Fix:** Cast to Python builtins before use: `float(value)`, `int(value)`.
