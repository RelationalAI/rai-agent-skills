# RelationalAI-Cortex Integration Examples

For full documentation — configuration, privileges, verbalizers, queries, and lifecycle management — see [cortex-agents.md](../references/cortex-agents.md).

## Examples

| Example | File | Description |
|---------|------|-------------|
| Deployment Script | `deploy.py` | Primary reference: CLI lifecycle management using the recommended zero-arg `init_tools()` pattern. Configures the default `ModelVerbalizer` plus catalog + dynamic queries (Step 3, level 2 of the progression) via `QueryCatalog(..., model=...)` |
| Debug Script | `debug.py` | Describes the deployed agent, invokes each RAI sproc directly, and traces a chat turn. Run after a successful `deploy` when the agent returns errors or unexpected answers — see the *Debugging a Deployed Agent* section of [cortex-agents.md](../references/cortex-agents.md) |
| Model modules | `model/` | Core, computed, and query modules referenced by `init_tools()` |

`deploy.py` is a reference implementation intended to be copied into the user's
own project package. Adjust the package imports and Snowflake config values
before running it. For the bare default-tools shape (no queries) or the
`SourceCodeVerbalizer`-enabled shape, see Step 3 of [cortex-agents.md](../references/cortex-agents.md).
