<!-- TOC -->
- [Validation Checklist](#validation-checklist)
- [Testing Approaches](#testing-approaches)
- [Debugging Common Failures](#debugging-common-failures)
- [Classification Completeness Verification](#classification-completeness-verification)
<!-- /TOC -->

## Validation Checklist

Run these checks on every rule before considering it complete.

| # | Check | What to verify | Failure signal |
|---|-------|---------------|----------------|
| 1 | **Output type** | `Relationship` for boolean flags, `Property` for values | `FDError` if Property gets multiple values per entity |
| 2 | **Property exists** | All referenced properties are declared in the model | `AttributeError` or zero results |
| 3 | **Join path valid** | `.where()` relationships traverse existing paths | Zero results despite matching data |
| 4 | **Type alignment** | Compared values are same type (`Integer` vs `Float` vs `String`) | Silent zero matches from type mismatch |
| 5 | **Classification exclusive** | No entity matches two classification conditions | `FDError` on the Property |
| 6 | **Aggregation scoped** | `.per()` present when aggregating across entities | Single global result instead of per-entity |
| 7 | **No circular deps** | Rule outputs do not feed back into their own conditions | Runtime error or infinite loop |

**Quick validation pattern:**

```python
# Check that a rule produces results on test data
result = model.where(Entity.is_flagged()).select(Entity.id).to_df()
print(f"Flagged: {len(result)} entities")
assert len(result) > 0, "Rule produced zero results — check conditions"
```

---

## Testing Approaches

### Known-Data Testing

Load a small test dataset with known expected outcomes, run the rule, and compare.

```python
import pandas as pd

# 1. Load test data with known outcomes
test_df = pd.DataFrame({
    "id": [1, 2, 3],
    "amount": [500.0, 1500.0, 800.0],
    "limit": [1000.0, 1000.0, 1000.0],
})
# ... load into model concepts ...

# 2. Apply rule (define statements)
# ... rule code here ...

# 3. Verify results
flagged = model.where(Order.exceeds_limit()).select(Order.id).to_df()
expected = {2}  # Only order 2 (amount 1500 > limit 1000)
actual = set(flagged["id"])
assert actual == expected, f"Expected {expected}, got {actual}"
```

### Boundary Testing

Test values exactly at thresholds to verify operator correctness.

| Threshold | Test values | Expected behavior |
|-----------|------------|-------------------|
| `>= 50000` (VIP tier) | 49999, 50000, 50001 | 49999 → not VIP; 50000 → VIP; 50001 → VIP |
| `> limit` (violation) | limit - 1, limit, limit + 1 | Only `limit + 1` is flagged |
| `< 0.01` (tolerance) | 0.009, 0.01, 0.011 | 0.009 → within tolerance; 0.01 → boundary; 0.011 → discrepancy |

### Coverage Testing

Verify the proportion of entities affected by a rule.

```python
from relationalai.semantics.std import aggregates

total = model.select(aggregates.count(Entity)).to_df().iloc[0, 0]
flagged = model.where(Entity.is_flagged()).select(aggregates.count(Entity)).to_df().iloc[0, 0]
print(f"Flagged: {flagged}/{total} ({flagged/total*100:.1f}%)")
```

If 100% or 0% of entities are flagged, the rule likely has a logic error.

### Negative Testing

Verify that entities not matching the rule do NOT receive the derived property.

```python
# Entities that should NOT be flagged
clean = model.where(Entity, model.not_(Entity.is_flagged())).select(Entity.id).to_df()
for entity_id in known_clean_ids:
    assert entity_id in set(clean["id"]), f"Entity {entity_id} should not be flagged"
```

---

## Debugging Common Failures

| Symptom | Likely Cause | Debug Step |
|---------|-------------|------------|
| Rule produces zero results | Condition never matches | Query each condition property individually: `model.select(Entity.id, Entity.amount).to_df()` |
| Rule flags all entities | Condition too broad or always true | Print condition property distribution to check value ranges |
| `FDError` | Two rules assign different values to same Property | Query overlapping conditions: check which entities match multiple branches |
| Results disappear after chaining | Upstream rule produced no output | Verify upstream rule results before running downstream rule |
| Count is larger than expected | Join expansion (relationship multiplies matches) | Wrap with `distinct()`: `aggregates.count(distinct(Entity))` |
| Missing entities in aggregation | Groups with no matches are omitted | Add `\| 0` fallback: `aggregates.count(X).per(Y) \| 0` |
| Type mismatch — silent zero matches | Comparing `String` property to `Integer` literal | Cast explicitly: `numbers.integer(Entity.text_field)` or `strings.string(Entity.num_field)` |
| Parsed values missing | `parse_number()` or `fromisoformat()` failed on bad input | Select raw and parsed values together to identify failed rows |
| Aggregation returns single row | Missing `.per()` on aggregate expression | Add `.per(GroupKey)` to scope the aggregation |
| Rule works in isolation but fails in chain | Dependency not yet materialized | PyRel is declarative — check that the upstream `define()` is in scope |
| `Query error` / `Unreachable` on `m.define()` chain | `m.define()` references aggregation-computed property in arithmetic (even transitively) | `m.define()` cannot chain on aggregation results at all — not just subtypes. Define the agg property but compute downstream values at query time with pandas |
| `Query error` poisons unrelated queries | Broken `m.define()` (agg-dependent or OR in subtype) in model | Remove the broken definition; it affects ALL queries on the parent entity |
| `Query error` on subtype with OR (`\|`) | Subtype uses `(a == "x") \| (a == "y")` in `where()` | Split into multiple `m.define()` calls — one per OR branch |
| `[Unknown Concept]` on `m.Property()` | Double braces `{{m.X}}` in f-string outputs literal text | Use single braces: `f"{m.Entity} has prop {m.ValueType}"` |
| `AttributeError` on non-existent model function | Non-existent function (e.g., `m.parse_int`, `m.cast`) | Valid model methods: `m.define`, `m.where`, `m.select`, `m.require`, `m.not_`, `m.Concept`, `m.Property`, `m.Relationship`. Standalone: `count/sum/avg/min/max`, `Float/Integer/String/Boolean` |
| `bad operand type for unary ~: 'Chain'` | Used `~` to negate a boolean relationship in `m.where()` | No direct negation for boolean relationships; use two-query pandas subtraction pattern |
| `not` on boolean relationship returns wrong results | Python `not` on a Chain coerces to bool, doesn't negate semantically | Use two-query subtraction: query positive set, query intersection, subtract with `~isin()` |
| `TyperError` / `Type errors detected during type inference` when querying subtypes | Accessing properties directly on subtype concept (`m.FlopMovie.title`) | Bind subtype to parent with `m.Subtype(m.Parent)` in `where()`, then access all properties via `m.Parent.prop` in `select()` |
| `TyperError` when selecting a boolean relationship as column | Boolean relationship (e.g., `m.Entity.was_clicked.alias("col")`) placed in `select()` | Relationships are filter-only — use in `where()` only. To project as column: query all entities, query flagged subset, then `df["flag"] = df["id"].isin(flagged_ids["id"])` |
| `unsupported operand type(s) for *: 'Int128Array' and 'int'` | Snowflake returns Int128 dtype columns; pandas can't do arithmetic on them | Auto-fixed by `execute_query` patching `.to_df()` → `.to_df().pipe(_fix_df)`. Manual fix: `df[col] = df[col].astype("int64")` |
| `Unreachable` on cross-entity `m.define()` | Dot-chain navigation (`m.EntityA.rel.prop`) in `m.define()` arithmetic | Use explicit join: `m.EntityB.prop` in arithmetic + `m.EntityA.rel(m.EntityB)` in `.where()` |

---

## Classification Completeness Verification

For classification rules, verify MECE (mutually exclusive, collectively exhaustive).

**Check for unclassified entities:**

```python
unclassified = model.where(
    Entity,
    model.not_(Entity.tier),
).select(Entity.id).to_df()

if len(unclassified) > 0:
    print(f"WARNING: {len(unclassified)} entities have no tier assigned")
    print(unclassified.head())
```

**Check for overlap (detect before `FDError`):**

Use a temporary `Relationship` instead of `Property` to detect multi-assignment without error:

```python
# Temporarily define as Relationship to allow multiple values
Entity.tier_check = model.Relationship(f"{Entity} has tier check {String:tier}")
# ... apply same conditions as the real classification ...

# Count tiers per entity — any entity with count > 1 has overlap
from relationalai.semantics.std import aggregates
tier_count = aggregates.count(Entity.tier_check).per(Entity)
overlaps = model.where(tier_count > 1).select(Entity.id).to_df()
assert len(overlaps) == 0, f"Overlapping conditions for: {overlaps['id'].tolist()}"
```
