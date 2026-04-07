# Known Limitations (Secondary)

Additional known limitations for the prescriptive problem formulation skill. For critical limitations (`model.union()` and PyRel additive semantics), see the main skill.md.

---

## Constraint naming with lists

Name constraints with list expressions for readable debug output:

```python
p.satisfy(model.require(
    Edge.x_flow <= Edge.capacity
), name=["capacity", Edge.i, Edge.j])
# Produces names like: "capacity_1_3", "capacity_2_5"
```

List elements are joined with underscores. Use entity identifiers (IDs, names) in the list for per-entity constraint names.

## Re-Solve Behavior (1.0.3+)

Re-solving the same `Problem` instance is safe. Result import uses `experimental.load_data` with replace semantics — previous results remain intact if a subsequent solve fails. The inline formulation pattern (fresh `Problem` per scenario loop iteration) is still useful for clean separation of scenarios, but is no longer required for error recovery.

**Multi-scenario re-solve pattern:**

When solving multiple scenarios in a loop (e.g., varying parameters, what-if analysis), create a **fresh `Problem` per iteration**, use `populate=False` on `solve_for`, and extract results via `variable_values().to_df()`. This avoids `Duplicate relationship` / `FDError` caused by writing conflicting results back to the graph on each iteration.

```python
results = []
for scenario in scenarios:
    p = Problem(model, Float)               # fresh Problem each iteration
    p.solve_for(Entity.x_var, populate=False, ...)
    p.satisfy(...)
    p.minimize(...)
    p.solve(solver, ...)
    df = p.variable_values().to_df()        # extract without populating graph
    df["scenario"] = scenario
    results.append(df)
all_results = pd.concat(results)
```

See [examples/partitioned_subproblem.py](../examples/partitioned_subproblem.py) for a complete working example of this pattern.

## `| 0` Fallback in Solver Constraints

The `| 0` (default-value) operator inside `p.satisfy(model.require(...))` with nested `sum().per().where()` aggregation causes `TyperError: Type errors detected during type inference`. This occurs when the RHS of a constraint combines a property with a conditional aggregation that uses `| 0` as a fallback.

```python
# BROKEN — | 0 inside solver constraint with nested aggregation
p.satisfy(model.require(
    Entity.supply >= sum(Flow.x_qty).per(Entity).where(Flow.dest(Entity)) | 0
))

# CORRECT — pre-compute aggregation in pandas, load as flat property
combos = pd.merge(entity_df, flow_df, how="left", on="entity_id")
combos["inflow"] = combos.groupby("entity_id")["qty"].transform("sum").fillna(0)
model.define(Entity.filter_by(id=entity_data.entity_id).inflow(entity_data.inflow))
p.satisfy(model.require(Entity.supply >= Entity.inflow))
```

**Workaround:** Pre-compute the aggregation in Python (e.g., enumerate combinations and build a denormalized parameter DataFrame), then pass the result as a flat property on the decision concept. Avoid nested `per().where() | 0` inside solver constraints.

## numpy Types as Solver Literals

`numpy.float64`, `numpy.int64`, and other numpy scalar types are not accepted as literals in solver constraints. Extracting a value from a DataFrame (e.g., `df["col"].iloc[0]`) returns a numpy scalar, and passing it directly to `model.require()` causes `NotImplementedError: Literal type not implemented for value type: numpy.float64`.

**Fix:** Cast to Python builtins before use: `float(value)`, `int(value)`.
