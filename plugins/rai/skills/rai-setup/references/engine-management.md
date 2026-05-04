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

### SQL stored procedures (canonical fallback)

The CLI and Python clients are thin wrappers over `RELATIONALAI.API.*` stored procedures. These procedures are the canonical interface — useful directly from notebooks/SQL worksheets, and the right fallback when the CLI version trails the backend on a new flag or size. See [Manage compute resources](https://docs.relational.ai/manage/compute-resources/) for the full reference.

| Procedure / view | Purpose |
|---|---|
| `RELATIONALAI.API.CREATE_REASONER(type, name, size, settings_json)` | Create a reasoner. The async variant `CREATE_REASONER_ASYNC` returns immediately and is the SDK's default code path — poll `GET_REASONER` for `STATUS=READY`. |
| `RELATIONALAI.API.GET_REASONER(type, name)` | Read reasoner state — `STATUS`, `SIZE`, `RUNTIME`, `SETTINGS`, `AUTO_SUSPEND_MINS`, … |
| `RELATIONALAI.API.SUSPEND_REASONER(type, name)` | Suspend (synchronous). |
| `RELATIONALAI.API.RESUME_REASONER_ASYNC(type, name)` | Submit resume; returns immediately — poll `GET_REASONER`. |
| `RELATIONALAI.API.DELETE_REASONER(type, name)` | Delete (synchronous). |
| `RELATIONALAI.API.ALTER_REASONER_AUTO_SUSPEND_MINS(type, name, n)` | Change auto-suspend threshold. |
| `RELATIONALAI.API.ALTER_REASONER_POOL_NODE_LIMITS(type, name, min, max)` | Configure compute-pool `MIN_NODES` / `MAX_NODES`. |
| `RELATIONALAI.API.GET_JOB(type, id)` | Fetch metadata for one job. |
| `RELATIONALAI.API.CANCEL_JOB(type, id)` | Cancel an active job. |
| `RELATIONALAI.API.REASONERS` (view) | All reasoners — equivalent of `rai reasoners:list`. |
| `RELATIONALAI.API.JOBS` (view) | Job ledger — `ID`, `STATE`, `JOB_TYPE`, `PAYLOAD`, `CREATED_ON`, … Filter by `STATE IN ('QUEUED','RUNNING')` for active jobs. |

The `type` argument is the canonical reasoner family — `'logic'` or `'prescriptive'`. SDK code paths in `relationalai/services/reasoners/gateways.py` invoke exactly these procs.

#### Async + poll pattern

`CREATE_REASONER_ASYNC` and `RESUME_REASONER_ASYNC` return as soon as the operation is queued — the reasoner is not yet `READY`. Loop on `GET_REASONER` until `STATUS='READY'`:

```sql
-- 1. Submit creation
CALL RELATIONALAI.API.CREATE_REASONER_ASYNC('logic', 'my_logic', 'HIGHMEM_X64_M', PARSE_JSON('{}'));

-- 2. Poll until READY (every 5–10 s; PROVISIONING → READY typically takes 1–3 minutes)
CALL RELATIONALAI.API.GET_REASONER('logic', 'my_logic');
-- Repeat until STATUS=READY (or stop on FAILED / ERROR)
```

The `settings_json` argument carries the same dict accepted by the Python client — `{"auto_suspend_mins": 30, "await_storage_vacuum": true, "settings": {...}}`. Empty `PARSE_JSON('{}')` accepts all defaults.

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
