# Formulation Simplification

## Table of Contents
- [Static parameters vs. dynamic calculations](#static-parameters-vs-dynamic-calculations)
- [Requirements vs. goals: constraint or objective?](#requirements-vs-goals-constraint-or-objective)
- [Grouped constraints vs. granular combinations](#grouped-constraints-vs-granular-combinations)
- [Recognizing over-specification](#recognizing-over-specification)
- [Simplification principles](#simplification-principles)

---

## Static parameters vs. dynamic calculations

**The problem:** Users want constraints that depend on dynamically calculated values ("capacity can't exceed 3x last period's utilization," "limit should be 150% of historical average").

**Why it is problematic:** Requires pulling historical data at solve time, makes the model harder to debug, creates hidden dependencies, and makes what-if analysis difficult.

**Better approach:** Use static parameters that can be easily updated. Instead of computing a dynamic cap, set a static limit that achieves the same constraint. The user can update it when planning changes.

**When dynamic IS appropriate:** The calculation is simple and stable (e.g., sum of child values), the relationship is fundamental (e.g., inventory balance), or real-time data is essential (rare in planning problems).

## Requirements vs. goals: constraint or objective?

**The fundamental distinction:**
- **Requirements** (non-negotiable) become **constraints**: must be satisfied for a valid solution
- **Goals** (can trade off) become **objective terms**: what we are trying to achieve, with priorities

It is a REQUIREMENT (constraint) if:
- Violating it makes the solution invalid/unusable
- There are contractual, legal, or safety implications
- It is a physical impossibility to violate (capacity, conservation)

It is a GOAL (objective) if:
- Missing it is undesirable but the solution is still useful
- There are trade-offs between competing targets
- Priorities exist (some targets matter more than others)
- You want visibility into how close you got

**The problem with goals-as-constraints:** Problem becomes infeasible if goals conflict with capacity. No solution tells you nothing about which goal caused the conflict. Small data changes can flip from feasible to infeasible.

**Better approach for goals:** Use shortfall variables and penalty terms in the objective. This lets the optimizer trade off between goals and shows how close you got to each target.

## Grouped constraints vs. granular combinations

**The problem:** Users specify constraints for specific entity combinations ("Facilities A and B combined must handle 60% of demand"). This creates many specific constraints, is hard to maintain as entities change, and obscures the underlying business intent.

**Better approach:** Define groups that capture the business intent. A single group constraint replaces multiple pairwise constraints. Adding/removing members means updating group membership, not rewriting constraints.

**When granular IS appropriate:** Truly entity-specific rules (contractual minimums with specific partners), temporary exceptions, or when the grouping does not exist conceptually in the business.

## Recognizing over-specification

| User says | Likely issue | Better approach |
|-----------|-------------|-----------------|
| "calculated from historical data" | Dynamic dependency | Static parameter |
| "MUST hit target" | Goal vs. requirement unclear | Clarify, then constraint or objective |
| "X and Y combined" | Granular combinations | Meaningful groups |
| "factor in the score/rating" | Complex constraint coefficient | Objective term |
| "only if", "depends on" | Conditional complexity | Simplify or use indicator |

## Simplification principles

**Prefer:**
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for requirements
- Group-level constraints over pairwise/granular combinations
- Simple bounds over conditional logic

**The test:** "If the business context changes slightly, how hard is it to update this formulation?" A good formulation requires changing one parameter or group membership. A problematic formulation requires rewriting multiple constraints.
