## Engine Management

Operational engine management uses the `Resources` class. Each engine has a **name** and a **type** (`LOGIC`, `SOLVER`, `PREDICTIVE`). Multiple engine types can share the same name.

### Setup

```python
from relationalai import Resources
r = Resources()  # auto-discovers raiconfig.yaml / raiconfig.toml
```

### List Engines

```python
engines = r.list_engines()
# Returns list of dicts with keys: name, id, type, size, state, created_by,
#   created_on, updated_on, auto_suspend_mins, suspends_at, settings
for e in engines:
    print(f"{e['name']} | type={e['type']} | size={e['size']} | state={e['state']}")
```

Engine states: `READY`, `SUSPENDED`, `PROVISIONING`, `DELETING`, `ERROR`.

### Create Engine

```python
r.create_engine(
    name="my_engine",
    type="LOGIC",              # required: "LOGIC", "SOLVER", or "PREDICTIVE"
    size="HIGHMEM_X64_S",      # optional, defaults from config
    auto_suspend_mins=30,      # optional
)
```

### Delete Engine

```python
r.delete_engine(name="my_engine", type="LOGIC")  # type is required
```

### Get Engine Status

```python
info = r.get_engine(name="my_engine", type="LOGIC")  # type is required
```

### Resume / Suspend Engine

```python
r.resume_engine(name="my_engine")
r.suspend_engine(name="my_engine")
# Async variants: r.resume_engine_async(), r.create_engine_async()
```

### Common Pattern: Delete and Recreate

Useful when an engine is in a bad state or needs a clean restart:

```python
r = Resources()
engine_name = r.config.get("engine")
engine_size = r.config.get("engine_size")

r.delete_engine(engine_name, "LOGIC")
r.create_engine(engine_name, "LOGIC", size=engine_size, auto_suspend_mins=30)
```

### Engine Types and Naming

A single engine name (e.g., `prescriptive_assistant`) typically has **two** engines:
- **LOGIC** — runs model rules, queries, data loading
- **SOLVER** — runs optimization solves (HiGHS, MiniZinc, Ipopt, Gurobi)

These are independent — deleting one does not affect the other.

### Warm Reasoners

Warm reasoners are pre-provisioned reasoners kept running and ready to accept jobs immediately, eliminating cold-start latency. When a user creates or resumes a reasoner and a warm instance is available for the requested size, the system assigns the warm reasoner instead of provisioning a new one.

**Enable a warm reasoner** (requires `app_admin` application role):

```sql
CALL relationalai.app.enable_warm_reasoner('<type>', '<instance_family>');
-- type: 'logic', 'prescriptive', or 'predictive'
-- instance_family: compute pool size, e.g. 'HIGHMEM_X64_S'
```

Example for prescriptive workloads:

```sql
CALL relationalai.app.enable_warm_reasoner('prescriptive', 'HIGHMEM_X64_S');
```

When a warm reasoner is assigned to a user, a replacement is automatically created to maintain capacity. Use `app.set_warm_reasoners()` to configure multiple warm reasoners per size.

**Trade-off:** Warm reasoners consume compute resources continuously and incur charges on consumption-based plans. Use them when cold-start latency is a bottleneck (e.g., interactive workflows, demos).
