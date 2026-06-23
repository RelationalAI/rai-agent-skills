# Local Development with DuckDB (no Snowflake)

PyRel runs against a local DuckDB database — in-memory or file-backed — with no Snowflake
account or Native App. Use it for development, prototyping, demos, and fast iteration.
**Requires `relationalai >= 1.13`.** Local DuckDB execution relies on deploy mode, which the
package flags as experimental — use it for local work, and confirm the support stance with the
RelationalAI team before customer-facing deliverables.

The coarse per-reasoner summary lives in the `rai-setup` SKILL.md support table. This reference goes deeper on what is specific to the local backend: the config recipe, data loading, and gotchas. The modeling itself — concepts, rules, queries, relationship traversal, string and regex matching — is identical to Snowflake; see `rai-pyrel-coding` and `rai-querying`.

## Config

```python
from relationalai.config import create_config, DuckDBConnection
from relationalai.semantics import Model

config = create_config(
    connections={"local": DuckDBConnection(path=":memory:")},  # or a file path, e.g. "./dev.duckdb"
    default_connection="local",
    deployment={"schema": "main", "auto_deploy": True},   # routes to the DuckDB executor + materializes before queries
)
model = Model("my_model", config=config)
```

Equivalent `raiconfig.yaml`:

```yaml
default_connection: local
connections:
  local:
    type: duckdb
    path: ":memory:"        # or a file, e.g. ./dev.duckdb
deployment:
  schema: main
  auto_deploy: true
```

## Loading data

Seed the DuckDB session directly, then reference tables by their **3-part FQN**
(`<database>.<schema>.<table>` — in-memory DuckDB defaults to `memory.main`). Keep source
tables in a schema **separate** from the model install schema:

```python
session = config.get_connection(DuckDBConnection).get_session()
session.execute("CREATE SCHEMA raw")
session.execute("CREATE TABLE raw.employees (id INTEGER, name VARCHAR, dept VARCHAR)")
session.execute("INSERT INTO raw.employees VALUES (1, 'Ada', 'Engineering')")

employees = model.Table("memory.raw.employees")   # 3-part FQN; separate schema
```

From here the model is authored exactly as against Snowflake — see `rai-pyrel-coding`.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `Expected a fully-qualified table name with 3 parts` | DuckDB tables need `database.schema.table` | Reference as `memory.<schema>.<table>` |
| Query falls back to the Snowflake path, or reads an empty/missing model relation | `deployment` section / `auto_deploy` not set | Add a `deployment` section with `auto_deploy: true` |
| `Configuration must specify a non-empty schema name` | No install schema for model relations | Set `deployment.schema` (e.g. `main`) |
| `Existing object X is of type Table, trying to replace with type View` | DuckDB is case-insensitive — a source table named like a concept collides with the installed view | Put source tables in a schema separate from the model install schema (`deployment.schema`) |
| Aggregate shows the global value on every group row | Bare `select(key, agg)` doesn't group | Wrap in `distinct(key.alias(...), agg.per(key).alias(...))` |
