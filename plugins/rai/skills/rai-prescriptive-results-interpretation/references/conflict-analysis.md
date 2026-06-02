<!-- TOC -->
- [Conflict (IIS) Analysis](#conflict-iis-analysis)
  - [What an IIS is, and why it beats bisection](#what-an-iis-is-and-why-it-beats-bisection)
  - [Requesting it: the asymmetry vs. sensitivity](#requesting-it-the-asymmetry-vs-sensitivity)
  - [Reading membership](#reading-membership)
  - [Joining the conflict to its entity by key](#joining-the-conflict-to-its-entity-by-key)
  - [conflict_status vocabulary and how to act](#conflict_status-vocabulary-and-how-to-act)
  - [The MAYBE_IN_CONFLICT collapse caveat](#the-maybe_in_conflict-collapse-caveat)
  - [Example / idiom guardrail](#example--idiom-guardrail)
<!-- /TOC -->

## Conflict (IIS) Analysis

This reference covers reading an infeasibility **conflict** (an Irreducible Infeasible Subset, IIS) produced by `solve(conflict=True)`. For *changing* a formulation in response to a conflict, see `rai-prescriptive-problem-formulation`; for *exact marginals* on a feasible model, see [sensitivity-analysis.md](sensitivity-analysis.md).

### What an IIS is, and why it beats bisection

An IIS is a **minimal** set of constraints and variable bounds that cannot all hold simultaneously — minimal in that removing any one member makes that subset satisfiable. It localizes *why* a model is infeasible without your having to guess.

`solve(conflict=True)` returns the conflicting subset in a **single solve**. The fallback — when the solver can't produce an IIS (see `NOT_SUPPORTED` below) — is **bisection**: rebuild the Problem omitting one `satisfy(...)` call at a time and re-solve, narrowing down the offender across N solves.

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

### Reading membership

Conflict membership is exposed as **bare predicates** on the objects `satisfy()` and `solve_for()` already return. Use them directly in `where(...)`:

| Predicate | True when |
|---|---|
| `con.in_conflict` | the constraint is in the IIS |
| `var.lower_in_conflict` | the variable's lower bound is in the IIS |
| `var.upper_in_conflict` | the variable's upper bound is in the IIS |
| `var.integrality_in_conflict` | the variable's integrality requirement is in the IIS |

```python
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

This depends on each constraint-family instance being named distinctly at formulation time (`name=["coverage", Shift.name]`); see `rai-prescriptive-problem-formulation/references/constraint-formulation.md`.

### conflict_status vocabulary and how to act

`solve_info().conflict_status` is `None` unless `conflict=True` was set. When set, it takes one of:

| `conflict_status` | Meaning | Action |
|---|---|---|
| `"CONFLICT_FOUND"` | A minimal conflicting subset of candidates exists — constraints and/or variable-bound flags | Inspect the members; relax / omit / soften one. Relaxing one member resolves **that** subset; if other independent conflicts remain the model can still be infeasible, so **re-solve to confirm**. |
| `"NO_CONFLICT_EXISTS"` | The model is feasible (or feasibility wasn't the blocker) | No conflict to read; revisit the termination status. |
| `"NOT_SUPPORTED"` | The chosen solver can't produce an IIS | Fall back to **bisection** (rebuild omitting one `satisfy(...)` at a time), or switch to a solver that supports conflicts. |
| `"FAILED"` | The conflict computation itself errored | Read `solve_info().conflict_message` for the solver's reason. |

The conflict is a subset of *candidates*, which may mix constraints and variable-bound flags (including collapsed maybe-members, below). Walk every flagged member, not just the constraints.

### The MAYBE_IN_CONFLICT collapse caveat

The solver distinguishes `IN_CONFLICT` from `MAYBE_IN_CONFLICT`, but the membership predicates **collapse both into `True`**. Two consequences:

- A `True` flag (`in_conflict`, `*_in_conflict`) may be only a *maybe* — the tool couldn't rule the member out, not necessarily that it's a definite part of the conflict.
- A `False` flag does **not** prove the constraint or bound is uninvolved in the infeasibility. The conflict is *one* minimal subset, and an IIS is not unique — a different valid IIS, or an independent conflict elsewhere, could involve a member this one left out.

So treat only `True` as a lead to act on, and never read a `False` flag as a clean bill of health — confirm non-involvement by relaxing a member and re-solving, not by reading flags. This matters most for `integrality_in_conflict`.

### Example / idiom guardrail

Keep conflict snippets on `≤` / `≥` constraint families — the tested shape. `in_conflict` on an **equality (`==`)** row (which the conflict tool splits internally into a `≤` and a `≥`) together with the `MAYBE_IN_CONFLICT` path is currently **unverified** on-engine; don't lean on equality-in-IIS in examples until it's confirmed.
