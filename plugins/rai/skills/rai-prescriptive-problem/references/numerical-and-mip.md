<!-- TOC -->
- [Operator and Construct Compatibility by Solver](#operator-and-construct-compatibility-by-solver)
- [Reformulation Techniques for Solver Compatibility](#reformulation-techniques-for-solver-compatibility)
  - [Logical implication in MIP → Big-M](#logical-implication-in-mip--big-m)
<!-- /TOC -->

## Operator and Construct Compatibility by Solver

Before building a formulation, verify that the operators and constructs you plan to use are supported by the target solver. Using an unsupported construct causes a solve-time error that requires reformulation.

Operators are imported from `relationalai.semantics.std.math` (`math.abs`, `math.exp`, etc.) or are Python operators (`**`, `*`, `+`). Constructs shown as `name(...)` (e.g., `implies(...)`, `all_different(...)`) are special-form helpers from the prescriptive library.

| Operator / Construct | HiGHS | Gurobi | Ipopt | MiniZinc |
|----------------------|-------|--------|-------|----------|
| Linear arithmetic (`+`, `-`, `*` by const, `/` by const) | Yes | Yes | Yes | Yes |
| Integer / binary variables (`type="int"`, `type="bin"`) | Yes | Yes | No (continuous only) | Yes |
| Quadratic objective (`var * var` in `minimize`/`maximize`) | Yes (convex) | Yes | Yes | No |
| Bilinear / quadratic constraints (`var * var` in `satisfy`) | No (linearize) | Yes (convex) | Yes | Yes (discrete vars only) |
| `math.abs(x)` | No (reformulate) | Yes | Yes | Yes |
| Aggregate `min(...)` / `max(...)` over a collection (`from relationalai.semantics import min, max`) | No (reformulate) | Yes (general constraints) | No (reformulate) | Yes |
| `math.exp(x)`, `math.log(x)` (and `math.log2`, `math.log10`, `math.natural_log`) | No | Yes | Yes | No |
| `math.sqrt(x)`, `math.cbrt(x)` | No | Yes | Yes | No |
| `x ** n` / `math.pow(x, n)` | No (n=2: linearize) | Yes | Yes | Yes (integer n) |
| `implies(...)` | Bounded variables only (rewritten to big-M) | Yes (indicator constraints) | N/A | Yes |
| `all_different(...)` | No | No | No | Yes |
| `special_ordered_set_type_1(...)` / `_type_2(...)` | Bounded variables only (rewritten to binaries) | Yes | No | Bounded variables only |

**Not supported *on a decision variable*.** Every operator below raises `NotImplementedError` when its argument depends on a decision variable inside `solve_for`/`satisfy`/`minimize`/`maximize`, verified against `relationalai` 1.30.3: `%` (modulo), `//` (floor division), `math.floor`, `math.ceil`, `math.round`, `math.sign`, `math.clip`, `math.minimum(x, y)` / `math.maximum(x, y)` (pairwise, use the aggregate `min`/`max` row above instead), trig (`math.sin`/`cos`/`tan` and their hyperbolic/inverse variants, including `math.degrees`/`math.radians`), `math.factorial`, `math.erf`/`math.erfinv`. These are the common cases, not an exhaustive list.

**The same call over data alone is fine**, because it is evaluated into a coefficient before the solver sees it: `math.floor(Site.demand) * Site.x` is accepted and renders `0.0 * x_1 <= 5.0` for a demand of 0.7, and `math.asin(Site.lat) * Site.x` renders `0.775397496610753 * x_1 <= 5.0`. Only the decision-variable form raises. So a rejection here means "move this arithmetic to the data side", not "this function is unusable".

The message names an operator, but not always the one you wrote: it may name an internal operator the expression decomposes to, as `math.clip` reports `maximum`. It comes in two forms — "not supported in prescriptive problem expressions", or "not supported by the solver engine" followed by a list of supported operators. That list is the first-order and comparison set the prescriptive compiler accepts, not everything the solver supports: aggregates such as `sum` and `count` are absent from it and are still valid.

**`math.haversine` is wrong at the source — do not use it anywhere, in a formulation or in a plain query.** It passes its coordinate term into the *result* field of the binary `*` relation rather than multiplying by it, so the expression it builds means `2 * radius = asin(sqrt(...))`. Nothing raises, and what you get back depends on the execution path:

- **Deploy Mode (SQL):** `2 * radius` for every input. `haversine(0, 0, 0, 0, 6371)` returns `12742.0` instead of `0.0` — a plausible-looking distance, which is the dangerous case.
- **Default `Model(...)` (LQP):** `NaN` for every input, keyword or positional radius, constant or property coordinates.
- **Inside a `Problem`:** a decision variable as `radius=` renders the constraint as `2.0 * x_1 <= 5.0`; one as a *coordinate* raises `ValueError: Expression does not reference any decision variables`, which is not a `solve_for` wiring bug; and with no decision variable in the call the family grounds **0 rows** where an otherwise identical `2.0 * x` control grounds 2.

Precomputing the distance with `model.define()` does not rescue it, because the function itself is wrong. Build great-circle distance from `asin`, `sqrt`, `sin` and `cos` over the coordinate *data* — `asin(sqrt(sin(Site.lat))) * x` grounds — or ingest the distances as data. Those functions raise if you apply them to a decision variable instead.

**Division between two decision variables is not on either list.** It compiles and renders (`a_1 / b_1 <= 5.0`), so whether it is usable is a target-solver question rather than a compile-time one. The table above has no row for it: treat it as nonlinear and confirm against the target solver's own documentation before relying on it.

Use piecewise-linear approximations or reformulations for unsupported operators.

**Decision rule:** If the problem needs nonlinear functions (`math.exp`, `math.log`, `math.sqrt`, `x**n`) → Gurobi (preferred when licensed) or Ipopt. If it needs `all_different(...)` or complex logical constraints → MiniZinc. If it needs integer variables with quadratic terms → Gurobi. For pure linear/MIP → HiGHS (default) or Gurobi.

**Before solving:** Check that every expression in the formulation uses only operators supported by the selected solver. If not, either switch solvers or apply a reformulation technique (see below).

---

## Reformulation Techniques for Solver Compatibility

When the target solver rejects a construct in the table above, reformulate rather than switch solvers (a switch may lose integrality or another capability). The standard linearizations apply: an auxiliary variable for `math.abs` or aggregate `min`/`max`, McCormick for a binary × bounded-continuous product in a constraint, an integer variable `y` with `x - 1 + ε <= y <= x` for `math.floor` of a decision variable (`math.floor` itself raises on every solver; ε stands in for a strict `<`, so the encoding is exact only when `x` cannot fall within ε below an integer, such as `x = n / N` for integer `n`, positive integer `N` and `0 < ε <= 1 / N`), integers `q` and `r` with `x == k * q + r` and `0 <= r <= k - 1` for `x // k` (`q`) and `x % k` (`r`) with integer `x` and a positive integer constant `k`, and piecewise-linear segments for `exp`/`log`/`sqrt` on HiGHS. Ipopt has no integer variables and, of the four solvers, only Gurobi takes `exp`/`log`/`sqrt` alongside them, so without Gurobi a nonlinear MIP must be linearized.

### Logical implication in MIP → Big-M

For "if `y = 1` then `x <= b`" with `y` binary: `x <= b + M * (1 - y)`; for "if `y = 0` then `x = 0`": `x <= M * y` (add `x >= -M * y` if `x` can be negative). Derive `M` from data as the tightest valid bound (facility capacity, remaining budget, `min(supply, demand)` on an arc): a loose `M` weakens the relaxation, and with `M = 1e9` a `y` of `1e-9`, zero within integrality tolerance, lets `x` reach 1. Where the target solver takes `implies(...)` (see the table), prefer it to a hand-written Big-M. PyRel Big-M code: [constraint-formulation.md](constraint-formulation.md) > Capacity limits and binary activation.
