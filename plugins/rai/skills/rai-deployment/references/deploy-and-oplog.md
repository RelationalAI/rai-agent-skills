# Deploy and the op log

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). Op-log recording is on by default. See `rai-deployment` § Prerequisites.

How `rai models deploy` works, what the op log records, and the backends.

## What deploy does

`rai models deploy` resolves the model file (`--path`, else `model.path` in config), loads it, and installs its resources and outputs into the target schema (`deployment.public_schema`). When op-log recording is on, it also records the *diff* versus the previously deployed version as operations appended to the schema's op log.

```sh
rai models deploy            # deploy the current model; blocks until the first refresh completes
rai models deploy --no-wait  # return once installed
rai models deploy --path models/sales.py --name sales
```

### Minimal raiconfig for an op-log deploy

Every key below is load-bearing for the deploy; the connection/auth fields come from `rai-setup`.

```yaml
connections:
  sf:
    type: snowflake
    # ... auth fields (see rai-setup) ...
oplog:
  enabled: true              # default; records each deploy to the op log
  backend: snowflake
deployment:
  public_schema: MY_DB.MY_MODEL  # fully qualified <DATABASE>.<SCHEMA>; MY_DB must already exist
  identity:
    internal_schema: MY_DB.MY_MODEL_INTERNAL  # required; holds the model's internal objects and metadata
  # role: MY_DEPLOY_ROLE     # role for deploy + refresh tasks (default: connection/session role)
  schedules:
    standard:
      interval_s: 0          # 0 = refresh once on deploy, then only on manual/external trigger; >= 10 for periodic
  schedule: standard         # outputs must attach to a schedule, or deploy refuses with "Unscheduled Outputs"
model:
  path: model.py             # the model file to deploy
```

Options:
- `--path` — model file or package directory. Wins over config's `model.path`.
- `--name` — which model in the file to deploy; required only when the file defines several (otherwise the last-defined model is used).
- `--no-wait` — return once the model is installed, without waiting for the first refresh. `--wait-timeout SECONDS` caps the default wait instead. (`--wait` is deprecated: waiting is the default.)
- `--force` — accept recorded model-configuration changes.
- `--schema` — overrides `deployment.public_schema` for this deploy; a target other than the configured model keeps its metadata in `<target>_META`, not `identity.internal_schema`. For a persistent change, set `deployment.public_schema` and `deployment.identity.internal_schema` in `raiconfig.yaml`.

## Schedules and materialization

- `interval_s` must be `0` (refresh only on deploy or on a manual/external trigger of the schedule's task) or `>= 10` seconds. Schedule names start with a letter and use only letters, numbers, and underscores. An interval is a refresh cadence, not a freshness guarantee.
- Every schedule runs once on deploy — even at `interval_s: 0`. Set `run_on_deploy: false` on the schedule to deploy without triggering a refresh.
- `deployment.suspend_after_mins: N` auto-suspends schedules after N minutes — useful in development so test deployments don't leave tasks running.
- `deployment.materialized` and `deployment.incremental` set the default materialization. Each takes `auto` (the default), `true`, or `false`: `materialized: true` always materializes, `materialized: false` computes on read, and `incremental: true` uses dynamic tables. Per-object `overrides` change individual outputs. PyRel falls back to a table when an output can't be represented as a dynamic table.
- Everything PyRel creates carries a `relationalai_managed` tag whose value names the owning model (`model=<id>...`; `'true'` is legacy), and deploy **errors rather than overwrite an untagged object or one owned by another model** — keep the target schema dedicated to the model.

## Privileges for a custom deploy role

`rai_developer` is the standard role (see `rai-setup`). A scoped deploy role needs, beyond the `relationalai.rai_user` application role: USAGE on the model database and the warehouse, SELECT on the source tables (grant on ALL and FUTURE), and CREATE SCHEMA on the model database — or ownership of pre-created target + internal schemas. Verified on a live account (1.25.0) to the schema-DDL + source-read level; before locking CI onto a scoped role, validate one full `rai models deploy` under it — the app-side minimal set for the complete deploy/refresh path is not documented anywhere else. Separately, PyRel's deploy checks that a role whose schedules run (an interval, or run on deploy) holds the account-level EXECUTE TASK privilege, granted by an ACCOUNTADMIN: Snowflake checks it against the role that owns the refresh tasks and ignores secondary roles, so without it the deploy fails with `Could not start the model's refresh tasks`.

Create the target and internal schemas as regular schemas, not `WITH MANAGED ACCESS`: managed access restricts object-level grants to the schema owner, and the deployed objects rely on grants PyRel applies to what it creates.

## The internal schema

Deploy also maintains an **internal schema**, named by the required `deployment.identity.internal_schema`, holding model state, the refresh tasks, and the refresh log. New projects use what `rai models init` generates (`<public_schema>_INTERNAL`); a 1.x deployment keeps its `<schema>_META` ([upgrading-from-1x.md](upgrading-from-1x.md)). Its `REFRESH_STATUS` procedure is the stable, public surface for refresh state; the rest of its contents are internal. Reading state back — `REFRESH_STATUS`, the refresh log, `rai doctor report` — is covered in [dev-loop-and-monitoring.md](dev-loop-and-monitoring.md).

## Outcome messages

- Changes recorded: `N model history changes recorded.`
- Nothing to record: `0 model history changes recorded.`

## The op log

The op log is the model's ordered history: each `deploy` appends its diff to the current model's log, and `teardown` removes the log with the model. You never edit the op log directly — the `rai models` commands maintain it. Each model keeps its own.

## Op-log recording on and off

Recording is **on by default**. Set it explicitly in `raiconfig.yaml`:

```yaml
oplog:
  enabled: true        # default
  backend: snowflake   # default
```

Behavior by state:
- **On (`enabled: true`, the default)** — deploy installs *and* records to the op log.
- **Off (`enabled: false`)** — deploy installs only, records nothing.

`teardown` works regardless of this setting.

## Backends

- **`snowflake`** (default) — the real op log, stored in the `_INTERNAL_OPLOG` table in the internal schema, a standard table by default (`oplog.table_type: hybrid` opts in). This is the production backend.
- **`jsonl`** — a local file; **reserved for tests/demos only**, not production.
