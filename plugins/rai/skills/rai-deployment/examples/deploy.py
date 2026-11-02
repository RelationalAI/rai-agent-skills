"""
Deployment script - deploy, update, status, chat, teardown, preflight, or
emit setup SQL for a Cortex agent.

The agent reads a model already deployed with PyRel deploy mode
(`rai models deploy`) at MODEL_SCHEMA. Deploy the model first.

Usage:
    python -m <package>.deploy deploy
    python -m <package>.deploy update
    python -m <package>.deploy status
    python -m <package>.deploy chat "What can I ask about?"
    python -m <package>.deploy teardown
    python -m <package>.deploy preflight
    python -m <package>.deploy setup-sql --deployer-role MY_ROLE [--si-role MY_SI]
"""
import argparse

from rich.console import Console
from rich.pretty import Pretty
from snowflake import snowpark

from relationalai.config import create_config, SnowflakeConnection
from relationalai.agent.cortex import (
    AgentConfig,
    CortexAgentManager,
    DefaultTool,
    ModelDeployment,
    QueryCatalog,
    discover_imports,
)

console = Console()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AGENT_NAME = "EXAMPLE_AGENT"
TOOLS_SCHEMA = "EXAMPLE.CUSTOMERS_AGENT"  # sprocs, stage, and the agent
MODEL_SCHEMA = "EXAMPLE.CUSTOMERS"  # the model's deployment.schema
AGENT_SCHEMA = None  # e.g. "SNOWFLAKE_INTELLIGENCE.AGENTS"
WAREHOUSE = "TEAM_ECO"


def _build_manager() -> CortexAgentManager:
    session: snowpark.Session = create_config().get_session(SnowflakeConnection)
    return CortexAgentManager(
        session=session,
        config=AgentConfig(
            agent_name=AGENT_NAME,
            tools_schema=TOOLS_SCHEMA,
            model_deployment=ModelDeployment(schema=MODEL_SCHEMA),
            agent_schema=AGENT_SCHEMA,
            warehouse=WAREHOUSE,
            allow_preview=True,
        ),
    )


# ---------------------------------------------------------------------------
# init_tools - executed inside each sproc invocation.
#
# Zero-arg and self-contained: import model modules inside the function so
# they initialize within the sproc session, and don't close over local
# runtime state (sessions, connections, dataframes, etc.).
#
# Returns one DefaultTool for the one model this agent serves, with the
# default ModelVerbalizer plus catalog + dynamic queries: passing `model=`
# to QueryCatalog lets the agent author dynamic JSON specs against the
# model's queryable schema when no catalog query fits.
# ---------------------------------------------------------------------------
def init_tools():
    # `computed` registers ltv / ValueSegment / value_segment / profit
    # onto the core model; `segment_summary` reads them.
    from .model import computed, core, queries  # noqa: F401

    return DefaultTool(
        model=core.model,
        description="Customers and orders",
        queries=QueryCatalog(queries.segment_summary, model=core.model),
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_deploy(manager: CortexAgentManager) -> None:
    console.print(
        f"Deploying agent [bold]{AGENT_NAME}[/bold] to [bold]{TOOLS_SCHEMA}[/bold] "
        f"over the model deployed at [bold]{MODEL_SCHEMA}[/bold] ..."
    )
    manager.deploy(init_tools=init_tools, imports=discover_imports())
    console.print(Pretty(manager.status()))


def cmd_update(manager: CortexAgentManager) -> None:
    console.print(f"Updating stored procedures for [bold]{AGENT_NAME}[/bold] ...")
    manager.update(init_tools=init_tools, imports=discover_imports())
    console.print(Pretty(manager.status()))


def cmd_status(manager: CortexAgentManager) -> None:
    console.print(Pretty(manager.status()))


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    chat = manager.chat()
    response = chat.send(message)
    console.print(response.full_text())


def cmd_teardown(manager: CortexAgentManager) -> None:
    console.print(f"Tearing down agent [bold]{AGENT_NAME}[/bold] and its sprocs in [bold]{TOOLS_SCHEMA}[/bold] ...")
    console.print("[yellow]WARNING: this permanently deletes SI conversation history.[/yellow]")
    manager.cleanup()
    console.print(Pretty(manager.status()))


def cmd_preflight(manager: CortexAgentManager) -> None:
    report = manager.preflight(init_tools=init_tools)
    console.print(report.format(config=manager.config, role=report.role))


def cmd_setup_sql(manager: CortexAgentManager, deployer_role: str, si_role: str | None) -> None:
    console.print(manager.print_setup_sql(deployer_role=deployer_role, si_role=si_role))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the Cortex agent lifecycle.")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy", help="Preflight, then create stage, sprocs, and agent")
    sub.add_parser("update", help="Update sprocs without re-registering the agent")
    sub.add_parser("status", help="Print deployment status")

    chat_p = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")

    sub.add_parser("teardown", help="Remove all agent resources")
    sub.add_parser("preflight", help="Probe grants and the model deployment without deploying")

    setup_p = sub.add_parser("setup-sql", help="Emit a paste-ready GRANT block")
    setup_p.add_argument("--deployer-role", default="<your_role>")
    setup_p.add_argument("--si-role", default=None)

    args = parser.parse_args()
    manager = _build_manager()

    commands = {
        "deploy": lambda: cmd_deploy(manager),
        "update": lambda: cmd_update(manager),
        "status": lambda: cmd_status(manager),
        "chat": lambda: cmd_chat(manager, args.message),
        "teardown": lambda: cmd_teardown(manager),
        "preflight": lambda: cmd_preflight(manager),
        "setup-sql": lambda: cmd_setup_sql(manager, args.deployer_role, args.si_role),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
