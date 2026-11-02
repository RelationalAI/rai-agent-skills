## Pre-Solve Validation

*The `display_string` reads in this file require `relationalai>=1.29`.*

Run these checks after building the formulation and before calling `problem.solve()`. Catching issues here is dramatically cheaper than debugging infeasible or nonsensical solutions after the fact. The checks are ordered by severity — earlier checks catch more fundamental problems.

### 1. Entity population — do variables exist?

The most common pre-solve failure: `problem.display()` prints `Problem (...): empty` (and `problem.num_variables() == 0`). This means entity creation produced nothing — typically a join mismatch in `.where()` or missing data.

**How to diagnose zero entities:**
- Query each source concept independently: `model.select(Concept).to_df()` — confirm non-empty
- Test join conditions one at a time in `.where()` clauses to isolate which filter eliminates all entities
- Check for case mismatches or type mismatches in join keys (string "123" vs integer 123)

Count code: [Cardinality checks](#cardinality-checks) below.

### 2. Constraint population — are constraints active?

Zero constraints is almost as bad as zero variables. `model.require()` produces empty constraint sets when `.where()` filters match nothing.

**What to check:**
- `problem.num_constraints() > 0`
- Constraint count is proportional to the entities they constrain — e.g., one capacity constraint per facility
- At least one forcing constraint exists for minimize objectives (a constraint that requires positive variable values, e.g., `sum(Decision.x) >= demand`)
- **Per-constraint cardinality** for any per-entity constraint: capture the `satisfy()` return value and assert it grounded on the expected number of entities. `num_constraints()` is a global check; per-constraint cardinality + a `display_string` select on the ref localize *which* one is short.

### Cardinality checks

A formulation can register every call and still ground nothing: a join that matched no rows, a variable registered with zero instances, a per-entity constraint that grounded for only some entities. None of these raises. Capture each `solve_for` / `satisfy` return value ([diagnostic-workflow.md](diagnostic-workflow.md) > The capture-ref pattern) and compare its row count with the entity count it should match:

```python
from relationalai.semantics.std import aggregates as aggs

def rows(x):
    return len(model.select(x).to_df())

# Entity population: 0 rows = join mismatch or missing data (§ 1)
assert rows(Route) > 0, "Route has no entities"

# Binding: registration is not binding. A where= that matches nothing
# registers the variable with zero instances and the solver runs on an empty set.
x_flow = problem.solve_for(Route.x_flow, name=["flow", Route.id], lower=0)
assert rows(x_flow) == rows(Route), "x_flow is missing instances"

# Grounding: a per-entity body grounds no row for an entity whose bound is
# empty, so a sparse Route.cap leaves those routes unconstrained.
cap = problem.satisfy(model.require(Route.x_flow <= Route.cap), name=["cap", Route.id])
if rows(cap) != rows(Route):
    # See which grounded. Needs the install AND name= on every variable;
    # without either, display_string is silently null.
    problem.install_display_strings()
    print(model.where(aggs.limit(10, cap.name))
               .select(cap.name, cap.display_string).to_df())
    raise AssertionError(f"cap grounded {rows(cap)}/{rows(Route)}: Route.cap missing for some routes")

# Coefficient presence: an unpopulated coefficient has no tuple, so its term
# silently drops out (OPTIMAL on a vacuous objective). Count non-nulls, not
# rows: a select keeps a row per entity, with a null where the value is missing.
assert model.select(Route, Route.cost).to_df()["cost"].notna().sum() == rows(Route)
```

`problem.num_variables()`, `num_constraints()`, `num_min_objectives()` and `num_max_objectives()` are engine-side Integer Relationships. Read one as a scalar with `model.select(problem.num_constraints()).to_df().iloc[0, 0]`, or assert it as an IC:

```python
model.require(problem.num_constraints() == aggs.count(Source) + aggs.count(Sink))  # cap per Source + demand per Sink
```

The IC form has two limits. It persists for the model's lifetime, so an exact count goes stale as soon as a re-solve adds constraints; in an iterative loop use the scalar or `rows(ref)` reads. And a violated IC reports only when the config sets `compiler: require_mode: report` (default `ignore`), and never on the SQL backend.

### 3. Objective population — is the objective meaningful?

**What to check:**
- Exactly one `problem.minimize()` or `problem.maximize()` call **for an optimization or `sensitivity=True` solve** — a pure feasibility / CSP solve correctly has **zero**. `conflict=True` is objective-agnostic: it needs no objective, but tolerates one, so you can diagnose an infeasible *optimization* model without dropping its objective
- Objective expression references at least one decision variable (not just data properties)
- `problem.num_min_objectives() + problem.num_max_objectives() == 1` (optimization/sensitivity; `== 0` for pure feasibility/CSP; `conflict=True` allows either)

### 4. Data integrity — garbage in, garbage out

Check domain-specific properties for validity before the solver trusts them as coefficients. The PyRel-specific trap is completeness: a null coefficient or bound produces no tuple in the join, so its term silently drops out of the formulation (PyRel relational semantics).

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

### 6. CSP-style cross-check — `Problem(model, ...)` / solver pairing

Before solving, verify the `Problem(model, ...)` type matches the chosen solver:

| `Problem(model, ...)` | Compatible solvers | Incompatible — known failure modes |
|-----------------------|--------------------|------------------------------------|
| `Float` | `"highs"`, `"gurobi"`, `"ipopt"` | `"minizinc"` raises `JobInvalidRequestError: ... only supports (int)` |
| `Integer` | `"minizinc"` | `"highs"`, `"gurobi"`, `"ipopt"` raise `JobInvalidRequestError: ... only supports (float)` |

```python
# Pre-solve type check — uses the documented public attribute
if solver_name == "minizinc":
    # MiniZinc requires Integer-typed Problem
    # (a Float decision or Float data in an expression fails)
    assert problem.numeric_type is Integer, (
        "MiniZinc requires Problem(model, Integer)."
    )
else:
    # HiGHS, Gurobi and Ipopt accept only Float-typed Problems
    assert problem.numeric_type is Float, (
        f"{solver_name} requires Problem(model, Float); for Integer use minizinc."
    )
```

For the full CSP-style formulation guide, see [csp-formulation.md](csp-formulation.md).

### 7. Multi-arg Properties (Scenario Concept pattern)

When using the Scenario Concept pattern, decision variables are registered as multi-arg Properties:

```python
# Single-arg (standard): one variable per entity
problem.solve_for(Stock.x_quantity, type="cont", name=["qty", Stock.index], lower=0)

# Multi-arg (scenario): one variable per (entity, scenario) pair
x_qty_ref = Float.ref()
problem.solve_for(Stock.x_quantity(Scenario, x_qty_ref), type="cont",
                  name=[Scenario.name, "qty", Stock.index], lower=0)
```

The `(Scenario, x_qty_ref)` binding is a dimension index, not a separate variable. `Stock.x_quantity` IS a fully defined decision variable in this pattern. Constraint expressions reference the variable via the ref name (`x_qty_ref`) with `.where()` bindings:

```python
# Constraint using scenario-indexed variable
problem.satisfy(model.where(Stock.x_quantity(Scenario, x_qty_ref)).require(
    sum(Stock.cost * x_qty_ref).per(Scenario) <= Scenario.budget
))
```

Do NOT flag multi-arg Properties as missing linking constraints or undefined variables.

---
