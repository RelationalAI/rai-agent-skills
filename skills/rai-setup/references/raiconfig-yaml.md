## raiconfig.yaml Reference

**Primary file:** `raiconfig.yaml` (also accepts `raiconfig.yml`). TOML (`raiconfig.toml`) is deprecated with a warning.

**Auto-discovery:** `create_config()` walks upward from CWD to find the config file.

**Fallback sources** (when no `raiconfig.yaml` found): `raiconfig.toml` (deprecated) → `~/.snowflake/config.toml` → `~/.dbt/profiles.yml`.

**Transition note (as of Feb 2026):** Use `raiconfig.yaml` for all new projects. See the `Both raiconfig.toml and .yaml present` pitfall in SKILL.md for the precedence gotcha.

### Full YAML structure

```yaml
default_connection: sf
active_profile: dev          # or set RAI_PROFILE env var

connections:
  sf:
    type: snowflake
    authenticator: username_password
    account: my_account
    warehouse: my_warehouse
    user: my_user
    password: ${SNOWFLAKE_PASSWORD}    # env var substitution
    role: my_role                      # optional
    database: my_database              # optional
    schema: my_schema                  # optional

reasoners:
  backend: sql                         # "sql" (default) or "direct_access"
  logic:
    name: team_logic                   # optional; identifier for this reasoner
    size: HIGHMEM_X64_S                # used when creating the reasoner
    use_lqp: true
    emit_constraints: false
  predictive:
    name: team_predictive              # optional
    size: HIGHMEM_X64_S
  prescriptive:
    name: team_prescriptive            # optional
    size: HIGHMEM_X64_S

data:
  wait_for_stream_sync: true           # wait for streams before queries (default true)
  data_freshness_mins: 5               # allow queries if data is within N mins (default unset = must be fully synced; max 30240 = 3 weeks)
  query_timeout_mins: 10               # client-side timeout (default unset = no timeout)
  ensure_change_tracking: false        # auto-enable change tracking on tables read (default false; requires OWNERSHIP)
  check_column_types: true             # validate column types on load (default true)
  download_url_type: external          # "internal" (default) or "external" (accessible outside Snowflake)

compiler:
  strict: false
  soft_type_errors: false

model:
  schema: analytics                    # install schema for SQL views/tables
  implicit_properties: true            # allow undeclared properties on first access
  keep: true
  isolated: true

execution:
  metrics: false                       # collect SDK timing/counter metrics (default false)
  logging: false                       # emit structured execution logs to Python logger (default false)
  retries:
    enabled: false
    max_attempts: 3                    # total attempts including first try
    base_delay_s: 0.25
    max_delay_s: 5.0
    jitter: 0.2                        # random jitter fraction added to each delay

debug:
  show_full_traces: false

profile:
  dev:
    connections:
      sf:
        warehouse: dev_warehouse
  prod:
    connections:
      sf:
        warehouse: prod_warehouse
```

### Environment variable syntax
Use `${VAR_NAME}` in any string value.

### Profile overlays
Profile selection priority (highest wins): `create_config(active_profile=...)` > `RAI_PROFILE` env var > `active_profile` in YAML. The selected profile's values merge on top of the base config.

### Model-level config fields

Set under `model:` in YAML, or pass via `create_config(model={...})`:

| Field | Default | Purpose |
|---|---|---|
| `schema` | `None` | Install schema for SQL views/tables |
| `implicit_properties` | `true` | Allow undeclared properties on first access |
| `keep` | `true` | Keep model after execution |
| `isolated` | `true` | Run model in isolated mode |
