# RelationalAI-Cortex Integration Examples

For full documentation — configuration, privileges, verbalizers, queries, and lifecycle management — see [SKILL.md](../SKILL.md).

## Examples

| Example | File | Description |
|---------|------|-------------|
| Default | `cortex.py` | Minimal setup using built-in model verbalization |
| Verbalizer | `cortex_verbalizer.py` | Adds `SourceCodeVerbalizer` for richer model context |
| Verbalizer + Queries | `cortex_verbalizer_queries.py` | Adds `QueryCatalog` for pre-defined queries (PREVIEW) |

Run any example with:

```bash
python -m example.cortex.cortex
python -m example.cortex.cortex_verbalizer
python -m example.cortex.cortex_verbalizer_queries
```
