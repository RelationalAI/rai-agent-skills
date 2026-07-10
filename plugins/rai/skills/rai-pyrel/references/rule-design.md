# Rule Design — NL Translation Tables and Design Principles

Detail behind SKILL.md § Rules Authoring step 4. Load when translating a non-trivial natural-language rule or reviewing a rule design.

## NL-to-PyRel condition mapping

| NL Phrase | PyRel Translation |
|-----------|-------------------|
| "X is Y when condition" | `model.where(condition).define(X.is_Y())` |
| "X has tier based on score" | Multiple `model.where(range).define(X.tier(value))` |
| "total X across children" | `aggregates.sum(Child.x).per(Parent).where(Child.parent(Parent))` |
| "flag X where threshold exceeded" | `model.where(X.value > X.limit).define(X.is_flagged())` |
| "X and Y agree" | `model.where(math.abs(X.v - Y.v) < epsilon).define(Match.is_reconciled())` |

## Logical operators

| NL | PyRel | Notes |
|----|-------|-------|
| "A **and** B" | `model.where(A, B)` | Multiple args in `.where()` = conjunction |
| "A **or** B" | `model.union(branch_a, branch_b)` | Separate branch per condition |
| "**not** A" | `model.not_(A)` | Negates the full conjunction |
| "**at least** N" | `>= N` | |
| "**no more than** N" | `<= N` | |
| "**exactly** N" | `== N` | |

For string, numeric, date, and aggregation syntax with examples, see [standard-library.md](standard-library.md) and [expression-rules.md](expression-rules.md).

## The nine design principles

1. **Declare the output first.** Define the `Property` or `Relationship` the rule produces before writing the logic — makes the rule's shape explicit and reviewable.
2. **Relationship for boolean flags, Property for values.** Boolean outputs (`is_compliant`, `is_overdue`) are unary Relationships; categorical or numeric outputs (`risk_tier`, `total_cost`) are Properties. Mixing causes `FDError` or silent data loss.
3. **Conditions are conjunctive by default.** Multiple `.where()` arguments are AND; use `model.union()` for OR. Never mix AND and OR in one `.where()`.
4. **Classification rules must be mutually exclusive.** Overlapping conditions give the Property multiple values per entity → `FDError`. Use `<` on one boundary, `>=` on the other.
5. **Decide exhaustive vs partial.** Should every entity get a classification? If yes, add a default/catch-all rule — but implement it through an intermediate property. A catch-all whose body reads `model.not_()` of the property it defines is recursion through negation and aborts with `UnsupportedRecursionError` when that property is queried; route the specific rules through an intermediate property and derive the final one from it (pattern in [pyrel-rule-patterns.md](pyrel-rule-patterns.md#classification-rules)). If no, document which entities carry no value.
6. **Test boundary conditions.** What happens when the value is exactly at the threshold?
7. **Prefer data-driven thresholds.** `Entity.amount > Entity.credit_limit` beats a hardcoded `> 10000`. Explore `min`/`max`/`avg` of the property before choosing any literal — the data's actual scale decides the threshold (workflow step 3 in [SKILL.md](../SKILL.md#rules-authoring) mandates this check).
8. **One rule per derived property.** Keep all conditions producing the same output together, for readability and correctness review.
9. **Reuse an existing classification; don't re-derive it from a composite.** When a downstream rule or summary references a tier/segment/flag an earlier step already produced, carry that derived property forward. Re-thresholding a new composite metric (e.g. classifying on `centrality × probability`) invents a second, inconsistent definition of the same label. Define a fresh threshold only when the question asks for a genuinely new classification.

## Projecting boolean flags into a table

Unary Relationships can't appear in `select()`. Query each flag's matching IDs separately and merge:

```python
def query_flag(model, relationship, concept, flag_name):
    """Query entities matching a boolean Relationship, return df with flag column."""
    df = model.where(relationship()).select(concept.id.alias("id")).to_df()
    df[flag_name] = True
    return df

base_df = model.select(Entity.id.alias("id"), Entity.name.alias("name")).to_df()
flag_df = query_flag(model, Entity.fails_check, Entity, "fails_check")
base_df = base_df.merge(flag_df, on="id", how="left")
base_df["fails_check"] = base_df["fails_check"].fillna(False)
```

This merge pattern is ONLY for surfacing boolean Relationships. Any derived value that depends on the flags — counts, tiers, risk scores — must still be declared with `model.Property()` + `define()`. Computing a new derived column from the merged DataFrame (`.apply()`, `.map()`, arithmetic) is the same mistake as computing the rule output in pandas.
