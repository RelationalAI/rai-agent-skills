---
name: rai-prescriptive-results
description: Runs optimization solves and interprets the output — solve execution and parameters, diagnostics requests (sensitivity, conflict / IIS), status codes, solution extraction, quality assessment, sensitivity analysis, infeasibility diagnosis, and stakeholder explanation. Use when executing a formulated problem or analyzing anything a solve produced — status, duals, marginals, conflicts, trivial solutions, what-if scenarios. Formulation changes and solver selection go back to rai-prescriptive-problem.
---

# Prescriptive Results
<!-- v1-SENSITIVE -->

> **Requires `relationalai>=1.11.0`.** Sensitivity (shadow prices, reduced costs, basis status) and conflict / IIS diagnosis depend on the dual-bearing solver; earlier versions reject `solve("highs", sensitivity=True)` and omit the dual fields on `solve_info()`. See `rai-setup`.

## Summary

**What:** The solve and everything it produces — execution and parameters, status interpretation, solution extraction, quality assessment, sensitivity analysis, infeasibility diagnosis, and result explanation.

**When to use:**
- Executing a formulated problem: `solve()` parameters, time limits, gap tolerances, diagnostics requests, parametric sweeps
- Extracting solution values; communicating any status (OPTIMAL, INFEASIBLE, DUAL_INFEASIBLE, TIME_LIMIT) to stakeholders
- Diagnosing why a solved-OPTIMAL result is trivial or wrong (all zeros, all at bounds, concentrated on one entity), or why a model is infeasible (conflict / IIS)
- Reading duals and marginals; running sensitivity / what-if analysis; explaining results in business language

**When NOT to use:**
- Designing or fixing the formulation (adding constraints, changing variables), classifying the problem type, or selecting a solver — see `rai-prescriptive-problem`. In particular, an OPTIMAL result the user rejects on preference grounds ("too much X") signals latent constraints, not a bug — route to `rai-prescriptive-problem` > Step 7 / constraint elicitation.
- PyRel and query syntax — see `rai-pyrel`

**Overview:**
1. Execute the solve to completion — parameters set, diagnostics requested up front
2. Check termination status; recall the optimization goal the formulation encodes
3. Extract solution values (model queries or `Variable.values()`)
4. Assess quality against the goal (trivial-solution detection, reasonableness)
5. Explain to stakeholders (decisions, drivers, business impact)
6. Explore what-if (marginals to rank, scenarios to quantify)

---

## Solve Execution

```python
problem.solve(solver_name, time_limit_sec=60)      # returns None — never assign it
model.require(problem.termination_status() == "OPTIMAL")   # engine-side check
si = problem.solve_info()                           # Python-side summary
si.display()
if si.termination_status != "OPTIMAL":
    print(si.error)                                 # solver-level error details
```

`problem.solve()` **returns `None`** — `result = problem.solve(...); result.status` raises `AttributeError`. Status lives in `problem.solve_info()` (Python-side) or `problem.termination_status()` — with parens — inside `model.require()` (engine-side). Check `si.solver_version` rather than hardcoding solver versions.

**Run to completion before reporting.** `solve()` blocks until the solver returns. Read terminal status + objective + variable values **in the same run** before composing any answer. A formulation summary, a "solver is still running" status, or a backgrounded solve whose output was never collected is **not a result**. If a solve is slow, raise `time_limit_sec` deliberately and wait.

**Parametric sweeps and what-if re-solves.** Each `problem.satisfy(...)` accumulates, so build a **fresh Problem per scenario / sweep point**; extract each point's results before moving on (a later failure can't erase earlier rows). Before re-solving a point, check whether the active constraint set actually changed — identical registrations mean a reusable result. Derive per-point inputs once, up front, not inside the loop.

### First-class solve parameters

Solver-independent — every solver accepts them (solver-specific kwargs, warm starting via `start=`, and re-solve rules: [solver-parameters.md](references/solver-parameters.md)). The two diagnostic flags are the caveat: any solver accepts the *request*, but output depends on model class and capability (unsupported cases degrade to empty results, a warning, or `NOT_SUPPORTED` — not a call-time error):

| Parameter | Type | Description |
|-----------|------|-------------|
| `time_limit_sec` | float | Max solve seconds (unset → solver-service default, currently 300s) |
| `silent` / `log_to_console` | bool | Suppress / stream solver output |
| `solution_limit` | int | Max solutions to find (MiniZinc multi-solution) |
| `relative_gap_tolerance` / `absolute_gap_tolerance` | float | Optimality gap (e.g. 0.01 = 1%) |
| `print_only` / `print_format` | bool / str | Print the solver model without solving; formats `"moi"`, `"latex"`, `"mof"`, `"lp"`, `"mps"`, `"nl"` → `si.printed_model` |
| `sensitivity` | bool | Populate post-solve duals (`reduced_cost`, `shadow_price`, `basis_status`). LP/QP only; **requires an objective**; not with `solution_limit`/`print_only` |
| `conflict` | bool | Populate conflict / IIS on an infeasible model (`con.in_conflict`, `var.*_in_conflict`, `si.conflict_status`). **No objective required**; works on MIP; not with `print_only` |

**Diagnostics are solve options, not post-processing.** Request the flag on the solve whose results you'll read. An objectiveless `solve(sensitivity=True)` raises `ValueError` (duals are marginals *of the objective* — use `conflict=True` for pure-feasibility models: the asymmetry that's easy to miss). A MIP under `sensitivity=True` returns empty duals with a warning; interior-point solvers (Ipopt) populate marginals but no `basis_status`. The flags also pin the Problem to the diagnostic result schema: plain and diagnostic solves can't mix on one Problem, and a re-solve may add a diagnostic family but never drop one — rebuild a fresh Problem to change regime.

**Unsupported operators** (not lowered to any solver inside `solve_for`/`satisfy`/`minimize`/`maximize`): `%`, `//` (between two decision variables), `math.floor/ceil/round/sign/clip/factorial/erf`, trig. No `if_then_else` — use `implies()` (Gurobi/MiniZinc) or Big-M (HiGHS). Full compatibility table and reformulation techniques: `rai-prescriptive-problem/references/numerical-and-mip.md`.

---

## Interpretation Workflow

**Precondition — a finished solve** (see Solve Execution above). Then, in order:

1. **Recall the goal** — what decisions, what objective, what constraints. OPTIMAL means nothing if the solution doesn't address the intent.
2. **Check status** (Status Interpretation) — INFEASIBLE / DUAL_INFEASIBLE / error: stop, diagnose, do not present results. TIME_LIMIT with gap > 10%: flag uncertainty.
3. **Assess quality** (Quality Assessment) — trivial (all zeros, all at bounds)? Diagnose before presenting.
4. **Extract and filter** — drop near-zero noise (< 0.5 binary, < 1e-6 continuous), group by decision concept, map to business entities.
5. **Explain** (Result Explanation) — context → decisions → drivers → quality → impact → next steps.
6. **Explore what-if** (Sensitivity Analysis) — marginals rank what to perturb; scenarios quantify.

---

## Solution Extraction

**Engine-side (Relationships):** `problem.termination_status()`, `problem.objective_value()`, `problem.num_points()`, `problem.error()`, plus model-shape accessors — usable in `model.require()`/`model.select()`. Full accessor table: [solution-extraction-details.md](references/solution-extraction-details.md).

**Python-side (`solve_info()`):**

| Attribute | Type | Description |
|-----------|------|-------------|
| `si.termination_status` | `str` | `"OPTIMAL"`, `"INFEASIBLE"`, `"DUAL_INFEASIBLE"`, `"TIME_LIMIT"`, `"LOCALLY_SOLVED"`, `"SOLUTION_LIMIT"` |
| `si.objective_value` | float/int | Objective value — `None` on infeasible/unbounded solves; **check status first** |
| `si.solve_time_sec` / `si.num_points` / `si.solver_version` | | Wall-clock, solution count, solver version |
| `si.printed_model` | str | Solver-model text (when `print_format=` was set) |
| `si.sensitivity` / `si.conflict` | bool | Which diagnostics this solve requested |
| `si.conflict_status` | str/None | `"CONFLICT_FOUND"` / `"NO_CONFLICT_EXISTS"` / `"NOT_SUPPORTED"` / `"FAILED"`; `None` unless `conflict=True` |
| `si.error` | tuple | Solver's reason(s) on error — a `FAILED` conflict's reason rides this channel too |
| `si.ancillary` | Mapping | Solution-quality metrics (gap, bounds, node counts); schema-less — discover keys via `si.display()`, read with `.get(key)` |

**Where solution values live** depends on `solve_for(populate=)`:

| Setting | Results live | Access |
|---|---|---|
| `populate=True` (default) | Written back into model properties | `model.select()` with entity context — standard single-solve |
| `populate=False` | Solver-level only | `Variable.values(sol_index, ref)` on the `ProblemVariable` — scenario loops, multi-solve |

```python
# populate=True — canonical extraction: filter active binaries, alias, inspect/to_df
model.select(
    MachinePeriod.machine.machine_id.alias("machine_id"),
    MachinePeriod.period.pid.alias("period"),
    MachinePeriod.x_maintain.alias("maintained"),
).where(MachinePeriod.x_maintain > 0.5).inspect()

# populate=False — back-pointer attributes + values(sol_index, ref)
assign_var = problem.solve_for(Assignment.x, type="bin", populate=False)
problem.solve("highs")
if problem.solve_info().termination_status in ("OPTIMAL", "LOCALLY_SOLVED"):
    v = Float.ref()
    df = model.select(assign_var.assignment.worker.name.alias("worker"), v.alias("value")
        ).where(assign_var.values(0, v), v > 0.5).to_df()
```

**Extraction principles:** binaries filter `> 0.5` (MIP tolerance), continuous `> 1e-6`; scalar objective via `si.objective_value`; alias every column; integer columns come back as `Int128Array` — cast at extraction (`df["n"] = df["n"].astype("int64")`) before any pandas reduction. Per-pattern variations (multiple solutions, iterative, scenario extraction, back-pointer naming rules, Snowflake export): [solution-extraction-details.md](references/solution-extraction-details.md).

### Sensitivity & conflict attributes

Together the two flags make a solve *interrogable*: `sensitivity=True` tells you, at the optimum, what each constraint is worth and how close each unused option is to entering; `conflict=True` tells you why an infeasible model has no plan. Read the populated attributes **straight off the objects `solve_for()` and `satisfy()` returned** — like `.name`, not through a separate API. Each is **single-valued** (no `sol_index`, unlike `Variable.values()`) and joins to its entity through the **back-pointer key**, never by parsing a name string.

| Accessor | Shape | Read like |
|---|---|---|
| `var.reduced_cost` / `con.shadow_price` | single-valued | `model.select(var.reduced_cost)` |
| `var.values(k, ref)` | indexed (needs `sol_index` + ref) | `where(var.values(k, ref))` |

**Variable attributes:** `reduced_cost` (Float; sign = objective sense × active bound; empty for MIP), `basis_status` (MOI status; absent for interior-point), `lower_in_conflict` / `upper_in_conflict` / `integrality_in_conflict` (predicates — *leads*, not proof; collapse `IN_CONFLICT` + `MAYBE_IN_CONFLICT`). **Constraint attributes:** `shadow_price` (∂obj/∂RHS; empty for MIP), `basis_status`, `in_conflict` (predicate, same lead semantics).

```python
food_vars = problem.solve_for(Food.amount, name=Food.name, lower=0)
floor = problem.satisfy(model.require(intake >= Nutrient.min), keyed_by={"nutrient": Nutrient})
problem.minimize(sum(Food.cost * Food.amount))       # sensitivity needs an objective
problem.solve("highs", sensitivity=True)
model.select(food_vars.food.name, food_vars.reduced_cost, food_vars.basis_status).inspect()
model.select(floor.nutrient.name, floor.shadow_price).inspect()
```

Reading a marginal or conflict flag **by entity** requires the constraint's grounding key to be **declared** at formulation time — `satisfy(..., keyed_by={"nutrient": Nutrient})`; a variable's back-pointer is automatic, a constraint's is not. Full `keyed_by` idiom: `rai-prescriptive-problem/references/constraint-formulation.md`. Dual economics and IIS reading in depth: [sensitivity-analysis.md](references/sensitivity-analysis.md), [conflict-analysis.md](references/conflict-analysis.md).

### Post-solve constraint verification

`problem.verify(*fragments)` temporarily installs the original `model.require(...)` fragments as ICs at IC strictness (tighter than solver tolerance) — useful for exact solvers (HiGHS MIP, MiniZinc). It checks `termination_status` first and cleans up in a `finally`. Known silent limitation on solver-only-IC bodies: see Common Pitfalls.

---

## Status Interpretation

| Status | Meaning | Action |
|---|---|---|
| `OPTIMAL` | Best solution within tolerance (~1e-6 LP, 0.01% MIP gap) | Quality assessment, then explain |
| `INFEASIBLE` | No solution satisfies all constraints | Diagnose before presenting — see Infeasible diagnosis |
| `DUAL_INFEASIBLE` | Unbounded (the status string is not `"UNBOUNDED"`) | See Unbounded diagnosis |
| `"Feasible"` (MIP) | HiGHS found a solution, optimality unproven | Treat as TIME_LIMIT for gap purposes |
| `TIME_LIMIT` | Feasible found, optimality unproven | Read the realized gap from `si.ancillary` (schema-less: discover the key via `si.display()`, read with `.get()` — a hardcoded key risks `KeyError` across solvers). Gap < 1%: near-optimal; 1-5%: good; > 10%: uncertain — more time, tighter Big-M, symmetry breaking, or simplify |
| Error / Unknown | Compilation or solver error | Check `si.error`; expression/property fixes → `rai-prescriptive-problem` |

A non-optimal status is information, not necessarily failure: INFEASIBLE on a probe constraint set is a valid feasibility-boundary test, and TIME_LIMIT with gap < 5% and sensible values is presentable as near-optimal ("is a 2% improvement worth 10 more minutes?"). **Iterate** on INFEASIBLE-without-clear-conflict, DUAL_INFEASIBLE, gap > 10%, or trivial solutions; **accept** OPTIMAL, gap < 5%, or intentional probes. Per-status stakeholder phrasing: [status-interpretation.md](references/status-interpretation.md).

### Infeasible diagnosis

**Localize with `solve(conflict=True)` first** — one solve returns the IIS, a *minimal* set of constraints and bounds that cannot all hold, read as bare predicates joined by key:

```python
problem.solve("highs", conflict=True)   # request upfront — a plain-solved Problem can't add it on re-solve
si = problem.solve_info()
if si.conflict_status == "CONFLICT_FOUND":
    model.select(coverage.shift.name, coverage.shift.min_coverage).where(coverage.in_conflict).inspect()
```

Each flagged member is a *candidate* (leads, not proof): relax one and re-solve to confirm — other independent conflicts may remain. `NO_CONFLICT_EXISTS` means the conflict solve found the model *feasible* — the earlier INFEASIBLE came from a different formulation or data state; re-check what changed. `NOT_SUPPORTED` / `FAILED` (read `si.error`) → manual checks: (1) total demand vs capacity; (2) contradictory constraints (`x >= 10`, `x <= 5`); (3) bound consistency (lower > upper); (4) bisect by rebuilding the Problem with one `satisfy()` or bound removed at a time (no in-place removal API). After localizing: present trade-off options; moving the conflicting hard constraint to the objective with a penalty (softening) is often more useful than pure diagnosis. See [conflict-analysis.md](references/conflict-analysis.md); for the full failure-mode catalog (symptom → root cause → fix), load [diagnostic-taxonomy.md](references/diagnostic-taxonomy.md).

### Unbounded (DUAL_INFEASIBLE) diagnosis

(1) All variables bounded (upper bounds for maximize, lower for minimize)? (2) Budget/capacity constraints present? (3) Objective direction right? (4) Coefficient signs right?

### Audit / witness mode — status-aware verdict (CSP-style)

When the question is "does the property hold?", the answer is the termination status — **inverting** MIP intuition:

| Termination status | Audit verdict |
|--------------------|---------------|
| `INFEASIBLE` | **PASS** — no configuration violates the property |
| `OPTIMAL` / `SOLUTION_LIMIT` | **FAIL** — a violating configuration exists; extract witnesses |
| `TIME_LIMIT`, error, `LOCALLY_SOLVED` on a CSP | **INCONCLUSIVE** — search not exhausted; never report as PASS |

**`num_points() == 0` does not prove the property holds** — the solver may have crashed or timed out. Status first, always. Full pattern: `rai-prescriptive-problem/references/csp-formulation.md` § 5 and its `audit_witness.py` example.

---

## Solvability Ladder

Progressive quality gates — each level subsumes the previous. Use it to classify where a formulation stands and what to fix next; report against it ("reaches optimal but fails non-trivial — all-zero, missing forcing constraints").

| Level | Gate | Check |
|-------|------|-------|
| **generates** | Syntactically valid PyRel | Parses |
| **compiles** | `display()` succeeds | Variables, constraints, objective registered |
| **solves** | Solver returns any status without crash | `solve()` completes; `solve_info()` has a status |
| **optimal** | Proven optimum (or acceptable gap) | `OPTIMAL`, or `TIME_LIMIT` with gap < 5% |
| **non-trivial** | Meaningful activity | Objective ≠ 0, non-zero ratio > 1%, not all at bounds |
| **meaningful** | Actionable decisions | Domain-specific: scale matches demand, coverage complete, flows balance |

Root causes by level and the 5-step diagnosis protocol: [failure-taxonomy.md](references/failure-taxonomy.md).

---

## Quality Assessment

An "optimal" status can decorate a trivially empty problem. Type-specific expectations: resource allocation → non-zero allocations near budget; network flow → balanced non-zero arcs; scheduling → every task covered; pricing → differentiated prices; multi-period → non-trivial quantities across periods.

**Trivial-solution signatures:**
1. **All-zero** (non-zero ratio < 1%): "do nothing" is cheapest — missing forcing constraints.
2. **Objective = 0 on minimize**: forcing constraints missing or their joins matched zero rows.
3. **All binaries same value**: no meaningful differentiation — check costs differ and cardinality constraints exist.
4. **One entity absorbs everything**: missing balance/fairness constraints or extreme cost differentials.
5. **All variables at bounds** (≥ 90%): at lower → constraint joins matched zero rows; at upper → capacity too tight or maximize without caps.

**Diagnosis sequence:** understand the domain → for minimize-with-zero find what should force activity → locate the requirement data in the model → link variable sums to requirements via correct relationship paths. Fix *constraints* over variables, ground every fix in actual model surface, and fix broken join paths rather than aggregate workarounds — navigate FROM the `.per()` entity (`Demand.customer.site`, not `Customer.site`). Forcing-constraint patterns: `rai-prescriptive-problem/references/constraint-formulation.md` > Forcing constraints; fix taxonomy: `rai-prescriptive-problem/references/fix-generation-guidelines.md`.

**Reasonableness (domain judgment):** quantities match demand scale? flows within known capacity? assignments geographically sensible? objective in a plausible range? **Interpretability:** decision-variable attributes carry an `x_` prefix — translate to business language in all user-facing prose (`x_flow` → "units shipped"); code samples stay technical.

**Post-solve diagnosis checklist:** status OPTIMAL (or acceptable gap)? objective non-zero and plausible? non-zero ratio reasonable? no values > 1e10? not clustered at bounds? business sense? binding constraints match known bottlenecks? stable to small perturbations? Failing checks: all-zero → forcing constraints; infeasible → `solve(conflict=True)`.

---

## Result Explanation Guide

Explanation is the return leg of bidirectional translation: the solver produced math; translate it back to business language. Present in order: **(1) problem context** (2-3 sentences), **(2) what was decided** (lead with the actionable output; objective in business terms), **(3) why these decisions** (which constraints and costs drove each selection/exclusion — answer "why was X selected?", "what's preventing Z?" with actual entity names), **(4) solution quality** (non-triviality, red flags), **(5) business impact**, **(6) next steps**. Map extended (cross-product) decision concepts back to their base entities. Full 6-part template with worked phrasing and explainability question patterns: [result-explanation.md](references/result-explanation.md).

For *why* a constraint binds or an option was excluded: `sensitivity=True` gives exact marginals on LP/QP (a constraint's `shadow_price` = one more unit of RHS; a variable's `reduced_cost` = objective marginal at its bound). For MIP (no duals) or structural changes, reason from binding-constraint identification and scenario deltas. Frame in the decision maker's entities, never variable indices.

---

## Sensitivity Analysis

Two tools answer "what if an assumption changes," and they don't substitute:

- **Exact marginals at the optimum** — `solve(sensitivity=True)`: LP/QP duals, *local first-order* rates at the current optimum. No coefficient/RHS *ranging* — a marginal gives the rate, not the range it holds over. [sensitivity-analysis.md](references/sensitivity-analysis.md).
- **Finite / structural what-if** — scenario sweeps and Pareto frontiers: finite changes, MIP models, structural shifts. Present as scenario comparison tables, not derivatives.

Duals *rank* what to perturb; scenarios *quantify* the result. Treat scenarios as a default post-solve step — after every solve, proactively suggest 1-2 variations based on binding constraints. Prioritize parameters that are uncertain, controllable, or high-impact (a parameter is **critical** if small changes flip selected entities, move the objective > 5% per 10% variation, or flip constraint status).

**Sweep semantics — vary exactly what's named.** A sweep varies the named parameter(s); every other constant, boundary, and anchor stays fixed. When the swept parameter sits inside a larger definition (a tier partition, a derived bound), restate the full definition at each value and confirm only the named parameter moved. Reuse a **derived artifact** (a first-class object an earlier step wrote back — a subtype, a computed property) by referencing it; **re-derive a structural constant** (a number a sibling analysis chose — band width, offset, cap multiplier) from the current task rather than copying it. If wording admits multiple readings, choose the minimal-change reading and state it in one line.

**A discontinuity is a finding about your assumptions until verified.** When one sweep point flips status or steps the objective while neighbors don't, identify which modeling choice creates the break; test whether a plausible alternative reading removes it, and if so report both readings.

**Strategic vs operational:** one-time planning → Pareto frontier (stakeholders pick a point; "the knee is where improving one goal starts costing disproportionately in the other"); recurring operations → weighted objectives with tunable weights. If the sweep was dual-guided (`sensitivity=True` on LP/QP), the ε-bound's `shadow_price` is the *exact* frontier slope at each point, and the frontier validates relationally (non-dominance, monotone-dual convexity): [sensitivity-analysis.md](references/sensitivity-analysis.md) and [examples/frontier_relational_validation.py](examples/frontier_relational_validation.py).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Presented a plan/formulation as the result | Solve still running or backgrounded — no terminal status or values ever read | A finished solve is the precondition: status + objective + values first |
| Zero objective on minimize | Missing forcing constraints | Add `sum(x).per(Entity) >= Entity.demand`; joins matching zero rows are the sibling cause |
| Infeasible: demand > capacity | Total demand exceeds supply | Slack/penalty variables or relax demand |
| Silent: `problem.termination_status == "OPTIMAL"` always False | No parens — bound method compared to a string | Engine-side: `problem.termination_status()` (parens) in `require()`; Python-side: `si.termination_status` (no parens) |
| `AttributeError` on `solve()` return value | `solve()` returns `None` | `solve_info()` for status; `model.select()` / `Variable.values()` for values |
| Silent: non-OPTIMAL extraction returns empty df / `None` objective | Loop extracts without checking status | Guard: `if si.termination_status not in ("OPTIMAL", "LOCALLY_SOLVED"): continue` |
| Multi-solution overclaim | `solution_limit=K` returns up to K **distinct feasible** solutions — neither ranked nor diversity-maximized | Document the semantics; for top-K re-solve K times with previous-best as constraint. `rai-prescriptive-problem/references/csp-formulation.md` § 4 |
| Silent: `verify()` OK on solver-only-IC bodies (`implies` / `all_different`) even when violated | Verify engine can't ground wire-format constraint relations; documented limitation | Mixed constraints → `verify()` + post-solve assertions on solver-only ICs; all-solver-only or `populate=False` → skip `verify()`. `rai-prescriptive-problem/references/csp-formulation.md` § 6 |
| Audit misread: `num_points() == 0` as "property holds" | Zero points can mean crash/time-limit | Status first; only `INFEASIBLE` proves PASS (see Audit / witness mode) |
| Marginal reads empty on LP/QP | `sensitivity=True` not requested on that solve | Request on the solve you'll read; re-solving plain to "add" duals raises `ValueError` — rebuild the Problem |
| Marginal still empty with `sensitivity=True` | Non-optimal solve (no duals) or MIP (integer models have none; warning fires) | Check status first; if OPTIMAL and empty, it's a MIP — use scenarios / binding-constraint reasoning |
| Empty `basis_status` | Interior-point (Ipopt) has no simplex basis | Expected; use marginals, or a simplex solver if a basis is needed |
| `conflict=True` confused with `sensitivity=True` | Conflict populates `in_conflict` predicates, not marginals; sensitivity the reverse | Request the one matching the question; confirm which ran from `si.conflict` / `si.sensitivity` / `si.conflict_status` — an always-False `in_conflict` can equally mean `NO_CONFLICT_EXISTS`, `NOT_SUPPORTED`, or "not in this (non-unique) IIS" |
| Dual sign assumed from objective sense alone | `shadow_price` sign = objective sense × constraint direction; `reduced_cost` sign = objective sense × active bound | Read each marginal's sign from both factors: [sensitivity-analysis.md](references/sensitivity-analysis.md) § Sign convention |
| Asserting `reduced_cost > 0` for every unused option | The converse holds only under a unique optimum; degeneracy allows `≈ 0` on unused options | Assert only the always-true directions: in use ⇒ `reduced_cost ≈ 0`; nonzero ⇒ at a bound |
| `solve(sensitivity=True)` on an objectiveless model → `ValueError` | Duals are objective marginals | `conflict=True` for pure feasibility / CSP — it needs no objective |
| `integrality_in_conflict == False` read as "not involved" | The IIS is one minimal subset, not unique; `False` = "not in this subset" (and `True` may be a "maybe") | Treat only `True` as a lead; confirm non-involvement by relaxing and re-solving |
| Constraint family without a declared key | Back-pointers are declared, not inferred (`name=` is display-only) | `satisfy(..., keyed_by={"nutrient": Nutrient})` at formulation time; read via `con.nutrient` |
| `FDError` on a `keyed_by` constraint | Declared keys don't uniquely determine the instance (family wider than key, or two conjuncts sharing keys) | Add missing key(s), or split multi-conjunct `require` into one `satisfy` per conjunct |
| Sweep moves an unnamed boundary with the swept threshold | Structure (band width, offset) inherited from a sibling analysis instead of re-derived | Vary only the named parameter; restate the partition at each value; state the chosen reading (see Sensitivity Analysis) |

Additional interpretation pitfalls (numerical instability, degenerate solutions, aggregation scope, missing/null data): [common-pitfalls.md](references/common-pitfalls.md).

---

## Examples

| Pattern | Description | File |
|---|---|---|
| Scenario Concept results | Results in ontology via `model.select(Scenario.name, ...)`, per-scenario aggregation | [examples/scenario_concept_extraction.py](examples/scenario_concept_extraction.py) |
| Loop-based results | `Variable.values()`, status/objective access, scenario comparison table | [examples/loop_based_extraction.py](examples/loop_based_extraction.py) |
| Scenario Concept (parameter sweep) | Scenario as data concept, single solve, multi-arg variables | [examples/scenario_concept_parameter_sweep.py](examples/scenario_concept_parameter_sweep.py) |
| Scenario Concept (multi-binary MILP) | Binary variables indexed by Scenario, cross-variable budget | [examples/scenario_concept_milp.py](examples/scenario_concept_milp.py) |
| Scenario Concept (CSP) | Scenario indexing integer decisions; one MiniZinc solve over all scenarios | [examples/scenario_concept_csp.py](examples/scenario_concept_csp.py) |
| Entity exclusion (disruption) | Loop + `where=[]` with `!=` filter, `populate=False` | [examples/entity_exclusion_disruption.py](examples/entity_exclusion_disruption.py) |
| Partitioned sub-problems | Loop + `where=[]` per partition, `populate=False` | [examples/partitioned_iteration_scenarios.py](examples/partitioned_iteration_scenarios.py) |
| Pareto frontier analysis | Tradeoff table (secant + exact shadow-price), knee detection, regime shifts | [examples/pareto_frontier_analysis.py](examples/pareto_frontier_analysis.py) |
| Frontier relational validation | Swept points as a `FrontierPoint` concept; non-dominance/convexity/slope ICs | [examples/frontier_relational_validation.py](examples/frontier_relational_validation.py) |
| Marginals by key | `reduced_cost`/`shadow_price`/`basis_status` joined via `keyed_by` back-pointers | [examples/marginals_by_key_extraction.py](examples/marginals_by_key_extraction.py) |
| IIS membership by key | `solve(conflict=True)`; `con.in_conflict` joined by key, gated on `conflict_status` | [examples/iis_membership_extraction.py](examples/iis_membership_extraction.py) |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Solution extraction details | Engine-side accessor table, `populate=` variations, back-pointer naming rules, Snowflake export | [solution-extraction-details.md](references/solution-extraction-details.md) |
| Status communication | Per-status stakeholder phrasing, gap interpretation, iterate-vs-accept | [status-interpretation.md](references/status-interpretation.md) |
| Result explanation templates | Full 6-part structure, decision-variable translation, explainability patterns | [result-explanation.md](references/result-explanation.md) |
| Failure taxonomy | Root causes by solvability level, 5-step diagnosis protocol | [failure-taxonomy.md](references/failure-taxonomy.md) |
| Sensitivity analysis | Dual economics, sign rules, key-join idiom, sweeps, Pareto construction, dual-guided frontiers | [sensitivity-analysis.md](references/sensitivity-analysis.md) |
| Conflict (IIS) analysis | `in_conflict` membership, `conflict_status` vocabulary, joining conflicts to entities | [conflict-analysis.md](references/conflict-analysis.md) |
| Solver parameters | Solver-specific kwargs (HiGHS/Gurobi/Ipopt), tuning, warm starting, which solvers yield duals/basis/IIS | [solver-parameters.md](references/solver-parameters.md) |
| Diagnostic taxonomy | Solver-side root-cause codes mapping status to fix-action types | [diagnostic-taxonomy.md](references/diagnostic-taxonomy.md) |
| Common pitfalls | Additional interpretation pitfalls beyond the silent-bug rows above | [common-pitfalls.md](references/common-pitfalls.md) |
