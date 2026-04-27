## Reasoner Configuration

### Backend selection

```yaml
reasoners:
  backend: sql              # default -- uses Snowpark SQL
  # backend: direct_access  # HTTP-based; requires direct_access_base_url (mandatory when using direct_access)
  # direct_access_base_url: https://reasoners.example.com
```

### Engine sizes

| Platform | Valid sizes |
|---|---|
| AWS | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_L` |
| Azure | `HIGHMEM_X64_S`, `HIGHMEM_X64_M`, `HIGHMEM_X64_SL` |

### Per-reasoner settings

```yaml
reasoners:
  logic:
    name: team_logic                 # optional; if named reasoner exists, PyRel uses it as-is (ignores size)
    size: HIGHMEM_X64_S              # used only when auto-creating (name set but reasoner doesn't exist)
    use_lqp: true                    # LQP for rule execution (default true)
    emit_constraints: true           # emit constraint reports
    incremental_maintenance: "off"   # "off" (default), "auto", or "all"
    lqp:
      semantics_version: "1"         # opt into hard validation errors
  predictive:
    name: team_predictive            # optional
    size: HIGHMEM_X64_S
  prescriptive:
    name: team_prescriptive          # optional
    size: HIGHMEM_X64_S
```

> **Reasoner name/size behavior:** If `name` and `size` are both set and the named reasoner doesn't exist, PyRel creates it with the configured size. If the named reasoner already exists, PyRel uses it as-is and does not resize it. If the reasoner is later deleted and re-created automatically, it uses the default size (`HIGHMEM_X64_S`), not the previously configured size.

> **Note:** `auto_suspend_mins` and `await_storage_vacuum` are managed via the CLI only — they are not config fields.
> - Set auto-suspend after creation: `rai reasoners:alter --type Logic --name <name> --auto-suspend-mins <value>`
> - Set await-storage-vacuum at creation time: `rai reasoners:create --type Logic --name <name> --size <size> --await-storage-vacuum`

### Solver settings (Gurobi)

Gurobi requires three Snowflake objects and a named prescriptive engine:

1. **Snowflake secret** holding the Gurobi license key (e.g., `SOLVERS.SECRETS.GUROBI_LICENSE`)
2. **External access integration** allowing the engine to reach the Gurobi license server (e.g., `gurobi_integration`)
3. **A named prescriptive engine** — without `name`, PyRel uses an anonymous engine that does not receive the solver settings

```yaml
reasoners:
  prescriptive:
    name: my_prescriptive_engine    # required for Gurobi — must reference an existing engine
    size: HIGHMEM_X64_S
    settings:
      gurobi:
        enabled: true
        license_secret_name: solvers.secrets.gurobi_license
        external_access_integration: gurobi_integration
```

If `problem.solve("gurobi")` returns `Solver 'gurobi' is not enabled or not properly configured`, check:
- The `name` field is set and the engine exists (`rai reasoners:list --type Prescriptive`)
- The secret exists (`SHOW SECRETS IN SCHEMA SOLVERS.SECRETS`)
- The integration exists and is enabled (`DESCRIBE INTEGRATION gurobi_integration`)

For solver selection guidance, see `rai-prescriptive-solver-management`.

### Polling configuration

Controls how aggressively the client polls for long-running operations:

```yaml
reasoners:
  poll_initial_delay_s: 0.05
  poll_overhead_rate: 0.2        # +20% per poll (exponential backoff)
  poll_max_delay_s: 2.0
```

### Programmatic reasoner config

```python
cfg = create_config(
    connections={"sf": {...}},
    reasoners={
        "backend": "sql",
        "logic": {
            "size": "HIGHMEM_X64_M",
            "use_lqp": True,
            "emit_constraints": True,
        },
        "prescriptive": {
            "size": "HIGHMEM_X64_L",
        },
    },
)
```
