"""
Deployment script - deploy, update, status, chat, or teardown a Cortex agent.

Usage:
    python -m <package>.deploy deploy
    python -m <package>.deploy update
    python -m <package>.deploy status
    python -m <package>.deploy chat "What can I ask about?"
    python -m <package>.deploy teardown
"""
import argparse

from snowflake import snowpark

from relationalai.config import create_config, SnowflakeConnection
from relationalai.agent.cortex import (
    CortexAgentManager,
    DeploymentConfig,
    ToolRegistry,
    SourceCodeVerbalizer,
    QueryCatalog,
    discover_imports,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AGENT_NAME = "EXAMPLE_VERBALIZER_QUERIES"
DATABASE = "EXAMPLE"
SCHEMA = "CORTEX_VERBALIZER_QUERIES"
AGENT_SCHEMA = None  # e.g. "SNOWFLAKE_INTELLIGENCE.AGENTS"
WAREHOUSE = "TEAM_ECO"


def _agent_location() -> str:
    return AGENT_SCHEMA or f"{DATABASE}.{SCHEMA}"


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


# ---------------------------------------------------------------------------
# init_tools - executed inside each sproc invocation.
#
# Recommended form: zero-arg init_tools() that imports model modules inside
# the function so they initialize within the sproc session.
# Must be self-contained: don't close over local runtime state
# (sessions, connections, dataframes, etc.).
# ---------------------------------------------------------------------------
def init_tools():
    # IMPORTANT: import your model code inside init_tools so it is
    #            resolved from the packaged sproc code, not local state.
    from .model import core, computed, queries

    return ToolRegistry().add(
        model=core.model,
        description="Customers and orders",
        verbalizer=SourceCodeVerbalizer(core.model, core, computed),
        queries=QueryCatalog(queries.segment_summary),
    )


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_deploy(manager: CortexAgentManager) -> None:
    print(
        f"Deploying sprocs to {DATABASE}.{SCHEMA} "
        f"and agent {AGENT_NAME} to {_agent_location()} ..."
    )
    manager.deploy(
        init_tools=init_tools,
        imports=discover_imports(),
        extra_packages=["httpx"],
    )
    print(manager.status())


def cmd_update(manager: CortexAgentManager) -> None:
    print(f"Updating stored procedures for {AGENT_NAME} ...")
    manager.update(
        init_tools=init_tools,
        imports=discover_imports(),
        extra_packages=["httpx"],
    )
    print(manager.status())


def cmd_status(manager: CortexAgentManager) -> None:
    print(manager.status())


def cmd_chat(manager: CortexAgentManager, message: str) -> None:
    chat = manager.chat()
    response = chat.send(message)
    print(response.full_text())


def cmd_teardown(manager: CortexAgentManager) -> None:
    print(
        f"Tearing down agent {AGENT_NAME} from {_agent_location()} "
        f"and sprocs from {DATABASE}.{SCHEMA} ..."
    )
    print("WARNING: this permanently deletes SI conversation history.")
    manager.cleanup()
    print(manager.status())


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the Cortex agent lifecycle.")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    sub.add_parser("deploy", help="Create schema, stage, sprocs, and agent")
    sub.add_parser("update", help="Update sprocs without re-registering the agent")
    sub.add_parser("status", help="Print deployment status")

    chat_p = sub.add_parser("chat", help="Send a message to the deployed agent")
    chat_p.add_argument("message", help="Message to send")

    sub.add_parser("teardown", help="Remove all agent resources")

    args = parser.parse_args()
    manager = _build_manager()

    commands = {
        "deploy": lambda: cmd_deploy(manager),
        "update": lambda: cmd_update(manager),
        "status": lambda: cmd_status(manager),
        "chat": lambda: cmd_chat(manager, args.message),
        "teardown": lambda: cmd_teardown(manager),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
