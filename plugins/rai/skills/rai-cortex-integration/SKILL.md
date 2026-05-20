---
name: rai-cortex-integration
description: Covers deploying RAI models as Snowflake Cortex Agents for Snowflake Intelligence. Use when deploying a model as a Cortex Agent or configuring Snowflake Intelligence.
---

# Snowflake Intelligence Integration
<!-- v1-STABLE -->

## Summary

**What:** Operationalize a RAI knowledge graph by creating a **deployment script** that packages it as a Snowflake Intelligence (SI) agent. The deployment script is the primary output of this skill — a CLI that can preflight, deploy, update, test, and tear down the Cortex agent.

**When to use:**
- Scaffolding a deployment script to operationalize an existing RAI model as a Cortex agent
- Configuring `DeploymentConfig` (`database`, `schema`, optional `agent_schema`, warehouse, LLM, preview flags)
- Registering tools: `ModelVerbalizer` (default), `SourceCodeVerbalizer`, `QueryCatalog`, `DynamicQueries`, or default model tools
- Deploying, updating, or cleaning up stored procedures and agents
- Writing pre-defined query functions for `QueryCatalog`
- Running `manager.preflight()` and emitting a `GRANT` block for a Snowflake admin
- Troubleshooting deployment errors (missing grants, invalid `agent_schema`, preview flags, `init_tools` shape, payload truncation)

**When NOT to use:**
- Defining model logic (concepts, properties, relationships) — see `rai-pyrel-coding/SKILL.md`
- Designing ontologies or data models — see `rai-ontology-design/SKILL.md`
- Writing queries for local use (not deployment) — see `rai-querying`

**Primary output:** A deployment script with CLI subcommands (`deploy`, `update`, `status`, `chat`, `teardown`, `preflight`, `setup-sql`) that manages the full agent lifecycle. See [examples/deploy.py](examples/deploy.py) for the reference implementation.

**Overview:**
1. Create a deployment script with CLI that wraps the user's model
2. Use the script to deploy the user's model to a Snowflake Cortex Agent
3. Test via `chat` subcommand
4. Expose the agent to Snowflake Intelligence via `agent_schema` or the UI

---

## Quick Reference

The deployment script is the primary artifact. It provides a CLI to manage the full agent lifecycle:

```bash
python -m <package>.deploy deploy        # Preflight + create schema, stage, sprocs, and agent
python -m <package>.deploy update        # Update sprocs without re-registering the agent
python -m <package>.deploy status        # Print deployment status
python -m <package>.deploy chat "..."    # Send a message to the deployed agent
python -m <package>.deploy teardown      # Remove all agent resources
python -m <package>.deploy preflight     # Probe grants without deploying
python -m <package>.deploy setup-sql     # Emit a paste-ready GRANT block
```

The script contains four key parts — see [examples/deploy.py](examples/deploy.py) for the complete reference:

1. **Configuration** — constants for agent name, deployment `database`/`schema`, optional `agent_schema`, warehouse
2. **`_build_manager()`** — creates session and `CortexAgentManager`
3. **`init_tools()`** — called inside each sproc; builds a `ToolRegistry`
4. **CLI subcommands** — `deploy`, `update`, `status`, `chat`, `teardown`, `preflight`, `setup-sql`

**Expected project layout:**

```
<project_root>/                  # CWD when running the deploy script
├── <agent_pkg>/
│   ├── __init__.py
│   ├── deploy.py                # CLI entry — init_tools() lives here
│   └── queries.py               # (optional) query functions for QueryCatalog
└── <model_pkg>/                 # Your model code as a sibling package
    ├── __init__.py
    ├── core.py
    └── ...
```

Invoke as `python -m <agent_pkg>.deploy <command>` from `<project_root>`. Every module referenced by `init_tools()` (model code, query functions) must live under this root — `discover_imports()` packages local imports relative to CWD and excludes anything outside it. See Step 6 for the full `imports` contract and non-standard layouts.

Leverage PyRel's inline docstrings by inspecting the code or running eg `help(CortexAgentManager)` or `print(CortexAgentManager.__doc__)`.

---

## Instructions

The goal is to produce a deployment script (e.g., `deploy.py`) that operationalizes a RAI model as a Cortex agent. The script should expose CLI subcommands for the full lifecycle. Each step below corresponds to a section of the script.

### Step 1 — Create a Snowflake Session

Use `create_config().get_session(SnowflakeConnection)` to create a session from `raiconfig.yaml`. See `_build_manager()` in [examples/deploy.py](examples/deploy.py).

The deployer role must have these privileges. Use `manager.print_setup_sql(deployer_role=...)` to emit a paste-ready `GRANT` block parameterized with the actual deployment values; the table below is the same content as a reference.

| Privilege | Purpose |
|-----------|---------|
| `CREATE STAGE` on deployment schema | Store sproc dependencies (if `manage_stage=True`) |
| `CREATE PROCEDURE` on deployment schema | Register RAI tool sprocs |
| `CREATE AGENT` on the agent schema | Register the Cortex agent (`schema` by default, `agent_schema` if set) |
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `application role snowflake.ai_observability_events_lookup` | Access monitoring traces |
| `application role relationalai.rai_user` | Access the RAI Native App (created during install) |
| `USAGE` on `S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION` | Network egress to RAI services from inside the sproc |
| `USAGE` on the database, schema, and warehouse | Access the deployment target (and `agent_schema` if different) |

`S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION` is created by Step 4 of the RAI Native App install notebook. If the admin says the integration does not exist, that step has not been run.

`deploy()` runs preflight automatically before creating resources. To inspect grants without deploying, call `manager.preflight()` and `print(report.format(config=manager.config))`. To bypass for fast iteration once the environment is known good, pass `skip_preflight=True` to `deploy()`.

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
| `llm` | No | `"claude-opus-4-6"` | LLM for agent orchestration. Must be available in Snowflake Cortex |
| `query_timeout_s` | No | `300` | Timeout in seconds for stored procedure execution |
| `budget_seconds` | No | None | Time budget for agent execution |
| `budget_tokens` | No | None | Token budget for model consumption |
| `external_access_integration` | No | `"S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION"` | External access integration for sprocs |
| `artifact_repository` | No | `"snowflake.snowpark.pypi_shared_repository"` | Artifact repository for Python packages |
| `allow_preview` | No | `False` | Enable preview capabilities — `RAI_QUERY_MODEL` (catalog + dynamic queries) |
| `strict_payload_check` | No | `False` | If `True`, DISCOVER truncation in the deploy-time payload-size preflight becomes a blocking error instead of a warning |
| `sproc_config_overrides` | No | `None` | Top-level `Config` field overrides applied to every tool's `Model.config` inside the sproc sandbox. Example: `{"data": {"wait_for_stream_sync": False}}` to skip stream-sync waits for read-only ad-hoc queries |

See `_build_manager()` in [examples/deploy.py](examples/deploy.py) for a complete construction example.

### Step 3 — Write the `init_tools` Function

The `init_tools` function is executed inside each stored procedure invocation. It must be **self-contained** — do not close over local runtime state (sessions, connections, dataframes). Import your model code inside the function so it resolves from the packaged sproc code and initializes within the sproc session. See `init_tools()` in [examples/deploy.py](examples/deploy.py).

**Three configuration levels** — each adds more capability via `ToolRegistry.add()`. [examples/deploy.py](examples/deploy.py) shows the recommended (level 2) form; the snippets below show the registry shape for each level.

1. **Default** — model discovery and schema verbalization only (no queries).

   ```python
   def init_tools():
       from .model.core import model
       return ToolRegistry().add(
           model=model,
           description="Customers and orders",
       )
   ```

2. **Recommended — catalog + dynamic queries** (requires `allow_preview=True` in `DeploymentConfig`). Passing `model=` to `QueryCatalog` enables dynamic queries: the agent prefers catalog queries when one matches and falls back to authoring small JSON specs against the queryable schema otherwise.

   ```python
   def init_tools():
       from .model import core, computed, queries  # computed registers rules onto core.model
       return ToolRegistry().add(
           model=core.model,
           description="Customers and orders",
           queries=QueryCatalog(queries.segment_summary, model=core.model),
       )
   ```

3. **With `SourceCodeVerbalizer` (LEGACY)** — adds source-code-aware concept explanation. Planned for deprecation in favor of `ModelVerbalizer` plus PyRel's structured `EXPLAIN` drill-down. Retained for codebases that still depend on emitting raw Python source to the agent.

   ```python
   def init_tools():
       from .model import core, computed, queries
       return ToolRegistry().add(
           model=core.model,
           description="Customers and orders",
           verbalizer=SourceCodeVerbalizer(core.model, core, computed),
           queries=QueryCatalog(queries.segment_summary, model=core.model),
       )
   ```

**`init_tools` shapes**:
1. **Recommended** — zero-argument `init_tools()` that imports module-defined model code and returns `ToolRegistry().add(model=<imported module>.model, ...)`
2. **Legacy** — one-argument `init_tools(model)` for codebases that already build the model by mutating a framework-supplied `Model`

Prefer the zero-argument form for new code. PyRel validates that `init_tools` accepts **0 or 1 required parameters**; helper signatures with 2+ required parameters are rejected.

### Step 4 — Verbalizers

Verbalizers control how model structure is presented to the agent.

**`ModelVerbalizer` (default)** — returns relationship readings extracted from the model. By default, readings backed by auto-generated source-table column properties are filtered out, and the output is restricted to the model's traversal graph: identifier readings per concept plus readings whose rightmost field targets another entity concept. Primitive-typed property readings are dropped — the same information is reachable through `EXPLAIN(concept)`. Pass `include_source_columns=True` to restore the legacy emit-everything behavior.

`ModelVerbalizer` is the default and is used automatically when no verbalizer is specified. It is what you want for most deployments.

**`SourceCodeVerbalizer` (LEGACY — planned for deprecation)** — extends `ModelVerbalizer`. `explain_model` returns the standard relationship readings, while `explain_concept` returns Python source code from the modules you provide, filtered to definitions that reference the requested concept. Pass the model first, then the imported model **modules** that define it.

This interface is retained for backwards compatibility and is **not the recommended path for new deployments**. The default `ModelVerbalizer` combined with the structured per-concept view exposed by PyRel (identifiers, properties, relationships, data sources, and rule-defined predicates) and the `Concept.<member>` rule-body drill-down is the supported way to expose reasoning to the agent. Reach for `SourceCodeVerbalizer` only if you already depend on emitting raw Python source and need parity while migrating.

### Step 5 — QueryCatalog and Dynamic Queries (PREVIEW)

> The queries capability is in PREVIEW. Deployment requires `allow_preview=True`.

Without `QueryCatalog` (or `DynamicQueries`) wired into `ToolRegistry.add(..., queries=...)`, the agent can describe the model (via discovery and verbalization) but cannot execute any queries — `RAI_QUERY_MODEL` is not registered.

Two complementary surfaces ship under one capability:

- **Catalog queries** — pre-defined, vetted analytical functions built by domain experts. The agent picks one by `id` and supplies arguments.
- **Dynamic queries** — the agent authors a small JSON query spec at runtime against the model's queryable schema. Use for narrow exploratory analysis when no catalog query matches.

Both are exposed through `RAI_QUERY_MODEL`. **Recommended wiring** is `QueryCatalog(func1, func2, ..., model=model)` — the catalog routes the reserved id `"dynamic"` to a `DynamicQueries` over the same model internally. Catalog-only (`QueryCatalog(funcs...)`) and dynamic-only (`DynamicQueries(model)`) registries are both supported; use `CompositeQueries` for advanced layouts (e.g. multiple catalog providers).

Each catalog query function must:
- Return a `rai.Fragment` (a `rai.select(...)` expression) or `pandas.DataFrame`
- Have a clear **docstring** — used as the query description shown to the agent
- Have a `__name__` attribute — used as the query identifier (the name `"dynamic"` is reserved)

See [examples/model/queries.py](examples/model/queries.py) for a complete query definition.

Prefer **module-level zero-argument query functions** imported inside `init_tools()`. This keeps `__name__` and `__doc__` intact for `QueryCatalog` without wrappers or partials.

**Adding a new query:**
1. Define a module-level function in `queries.py` that returns a `rai.Fragment` or `pandas.DataFrame`. Give it a clear docstring — it becomes the description shown to the agent.
2. Add the function to the `QueryCatalog(...)` call inside `init_tools()` in `deploy.py`.
3. Redeploy with `deploy` (or `update` if the agent already exists).

**When to choose catalog vs dynamic.**

- Use **catalog queries** for high-value, opinionated entry points into advanced analysis that the agent should invoke directly rather than reconstruct from scratch — community detection outputs, graph metrics, scenario summaries, multi-hop region rollups, vetted analytical routines whose results you want surfaced reliably. Catalog queries carry the model author's judgment for the asks that matter most.
- Use **dynamic queries** (by passing `model=` to `QueryCatalog`) for the long tail — narrow filters, row-level lookups, simple aggregations the catalog doesn't anticipate. Dynamic queries are intentionally a small-result surface; the agent is instructed to write the answer query directly on the first attempt and probe column values only reactively, not proactively.

For open-ended dimensional analysis and ad hoc filtering/aggregation, Snowflake Semantic Views may also be a fit. `QueryCatalog` + dynamic queries is the right blend when the answers benefit from the semantic model's business logic, computed properties, and rules.

### Step 6 — CLI Subcommands

Wire the manager methods into CLI subcommands using `argparse`. Each command maps to a single manager call. See [examples/deploy.py](examples/deploy.py) for the complete implementation.

| Command | Manager method | Notes |
|---------|---------------|-------|
| `deploy` | `manager.deploy(init_tools=..., imports=discover_imports())` | Runs preflight, then creates schema, stage, sprocs, and agent |
| `update` | `manager.update(init_tools=..., imports=discover_imports())` | Updates sprocs without re-registering agent |
| `status` | `manager.status()` | Reports what exists |
| `chat` | `manager.chat().send(message)` | Test the deployed agent |
| `teardown` | `manager.cleanup()` | Removes all resources — **permanently loses SI conversation history** |
| `preflight` | `manager.preflight(init_tools=...)` | Probes grants without deploying |
| `setup-sql` | `manager.print_setup_sql(deployer_role=..., si_role=...)` | Emits a paste-ready GRANT block parameterized with the actual config |

`deploy()` calls `preflight()` automatically. Pass `skip_preflight=True` to bypass for fast iteration once the environment is known good. When `init_tools` is supplied to `preflight()` it additionally probes per-call DISCOVER/VERBALIZE/EXPLAIN sizes against the envelope budget; with `strict_payload_check=True` on `DeploymentConfig`, DISCOVER truncation escalates from warning to deploy-blocking error.

**`imports`** — `discover_imports()` recursively discovers local Python imports and packages them into the stored procedure. It excludes standard library and installed packages; the `relationalai` package is included automatically. It uses the **current working directory** as the project root and filters out anything outside it. This is why the canonical layout (see Quick Reference → *Expected project layout*) keeps the agent package and model package as siblings under `<project_root>` and expects you to invoke `python -m <agent_pkg>.deploy ...` from that root — with that setup, no extra import wiring is needed.

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

Pass this in place of `discover_imports()`: `manager.deploy(init_tools=init_tools, imports=_imports())`. Directory entries use `(path, module_name)` tuples so Snowpark registers them as top-level importable packages inside the sproc. `init_tools()` itself stays self-contained per Step 3 — **no `sys.path` manipulation inside `init_tools()`**. The tuple form already makes the package importable in the sproc; mutating `sys.path` there is a no-op inside the sproc and masks the real fix for local invocation.

**Workaround if you ignore the run-from-project-root guidance:** if you must invoke the deploy script from somewhere else and local imports fail, add a one-time `sys.path` fix at the *top of the deploy module* — not inside `init_tools()`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

This is a local-invocation crutch, not a deploy requirement. Prefer running from the project root.

**`extra_packages`** — optional parameter on `deploy()`/`update()` that specifies additional PyPI packages Snowflake installs in the sproc environment. Use this only for third-party libraries your model or query code depends on; `relationalai` and its declared dependencies are installed automatically.

If `agent_schema` is set, `deploy()`, `status()`, `chat()`, and `cleanup()` operate on the agent in that schema while the stored procedures and stage remain in `database`.`schema`.

---

## After Deployment

After a successful deploy, inform the user of these next steps:

1. **Verify** — run the `status` subcommand to confirm all sprocs are created.
2. **Test** — run the `chat` subcommand with a sample question (e.g., `"What can I ask about?"`) to confirm the agent responds correctly.
3. **Find the agent in Snowflake** — navigate to **AI & ML > Agents** in the Snowflake UI. The agent appears under `agent_schema` if you set it, otherwise under `database`.`schema`.
4. **Preview the agent** — click the agent name to open its detail page. Use the **Chat** tab to interact with it directly and verify it answers domain questions correctly.
5. **Expose it in Snowflake Intelligence** — if you deployed the agent directly to `SNOWFLAKE_INTELLIGENCE.AGENTS` via `agent_schema`, it is already in the SI schema. Otherwise, use **Add to Snowflake Intelligence** on the agent detail page to promote it.
6. **Monitor conversations** — the **Monitoring** tab on the agent detail page shows all conversations (both SI and programmatic via `manager.chat()`), including full tool-call traces for debugging.

---

## Debugging a Deployed Agent

A successful `deploy` means the sprocs and agent exist — it does *not* mean the agent answers correctly. Permission gaps, stale imports, an invalid `llm` choice, missing `allow_preview`, or a model that imports cleanly locally but fails inside the sproc sandbox all surface only at runtime, often as terse "tool error" messages in the agent's reply.

See [examples/debug.py](examples/debug.py) for a runnable script that performs the three checks below in order. Copy it alongside `deploy.py`, keep the configuration block in sync, and run `python -m <package>.debug` from the project root.

**1. Describe the agent.** Fetch the agent spec via the Snowflake API to confirm what's actually registered: the tool names, their input schemas, and the bound stored procedures. If a tool is missing from the spec, the orchestrator can't call it; if a tool resource points at the wrong schema, every call returns a "does not exist" error.

```python
described = manager._api.describe(
    manager.config.agent_database,
    manager.config.agent_schema_name,
    manager.config.agent_name,
)
# described.agent_spec.tools — list of registered tools
# described.agent_spec.tool_resources — sproc/identifier bindings
```

**2. Invoke each sproc directly.** Calling the RAI sprocs as plain SQL is the fastest way to read the underlying error message — Snowflake returns the import error, missing-grant message, or `Model` construction failure verbatim, instead of the agent wrapping it in a generic envelope. Call in dependency order:

```sql
CALL <db>.<schema>.RAI_DISCOVER_MODELS();
CALL <db>.<schema>.RAI_VERBALIZE_MODEL(<model_id>);
CALL <db>.<schema>.RAI_EXPLAIN_CONCEPT(<model_id>, '<concept_name>');
CALL <db>.<schema>.RAI_QUERY_MODEL(<model_id>, '{"id":"<query_id>","args":{}}');
```

`RAI_DISCOVER_MODELS` returns the `model_id` plus the catalog of available concepts and query ids — use its output to drive the remaining calls. If DISCOVER fails, none of the others can succeed; fix it first. Common direct-invocation failures:

- `does not exist or not authorized` on the sproc itself → the caller lacks `EXECUTE`, or the deployment role lacked `CREATE PROCEDURE` and the sproc was never created. Re-run `manager.preflight()`.
- Import or `ModuleNotFoundError` inside the sproc body → `init_tools()` references code outside the project root, or `discover_imports()` was invoked from the wrong CWD. See Step 6.
- `RAI_QUERY_MODEL does not exist` → `allow_preview=True` was not set on `DeploymentConfig`.
- "Invalid model" / unknown `llm` → the `llm` in `DeploymentConfig` is not available in this Snowflake region; pick a different Cortex-supported model.
- Sproc runs but the envelope contains a `kind: error` payload → read the `hint` field; it names the missing concept, query id, or grant.

**3. Trace one chat turn.** Send a known-good question and dump the tool calls, tool result envelopes, and orchestrator thinking. This reveals planning bugs (the agent invokes the wrong tool, or never calls `RAI_DISCOVER_MODELS` first) and shows how tool-result errors are reaching the orchestrator.

```python
response = manager.chat().send("What can I ask about?")
response.tool_calls()    # what the orchestrator asked for
response.tool_results()  # envelopes returned by the sprocs (errors land here)
response.raw["content"]  # includes `thinking` blocks with the orchestrator's plan
```

If you reach this step and the answers still look wrong but the sproc envelopes are clean, the issue is usually a verbalization or catalog-description gap, not a deployment failure — iterate on `init_tools()` and redeploy with `update`.

---

## Deployed Stored Procedures

Four CALLER'S RIGHTS stored procedures are created in the deployment schema (`database`.`schema`), even if the agent itself is created elsewhere via `agent_schema`:

| Sproc | Purpose | Maturity |
|-------|---------|----------|
| `RAI_DISCOVER_MODELS` | Lists registered RAI models, their key concepts, the catalog queries they expose, and whether they support dynamic queries | GA |
| `RAI_VERBALIZE_MODEL` | Returns the model's traversal graph (entity-targeted relationship readings + per-concept identifier readings) | GA |
| `RAI_EXPLAIN_CONCEPT` | Explains a single concept, a single catalog query (`q:<id>`), a computed-predicate drill-down (`Concept.<member>`), or — for dynamic-mode models — the full dynamic-query reference (`"dynamic"`) | GA |
| `RAI_QUERY_MODEL` | Executes a named catalog query (by id) or a dynamic query (`{"id":"dynamic","args":{"spec":{...}}}`) | PREVIEW |

All sprocs run under the **invoking user's privileges**, not the owner's — Snowflake's existing RBAC is the single source of truth for data governance across all agent interactions. No privilege escalation is possible.

Every sproc returns a uniform response envelope: `{content, kind, truncated, truncation_reason, applied_limit?}`. Errors land in the envelope too, as typed `{kind, path, available, hint}` payloads under `content`, so the agent has a single way to read both success and failure and can self-correct on the next turn without a round trip.

SI users need:

| Privilege | Purpose |
|-----------|---------|
| `USAGE` on warehouse | Execute sprocs |
| `USE AI FUNCTIONS` on account | Access Cortex AI functions (granted to `PUBLIC` by default) |
| `database role snowflake.cortex_user` | Access Cortex services (granted to `PUBLIC` by default) |
| `database role snowflake.pypi_repository_user` | Install Python packages in sproc environment |
| `application role relationalai.rai_user` | Access the RAI Native App at sproc runtime |
| `USAGE` on `S3_RAI_INTERNAL_BUCKET_EGRESS_INTEGRATION` | Network egress to RAI services from inside the sproc |
| `USAGE` on the relevant databases and schemas | Access the agent schema plus any deployment/data schemas it touches |
| `SELECT` on tables | Read data accessed by the model |
| `EXECUTE` on stored procedures | Invoke RAI tools in the deployment schema |

Emit a paste-ready SQL block for an admin with `manager.print_setup_sql(deployer_role="MY_DEPLOYER", si_role="MY_SI")`.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `use schema` fails during deploy | Deployment schema doesn't exist | Run `CREATE SCHEMA IF NOT EXISTS` before deploying. If `agent_schema` is different, ensure that schema exists and the deployer can use it too |
| Object "does not exist" errors from Snowflake | Role lacks required privileges — Snowflake reports missing permissions as "does not exist" | Run `manager.preflight()` to get a named-grant fix list; `manager.print_setup_sql(deployer_role=...)` emits a paste-ready block |
| Agent does not show up where expected in the UI | Agent was created in `database`.`schema`, not the SI schema | Set `agent_schema="SNOWFLAKE_INTELLIGENCE.AGENTS"` or promote the deployed agent from **AI & ML > Agents** in the UI |
| `agent_schema` validation fails | Value is not a two-part `DATABASE.SCHEMA` name | Use a fully qualified two-part name such as `SNOWFLAKE_INTELLIGENCE.AGENTS` |
| `QueryCatalog` rejects a query definition | Wrapped queries lost `__name__` or `__doc__` metadata, or the function name is `"dynamic"` | Prefer module-level query functions with docstrings; avoid `functools.partial`; rename functions away from the reserved id `"dynamic"` |
| Sproc fails at runtime with table-not-found | Model references a table unavailable in the sproc context | Restructure entity seeding to make that table optional |
| `RAI_QUERY_MODEL` not available | `allow_preview` not set | Set `allow_preview=True` in `DeploymentConfig` |
| Agent answers describe the model but can't run dynamic queries | `QueryCatalog` constructed without `model=` | Pass `model=...` to `QueryCatalog` to enable the dynamic path alongside the catalog |
| `init_tools` is rejected or fails with stale state | Closed over local runtime objects or declared 2+ required parameters | Keep `init_tools` self-contained and use only the supported 0-param (recommended) or 1-param (legacy) forms |
| Agent can't explain business rules | Per-concept rule signatures alone aren't enough for the question being asked | Drill via `EXPLAIN("Concept.<member>")` for rule bodies; `SourceCodeVerbalizer` is a legacy escape hatch retained for migration |
| `discover_imports()` misses model code | Model package lives outside CWD, or needs a specific sproc-visible module name | Run the deploy script from the project root; for exceptions, use an explicit `_imports()` list with `(path, module_name)` tuples — see Step 6 |
| Preflight warns about DISCOVER truncation | Catalog has many queries and/or prose-rich descriptions | Trim descriptions or split into multiple registered models. Set `strict_payload_check=True` to make DISCOVER truncation block deploys |
| Snowflake error during `deploy()` after preflight passed | Race or grant edge case | Re-run `manager.preflight()`; the report formats a SQL fix block. For one-off iteration, `deploy(skip_preflight=True)` after fixing |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| **Deployment script** | **Complete CLI with preflight/setup-sql/deploy/update/status/chat/teardown — primary reference. Uses the recommended catalog + dynamic queries form (level 2); see Step 3 for level 1 and level 3 registry shapes** | [**examples/deploy.py**](examples/deploy.py) |
| Debug script | Describes the deployed agent, calls each sproc directly, and traces a chat turn. Run after a successful `deploy` when the agent misbehaves at runtime | [examples/debug.py](examples/debug.py) |
| Model modules | Core, computed, and query modules for the recommended zero-arg `init_tools()` pattern | [examples/model/](examples/model/) |
