## Pre-Solve Validation

Run these checks after building the formulation and before calling `problem.solve()`. Catching issues here is dramatically cheaper than debugging infeasible or nonsensical solutions after the fact. The checks are ordered by severity — earlier checks catch more fundamental problems.

### 1. Entity population — do variables exist?

The most common pre-solve failure: `problem.display()` prints `Problem (...): empty` (and `problem.num_variables() == 0`). This means entity creation produced nothing — typically a join mismatch in `.where()` or missing data.

**What to check:**
- `problem.num_variables() > 0` — if zero, no solve will produce results
- Variable count matches expectations — e.g., if you have 50 products, expect ~50 product variables
- For cross-product concepts, verify both source concepts have loaded data

**How to diagnose zero entities:**
- Query each source concept independently: `model.select(Concept).to_df()` — confirm non-empty
- Test join conditions one at a time in `.where()` clauses to isolate which filter eliminates all entities
- Check for case mismatches or type mismatches in join keys (string "123" vs integer 123)

```python
# Verify concepts have data before formulation
assert len(model.select(Product).to_df()) > 0, "Product concept has no entities"
assert len(model.select(Route).to_df()) > 0, "Route concept has no entities"

# After formulation, verify variable count
problem.display()
model.require(problem.num_variables() > 0)  # No variables created — check entity creation joins
```

### 2. Constraint population — are constraints active?

Zero constraints is almost as bad as zero variables. `model.require()` produces empty constraint sets when `.where()` filters match nothing. A subtler mode: a per-entity constraint that should fire on every entity drops the bodies for entities whose bound property is empty (PyRel relational semantics) — `num_constraints()` is short of expected, but it doesn't tell you *which* one vanished.

**What to check:**
- `problem.num_constraints() > 0`
- Constraint count is proportional to the entities they constrain — e.g., one capacity constraint per facility
- At least one forcing constraint exists for minimize objectives (a constraint that requires positive variable values, e.g., `sum(x) >= demand`)
- **Per-constraint cardinality** for any per-entity constraint: capture the `satisfy()` return value and assert it grounded on the expected number of entities. `num_constraints()` is a global check; per-constraint cardinality + `display(constr_ref)` localize *which* one is short.

```python
# Capture at satisfy time; pass name=[Entity.id] so display rows are identifiable.
cap_constr = problem.satisfy(
    model.require(usage <= Entity.cap),
    name=["cap", Entity.id],
)
n_grounded = len(model.select(cap_constr).to_df())
n_entities = len(model.select(Entity).to_df())
if n_grounded != n_entities:
    # Drill in. limit caps very-large constraints; summary header shows true totals.
    problem.display(cap_constr, limit=10)
    raise AssertionError(
        f"cap_constr fired {n_grounded}/{n_entities}: bound data missing for some entities"
    )
```

### 3. Objective population — is the objective meaningful?

**What to check:**
- Exactly one `problem.minimize()` or `problem.maximize()` call
- Objective expression references at least one decision variable (not just data properties)
- `problem.num_min_objectives() + problem.num_max_objectives() == 1`

### 4. Data integrity — garbage in, garbage out

Check domain-specific properties for validity before the solver trusts them as coefficients:

| Check | What to query | Why it matters |
|-------|--------------|----------------|
| **Non-negativity** | Costs, capacities, demands >= 0 | Negative costs flip optimization direction; negative capacity is meaningless |
| **Completeness** | No nulls in properties used as coefficients or bounds | Null coefficients silently drop terms from the formulation |
| **Monotonicity** | PWL breakpoints non-decreasing; time period indices ordered | SOS2 and inventory balance constraints assume ordered sequences |
| **Bound consistency** | Variable lower bound <= upper bound | Contradictory bounds guarantee infeasibility for that variable |
| **Capacity vs demand** | `sum(demand)` vs `sum(capacity)` | If total demand > total capacity without slack variables, the problem is infeasible by construction |

```python
# Check for nulls in critical properties
df = model.select(Route, Route.cost, Route.capacity).to_df()
assert df["cost"].notna().all(), "Route.cost has null values"
assert (df["cost"] >= 0).all(), "Route.cost has negative values"

# Check capacity vs demand feasibility
total_demand = model.select(sum(Customer.demand)).to_df().iloc[0, 0]
total_capacity = model.select(sum(Facility.capacity)).to_df().iloc[0, 0]
if total_demand > total_capacity:
    print(f"WARNING: demand ({total_demand}) > capacity ({total_capacity}) — add slack variables or problem is infeasible")
```

### 5. Formulation structure — does it make sense?

Use `problem.display()` output as the final structural check before solving. See [formulation-display.md](formulation-display.md) for interpreting the output.

**Quick sanity checks from display:**
- All variable types match intent (cont/int/bin)
- Variable bounds are finite and reasonable (not 0 to 1e18)
- Objective expression contains recognizable cost/profit terms
- Constraint expressions reference the right concepts

### Pre-solve checklist (copy-paste)

```python
# Run after formulation, before problem.solve()
problem.display()
model.require(problem.num_variables() > 0)
model.require(problem.num_constraints() > 0)
model.require(problem.num_min_objectives() + problem.num_max_objectives() == 1)
# Problem-specific: adjust counts to match your formulation
# model.require(problem.num_variables() == expected_var_count)
# model.require(problem.num_constraints() >= expected_constraint_count)

# Per-constraint cardinality (for per-entity constraints — catches PyRel
# relational-semantics drops when a bound is empty for some entities):
# cap_constr = problem.satisfy(model.require(...), name=["cap", Entity.id])
# assert len(model.select(cap_constr).to_df()) == len(model.select(Entity).to_df())
# problem.display(cap_constr)  # human-readable view of survivors (limit=N for large)
```

### 6. Multi-arg Properties (Scenario Concept pattern)

When using the Scenario Concept pattern, decision variables are registered as multi-arg Properties:

```python
# Single-arg (standard): one variable per entity
problem.solve_for(Stock.x_quantity, type="cont", name=["qty", Stock.index], lower=0)

# Multi-arg (scenario): one variable per (entity, scenario) pair
x_qty_ref = Float
problem.solve_for(Stock.x_quantity(Scenario, x_qty_ref), type="cont",
                  name=[Scenario.name, "qty", Stock.index], lower=0)
```

The `(Scenario, x_qty_ref)` binding is a dimension index, not a separate variable. `Stock.x_quantity` IS a fully defined decision variable in this pattern. Constraint expressions reference the variable via the ref name (`x_qty_ref`) with `.where()` bindings:

```python
# Constraint using scenario-indexed variable
model.require(
    (sum(Stock.cost * x_qty_ref).per(Scenario) <= Scenario.budget)
    .where(Stock.x_quantity(Scenario, x_qty_ref))
)
```

Do NOT flag multi-arg Properties as missing linking constraints or undefined variables.

---
