# Usage: python -m example.cortex.cortex_verbalizer
# This example shows using the SourceCodeVerbalizer, which provides your model
# definition code as context to the agent. Use it to enable explanations
# of complex business rules, and include crucial context from your comments.
from snowflake import snowpark

from relationalai.config import SnowflakeConnection, create_config
from relationalai.agent.cortex import CortexAgentManager, DeploymentConfig, discover_imports, ToolRegistry, \
    SourceCodeVerbalizer

# Create session using role for deployment
session: snowpark.Session = create_config().get_session(SnowflakeConnection)

# Configure manager
manager = CortexAgentManager(
    session=session,
    config=DeploymentConfig(
        agent_name="EXAMPLE_VERBALIZER",  # Unique name for the agent
        database="EXAMPLE",  # Snowflake database for deployment (sprocs & agent)
        schema="CORTEX_VERBALIZER",  # Snowflake schema for deployment (sprocs & agent)
        warehouse="TEAM_ECO"))  # Warehouse for RAI tool execution (SI users need USAGE)


# Initialize RAI Tools
# - This function is executed during each sproc invocation
#   It must be self-contained — don't close over local
#   runtime state (sessions, connections, dataframes, etc.).
def init_tools():
    # IMPORTANT only import your RelationalAI Model and dependent code
    #           inside init_tools so it runs within the sproc session.
    from .model import core, computed
    return ToolRegistry().add(
        model=core.model,  # Expose model through tools
        description="Customers and orders",
        # Provide source code as context to agent
        verbalizer=SourceCodeVerbalizer(core.model, core, computed))

# Deploy
manager.deploy(
    init_tools=init_tools,  # Initialize RAI Tools
    imports=discover_imports())  # Specify local python modules to package into sproc
print(manager.status())

chat = manager.chat()
r = chat.send("What can I ask about?")
print(r.full_text())

# Delete resources
# manager.cleanup()
# print(manager.status())
