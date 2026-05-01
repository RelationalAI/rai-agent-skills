<!-- TOC -->
- [Numerical Stability](#numerical-stability)
  - [Four Categories of Numerical Issues](#four-categories-of-numerical-issues)
  - [Coefficient Scaling](#coefficient-scaling)
  - [Big-M Sizing](#big-m-sizing)
  - [Tolerances](#tolerances)
  - [Additional Numerical Guidelines](#additional-numerical-guidelines)
- [Solver Log Interpretation](#solver-log-interpretation)
- [MIP Formulation Techniques](#mip-formulation-techniques)
  - [LP Relaxation Strength](#lp-relaxation-strength)
  - [Symmetry Breaking](#symmetry-breaking)
  - [Integrality Tolerance](#integrality-tolerance)
  - [Modeling Logical Constraints](#modeling-logical-constraints)
  - [MIP Self-Check](#mip-self-check)
- [Operator and Construct Compatibility by Solver](#operator-and-construct-compatibility-by-solver)
- [Reformulation Techniques for Solver Compatibility](#reformulation-techniques-for-solver-compatibility)
<!-- /TOC -->

## Numerical Stability

Numerical issues are among the most common causes of solver failures and unreliable results. All numerical assessment should be **relative to the specific formulation's data, domain, and solver** -- not against fixed thresholds.

### Four Categories of Numerical Issues

1. **Coefficient rounding during construction:** Truncating coefficients when building the model (e.g., 0.333 instead of 1/3). Preserve full precision.
2. **Floating-point arithmetic limitations:** 0.1 + 0.2 != 0.3 in floating point. Avoid equality comparisons on computed values.
3. **Unrealistic precision expectations:** Expecting 12 decimal places of accuracy. Accept solver tolerances (typically 1e-6 to 1e-9).
4. **Ill-conditioning and geometry:** Nearly parallel constraints, very flat feasible regions. Reformulate to improve conditioning.

### Coefficient Scaling

Assess the ratio between the largest and smallest non-zero coefficients **in this formulation** (objective + constraints combined). When the range is wide enough that small terms become invisible relative to solver tolerances, the solver effectively ignores them.

**Context to check:** Solver sensitivity (HiGHS/Ipopt > Gurobi; simplex > interior point), problem type (LP more sensitive than MIP), and whether the small-coefficient terms actually matter for solution quality.

**When flagging, explain in domain terms** -- e.g., "cost coefficients are $0.01/unit while capacity is 10M -- small cost differences may be treated as zero."

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Solver reports ill-conditioned | Large coefficient range relative to tolerances | Scale data to similar magnitudes |
| Solution violates constraints | Near-zero coefficients indistinguishable from zero | Round small values to zero or rescale |
| Slow convergence | RHS values far from coefficient scales | Normalize RHS with problem scale |
| Cycling (simplex) | Degeneracy + numerics | Use perturbation or different algorithm |

### Big-M Sizing

Big-M constraints model logical implications: `x <= M * y` means "if y=0 then x=0."

**The trickle flow problem:** If M = 10^9 and feasibility tolerance is 10^-6, then y = 10^-9 (considered 0 by integrality tolerance) allows x up to 1.0, violating logical intent.

**Rules:**
1. **Always derive M from problem data** -- use the tightest valid upper bound for the constrained variable. A loose M weakens the LP relaxation and can allow trickle flow through solver tolerance interactions.
2. If the data-derived M is large relative to other formulation coefficients, consider alternatives: indicator constraints, SOS1/SOS2, or reformulation without Big-M.

| Constraint type | Calculate M as |
|----------------|----------------|
| Production if open | facility_capacity |
| Flow if arc selected | min(supply_at_source, demand_at_sink) |
| Assignment if available | 1 (for binary assignment) |
| Spending if approved | remaining_budget |

### Tolerances

| Tolerance | Typical default | Purpose |
|-----------|----------------|---------|
| Feasibility | 1e-6 | Constraint violation allowed |
| Optimality | 1e-6 | Reduced cost threshold |
| Integrality | 1e-5 | Integer variable rounding |
| MIP Gap | 1e-4 (0.01%) | Relative optimality gap |

Tightening tolerances increases solve time and may cause spurious infeasibility. Loosening tolerances may mask real issues.

**Reformulate vs. adjust tolerances:** Prefer reformulation for structural issues (bad scaling, loose Big-M, ill-conditioned geometry). Consider tolerance adjustment for marginal feasibility issues where the violation is business-acceptable.

### Additional Numerical Guidelines

- **Avoid manual rounding:** Input 1/3 as a fraction or full precision, not 0.333.
- **RHS values:** Absolute magnitude doesn't matter -- a $50M budget constraint is fine if LHS coefficients are on a similar scale. What matters is the **ratio between RHS and LHS coefficient scales within the same constraint**.
- **Objective value scale:** Compare the optimal objective value to **the domain and input data scales**, not a fixed range. If site costs are $1M-$50M but total objective is $10, the solver is barely activating anything.
- **No strict inequalities:** Solvers satisfy constraints within tolerances, so strict `<` and `>` become equivalent to `<=` and `>=`. Use weak inequalities with small epsilon if a strict bound is needed.
- **Avoid thin feasible regions:** Nearly parallel constraints create regions where small data changes cause huge solution changes. Remove near-redundant constraints.
- **Bound all variables:** Finite lower and upper bounds help solver bounding algorithms and numerical stability.

---

## Solver Log Interpretation

Solver logs contain diagnostic signals that help distinguish formulation issues from solver parameter issues. Learn to read these patterns before adjusting tolerances or increasing time limits.

**HiGHS log patterns:**
- `"Ill-conditioning detected"` — Coefficient range is too wide. Rescale data before retrying.
- `"Primal infeasible at iteration N"` with low N — Constraints are structurally conflicting, not a numerics issue. Check constraint logic.
- `"Presolve reduced to 0 variables"` — Model is trivially solved or trivially infeasible after presolve. Check that constraints aren't accidentally fixing all variables.
- `"Objective value improvement stalled"` — LP relaxation is weak. Consider disaggregated variables or valid inequalities.
- Rapidly increasing iteration count with no objective improvement — Degeneracy. Consider perturbation or reformulation.

**Gurobi log patterns:**
- `"Sub-optimal termination"` — Solver gave up before proving optimality. Check for numerical issues or increase time.
- `"Barrier convergence not met"` — Interior point method struggled. Try simplex instead, or rescale.
- Node count growing without gap improvement — LP relaxation is too weak. Tighten formulation (stronger cuts, disaggregated variables).
- `"Infeasible or unbounded"` — Run with `DualReductions=0` to disambiguate.

**MIP gap progression:**
- Best bound improves but incumbent doesn't change — Solver can't find better feasible solutions. Consider heuristic parameters or warm starts.
- Incumbent improves but best bound is static — LP relaxation is loose. Formulation tightening (cuts, extended formulations) will help more than more time.
- Both stalled — Problem may be at or near optimality. Check if the gap is acceptable for operational use.

**Ipopt log patterns:**
- `"Restoration phase"` — Solver is trying to recover feasibility. Constraints may be locally infeasible from the current starting point. Try different initial values.
- `"Number of iterations exceeded"` — Increase `max_iter` or improve starting point.
- `"Converged to locally infeasible point"` — NLP is non-convex and starting point led to an infeasible region. Try multiple random starts.

**Actionable rule:** Read the log before changing parameters. If the log says "infeasible," no amount of time will help — fix the formulation. If the log shows gap progress, more time may help.

---

## MIP Formulation Techniques

Mixed-integer problems introduce discrete decisions that create unique challenges. A good formulation can make the difference between solving in seconds vs. hours.

> **See also:** Big-M code patterns → `rai-prescriptive-problem-formulation/constraint-formulation.md` > Capacity limits and binary activation. Symmetry breaking code → `rai-prescriptive-problem-formulation/variable-formulation.md` > Symmetry breaking.

### LP Relaxation Strength

The solver starts by solving the LP relaxation (ignoring integrality). A strong LP relaxation means LP optimal is close to MIP optimal, which means less branching and faster solve.

**Strengthening techniques:**
- **Extended formulations:** Instead of `x <= M * y`, use `x <= capacity_j * y_j` for each item j
- **Disaggregated variables:** Instead of `flow[arc]`, use `flow[arc, commodity]` for multi-commodity flow
- **Valid inequalities:** Cover inequalities for set covering, clique inequalities for assignment, flow cover cuts for capacitated problems

### Symmetry Breaking

Many MIP problems have symmetry (identical facilities, workers, machines), causing the solver to explore equivalent branches.

**Ordering constraints:** If workers are identical, order their loads: `load[1] >= load[2] >= load[3]`

**Fix representative:** Assign item 1 to facility 1 to break permutation symmetry.

**Lexicographic ordering:** For matrices with symmetric rows/columns, enforce `lex_lesseq(row[i], row[i+1])`.

### Integrality Tolerance

Integer variables are stored as floating-point. A variable is "integer" if within tolerance (typically 10^-5) of an integer value.

**Post-solution processing:** Always round integer variables to nearest integer. Verify feasibility after rounding. Report rounded values, not raw solver output. For binary variables, use `x > 0.5` not `x == 1`.

### Modeling Logical Constraints

**If-then:** `if y=1, then x <= 10` becomes `x <= 10 + M*(1-y)` with Big-M, or use indicator constraints (preferred when solver supports them).

**Either-or:** `x <= 10 OR x >= 20` requires a binary variable z: `x <= 10 + M*z` and `x >= 20 - M*(1-z)`.

**At-most-K:** `sum(is_open[f]) <= K`

**Exactly-one:** `sum(assign[task, w] for w in workers) == 1` for each task.

### MIP Self-Check

- [ ] Are Big-M values as tight as possible?
- [ ] Can variables be disaggregated for stronger relaxation?
- [ ] Are there identical entities that can be ordered (symmetry breaking)?
- [ ] Are all integer bounds reasonable?
- [ ] Are Big-M values < 10^6?
- [ ] Are indicator constraints used where appropriate? (Gurobi only — use Big-M for HiGHS)
- [ ] Are SOS constraints used for piecewise linear functions? (Gurobi only — use binary variable formulations for HiGHS)

---

## Operator and Construct Compatibility by Solver

Before building a formulation, verify that the operators and constructs you plan to use are supported by the target solver. Using an unsupported construct causes a solve-time error that requires reformulation.

Operators are imported from `relationalai.semantics.std.math` (`math.abs`, `math.exp`, etc.) or are Python operators (`**`, `*`, `+`). Constructs in `()` are special-form helpers from the prescriptive library.

| Operator / Construct | HiGHS | Gurobi | Ipopt | MiniZinc |
|----------------------|-------|--------|-------|----------|
| Linear arithmetic (`+`, `-`, `*` by const, `/` by const) | Yes | Yes | Yes | Yes |
| Integer / binary variables (`type="int"`, `type="bin"`) | Yes | Yes | No (continuous only) | Yes |
| Quadratic objective (`var * var` in `minimize`/`maximize`) | Yes (convex) | Yes | Yes | No |
| Bilinear / quadratic constraints (`var * var` in `satisfy`) | No (linearize) | Yes (convex) | Yes | Yes (discrete vars only) |
| `math.abs(x)` | No (reformulate) | Yes | Yes | Yes |
| Aggregate `min(...)` / `max(...)` over a collection (`from relationalai.semantics import min, max`) | No (reformulate) | Yes (general constraints) | No (reformulate) | Yes |
| `math.exp(x)`, `math.log(x)` (and `log2`, `log10`, `natural_log`) | No | Yes | Yes | No |
| `math.sqrt(x)`, `math.cbrt(x)` | No | Yes | Yes | No |
| `x ** n` / `math.pow(x, n)` | No (n=2: linearize) | Yes | Yes | Yes (integer n) |
| `implies(...)` | No (Big-M) | Yes (indicator constraints) | N/A | Yes |
| `all_different(...)` | No | No | No | Yes |
| `special_ordered_set_type_1(...)` / `_type_2(...)` | No | Yes | No | No |

**Not supported in solver expressions** (compile-time error if used inside `solve_for`/`satisfy`/`minimize`/`maximize`): `%` (modulo), `//` (floor division), `math.floor`, `math.ceil`, `math.round`, `math.sign`, `math.clip`, `math.minimum(x, y)` / `math.maximum(x, y)` (pairwise — use the aggregate `min`/`max` row above instead), trig (`math.sin`/`cos`/`tan` and their hyperbolic/inverse variants — including `math.degrees`/`math.radians`/`math.haversine`), `math.factorial`, `math.erf`/`math.erfinv`, division between two decision variables. (These are common examples; the prescriptive wire format's authoritative list of supported operators is `_OP_CODES` in `relationalai.semantics.reasoners.prescriptive.wire_format` — anything not in that list does not lower to the solver.) Use piecewise-linear approximations or reformulations for unsupported operators.

**Decision rule:** If the problem needs nonlinear functions (`math.exp`, `math.log`, `math.sqrt`, `x**n`) → Gurobi (preferred when licensed) or Ipopt. If it needs `all_different(...)` or complex logical constraints → MiniZinc. If it needs integer variables with quadratic terms → Gurobi. For pure linear/MIP → HiGHS (default) or Gurobi.

**Before solving:** Check that every expression in the formulation uses only operators supported by the selected solver. If not, either switch solvers or apply a reformulation technique (see below).

---

## Reformulation Techniques for Solver Compatibility

When a formulation uses constructs unsupported by the target solver, reformulate rather than switch solvers (which may lose other capabilities like integrality).

### Product of binary x continuous → McCormick / Big-M linearization

Replace `z = x * y` (where x is binary, y is continuous with bounds [L, U]) with:
- `z <= U * x`
- `z >= L * x`
- `z <= y - L * (1 - x)`
- `z >= y - U * (1 - x)`

This is exact — no approximation. Requires known bounds on y.

### Absolute value → auxiliary variable + two constraints

Replace `minimize abs(x)` with auxiliary variable `t >= 0`:
- `t >= x`
- `t >= -x`
- Minimize `t` instead

For `abs(x) <= K`: add `x <= K` and `x >= -K`.

### Min / max → epigraph reformulation

Replace `z = min(x1, x2, ..., xn)` with:
- `z <= x_i` for all i
- Maximize `z` (or let it be pushed down by other constraints)

Replace `z = max(x1, x2, ..., xn)` with:
- `z >= x_i` for all i
- Minimize `z` (or let it be pushed up)

### Logical implication in MIP → Big-M

For "if y=1 then x <= b" (where y is binary):
- `x <= b + M * (1 - y)` where M is the tightest valid upper bound on (x - b)

For "if y=0 then x = 0" (indicator):
- `x <= M * y` and `x >= -M * y` (if x can be negative)

Prefer indicator constraints when solver supports them (Gurobi, MiniZinc) — they are numerically superior to Big-M.

### Piecewise linear → SOS2

For `y = f(x)` where f is piecewise linear with breakpoints `x_0, ..., x_k`:
- Introduce weights `w_0, ..., w_k` with SOS2 constraint (at most 2 adjacent nonzero)
- `x = sum(w_i * x_i)`, `y = sum(w_i * f(x_i))`, `sum(w_i) = 1`

### Floor / ceil on decision variables → integer variable

Replace `y = floor(x)` with integer variable `y` and constraints:
- `y <= x` and `y >= x - 1 + epsilon`

### Nonlinear + integer → decomposition

If the problem mixes nonlinear functions with integer variables:
1. **Gurobi** handles quadratic, `exp`, `log`, `sqrt`, and general `x**n` nonlinearity natively alongside integer/binary variables — preferred when licensed.
2. For nonlinear shapes Gurobi doesn't handle: decompose into an outer integer master problem (HiGHS/Gurobi) and inner NLP subproblem (Ipopt), solved iteratively. Ipopt itself does NOT handle integer variables.
3. Alternative: linearize the nonlinear part (piecewise linear approximation) and solve as MIP.

---
