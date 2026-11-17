# Teardown

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). See `rai-deployment` § Prerequisites.

Remove a deployed model safely. Teardown works whether or not op-log recording is on.

## Tear down a model

`rai models teardown` removes the objects PyRel created for the **current model** from its public schema and its internal schema, op log included. It never drops the schemas themselves, so anything else in them stays. It has no `--name`: to tear down a different model, point `deployment.public_schema` and `deployment.identity.internal_schema` at it first.

**It is a dry run by default**: it prints exactly what would be dropped and stops. Re-run with `--force` to perform it.

First check that `rai --version` meets the `rai-setup` minimum: older releases drop the schemas.

```sh
rai models teardown          # dry run: shows what would be dropped
rai models teardown --force  # actually drop it
```

Teardown leaves `raiconfig.yaml` untouched, so `deployment.public_schema` still names the model you tore down; edit or clear it before using it again. Your model source is left untouched too.

Teardown of a model deployed by 1.x can refuse until its config and ownership tags are upgraded: see [upgrading-from-1x.md](upgrading-from-1x.md).
