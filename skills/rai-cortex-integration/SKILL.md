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
- Configuring `DeploymentConfig` (`database`, `schema`, optional `agent_schema`, warehouse, LLM, preview flags)
- Registering tools: `SourceCodeVerbalizer`, `QueryCatalog`, or default model tools
- Deploying, updating, or cleaning up stored procedures and agents
- Writing pre-defined query functions for `QueryCatalog`
- Troubleshooting deployment errors (missing schema, invalid `agent_schema`, preview flags, `init_tools` shape)

**When NOT to use:**
- Defining model logic (concepts, properties, relationships) — see `rai-pyrel-coding/SKILL.md`
- Designing ontologies or data models — see `rai-ontology-design/SKILL.md`
- Writing queries for local use (not deployment) — see `rai-querying`

**Primary output:** A deployment script with CLI subcommands (`deploy`, `update`, `status`, `chat`, `teardown`) that manages the full agent lifecycle. See [examples/deploy.py](examples/deploy.py) for the reference implementation.

**Overview:**
1. Create a deployment script with CLI that wraps the user's model
2. Use the script to deploy the user's model to a Snowflake Cortex Agent
3. Test via `chat` subcommand
4. Expose the agent to Snowflake Intelligence via `agent_schema` or the UI

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

1. **Configuration** — constants for agent name, deployment `database`/`schema`, optional `agent_schema`, warehouse
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
| `CREATE STAGE` on deployment schema | Store sproc dependencies |
| `CREATE PROCEDURE` on deployment schema | Register RAI tool sprocs |
| `CREATE AGENT` on the agent schema | Register the Cortex agent (`schema` by default, `agent_schema` if set) |
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `application role snowflake.ai_observability_events_lookup` | Access monitoring traces |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `rai_developer` role | Access RAI (granted during native app install) |
| `USAGE` on the relevant databases and schemas | Access the deployment schema and, if different, the `agent_schema` target |

### Step 2 — Configure DeploymentConfig

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_name` | Yes | — | Unique name for the Cortex agent within the agent schema |
| `database` | Yes | — | Snowflake database where stored procedures and the stage are created |
| `schema` | Yes | — | Snowflake schema where stored procedures and the stage are created |
| `agent_schema` | No | `None` | Fully-qualified `DATABASE.SCHEMA` where the agent is created. Use `SNOWFLAKE_INTELLIGENCE.AGENTS` to place the agent directly in the SI schema. If omitted, the agent is created alongside the sprocs |
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

The `init_tools` function is executed inside each stored procedure invocation. It must be **self-contained** — do not close over local runtime state (sessions, connections, dataframes). Import your model code inside the function so it resolves from the packaged sproc code and initializes within the sproc session. See `init_tools()` in [examples/deploy.py](examples/deploy.py).

**Three configuration levels** — each adds more capability via `ToolRegistry.add()`:

1. **Default** — model discovery and schema verbalization only. See [examples/cortex.py](examples/cortex.py).
2. **With verbalizer** — adds source-code-aware concept explanation. See [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py).
3. **With verbalizer + queries** — adds pre-defined analytical queries (requires `allow_preview=True`). See [examples/cortex_verbalizer_queries.py](examples/cortex_verbalizer_queries.py).

**`init_tools` shapes**:
1. **Recommended** — zero-argument `init_tools()` that imports module-defined model code and returns `ToolRegistry().add(model=<imported module>.model, ...)`
2. **Legacy** — one-argument `init_tools(model)` for codebases that already build the model by mutating a framework-supplied `Model`

Prefer the zero-argument form for new code. PyRel validates that `init_tools` accepts **0 or 1 required parameters**; helper signatures with 2+ required parameters are rejected.

### Step 4 — Verbalizers

Verbalizers control how model structure is presented to the agent.

**ModelVerbalizer (default)** — returns relationship readings extracted from the model (e.g., "Customer has many Orders"). Used automatically when no verbalizer is specified.

**SourceCodeVerbalizer** — extends `ModelVerbalizer`. `explain_model` returns the standard relationship readings, while `explain_concept` returns Python source code from the modules you provide, filtered to definitions that reference the requested concept. Comments are included, so clarifications in your code benefit the agent. Pass the imported model **modules** that define the model. See [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py).

Use `SourceCodeVerbalizer` when important domain logic is encoded in rule definitions, computed properties, subtype logic, or inline comments rather than being obvious from concept/relationship structure alone. This is what enables the agent to answer questions that go deeper than "what concepts exist and how are they related?", such as whether a `Cancel Transaction` can cancel another `Cancel Transaction`, or why a concept is derived under a particular set of rule conditions.

If the model is simple and the agent only needs schema-level understanding, the default `ModelVerbalizer` is usually enough. Add `SourceCodeVerbalizer` when the agent needs access to the reasoning encoded in the source.

### Step 5 — QueryCatalog (PREVIEW)

> The queries capability is in PREVIEW. Deployment requires `allow_preview=True`.

Each query function must:
- Return a `rai.Fragment` (a `rai.select(...)` expression) or `pandas.DataFrame`
- Have a clear **docstring** — used as the query description shown to the agent
- Have a `__name__` attribute — used as the query identifier

See [examples/model/queries.py](examples/model/queries.py) for a complete query definition.

Prefer **module-level zero-argument query functions** imported inside `init_tools()`. This keeps `__name__` and `__doc__` intact for `QueryCatalog` without wrappers or partials.

Use `QueryCatalog` to expose a small set of curated, parameterized entry points into advanced analysis that the agent should invoke directly rather than reconstruct from scratch. Good candidates are things like community detection outputs, graph metrics, scenario summaries, or other pre-modeled analytical routines whose results you want surfaced reliably.

Do **not** use `QueryCatalog` as a general-purpose slicing-and-dicing layer for ordinary business exploration. For open-ended dimensional analysis and ad hoc filtering/aggregation, Snowflake Semantic Views are usually the better fit. `QueryCatalog` is for high-value, opinionated queries that expose complex analysis results cleanly to the agent.

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

When model code lives **outside** the deploy script's directory (e.g., an `ontology/` package at the project root), `discover_imports()` may not find it because it walks from the calling file's location. In this case, build an explicit imports list instead:

```python
def _imports():
    return [
        os.path.join(_AGENT_DIR, "queries.py"),
        (os.path.join(_PROJECT_ROOT, "ontology"), "ontology"),  # (path, module_name) tuple
    ]
```

Directories are passed as `(path, module_name)` tuples so Snowpark registers them as importable packages. Additionally, `init_tools()` must add the project root to `sys.path` so cross-directory imports resolve inside the sproc sandbox:

```python
def init_tools():
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ontology.Ontology import ...
```

**`extra_packages`** — optional parameter on `deploy()`/`update()` that specifies additional PyPI packages Snowflake installs in the sproc environment. `httpx` is a known required entry — it is a dependency of `relationalai.agent.cortex` but is not auto-installed as a transitive dependency in the sproc environment.

If `agent_schema` is set, `deploy()`, `status()`, `chat()`, and `cleanup()` operate on the agent in that schema while the stored procedures and stage remain in `database`.`schema`.

---

## After Deployment

After a successful deploy, inform the user of these next steps:

1. **Verify** — run the `status` subcommand to confirm all sprocs are created.
2. **Test** — run the `chat` subcommand with a sample question (e.g., `"What can I ask about?"`) to confirm the agent responds correctly.
3. **Find the agent in Snowflake** — navigate to **AI & ML > Cortex Agents** in the Snowflake UI. The agent appears under `agent_schema` if you set it, otherwise under `database`.`schema`.
4. **Preview the agent** — click the agent name to open its detail page. Use the **Chat** tab to interact with it directly and verify it answers domain questions correctly.
5. **Expose it in Snowflake Intelligence** — if you deployed the agent directly to `SNOWFLAKE_INTELLIGENCE.AGENTS` via `agent_schema`, it is already in the SI schema. Otherwise, use **Add to Snowflake Intelligence** on the agent detail page to promote it.
6. **Monitor conversations** — the **Monitoring** tab on the agent detail page shows all conversations (both SI and programmatic via `manager.chat()`), including full tool-call traces for debugging.

---

## Deployed Stored Procedures

Four CALLER'S RIGHTS stored procedures are created in the deployment schema (`database`.`schema`), even if the agent itself is created elsewhere via `agent_schema`:

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
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `rai_developer` role | Access RAI |
| `USAGE` on the relevant databases and schemas | Access the agent schema plus any deployment/data schemas it touches |
| `SELECT` on tables | Read data accessed by the model |
| `EXECUTE` on stored procedures | Invoke RAI tools in the deployment schema |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `use schema` fails during deploy | Deployment schema doesn't exist | Run `CREATE SCHEMA IF NOT EXISTS` before deploying. If `agent_schema` is different, ensure that schema exists and the deployer can use it too |
| Object "does not exist" errors from Snowflake | Role lacks required privileges — Snowflake reports missing permissions as "does not exist" | Verify deployer and SI user privileges against the tables in Steps 1 and 6 (Deployed Stored Procedures) |
| Agent does not show up where expected in the UI | Agent was created in `database`.`schema`, not the SI schema | Set `agent_schema="SNOWFLAKE_INTELLIGENCE.AGENTS"` or promote the deployed agent from the UI |
| `agent_schema` validation fails | Value is not a two-part `DATABASE.SCHEMA` name | Use a fully qualified two-part name such as `SNOWFLAKE_INTELLIGENCE.AGENTS` |
| `QueryCatalog` rejects a query definition | Wrapped queries lost `__name__` or `__doc__` metadata | Prefer module-level query functions with docstrings; avoid `functools.partial` |
| Sproc fails at runtime with table-not-found | Model references a table unavailable in the sproc context | Restructure entity seeding to make that table optional |
| `RAI_QUERY_MODEL` not available | `allow_preview` not set | Set `allow_preview=True` in `DeploymentConfig` |
| `init_tools` is rejected or fails with stale state | Closed over local runtime objects or declared 2+ required parameters | Keep `init_tools` self-contained and use only the supported 0-param (recommended) or 1-param (legacy) forms |
| Agent can't explain business rules | No verbalizer configured | Add `SourceCodeVerbalizer` with all relevant model modules |
| `discover_imports()` misses model code | Model package lives outside the deploy script's directory | Use an explicit imports list with `(path, module_name)` tuples and add `sys.path` insertion in `init_tools()` — see Step 6 |
| Sproc fails with `ModuleNotFoundError: httpx` | `httpx` is a transitive dependency not auto-installed in sproc environment | Add `"httpx"` to `extra_packages` on `deploy()`/`update()` |
| Deploy returns 404 on Azure-hosted Snowflake | `_hostname()` uses only the account locator, missing the Azure regional hostname | Known SDK issue — workaround: monkey-patch `relationalai.agent.cortex.api.client._hostname` to return the full regional hostname (e.g., `account.east-us-2.azure.snowflakecomputing.com`) |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| **Deployment script** | **Complete CLI with deploy/update/status/chat/teardown — primary reference** | [**examples/deploy.py**](examples/deploy.py) |
| Default deployment | Minimal CortexAgentManager with model tools only | [examples/cortex.py](examples/cortex.py) |
| Verbalizer deployment | Adds SourceCodeVerbalizer for concept explanation | [examples/cortex_verbalizer.py](examples/cortex_verbalizer.py) |
| Full deployment | Verbalizer + QueryCatalog with pre-defined queries | [examples/cortex_verbalizer_queries.py](examples/cortex_verbalizer_queries.py) |
| Model modules | Core, computed, and query modules for the recommended zero-arg `init_tools()` pattern | [examples/model/](examples/model/) |
