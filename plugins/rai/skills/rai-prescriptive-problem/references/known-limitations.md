# Known Limitations (Secondary)

Additional known limitations for the prescriptive problem formulation skill. For critical limitations (multi-component objective totals and PyRel additive semantics), see the parent [SKILL.md](../SKILL.md) > Known Limitations.

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

## Re-Solve Behavior

Re-solve contract: `rai-prescriptive-results` > Re-solving the same Problem. A loop over scenarios (fresh `Problem` per iteration, `populate=False`, read `var.values(sol_idx, val)`, which avoids the `Duplicate relationship` / `FDError` of writing each iteration back to the model): [scenario-analysis.md](scenario-analysis.md) > Pattern 2.

See `rai-prescriptive-results/examples/partitioned_iteration_scenarios.py` for a complete working example of this pattern.

## Decision-variable aggregate agreement

These aggregate forms over decision variables can make PyRel's read-back disagree with the solver. Use these spellings instead, writing each default as `0` rather than `0.0` in an `Integer` problem:

- **Union sums:** add separate totals, `(sum(A.x) | 0.0) + (sum(B.x) | 0.0)`; default each potentially empty term (relationalai>=1.13.0) or it drops the whole objective. `min`/`max` over a union is fine; filters and data-only aggregates are unaffected.
- **Unkeyed sum/count:** name the decision's identifying entities as leading args or group keys: `sum(f, xf).where(f.flow_var(xf))`, `count(f, xf >= 1).where(f.flow_var(xf))`. Property sums like `sum(Flow.x)` are already keyed.
- **Nested totals:** an outer total names every inner group key or reads it in its own body: `sum(Item, sum(...).per(Item))`, or `sum(Item.w * sum(...).per(Item))`. A row-wise inner such as `rank` adds its keys too: `count(Y, X.x * rank(Y.w) >= 1)`, not `count(X.x * rank(Y.w) >= 1)`, and so does a grouped inner read in a filter: `sum(Y, X.x).where(count(Y).per(Y) >= 1)`. For one total per property group, bind the value to a ref, `sum(g, sum(Item.x).where(Item.group(g)).per(g))`; keying the outer sum on `Item.group` makes the solver count each group's total once per `Item`. If the outer body also reads the entity (`Item.w * ...`), a bound `g` pairs every `Item.w` with every group's total; total per entity with a fresh ref instead: `J = Item.ref()`, then `sum(Item, Item.w * sum(J.x).where(J.group == Item.group).per(Item))`.
- **Constant fallback inside an aggregate with X unbound outside:** replace `sum(X.a | 0.0)` with `sum(X.a | model.select(0.0).where(X))` for a per-entity default (relationalai>=1.32.0), or bind X outside (`model.where(X).select(...)` / `.per(X)`). For an empty-total default use `sum(X.a) | 0.0`; the same scope rule applies to `min`/`max` defaults. An aggregate arm is keyed by its `.per()` keys: `min(sum(X.x).per(X)) | 1.0`, not `min(sum(X.x).per(X) | 1.0)`.

## numpy Types as Solver Literals

`numpy.float64`, `numpy.int64`, and other numpy scalar types are not accepted as literals in solver constraints. Extracting a value from a DataFrame (e.g., `df["col"].iloc[0]`) returns a numpy scalar, and passing it directly to `model.require()` causes `NotImplementedError: Literal type not implemented for value type: numpy.float64`.

**Fix:** Cast to Python builtins before use: `float(value)`, `int(value)`.

## CSP-style limitations

When using `Problem(model, Integer)` + `solver="minizinc"`:

- **`Problem(model, Integer)` is required.** A Float decision property raises `ValueError` at `solve_for`, and Float data in an expression fails at solve with `[TypeMismatch] Expected 'Number(38,0)'`. Mismatched pairings raise `JobInvalidRequestError` at job creation: `Problem(model, Float)` + `solver="minizinc"`, and `Problem(model, Integer)` with any other solver.
- **Empty-aggregate silent-drop is documented correctness.** A `sum` / `count` over an empty relation drops the IC at compile time. Detect via a `num_constraints` / `num_min_objectives` diff before and after a model edit. Sibling silent-failure mode to the `verify()` skip on `implies`-bodied ICs (see [global-constraints.md](global-constraints.md) > verify() caveat).
- **`circuit`, `cumulative`, `element`, `table`, `no_overlap`, `inverse`, `lex_lesseq` are not Python-callable today.** MiniZinc's native global-constraint library is far richer than what PyRel exposes; only `all_different`, `implies`, SOS1, SOS2 are callable from PyRel. See [global-constraints.md](global-constraints.md) > Per-solver coverage matrix.
- **`%` and `//` on decision variables** are rejected on every solver path: [numerical-and-mip.md](numerical-and-mip.md) > Operator and Construct Compatibility by Solver.
- **MiniZinc supports a single scalar objective.** No multi-objective MiniZinc lower; use the epsilon-constraint loop (see `multi-objective-formulation.md`) for bi-objective.
- **Chuffed is the only MiniZinc backend exposed.** Gecode / CP-SAT are not currently selectable. Native MiniZinc logging is not captured into LogMessage events.

For the full CSP-style guide, see [csp-formulation.md](csp-formulation.md).
