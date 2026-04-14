# RelationalAI-Cortex Integration Examples

For full documentation — configuration, privileges, verbalizers, queries, and lifecycle management — see [SKILL.md](../SKILL.md).

## Examples

| Example | File | Description |
|---------|------|-------------|
| Deployment Script | `deploy.py` | Primary reference: CLI lifecycle management using the recommended zero-arg `init_tools()` pattern |
| Default | `cortex.py` | Minimal setup using built-in model verbalization |
| Verbalizer | `cortex_verbalizer.py` | Adds `SourceCodeVerbalizer` for richer model context |
| Verbalizer + Queries | `cortex_verbalizer_queries.py` | Adds `QueryCatalog` for pre-defined queries (PREVIEW) |

These files are reference implementations intended to be copied into the user's
own project package. Adjust the package imports and Snowflake config values
before running them.
