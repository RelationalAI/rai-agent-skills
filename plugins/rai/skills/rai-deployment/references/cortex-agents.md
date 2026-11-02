# Deploy as a Snowflake CoWork (Cortex) agent

This reference covers operationalizing a built RAI model as a Snowflake CoWork (Cortex) agent — one of the paths to prod from the [deployment hub](../SKILL.md). The agent serves **one model that is already deployed** with deploy mode (`rai models deploy`, see [Deploy](../SKILL.md#deploy-the-foundation)): it reads that **model deployment** and never deploys or refreshes the model. Every tool call runs as one SQL statement over the deployed tables and views, in the caller's session.

The primary output is a deployment script — a CLI that can preflight, deploy, update, test, and tear down the agent — and [deploy.py](../examples/deploy.py) is the reference implementation.

This API (`AgentConfig`, `DefaultTool`, `ModelDeployment`) requires a `relationalai` release where `from relationalai.agent.cortex import AgentConfig` succeeds. If that import fails, upgrade `relationalai` before following this reference.

## Quick Reference

The deployment script provides a CLI for the full agent lifecycle:

```bash
python -m <package>.deploy deploy        # Preflight + create stage, sprocs, and agent
python -m <package>.deploy update        # Update sprocs without re-registering the agent
python -m <package>.deploy status        # Print deployment status
python -m <package>.deploy chat "..."    # Send a message to the deployed agent
python -m <package>.deploy teardown      # Remove all agent resources
python -m <package>.deploy preflight     # Probe grants and the model deployment without deploying
python -m <package>.deploy setup-sql     # Emit a paste-ready GRANT block
```

The script contains four key parts — see [deploy.py](../examples/deploy.py) for the complete reference:

1. **Configuration** — constants for agent name, `tools_schema`, the model's deployment schema, optional `agent_schema`, warehouse
2. **`_build_manager()`** — creates the session and a `CortexAgentManager` over an `AgentConfig`
3. **`init_tools()`** — called inside each sproc; returns one `DefaultTool` for the model
4. **CLI subcommands** — `deploy`, `update`, `status`, `chat`, `teardown`, `preflight`, `setup-sql`

**Expected project layout:**

```
<project_root>/                  # CWD when running the deploy script
├── raiconfig.yaml               # connection + the model's deployment block
├── <agent_pkg>/
│   ├── __init__.py
│   ├── deploy.py                # CLI entry — init_tools() lives here
│   └── queries.py               # (optional) query functions for QueryCatalog
└── <model_pkg>/                 # Your model code as a sibling package
    ├── __init__.py              # imports every module that defines the model
    ├── core.py
    └── ...
```

Deploy the model with `rai models deploy --path <model_pkg>` and the agent with `python -m <agent_pkg>.deploy deploy`, both from `<project_root>`. A directory `--path` imports the package, so `<model_pkg>/__init__.py` must import every module that adds to the model (see [model/__init__.py](../examples/model/__init__.py)). Every module referenced by `init_tools()` must live under the project root — `discover_imports()` packages local imports relative to CWD and excludes anything outside it (Step 6).

Leverage PyRel's inline docstrings by running eg `help(CortexAgentManager)` or `print(relationalai.agent.cortex.__doc__)`.

---

## Instructions

The goal is a deployment script (e.g., `deploy.py`) that operationalizes a deployed RAI model as a Cortex agent. Each step below corresponds to a section of the script.

### Step 1 — Deploy the model

The agent reads the model deployment's identity marker, deploy state, and op log from its meta schema, `<schema>_META`, and replays the op log to rebuild the model. Deploy the model so all three exist:

- **Op-log recording on** (`oplog.enabled`, the default since relationalai 1.28.0) — without it, the agent deploy fails with `ModelDeploymentHasNoOplog`.
- **Default compiler** — a model deployed with `compiler.optimization: aggressive` reports `ModelDeploymentIncomplete`.
- **Default meta schema** — a model deployed with a custom `deployment.meta_schema` reports `ModelDeploymentNotFound`.
- **Snowflake-table sources** (`model.Table("DB.SCHEMA.TABLE")`) — inline `model.data(...)` rows can't be deployed.
- **No `Model(..., config=...)`** — the agent's model runs with PyRel defaults plus the deployment's location and `preserve_column_case`. A model built with an explicit config keeps that config's `preserve_column_case`; build it without one, or match the deployed value.

Confirm the refresh succeeded (`CALL <db>.<schema>_META.REFRESH_STATUS();`) before deploying the agent. The deploy recipe and refresh-schedule settings are in [deploy-and-oplog.md](deploy-and-oplog.md).

### Step 2 — Create a Snowflake Session

Use `create_config().get_session(SnowflakeConnection)` to create a session from `raiconfig.yaml`. See `_build_manager()` in [deploy.py](../examples/deploy.py). Deploy and update the agent from a process with exactly one open Snowpark session; with more than one they fail with "No active Snowpark session found".

The deployer role needs these privileges. `manager.print_setup_sql(deployer_role=...)` emits a paste-ready `GRANT` block parameterized with the actual config; the table below is the same content as a reference.

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on the `tools_schema` database and schema, and on the warehouse | Access the deployment target |
| `CREATE STAGE` on `tools_schema` | Store sproc dependencies (if `manage_stage=True`) |
| `CREATE PROCEDURE` on `tools_schema` | Register RAI tool sprocs |
| `CREATE AGENT` on `tools_schema` — or on `agent_schema`, plus `USAGE` on it and its database, when that is set | Register the Cortex agent |
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `database role snowflake.pypi_repository_user` | Install Python packages in the sproc environment |
| `application role snowflake.ai_observability_events_lookup` | Access monitoring traces |
| `USAGE` on the model's meta schema (`<schema>_META`) and its database | Read the model deployment's metadata |
| `SELECT` on the meta schema's `_INTERNAL_MODEL_IDENTITY`, `_INTERNAL_DEPLOY_STATE`, and `_INTERNAL_OPLOG` tables (named with the deployment's prefix and suffix) | Find the deployment, check its last deploy, and replay its model |

The deployer needs no access to the model's source tables or deployed outputs. For a branch deployment, the deployer also needs `SELECT` on the parent deployment's identity marker and op log, which `print_setup_sql` doesn't emit.

`deploy()` runs preflight automatically before creating resources. To inspect findings without deploying, call `manager.preflight(init_tools=...)` and `print(report.format(config=manager.config, role=report.role))`. To bypass the grant probes once the environment is known good, pass `skip_preflight=True` to `deploy()` — the model-deployment check still runs.

### Step 3 — Configure AgentConfig

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `agent_name` | Yes | — | Unique name for the Cortex agent within its schema |
| `tools_schema` | Yes | — | Fully-qualified `DATABASE.SCHEMA` for the sprocs and stage, and the agent unless `agent_schema` is set. Must already exist. Keep it separate from the model's deployment schema |
| `model_deployment` | Yes | — | `ModelDeployment(schema=..., object_name_prefix=..., object_name_suffix=...)` naming where the model was deployed — its `deployment.schema`, plus its `object_name_prefix`/`object_name_suffix` when several models share that schema |
| `warehouse` | No | `None` | Warehouse for RAI tool execution. SI users need USAGE. If omitted, tools use the caller's session warehouse |
| `agent_schema` | No | `None` | Fully-qualified `DATABASE.SCHEMA` where the agent is created. Use `SNOWFLAKE_INTELLIGENCE.AGENTS` to place it directly in the SI schema. If omitted, the agent is created in `tools_schema` |
| `allow_preview` | No | `False` | Enable preview capabilities — `RAI_QUERY_MODEL` (catalog + dynamic queries) |
| `procedure_prefix` | No | `None` | Namespaces the physical stored-procedure names so several agents can share one `tools_schema` (e.g. `SALES_RAI_DISCOVER_MODEL`). Restricted-environment fallback; prefer a `tools_schema` per agent. See [Deploying multiple agents to one schema](#deploying-multiple-agents-to-one-schema) |
| `stage_name` | No | `"rai_sprocs"` | Name of the Snowflake stage for storing sproc dependencies |
| `manage_stage` | No | `True` | Automatically create/drop the stage during deploy/cleanup. Set `False` for a pre-existing stage |
| `llm` | No | `"claude-opus-4-6"` | LLM for agent orchestration. Must be available in Snowflake Cortex |
| `query_timeout_s` | No | `300` | Timeout in seconds for stored procedure execution |
| `budget_seconds` | No | `None` | Time budget for agent execution |
| `budget_tokens` | No | `None` | Token budget for model consumption |
| `artifact_repository` | No | `"snowflake.snowpark.pypi_shared_repository"` | Artifact repository for Python packages |

Unquoted identifiers resolve uppercase; double-quote a name only when the Snowflake object was created lowercase or mixed-case. See `_build_manager()` in [deploy.py](../examples/deploy.py) for a complete construction example.

### Step 4 — Write the `init_tools` Function

`init_tools` runs once locally to validate the tool and again inside each stored procedure invocation. It takes **no parameters**, returns **one `Tool`** — usually a `DefaultTool` over the one model the agent serves — and must be **self-contained**: do not close over local runtime state (sessions, connections, dataframes). Import your model code inside the function so it resolves from the packaged sproc code. See `init_tools()` in [deploy.py](../examples/deploy.py).

`deploy()` and `update()` point the model `init_tools` returns at `model_deployment`, so afterwards that in-process model reads the deployment and no longer auto-deploys.

**Three configuration levels** — each adds capability via `DefaultTool(...)`. [deploy.py](../examples/deploy.py) shows the recommended (level 2) form.

1. **Default** — model discovery and schema verbalization only (no queries).

   ```python
   def init_tools():
       from .model.core import model
       return DefaultTool(
           model=model,
           description="Customers and orders",
       )
   ```

2. **Recommended — catalog + dynamic queries** (requires `allow_preview=True` in `AgentConfig`). Passing `model=` to `QueryCatalog` enables dynamic queries: the agent prefers catalog queries when one matches and falls back to authoring small JSON specs against the queryable schema otherwise.

   ```python
   def init_tools():
       from .model import core, computed, queries  # computed registers rules onto core.model
       return DefaultTool(
           model=core.model,
           description="Customers and orders",
           queries=QueryCatalog(queries.segment_summary, model=core.model),
       )
   ```

3. **With `SourceCodeVerbalizer` (LEGACY)** — adds source-code-aware concept explanation. Planned for deprecation in favor of `ModelVerbalizer` plus PyRel's structured `EXPLAIN` drill-down. Retained for codebases that still depend on emitting raw Python source to the agent.

   ```python
   def init_tools():
       from .model import core, computed, queries
       return DefaultTool(
           model=core.model,
           description="Customers and orders",
           verbalizer=SourceCodeVerbalizer(core.model, core, computed),
           queries=QueryCatalog(queries.segment_summary, model=core.model),
       )
   ```

The model `init_tools` builds should match the deployed model. `deploy()` replays the op log and compares the two; a difference is a `DeployedModelMismatch` warning naming what changed, not an error, so an agent can be redeployed mid-rollout. A query that reads a relation the deployment lacks fails when the agent runs it — treat the warning as a to-do.

### Step 5 — Verbalizers

Verbalizers control how model structure is presented to the agent.

**`ModelVerbalizer` (default)** — returns relationship readings extracted from the model. By default, readings backed by auto-generated source-table column properties are filtered out, and the output is restricted to the model's traversal graph: identifier readings per concept plus readings whose rightmost field targets another entity concept. Primitive-typed property readings are dropped — the same information is reachable through `EXPLAIN(concept)`. Pass `include_source_columns=True` to restore the legacy emit-everything behavior.

`ModelVerbalizer` is used automatically when no verbalizer is specified. It is what you want for most deployments.

**`SourceCodeVerbalizer` (LEGACY — planned for deprecation)** — extends `ModelVerbalizer`. `explain_model` returns the standard relationship readings, while `explain_concept` returns Python source code from the modules you provide, filtered to definitions that reference the requested concept. Pass the model first, then the imported model **modules** that define it. Reach for it only if you already depend on emitting raw Python source and need parity while migrating; the default `ModelVerbalizer` plus the per-concept view and `Concept.<member>` rule-body drill-down is the supported path.

### Step 6 — QueryCatalog and Dynamic Queries (PREVIEW)

> The queries capability is in PREVIEW. Deployment requires `allow_preview=True`.

Without `QueryCatalog` (or `DynamicQueries`) passed as `DefaultTool(..., queries=...)`, the agent can describe the model but cannot execute any queries — `RAI_QUERY_MODEL` is not registered.

Two complementary surfaces ship under one capability:

- **Catalog queries** — pre-defined, vetted analytical functions built by domain experts. The agent picks one by `id` and supplies arguments.
- **Dynamic queries** — the agent authors a small JSON query spec at runtime against the model's queryable schema. Use for narrow exploratory analysis when no catalog query matches.

Both are exposed through `RAI_QUERY_MODEL`. **Recommended wiring** is `QueryCatalog(func1, func2, ..., model=model)` — the catalog routes the reserved id `"dynamic"` to a `DynamicQueries` over the same model. Catalog-only (`QueryCatalog(funcs...)`) and dynamic-only (`DynamicQueries(model)`) tools are both supported; use `CompositeQueries` for advanced layouts (e.g. multiple catalog providers).

Each catalog query function must:
- Return a `rai.Fragment` (a `rai.select(...)` expression) or `pandas.DataFrame`
- Have a clear **docstring** — used as the query description shown to the agent
- Have a `__name__` attribute — used as the query identifier (the name `"dynamic"` is reserved)

Type-annotated parameters become the agent-visible `args` schema. See [queries.py](../examples/model/queries.py) for a complete query definition. Prefer **module-level zero-argument query functions** imported inside `init_tools()`, which keeps `__name__` and `__doc__` intact without wrappers or partials.

**Adding a new query:**
1. Define a module-level function in `queries.py` that returns a `rai.Fragment` or `pandas.DataFrame`, with a docstring.
2. Add the function to the `QueryCatalog(...)` call inside `init_tools()`.
3. Redeploy with `update` (or `deploy` if the agent doesn't exist yet).

Catalog and dynamic queries read the model deployment's materialized tables, so a query over a derived property or concept reads its precomputed values. To precompute an aggregation, model it as a derived property so it becomes a deployed output.

**When to choose catalog vs dynamic.**

- Use **catalog queries** for high-value, opinionated entry points the agent should invoke directly rather than reconstruct — community detection outputs, graph metrics, scenario summaries, multi-hop region rollups, vetted analytical routines. Catalog queries carry the model author's judgment for the asks that matter most.
- Use **dynamic queries** (by passing `model=` to `QueryCatalog`) for the long tail — narrow filters, row-level lookups, simple aggregations the catalog doesn't anticipate. Dynamic queries are intentionally a small-result surface; the agent is instructed to write the answer query directly on the first attempt and probe column values only reactively.

For open-ended dimensional analysis and ad hoc filtering/aggregation, Snowflake Semantic Views may also be a fit. `QueryCatalog` + dynamic queries is the right blend when the answers benefit from the semantic model's business logic, computed properties, and rules.

### Step 7 — CLI Subcommands

Wire the manager methods into CLI subcommands using `argparse`. Each command maps to a single manager call. See [deploy.py](../examples/deploy.py) for the complete implementation.

| Command | Manager method | Notes |
|---------|---------------|-------|
| `deploy` | `manager.deploy(init_tools=..., imports=discover_imports())` | Runs preflight, checks the model deployment, then creates stage, sprocs, and agent |
| `update` | `manager.update(init_tools=..., imports=discover_imports())` | Updates sprocs without re-registering the agent. Run after every model redeploy |
| `status` | `manager.status()` | Reports what exists |
| `chat` | `manager.chat().send(message)` | Test the deployed agent |
| `teardown` | `manager.cleanup()` | Removes agent, sprocs, and stage — **permanently loses SI conversation history**. Leaves the model deployment untouched |
| `preflight` | `manager.preflight(init_tools=...)` | Probes grants and the model deployment without deploying |
| `setup-sql` | `manager.print_setup_sql(deployer_role=..., si_role=..., create_role=...)` | Emits a paste-ready GRANT block parameterized with the actual config |

The procedures carry the deployment's source-table columns and `preserve_column_case` as read at agent deploy, so **after every model redeploy, run `update`** to pick up the new model. When `init_tools` is supplied to `preflight()` it also compares the built model with the deployed one and probes DISCOVER/VERBALIZE/EXPLAIN payload sizes against the response budget (`Truncated*Payload` warnings); `deploy()` surfaces only `DeployedModelMismatch` among the warnings.

**`imports`** — `discover_imports()` recursively discovers local Python imports and packages them into the stored procedure. It excludes standard library and installed packages; `relationalai==<installed version>` is installed in the sproc from `artifact_repository`. It uses the **current working directory** as the project root and filters out anything outside it, which is why the canonical layout keeps the agent and model packages as siblings under `<project_root>` and runs `python -m <agent_pkg>.deploy ...` from there.

For cases `discover_imports()` can't cover — e.g., a package that must be registered under a specific sproc-visible module name, or model code that cannot be relocated under the project root — build an explicit imports list:

```python
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _AGENT_DIR.parent

def _imports():
    return [
        str(_AGENT_DIR / "queries.py"),
        (str(_PROJECT_ROOT / "ontology"), "ontology"),  # (path, module_name) tuple
    ]
```

Pass this in place of `discover_imports()`: `manager.deploy(init_tools=init_tools, imports=_imports())`. Directory entries use `(path, module_name)` tuples so Snowpark registers them as top-level importable packages inside the sproc. Keep `init_tools()` self-contained per Step 4 — **no `sys.path` manipulation inside `init_tools()`**: the tuple form already makes the package importable in the sproc, and mutating `sys.path` there is a no-op that masks the real fix.

**Workaround if you ignore the run-from-project-root guidance:** if you must invoke the deploy script from somewhere else and local imports fail, add a one-time `sys.path` fix at the *top of the deploy module* — not inside `init_tools()`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This is a local-invocation crutch, not a deploy requirement. Prefer running from the project root.

**`extra_packages`** — optional parameter on `deploy()`/`update()` naming additional PyPI packages Snowflake installs in the sproc environment. Use it only for third-party libraries your model or query code depends on; `relationalai` and its declared dependencies are installed automatically.

If `agent_schema` is set, `deploy()`, `status()`, `chat()`, and `cleanup()` operate on the agent in that schema while the stored procedures and stage remain in `tools_schema`.

### Step 8 — Deploying from a Snowflake Workspace / notebook

Snowflake Workspaces and notebooks run the deploy script from the **workspace root** under an ipykernel, on a managed filesystem that handles targeted single-file I/O but throws `[Errno 5] Input/output error` (EIO) on the bulk or recursive I/O that the canonical flow relies on. Three things that work when running from a project root fail here; each needs a deliberate adjustment.

**Prerequisites — the *user* must complete these first; the agent cannot.** Both require Snowflake UI / terminal access the agent does not have, so when you (the agent) are helping someone deploy from a Workspace, **surface this guidance to the user explicitly** and wait for them to confirm both are done before deploying:

1. **Configure the Python kernel under "Edit service".** In the notebook's service/runtime settings ("Edit service"), attach the **pip artifact repository**. Without it the kernel can't install packages.
2. **Install the SDK from the terminal** — the user runs `pip install relationalai` in the Workspace terminal.

Only once both are done will the deploy script run. The three adjustments below are code-level and the agent handles them.

**1. Layout — deploy script at the workspace root, model in a sibling module dir.** You can't `python -m <pkg>.deploy` here; the Run action executes the file directly with CWD = workspace root.

```
<workspace_root>/          # CWD when the script runs
├── agent.py               # deploy script — at the root, run directly
└── my_model/              # model package, sibling of the script
    ├── clinical.py
    └── queries.py
```

`init_tools()` imports from the package as usual: `from my_model import clinical, queries`.

**2. Pass explicit file-level imports; do not use `discover_imports()`.** `discover_imports()` reads the *calling file* — in a Workspace that's a synthetic `/tmp/ipykernel_*.py` that doesn't exist on disk, so it warns `File not found` and returns `[]`. And a directory tuple like `("my_model/", "my_model")` makes Snowpark recursively read the whole tree (including `__pycache__`), which trips the EIO. Pass **file-level** tuples with dotted module names instead:

```python
manager.deploy(
    init_tools=init_tools,
    imports=[
        ("my_model/clinical.py", "my_model.clinical"),
        ("my_model/queries.py",  "my_model.queries"),
    ],
)
```

Each tuple is `(local_file_path, dotted_module_name)`. List every module `init_tools()` imports; add `("my_model/__init__.py", "my_model")` if your `__init__.py` carries real content.

**3. Disable the on-disk tracer.** PyRel's telemetry tracer writes `spans.jsonl` to `build/` during the run. Its auto-init guard falls back to a no-op tracer only for **read-only** filesystems (`EROFS`, errno 30 — the in-sproc case); it does **not** catch the Workspace's EIO, so span flushes raise mid-deploy. Stub the tracer at the very top of the script, before importing or constructing the model:

```python
from relationalai.observability.tracing import set_tracer, StubTracer
set_tracer(StubTracer())
```

All three are facets of one root cause — the Workspace's managed filesystem rejecting bulk/recursive I/O — and none of them affect the canonical run-from-project-root flow in the Quick Reference.

---

## Model deployment errors

`deploy()` and `update()` read the model deployment before registering any procedure and write nothing to it. When the deployment can't serve the agent, `update()` and `deploy(skip_preflight=True)` raise the code below; `deploy()` otherwise raises `PreflightFailed` with the code in its report.

| Code | Cause | Fix |
|------|-------|-----|
| `ModelDeploymentNotFound` | No model deployed at that schema with that prefix/suffix; the identity marker belongs to another deployment (e.g. a cloned database); a custom `deployment.meta_schema`; or the role can't read the meta schema | Check `ModelDeployment(schema=...)` matches the model's `deployment.schema`, prefix, and suffix; grant the meta-schema reads from Step 2 |
| `ModelDeploymentIncomplete` | First model deploy hasn't finished; deployed with `compiler.optimization: aggressive`; or the role can't read its deploy state | Wait for `rai models deploy --wait` to finish; redeploy with the default compiler |
| `ModelDeploymentFailed` | The model's last deploy failed — the message carries the recorded error | Fix and redeploy the model ([dev-loop-and-monitoring.md](dev-loop-and-monitoring.md)) |
| `ModelDeploymentHasNoOplog` | Model deployed with `oplog.enabled: false`, or the role can't read its op log | Redeploy the model with op-log recording on |

---

## Deploying multiple agents to one schema

An agent serves exactly one model; deploy one agent per model (Snowflake Intelligence users can switch agents within a chat). Each agent creates four fixed-name stored procedures (`RAI_DISCOVER_MODEL`, `RAI_VERBALIZE_MODEL`, `RAI_EXPLAIN_CONCEPT`, `RAI_QUERY_MODEL`), so two agents pointed at the **same** `tools_schema` would overwrite each other's sprocs. **Prefer a dedicated `tools_schema` per agent** — every example here assumes it.

For **restricted environments** where you cannot provision a schema per agent, set a distinct `procedure_prefix` on each `AgentConfig`:

```python
AgentConfig(agent_name="SALES_ASSISTANT", tools_schema="APPS.CORTEX",
            model_deployment=ModelDeployment(schema="APPS.SALES"),
            warehouse="MY_WH", procedure_prefix="SALES")  # -> SALES_RAI_DISCOVER_MODEL, ...
AgentConfig(agent_name="OPS_ASSISTANT",   tools_schema="APPS.CORTEX",
            model_deployment=ModelDeployment(schema="APPS.OPS"),
            warehouse="MY_WH", procedure_prefix="OPS")    # -> OPS_RAI_DISCOVER_MODEL, ...
```

How it behaves:

- **Agent-facing tool names are unchanged.** The prefix affects only the physical Snowflake procedure names, so orchestration text is identical across agents.
- **One shared stage.** The `rai_sprocs` stage is created with `CREATE STAGE IF NOT EXISTS`, so multiple agents safely share it; Snowpark content-addresses the packaged `imports` under checksum paths, so nothing collides. A single `GRANT ... ON STAGE rai_sprocs` and `GRANT USAGE ON ALL PROCEDURES IN SCHEMA ...` cover every prefixed agent.
- **Cache-bust and cleanup are prefix-scoped.** Deploy and cleanup run `REMOVE @rai_sprocs/<PREFIX>_RAI_*/` for that agent only; `cleanup()` drops only that agent's sprocs and leaves the shared stage and sibling agents in place. An unprefixed agent still drops the stage it manages.
- **Status ignores the shared stage.** For a prefixed agent, `status()` reports on the agent and its own sprocs only.

---

## After Deployment

After a successful deploy, inform the user of these next steps:

1. **Verify** — run the `status` subcommand to confirm all sprocs are created.
2. **Test** — run the `chat` subcommand with a sample question (e.g., `"What can I ask about?"`) to confirm the agent responds correctly.
3. **Grant SI users** — run the SI-user block from `setup-sql --si-role <role>` *after* deploy: it grants on the agent and the procedures that exist then. `update()` keeps those grants.
4. **Find the agent in Snowflake** — navigate to **AI & ML > Agents** in the Snowflake UI. The agent appears under `agent_schema` if you set it, otherwise under `tools_schema`.
5. **Preview the agent** — click the agent name and use the **Chat** tab to verify it answers domain questions correctly.
6. **Expose it in Snowflake CoWork** — if you deployed the agent directly to `SNOWFLAKE_INTELLIGENCE.AGENTS` via `agent_schema`, it is already in the SI schema. Otherwise, use **Add to Snowflake CoWork** on the agent detail page to promote it.
7. **Monitor conversations** — the **Monitoring** tab on the agent detail page shows all conversations (both SI and programmatic via `manager.chat()`), including full tool-call traces.
8. **Keep it current** — after every model redeploy, run `update`.

---

## Debugging a Deployed Agent

A successful `deploy` means the sprocs and agent exist — it does *not* mean the agent answers correctly. Permission gaps, stale imports, an invalid `llm` choice, missing `allow_preview`, a stale agent after a model redeploy, or a `relationalai` mismatch inside the sproc all surface only at runtime, usually as the agent apologizing for an "internal error".

See [debug.py](../examples/debug.py) for a runnable script that performs the three checks below in order. Copy it alongside `deploy.py`, keep the configuration block in sync, and run `python -m <package>.debug` from the project root.

**1. Describe the agent.** Fetch the agent spec via the Snowflake API to confirm what's actually registered: the tool names, their input schemas, and the bound stored procedures. If a tool is missing from the spec, the orchestrator can't call it; if a tool resource points at the wrong schema, every call returns a "does not exist" error.

```python
described = manager._api.describe(
    manager.config.agent_database,
    manager.config.agent_schema_name,
    manager.config.agent_name,
)
# described.agent_spec.tools — list of Tool(tool_spec=ToolSpec(name, type, ...))
# described.agent_spec.tool_resources — {tool name: ToolResourceSpec(identifier, ...)}
```

**2. Invoke each sproc directly.** Calling the RAI sprocs as plain SQL is the fastest way to read the underlying error — Snowflake returns the import error, missing-grant message, or Python traceback verbatim instead of the agent wrapping it in a generic envelope. Call in dependency order:

```sql
CALL <tools_schema>.RAI_DISCOVER_MODEL();
CALL <tools_schema>.RAI_VERBALIZE_MODEL();
CALL <tools_schema>.RAI_EXPLAIN_CONCEPT('<concept_name>');
CALL <tools_schema>.RAI_QUERY_MODEL('{"id":"<query_id>","args":{}}');
```

`RAI_DISCOVER_MODEL` returns the model's concepts and catalog query ids — use its output to drive the remaining calls. If DISCOVER fails, none of the others can succeed; fix it first. Common direct-invocation failures:

- `does not exist or not authorized` on the sproc itself → the caller lacks `USAGE` on the procedure, or the deployer lacked `CREATE PROCEDURE` and the sproc was never created. Re-run `manager.preflight()`.
- `ModuleNotFoundError: No module named 'relationalai.agent.cortex.…'` inside the sproc → the sproc installed a `relationalai` build that lacks code your local install has (an unreleased or dev build shares a version number with an older PyPI release). Deploy from a released `relationalai`.
- `ModuleNotFoundError` for your own package → `init_tools()` references code outside the project root, or `discover_imports()` was invoked from the wrong CWD. See Step 7.
- `RAI_QUERY_MODEL does not exist` → `allow_preview=True` was not set on `AgentConfig`.
- "Invalid model" / unknown `llm` → the `llm` in `AgentConfig` is not available in this Snowflake region; pick a different Cortex-supported model.
- Sproc runs but the envelope contains a `kind: error` payload → read the `hint` field; it names the missing concept, query id, relation, or grant.

**3. Trace one chat turn.** Send a known-good question and dump the tool calls, tool result envelopes, and orchestrator thinking. This reveals planning bugs (the agent invokes the wrong tool, or never calls `RAI_DISCOVER_MODEL` first) and shows how tool-result errors are reaching the orchestrator.

```python
response = manager.chat().send("What can I ask about?")
response.tool_calls()    # what the orchestrator asked for
response.tool_results()  # envelopes returned by the sprocs (errors land here)
response.raw["content"]  # includes `thinking` blocks with the orchestrator's plan
```

If the answers still look wrong but the sproc envelopes are clean, the issue is usually a verbalization or catalog-description gap, not a deployment failure — iterate on `init_tools()` and redeploy with `update`.

---

## Deployed Stored Procedures

Four CALLER'S RIGHTS stored procedures are created in `tools_schema`, even if the agent itself is created elsewhere via `agent_schema`:

| Sproc | Purpose | Maturity |
|-------|---------|----------|
| `RAI_DISCOVER_MODEL()` | Describes the agent's model: its key concepts, the catalog queries it exposes, and whether it supports dynamic queries | GA |
| `RAI_VERBALIZE_MODEL()` | Returns the model's traversal graph (entity-targeted relationship readings + per-concept identifier readings) | GA |
| `RAI_EXPLAIN_CONCEPT(name)` | Explains a single concept, a single catalog query (by its id, returning its source), a computed-predicate drill-down (`Concept.<member>`), or — for dynamic-mode models — the full dynamic-query reference (`"dynamic"`) | GA |
| `RAI_QUERY_MODEL(json)` | Executes a named catalog query (`{"id":"<id>","args":{...}}`) or a dynamic query (`{"id":"dynamic","args":{"spec":{...}}}`) | PREVIEW |

When `procedure_prefix` is set, the physical procedure names are namespaced (e.g. `SALES_RAI_DISCOVER_MODEL`); the agent-facing tool names are unchanged.

All sprocs run under the **invoking user's privileges**, not the owner's — Snowflake's existing RBAC is the single source of truth for data governance across all agent interactions. No privilege escalation is possible.

Every sproc returns a uniform response envelope: `{content, kind, truncated, truncation_reason, applied_limit?}`. Errors land in the envelope too, as typed `{kind, path, available, hint}` payloads under `content`, so the agent has a single way to read both success and failure and can self-correct on the next turn.

SI users need:

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on warehouse | Execute sprocs (warehouse from `AgentConfig`, or session default) |
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `USAGE` on the databases and schemas of `tools_schema` and `agent_schema` | Reach the sprocs and the agent |
| `USAGE ON ALL PROCEDURES` in `tools_schema` | Invoke RAI tools |
| `USAGE` on the agent | Chat with the agent |
| `USAGE` on the model's deployment schema and meta schema, and their databases | Reach the model deployment |
| `SELECT` on all and future tables, dynamic tables, and views in both schemas | Read the deployed outputs (including outputs later model deploys add) and synthetic concepts, which live in the meta schema |

SI users need no grants on the model's source tables — deployed views read them with the view owner's rights. Emit a paste-ready block with `manager.print_setup_sql(deployer_role="MY_DEPLOYER", si_role="MY_SI", create_role=True)`, and run the SI block after the agent is deployed.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `ImportError: cannot import name 'AgentConfig'` | Installed `relationalai` predates the model-deployment agent API | Upgrade `relationalai` |
| Agent deploy fails with a `ModelDeployment*` code | The model isn't deployed where `ModelDeployment` points, or was deployed without the op log / with the aggressive compiler | See [Model deployment errors](#model-deployment-errors); deploy the model first per Step 1 |
| `rai models deploy --path <model_pkg>` fails: "No models found" | A directory path imports the package, and its `__init__.py` imports nothing | Import every model module in `<model_pkg>/__init__.py` |
| `DeployedModelMismatch` warning at agent deploy | The model `init_tools` builds differs from the deployed one (e.g. `init_tools` imports a module the model deploy didn't, or the model changed since its last deploy) | Redeploy the model with the same modules `init_tools` imports, then `update` the agent. Queries over relations missing from the deployment fail at runtime |
| Agent answers with stale results or errors after a model redeploy | The procedures carry the deployment's columns as read at agent deploy | Run `update` after every model redeploy |
| Every tool call returns "internal error" right after a clean deploy | Sproc-side failure — import, grant, or `relationalai` mismatch | Call the sprocs directly (Debugging, step 2) to read the real error |
| `use schema` / "does not exist" during deploy | `tools_schema` doesn't exist — deploy does not create it | `CREATE SCHEMA IF NOT EXISTS <tools_schema>` first; if `agent_schema` differs, ensure it exists and the deployer can use it too |
| Object "does not exist" errors from Snowflake | Role lacks required privileges — Snowflake reports missing permissions as "does not exist" | Run `manager.preflight()` for a named-grant fix list; `manager.print_setup_sql(deployer_role=...)` emits a paste-ready block |
| Preflight warns `MissingCreateStage` / `MissingCreateProcedure` / `MissingCreateAgent` though deploy works | Preflight checks direct grants; a role that owns the schema (or inherits the privilege) has no direct grant | False alarm when the role owns or inherits the privilege; otherwise grant it |
| SI users get "does not exist" on tools or data | SI grants run before the agent existed, or miss the model's meta schema | Run the SI block from `setup-sql --si-role` after deploy; it covers the deployment schema *and* its `_META` schema |
| Agent does not show up where expected in the UI | Agent was created in `tools_schema`, not the SI schema | Set `agent_schema="SNOWFLAKE_INTELLIGENCE.AGENTS"` or promote it from **AI & ML > Agents** |
| A second agent in the same schema overwrote the first agent's tools | Both created the same fixed-name sprocs | Give each agent its own `tools_schema` (preferred), or a distinct `procedure_prefix` |
| `tools_schema` / `agent_schema` validation fails | Value is not a two-part `DATABASE.SCHEMA` name | Use a fully qualified two-part name |
| `InvalidInitTools` | `init_tools` takes parameters, or doesn't return a `Tool` | Use a zero-arg `init_tools()` returning one `DefaultTool` |
| `QueryCatalog` rejects a query definition | Wrapped queries lost `__name__` or `__doc__`, or the function name is `"dynamic"` | Prefer module-level query functions with docstrings; avoid `functools.partial`; rename away from `"dynamic"` |
| `RAI_QUERY_MODEL` not available | `allow_preview` not set | Set `allow_preview=True` in `AgentConfig` |
| Agent describes the model but can't run dynamic queries | `QueryCatalog` constructed without `model=` | Pass `model=...` to `QueryCatalog` |
| Agent can't explain business rules | Per-concept rule signatures alone aren't enough for the question | Drill via `EXPLAIN("Concept.<member>")` for rule bodies; `SourceCodeVerbalizer` is a legacy escape hatch |
| `discover_imports()` misses model code | Model package lives outside CWD, or needs a specific sproc-visible module name | Run from the project root; otherwise use an explicit `_imports()` list with `(path, module_name)` tuples — Step 7 |
| `[Errno 5] Input/output error` during `deploy()` in a Snowflake Workspace | Snowpark recursively reads a directory import, or PyRel's tracer writes `spans.jsonl`, against the Workspace's managed filesystem | File-level `imports` tuples and `set_tracer(StubTracer())` — Step 8 |
| `discover_imports()` warns `File not found: /tmp/ipykernel_*.py` and returns `[]` | Running in a Workspace/notebook — the cell has no source file on disk | Pass explicit file-level `imports` tuples — Step 8 |
| "No active Snowpark session found" during deploy/update | More than one Snowpark session open in the process | Deploy from a process with exactly one session |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| **Deployment script** | **Complete CLI with preflight/setup-sql/deploy/update/status/chat/teardown — primary reference. Uses the recommended catalog + dynamic queries form (level 2); see Step 4 for level 1 and level 3** | [**deploy.py**](../examples/deploy.py) |
| Debug script | Describes the deployed agent, calls each sproc directly, and traces a chat turn | [debug.py](../examples/debug.py) |
| Model modules | Table-sourced core, computed rules, and catalog queries; `__init__.py` imports the model modules so `rai models deploy --path <package>/model` deploys them | [model/](../examples/model/) |
