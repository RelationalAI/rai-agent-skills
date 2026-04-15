## Migration from v0.13

### Config File

```
raiconfig.toml  -->  raiconfig.yaml
```

### Model Creation

```python
# v0.13
model = Model(f"name_{time_ns()}", config=config, use_lqp=False)

# v1
model = Model("name")          # auto-discovers config
model = Model("name", config=cfg)  # explicit config; use_lqp is in config now
```

### Problem Creation

```python
# v0.13
from relationalai.semantics.reasoners.optimization import SolverModel, Solver
s = SolverModel(model, "cont", use_pb=True)

# v1
from relationalai.semantics.reasoners.prescriptive import Problem
problem = Problem(model, Float)   # use_pb removed; pass Float or Integer type
```

### Solver Creation

```python
# v0.13
solver = Solver("highs", resources=model._to_executor().resources)
problem.solve(solver, time_limit_sec=60)

# v1
problem.solve("highs", time_limit_sec=60)  # pass solver name directly as string
```

### Imports

```python
# v0.13
from relationalai.semantics import Model, Concept, Property, Float, Integer
from relationalai.semantics.reasoners.optimization import SolverModel, Solver

# v1
from relationalai.semantics import Model, Float, Integer
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.config import create_config
```

### Summary of Removed Parameters

| Parameter | Location | Action |
|---|---|---|
| `use_lqp` | `Model()` | Moved to `reasoners.logic.use_lqp` in config |
| `use_pb` | `SolverModel()` / `Problem()` | Removed entirely |
| `resources` | `Solver()` | Removed; pass solver name as string to `s.solve()` |
| `strict` | `Model()` | Removed; use `model.implicit_properties: false` in `raiconfig.yaml` |
| `connection`/`session` | `Model()` | Removed; connection via config file or `create_config()` |
| `config` as positional | `Model()` | Still accepted as keyword, or auto-discovered |
