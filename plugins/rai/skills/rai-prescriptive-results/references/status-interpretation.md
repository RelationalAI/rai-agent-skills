# Status Communication Guide

Per-status stakeholder phrasing, gap interpretation, reframing language, and the iterate-vs-accept judgment. Diagnosis procedures (conflict / IIS localization, fallback checks, unbounded checklist) live in SKILL.md > Status Interpretation — this file covers the communication layer. Load it when composing a user-facing report on any solve outcome.

## Optimal

The solver found the best possible solution within its tolerance settings (typically 1e-6 for LP, 0.01% MIP gap for MIP).

**What to tell users:** "We found the best possible plan given your requirements. Here is what it recommends..."
**Next steps:** Proceed to quality assessment, then explain results.

## Infeasible

No solution satisfies all constraints simultaneously. The problem as stated is impossible. Diagnose before presenting — see SKILL.md > Infeasible diagnosis.

**What to tell users:** "The requirements as stated cannot all be satisfied simultaneously. The most likely conflict is [specific conflict]. Options: relax [constraint], increase [capacity], or allow unmet demand with a penalty."
**Next steps:** Identify the binding conflict, present trade-off options, add slack/penalty variables. A common and valuable path is moving the conflicting hard constraint to the objective with a penalty — feasibility restoration through softening is often more useful than pure diagnosis.

**INFEASIBLE as diagnostic tool:** Intentionally solving with a proposed constraint set to test feasibility boundaries is a valid modeling technique. An infeasible result tells you the constraint set is too tight — which constraints to relax.

## Unbounded (DUAL_INFEASIBLE)

The objective can improve infinitely — the solver can keep making the solution "better" without limit. The termination status is `"DUAL_INFEASIBLE"` (not `"UNBOUNDED"`).

**What to tell users:** "The model is missing limits that would bound the solution. Likely cause: [missing capacity constraint / missing budget limit / wrong objective direction]."
**Next steps:** Add missing bounds or constraints, verify objective direction and coefficient signs.

## Feasible (MIP)

For MIP problems, HiGHS may return `"Feasible"` instead of `"OPTIMAL"` when a solution is found but optimality is not proven within the default MIP gap tolerance. Treat `"Feasible"` the same as `"TIME_LIMIT"` for gap interpretation below; read the realized gap from `si.ancillary` if present, or the solver log otherwise.

## Time Limit

The solver found a feasible solution but could not prove it is optimal within the time allowed.

**Gap interpretation:**
- Gap < 1%: Solution is very close to optimal; usually acceptable.
- Gap 1-5%: Solution is good but there may be modest room for improvement.
- Gap > 10%: Solution quality is uncertain; consider increasing time limit or simplifying the model.

Read the realized gap programmatically from `si.ancillary` when present — it's a schema-less `Mapping[str, str]`, so discover the key first (`si.display()` or iterate `si.ancillary.items()`) and read with `.get(key)`, never `si.ancillary[key]` (a hardcoded key risks `KeyError` across solvers). Fall back to the solver log if no gap-style key is present.

**What to tell users:** "The solver found a solution within [X%] of the best possible. [If gap is small: This is likely very close to optimal.] [If gap is large: More time or a simpler model could improve this.]"
**Next steps:** For large gaps, increase time limit, tighten Big-M values, add symmetry-breaking constraints, or simplify the model.

**TIME_LIMIT with acceptable gap:**
- A 2% gap after 60 seconds may be perfectly good for operational use. The "optimal" solution is at most 2% better — often indistinguishable in business terms.
- **Rule of thumb:** If the gap is under 5% and the solution values make business sense, present it as "near-optimal" and let the user decide whether to invest more solve time.
- Don't automatically increase time limits — ask: "Is a 2% improvement worth waiting 10 minutes?"

## Error / Unknown

Compilation or solver errors prevented a solution.

**Common causes:** Undefined properties referenced in formulation, type mismatches, syntax errors in expressions, solver license issues.
**What to tell users:** "The model could not be solved due to a technical error: [error message]. This needs to be fixed before we can get results."
**Next steps:** Check compilation output, fix expression syntax, verify all referenced properties exist.

## Reframing for users

A non-optimal termination status is information about the problem structure, not necessarily a failure to fix.

- Instead of "the solver failed to find an optimal solution," say: "The solver found a solution within X% of the theoretical best. Here's what it tells us about the problem..."
- INFEASIBLE + constraint analysis = "These requirements cannot all be satisfied simultaneously. Which one has the most flexibility?"
- TIME_LIMIT + good gap = "This is a strong solution. More time would give diminishing returns."

## When to iterate vs. accept

- **Iterate:** INFEASIBLE with no clear conflict, DUAL_INFEASIBLE, TIME_LIMIT with gap > 10%, trivial solution (all zeros)
- **Accept:** TIME_LIMIT with gap < 5%, OPTIMAL (always), INFEASIBLE when used as intentional feasibility probe
