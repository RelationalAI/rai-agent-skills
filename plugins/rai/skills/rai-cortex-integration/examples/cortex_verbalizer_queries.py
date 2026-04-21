# Usage: python -m example.cortex.cortex_verbalizer_queries
# This example shows using all configurable capabilites, including
# pre-baked queries which are in Preview.
from snowflake import snowpark

from relationalai.config import SnowflakeConnection, create_config
from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig, discover_imports, ToolRegistry, \
    SourceCodeVerbalizer, QueryCatalog

# Create session using role for deployment
session: snowpark.Session = create_config().get_session(SnowflakeConnection)

# Configure manager
manager = CortexAgentManager(
    session=session,
    config=DeploymentConfig(
        agent_name="EXAMPLE_VERBALIZER_QUERIES",  # Unique name for the agent
        database="EXAMPLE",  # Snowflake database for deployment (sprocs & agent)
        schema="CORTEX_VERBALIZER_QUERIES",  # Snowflake schema for deployment (sprocs & agent)
        warehouse="TEAM_ECO",  # Warehouse for RAI tool execution (SI users need USAGE)
        allow_preview=True,  # Query capability is in Preview
    ))

# Initialize RAI Tools
# - This function is executed during each sproc invocation
#   It must be self-contained — don't close over local
#   runtime state (sessions, connections, dataframes, etc.).
def init_tools():
    # IMPORTANT only import your RelationalAI Model and dependent code
    #           inside init_tools so it runs within the sproc session.
    from .model import core, computed, queries
    return ToolRegistry().add(
        model=core.model,  # Expose model through tools
        description="Customers and orders",
        # Provide source code as context to agent
        verbalizer=SourceCodeVerbalizer(core.model, core, computed),
        # Register pre-defined queries (PREVIEW)
        queries=QueryCatalog(queries.segment_summary))

# Deploy
manager.deploy(
    init_tools=init_tools,  # Initialize RAI Tools
    imports=discover_imports())  # Specify local python modules to package into sproc
print(manager.status())

chat = manager.chat()
r = chat.send("Explain how customers are segmented, and show me the topline metrics")
print(r.full_text())

# Delete resources
# manager.cleanup()
# print(manager.status())
