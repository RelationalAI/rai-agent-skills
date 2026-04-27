# Failure Taxonomy

This taxonomy spans the full optimization lifecycle (generate → compile → solve → optimal → non-trivial → meaningful). Agents from `rai-prescriptive-problem-formulation` consult it for `generates`/`compiles` levels, and agents from `rai-prescriptive-solver-management` consult it for `solves` and `optimal` levels. Kept in one place so the ladder stays coherent.

## Table of Contents
- [Failure Taxonomy by Level](#failure-taxonomy-by-level)
- [Diagnosis Protocol](#diagnosis-protocol)

---

## Failure Taxonomy by Level

When a formulation fails at a level, the root cause falls into specific categories. Diagnose using the taxonomy for the **first failed level** — fixing upstream failures often resolves downstream ones.

| Failed Level | Root Cause | Description | Typical Fix |
|-------------|-----------|-------------|-------------|
| **generates** | `syntax_error` | Invalid Python / PyRel syntax | Fix indentation, missing imports, malformed expressions |
| **generates** | `undefined_reference` | References concept/property that doesn't exist | Check model introspection; use `enrich_ontology` if property is missing |
| **compiles** | `type_mismatch` | Wrong types in `solve_for`, `satisfy`, or `minimize`/`maximize` | Check that variable types match constraint operands (Float vs Integer) |
| **compiles** | `unresolved_overload` | `name=[]` traverses relationships or has multi-hop paths | Use primitive identity fields in `name=[]`; single-hop only |
| **compiles** | `missing_registration` | Variables/constraints defined but not registered with Problem | Ensure all `solve_for`, `satisfy`, `minimize`/`maximize` calls reference the Problem instance |
| **solves** | `solver_crash` | Solver errors out (license, memory, malformed problem) | Check solver logs; simplify problem size; verify solver availability |
| **solves** | `solve_error` | Solver returned error (license, timeout, numerical) | Check solver logs; re-solve is safe on same Problem instance (SDK >= 1.0.3) |
| **optimal** | `infeasible` | No solution satisfies all constraints | Over-constrained — relax bounds, remove conflicting constraints, add slack |
| **optimal** | `dual_infeasible` | Objective can improve infinitely (unbounded) | Missing bounds or capacity constraints; check objective direction |
| **optimal** | `time_limit_large_gap` | Solver timed out with >5% gap | Increase time, tighten Big-M, add symmetry breaking, reduce problem size |
| **non-trivial** | `missing_forcing_constraint` | "Do nothing" satisfies all constraints — trivial zero solution | Add demand satisfaction, coverage, or assignment completeness constraints |
| **non-trivial** | `join_mismatch` | Forcing constraints exist but `.where()` joins match zero rows | Fix relationship paths in constraint joins; verify data alignment |
| **non-trivial** | `disconnected_variables` | Multiple variable sets but not all linked through constraints | Add conservation or linking constraints at shared entities |
| **non-trivial** | `all_at_bounds` | Variables pushed to lower/upper bounds uniformly | Check that constraint RHS values are populated (not null/zero); verify data loads |
| **meaningful** | `wrong_scale` | Values exist but are implausible (1e12 production, 0.001 assignments) | Check coefficient magnitudes; verify unit consistency in data |
| **meaningful** | `concentrated` | Solution uses only 1 entity when many expected | Add fairness/balance constraints or check cost differentials |
| **meaningful** | `wrong_direction` | Objective optimizes in wrong direction (minimizing revenue, maximizing cost) | Flip `minimize` ↔ `maximize`; check coefficient signs |
| **meaningful** | `missing_entity_coverage` | Some required entities (tasks, demands, regions) have no assigned activity | Check that entity creation covers all required instances; verify `.where()` filters |

## Diagnosis Protocol

1. Determine the highest level reached on the ladder
2. Look up the failed level in the taxonomy
3. Check root causes in order (most common first)
4. Apply the typical fix, re-check the ladder
5. If fix causes regression (drops to lower level), revert and try alternative
