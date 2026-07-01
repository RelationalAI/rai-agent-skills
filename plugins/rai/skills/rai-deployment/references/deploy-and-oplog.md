# Deploy and the op log

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults), and op-log recording is off by default. See `rai-deployment` § Prerequisites.

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
    database: MY_DB          # model-management resolves its metadata schema from this; if unset it
                             # falls back to the app name and deploy fails with
                             # "Insufficient privileges to operate on application 'RELATIONALAI'"
oplog:
  enabled: true              # required for branch / pull / merge
  backend: snowflake
deployment:
  schema: MY_DB.MY_MODEL     # the current model (deploy target); MY_DB must already exist
  schedules:
    standard:
      interval_s: 0          # 0 = refresh once on deploy; >= 10 for a periodic refresh
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
- `--schema` — **ignored** (RAI-51584). The target is always `deployment.schema`; change it with `rai models switch`.

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

## Op-log recording is opt-in

Recording is **off by default** ("opt-in while rolling out"; expected to default on soon). Turn it on in `raiconfig.yaml`:

```yaml
oplog:
  enabled: true        # required for branch / pull / merge
  backend: snowflake   # default
```

Behavior by state:
- **On (`enabled: true`)** — deploy installs *and* records to the op log; `branch`/`pull`/`merge` are available.
- **Off (default)** — deploy installs only, records nothing; `branch`/`pull`/`merge` refuse with `Oplog recording is disabled (config.oplog.enabled = false).`

`teardown` works regardless of this setting.

## Backends

- **`snowflake`** (default) — the real op log, stored in a hybrid table beside the model. This is the production backend.
- **`jsonl`** — a local file; **reserved for tests/demos only**, not production collaboration.

## shared_model.py (generated)

On every non-empty deploy and every non-up-to-date pull, PyRel (re)writes `shared_model.py` next to the model file. It projects the *shared* entities from the op log into a `build_shared(m)` function and wires them into the model automatically. Details and the collaboration contract: [collaboration.md](collaboration.md).
