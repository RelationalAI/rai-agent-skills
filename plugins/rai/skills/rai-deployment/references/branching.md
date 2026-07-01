# Branching

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults), and op-log recording is off by default. See `rai-deployment` § Prerequisites.

Fork a deployed model into an isolated schema, work in it without touching the parent, and choose how it tracks the parent over time.

Requires op-log recording on (see [deploy-and-oplog.md](deploy-and-oplog.md)).

## The current model: switch and list

Every lifecycle command acts on the **current model** — the schema named by `deployment.schema` in `raiconfig.yaml`.

```sh
rai models list                          # schema, parent, type, HEAD, owner, created
rai models switch MY_DB.MY_DEV_SCHEMA    # validate + set deployment.schema
```

- `rai models list` discovers the deployed models registered in the **connection's `database`** — all of them, not just the current model, so it's how you find existing ontologies. It shows each model's name, its parent (if a branch), its type (base / live branch / static branch), its HEAD sequence, and owner. Scope is that one database's `_RAI_MODEL_MGMT` registry, not account-wide; point the connection's `database` at another DB to list its models. `--limit N` caps the rows (default 100).
- `rai models switch NAME` validates that `NAME` is a provisioned model, then rewrites `deployment.schema` (preserving comments/layout). `-y/--yes` skips the confirmation prompt (e.g. when editing a raiconfig outside the current directory). A branch is a valid switch target — that is how you work inside a branch.

## Create a branch

A branch is a zero-copy fork of the current model into a new schema — it duplicates none of the parent's data. It starts from the parent's deployed state and history, then evolves independently.

```sh
rai models switch MY_DB.MY_DEV_SCHEMA   # confirm the parent (the current model)
rai models branch EXPERIMENT_X          # fork it
rai models switch EXPERIMENT_X          # work inside the branch
rai models deploy --wait                # changes land in the branch; parent untouched
```

`rai models branch NAME` takes the new branch's schema name. A bare name creates it in the parent's database; a fully-qualified `DATABASE.SCHEMA` places it explicitly. The parent is the current model, so it must already be deployed.

Refusals you may hit:
- Parent not deployed: `Parent '...' doesn't exist. Run rai models deploy to create a new model instead of branching.`
- Parent exists but isn't a model: `Parent '...' exists but isn't a provisioned model. Deploy to it first, then branch.`
- Target name taken: `Schema '...' already exists. Use rai models switch ... to switch to it.`

## Live vs. static branches

The branch type is fixed at creation and governs how it tracks the parent as the parent keeps changing:

- **Live** (default) — `rai models pull` reconciles the parent's latest changes into the branch automatically, on every pull. Choose for short-lived work that should keep pace with the parent.
- **Static** (`rai models branch --static`) — frozen at the fork point. A plain `rai models pull` does **not** bring in the parent's later changes; you incorporate them explicitly with `rai models pull --from-parent`. Choose when you want a stable base that only changes when you ask.

`--from-parent` applies only to static branches. On a live branch or a non-branch model it refuses (`--from-parent applies only to static branches; ...`).

## Single-level only

Branching is single-level: you can branch a deployed base model, but you **cannot branch a branch**. The CLI enforces this at creation:

```
Cannot branch from '...': it is itself a branch. Branching off a branch is
not supported (single level in v1); branch from its base model instead.
```

To explore a second direction, branch again from the base model.
