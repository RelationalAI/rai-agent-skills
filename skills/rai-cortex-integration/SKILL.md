---
name: rai-cortex-integration
description: Covers deploying RAI models as Snowflake Cortex Agents for Snowflake Intelligence. Use when deploying a model as a Cortex Agent or configuring Snowflake Intelligence.
---

# Snowflake Intelligence Integration
<!-- v1-STABLE -->

## Summary

**What:** Operationalize a RAI knowledge graph by creating a **deployment script** that packages it as a Snowflake Intelligence (SI) agent. The deployment script is the primary output of this skill — a CLI that can deploy, update, test, and tear down the Cortex agent.

**When to use:**
- Scaffolding a deployment script to operationalize an existing RAI model as a Cortex agent
- Configuring `DeploymentConfig` (database, schema, warehouse, LLM, preview flags)
- Registering tools: `SourceCodeVerbalizer`, `QueryCatalog`, or default model tools
- Deploying, updating, or cleaning up stored procedures and agents
- Writing pre-defined query functions for `QueryCatalog`
- Troubleshooting deployment errors (missing schema, preview flags, query binding)

**When NOT to use:**
- Defining model logic (concepts, properties, relationships) — see `rai-pyrel-coding/SKILL.md`
- Designing ontologies or data models — see `rai-ontology-design/SKILL.md`
- Writing queries for local use (not deployment) — see `rai-querying`

**Primary output:** A deployment script with CLI subcommands (`deploy`, `update`, `status`, `chat`, `teardown`) that manages the full agent lifecycle. See [examples/deploy.py](examples/deploy.py) for the reference implementation.

**Overview:**
1. Create a deployment script with CLI that wraps the user's model
2. Use the script to deploy the user's model to a Snowflake Cortex Agent
3. Test via `chat` subcommand
4. Promote to Snowflake Intelligence via the UI

---

## Quick Reference

The deployment script is the primary artifact. It provides a CLI to manage the full agent lifecycle:

```bash
python -m <package>.deploy deploy      # Create schema, stage, sprocs, and agent
python -m <package>.deploy update      # Update sprocs without re-registering the agent
python -m <package>.deploy status      # Print deployment status
python -m <package>.deploy chat "..."  # Send a message to the deployed agent
python -m <package>.deploy teardown    # Remove all agent resources
```

The script contains four key parts — see [examples/deploy.py](examples/deploy.py) for the complete reference:

1. **Configuration** — constants for agent name, database, schema, warehouse
2. **`_build_manager()`** — creates session and `CortexAgentManager`
3. **`init_tools()`** — called inside each sproc; builds a `ToolRegistry`
4. **CLI subcommands** — `deploy`, `update`, `status`, `chat`, `teardown`

Leverage PyRel's inline docstrings by inspecting the code or running eg `help(CortexAgentManager)` or `print(CortexAgentManager.__doc__)`

---

## Instructions

The goal is to produce a deployment script (e.g., `deploy.py`) that operationalizes a RAI model as a Cortex agent. The script should expose CLI subcommands for the full lifecycle. Each step below corresponds to a section of the script.

### Step 1 — Create a Snowflake Session

Use `create_config().get_session(SnowflakeConnection)` to create a session from `raiconfig.yaml`. See `_build_manager()` in [examples/deploy.py](examples/deploy.py).

The deployer role must have these privileges:

| Privilege | Purpose |
|-----------|---------|
| `CREATE STAGE` on target schema | Store sproc dependencies |
| `CREATE PROCEDURE` on target schema | Register RAI tool sprocs |
| `CREATE AGENT` on target schema | Register the Cortex agent |
| `database role snowflake.cortex_user` | Access Cortex services |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `rai_developer` role | Access RAI (granted during native app install) |
| `USAGE` on database and schema | Access the deployment target |

### Step 2 — Configure DeploymentConfig

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_name` | Yes | — | Unique name for the Cortex agent within the schema |
| `database` | Yes | — | Snowflake database for deployment |
| `schema` | Yes | — | Snowflake schema for deployment. For SI UI access, deploy to the schema configured for your account (typically `AGENTS`) |
| `model_name` | No | Same as `agent_name` | Name for the `Model` instance created inside each stored procedure |
| `warehouse` | No | None | Warehouse for RAI tool execution. SI users need USAGE. If omitted, tools use the caller's session warehouse |
| `stage_name` | No | `"rai_sprocs"` | Name of the Snowflake stage for storing sproc dependencies |
| `manage_stage` | No | `True` | Automatically create/drop the stage during deploy/cleanup. Set `False` for a pre-existing stage |
| `llm` | No | `"claude-sonnet-4-5"` | LLM for agent orchestration. Must be available in Snowflake Cortex |
| `query_timeout_s` | No | `300` | Timeout in seconds for stored procedure execution |
| `budget_seconds` | No | None | Time budget for agent execution |
| `budget_tokens` | No | None | Token budget for model consumption |
| `external_access_integration` | No | `"S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION"` | External access integration for sprocs |
| `artifact_repository` | No | `"snowflake.snowpark.pypi_shared_repository"` | Artifact repository for Python packages |
| `allow_preview` | No | `False` | Enable preview capabilities (e.g., `RAI_QUERY_MODEL` sproc) |

See `_build_manager()` in [examples/deploy.py](examples/deploy.py) for a complete construction example.

### Step 3 — Write the `init_tools` Function

The `init_tools` function is executed inside each stored procedure invocation with a fresh `Model`. It must be **self-contained** — do not close over local runtime state (sessions, connections, dataframes). Import your model code inside the function so it resolves from the packaged sproc code. See `init_tools()` in [examples/deploy.py](examples/deploy.py).

**Three configuration levels** — each adds more capability via `ToolRegistry.add()`:

1. **Default** — model discovery and schema verbalization only. See [examples/cortex.py](examples/cortex.py).
2. **With verbalizer** — adds source-code-aware concept explanation. See [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py).
3. **With verbalizer + queries** — adds pre-defined analytical queries (requires `allow_preview=True`). See [examples/cortex_verbalizer_queries.py](examples/cortex_verbalizer_queries.py).

**Note**:
Two forms of PyRel program are supported
1) the form displayed in the examples which defines the model directly in modules
2) a form which defines the model inside functions that take a Model object
The `model: Model` param to `init_tools` is intended to be passed to functions present in 2). It must be provided in case of 1), but the ToolRegistry should instead use the Model that the user declares in their own module after importing it.

### Step 4 — Verbalizers

Verbalizers control how model structure is presented to the agent.

**ModelVerbalizer (default)** — returns relationship readings extracted from the model (e.g., "Customer has many Orders"). Used automatically when no verbalizer is specified.

**SourceCodeVerbalizer** — extends `ModelVerbalizer`. `explain_model` returns the standard relationship readings, while `explain_concept` returns Python source code from the functions you provide, filtered to those referencing the requested concept. Comments are included, so clarifications in your code benefit the agent. Pass **functions** (not modules) — the verbalizer inspects their source code via `inspect.getsource()`. See [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py).

### Step 5 — QueryCatalog (PREVIEW)

> The queries capability is in PREVIEW. Deployment requires `allow_preview=True`.

Each query function must:
- Return a `rai.Fragment` (a `rai.select(...)` expression) or `pandas.DataFrame`
- Have a clear **docstring** — used as the query description shown to the agent
- Have a `__name__` attribute — used as the query identifier

See [examples/model/queries.py](examples/model/queries.py) for a complete query definition.

**Binding pattern** — when standalone query functions need a model argument, use `functools.wraps` to preserve `__name__` and `__doc__`:

```python
import functools

def _bind(func, model: Model):
    @functools.wraps(func)
    def wrapper():
        return func(model)
    return wrapper

queries = QueryCatalog(_bind(query_fn_1, model), _bind(query_fn_2, model))
```

### Step 6 — CLI Subcommands

Wire the manager methods into CLI subcommands using `argparse`. Each command maps to a single manager call. See [examples/deploy.py](examples/deploy.py) for the complete implementation.

| Command | Manager method | Notes |
|---------|---------------|-------|
| `deploy` | `manager.deploy(init_tools=..., imports=discover_imports())` | Creates schema, stage, sprocs, and agent |
| `update` | `manager.update(init_tools=..., imports=discover_imports())` | Updates sprocs without re-registering agent |
| `status` | `manager.status()` | Reports what exists |
| `chat` | `manager.chat().send(message)` | Test the deployed agent |
| `teardown` | `manager.cleanup()` | Removes all resources — **permanently loses SI conversation history** |

**`imports`** — `discover_imports()` recursively discovers all local Python imports from the calling file and packages them into the stored procedure. It excludes standard library and installed packages. The `relationalai` package is included automatically.

**`extra_packages`** — optional parameter on `deploy()`/`update()` that specifies additional PyPI packages Snowflake installs in the sproc environment.

---

## After Deployment

After a successful deploy, inform the user of these next steps:

1. **Verify** — run the `status` subcommand to confirm all sprocs are created.
2. **Test** — run the `chat` subcommand with a sample question (e.g., `"What can I ask about?"`) to confirm the agent responds correctly.
3. **Find the agent in Snowflake** — navigate to **AI & ML > Cortex Agents** in the Snowflake UI. The agent appears under the configured database and schema.
4. **Preview the agent** — click the agent name to open its detail page. Use the **Chat** tab to interact with it directly and verify it answers domain questions correctly.
5. **Promote to Snowflake Intelligence** — on the agent detail page, click **Add to Snowflake Intelligence** to make the agent available to all SI users in the account. Once promoted, users can discover and chat with the agent from the Snowflake Intelligence homepage.
6. **Monitor conversations** — the **Monitoring** tab on the agent detail page shows all conversations (both SI and programmatic via `manager.chat()`), including full tool-call traces for debugging.

---

## Deployed Stored Procedures

Four CALLER'S RIGHTS stored procedures are created in the target schema:

| Sproc | Purpose | Maturity |
|-------|---------|----------|
| `RAI_DISCOVER_MODELS` | Lists all registered RAI models and their concepts | GA |
| `RAI_VERBALIZE_MODEL` | Returns human-readable schema description for the LLM | GA |
| `RAI_EXPLAIN_CONCEPT` | Explains a specific concept using verbalizer context | GA |
| `RAI_QUERY_MODEL` | Executes a named pre-defined query from `QueryCatalog` | PREVIEW |

All sprocs run under the **invoking user's privileges**, not the owner's — Snowflake's existing RBAC is the single source of truth for data governance across all agent interactions. No privilege escalation is possible.

SI users need:

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on warehouse | Execute sprocs |
| `database role snowflake.cortex_user` | Access Cortex services |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `rai_developer` role | Access RAI |
| `USAGE` on database and schema | Access the data |
| `SELECT` on tables | Read data accessed by the model |
| `EXECUTE` on stored procedures | Invoke RAI tools |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `use schema` fails during deploy | Target schema doesn't exist | Run `CREATE SCHEMA IF NOT EXISTS` before deploying |
| Object "does not exist" errors from Snowflake | Role lacks required privileges — Snowflake reports missing permissions as "does not exist" | Verify deployer and SI user privileges against the tables in Steps 1 and 6 (Deployed Stored Procedures) |
| `QueryCatalog` raises `ValueError` on `__name__` | Query wrapped with `functools.partial` which doesn't preserve `__name__` | Use `_bind()` with `functools.wraps` instead |
| Sproc fails at runtime with table-not-found | Model references a table unavailable in the sproc context | Restructure entity seeding to make that table optional |
| `RAI_QUERY_MODEL` not available | `allow_preview` not set | Set `allow_preview=True` in `DeploymentConfig` |
| `init_tools` fails with stale state | Closed over local runtime objects (session, dataframe) | Keep `init_tools` self-contained — only reference importable functions |
| Agent can't explain business rules | No verbalizer configured | Add `SourceCodeVerbalizer` with all relevant define functions |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| **Deployment script** | **Complete CLI with deploy/update/status/chat/teardown — primary reference** | [**examples/deploy.py**](examples/deploy.py) |
| Default deployment | Minimal CortexAgentManager with model tools only | [examples/cortex.py](examples/cortex.py) |
| Verbalizer deployment | Adds SourceCodeVerbalizer for concept explanation | [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py) |
| Full deployment | Verbalizer + QueryCatalog with pre-defined queries | [examples/cortex_verbalizer_queries.py](examples/cortex_verbalizer_queries.py) |
| Model definition | Core and computed model structure for deployment | [examples/model/](examples/model/) |
