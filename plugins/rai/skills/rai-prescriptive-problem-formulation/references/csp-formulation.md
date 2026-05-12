# MiniZinc-style formulation in PyRel

This doc covers PyRel's MiniZinc-style prescriptive formulation — often called CSP as community shorthand. It covers both problems with objectives (e.g., `chromatic_number` minimizes max color, `book_slate` maximizes revenue, `planogram` maximizes revenue via an `implies` cascade) and pure-satisfaction modes (audit / witness / property-check, multi-solution enumeration without ranking — see §§ Multi-solution mode, Audit / witness enumeration).

MiniZinc-style is a **style**, not a separate problem class. It is characterized by `Problem(model, Integer)` + `solver="minizinc"`, all-discrete decisions and data, and constraint + objective shapes (globals, `count` / products over decision variables, `min`/`max` in objective) that MiniZinc supports natively where HiGHS/Gurobi require manual reformulation. Any of the five existing prescriptive problem types (Resource Allocation, Network Flow / Design, Routing, Scheduling / Assignment, Pricing) can adopt this style.

<!-- TOC -->
- [0. PyRel-level cross-references](#0-pyrel-level-cross-references)
- [1. When this style fits](#1-when-this-style-fits)
- [2. Decision-variable shapes](#2-decision-variable-shapes)
- [3. Constraint idioms](#3-constraint-idioms)
- [4. Multi-solution mode](#4-multi-solution-mode)
- [5. Audit / witness enumeration](#5-audit--witness-enumeration)
- [6. The verify() caveat for implies-bodied ICs](#6-the-verify-caveat-for-implies-bodied-ics)
- [7. Pitfall: big-M vs half-reified implies for active-iff with aggregate body](#7-pitfall-big-m-vs-half-reified-implies-for-active-iff-with-aggregate-body)
- [8. Globals available today](#8-globals-available-today)
- [9. Cross-reasoner handoff](#9-cross-reasoner-handoff)
- [10. Cross-links to examples](#10-cross-links-to-examples)
<!-- /TOC -->

---

## 0. PyRel-level cross-references

This doc focuses on what is distinctive about MiniZinc-style formulation. General PyRel mechanics live one level up in `rai-pyrel-coding`. Before reading the rest of this doc, know that:

- `count(X, condition)` syntax — second arg is a condition expression on `X` — is documented in `rai-pyrel-coding/references/common-pitfalls.md` (count syntax row). This doc only surfaces the MiniZinc-style-distinctive twist on top of that base syntax (see § Constraint idioms).
- `.ref()` mechanics for pairwise self-joins (`Concept.ref()`) and value-binding (`Float.ref()`, `Integer.ref()`) are documented in `rai-pyrel-coding/SKILL.md` § References and Aliasing.
- Undirected-edge expansion via reverse-define is documented in `rai-pyrel-coding/references/expression-rules.md` (undirected-edge expansion section). MiniZinc-style chromatic_number / pod_placement / book_slate problems hit this mechanic frequently — see the cross-reference in `chromatic_number.py`.
- `model.union()` branch-shape requirement is documented in `rai-pyrel-coding/references/common-pitfalls.md` (inconsistent branches row).

---

## 1. When this style fits

Two headline rules govern the choice between MIP-style and MiniZinc-style:

- **Any continuous decision or data forces MIP — no middle ground.** MiniZinc requires `Problem(model, Integer)`; a single Float decision variable coerces the whole problem to MIP.
- **MIP is the more restrictive standard form.** MiniZinc accepts a richer expression surface in constraints and objectives without manual linearization: `min`/`max` directly in the objective (`minimize(max(...))` — see `chromatic_number.py`; `minimize(min(...))` for worst-case-bound problems), `*` on two decision variables (bilinear), `count` and `all_different` as primitives, `implies` as a direct indicator. MIP requires equivalent reformulation: auxiliary `t` with `t >= each_term` for max-in-objective, McCormick envelopes for bilinear, big-M for indicators, manual binary/disjunctive reformulation for `all_different`. MiniZinc-style often saves real formulation work even when both solver families could in principle handle the problem.

**Decision flow (apply in order; first hard rule that fires decides):**

1. **Continuity filter (hard rule)** — any continuous decision variable or continuous numeric data participating in a constraint → MIP-style.
2. **Expression-surface filter** — `min`/`max` in objective, `*` on two decision variables, `count` / `all_different` as primitives, `implies` cascades → MiniZinc-style fits naturally; MIP requires manual reformulation.
3. **Problem-mode filter** — pure feasibility, find-K-feasible, property-check / counterexample search, audit-witness, multi-solution enumeration → MiniZinc-style. Optimization with provable optimality or gap-reporting on TIME_LIMIT → MIP-style.
4. **Global-constraint filter** — heavy `all_different` or many `implies` cascades → MiniZinc-style exploits these via propagation.
5. **Data-shape filter** — sparse, structural, combinatorial / all-integer IDs → MiniZinc-style. Dense continuous flows, portfolio with continuous weights → MIP-style. Convex QP objective → HiGHS (MiniZinc has no QP).

**Note on operator support.** `//` (floor division) and `%` (modulo) on two decision variables are **not accepted by either solver wire** — both raise compile-time errors. They are not a MiniZinc-vs-MIP differentiator. See `rai-pyrel-coding/references/common-pitfalls.md` (`//` on two decision variables row) and `rai-prescriptive-solver-management/SKILL.md` § Unsupported operators.

For the expanded reference table with per-filter template precedents and the rationale behind each, see `global-constraints.md` § "MIP-style vs MiniZinc-style — when to choose which."

---

## 2. Decision-variable shapes

MiniZinc-style problems share a small set of recurring decision-variable shapes. Pick the one that matches the data, then verify membership.

### 2a. Integer slot in `{1..K+1}` with `K+1` = unpicked sentinel

When a decision is "which of K choices, or nothing," reserve `K+1` as the sentinel for "not picked" and let cardinality fall out of how many slots equal each choice. One variable carries both the cardinality and the position information.

```python
# Slot = position in K+1-long range; K+1 is the sentinel for "not picked"
problem.solve_for(Slot.choice, type="int", lower=1, upper=K + 1, name=["choice", Slot.index])
# A choice c is "selected" iff at least one slot picked it:
chosen = count(Slot.choice, Slot.choice == c).per(c)
```

Demonstrated end-to-end in `integer_slot_with_sentinel.py` (distilled from `book_slate_recommendation`).

### 2b. Sub-concept predicate marker + `solve_for(Sub.prop)`

Declare a sub-concept whose membership is the eligibility predicate, declare the decision Property on the parent concept, and `solve_for` the property keyed by the sub-concept — the solver only creates decision variables for sub-concept rows. The scoping is structural: ineligible parent rows have no variable, so downstream constraints cannot accidentally pick them.

```python
# Sub-concept populated by the Rules layer
EligiblePatient = model.Concept("EligiblePatient", extends=[Patient])
model.define(EligiblePatient(Patient)).where(Patient.score >= threshold)

# Decision Property declared on the parent concept, scoped via solve_for
Patient.is_in_cohort = model.Property(f"{Patient} is in cohort if {Integer:in_cohort}")
problem.solve_for(EligiblePatient.is_in_cohort, type="bin")
problem.satisfy(model.require(sum(EligiblePatient.is_in_cohort) == cohort_size))
```

Demonstrated end-to-end in `subconcept_solve_for.py` (distilled from `patient_cohort_recruitment`).

### 2c. Integer-ID decision with explicit membership IC

This is the shape that admits the most-frequent silent-failure mode in MiniZinc-style formulation. **When an integer decision variable is bounded only by `lower=min(Ref.id), upper=max(Ref.id)`, the solver is free to pick any integer in that range — including IDs not present in the reference data.** If a downstream `implies(decision_id == Ref.id, ...)` cascade looks up properties on the chosen ID and the lookup is non-total, those properties stay silently unconstrained, and `verify()` returns OK because `implies`-bodied ICs are not re-evaluated post-solve (see § 6).

Two safe forms:

```python
# Form A: explicit membership IC
problem.solve_for(Decision.id, type="int", lower=min_id, upper=max_id)
problem.satisfy(model.where(Decision.id == id).require(Reference(id)))

# Form B: dense-contiguous validation upfront (pre-solve)
# Check at problem-build time that {min_id..max_id} == set(Reference.id);
# if not, switch to Form A or filter Reference to a dense range.
```

Demonstrated in `implies_table_lookup.py` (distilled from `planogram_optimization` and cross-referenced with `underwriting_audit`).

### 2d. Binary-availability-scoped decision

Familiar pattern from MIP-style scheduling (e.g., `shift_assignment`). Worth listing here because it remains correct in MiniZinc-style and pairs naturally with `count` over decision-dependent filters (idiom 3a).

```python
Worker.x_assigned = model.Property(f"{Worker} on {Shift} is {Integer:assigned}")
problem.solve_for(
    Worker.x_assigned, type="bin",
    where=[Worker.available_for(Shift)],
    name=["assign", Worker.id, Shift.id],
)
```

---

## 3. Constraint idioms

### 3a. Cardinality via `count(X, cond).per(group)` — decision-dependent filter

The MiniZinc-style-distinctive point on top of the base `count(X, cond)` syntax (documented in `rai-pyrel-coding/references/common-pitfalls.md`): when `cond` depends on a decision variable, the filter **must live inside** `count`'s second argument, not in an outer `where`. An outer `where` would prune the search space at pre-solve, eliminating feasible search states; the inner form lets `count` count states per branch during solving.

```python
# CORRECT — decision-dependent filter inside count
problem.satisfy(model.require(
    count(Slot, Slot.choice == c).per(c) <= max_per_choice
))

# WRONG — outer where prunes the search instead of counting
problem.satisfy(model.where(Slot.choice == c).require(
    count(Slot).per(c) <= max_per_choice
))
```

### 3b. Undirected-edge expansion via reverse-define

PyRel relationships are directed. MiniZinc-style graph problems (coloring, pod placement on an anti-affinity graph, book-slate authorship pairs) need both orientations. Use reverse-define at the Rules level for persistent symmetric relations, or `.ref()`-pair inline for single-IC undirected matching.

For the mechanic, see `rai-pyrel-coding/references/expression-rules.md` (undirected-edge expansion section). `chromatic_number.py` carries the concrete worked example.

### 3c. Pairwise via dual `.ref()` + `id_a < id_b` — MiniZinc-style symmetry-break

`.ref()` mechanics (pairwise `Concept.ref()` + `Float.ref()` value-binding) are documented in `rai-pyrel-coding/SKILL.md` § References and Aliasing. The MiniZinc-style point is the `id_a < id_b` half-pair filter: it prevents the solver from re-encoding `(a, b)` and `(b, a)` as two separate constraint instances, halving the constraint count without changing the feasible set.

```python
Qi = Queen
Qj = Queen.ref()
problem.satisfy(model.where(Qi.row < Qj.row).require(
    Qi.column != Qj.column,
    std.math.abs(Qi.column - Qj.column) != Qj.row - Qi.row,
))
```

`n_queens.py` demonstrates this end-to-end.

### 3d. `implies` cascade as decision-indexed table lookup + lookup-totality pre-solve check

The dominant pattern for "predict-then-optimize" in MiniZinc-style: a decision integer selects an entry from a reference table; an `implies` cascade binds an auxiliary variable to the chosen row's value; downstream constraints / objective use the auxiliary.

```python
# Decision: which assortment is placed at this position
problem.solve_for(Position.x_assort, type="int", lower=min_id, upper=max_id)
# Auxiliary: revenue at this position
problem.solve_for(Position.x_revenue, type="cont")
# Cascade: revenue is the looked-up value for the chosen assortment
problem.satisfy(model.require(
    implies(Position.x_assort == Assortment.id, Position.x_revenue == Assortment.revenue)
))
problem.maximize(sum(Position.x_revenue))
```

This idiom is sound **only if every value in the decision's domain has a covering Ref row**. Otherwise the chosen-but-uncovered case leaves `x_revenue` unconstrained and `verify()` silently returns OK (see § 6). Use the integer-ID membership IC from § 2c, plus a pre-solve check that the reference table is total over the decision's range:

```python
# Pre-solve lookup-totality assertion (runs in-engine before solve)
n_decision_domain = (max_id - min_id + 1)  # or len of explicit domain
n_ref_rows = len(model.select(Assortment.id).to_df())
assert n_decision_domain == n_ref_rows, "implies-cascade lookup is non-total"
```

`implies_table_lookup.py` carries the canonical worked form including the totality check.

---

## 4. Multi-solution mode

MiniZinc-style problems frequently want K different feasible solutions rather than one optimum. `solution_limit` enables this; the semantics need care.

- **`solution_limit=K` is a `solve(...)` kwarg, not `solve_for(...)`.**
- **Termination status interpretation:**
  - `OPTIMAL` means the search exhausted the feasible space with ≤ K solutions found.
  - `SOLUTION_LIMIT` means the search stopped at K with more feasible solutions remaining.
- **K must exceed the feasible-set size for `OPTIMAL` + stable extraction order.** If K < feasible-set size, you get a `SOLUTION_LIMIT` cut-off whose order is solver-dependent — fine for K-of-many enumeration, problematic when the test expects a deterministic full set.
- **Extract via `Variable.values(sol_index, value_ref)`** — solution `0` to `num_points - 1`. With `populate=True` the first solution is also written back to model properties; with `populate=False` only `Variable.values` is populated, and the model is unchanged.
- **The returned set is up to K distinct feasible solutions — NOT top-K-optimal, NOT ranked, NOT diversity-maximized.** Don't promise any of these properties to users.

```python
problem.solve("minizinc", solution_limit=K, time_limit_sec=60)
si = problem.solve_info()
if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):
    val = Integer.ref()
    for idx in range(si.num_points):
        df = (
            model.select(decision_var.entity.id.alias("entity"), val.alias("value"))
            .where(decision_var.values(idx, val))
            .to_df()
        )
        # process solution idx
```

`multi_solution_enumeration.py` carries this end-to-end including `populate=False` and the MAX_WITNESSES sizing rule.

### Use `populate=False` for multi-solution workflows

`populate=True` writes the first solution back to model properties — every subsequent solve on the same model raises `FDError: Found non-unique values` because the property already has tuples from the prior solve. `populate=False` keeps the solver-side values only, accessible via `Variable.values(sol_index, value_ref)`.

```python
decision_var = problem.solve_for(Decision.x, type="bin", populate=False)
```

`populate=False` also suppresses spurious `verify()` warnings tied to the first-solution write-back.

---

## 5. Audit / witness enumeration

When the question is "does the property hold?" or "is there any configuration where X happens?", the solver answer comes from the termination status, not the objective value. This **inverts** MIP intuition: `INFEASIBLE` is the desired outcome.

| Termination status | Audit verdict |
|--------------------|---------------|
| `INFEASIBLE` | **PASS** — no configuration satisfies the witness condition. The property holds. |
| `OPTIMAL` or `SOLUTION_LIMIT` | **FAIL** — at least one configuration was found that violates the property. Extract witnesses for the report. |
| Other (`TIME_LIMIT`, error, `LOCALLY_SOLVED` on a CSP) | **INCONCLUSIVE** — solver did not exhaust the search. Do not interpret as PASS. |

`num_points() == 0` does **not** prove the property holds — the solver may have crashed, hit a time limit, or produced zero solutions for any other reason. Always check the termination status first.

```python
problem.solve("minizinc", solution_limit=MAX_WITNESSES, time_limit_sec=60)
si = problem.solve_info()
if si.termination_status == "INFEASIBLE":
    verdict = "PASS"
elif si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):
    verdict = "FAIL"
    # extract up to si.num_points witnesses
else:
    verdict = "INCONCLUSIVE"
```

`audit_witness.py` (distilled from `underwriting_audit`) carries this pattern end-to-end.

---

## 6. The verify() caveat for implies-bodied ICs

> **`verify()` does not re-evaluate `implies`-bodied integrity constraints.** When an IC's body is wrapped in `implies(condition, body)`, the verify engine has no way to ground the antecedent at check time and silently returns OK — even when the IC is violated by the returned solution. This is **not** a bug in the solver; it is a documented engine limitation. For any IC whose body uses `implies` (decision-indexed table lookups in particular), add an explicit post-solve assertion in Python that re-evaluates the constraint against the extracted values. Templates that demonstrate this skip: `planogram_optimization` (planogram_optimization.py:306), `synthetic_order_lifecycle` (242-243), `synthetic_eligibility_records` (213-214).

The companion silent-failure mode is the empty-aggregate silent-drop: `sum` / `count` over an empty relation drops the IC at compile time. Detect both classes by diffing `num_constraints` / `num_min_objectives` before and after a model edit — if the count drops unexpectedly, an IC was dropped silently.

```python
# Post-solve assertion for an implies-bodied IC
val = Float.ref()
chosen = Integer.ref()
extracted = (
    model.select(decision_var.entity.id, chosen.alias("chosen"))
    .where(decision_var.values(0, chosen))
    .to_df()
)
for row in extracted.itertuples():
    expected = reference_table.loc[row.chosen, "value"]
    actual_aux = aux_values[row.entity]
    assert actual_aux == expected, f"implies cascade violated at entity={row.entity}"
```

---

## 7. Pitfall: big-M vs half-reified implies for active-iff with aggregate body

When an active-iff condition's body is an aggregate over decision variables AND multi-solution mode is on, `implies(active == 1, body <= 0)` spawns a free Boolean auxiliary per inactive row. In enumeration mode this exponentially inflates `num_points` with solutions that differ only in the values of these free auxiliaries.

The big-M form `body + M*active <= TOL + M` has no auxiliary — it is a single inequality whose feasibility flips with `active`. Use it for active-iff conditions where the body is an aggregate over decision variables in multi-solution mode.

```python
# AVOID in multi-solution mode when body is an aggregate over DVs:
implies(active == 1, sum(x_flow).per(Path) <= 0)

# PREFER in multi-solution mode:
sum(x_flow).per(Path) + BIG_M * active <= TOL + BIG_M
```

For decision-indexed **table lookup** (body references a single Ref row's value, not an aggregate), `implies` is still the right shape — see `planogram_optimization` and § 3d above. The pitfall is specific to aggregate-body active-iff in enumeration mode.

Demonstrated at `v1/money_laundering_motif_detection/motif_butterfly.py:165-170`.

---

## 8. Globals available today

Only four global constraints are callable from PyRel today: `all_different`, `implies`, `special_ordered_set_type_1`, `special_ordered_set_type_2`. MiniZinc's native global-constraint library is far richer (`circuit`, `cumulative`, `element`, `table`, `no_overlap`, `inverse`, `lex_lesseq`) but those are not yet exposed.

For the full per-solver coverage matrix (which of the four globals each solver supports) and the syntax for each, see `global-constraints.md`.

---

## 9. Cross-reasoner handoff

MiniZinc-style problems frequently chain off a graph-reasoner output. The typical handoff is `Graph.reachable` (or `Graph.connected_component`) producing a binary closure relation, which the CSP then scopes over via `where=[Reachable(EntityA, EntityB)]`. The CSP's decision variables then range only over the reachable closure, dramatically shrinking the search.

For the chained-discovery handshake (how to declare the closure as enrichment from `rai-graph-analysis`), see `rai-discovery/SKILL.md` § Multi-Reasoner Chaining. `patient_cohort_recruitment` is the canonical template precedent.

---

## 10. Cross-links to examples

The seven examples that distill the idioms above:

| File | Idioms |
|------|--------|
| `examples/multi_solution_enumeration.py` | § 4 (solution_limit, Variable.values, status-gated extraction, MAX_WITNESSES, populate=False) |
| `examples/audit_witness.py` | § 5 (audit verdict mapping, pure-satisfaction property encoding) |
| `examples/integer_slot_with_sentinel.py` | § 2a (K+1 sentinel) + § 3a (count over decision-dependent filter) |
| `examples/implies_table_lookup.py` | § 3d (implies cascade) + § 2c (integer-ID membership IC) + § 6 (verify() skip) |
| `examples/subconcept_solve_for.py` | § 2b (sub-concept predicate marker) |
| `examples/chromatic_number.py` | `minimize(max(...))` directly (no MIP linearization), data-driven bounds, undirected-edge expansion |
| `../../rai-prescriptive-solver-management/examples/scenario_concept_minizinc.py` | MiniZinc analog of `scenario_concept_milp.py` — Scenario as data concept indexing integer decisions; single MiniZinc solve |
