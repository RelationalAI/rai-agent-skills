# CSP-style formulation in PyRel

CSP-style is a **style**, not a separate problem class, and it covers optimization as well as pure satisfaction. It is characterized by `Problem(model, Integer)` + `solver="minizinc"`, all-discrete decisions and data, and constraint + objective shapes (globals, `count` / products over decision variables, `min`/`max` in objective) that MiniZinc supports natively where HiGHS/Gurobi require manual reformulation.

<!-- TOC -->
- [1. When this style fits](#1-when-this-style-fits)
- [2. Decision-variable shapes](#2-decision-variable-shapes)
- [3. Constraint idioms](#3-constraint-idioms)
- [4. Multi-solution mode](#4-multi-solution-mode)
- [5. Audit / witness enumeration](#5-audit--witness-enumeration)
- [6. The verify() caveat for solver-only IC bodies](#6-the-verify-caveat-for-solver-only-ic-bodies)
- [7. Pitfall: big-M vs half-reified implies for active-iff with aggregate body](#7-pitfall-big-m-vs-half-reified-implies-for-active-iff-with-aggregate-body)
- [8. Globals available today](#8-globals-available-today)
- [9. Cross-reasoner handoff](#9-cross-reasoner-handoff)
- [10. Cross-links to examples](#10-cross-links-to-examples)
<!-- /TOC -->

---

## 1. When this style fits

MIP-style vs CSP-style decision rules: [SKILL.md](../SKILL.md) > MIP-style vs CSP-style. The CSP-specific detail on top of it:

- `all_different` (callable MiniZinc-only — see the matrix in `global-constraints.md`), `!=` / `==` between decision variables, and pairwise `count` over decision-variable equality. The MIP wire does not consume `!=` natively, so the MIP equivalent is pairwise binary indicators with big-M per pair. MiniZinc takes these directly with strong propagation. See `n_queens.py`, `sudoku.py`, `chromatic_number.py` (per-edge `!=`), `pairwise_no_repeat.py`.
- Multi-solution enumeration. `solution_limit=K` + `Variable.values(sol_index, val)` enumerates up to K distinct feasible solutions on MiniZinc (§ 4); HiGHS does not enumerate — there the limit can stop the search early and return a suboptimal incumbent. Per-solver semantics: `rai-prescriptive-results/references/solver-parameters.md` > `solution_limit` semantics. See `multi_solution_enumeration.py`, `audit_witness.py`.
- Decision-indexed `implies` cascades (§ 3d). HiGHS and Gurobi reject any antecedent other than `x == 0` / `x == 1` on a single variable `x` (`The implies condition must compare to 0 or 1.`), so a cascade over `decision_id == k` is MiniZinc-only as written.

Per-solver operator support, including the operators every solver rejects on decision variables (`//`, `%`, floor/ceil, trig): `numerical-and-mip.md` > Operator and Construct Compatibility by Solver.

---

## 2. Decision-variable shapes

CSP-style problems share a small set of recurring decision-variable shapes. Pick the one that matches the data, then verify membership.

From `relationalai>=1.29`, `problem.display()` raises `ValueError` unless **every** decision variable in the Problem carries a `name=`, not just the ones you read, and it checks once at least one variable has grounded. Pass a discriminating `name=["x", Entity.id]` on each `solve_for`. The skeletons below omit it where it would obscure the pattern.

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

This is the shape that admits the most-frequent silent-failure mode in CSP-style formulation. **When an integer decision variable is bounded only by `lower=min(Ref.id), upper=max(Ref.id)`, the solver is free to pick any integer in that range — including IDs not present in the reference data.** If a downstream `implies(decision_id == Ref.id, ...)` cascade looks up properties on the chosen ID and the lookup is non-total, those properties stay silently unconstrained, and `verify()` returns OK because `implies`-bodied ICs are not re-evaluated post-solve (see § 6).

Two safe forms:

```python
# Form A: explicit membership IC — exactly one Reference row matches each Decision
problem.solve_for(Decision.id, type="int", lower=min_id, upper=max_id)
problem.satisfy(model.require(
    count(Reference, Reference.id == Decision.id).per(Decision) == 1
))

# Form B: dense-contiguous validation upfront (pre-solve)
# Check at problem-build time that {min_id..max_id} == set(Reference.id);
# if not, switch to Form A or filter Reference to a dense range.
n_decision_domain = (max_id - min_id + 1)
n_ref_rows = len(model.select(Reference.id).to_df())
assert n_decision_domain == n_ref_rows, "integer-ID decision domain is not dense over Reference"
```

Demonstrated in `implies_table_lookup.py` (distilled from `planogram_optimization` and cross-referenced with `underwriting_audit`).

### 2d. Binary-availability-scoped decision

Familiar pattern from MIP-style scheduling (e.g., `shift_assignment`). Worth listing here because it remains correct in CSP-style and pairs naturally with `count` over decision-dependent filters (idiom 3a).

```python
Worker.x_assigned = model.Property(f"{Worker} on {Shift} is {Integer:assigned}")
problem.solve_for(
    Worker.x_assigned, type="bin",
    where=[Worker.available_for(Shift)],
    name=["assign", Worker.id, Shift.id],
)
```

### 2e. Enum-indexed decision: one binary per (entity, member)

*Requires relationalai>=1.12.* Not CSP-specific — the same shape works in MIP-style.

When the decision is "which member of a closed vocabulary does each entity take," declare a `model.Enum`, type the decision property by it, and `solve_for` once — the solver creates one binary variable per (entity, member) pair. This replaces K parallel per-member binary properties.

```python
class EventType(model.Enum):
    PLACE = 1
    MODIFY = 2
    CANCEL = 3
    FILL = 4

Event.has_type = model.Property(f"{Event} is {EventType:event_type} if {Integer:indicator}")
problem.solve_for(Event.has_type, type="bin", name=["is_type", Event.id])

# Exactly one member per entity (one-hot)
problem.satisfy(model.require(sum(Event.has_type).per(Event) == 1))

# Member-sliced constraint: bind one member's indicator column via the ternary
# form, then aggregate it per parent entity (Event.order = parent relationship)
place_ind = Integer.ref()
problem.satisfy(
    model.where(Event.has_type(EventType.PLACE, place_ind))
    .require(sum(Event, place_ind).per(Event.order) == 1)
)
```

**Readback of the decided member.** `Enum.lookup()` is forward-only — `EventType.lookup(free_ref)` compiles at construction but fails at query time with `[Unground Variable]`. Recover the chosen member with a derived enum-typed property, one `define()` per member (members are Python-iterable):

```python
Event.event_type = model.Property(f"{Event} has decided {EventType:event_type}")
for member in EventType:
    ind = Integer.ref()
    model.define(Event.event_type(member)).where(Event.has_type(member, ind), ind == 1)

# Post-solve:
model.select(Event.id, Event.event_type.name.alias("event_type")).to_df()
```

---

## 3. Constraint idioms

### 3a. Cardinality via `count(X, cond).per(group)` — decision-dependent filter

The CSP-style-distinctive point on top of the base `count(X, cond)` syntax (documented in `rai-pyrel/references/common-pitfalls.md`): when `cond` depends on a decision variable, the comparison **must live inside** `count`'s second argument, not as a filter in an outer `where`. An outer `where` filter on a decision-variable value would prune the search space at pre-solve, eliminating feasible search states; the inner form lets `count` count states per branch during solving.

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

**Binder vs filter in the outer `where`.** A multi-arity-property invocation in `where(...)` (e.g., `Player.assign(w, x)`) is a binder over the relation's tuples — it does NOT prune to a specific decision value. See `rai-pyrel/references/expression-rules.md` (Multi-arity property invocation in where as binder) for the general mechanic. The CSP-specific consequence is the rule above: putting a decision-var **equality** in the outer where is a search-pruning filter and is the failure mode this section guards against.

**Two decision-variable refs in the count's comparison.** When `count`'s second-arg comparison is between TWO decision-variable values rather than decision-vs-data, both refs must be bound through the outer `where` (via the multi-arity-binder pattern). This is the pairwise no-repeat shape — count occurrences of "two entities' decisions match" across a data dimension.

```python
r = Integer.ref()   # shared round-dimension ref
# Pairwise no-repeat: count rounds where two players are in the same group, must be <= 1
model.where(
    p0 := Player.ref(),
    p1 := Player.ref(),
    p0.p < p1.p,                # data filter (Player.p is data) — picks one orientation
    g0 := Integer.ref(),
    g1 := Integer.ref(),
    p0.assign(r, g0),           # binder — anchors g0 to p0's decision value at round r
    p1.assign(r, g1),           # binder — anchors g1 to p1's decision value at round r
).require(
    count(r, g0 == g1).per(p0, p1) <= 1   # count's last arg compares two decision refs
)
```

The MIP-side cost of this shape is steep — pairwise `count(...) <= 1` over decision-variable equality lowers to `O(n_pairs × n_rounds)` big-M disjunctions. MiniZinc consumes the equality directly via propagation. Demonstrated end-to-end in `pairwise_no_repeat.py` (adapted from the classic social golfer benchmark, CSPLib Problem 010).

**Symbolic in `per(...)`** is always wrong — `per(...)` groups by data dimensions, not by decision values. If grouping requires a derived integer (e.g., sudoku's 3×3 box index `(i - 1) // side`), arithmetic on data refs in `per(...)` is fine; arithmetic involving a decision-variable value is not.

### 3b. Undirected-edge expansion via reverse-define

PyRel relationships are directed. CSP-style graph problems (coloring, pod placement on an anti-affinity graph, book-slate authorship pairs) need both orientations. Use reverse-define at the Rules level for persistent symmetric relations, or `.ref()`-pair inline for single-IC undirected matching.

For the mechanic, see `rai-pyrel/references/expression-rules.md` (undirected-edge expansion section). `chromatic_number.py` carries the concrete worked example.

### 3c. Pairwise via dual `.ref()` + `id_a < id_b` — CSP-style symmetry-break

`.ref()` mechanics (pairwise `Concept.ref()` + `Float.ref()` value-binding) are documented in `rai-pyrel/references/expression-rules.md` § References and Aliasing. The CSP-style point is the `id_a < id_b` half-pair filter: it prevents the solver from re-encoding `(a, b)` and `(b, a)` as two separate constraint instances, halving the constraint count without changing the feasible set.

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

The dominant pattern for "predict-then-optimize" in CSP-style: a decision integer selects an entry from a reference table; an `implies` cascade binds an auxiliary variable to the chosen row's value; downstream constraints / objective use the auxiliary.

```python
# Decision: which assortment is placed at this position
problem.solve_for(Position.x_assort, type="int", lower=min_id, upper=max_id)
# Auxiliary: revenue at this position (Integer — MiniZinc requires Problem(model, Integer))
problem.solve_for(Position.x_revenue, type="int", lower=0)
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

CSP-style problems frequently want K different feasible solutions rather than one optimum. `solution_limit=K` on `solve(...)` enables this on MiniZinc; its statuses and what the returned set is (and is not): `rai-prescriptive-results/references/solver-parameters.md` > `solution_limit` semantics.

- **K must exceed the feasible-set size for `OPTIMAL` + stable extraction order.** If K < feasible-set size, you get a `SOLUTION_LIMIT` cut-off whose order is solver-dependent — fine for K-of-many enumeration, problematic when the test expects a deterministic full set. `OPTIMAL` proves the set complete only if the run finished inside `time_limit_sec`.
- **Extract via `Variable.values(sol_index, value_ref)`** — solution `0` to `num_points - 1`. With `populate=True` the first solution is also written back to model properties; with `populate=False` only `Variable.values` is populated, and the model is unchanged.

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

`verify()` cannot check a `populate=False` solution (§ 6, Regime 3).

---

## 5. Audit / witness enumeration

When the question is "does the property hold?" or "is there any configuration where X happens?", the answer is the termination status: the status → PASS / FAIL / INCONCLUSIVE table and the `num_points() == 0` caveat are in `rai-prescriptive-results` > Audit / witness mode. This section is the formulation side.

**Counterexample IC = property negation.** The modeling move behind every audit problem: encode the property to be audited as its negation in the constraint set. `INFEASIBLE` on the negated form proves the original property holds across the entire feasible space (not just sampled fixtures); `OPTIMAL` / `SOLUTION_LIMIT` returns a witness that violates the original property. `audit_witness.py` follows this move — the IC `sum(salary × x_flagged) >= cap + 1` is the negation of "no K-subset exceeds cap"; INFEASIBLE on the negation = PASS on the original.

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

`audit_witness.py` (distilled from `underwriting_audit`) carries this pattern end-to-end. A "FAIL" verdict line should disambiguate itself (e.g., `FAIL (ruleset has counterexamples)`) so consumers don't misread a property failure as a template error. The same negation audit runs on HiGHS/Gurobi (no `solution_limit`) when the data is continuous, but yields at most one witness, and the example's breach threshold `cap + 1` assumes integer totals: with continuous data, use `cap + tol` for a tolerance you state, and report PASS as holding up to that tolerance.

---

## 6. The verify() caveat for solver-only IC bodies

> **`verify()` does not re-evaluate ICs whose body is a solver-only construct (`implies`-bodied or `all_different`-bodied).** These constraints lower to wire-format constraint relations the verify engine cannot ground at check time, so verify silently returns OK — even when the IC is violated by the returned solution. This is **not** a bug in the solver; it is a documented engine limitation. The `implies` case is the most common (decision-indexed table lookups in particular); `all_different` has the same root cause and the same silent-OK behavior.

The companion silent-failure mode is the empty-aggregate silent-drop: `sum` / `count` over an empty relation drops the IC at compile time. Detect both classes by diffing `num_constraints` / `num_min_objectives` before and after a model edit — if the count drops unexpectedly, an IC was dropped silently.

### Three regimes for handling verify() with solver-only ICs

Pick the regime that matches the constraint mix:

**Regime 1 — Mixed (some arithmetic ICs, some solver-only).** Call `verify()` to re-evaluate the arithmetic ICs; pair each solver-only IC with an explicit post-solve Python assertion that re-evaluates the constraint against the extracted values. `implies_table_lookup.py` follows this regime — the `implies` cascade ships with the post-solve loop below.

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

**Regime 2 — All solver-only (every IC is `implies`- or `all_different`-bodied).** `verify()` has nothing it can re-evaluate; skip it entirely and rely on per-IC post-solve Python assertions. Calling `verify()` in this regime just adds noise.

**Regime 3 — `populate=False`.** Multi-solution and audit/witness workflows use `populate=False` so decision values stay solver-side rather than being written back to the relational layer (see § 4). With no values in the relational layer, `verify()` cannot ground *any* IC against the chosen solution — even pure-arithmetic ICs — and prints spurious "Requirements not met" warnings instead of doing real verification. Skip `verify()` and use per-IC post-solve assertions, OR `model.select(decision_var.values(idx, val))`-style extraction + Python checks. `multi_solution_enumeration.py` and `audit_witness.py` are in this regime.

---

## 7. Pitfall: big-M vs half-reified implies for active-iff with aggregate body

When an active-iff condition's body is an aggregate over decision variables AND multi-solution mode is on, `implies(active == 1, body <= 0)` spawns a free Boolean auxiliary per inactive row. In enumeration mode this exponentially inflates `num_points` with solutions that differ only in the values of these free auxiliaries.

The big-M form `body + M*active <= TOL + M` has no auxiliary — it is a single inequality whose feasibility flips with `active`. Use it for active-iff conditions where the body is an aggregate over decision variables in multi-solution mode.

```python
# AVOID in multi-solution mode when body is an aggregate over DVs:
implies(active == 1, sum(Flow.x_flow).per(Path) <= 0)

# PREFER in multi-solution mode:
sum(Flow.x_flow).per(Path) + BIG_M * active <= TOL + BIG_M
```

For decision-indexed **table lookup** (body references a single Ref row's value, not an aggregate), `implies` is still the right shape — see § 3d above. The pitfall is specific to aggregate-body active-iff in enumeration mode.

Demonstrated end-to-end in `big_m_active_iff_aggregate.py` (distilled from the AML motif-butterfly detector — hub-balance constraint that is active only when an account is chosen as a hub).

---

## 8. Globals available today

Callable globals, their syntax and per-solver coverage: [global-constraints.md](global-constraints.md).

---

## 9. Cross-reasoner handoff

CSP-style problems frequently chain off a graph-reasoner output. The typical handoff is `Graph.reachable` (or `Graph.connected_component`) producing a binary closure relation, which the CSP then scopes over via `where=[Reachable(EntityA, EntityB)]`. The CSP's decision variables then range only over the reachable closure, dramatically shrinking the search.

For the chained-discovery handshake (how to declare the closure as enrichment from `rai-graph-analysis`), see `rai-discovery/SKILL.md` § Multi-Reasoner Chaining. `patient_cohort_recruitment` is the canonical template precedent.

---

## 10. Cross-links to examples

Every example named above, plus the other CSP-style examples, is in [examples-index.md](examples-index.md) (rows marked CSP).
