## Engine Management

Two interfaces manage engines/reasoners: the `rai reasoners:*` CLI (operational one-liners) and the Python `Resources` class / `connect_sync()` client (scriptable). Each engine has a **name** and a **type** (`LOGIC`, `SOLVER`, `PREDICTIVE` in the Python API; `Logic`, `Prescriptive`, `Predictive` in the CLI — `SOLVER` ↔ `Prescriptive`). Multiple engine types can share the same name.

### CLI (`rai reasoners:*`)

All commands accept `--type` (`Logic` / `Prescriptive` / `Predictive`) and `--name`. Both are optional — interactive prompts fill missing values.

| Command | Purpose |
|---|---|
| `rai reasoners:create --type Logic --name <name> --size <size>` | Create a reasoner. Add `--await-storage-vacuum` to block until storage is ready. |
| `rai reasoners:delete --type Logic --name <name>` | Delete a reasoner |
| `rai reasoners:suspend --type Logic --name <name>` | Suspend (stop billing) |
| `rai reasoners:resume --type Logic --name <name>` | Resume a suspended reasoner |
| `rai reasoners:list` | List all reasoners (filterable by `--type`, `--name`, `--size`, `--state`) |
| `rai reasoners:get --type Logic --name <name>` | Get details for one reasoner |
| `rai reasoners:alter --type Logic --name <name> --auto-suspend-mins <N>` | Change settings (e.g. `auto_suspend_mins`) |

**Resize pattern:** No in-place resize — delete and recreate: `suspend` → `delete` → `create` with the new size.

### Python API — `Resources`

Operational engine management uses the `Resources` class.

#### Setup

```python
from relationalai import Resources
r = Resources()  # auto-discovers raiconfig.yaml / raiconfig.toml
```

#### List Engines

```python
engines = r.list_engines()
# Returns list of dicts with keys: name, id, type, size, state, created_by,
#   created_on, updated_on, auto_suspend_mins, suspends_at, settings
for e in engines:
    print(f"{e['name']} | type={e['type']} | size={e['size']} | state={e['state']}")
```

Engine states: `READY`, `SUSPENDED`, `PROVISIONING`, `DELETING`, `ERROR`.

#### Create Engine

```python
r.create_engine(
    name="my_engine",
    type="LOGIC",              # required: "LOGIC", "SOLVER", or "PREDICTIVE"
    size="HIGHMEM_X64_S",      # optional, defaults from config
    auto_suspend_mins=30,      # optional
)
```

#### Delete Engine

```python
r.delete_engine(name="my_engine", type="LOGIC")  # type is required
```

#### Get Engine Status

```python
info = r.get_engine(name="my_engine", type="LOGIC")  # type is required
```

#### Resume / Suspend Engine

```python
r.resume_engine(name="my_engine")
r.suspend_engine(name="my_engine")
# Async variants: r.resume_engine_async(), r.create_engine_async()
```

#### Common Pattern: Delete and Recreate

Useful when an engine is in a bad state or needs a clean restart:

```python
r = Resources()
engine_name = r.config.get("engine")
engine_size = r.config.get("engine_size")

r.delete_engine(engine_name, "LOGIC")
r.create_engine(engine_name, "LOGIC", size=engine_size, auto_suspend_mins=30)
```

#### Engine Types and Naming

A single engine name (e.g., `prescriptive_assistant`) typically has **two** engines:
- **LOGIC** — runs model rules, queries, data loading
- **SOLVER** — runs optimization solves (HiGHS, MiniZinc, Ipopt, Gurobi)

These are independent — deleting one does not affect the other.

### `connect_sync()` Client API

The newer `connect_sync()` client provides typed methods for reasoner management alongside the `Resources` class:

```python
from relationalai.client import connect_sync

with connect_sync() as client:
    # Create a reasoner (blocks until READY)
    client.reasoners.create_ready(
        "Logic", "my_reasoner",
        reasoner_size="HIGHMEM_X64_S",
        auto_suspend_mins=60,
    )

    # List, get, suspend, resume, delete
    client.reasoners.list()
    client.reasoners.get("Logic", "my_reasoner")
    client.reasoners.suspend("Logic", "my_reasoner")
    client.reasoners.resume_ready("Logic", "my_reasoner")
    client.reasoners.delete("Logic", "my_reasoner")

    # Job monitoring
    jobs = client.jobs.list("Logic", name="my_reasoner")
    job = client.jobs.get("Logic", "<job_id>")
    client.jobs.cancel("Logic", "<job_id>")
```

### Warm Reasoners

Warm reasoners are pre-provisioned reasoners kept running and ready to accept jobs immediately, eliminating cold-start latency. When a user creates or resumes a reasoner and a warm instance is available for the requested size, the system assigns the warm reasoner instead of provisioning a new one.

> **Note:** Unwarmed logic-reasoner cold-start compounds with per-table CDC stream sync on first model query, producing a 5–10 minute `Initializing data index` hang. See `rai-build-starter-ontology` § Common Pitfalls for the full row.

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
