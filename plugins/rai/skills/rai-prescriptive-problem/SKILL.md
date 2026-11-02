---
name: rai-prescriptive-problem
description: Formulates optimization and constraint-satisfaction problems from ontology models — decision variables, constraints, objectives, problem-type classification, solver selection, global constraints, and pre-solve validation. Use when building, reviewing, debugging, or relaxing a formulation, through the point where a validated Problem and chosen solver are ready to run. Not for executing the solve or interpreting output — status, extraction, sensitivity, conflicts (see rai-prescriptive-results).
---

# Prescriptive Problem
<!-- v1-SENSITIVE -->

> **Requires `relationalai>=1.11.0`.** The dual-guided multi-objective methods here read solver sensitivity via `solve("highs", sensitivity=True)`; earlier versions reject the request. See `rai-setup`. The formulation-display surface requires `relationalai>=1.29.0`: `display_string`, `install_display_strings()`, and a `display()` whose signature is `(*, limit=None, print_output=True)`. A `|` default on an aggregate over decision variables requires `relationalai>=1.13.0`, and a per-entity default inside one (`sum(X.a | model.select(0.0).where(X))`) requires `relationalai>=1.32.0`. Deploy mode (`configure()`, preview) requires `relationalai>=1.30.3`.

## Summary

**What:** Everything before the solve runs — decision variables, constraints, objectives, problem-type classification, solver selection, and pre-solve validation. Assumes a problem has already been selected via discovery.

**When to use:**
- Formulating variables, constraints, and objectives for a selected problem; reviewing or validating an existing formulation
- Translating business requirements into mathematical formulation (and eliciting the constraints users can't articulate upfront)
- Debugging formulations that would produce trivial or infeasible solutions (missing constraints, conflicting bounds, wrong aggregation scope), or relaxing an over-constrained formulation to resolve a reported conflict / IIS
- Classifying the problem type (LP / MILP / QP / QCP / NLP / CSP) and choosing a solver
- Designing multi-concept coordination (flow networks, selection + quantity)

**When NOT to use:**
- Executing the solve, reading status/duals/IIS, quality assessment, or explaining results — see `rai-prescriptive-results`
- Question discovery (what can this ontology answer) — see `rai-discovery`
- PyRel syntax — see `rai-pyrel`; ontology modeling or enrichment — see `rai-ontology`

**Overview:**
1. Ground in the base ontology via `inspect.schema(model)`
2. Define decision variables (type, bounds, scope, naming)
3. Define constraints (forcing, capacity, balance, linking)
4. Define objective(s) (direction, coefficients, multi-component)
5. Validate the complete formulation — including the pre-solver audit that variables/constraints/objectives registered, bound, and grounded
6. Classify the problem type, select the solver, solve and refine (targeted `display_string` diagnosis)
7. Post-solve refinement — present results, surface reactions, iterate on the formulation

---

## Quick Reference — Problem API

```python
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

# Problem(model, Float) for MIP-style; Problem(model, Integer) for CSP-style (see references/csp-formulation.md).
problem = Problem(model, Float)

# Decision variable — prefer scoped form (where=[...]); capture the ref for targeted diagnostics.
x_flow = problem.solve_for(Lane.flow, where=[Lane.active], name=["flow", Lane.item_id, Lane.src_id], lower=0.0, type="cont")

# Constraint — capture the ref; name=[Entity.id] makes display rows identifiable.
cap = problem.satisfy(
    model.require(aggs.sum(Lane.flow).per(Source).where(Lane.from_source(Source)) <= Source.capacity),
    name=["cap", Source.id])

cost = problem.minimize(aggs.sum(Lane.flow * Lane.unit_cost), name="cost")

problem.solve("highs", time_limit_sec=60)   # deploy mode: problem.configure(...) with the same arguments
```

| Method | Signature | Purpose |
|--------|-----------|---------|
| `solve_for` | `(expr, where=, populate=True, name=, type=, lower=, upper=, start=)` | Declare decision variable. Returns `ProblemVariable` (a Concept). Row inspection: `model.select(var.name, var.lower, var.upper).to_df()`. `type`: `"cont"`, `"int"`, `"bin"`. Pass a discriminating `name=` on every variable in the Problem: `display()` raises `ValueError` unless all of them are named, checked once at least one has grounded. An unnamed variable also renders a null `display_string`, and a constant name on a per-entity variable makes rows indistinguishable wherever their remaining terms match too. Use `name=["x", Entity.id]`. `name=` entries may be strings, scalar entity properties, or (relationalai>=1.13) enum members; on 1.12.0 pass `Member.name` |
| `satisfy` | `(expr, name=, keyed_by=)` | Add constraint. Returns `ProblemConstraint`. `keyed_by={"key": Concept}` declares the family's grounding keys as entity back-pointers for post-solve readback — see [constraint-formulation.md](references/constraint-formulation.md) > Declaring constraint keys |
| `minimize` / `maximize` | `(expr, name=)` | Set the (single) objective. Returns `ProblemObjective` |
| `solve` | `(solver, time_limit_sec=, ...)` | Execute — parameters, diagnostics requests, and everything after are `rai-prescriptive-results`. In deploy mode use `configure` |
| `configure` | same signature as `solve` | **Deploy-mode replacement for `solve`:** stores the request for the deployed refresh and runs nothing now. Once per Problem, never with `solve` on the same Problem. See Deploy Mode |
| `verify` | `(*fragments)` | Post-solve constraint check — pass the original `model.require(...)` values (see `rai-prescriptive-results`) |
| `display` | `(*, limit=None, print_output=True)` | Print the whole materialized formulation. `limit=N` caps each table at its first N rows per type section, ordered as plain text (`cap_10` before `cap_2`); header counts stay whole-problem. `print_output=False` returns the text instead of printing. Reading one component is `display_string`, not an argument here |
| `install_display_strings` | `()` | Install the rules that render `display_string` on constraints and objectives. Call once per `Problem`, after the model is fully declared; installing on one Problem does not render another's, even on the same model. `display()` installs on demand, a direct select does not; a repeat call is a no-op. Under Deploy Mode install before deploying. Cost (the published figures are offline in-memory DuckDB; on Snowflake the first query after installing has been measured 131-240s slower), its three limits, and null rows: [formulation-display.md](references/formulation-display.md) > Targeted Inspection with `display_string` |
| `num_variables` / `num_constraints` / `num_min_objectives` / `num_max_objectives` | `()` | Engine-queryable counts; usable in `model.require(...)` before solve |
| `problem.variables` / `.constraints` / `.objectives` | attributes | Registered refs in declaration order — iterate to walk an unfamiliar Problem |

## Deploy Mode (preview)

When the model's config has a `deployment` section, the Problem runs in the deployed model's refresh, not at call time: register it with `problem.configure(solver, ...)`, which takes `solve()`'s arguments and validates them the same way. The formulation is unchanged, the model file holds no queries, and results are read after a refresh (`rai-prescriptive-results` > Deploy-mode results). Snowflake only, after the one-time PAT setup in [prescriptive-deploy-setup.md](../rai-setup/references/prescriptive-deploy-setup.md). Several Problems on one Model each need `name=` (`Problem(model, Float, name="first")`); one may read another's results, and the refresh plan orders them.

---

## Problem Type Classification and Solver Selection

Classify from the formulation itself — variable types, then nonlinearity, then constraint structure:

| Type | Signature |
|------|-----------|
| **LP** | All variables continuous; objective and constraints linear |
| **MILP** | Some integer/binary variables; everything linear (products of integer variables make it nonlinear). Keep Big-M tight |
| **QP** | Quadratic terms in the *objective* only (e.g. covariance risk); constraints linear. Check convexity for a global optimum |
| **QCP** | Quadratic terms in *constraints* (norm bounds); more restrictive solver support |
| **NLP** | Nonlinear functions (`exp`, `log`, `sqrt`); local optima possible; integer + NLP (MINLP) is very hard |
| **CSP** | No meaningful objective — find any feasible solution; discrete combinatorial constraints; benefits from global constraints |

### Support matrix and profiles

| Problem type | Gurobi | HiGHS | Ipopt | MiniZinc |
|---|---|---|---|---|
| LP / MILP | YES / YES | YES / YES | YES / NO | NO / NO |
| QP / QCP | YES / YES | YES (convex obj) / NO | YES / YES | NO / NO |
| NLP | YES | NO | YES | NO |
| Constraint programming | NO | NO | NO | YES |
| Discrete vars / continuous vars | YES / YES | YES / YES | NO / YES | YES / NO |

- **Gurobi** (commercial, via RAI): best on every type it supports — always prefer it when the user has a license. Needs a named prescriptive engine with a Snowflake secret + external access integration in `raiconfig.yaml` (see `rai-setup`); fall back to HiGHS/Ipopt without one.
- **HiGHS** (open-source): LP, MILP, convex QP objectives. No native indicator or SOS constraints: `implies` and SOS1/SOS2 are rewritten to binary big-M form, which needs finite `lower=`/`upper=` on the variables involved (without them the solve raises `RuntimeError: ... backend.failed`). No quadratic constraints, no nonlinear functions.
- **MiniZinc** (open-source, Chuffed backend): CP/CSP. Requires `Problem(model, Integer)` with Integer decisions and data: a Float decision property raises `ValueError` at `solve_for`, and Float data in an expression fails at solve with `[TypeMismatch] Expected 'Number(38,0)'`. `solution_limit=K` enumerates up to K solutions. `OPTIMAL` can also mean the time limit hit after a solution was found (`rai-prescriptive-results/references/solver-parameters.md` > `solution_limit` semantics). Of its global constraints, PyRel exposes only `all_different`, `implies` and SOS1/SOS2. Native logs need `log_to_console=True`.
- **Ipopt** (open-source): smooth continuous NLP, local optima only; no integer/binary variables (will FAIL).

| Your problem has... | Gurobi available | No Gurobi license |
|---|---|---|
| Binary/integer + linear (MILP) | **Gurobi** | HiGHS |
| Binary/integer + quadratic (MIQP) | **Gurobi** | (no open-source alternative) |
| Continuous + linear/quadratic-objective | **Gurobi** | HiGHS |
| Continuous + quadratic constraints (QCP) | **Gurobi** | Ipopt |
| Continuous + nonlinear (NLP) | **Gurobi** or Ipopt | Ipopt |
| Discrete constraint satisfaction / multiple solutions | MiniZinc | MiniZinc |

With no objective, a discrete constraint-satisfaction model goes to MiniZinc; anything else runs as a feasibility solve on the solver its constraints need, from the table. Which operators each solver accepts on decision variables (`%`, `//`, trig and rounding are rejected on all of them): [numerical-and-mip.md](references/numerical-and-mip.md) > Operator and Construct Compatibility by Solver.

### MIP-style vs CSP-style

Most problems can be written either way, and the choice is usually preference. What is structural:

- **MIP-style is forced** (`Problem(model, Float)` + HiGHS/Gurobi/Ipopt) by any continuous decision variable or continuous data in a constraint (an Integer Problem rejects both), or a QP objective.
- **CSP-style is required as written** for an `implies` whose antecedent is anything but `x == 0` / `x == 1` on one variable, such as a `decision_id == k` cascade: HiGHS and Gurobi reject it. To keep such a model MIP (for example with continuous data), give each (entity, option) pair its own binary with a one-hot constraint, so every antecedent is `b == 1` ([csp-formulation.md](references/csp-formulation.md) § 2e shows the shape).
- **CSP-style is markedly easier** (`Problem(model, Integer)` + MiniZinc) for `all_different`, `!=` / `==` between decision variables and pairwise `count` over their equality (the MIP path takes no native `!=`: each pair needs binary indicators with big-M), and for multi-solution enumeration.
- **Either works** for `min`/`max` objectives, other `count`s over decision variables, `implies` cascades on a 0/1 antecedent and products of decision variables: MiniZinc takes them directly; apart from `implies` (solver support below), MIP needs them linearized (an auxiliary `t` for `max`; for a product, McCormick (exact only when one factor is binary and the other bounded), otherwise a non-convex QP on Gurobi).
- **Performance:** MIP tends to win when the LP relaxation is tight, and reports a gap on `TIME_LIMIT`; CP tends to win on logical / global-constraint structure. If it matters for an instance, try both. Writing-time idioms: [csp-formulation.md](references/csp-formulation.md).

### Global constraints

`all_different`, `implies`, SOS1/SOS2 give the solver combinatorial structure, with solver requirements: `all_different` → MiniZinc (else O(n²) pairwise inequalities); `implies` → Gurobi or MiniZinc, or HiGHS on bounded variables (rewritten to big-M); SOS1/SOS2 → Gurobi, or HiGHS / MiniZinc on bounded variables. Syntax, examples and per-solver coverage: [global-constraints.md](references/global-constraints.md).

---

## Formulation Workflow

**Interaction mode:** ask the user first — **Guided** (confirm variables, constraints, objective at each step; framing involves judgment about hard vs soft and scoping) or **One-shot** (best single pass, review after).

### Step 1: Ground in the base ontology

Before writing `solve_for` / `satisfy` / `minimize` / `maximize`, confirm every name and type against the real schema:

```python
from relationalai.semantics import inspect
schema = inspect.schema(model)
for name in referenced_concepts:
    assert name in schema, f"Concept {name} not in model"
```

Catches the two silent failure modes behind most prescriptive errors: **hallucinated surface** (`Customer.tier` when the real property is `Customer.category` — the solver happily runs on wrong variables) and **wrong-type inference** (Integer treated as Float, masking incorrect bound derivation).

**Reuse upstream derived surface.** Subtypes and properties earlier steps wrote back (classification subtypes, centrality scores, flags) are in `inspect.schema(model)` — reference them directly rather than re-deriving. See [examples/chained_rules_prescriptive.py](examples/chained_rules_prescriptive.py).

**Confirm modeled dimensions.** If the problem spans periods/scenarios/categories, that dimension must exist — as a Concept (`Week`, `Scenario`), an `Integer` ref scoped via `std.common.range()`, or a `model.Enum` (relationalai>=1.12; enum-indexed `solve_for` creates one binary per (entity, member) — [csp-formulation.md](references/csp-formulation.md) § Enum-indexed decision). **Never** iterate the dimension in Python or hand-enumerate its values. See `rai-ontology` if enrichment is needed.

**When to skip:** small greenfield models or one-shot formulations you just wrote yourself.

### Step 2: Define Variables

What can the solver control? Identify the primary decision entity, then auxiliary/aggregation variables; choose types (cont/int/bin) and bounds from data; for minimize objectives include a slack/unmet variable to avoid infeasibility. Full treatment (context integration, entity creation, parametric/time-indexed, slack): [variable-formulation.md](references/variable-formulation.md).

### Step 3: Define Constraints

What must the solution satisfy? Add **forcing constraints first** (they prevent trivial zero solutions on minimize), then capacity/resource from data properties, then flow conservation for network structure. Derive parameters from data ranges. For multi-period recurrence (inventory balance, sequencing), use declarative quantification — `Concept.ref()` adjacency joins (`w_prev.num == w.num - 1`) or `where=[t == std.common.range(start, stop)]` — one `satisfy()` grounds all periods: [constraint-formulation.md](references/constraint-formulation.md) > Temporal recurrence, [examples/multi_period_flow_conservation.py](examples/multi_period_flow_conservation.py). Canonical constraint shapes per problem family: [problem-patterns-and-validation.md](references/problem-patterns-and-validation.md).

### Step 4: Define Objective(s)

Map the stated goal to minimize/maximize ([objective-formulation.md](references/objective-formulation.md)). Check trivial-solution risk: "if all variables = 0, are all constraints satisfied?" — if yes, Step 3 needs a forcing constraint. **Competing objectives?** A penalty bundling two concerns, or a constraint representing a competing goal, may mean the user wants the tradeoff explored — [multi-objective-formulation.md](references/multi-objective-formulation.md) (epsilon constraint). **Parameter what-if?** Parameterize with the Scenario Concept pattern — one solve over all scenarios, results queryable in the ontology for the rest of the solving process: [scenario-analysis.md](references/scenario-analysis.md).

### Step 5: Validate

Structural checks: every variable in ≥1 constraint (a variable appearing *only* in the objective gets pushed straight to a bound — usually a missing constraint, not a modeling choice); every constraint references ≥1 decision variable; `.where()` join paths connect to actual data; bounds consistent (lower ≤ upper); exactly one objective for an optimization solve, zero for pure feasibility/CSP.

- **Trivial-solution gate (before presenting or solving):** substitute every decision variable with its objective-preferred bound (typically zero for minimize) and evaluate against the *actual input data*. If every constraint still holds, the solver will return that trivial point as optimal — the formulation is wrong. The non-obvious failure: a forcing constraint that exists but is vacuous against current data (its `where=` matches no rows). Do not present a formulation that fails this gate; if the outcome depends on input data, state that with row-count evidence.
- **Data-driven feasibility precheck:** when bounds derive from data, verify a feasible point exists — at the **constraint's natural disaggregation level** (per-entity for per-entity constraints; a global `Σ supply ≥ Σ demand` can mask per-slice infeasibility). Run as PyRel aggregation queries so the check pushes down to the warehouse. See [examples/presolve_feasibility_gate.py](examples/presolve_feasibility_gate.py).

**Pre-solver audit (a-d):** run before `problem.solve(...)`. In deploy mode these checks are queries, which the model file must not contain, so run them on an interactive copy of the model (no `deployment` section in its config) before deploying.

**(a) Registration.** `solve_for`/`satisfy`/`minimize`/`maximize` register `Variable_<id>`/`Constraint_<id>`/`Objective_<id>` concepts — confirm one per call in `inspect.schema(model).concepts`.

**(b) Binding cardinality.** Registration does NOT mean binding: `solve_for(..., where=[always_false])` registers a variable with zero bindings and the solver runs on an empty decision set. Count each variable's rows.

**(c) Coefficient presence.** Objective/constraint coefficient Properties must be populated by `model.define(...)` — an unbound coefficient has no tuples, the join produces no row, and the term silently vanishes (OPTIMAL with a vacuous objective). Count each coefficient's non-null values, not its rows: a select keeps a row per entity, with a null where the value is missing.

**(d) Constraint binding cardinality.** A per-grouping body that references a bound empty for some entities produces no row for them — those entities are silently unconstrained. Capture the `satisfy()` ref and compare its row count with the entity count.

(a)-(d) are the downstream complement of Step 1: Step 1 verifies formulation *inputs* exist; Step 5 verifies the *outputs* registered, bound, weighted, and grounded. The count code for (b)-(d): [pre-solve-validation.md](references/pre-solve-validation.md) > Cardinality checks; drilling into a short constraint with a `display_string` select: [diagnostic-workflow.md](references/diagnostic-workflow.md). Failures before any solve (`generates` / `compiles`): `rai-prescriptive-results` > Solvability Ladder.

### Step 6: Solve and refine (iterate)

Select the solver (section above), solve, and triage. Solve execution mechanics — parameters, diagnostics requests, run-to-completion discipline, saving results after a sweep or long solve — live in `rai-prescriptive-results`; this step is the *formulation-side* debugging loop, using the refs captured at write time:

- `si = problem.solve_info(); si.display()` first; branch by status: `INFEASIBLE` → localize with `solve(conflict=True)` (as a re-solve on relationalai>=1.26), walking constraints only when `conflict_status` is `NOT_SUPPORTED` / `FAILED`; `OPTIMAL` with suspicious values → unbound coefficients or vacuous forcing constraints; right shape → `problem.verify(*original_fragments)` on integer constraints; on continuous ones it flags points within solver tolerance, and it is silent without `require_mode: report` ([diagnostic-workflow.md](references/diagnostic-workflow.md) > `problem.verify(*fragments)` — post-solve constraint check).
- `model.select(var_ref.name, var_ref.lower, var_ref.upper).to_df()` — bounds and tuples per instance; catches `where=` over-/under-scoping.
- `problem.install_display_strings()` once, then `model.select(constr_ref.name, constr_ref.display_string).to_df()` — grounded sums per row; catches `.per()` mis-scoping (the silent-OPTIMAL trap), contradictions, and bodies that didn't ground (Step 5(d)'s runtime view). Without the install every `display_string` comes back null with no error; so does an expression over a variable declared without `name=`.
- `model.select(obj_ref.name, obj_ref.display_string).to_df()` — expanded objective; catches unbound coefficients. `c = problem.Constraint; model.select(c.name, c.display_string).to_df()` reads all of them at once when one of many is the offender.
- Sampling very large constraints (`aggs.limit(N, ref.name)` in a `where`, or a `where` on `.name`): [formulation-display.md](references/formulation-display.md) > Targeted Inspection with `display_string`.
- Fix priority by status, and join-path fix rules: [fix-generation-guidelines.md](references/fix-generation-guidelines.md).

**Simplify once correct:** static parameters over dynamic calculations; objective terms for goals, constraints for hard requirements; group-level over pairwise.

### Step 7: Present, React, Refine

Steps 1-6 build the best formulation from what the user *told* you; Step 7 discovers what they couldn't articulate until they saw a result. Solve, present (highlighting large shifts from status quo, domain-norm anchors, trade-off costs, boundary solutions — presentation format: `rai-prescriptive-results` > Result Explanation Guide), ask reaction questions, disambiguate rejections into constraint types, add, re-solve — until acceptance or feasibility pressure forces explicit prioritization. Most real formulations need at least one pass. If the result is *technically* wrong (infeasible, all-zero, solver error), route to `rai-prescriptive-results` for diagnosis — it routes back here when the issue is a missing constraint. The full elicitation playbook (diagnostic questions, disambiguation tables, reaction questions, stop conditions, documentation trail): [constraint-elicitation.md](references/constraint-elicitation.md).

---

## Formulation Principles

**Business language framing:** describe variables/constraints/objectives to the user in business terms first ("don't exceed warehouse capacity", "total X quantity per entity"), then the technical form; code stays valid PyRel.

**Constraint vs objective decision rule:** if violating it makes the solution invalid → constraint; if it's a preference → objective term. Ambiguous phrases ("keep costs under X", "try to balance") must be clarified — when unclear, default to soft and ask: "if violating this saved 20% on cost, acceptable?" Full disambiguation tables: [constraint-elicitation.md](references/constraint-elicitation.md).

---

## Multi-Concept Coordination

With MULTIPLE cross-product/junction decision concepts, link them:

1. **Flow networks** (production → transport → fulfillment): conservation constraints — inflow = outflow at transshipment nodes, inventory balance at storage.
2. **Selection + quantity** (binary use/don't-use + continuous quantity): linking constraint `quantity <= capacity * selection`.
3. **Shared base entities** (multiple decision concepts touching the same Site): balance/conservation at that entity.

Without linking constraints, multiple decision concepts produce trivial (independently-optimized zeros), unbounded, or inconsistent solutions. Not always wrong — the user may intend unlinked variables — so flag it to verify, don't auto-correct.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| All-zero solution on minimize | Missing forcing constraints | Add `sum(Decision.x).per(Entity) >= Entity.demand` or equivalent |
| Objective-only variable lands exactly on a bound | Variable appears in the objective but no constraint — solver pushes it to its bound | Connect it to a constraint, or drop it from the formulation |
| Infeasible after adding constraints | Conflicting bounds or over-specified assignments | Localize with `solve(conflict=True)` (Step 6); re-add constraints in tiers only when `conflict_status` is `NOT_SUPPORTED` / `FAILED` |
| Variables created but unused | `solve_for` registered but objective references different properties | Verify the objective includes all decision-variable properties |
| Constraint has no decision variable | `problem.satisfy(model.require(Operation.cost >= 0.01))` is a data assertion | Constraints must reference `solve_for`-registered properties |
| Solution ignores a constraint, no error | Written as `model.require(...)` but never passed to `problem.satisfy()`: it stays an engine-side check the solver never sees | Wrap every decision-variable constraint in `problem.satisfy(...)`; `problem.num_constraints()` counts only those |
| Wrong aggregation scope | `.per(Y)` but Y not joined to the summed concept | Add explicit relationship join in `.where()` |
| Big-M too loose → slow solve | Arbitrary `999999` instead of data-driven bound | `M = capacity` or `M = max_demand` from entity properties |
| Missing forcing requirement | MINIMIZE with no forcing constraint yields zero | Identify what real-world requirement forces positive activity |
| Forcing constraint added when the objective already penalizes inaction | `>= 1` forcing alongside a cost-penalty objective over-constrains — OPTIMAL-with-tradeoff becomes INFEASIBLE | Only add forcing the problem statement requires; check whether the objective already penalizes zero activity |
| Constraint references unwired relationship | Relationship declared but no `define()` binding — joins to zero rows, constraint produces no rows, OPTIMAL with vacuous objective | Verify all relationships in `.where()` joins have `define()` rules. Detail: [constraint-formulation.md](references/constraint-formulation.md) > Unwired Relationships |
| Per-entity constraint applies to fewer entities than `.per(Entity)` suggests | Sparse bound (`Entity.bound` empty for some entities) → no row for them; those entities silently unconstrained | Step 5(d) cardinality check; populate the missing values, coalesce (`Entity.bound \| 0.0`), or join via a fully-populated relationship; localize with `problem.install_display_strings()` then `model.where(aggs.limit(10, constr_ref.name)).select(constr_ref.name, constr_ref.display_string).to_df()` |
| `ValueError: display() requires every decision variable to have a name, but N variables are unnamed` | The check covers **every** variable in the Problem, not just the ones in the expression you wanted to read, and fires once at least one variable has grounded | Pass `name=` on every `solve_for` in the Problem — `name=["x", Entity.id]`; set it at creation, not afterwards. [variable-formulation.md](references/variable-formulation.md) > Naming conventions |
| `TypeError: display() no longer takes part or where` (from `problem.display(ref)` or `display(where=...)`) | `display()` takes no component argument; it prints the whole problem | Install the rendering rules and select the component: `problem.install_display_strings()`, then `model.select(ref.name, ref.display_string).to_df()`. [formulation-display.md](references/formulation-display.md) > Targeted Inspection with `display_string` |
| `display_string` column comes back all null, with no error | First two checks: rendering rules not installed, or a decision variable in the expression has no `name=` | `problem.install_display_strings()` once after the model is declared; re-installing will not fix a missing `name=`. [formulation-display.md](references/formulation-display.md) > Targeted Inspection with `display_string` |
| `solve()` raises `NotImplementedError: solve() performs eager prescriptive execution and cannot be called when model deployments are enabled` | The model's config has a `deployment` section (deploy mode) | `problem.configure(...)` with the same arguments, then `rai models deploy`; or drop the `deployment` section to solve interactively |
| `ValueError: When multiple Problems are configured on one Model, each Problem must have an explicit name` | A second Problem was configured and at least one of them was built without `name=` | Name every Problem: `Problem(model, Float, name="first")` |
| Inline cast, subtype filter, or multi-hop join inside `satisfy(...)`/`minimize(...)` crashes | Constraint scope is less expressive than query `.where()` — `floats.float(...)`, subtype applications, multi-hop joins fail with `AttributeError: ... '_short_name'` | Pre-derive casts as Float properties via `model.define()`; resolve subtype/join membership to id sets and scope with `Entity.id.in_([...])` |
| `problem.satisfy()` / `model.define()` in a Python loop, or hardcoded per-period constraints | Iterating a modeled dimension in Python or hand-writing N near-identical `satisfy()` calls — both bypass declarative quantification | One constraint quantifying over the dimension: Concept + `ref()` adjacency, `Integer` ref via `range()`, or `.per(Entity)`. See [examples/multi_period_flow_conservation.py](examples/multi_period_flow_conservation.py), [scenario-analysis.md](references/scenario-analysis.md) |
| `Duplicate relationship` / `FDError` on re-solve | Multi-scenario solving with `populate=True` writes conflicting results | `populate=False` + `Variable.values()`; fresh `Problem` per iteration. Runnable loop: `rai-prescriptive-results/examples/partitioned_iteration_scenarios.py` |
| Infeasible but not caught before solve | Feasibility arithmetic unvalidated (50 entities, 4 periods × 5/period = 20 slots) | Verify `entity_count / periods / capacity` fits before formulating |
| Linear objective over continuous variables collapses to one entity | LP pushes to the boundary — max-coefficient entity absorbs all budget | Per-entity upper cap, concave objective (`sqrt`, `log`), or piecewise-linear saturation |
| `solve_for(where=expr)` errors on `__bool__` guard | `where` is iterated as a tuple; a bare expression triggers Python truthiness | Wrap in a list: `where=[Concept.prop >= threshold]` |
| `problem.satisfy(<expr>)` raises `TypeError` expecting a `Fragment` | Bare comparison passed instead of `model.require(...)` | Wrap with `model.require(<expr>)` / `model.where(...).require(...)` |
| `solve_for(concept_ref.property)` raises `TypeError` about Chain start | First arg requires bare `Concept.property`; refs are valid only inside `where=[...]` | Pass bare `Concept.property`; reserve refs for `where=` joins |
| `minimize()`/`maximize()` raises `ValueError: no decision variables` | Objective references a detached `model.Property(...)` handle instead of a Concept attribute | Attach first (`Opt.x = model.Property(...)`), then `solve_for(Opt.x, ...)` and reference `Opt.x` in the objective |
| Decision-variable **equality** in outer `where(...)` prunes the search | `model.where(x == k).require(...)` filters states the solver never sees (multi-arity-property invocation in `where` is a *binder* and is correct) | Put decision-var comparisons inside `count(X, x == k)` or inside `require(x == k)`; keep binders in `where`. See [csp-formulation.md](references/csp-formulation.md) § 3a, `rai-pyrel/references/expression-rules.md` |
| Integer-ID decision + `implies` cascade over a sparse Ref table | Solver picks an ID absent from the table; the cascade doesn't fire; aux variable silently free (and `verify()` won't catch it) | Membership IC (`count(Ref, Ref.id == Decision.id).per(Decision) == 1`) + pre-solve lookup-totality check. [csp-formulation.md](references/csp-formulation.md) §§ 2c, 3d |
| `Problem(model, Float)` + `solver="minizinc"` raises `JobInvalidRequestError: ... minizinc only supports (int)` | MiniZinc requires `Problem(model, Integer)`; Float problems can't lower to it | `Problem(model, Integer)` for MiniZinc; continuous data/decisions → MIP-style + HiGHS/Gurobi/Ipopt. Pairing rules: [pre-solve-validation.md](references/pre-solve-validation.md) > CSP-style cross-check |
| `Problem(model, Integer)` + `solver="highs"` / `"gurobi"` / `"ipopt"` raises `JobInvalidRequestError: ... only supports (float)` | Only MiniZinc takes Integer problems | `Problem(model, Float)` + `type="int"` / `"bin"` for a MIP on HiGHS or Gurobi |
| Cannot remove a constraint | Every `satisfy()` accumulates | New `Problem` for a different constraint set (see Known Limitations) |
| Binary variable has no effect | Defined but not linked to quantities | Add `flow <= capacity * x_open` linking constraints |
| Numerical issues | Coefficients differing by >1e6 | Rescale data to similar magnitudes; Big-M sizing: [numerical-and-mip.md](references/numerical-and-mip.md) > Logical implication in MIP |

Silent `verify()` limitations on solver-only-IC bodies and post-solve misreads are `rai-prescriptive-results` Common Pitfalls.

---

## Known Limitations

**Problem is additive** — `solve_for`/`satisfy`/`minimize` accumulate (PyRel append-only; see `rai-pyrel` > Definitions). No remove/replace: to weaken or drop an element, build a **new Problem**. Re-calling `problem.solve()` on the same Problem is safe for *adding* constraints and re-solving. Only one `minimize()`/`maximize()` per Problem (HiGHS rejects multiples); for competing objectives, scalarize and sweep — with `sensitivity=True` on LP/QP the epsilon-bound's `shadow_price` is the exact frontier slope, enabling adaptive sampling: [multi-objective-formulation.md](references/multi-objective-formulation.md).

**Multi-component objectives** add separately aggregated totals, not `sum(model.union(...))`: a union counts equal decision values once in PyRel while the solver counts every term. Default each potentially empty total with `| 0.0` (`| 0` in an `Integer` problem); otherwise one missing term drops the whole objective:

```python
inv = sum(t, x_inv).per(ResourceGroup).where(ResourceGroup.x_inv(t, x_inv))
problem.minimize(
    (sum(ResourceGroup, ResourceGroup.holding_cost * inv) | 0.0)
    + (sum(Arc.transport_cost * Arc.x_flow) | 0.0)
    + (sum(Factory.unit_cost * Factory.x_production) | 0.0))
```

Parametric-variable pitfalls (`name=[]` scalar resolution, cross-concept join attribute collisions), constraint naming, aggregate keys/defaults, numpy casting: [known-limitations.md](references/known-limitations.md). CSP-style gotchas (MiniZinc pairing, empty-aggregate silent-drop, unexposed globals): [known-limitations.md](references/known-limitations.md) § CSP-style and [csp-formulation.md](references/csp-formulation.md).

---

## Examples

For all example problems and the patterns they demonstrate, see [examples-index.md](references/examples-index.md). When reviewing an existing formulation, see [formulation-analysis-context.md](references/formulation-analysis-context.md).

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Variable formulation | Types, bounds, scope, entity creation, slack, parametric/time-indexed | [variable-formulation.md](references/variable-formulation.md) |
| Constraint formulation | Forcing, capacity, balance, linking, `keyed_by`, temporal recurrence, unwired relationships | [constraint-formulation.md](references/constraint-formulation.md) |
| Objective formulation | Direction, multi-component, penalty terms | [objective-formulation.md](references/objective-formulation.md) |
| Constraint elicitation | Pre-solve diagnostic questions, business-phrase disambiguation, post-solve refinement loop, reaction questions, stop conditions | [constraint-elicitation.md](references/constraint-elicitation.md) |
| Problem patterns & validation | Skeletons per problem family (assignment, flow, diet, facility, routing, multi-period, PWL); temporal filters | [problem-patterns-and-validation.md](references/problem-patterns-and-validation.md) |
| Global constraints | `all_different`, `implies`, SOS1/SOS2, per-solver coverage | [global-constraints.md](references/global-constraints.md) |
| CSP-style formulation | When it fits, decision shapes, constraint idioms, multi-solution, audit/witness | [csp-formulation.md](references/csp-formulation.md) |
| Scenario analysis | Scenario Concept vs Loop + `where=`, decision matrix | [scenario-analysis.md](references/scenario-analysis.md) |
| Multi-objective formulation | Dual-guided scalarization, shadow-price = frontier slope, sampling policies | [multi-objective-formulation.md](references/multi-objective-formulation.md) |
| Diagnostic workflow | Capture-ref pattern, targeted `display_string` reads, `solve_info` triage, INFEASIBLE walk | [diagnostic-workflow.md](references/diagnostic-workflow.md) |
| Pre-solve validation | Entity/constraint population, cardinality checks, data integrity queries, solver-pairing check | [pre-solve-validation.md](references/pre-solve-validation.md) |
| Formulation display | `problem.display()` output structure, targeted inspection | [formulation-display.md](references/formulation-display.md) |
| Numerical stability & MIP | Operator compatibility by solver, reformulation, Big-M sizing | [numerical-and-mip.md](references/numerical-and-mip.md) |
| Fix generation guidelines | Join-path fix rules; fix priority for trivial-OPTIMAL and INFEASIBLE | [fix-generation-guidelines.md](references/fix-generation-guidelines.md) |
| Examples index | All example problems with patterns demonstrated | [examples-index.md](references/examples-index.md) |
| Formulation analysis context | Naming conventions, expression parsing for review | [formulation-analysis-context.md](references/formulation-analysis-context.md) |
| Known limitations | Constraint naming, re-solve behavior, decision-variable aggregate keys/defaults, numpy casting, CSP-style gotchas | [known-limitations.md](references/known-limitations.md) |
