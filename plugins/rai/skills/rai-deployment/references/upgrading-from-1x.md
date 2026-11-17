# Upgrading a 1.x deployment

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). See `rai-deployment` § Prerequisites.

PyRel 2.0 refuses 1.x deployment keys at config load. Its default stateless deploy also refuses `rai models branch`, `pull`, `merge` and `switch`, and refuses to deploy or tear down a branch or a root with children, so merge or tear down branches on 1.x first. Then, to keep an existing model:

1. **Rename the config.**
   - `deployment.schema` becomes `deployment.public_schema`.
   - `deployment.meta_schema` becomes `deployment.identity.internal_schema` (now required).
   - `deployment.object_name_prefix` and `deployment.object_name_suffix` move under `identity`; keep their values unchanged.
   - `deployment.outputs` is gone: `schedule`, `reasoner`, `storage` and `overrides` move up to `deployment`.
   - `type` is replaced, and an override that sets it is rejected: `table` becomes `materialized: true`, `dynamic_table` becomes `incremental: true`, and `view` becomes `materialized: false`.
   - `default_volume` and an override's `volume` become `external_volume`.
2. **Set `identity.internal_schema` to the existing `<schema>_META` schema** (or whatever `meta_schema` named). `identity` defines which objects count as the same model, so a new name, such as the `_INTERNAL` one `rai models init` generates, is a different model.
3. **Protect remote edits.** The default stateless deploy deletes remote entities absent from source, including shared or RelApp-authored ones, and stale source reverts remote changes. If anyone else edits the model, pull on 1.x first and keep `shared_model.py` with the source.
4. **Plan for the switch to views.** The first 2.0 deploy replaces 1.x public tables with views over new stores in the internal schema. Data is unavailable until the first refresh, direct grants on the old tables are lost, public names and columns can change, and no rollback path was found. Use a maintenance window and try a dev copy first; afterwards re-grant consumers and confirm row counts. A 1.x table whose public name changed can be left behind as a stale copy that still answers queries: compare the public schema with the new views and drop the leftovers by hand. (Read from the 2.0 source, not observed on a live upgrade.)
5. **Redeploy before any teardown.** Deploy upgrades the ownership tags on 1.x objects.

Teardown refuses in two upgrade states, deleting nothing:

- `Cannot tear down '...': its metadata is at '...', not '...'.` — set `deployment.public_schema` and `deployment.identity.internal_schema` together to match the deployed model.
- `Cannot tear down '...': its ownership upgrade is incomplete.` — retry the deploy to finish it, or have an administrator repair the model.

## Op-log replay

A 1.x op log can't replay if the model annotated a relationship with `synthetic` or `computed_by` (`[OPLOG-INCOMPAT-001]` or `[OPLOG-INCOMPAT-002]`).

- **Root model with the default `oplog.auto_recover`:** deploy warns and continues, and the next deploy rebuilds the history from source. Don't tear down, even though the message says to.
- **`auto_recover: false`:** deploy fails, and an ordinary redeploy replays the same log. Check `rai --version` meets the `rai-setup` minimum (older releases drop the schemas), then run `rai models teardown --force`, which removes managed data, and deploy afresh. Bare `teardown` is a dry run.
