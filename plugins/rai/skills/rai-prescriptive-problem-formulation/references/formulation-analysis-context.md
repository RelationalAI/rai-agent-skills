# Formulation Analysis Context

## Table of Contents
- [Local Aliases and Constants](#local-aliases-and-constants)
- [Decision Variable Naming Convention](#decision-variable-naming-convention)
- [Expression Parsing Limitations](#expression-parsing-limitations)
- [Derived vs Decision Variables](#derived-vs-decision-variables)
- [V1 Aggregation Patterns](#v1-aggregation-patterns)
- [Python Variables in Constraints](#python-variables-in-constraints)

---

When reviewing a formulation, the LLM must understand these naming and reference conventions to avoid false positives:

## Local Aliases and Constants

If local variable aliases are defined (e.g., `Al -> Allocation.ref()`), then `Al.quantity` is VALID — refs use the slot name, no x_ prefix. If constants are defined (e.g., `MULTIPLIER = 2.0`), they ARE defined. Do NOT flag these as "undefined" — the code compiles and runs; if something were truly undefined, RAI would catch it.

## Decision Variable Naming Convention

- Decision variable attributes use `x_` prefix: `Entity.x_var_name` in Python code
- Property template strings use the SLOT name (no x_): `"{Entity} has {var_name:float}"`
- Ref-based access uses the slot name (no x_): `E = Entity.ref(); E.var_name`
- Do NOT flag variables as unused if you see the property name in constraints/objectives

## Expression Parsing Limitations

- Constraint expressions may be TRUNCATED or SUMMARIZED (e.g., `"sum(...)"` instead of full expansion)
- Variables used inside inline aggregations (`sum()`, `select()`, `where()`) may not appear in the expression string
- **Do NOT flag variables as unused if they appear in aggregation hints or are typical for the problem type**

## Derived vs Decision Variables

- Some properties are COMPUTED (e.g., `distance = sqrt(...)`) not decision variables
- Computed properties don't need to appear in constraints
- Only flag DECISION variables (from `solve_for()`) as unused, NOT computed properties

## V1 Aggregation Patterns

Structure: `sum(X.prop).where(filter).per(grouping)` (for full `.per()` semantics, see `rai-querying`)
- `.where()` on sum: FILTERS which items are aggregated
- `.per()` on sum: GROUPS the aggregation (one value per group)
- `.where()` on require(): ITERATES (one constraint per entity)

**For per-entity constraints, use `.per()` on BOTH the sum and the constraint:**
- `.per(Entity)` on `sum(...)` groups the aggregation (one total per Entity)
- `.where(Entity)` on `require()` iterates the constraint (one constraint per Entity)

Python variables holding expressions (e.g., `total = sum(...)`) are valid — don't flag as undefined.

## Python Variables in Constraints

Code uses Python variables for intermediate expressions. If an identifier is assigned before use, it's VALID.
