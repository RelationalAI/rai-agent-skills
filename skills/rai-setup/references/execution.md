## Execution Configuration

Controls SDK-level behavior: observability, retries, compiler strictness, and data loading defaults.

### Metrics and logging

```python
# View collected metrics after running a query
from relationalai.client import connect_sync
from relationalai.semantics import Model

client = connect_sync()
model = Model("MyModel")
model.select("hello world").to_df()
print(client.execution_metrics.counters)
print(client.execution_metrics.timings_ms)

# Enable structured logs (configure Python logging to display output)
import logging
logging.getLogger("relationalai.client.execution").setLevel(logging.INFO)
```

Enable both in `raiconfig.yaml`:
```yaml
execution:
  metrics: true
  logging: true
```

### Retries

Automatic re-attempts on transient failures. `max_attempts` is the total count including the first try:

```yaml
execution:
  retries:
    enabled: true
    max_attempts: 5
    base_delay_s: 0.25
    max_delay_s: 5.0
    jitter: 0.2
```

### Compiler strictness

```yaml
compiler:
  strict: true           # fail fast on ambiguous types — recommended for CI/production
  soft_type_errors: true # treat type errors as warnings — use in notebooks only
```

Use `strict: true` in CI. Use `soft_type_errors: true` only during rapid iteration — it hides real type problems.

### Data loading defaults

See the `data:` block in [raiconfig-yaml.md](raiconfig-yaml.md) for the full field list and defaults.

**Cautions:**
- `check_column_types: false` speeds up loading but silently allows type mismatches — keep `true` in CI.
- `ensure_change_tracking: true` modifies tables (requires OWNERSHIP) — leave `false` unless you intend this side effect.
- `data_freshness_mins` unset means queries wait until streams are fully synced; setting a value trades freshness for latency.
