# Solution Extraction Details

## Table of Contents
- [Engine-Side Result Attributes (Relationships)](#engine-side-result-attributes-relationships)
- [Querying Solution Values — Full Patterns](#querying-solution-values--full-patterns)
- [Variable.values() Back-Pointer Naming Rule](#variablevalues-back-pointer-naming-rule)
- [Constraint Back-Pointer Access (marginals & conflict membership)](#constraint-back-pointer-access-marginals--conflict-membership)
- [Silent-Failure Warnings](#silent-failure-warnings)
- [Exporting Solution Results to Tables](#exporting-solution-results-to-tables)
- [Multiple Solutions](#multiple-solutions)
- [Iterative Solving](#iterative-solving)
- [Scenario / Parametric Solving](#scenario--parametric-solving)

---

## Engine-Side Result Attributes (Relationships)

After `problem.solve()`, these accessors return Relationships usable in `model.require()`, `model.select()`, and solver expressions (the Python-side `solve_info()` counterparts live in SKILL.md > Solution Extraction):

| Method | Return type | Description |
|--------|-------------|-------------|
| `problem.termination_status()` | Relationship | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `problem.objective_value()` | Relationship | Optimal objective value |
| `problem.num_points()` | Relationship | Number of solutions returned |
| `problem.error()` | Relationship | Error message tuple (if solve failed) |
| `problem.printed_model()` | Relationship | Text representation (with `print_format=`) |
| `problem.num_variables()` | Relationship | Total registered variables |
| `problem.num_constraints()` | Relationship | Total constraints |
| `problem.num_min_objectives()` | Relationship | Number of minimize objectives |
| `problem.num_max_objectives()` | Relationship | Number of maximize objectives |

```python
# Engine-side: integrity constraint on status
model.require(problem.termination_status() == "OPTIMAL")
```

---

## Querying Solution Values — Full Patterns

### `populate=True` (default) — `model.select()` variations

With `populate=True`, solved values are written back into the model as property values. Query them like any other model data — with entity context, aliases, and filtering:

```python
# Display results — .inspect() prints to stdout (preferred for display-only)
model.select(
    MachinePeriod.machine.machine_id.alias("machine_id"),
    MachinePeriod.period.pid.alias("period"),
    MachinePeriod.x_maintain.alias("maintained"),
).where(MachinePeriod.x_maintain > 0.5).inspect()

# Use .to_df() when you need the DataFrame for further Python analysis
assignments_df = model.select(
    TechnicianMachinePeriod.technician.technician_id.alias("technician"),
    TechnicianMachinePeriod.machine.machine_id.alias("machine"),
    TechnicianMachinePeriod.period.pid.alias("period"),
).where(TechnicianMachinePeriod.x_assigned > 0.5).to_df()

# Binary variable selection — filter active decisions
model.select(
    Edge.i.alias("from"), Edge.j.alias("to")
).where(Edge.x_edge > 0.5).inspect()
```

### `populate=False` — `Variable.values()` on ProblemVariable

Use `populate=False` + `Variable.values()` for loop-based entity exclusion/partition scenarios. For Scenario Concept workflows, use `model.select()` — the scenario dimension is part of the variable identity. For loop workflows where multiple Problems share decision variables, `populate=False` prevents one solve from overwriting another's results.

`solve_for()` returns a `ProblemVariable` — a Concept that can be used in `model.define()`, `model.select()`, and `.ref()`. Call `.values(sol_index, value_ref)` on it to extract solution values.

```python
# solve_for() returns a ProblemVariable concept
assign_var = problem.solve_for(Assignment.x, type="bin", populate=False)

problem.solve("highs")

# Extract solution values using Variable.values()
value_ref = Float.ref()
df = model.select(
    assign_var.assignment.worker.name.alias("worker"),
    value_ref.alias("value"),
).where(assign_var.values(0, value_ref), value_ref > 0.5).to_df()
# Returns entity-aware results with proper identity columns

# For multiple solutions (e.g., from MiniZinc with solution_limit),
# pass different sol_index values (0-based)
```

**Key rules:**
- Use `model.select()` by default — it gives entity-aware results with proper identity columns
- Use `Variable.values()` for scenario loops or when you need per-variable extraction with `populate=False`
- The `ProblemVariable` returned by `solve_for()` is a Concept — you can traverse its relationships in `model.select()` for entity context
- `satisfy()` returns `ProblemConstraint` and `minimize()`/`maximize()` return `ProblemObjective` — also Concepts usable with `model.define()`, `model.select()`, `.ref()`

---

## Variable.values() Back-Pointer Naming Rule

Each **non-value** field in the Property's format string becomes a back-pointer attribute on the `ProblemVariable`. The **last** field is the value field — you read it via `var.values(sol_idx, val_ref)` and it is NOT a back-pointer. For each non-value field, the back-pointer attribute name is the **explicit `:name` from the format string if present**, otherwise the **lowercased type name**. Examples:

| Property definition | Back-pointers on the returned var | Value field |
|---|---|---|
| `f"{Assignment} has {Float:x}"` | `var.assignment` (lowercased type) | `x` |
| `f"{Edge:e} has {Float:flow}"` | `var.e` (explicit `:e` overrides `edge`) | `flow` |
| `f"{Queen} is in {Integer:column}"` | `var.queen` | `column` |
| `f"{Player} in {Integer:week} is in {Integer:group}"` | `var.player`, `var.week` | `group` |
| `f"cell {Integer:i} {Integer:j} is {Integer:x}"` | `var.i`, `var.j` (no entity concept) | `x` |
| `f"{MachinePeriod} has {Float:x}"` | `var.machineperiod` (lowercased as-is, NOT `machine_period`) | `x` |
| `f"{Float:x}"` | none — call `var.values(sol_idx, val)` directly | `x` |

The lowercased type name is the type name converted to lowercase **as-is** — no underscores or snake_case conversion. `MachinePeriod` becomes `machineperiod`, not `machine_period`.

---

## Constraint Back-Pointer Access (marginals & conflict membership)

`satisfy()` returns a `ProblemConstraint` — a Concept, like the `ProblemVariable` from `solve_for()`. When you request `sensitivity=True` or `conflict=True`, the marginal and membership attributes read **straight off it**, single-valued (no `sol_index`):

- `con.shadow_price`, `con.basis_status` — populated by `sensitivity=True`
- `con.in_conflict` — populated by `conflict=True`

It also carries an **entity back-pointer** for each grounding key declared via `keyed_by=` at `satisfy()` time, mirroring the variable back-pointer. That lets a marginal or conflict flag **join to entity data by key** (`con.entity.prop`) instead of parsing the constraint's name string. The back-pointer attribute is the **dict key you chose** in the declaration — `keyed_by={"resource": Resource}` reads back as `cap.resource` — not the `name=` display label (`"cap"`). The `name=` kwarg only sets the constraint's display name; it plays no part in the back-pointer.

```python
# Constraint family: one capacity limit per Resource, keyed by its Resource:
cap = problem.satisfy(
    model.require(usage <= Resource.capacity),
    name=["cap", Resource.name],
    keyed_by={"resource": Resource},
)
# ... an objective must already be set — duals are objective marginals:
problem.solve("highs", sensitivity=True)

# The entity back-pointer (cap.resource) joins the marginal to its entity by key:
model.select(cap.resource.name, cap.resource.capacity, cap.shadow_price).inspect()
```

**`keyed_by` is required for reading families back by key.** A constraint **family** — one logical constraint instantiated per entity (a capacity limit per Resource, a coverage floor per Shift) — only exposes per-instance back-pointers if its grounding keys are **declared** at formulation time (`keyed_by={"resource": Resource}`); there is no automatic constraint back-pointer. Without the declaration, a marginal / conflict flag can't be paired with its entity. A family grounded over several entities takes several keys (one back-pointer each); a scalar grounding takes a value reference (`keyed_by={"i": X.i}`). The authoritative formulation idiom — including the key-uniqueness rule (a too-coarse key raises at solve) — lives in `rai-prescriptive-problem-formulation/references/constraint-formulation.md`.

---

## Silent-Failure Warnings

`ProblemVariable` is a Concept subclass, and Concepts return a `Chain` from `__getattr__` for unknown attribute names instead of raising. Three common mistakes all silently return a `Chain` and produce empty or garbage results (not an `AttributeError`):

1. Writing `var.edge` when the format string said `{Edge:e}` (explicit `:name` was `:e`).
2. Writing `var.column` or `var.group` when the name is a **value** field — those are not back-pointers; read them through `var.values(sol_idx, val_ref)`.
3. Writing `var.machine_period` when the concept is `MachinePeriod` — the correct name is `var.machineperiod` (lowercased, no underscores).

Always match the attribute name to a non-value field name in the format string.

---

## Exporting Solution Results to Tables

After extracting solution values, export them to a Snowflake table using `.into().exec()`:

```python
# Export optimal allocations to a results table
results_table = model.Table("DB.SCHEMA.OPTIMIZATION_RESULTS")
model.select(
    Route.origin.name.alias("FROM_SITE"),
    Route.dest.name.alias("TO_SITE"),
    Route.x_flow.alias("OPTIMAL_FLOW"),
).where(Route.x_flow > 1e-6).into(results_table).exec()
```

**Replace vs update:** Use `update=True` to merge into an existing table (e.g., appending scenario results):

```python
results_table = model.Table("DB.SCHEMA.SCENARIO_RESULTS")
model.select(
    Food.name.alias("FOOD"), Food.amount.alias("AMOUNT"),
).into(results_table, update=True).exec()
```

The `.into(table)` call writes query results to the specified Snowflake table. Use `update=True` to merge into an existing table rather than replacing it.

## Multiple Solutions

v1 supports multiple solutions natively:

- **Request multiple solutions:** `problem.solve("minizinc", solution_limit=10)` — `solution_limit` is a first-class parameter
- **Check count:** `problem.num_points()` (Relationship) or `problem.solve_info().num_points` (Python)
- **Extract solution values:** Use `Variable.values(sol_index, value_ref)` on the `ProblemVariable` returned by `solve_for()` for structured access via back-pointers. For multi-solution access, use different `sol_index` values.

```python
# Solve with multiple solutions
problem = Problem(model, Float)
amount_var = problem.solve_for(Food.x_amount, lower=0)
problem.minimize(sum(Food.cost * Food.x_amount))
problem.solve("minizinc", solution_limit=5)
si = problem.solve_info()
print(f"Found {si.num_points} solutions")

# Extract solution at index 0 (preferred: Variable.values())
value_ref = Float.ref()
sol0_df = model.select(
    amount_var.food.name.alias("food"),
    value_ref.alias("amount"),
).where(amount_var.values(0, value_ref), value_ref > 0.001).to_df()

# Extract solution at index 2
sol2_df = model.select(
    amount_var.food.name.alias("food"),
    value_ref.alias("amount"),
).where(amount_var.values(2, value_ref), value_ref > 0.001).to_df()

```

**How many solutions to request:**

Two distinct sizing rules apply, depending on the use case:

1. **Human-comparison mode (3–10):** When the primary use is enabling human evaluation — like Google Maps showing a few route options — humans are not effective at comparing hundreds of alternatives. If there is an analytical way to compare solutions, that criterion belongs in the objective function, not in post-hoc filtering of a large set.

2. **Audit / witness enumeration mode (above feasible-set size):** When the use is "find ALL configurations violating the property" or "enumerate every valid build" (CSP-style audit / witness), `solution_limit` must exceed the expected feasible-set size so the search terminates with `OPTIMAL` (= search exhausted) rather than `SOLUTION_LIMIT` (= stopped at K with more remaining). `SOLUTION_LIMIT` is a valid status for K-of-many enumeration but its order is solver-dependent — fine for sampling, problematic when downstream tests expect a deterministic full set. See `rai-prescriptive-problem-formulation/references/csp-formulation.md` § 4 and `rai-prescriptive-problem-formulation/examples/audit_witness.py`.

Requesting very large solution counts (e.g., 100,000) is rarely appropriate in human-comparison mode. The few specialized cases where large solution sets make sense include audit / witness enumeration above, downstream simulation over candidate solutions, or feeding alternatives into a separate evaluation pipeline.

**Status-gated extraction:** for either mode, gate the extraction loop on `termination_status`:

```python
if si.termination_status not in ("OPTIMAL", "SOLUTION_LIMIT"):
    # Solver did not enumerate — do not iterate sol_index; results are undefined
    ...
else:
    n_points = si.num_points or 0
    for sol_idx in range(n_points):
        ...
```

A non-success status with `num_points == 0` (TIME_LIMIT, crash) does NOT mean the search was exhaustive — it means the search did not run to completion. Treating "zero results" as "exhaustive enumeration found nothing" is a silent-failure mode in audit-mode problems (see SKILL.md > Audit / witness mode).

**By problem type:**

| Problem type | Recommended count | Rationale |
|---|---|---|
| Binary assignment (scheduling, shift) | 5–10 | Each solution is a distinct assignment; users can compare alternatives |
| Resource allocation (continuous) | 5–15 | Different trade-off frontiers show budget/return variety |
| Routing (TSP, VRP) | 3–5 | Solutions differ subtly (permutations); diminishing returns above 5 |
| Multi-period/inventory | 3–5 | Large variable counts make diverse solutions expensive |

**Solver-specific limits:**
- **HiGHS:** Limited multi-solution support — typically returns 1–2 solutions. Cap at 5.
- **MiniZinc (Chuffed):** Native support for solution enumeration; can handle hundreds when the feasible space is structurally constrained. For audit / witness use, size above expected feasible-set size; termination is `OPTIMAL` when exhausted, `SOLUTION_LIMIT` when cut off. Requires `Problem(model, Integer)`.
- **Gurobi:** Pool search mode supports 10–20+ solutions efficiently.

## Iterative Solving

Constraints defined over concepts automatically apply to new data added between solves. Pattern:
1. Solve relaxed problem
2. Inspect solution (e.g., find subtours)
3. Add violated constraints as new data
4. Re-solve — existing `problem.satisfy()` picks up new data

## Scenario / Parametric Solving

**Scenario Concept (parameter variations) — preferred when applicable:** Results from a single solve are incorporated into the ontology — queryable via `model.select(Scenario.name, ...).where(Entity.x_var(Scenario, x_ref), x_ref > threshold)`, composable with other model queries, and available for downstream derived properties. Group by `Scenario.name` for comparison tables. Variables are multi-argument Properties indexed by (Entity, Scenario) — the scenario column is part of the variable identity. Use when only parameter values change between scenarios (budget, demand, thresholds). See [examples/scenario_concept_extraction.py](../examples/scenario_concept_extraction.py).

**Loop + where= (entity exclusion):** Each iteration produces results via `Variable.values()` — results live in Python DataFrames, outside the model. Collect per-iteration results in a list, label by scenario. Use `populate=False` to prevent cross-iteration contamination. Required when the problem *structure* changes between scenarios (entities added/removed, constraint graph differs). See [examples/loop_based_extraction.py](../examples/loop_based_extraction.py).
