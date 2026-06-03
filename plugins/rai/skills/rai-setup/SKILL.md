---
name: rai-setup
description: Setup and configuration for RelationalAI — first-time install walkthrough and all raiconfig.yaml tuning. Use when installing RAI, connecting to Snowflake, running RAI locally on DuckDB for development, or editing raiconfig.yaml. Not for writing PyRel model code (see rai-pyrel-coding) or solver usage and diagnostics (see rai-prescriptive-solver-management).
---

# RelationalAI Setup & Configuration
<!-- v1-SENSITIVE -->

Covers the [relationalai Python package](https://pypi.org/project/relationalai) (aka PyRel), which enables PyRel programs and ships the `rai` CLI.

## Summary

**What:** End-to-end RelationalAI setup and configuration — installing the Python package, connecting to Snowflake, validating the environment, running a starter program, and tuning all configuration surfaces (auth, model, reasoners, engines, execution).

**When to use:**
- First-time setup: install `relationalai`, connect to Snowflake, run a starter program
- Running RAI locally on DuckDB for development, prototyping, or demos (no Snowflake)
- Creating or editing `raiconfig.yaml`
- Choosing or troubleshooting an authentication method
- Tuning reasoner engines, sizes, solver settings
- Troubleshooting connection or config errors

**When NOT to use:**
- Writing PyRel models or queries — see `rai-pyrel-coding`
- Designing ontology structure — see `rai-ontology-design`
- Solver execution and diagnostics — see `rai-prescriptive-solver-management`
- Discovering what questions an existing model can answer — see `rai-discovery`

**Overview:** For a returning user tweaking config, start from **Quick Reference** below and the **Reference files** trigger table — load only the reference matching the task. For a first-time user, drop into **First-Time Setup Workflow** and walk them through install → connect → validate → starter → next steps. Always finish a connection change by running `rai connect` — never hand the user a config and assume it works.

---

## Prerequisites

Requires Python 3.10+ and `relationalai>=1.2.0`.

The RelationalAI Native App for Snowflake must be installed in your account by an administrator — request access [here](https://app.snowflake.com/marketplace/listing/GZTYZOOIX8H/relationalai-relationalai); see the [Native App docs](https://docs.relational.ai/manage/install). (Not required for local DuckDB development — see [Local Development with DuckDB](#local-development-with-duckdb-no-snowflake) below.)

The `rai_developer` role is the standard role for running PyRel programs. Custom Snowflake roles also work if granted the `rai_user` application role — see [User Access](https://docs.relational.ai/manage/user-access).

**Predictive (GNN) workflows need additional schema setup beyond the base install** — a customer-owned database + schema with `USAGE` and `CREATE EXPERIMENT`/`CREATE MODEL` granted to `APPLICATION RELATIONALAI`. Without it the very first `gnn.fit()` fails. See `rai-predictive-modeling` § Prerequisites for the DDL. The predictive submodule (`relationalai.semantics.reasoners.predictive`) also requires a `relationalai` version that ships it — confirm the minimum with the RelationalAI team before pinning.

Support / docs: support@relational.ai · sales@relational.ai · [docs.relational.ai](https://docs.relational.ai/)

---

## Quick Reference

```bash
rai init      # scaffold a new raiconfig.yaml
rai connect   # validate the connection (run after any connection change)
```

```yaml
# Minimal raiconfig.yaml
default_connection: sf
connections:
  sf:
    type: snowflake
    authenticator: username_password
    account: my_account
    warehouse: my_warehouse
    user: my_user
    password: {{ env_var('SNOWFLAKE_PASSWORD') }}
```

```python
# Programmatic config (no YAML needed)
import os
from relationalai.config import create_config
from relationalai.semantics import Model
config = create_config(
    default_connection="sf",
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
)
model = Model("my_model", config=config)
```

**Verify:** run `rai connect` before writing model code, and after any connection change.

**Before proposing fields in a user's `raiconfig.yaml` or a `create_config(...)` call, verify field names against [raiconfig-yaml.md](references/raiconfig-yaml.md) or [programmatic-config.md](references/programmatic-config.md).** Do not invent kwargs.

---

## First-Time Setup Workflow

Users are expected to be Snowflake users with existing credentials. Walk the user through these steps one-by-one, explaining each and prompting for the inputs you need to run it on their behalf.

### Step 1. Install the package
```bash
pip install relationalai>=1.2.0
# or
uv add relationalai>=1.2.0
```

### Step 2. Establish the connection
Check whether the user has an existing Snowflake connection (`~/.snowflake/config.toml`) or DBT connection (`~/.dbt/profiles.yml`).

- **If yes:** skip config creation — PyRel auto-discovers these. Run `rai` or a PyRel program directly.
- **If no:** run `rai init` to create a `raiconfig.yaml`, then fill in `account`, `warehouse`, `user`, `authenticator`. See [raiconfig-yaml.md](references/raiconfig-yaml.md) for the field reference and [authentication.md](references/authentication.md) for authenticator choice.

### Step 3. Validate the connection
Run `rai connect` to validate the configuration.
- Remind the user to check their MFA device if using `username_password_mfa` or `externalbrowser`.
- On failure, check: (1) credentials, (2) account identifier, (3) warehouse exists and role has access, (4) the Native App is installed. See Common Pitfalls below.

### Step 4. Create a sample
Offer a small sample program using inline data. Ask the user for a domain or use case and tailor the sample to it; if they don't have one, use a minimal structural default — one concept, a handful of instances, one derivation rule, one query — so the sample exercises the install without committing to a vertical. For PyRel syntax load `rai-pyrel-coding`. Ensure the sample runs and the user sees output. Offer to explain the components.

### Step 5. Propose next steps
1. Adapt the sample to real Snowflake tables, or
2. Enhance the sample with richer semantics and different analyses, or
3. Point them at the [project templates](https://docs.relational.ai/build/templates).

---

## Local Development with DuckDB (no Snowflake)

For development, prototyping, and demos, PyRel runs entirely against a local DuckDB database — no Snowflake account or Native App required. The data layer and the logic-family reasoners execute locally; only the engine-backed reasoners still need the cloud service.

| Capability | Local DuckDB | Needs Snowflake / RAI cloud |
|---|:---:|:---:|
| Data loading, querying (select / filter / join / aggregate) | ✓ | |
| Logic & rules (derived properties, classification, recursion, reconciliation) | ✓ | |
| Graph (centrality, community, reachability, components, similarity) | ✓ | |
| Optimization solve (`problem.solve()`) | | ✓ — external solver service |
| Predictive GNN training (`gnn.fit()`) | | ✓ — Snowflake `CREATE EXPERIMENT`/`CREATE MODEL` |

Rule of thumb: relational and recursive-logic reasoning runs locally; anything that hands off to a specialized engine (solver, GNN trainer) needs the cloud service.

**Config — four keys unlock the local path:**

```python
from relationalai.config import Config, DuckDBConnection
from relationalai.semantics import Model

config = Config(
    connections={"local": DuckDBConnection(path=":memory:")},  # or a file path, e.g. "./dev.duckdb"
    default_connection="local",
    install_mode=True,                                # routes to the DuckDB-aware executor
    model={"schema": "main", "auto_install": True},   # install schema + materialize before queries
)
model = Model("my_model", config=config)
```

Equivalent `raiconfig.yaml`:

```yaml
default_connection: local
install_mode: true
connections:
  local:
    type: duckdb
    path: ":memory:"        # or a file, e.g. ./dev.duckdb
model:
  schema: main
  auto_install: true
```

**Loading data:** seed the DuckDB session directly, then reference tables by their **3-part FQN** (`<database>.<schema>.<table>` — in-memory DuckDB defaults to `memory.main`):

```python
session = config.get_connection(DuckDBConnection).get_session()
session.execute("CREATE TABLE employees (id INTEGER, name VARCHAR, dept VARCHAR)")
session.execute("INSERT INTO employees VALUES (1, 'Ada', 'Engineering')")

employees = model.Table("memory.main.employees")   # 3-part FQN required
```

From here the model is authored exactly as against Snowflake — see `rai-pyrel-coding` for concepts, properties, and `define()`.

> **Experimental.** Local DuckDB execution relies on install-mode, which the package currently flags as experimental. Use it for local development and demos; confirm the support stance with the RelationalAI team before relying on it in customer-facing work.

---

## Reference files

Load the reference when the trigger fires — don't read them all upfront.

| Load when… | Reference |
|---|---|
| Creating or editing a `raiconfig.yaml` (need field names, defaults, profile overlays, env-var syntax, or fallback-source order) | [raiconfig-yaml.md](references/raiconfig-yaml.md) |
| Choosing an authenticator, user reports MFA/browser-auth failure, or running inside SPCS / Snowflake Notebooks | [authentication.md](references/authentication.md) |
| Building config in Python instead of YAML, or fetching a `session` / clearing a session cache | [programmatic-config.md](references/programmatic-config.md) |
| Configuring reasoners — backend, engine size, Gurobi, polling — or reasoner name/size doesn't take effect as expected | [reasoners.md](references/reasoners.md) |
| Turning on metrics/logging, tuning retries, toggling compiler strictness, or changing data-loading defaults | [execution.md](references/execution.md) |
| Provisioning, listing, resuming, or deleting engines via CLI/Python API, or evaluating warm reasoners | [engine-management.md](references/engine-management.md) |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Errors about RelationalAI Native App not existing | NA not installed, or current role lacks access | Verify the Native App is installed and the current role has `rai_developer` or a custom role granted the `rai_user` application role |
| `raiconfig.yaml` not found | File not in CWD or any parent directory | Place `raiconfig.yaml` in project root; `create_config()` walks upward from CWD |
| First invalid config raises with no fallback | PyRel validates the first source found; if invalid it stops | Fix the file — does not fall back to lower-priority sources after a parse error |
| Both `raiconfig.toml` and `.yaml` present | TOML may take precedence in some code paths | Remove `.toml` and use `.yaml` as canonical |
| `direct_access` backend with no `direct_access_base_url` | URL is required when `backend: direct_access` | Set `reasoners.direct_access_base_url` or switch to `backend: sql` |
| `execution.logging: true` produces no output | Python logging must be configured separately | Add `logging.getLogger("relationalai.client.execution").setLevel(logging.INFO)` |
| Auth fails with `externalbrowser` in CI | Browser auth requires an interactive session | Use `jwt` or `username_password` for non-interactive environments |
| Engine not provisioned | Reasoner config references a size unavailable on account | Check `reasoners.*.size` matches available sizes for your platform |
| Unicode errors on Windows (`UnicodeEncodeError`) | Windows console defaults to a non-UTF-8 encoding | Set `PYTHONIOENCODING=utf-8`. PowerShell: `$env:PYTHONIOENCODING = "utf-8"`; cmd: `set PYTHONIOENCODING=utf-8` |
| `rai` CLI fails on PowerShell | Execution policy blocks scripts | User runs `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| (DuckDB) `Expected a fully-qualified table name with 3 parts` | DuckDB tables need `database.schema.table` | Reference in-memory tables as `memory.main.<table>` |
| (DuckDB) Query falls back to the Snowflake path, or reads an empty/missing model relation | `install_mode` / `auto_install` not set | Set `install_mode: true` and `model.auto_install: true` (or run `rai models install` before querying) |
| (DuckDB) `Configuration must specify a non-empty schema name` | No install schema for model relations | Set `model.schema` (e.g. `main`) |

---

## Related Skills
- `rai-pyrel-coding` — PyRel syntax and data loading
- `rai-ontology-design` — domain modeling
- `rai-discovery` — surface answerable questions and route to the right reasoner
- `rai-prescriptive-solver-management` — solver lifecycle and diagnostics (includes Gurobi usage)
- `rai-health` — diagnose engine performance issues
