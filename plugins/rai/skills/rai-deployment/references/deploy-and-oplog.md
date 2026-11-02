# Deploy and the op log

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). Op-log recording is on by default since relationalai 1.28.0. See `rai-deployment` § Prerequisites.

How `rai models deploy` works, what the op log records, and the backends.

## What deploy does

`rai models deploy` resolves the model file (`--path`, else `model.path` in config), loads it, and installs its resources and outputs into the target schema (`deployment.schema`). When op-log recording is on, it also records the *diff* versus the previously deployed version as operations appended to the schema's op log, and regenerates `shared_model.py`.

```sh
rai models deploy            # deploy the current model
rai models deploy --wait     # block until the first refresh completes
rai models deploy --path models/sales.py --name sales
```

### Minimal raiconfig for an op-log deploy

Every key below is load-bearing for the lifecycle; the connection/auth fields come from `rai-setup`.

```yaml
connections:
  sf:
    type: snowflake
    # ... auth fields (see rai-setup) ...
oplog:
  enabled: true              # default since 1.28.0; required for branch / pull / merge
  backend: snowflake
deployment:
  schema: MY_DB.MY_MODEL     # fully qualified — model management co-locates its metadata schema in
                             # MY_DB (which must already exist). Bare or unset, it falls back to the
                             # connection's `database`, then the app name — which fails with
                             # "Insufficient privileges to operate on application 'RELATIONALAI'"
  # role: MY_DEPLOY_ROLE     # role for deploy + refresh tasks (default: connection/session role)
  schedules:
    standard:
      interval_s: 0          # 0 = refresh once on deploy, then only on manual/external trigger; >= 10 for periodic
  outputs:
    schedule: standard       # outputs must attach to a schedule, or deploy refuses with "Unscheduled Outputs"
model:
  path: model.py             # the model file to deploy
```

Options:
- `--path` — model file or package directory. Wins over config's `model.path`.
- `--name` — which model in the file to deploy; required only when the file defines several (otherwise the last-defined model is used).
- `--wait` — block until the first refresh triggered by the deploy completes. Use it in scripted/test flows for deterministic ordering.
- `--force` — override the `shared_model.py` edit guard and divergence checks.
- `--schema` — overrides `deployment.schema` for this deploy (working since 1.18; ignored on earlier releases — RAI-51584). For a persistent change, use `rai models switch`.

## Schedules and materialization

- `interval_s` must be `0` (refresh only on deploy or on a manual/external trigger of the schedule's task) or `>= 10` seconds. Schedule names start with a letter and use only letters, numbers, and underscores. An interval is a refresh cadence, not a freshness guarantee.
- Every schedule runs once on deploy — even at `interval_s: 0`. Set `run_on_deploy: false` on the schedule to deploy without triggering a refresh.
- `deployment.suspend_after_mins: N` auto-suspends schedules after N minutes — useful in development so test deployments don't leave tasks running.
- `deployment.outputs.type` sets the default materialization (`dynamic_table` — the default — `table`, or `view`); per-object `overrides` change individual outputs. PyRel falls back to a table when an output can't be represented as a dynamic table.
- Everything PyRel creates carries a `relationalai_managed = 'true'` tag, and deploy **errors rather than overwrite an untagged object** — keep the target schema dedicated to the model.

## Privileges for a custom deploy role

`rai_developer` is the standard role (see `rai-setup`). A scoped deploy role needs, beyond the `relationalai.rai_user` application role: USAGE on the model database and the warehouse, SELECT on the source tables (grant on ALL and FUTURE), and CREATE SCHEMA on the model database — or ownership of pre-created target + `_META` schemas. Verified on a live account (1.25.0) to the schema-DDL + source-read level; before locking CI onto a scoped role, validate one full `rai models deploy` under it — the app-side minimal set for the complete deploy/refresh path is not documented anywhere else. Separately, PyRel's deploy checks that a role whose schedules run (an interval, or run on deploy) holds the account-level EXECUTE TASK privilege, granted by an ACCOUNTADMIN: Snowflake checks it against the role that owns the refresh tasks and ignores secondary roles, so without it the deploy succeeds but the tables never refresh (`[Refresh Tasks Cannot Run]`).

Create the target and `_META` schemas as regular schemas, not `WITH MANAGED ACCESS`: managed access restricts object-level grants to the schema owner, and the deployed objects rely on grants PyRel applies to what it creates.

## The meta schema

Deploy also maintains a **meta schema** (`<target schema>_META` by default; override with `deployment.meta_schema`) holding model state, the refresh tasks, and the refresh log. Its `REFRESH_STATUS` procedure is the stable, public surface for refresh state; the rest of its contents are internal. Reading state back — `REFRESH_STATUS`, the refresh log, `rai doctor report` — is covered in [dev-loop-and-monitoring.md](dev-loop-and-monitoring.md).

## Outcome messages

- Changes recorded: `Recorded N change(s) to the snowflake oplog.`
- Nothing to record (empty diff): `No oplog changes to record (snowflake backend).`
- Owned source changes deployed: a warning to ensure the code is in version control.
- Remote ahead (someone deployed since your last pull): `Remote oplog is ahead (remote seq N, local seq M). Run 'rai models pull' first.` — pull, then deploy again.

## The op log

The op log is the model's ordered history. It is the foundation for the whole lifecycle:
- `deploy` appends the diff to the current model's log.
- `branch` forks a new log from the parent's history at the fork point.
- `merge` appends a branch's net changes back onto its parent's log.
- Collaboration replays the log to reconcile shared changes across developers.

You never edit the op log directly — the `rai models` commands maintain it. Each model and branch keeps its own.

## Op-log recording on and off

Recording is **on by default** since relationalai 1.28.0; earlier releases default it off. Set it explicitly in `raiconfig.yaml`:

```yaml
oplog:
  enabled: true        # default since 1.28.0; required for branch / pull / merge
  backend: snowflake   # default
```

Behavior by state:
- **On (`enabled: true`, the default)** — deploy installs *and* records to the op log; `branch`/`pull`/`merge` and Cortex agents are available.
- **Off (`enabled: false`)** — deploy installs only, records nothing; `branch`/`pull`/`merge` refuse with `Oplog recording is disabled (config.oplog.enabled = false).`

`teardown` works regardless of this setting.

## Backends

- **`snowflake`** (default) — the real op log, stored in the `_INTERNAL_OPLOG` hybrid table beside the model. This is the production backend.
- **`jsonl`** — a local file; **reserved for tests/demos only**, not production collaboration.

## shared_model.py (generated)

On every non-empty deploy and every non-up-to-date pull, PyRel (re)writes `shared_model.py` at the project root (next to the nearest `pyproject.toml`). It projects the *shared* entities from the op log into a `build_shared(m)` function and wires them into the model automatically. Details and the collaboration contract: [collaboration.md](collaboration.md).
