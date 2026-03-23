---
name: rai-configuration
description: Covers PyRel v1 configuration including raiconfig.yaml, connection setup, programmatic config, model and reasoner settings, and engine management. Use when setting up or troubleshooting RAI connections and configuration.
---

# Configuration
<!-- v1-SENSITIVE -->

## Summary

**What:** PyRel v1 configuration — config files, connection setup, authentication, model settings, and reasoner settings.

**When to use:**
- Setting up a new project (raiconfig.yaml)
- Configuring Snowflake connections
- Choosing an authentication method (username/password, JWT, OAuth, PAT, browser)
- Tuning reasoner engine sizes or solver settings
- Troubleshooting connection or config errors

**When NOT to use:**
- Model creation or PyRel syntax (concepts, properties, data loading) — see `rai-pyrel-coding`
- Solver execution and diagnostics — see `rai-prescriptive-solver-management`

**Overview:** Reference skill. Key lookup areas: Config File (raiconfig.yaml structure), Connection Setup (Snowflake auth methods), Programmatic Config (create_config), Model Settings, Reasoner Settings (engine sizes, per-reasoner options).

---

## Installation

```bash
pip install relationalai>=1.0.3
```

Requires Python 3.10+.

---

## Quick Reference

```yaml
# Minimal Snowflake config (raiconfig.yaml)
default_connection: sf
connections:
  sf:
    type: snowflake
    authenticator: username_password
    account: my_account
    warehouse: my_warehouse
    user: my_user
    password: ${SNOWFLAKE_PASSWORD}
```

```python
# Programmatic config (no YAML file needed)
from relationalai.config import create_config
from relationalai.semantics import Model
config = create_config(connection_type="snowflake")
model = Model("my_model", config=config)
```

**Verify connectivity:** Run `rai connect` to check the connection before writing model code. Also use it to validate after changing any connection-related configuration.

---

## Configuration File

**Primary file:** `raiconfig.yaml` (also accepts `raiconfig.yml`). TOML (`raiconfig.toml`) is deprecated with a warning.

**Auto-discovery:** `create_config()` walks upward from CWD to find the config file.

**Full YAML structure:**

```yaml
default_connection: sf
active_profile: dev          # or set RAI_PROFILE env var

connections:
  sf:
    type: snowflake
    authenticator: username_password
    account: my_account
    warehouse: my_warehouse
    user: my_user
    password: ${SNOWFLAKE_PASSWORD}    # env var substitution
    role: my_role                      # optional
    database: my_database              # optional
    schema: my_schema                  # optional

reasoners:
  backend: sql                         # "sql" (default) or "direct_access"
  logic:
    size: HIGHMEM_X64_S
    use_lqp: true
    emit_constraints: false
  predictive:
    size: HIGHMEM_X64_S
  prescriptive:
    size: HIGHMEM_X64_S

data:
  wait_for_stream_sync: true           # wait for streams before queries (default true)
  data_freshness_mins: 5               # allow queries if data is within N mins (default unset = must be fully synced; max 30240 = 3 weeks)
  query_timeout_mins: 10               # client-side timeout (default unset = no timeout)
  ensure_change_tracking: false        # auto-enable change tracking on tables read (default false; requires OWNERSHIP)
  check_column_types: true             # validate column types on load (default true)
  download_url_type: external          # "internal" (default) or "external" (accessible outside Snowflake)

compiler:
  strict: false
  soft_type_errors: false

model:
  schema: analytics                    # install schema for SQL views/tables
  implicit_properties: true            # allow undeclared properties on first access
  keep: true
  isolated: true

execution:
  metrics: false                       # collect SDK timing/counter metrics (default false)
  logging: false                       # emit structured execution logs to Python logger (default false)
  retries:
    enabled: false
    max_attempts: 3                    # total attempts including first try
    base_delay_s: 0.25
    max_delay_s: 5.0
    jitter: 0.2                        # random jitter fraction added to each delay

debug:
  show_full_traces: false

profile:
  dev:
    connections:
      sf:
        warehouse: dev_warehouse
  prod:
    connections:
      sf:
        warehouse: prod_warehouse
```

**Environment variable syntax:** Use `${VAR_NAME}` in any string value.

**Profile overlays:** Profile selection priority (highest wins): `create_config(active_profile=...)` > `RAI_PROFILE` env var > `active_profile` in YAML. The selected profile's values merge on top of the base config.

**Fallback sources** (when no `raiconfig.yaml` found): `raiconfig.toml` (deprecated) -> `~/.snowflake/config.toml` -> `~/.dbt/profiles.yml`.

**Transition note (as of Feb 2026):** New features (install mode, SQL backend) require `raiconfig.yaml`. However, the old code path still looks for `raiconfig.toml` — a minimal dummy toml may be needed alongside yaml during the transition. When both files are present, toml may take precedence in some code paths. This is being fixed upstream.

---

## Connection Setup

### Snowflake Authentication Methods

Six authenticators, selected via the `authenticator` field:

| Authenticator | Class | Key Fields |
|---|---|---|
| `username_password` (default) | `UsernamePasswordAuth` | `user`, `password` |
| `username_password_mfa` | `UsernamePasswordMFAAuth` | `user`, `password` |
| `externalbrowser` | `ExternalBrowserAuth` | `user` |
| `jwt` | `JWTAuth` | `user`, `private_key_path` or `private_key` |
| `oauth` | `OAuthAuth` | `token` |
| `programmatic_access_token` | `ProgrammaticAccessTokenAuth` | `token` |

All Snowflake authenticators share: `account`, `warehouse`, and optional `role`, `database`, `schema`.

### Active Session Auto-Detection (SPCS / Snowflake Notebooks)

When running inside Snowflake (notebooks, stored procedures, UDFs), PyRel auto-detects the active Snowpark session. No config file needed -- `create_config()` returns a `ConfigFromActiveSession` that wraps `get_active_session()`.

---

## Programmatic Configuration

```python
from relationalai.config import create_config
```

### Auto-Discovery (no args)

```python
cfg = create_config()  # finds raiconfig.yaml walking up from CWD
```

### Programmatic with Dicts

```python
import os
cfg = create_config(
    connections={
        "sf": {
            "type": "snowflake",
            "authenticator": "username_password",
            "account": os.environ["SNOWFLAKE_ACCOUNT"],
            "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
        }
    },
    default_connection="sf",
    reasoners={"logic": {"size": "HIGHMEM_X64_S"}},
)
```

### Typed Connection Objects

```python
from relationalai.config import create_config, UsernamePasswordAuth

cfg = create_config(
    connections={
        "sf": UsernamePasswordAuth(
            account="my_account",
            warehouse="my_warehouse",
            user="my_user",
            password="my_password",
        )
    }
)
```

### Getting Sessions from Config

```python
session = cfg.get_session()                              # default connection
session = cfg.get_session(SnowflakeConnection)           # typed, default
conn = cfg.get_connection(SnowflakeConnection, name="sf") # by name

# Or from the model (session is lazy — triggers on first job):
m = Model("MyModel")
session = m.config.get_session()          # get session from model
session.sql("SELECT 1").collect()         # verify connection works

# Force a fresh session (e.g., after rotating credentials):
conn = m.config.get_default_connection()
conn.clear_session_cache()
```

---

## Model Configuration

### Basic Model Creation

```python
from relationalai.semantics import Model

# Auto-discovers raiconfig.yaml
model = Model("my_model")

# Explicit config
model = Model("my_model", config=cfg)
```

### Model-Level Config Fields

Set in `raiconfig.yaml` under `model:` or pass via `create_config(model={...})`:

| Field | Default | Purpose |
|---|---|---|
| `schema` | `None` | Install schema for SQL views/tables |
| `implicit_properties` | `true` | Allow undeclared properties on first access |
| `keep` | `true` | Keep model after execution |
| `isolated` | `true` | Run model in isolated mode |

---

## Reasoner Configuration

### Backend Selection

```yaml
reasoners:
  backend: sql              # default -- uses Snowpark SQL
  # backend: direct_access  # HTTP-based; requires direct_access_base_url (mandatory when using direct_access)
  # direct_access_base_url: https://reasoners.example.com
```

### Engine Sizes

| Platform | Valid Sizes |
|---|---|
| AWS | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_L` |
| Azure | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_SL` |

### Per-Reasoner Settings

```yaml
reasoners:
  logic:
    size: HIGHMEM_X64_S
    use_lqp: true                    # LQP for rule execution (default true)
    emit_constraints: true           # emit constraint reports
    incremental_maintenance: "off"   # "on", "auto", or "off"
    lqp:
      semantics_version: "1"         # opt into hard validation errors
  predictive:
    size: HIGHMEM_X64_S
  prescriptive:
    size: HIGHMEM_X64_S
```

> **Note:** `auto_suspend_mins` and `await_storage_vacuum` are managed via the CLI only — they are not config fields.
> - Set auto-suspend after creation: `rai reasoners:alter --type logic --name <name> --auto-suspend-mins <value>`
> - Set await-storage-vacuum at creation time: `rai reasoners:create --type logic --name <name> --size <size> --await-storage-vacuum`

### Polling Configuration

Controls how aggressively the client polls for long-running operations:

```yaml
reasoners:
  poll_initial_delay_s: 0.05
  poll_overhead_rate: 0.2        # +20% per poll (exponential backoff)
  poll_max_delay_s: 2.0
```

### Programmatic Reasoner Config

```python
cfg = create_config(
    connections={"sf": {...}},
    reasoners={
        "backend": "sql",
        "logic": {
            "size": "HIGHMEM_X64_M",
            "use_lqp": True,
            "emit_constraints": True,
        },
        "prescriptive": {
            "size": "HIGHMEM_X64_L",
        },
    },
)
```

---

## Execution Configuration

Controls SDK-level behavior: observability, retries, compiler strictness, and data loading defaults.

### Metrics and Logging

```python
# View collected metrics after running a query
from relationalai.client import connect_sync
client = connect_sync()
m = Model("MyModel")
m.select("hello world").to_df()
print(client.execution_metrics.counters)
print(client.execution_metrics.timings_ms)

# Enable structured logs (configure Python logging to display output)
import logging
logging.getLogger("relationalai.client.execution").setLevel(logging.INFO)
```

Enable both in `raiconfig.yaml`:
```yaml
execution:
  metrics: true
  logging: true
```

### Retries

Automatic re-attempts on transient failures. `max_attempts` is the total count including the first try:

```yaml
execution:
  retries:
    enabled: true
    max_attempts: 5
    base_delay_s: 0.25
    max_delay_s: 5.0
    jitter: 0.2
```

### Compiler Strictness

```yaml
compiler:
  strict: true           # fail fast on ambiguous types — recommended for CI/production
  soft_type_errors: true # treat type errors as warnings — use in notebooks only
```

Use `strict: true` in CI. Use `soft_type_errors: true` only during rapid iteration — it hides real type problems.

### Data Loading Defaults

```yaml
data:
  wait_for_stream_sync: true      # wait for streams to sync before queries (default: true)
  data_freshness_mins: 5          # allow queries if data is within N mins (default: unset = fully synced; max 30240 = 3 weeks)
  query_timeout_mins: 10          # client-side timeout in minutes (default: unset = no timeout)
  ensure_change_tracking: false   # auto-enable change tracking on tables (requires OWNERSHIP; default: false)
  check_column_types: true        # validate column types on load (default: true — keep enabled in CI)
  download_url_type: internal     # "internal" (default) or "external" (for access outside Snowflake)
```

**Caution:** `check_column_types: false` speeds up loading but silently allows type mismatches. `ensure_change_tracking: true` modifies tables — only enable if you have OWNERSHIP.

---

## Engine Management

Use the `Resources` class to list, create, delete, resume, and suspend engines. Each engine has a name and a type (`LOGIC`, `SOLVER`, or `PREDICTIVE`). A typical deployment has both a LOGIC and a SOLVER engine under the same name — they are independent.

See [engine-management.md](references/engine-management.md) for full API reference, engine states, and the delete-and-recreate pattern.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `raiconfig.yaml` not found | File not in CWD or any parent directory | Place `raiconfig.yaml` in project root; `create_config()` walks upward from CWD |
| First invalid config raises error with no fallback | PyRel validates the first source found; if invalid it stops | Fix the file — it does not fall back to lower-priority sources after a parse error |
| `direct_access` with no `direct_access_base_url` | URL is required when `backend: direct_access` | Set `reasoners.direct_access_base_url` or switch to `backend: sql` |
| `execution.logging: true` produces no output | Python logging must be configured separately | Add `logging.getLogger("relationalai.client.execution").setLevel(logging.INFO)` |
| Auth fails with `externalbrowser` in CI | Browser auth requires interactive session | Use `jwt` or `username_password` for non-interactive environments |
| Both `raiconfig.toml` and `.yaml` present | Toml may take precedence in some code paths | Remove `.toml` and use `.yaml` as canonical |
| Engine not provisioned | Reasoner config references an engine size not available on account | Check `reasoners.prescriptive.size` matches available sizes for your platform |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Engine management | Engine provisioning, sizing, and lifecycle management | [engine-management.md](references/engine-management.md) |
