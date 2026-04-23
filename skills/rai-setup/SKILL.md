---
name: rai-setup
description: Setup and configuration for RelationalAI — first-time install and Snowflake connection walkthrough, plus raiconfig.yaml, authentication, reasoner/engine settings, and troubleshooting. Use when installing RAI, connecting to Snowflake, or configuring anything in raiconfig.yaml.
---

# RelationalAI Setup & Configuration
<!-- v1-SENSITIVE -->

Build AI that is aligned to your business, grounded in your semantic model, and powered by the advanced reasoners of the RelationalAI decision intelligence platform. Learn more at [relational.ai](https://relational.ai).

This skill refers to the [relationalai Python package](https://pypi.org/project/relationalai) (aka PyRel), which provides PyRel programs and the `rai` CLI.

## Summary

**What:** End-to-end RelationalAI setup and configuration — installing the Python package, connecting to Snowflake, validating the environment, running a starter program, and tuning all configuration surfaces (auth, model, reasoners, engines, execution).

**When to use:**
- First-time setup: install `relationalai`, connect to Snowflake, run a starter program
- Creating or editing `raiconfig.yaml`
- Choosing or troubleshooting an authentication method
- Tuning reasoner engines, sizes, solver settings
- Troubleshooting connection or config errors

**When NOT to use:**
- Writing PyRel models or queries — see `rai-pyrel-coding`
- Designing ontology structure — see `rai-ontology-design`
- Solver execution and diagnostics — see `rai-prescriptive-solver-management`
- Discovering what questions an existing model can answer — see `rai-discovery`

---

## Prerequisites

Requires Python 3.10+ and `relationalai>=1.0.14`.

The RelationalAI Native App for Snowflake must be installed in your account by an administrator.
- Request access [here](https://app.snowflake.com/marketplace/listing/GZTYZOOIX8H/relationalai-relationalai).
- See the [Native App docs](https://docs.relational.ai/manage/install) for details.

The `rai_developer` role is the standard role for running PyRel programs. Custom Snowflake roles also work if granted the `rai_user` application role — see [User Access](https://docs.relational.ai/manage/user-access).

## Contact
- support@relational.ai
- sales@relational.ai
- [official documentation](https://docs.relational.ai/)

---

## First-Time Setup Workflow

Users are expected to be Snowflake users with existing credentials. Walk the user through these steps one-by-one, explaining each and prompting for the inputs you need to run it on their behalf.

### Step 1. Install the package
```bash
pip install relationalai>=1.0.14
# or
uv add relationalai>=1.0.14
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
Offer a small sample program using inline data. If the user has a domain or analytical use case, tailor the sample to it; otherwise, use customer segmentation with graph analysis (see `rai-graph-analysis`). Reference `rai-pyrel-coding` for syntax. Ensure the sample runs and the user sees output. Offer to explain the components.

### Step 5. Propose next steps
1. Adapt the sample to real Snowflake tables, or
2. Enhance the sample with richer semantics and different analyses, or
3. Point them at the [project templates](https://docs.relational.ai/build/templates).

---

## Quick Reference

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
    password: ${SNOWFLAKE_PASSWORD}
```

```python
# Programmatic config (no YAML needed)
from relationalai.config import create_config
from relationalai.semantics import Model
config = create_config(connection_type="snowflake")
model = Model("my_model", config=config)
```

**Verify:** run `rai connect` before writing model code, and after any connection change.

---

## Where to find details

| Topic | Reference |
|---|---|
| Full `raiconfig.yaml` structure — connections, model, data, profile overlays, env vars, fallback sources | [raiconfig-yaml.md](references/raiconfig-yaml.md) |
| Snowflake authentication — 6 authenticators, SPCS / Snowflake Notebooks auto-detection | [authentication.md](references/authentication.md) |
| Programmatic config — `create_config()`, typed auth objects, sessions | [programmatic-config.md](references/programmatic-config.md) |
| Reasoner configuration — backends, engine sizes, per-reasoner settings, Gurobi, polling | [reasoners.md](references/reasoners.md) |
| Execution — metrics/logging, retries, compiler strictness, data-loading defaults | [execution.md](references/execution.md) |
| Engine management — CLI and Python API for provisioning and lifecycle | [engine-management.md](references/engine-management.md) |
| Migration from PyRel v0.13 | [v013-migration.md](references/v013-migration.md) |

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

---

## Related Skills
- `rai-pyrel-coding` — PyRel syntax and data loading
- `rai-ontology-design` — domain modeling
- `rai-discovery` — surface answerable questions and route to the right reasoner
- `rai-prescriptive-solver-management` — solver lifecycle and diagnostics (includes Gurobi usage)
- `rai-health-skill` — diagnose engine performance issues
