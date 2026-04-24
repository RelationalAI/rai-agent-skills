# RelationalAI-Cortex Integration Examples

For full documentation — configuration, privileges, verbalizers, queries, and lifecycle management — see [SKILL.md](../SKILL.md).

## Examples

| Example | File | Description |
|---------|------|-------------|
| Deployment Script | `deploy.py` | Primary reference: CLI lifecycle management using the recommended zero-arg `init_tools()` pattern. Configures the full level-3 registry (verbalizer + queries) |
| Model modules | `model/` | Core, computed, and query modules referenced by `init_tools()` |

`deploy.py` is a reference implementation intended to be copied into the user's
own project package. Adjust the package imports and Snowflake config values
before running it. For the lighter-weight registry shapes (default, verbalizer-only),
see Step 3 of [SKILL.md](../SKILL.md).
