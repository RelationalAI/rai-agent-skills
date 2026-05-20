"""
Debug a deployed Cortex agent.

Run this after a successful ``deploy`` if the agent is returning errors or
unexpected answers. It connects to the existing deployment and:

1. Describes the agent via the Snowflake API to show the registered tool
   resources and the agent spec the orchestrator actually sees.
2. Invokes each RAI tool sproc directly so any runtime error (missing grants,
   bad imports, invalid model code, payload truncation, preview-flag
   mismatch) surfaces in plain SQL output instead of being buried inside a
   tool-call trace.
3. Sends one chat turn and dumps tool calls, tool results, and the
   orchestrator's thinking so you can see exactly where a failed turn went
   wrong.

Adjust the configuration block at the top to match your deployment, then run
``python -m <package>.debug`` from the project root.
"""
import json
import sys

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from snowflake import snowpark

from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig
from relationalai.config import SnowflakeConnection, create_config

# ---------------------------------------------------------------------------
# Configuration — keep in sync with deploy.py
# ---------------------------------------------------------------------------
AGENT_NAME = "EXAMPLE_AGENT"
DATABASE = "EXAMPLE"
SCHEMA = "CORTEX_DEMO"
AGENT_SCHEMA = None  # e.g. "SNOWFLAKE_INTELLIGENCE.AGENTS"
WAREHOUSE = "TEAM_ECO"

# A sample question the agent should be able to answer.
QUESTION = "What can I ask about?"

console = Console()


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    return CortexAgentManager(
        session=session,
        config=DeploymentConfig(
            agent_name=AGENT_NAME,
            database=DATABASE,
            schema=SCHEMA,
            agent_schema=AGENT_SCHEMA,
            warehouse=WAREHOUSE,
            allow_preview=True,
        ),
    )


def _run_sql(session: snowpark.Session, sql: str) -> list[snowpark.Row]:
    """Run a SQL statement and return its rows, or raise with the error."""
    console.print(Syntax(sql, "sql", theme="ansi_dark", word_wrap=True))
    return session.sql(sql).collect()


def describe_agent(manager: CortexAgentManager) -> None:
    """Show the agent spec as Snowflake sees it.

    The spec lists each registered tool, its input schema, and the bound
    stored procedure. If a sproc is missing or pointing at the wrong schema,
    the agent will return cryptic "tool not found" errors at runtime — the
    spec is where you confirm what's actually wired up.
    """
    console.print(Rule("[bold]Agent spec[/bold]"))
    try:
        described = manager._api.describe(
            manager.config.agent_database,
            manager.config.agent_schema_name,
            manager.config.agent_name,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(Panel.fit(f"describe failed: {exc}", style="red"))
        return

    meta = Table(box=box.SIMPLE, show_header=False)
    meta.add_row("owner", described.owner)
    meta.add_row("database", described.database_name)
    meta.add_row("schema", described.schema_name)
    meta.add_row("name", described.name)
    console.print(meta)

    spec = described.agent_spec
    if spec is None:
        console.print("[yellow]agent_spec missing from describe response[/yellow]")
        return

    tools = Table(title="Registered tools", box=box.SIMPLE_HEAVY)
    tools.add_column("name")
    tools.add_column("type")
    tools.add_column("resource / sproc")
    for tool in spec.tools or []:
        tool_dict = tool.to_dict() if hasattr(tool, "to_dict") else dict(tool)
        spec_block = tool_dict.get("tool_spec") or tool_dict
        name = spec_block.get("name", "?")
        kind = spec_block.get("type", "?")
        resource = ""
        for resource_block in (spec.tool_resources or {}).values() if spec.tool_resources else []:
            if isinstance(resource_block, dict) and resource_block.get("name") == name:
                resource = resource_block.get("execution_environment", {}).get("query_timeout", "")
                break
        identifier = (spec.tool_resources or {}).get(name, {}).get("identifier") if spec.tool_resources else None
        tools.add_row(name, kind, identifier or resource or "")
    console.print(tools)


def invoke_sprocs(session: snowpark.Session) -> None:
    """Call each RAI tool sproc directly.

    A direct CALL surfaces grant errors, import errors, and model
    construction failures in a single SQL error message — much faster than
    waiting for the orchestrator to fail mid-turn. Run these in order:
    DISCOVER first to learn ``model_id`` and catalog query ids, then drill
    in with VERBALIZE, EXPLAIN, and QUERY.
    """
    console.print(Rule("[bold]Invoking sprocs directly[/bold]"))

    fq = f"{DATABASE}.{SCHEMA}"

    # 1. RAI_DISCOVER_MODELS — no args. Returns model_id, concepts, catalog.
    console.print(Rule("RAI_DISCOVER_MODELS", style="dim"))
    try:
        rows = _run_sql(session, f"CALL {fq}.RAI_DISCOVER_MODELS()")
        payload = json.loads(rows[0][0]) if rows else None
        console.print(Pretty(payload, max_depth=4))
        model_id = (payload or {}).get("content", [{}])[0].get("model_id", 1)
    except Exception as exc:  # noqa: BLE001
        console.print(Panel.fit(f"DISCOVER failed: {exc}", style="red"))
        return  # Nothing else will succeed without a model_id.

    # 2. RAI_VERBALIZE_MODEL(model_id) — emits the traversal graph.
    console.print(Rule("RAI_VERBALIZE_MODEL", style="dim"))
    try:
        rows = _run_sql(session, f"CALL {fq}.RAI_VERBALIZE_MODEL({model_id})")
        console.print(Pretty(json.loads(rows[0][0]), max_depth=3))
    except Exception as exc:  # noqa: BLE001
        console.print(Panel.fit(f"VERBALIZE failed: {exc}", style="red"))

    # 3. RAI_EXPLAIN_CONCEPT(model_id, name). Pick a concept from DISCOVER
    #    output and substitute it here. The reserved name "dynamic" returns
    #    the dynamic-query reference for preview-mode deployments.
    console.print(Rule("RAI_EXPLAIN_CONCEPT", style="dim"))
    concept_name = "Customer"  # <-- replace with a concept from DISCOVER
    try:
        rows = _run_sql(
            session,
            f"CALL {fq}.RAI_EXPLAIN_CONCEPT({model_id}, '{concept_name}')",
        )
        console.print(Pretty(json.loads(rows[0][0]), max_depth=4))
    except Exception as exc:  # noqa: BLE001
        console.print(Panel.fit(f"EXPLAIN failed: {exc}", style="red"))

    # 4. RAI_QUERY_MODEL(model_id, json_spec). Requires allow_preview=True.
    #    The spec below uses a catalog id; for dynamic queries pass
    #    {"id": "dynamic", "args": {"spec": {...}}}.
    console.print(Rule("RAI_QUERY_MODEL", style="dim"))
    query_spec = json.dumps({"id": "segment_summary", "args": {}})
    try:
        rows = _run_sql(
            session,
            f"CALL {fq}.RAI_QUERY_MODEL({model_id}, '{query_spec}')",
        )
        console.print(Pretty(json.loads(rows[0][0]), max_depth=4))
    except Exception as exc:  # noqa: BLE001
        console.print(Panel.fit(f"QUERY failed: {exc}", style="red"))


def chat_trace(manager: CortexAgentManager, question: str) -> None:
    """Send one turn and dump tool calls, tool results, and thinking.

    Use this to see how the orchestrator is sequencing its tool calls and to
    read tool-result envelopes — failures land in the envelope as
    ``{kind, path, available, hint}`` payloads under ``content``.
    """
    console.print(Rule(f"[bold]Chat turn[/bold] — {question!r}"))

    chat = manager.chat()
    response = chat.send(question)

    console.print(Rule("tool calls", style="dim"))
    for tc in response.tool_calls():
        console.print(f"[cyan]{tc.name}[/cyan]")
        console.print(Pretty(tc.arguments, max_depth=4))

    console.print(Rule("tool results", style="dim"))
    for tr in response.tool_results():
        console.print(f"[cyan]{tr.name}[/cyan]")
        raw = tr.json_result()
        if raw is None:
            console.print(f"  (no json_result; raw text head: {str(tr)[:500]})")
            continue
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                pass
        console.print(Pretty(raw, max_depth=4))

    console.print(Rule("thinking", style="dim"))
    for item in response.raw.get("content", []) or []:
        if item.get("type") != "thinking":
            continue
        body = item.get("thinking")
        text = body.get("text") if isinstance(body, dict) else str(body or "")
        console.print(Panel(text or "", border_style="dim"))

    console.print(Rule("final text", style="dim"))
    console.print(response.full_text())


def main() -> int:
    manager = _build_manager()
    console.print(Panel.fit(Pretty(manager.status()), title="Status"))

    describe_agent(manager)
    invoke_sprocs(manager._session)
    chat_trace(manager, QUESTION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
