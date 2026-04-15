# Solver Details

## Problem Size Guidelines

| Size | Variables | Constraints | Notes |
|------|-----------|-------------|-------|
| Small | < 1,000 | < 1,000 | Any formulation usually tractable |
| Medium | 1K - 100K | 1K - 100K | Formulation quality matters |
| Large | > 100K | > 100K | May need decomposition |

Each binary variable can double the search space. Tight bounds on integers reduce branching. Always ask: is integer truly required, or is rounding acceptable?

## Problem Initialization

In v1, pass the solver name as a string directly to `problem.solve()` — no separate `Solver` object needed. `Problem` initialization uses type references, not strings:

```python
from relationalai.semantics import Float, Integer

problem = Problem(model, Float)    # LP, NLP, MIP with continuous relaxation
problem = Problem(model, Integer)  # Pure integer / constraint programming

# Solver choice depends on problem type AND user license:
problem.solve("highs", time_limit_sec=60)    # LP/MIP (open-source)
problem.solve("gurobi", time_limit_sec=60)   # LP/MIP/QP/QCP (license required)
problem.solve("minizinc", time_limit_sec=60) # CP (open-source)
problem.solve("ipopt", time_limit_sec=60)    # NLP (open-source)
```

**Do not default to any single solver.** Always select based on the problem type (see Decision Rules above) and confirm the user has the required license (Gurobi is commercial). The second argument (`Float` or `Integer`) sets the default numeric type. Variables can override with `type="bin"`, `type="int"`, or `type="cont"` in `solve_for()`.
