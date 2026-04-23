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

```yaml
data:
  wait_for_stream_sync: true      # wait for streams to sync before queries (default: true)
  data_freshness_mins: 5          # allow queries if data is within N mins (default: unset = fully synced; max 30240 = 3 weeks)
  query_timeout_mins: 10          # client-side timeout in minutes (default: unset = no timeout)
  ensure_change_tracking: false   # auto-enable change tracking on tables (requires OWNERSHIP; default: false)
  check_column_types: true        # validate column types on load (default: true — keep enabled in CI)
  download_url_type: internal     # "internal" (default) or "external" (for access outside Snowflake)
```

**Caution:** `check_column_types: false` speeds up loading but silently allows type mismatches. `ensure_change_tracking: true` modifies tables — only enable if you have OWNERSHIP.
