<!-- TOC -->
- [Conflict (IIS) Analysis](#conflict-iis-analysis)
  - [What an IIS is, and why it beats bisection](#what-an-iis-is-and-why-it-beats-bisection)
  - [Requesting it: the asymmetry vs. sensitivity](#requesting-it-the-asymmetry-vs-sensitivity)
  - [Reading membership](#reading-membership)
  - [Joining the conflict to its entity by key](#joining-the-conflict-to-its-entity-by-key)
  - [conflict_status vocabulary and how to act](#conflict_status-vocabulary-and-how-to-act)
  - [The MAYBE_IN_CONFLICT collapse caveat](#the-maybe_in_conflict-collapse-caveat)
  - [Equality constraints in an IIS](#equality-constraints-in-an-iis)
<!-- /TOC -->

## Conflict (IIS) Analysis

This reference covers reading an infeasibility **conflict** (an Irreducible Infeasible Subset, IIS) produced by `solve(conflict=True)`. For *changing* a formulation in response to a conflict, see `rai-prescriptive-problem-formulation`; for *exact marginals* on a feasible model, see [sensitivity-analysis.md](sensitivity-analysis.md).

### What an IIS is, and why it beats bisection

An IIS is a **minimal** set of constraints and variable bounds that cannot all hold simultaneously — minimal in that removing any one member makes that subset satisfiable. It localizes *why* a model is infeasible without your having to guess.

`solve(conflict=True)` returns the conflicting subset in a **single solve**. The fallback — when the solver can't produce an IIS (see `NOT_SUPPORTED` below) — is **bisection**: rebuild the Problem omitting one `satisfy(...)` call — or relaxing one variable bound (`lower=` / `upper=` on `solve_for`) — at a time and re-solve, narrowing down the offender across N solves. Bisect over bounds too, not just constraints: as the IIS definition above says, variable bounds alone can be the entire source of infeasibility.

### Requesting it: the asymmetry vs. sensitivity

`conflict=True` and `sensitivity=True` are mirror diagnostics with **opposite objective requirements** — the easy-to-miss fact:

| | `conflict=True` | `sensitivity=True` |
|---|---|---|
| Objective | **None required** — works on pure-feasibility / CSP models | **Required** — duals are objective marginals |
| Model class | LP, QP, **and MIP** | LP / QP only (MIP has no duals) |
| Answers | *why is this infeasible?* | *what is a marginal worth at the optimum?* |

Request it on the solve whose result you intend to interpret — it's a solve *option*, not a post-processing step:

```python
problem.solve("highs", conflict=True)
```

It is also a *commitment*: a `Problem` already solved **without** diagnostics cannot re-solve **with** them — one result schema per `Problem`, enforced with a `ValueError` before the job is submitted. So an INFEASIBLE plain solve can't be followed by `conflict=True` on the same instance: request `conflict=True` up front when infeasibility is plausible, or re-run the formulation to build a fresh `Problem` for the diagnosis. Once a diagnostic family is loaded, every later re-solve of that `Problem` must keep requesting it — a re-solve may *add* a family (`sensitivity=True` → `sensitivity=True, conflict=True`), never drop one.

### Reading membership

Conflict membership is exposed as **bare predicates** on the objects `satisfy()` and `solve_for()` already return. Use them directly in `where(...)`:

| Predicate | True when (a *lead* — collapses `IN_CONFLICT` + `MAYBE_IN_CONFLICT`; see caveat below) |
|---|---|
| `con.in_conflict` | the solver flags the constraint as conflicting |
| `var.lower_in_conflict` | the solver flags the variable's lower bound as conflicting |
| `var.upper_in_conflict` | the solver flags the variable's upper bound as conflicting |
| `var.integrality_in_conflict` | the solver flags the variable's integrality requirement as conflicting |

```python
# coverage is a satisfy(...) constraint handle; level is a solve_for(...) variable handle.
# Which constraints are in the conflict:
model.select(coverage.shift.name).where(coverage.in_conflict).inspect()
# Which variable bounds are in the conflict:
model.select(level.activity.name).where(level.lower_in_conflict).inspect()
```

### Joining the conflict to its entity by key

A flagged constraint is far more useful paired with the entity it grounds. The constraint's **entity back-pointer** (`coverage.shift`) joins the IIS flag to entity data by key — no name-string parsing:

```python
problem.solve("highs", conflict=True)
si = problem.solve_info()
if si.conflict_status == "CONFLICT_FOUND":
    model.select(
        coverage.shift.name,
        coverage.shift.min_coverage,
    ).where(coverage.in_conflict).inspect()
```

This depends on the constraint family declaring its grounding key at formulation time (`keyed_by={"shift": Shift}`); see `rai-prescriptive-problem-formulation/references/constraint-formulation.md`.

### conflict_status vocabulary and how to act

`solve_info().conflict_status` is `None` unless `conflict=True` was set. When set, it takes one of:

| `conflict_status` | Meaning | Action |
|---|---|---|
| `"CONFLICT_FOUND"` | A minimal conflicting subset of candidates exists — constraints and/or variable-bound flags | Inspect the members; each is a *candidate* (the flags are leads), so relax / omit / soften one and **re-solve to confirm** — relaxing a true member clears *that* subset, but other independent conflicts may remain. |
| `"NO_CONFLICT_EXISTS"` | The model is feasible (or feasibility wasn't the blocker) | No conflict to read; revisit the termination status. |
| `"NOT_SUPPORTED"` | The chosen solver can't produce an IIS | Fall back to **bisection** (rebuild omitting one `satisfy(...)` — or relaxing one variable bound — at a time), or switch to a solver that supports conflicts. |
| `"FAILED"` | The conflict computation itself errored | Read `solve_info().error` (a `tuple[str, ...]`) for the solver's reason — a `FAILED` conflict reports on the shared error channel, not a conflict-specific field. |

The conflict is a subset of *candidates*, which may mix constraints and variable-bound flags (including collapsed maybe-members, below). Walk every flagged member, not just the constraints.

### The MAYBE_IN_CONFLICT collapse caveat

The solver distinguishes `IN_CONFLICT` from `MAYBE_IN_CONFLICT`, but the membership predicates **collapse both into `True`**. Two consequences:

- A `True` flag (`in_conflict`, `*_in_conflict`) may be only a *maybe* — the tool couldn't rule the member out, not necessarily that it's a definite part of the conflict.
- A `False` flag does **not** prove the constraint or bound is uninvolved in the infeasibility. The conflict is *one* minimal subset, and an IIS is not unique — a different valid IIS, or an independent conflict elsewhere, could involve a member this one left out.

So treat only `True` as a lead to act on, and never read a `False` flag as a clean bill of health — confirm non-involvement by relaxing a member and re-solving, not by reading flags. This matters most for `integrality_in_conflict` — Gurobi only ever reports `MAYBE_IN_CONFLICT` for integrality (never a definite `IN_CONFLICT`), so a `True` there is always a lead, never a confirmation.

### Equality constraints in an IIS

`in_conflict` works on **equality (`==`)** families too — the conflict tool splits an equality internally into a `≤` and a `≥`. Validated on HiGHS: an equality constraint returns a proven `IN_CONFLICT` membership, while binary / integrality members come back as `MAYBE_IN_CONFLICT` (folded into `True` by the collapse above). Both `≤` / `≥` and `=` families are safe to use in examples.
