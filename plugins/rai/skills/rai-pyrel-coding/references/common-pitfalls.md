<!-- TOC -->
- [Additional Pitfalls](#additional-pitfalls)
- [Debugging Empty or Unexpected Results](#debugging-empty-or-unexpected-results)
<!-- /TOC -->

## Additional Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `TypeMismatch` error | Comparing concepts of different types via `==` | Ensure both sides are the same concept type; value types prevent cross-type joins |
| Duplicate column name on Snowflake export | Case-insensitive column name collision (`LongShort` vs `longshort`) | Use distinct uppercase names for all `.alias()` values |
| Using Python builtins on RAI expressions | `abs()`, `min()`, `max()`, `round()` don't work on symbolic expressions | Use `math.abs()`, RAI aggregation imports, or algebraic equivalents |
| `//` on two decision variables | Floor division fails when both operands are decision variables | Works fine on property // constant (e.g., `Player.p // group_size`). Only fails with two solver variables — use algebraic reformulation |
| `count(X, condition)` not working | Using wrong syntax for conditional counting | Use `count(Player, x == group)` — second arg is a condition expression, works in both query and solver contexts |
| Long import lines breaking linters | LLMs generate 100+ char single-line imports | Split across multiple lines with `()` or use module alias (`import relationalai.semantics as rai`) |
| Relationship declared but has no data | `model.Relationship(...)` without a corresponding `model.define()` data binding | Relationship has NO DATA at runtime — any `.where()` join on it returns zero matches. Add `model.define(From.rel(To)).where(...)` to populate it from data. |
| Using aggregates without model.distinct() | Causes duplicate rows in output | use `model.select(model.distinct(expr))` around all columns |
| Incorrect datetimes for inline data | Causes query errors or empty result sets | use eg `df["date"] = pd.to_datetime(df["date"]).dt.date` |
| Entity-valued Property for concept-to-concept FK | Some model files use `model.Property(f"{Order} placed by {Customer:customer}")` for FKs | Recommended when the FK is many-to-one (each Order has exactly one Customer) — provides performance benefits and enforces the functional constraint. Use `model.Relationship()` only if the association is truly many-to-many or cardinality is uncertain |
| Dynamic model loading loses module-level concepts | Using `importlib.util` to load a model file — concepts defined as module variables aren't on the model object | After loading, iterate module attributes and `setattr(model, name, obj)` for each `rai.Concept` instance |
| Standalone script can't see base model data | New script creates `Model("same name")` but doesn't import the base model module — concept definitions and `define()` rules aren't in scope | Import the base model (e.g., `from base_model import model, Concept`) so all definitions execute in the same session |
| Typo creates silent empty property | `Customer.nmae` (typo) silently creates an empty property via implicit property creation — no error | `create_config(model={"implicit_properties": False})` or set `implicit_properties: false` under `model:` in raiconfig.yaml |
| `TypeError: model argument must be a Model, but is a module` | Package directory named `model/` shadows the `model` variable after `import model.submodule` | Rename the package directory to something other than `model` (e.g., `sc_model/`, `fraud_model/`) |
| `~Relationship()` for negation | `TypeError: bad operand type for unary ~: 'Expression'` — Python `~` doesn't work on RAI expressions | Use `model.not_(Concept.relationship())` for negation in `.where()` clauses |
| `[Inconsistent branches]` in `union()` | Branches return different numbers of values — e.g., a bare relation call (1 value) mixed with `where(...)` (0 values), or Fragments with different `select()` column counts | Make all branches return the same count: chain relation calls so all return values, or wrap all in `where(...)` with matching `select()` columns |
| Re-defining Property in function/loop fails | `Concept.prop = model.Property(...)` inside a function called multiple times — "already defined" on second call | Define Properties once at module level, outside any function or loop |
| `Int128Array` / `NotImplementedError` / silent empty results on pandas operations | RAI returns `Int128Array` for counts, integer aggregations, and IDs; `Float128` for float aggregations and Snowflake FLOAT columns. Int128 raises errors on `.fillna(0)`, `.groupby()`, `.sum()`; Float128 can fail silently (e.g., `.sort_values()` produces empty output without error) | Cast early: `df["col"].astype(int)` for integers, `df["col"].astype(float)` for floats |
| `ValidationError: Unused variable` after `import *` from another model script | `from other_script import *` brings all concepts/relationships into scope — any not referenced in the current query trigger the validator | Import only what you need: `from base_model import model, Customer, Order`. Never use `import *` across model scripts |
| `ImportError: cannot import name 'aggregates' from 'relationalai.semantics'` | Standard-library modules (`aggregates`, `math`, `strings`, `numbers`, `datetime`) live under `relationalai.semantics.std`, not `relationalai.semantics` directly | Use `from relationalai.semantics.std import aggregates` (or `math`, `strings`, `numbers`). For `datetime`: `from relationalai.semantics.std.datetime import datetime`. See `rai-pyrel-coding/references/imports.md` for the full catalog |
| `AttributeError: 'Model' object has no attribute 'query'` | `model.query()` doesn't exist in PyRel v1 — queries are built from `model.select()` or `model.where(...).select(...)` | Use `model.select(Entity.prop).to_df()` or `model.where(condition).select(...).to_df()`. See `rai-querying` for the full query API |
| Cross-type comparisons return empty (no error) | The PyRel typer is strict where Python coerces — `Date` vs `DateTime`, `Integer` vs `Float`, `String` vs numeric all silently match zero rows. `model.where(Order.shipped_at == today)` returns empty when `shipped_at` is `DateTime` and `today` is a `Date`; `where(Order.qty == 5)` returns empty when `qty` is `Float` | Match the property's declared type at the call site. Cast Python ints to Float via `floats.float(...)` when comparing to Float properties; explicitly convert `Date` ↔ `DateTime` rather than relying on Python coercion. Use `print(Concept.prop)` or `inspect.schema()` to confirm the declared type before composing the comparison |
| Unary boolean parens flip when chained vs. unchained | `Entity.is_flag()` *requires* parens on a bare concept, but the same flag is referenced without parens when reached through a chained navigation (`obj.relation.is_flag`). Calling `obj.relation.is_flag()` raises `Either use the expression without empty parentheses ... or provide an argument` | Bare concept call: `Concept.is_flag()`. Chained through a navigation: `obj.rel.is_flag` (no parens). Same rule for any unary boolean Property reached via `.` traversal |
| `short_name` is metadata, not the binding key | When you declare `Concept.foo = m.Property(..., short_name="cf_foo")`, the relation is registered under the Python attribute name (`foo`), not the short_name. Calling `.cf_foo(...)` on a filter when `model.implicit_properties=true` (default) silently creates a parallel implicit Property with field type `Any`, leaving your explicit Property unbound — queries return NaN for every row | Bind and query via `Concept.foo(...)` / `Concept.filter_by(foo=...)`. `short_name` is for `model.relationship_index[...]` lookup, debug/inspect display, and same-type-slot disambiguation in readings — not for invocation |

> **`TyperError` with empty diagnostic body** — `RAIException: [TyperError] ... see above for details` appears but the "above" details never reach stderr. Strip the failing expression to a minimal reproducer: remove one `.where()` clause or `.select()` column at a time until the error disappears. The last removed piece is the culprit. Common causes: a Relationship's `short_name` used in place of its Python attribute (see `short_name` is metadata row above), or an unbound `.ref()`.

For data loading pitfalls (NaN columns, `to_schema()` clobbering, NULL FKs), see [data-loading.md](data-loading.md) § Common Data Loading Mistakes.
For `.exists()` on Properties, see `rai-querying` Common Pitfalls.
For Graph + large model TyperError, see `rai-graph-analysis` Common Pitfalls.

---

## Debugging Empty or Unexpected Results

When a query returns an empty DataFrame or wrong values, work through these checks in order (cheapest/highest-yield first):

1. **Check for typos (implicit properties):**
   Typos silently create empty properties (see pitfall table above). Quick test:
   set `implicit_properties: false` in raiconfig.yaml and re-run — any typo will error.

2. **Check type alignment:**
   `.where(Order.id == "123")` returns empty when `id` is Integer — no error.
   Fix: use matching type (`.where(Order.id == 123)`).
   Use `print(Order.id)` to verify the expression references the expected concept and property.
   Use `.inspect()` to see actual values and infer types.
   Also check datetime columns: pandas Timestamps don't match Date properties —
   convert with `df["col"] = pd.to_datetime(df["col"]).dt.date`.

3. **Check join paths:**
   Does the relationship used in `.where()` have a `model.define()` populating it?
   Use `print(Concept.rel)` to verify the relationship references the expected concepts.
   Test: `Concept.rel.inspect()` — if empty, add a `model.define()` rule to populate it.

4. **Check entity counts:**

```python
model.select(count(Customer)).to_df()
```

   If 0: data not loaded. Check table path and `model.define()` rules.

> **Note:** `count(C)` on a concept with zero instances returns an empty DataFrame (no rows), not a DataFrame with `count=0` — the underlying relation is empty so the aggregation has no rows to reduce over. For chained workflows where a placeholder concept is populated by a downstream step, use `inspect.schema()` membership to verify the concept is declared rather than `count()` to verify data.

5. **Isolate where conditions:**

```python
model.where(A).select(X).to_df()            # works?
model.where(A, B).select(X).to_df()         # still works?
model.where(A, B, C).select(X).to_df()      # empty? → C is the culprit
```
