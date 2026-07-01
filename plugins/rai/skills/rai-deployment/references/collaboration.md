# Collaboration

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults), and op-log recording is off by default. See `rai-deployment` § Prerequisites.

Several developers work against one deployed model, with the op log as the shared source of truth — everyone's deploys append to it.

Requires op-log recording on (see [deploy-and-oplog.md](deploy-and-oplog.md)).

## Owned vs. shared

A model has two parts that stay in sync in different ways:

- **The part you own** — the model source you author. Split it across as many files as you like, named however you want. The op log records your changes to these entities, but **PyRel does not sync your source for you**: you share and reconcile it through version control (e.g. `git pull`). When you deploy owned changes, PyRel reminds you to commit them.
- **The shared part** — entities contributed through the op log, including by collaborators. PyRel projects these into a generated `shared_model.py` written next to your source, wires it into the model automatically on `deploy`/`pull`, and keeps it current by regenerating it from the op log. `rai models pull` reconciles shared changes for you.

In short: **`rai models pull` reconciles *shared* changes automatically; *owned* changes are yours to manage in version control.**

## The collaboration loop

```sh
rai models pull      # reconcile shared changes before you start
# ... edit your model ...
rai models deploy    # publish; appends to the shared op log
```

If a collaborator deployed since your last pull, your deploy is refused (`Remote oplog is ahead ... Run 'rai models pull' first.`). Pull and deploy again to get back in sync.

`rai models pull` reports `Pulled N change(s) from the snowflake oplog backend.`, or (when nothing is pending) `No changes to pull (snowflake oplog backend).` / `Already up to date.`

When the remote has **owned (source) changes** from a collaborator, pull tells you to sync version control first: `Remote has code-owned changes; pass --path to verify your code is in sync, or run git pull first.` Run `git pull`, then `rai models pull --path <model>` and deploy.

## Referencing shared entities

`shared_model.py` exposes a `build_shared` function:

```python
from shared_model import build_shared

shared = build_shared(m)   # shared.Person, shared.orders, ...
```

You normally let PyRel maintain this file. PyRel wires the shared entities in on deploy/pull regardless; the `build_shared(m)` call is only needed to *reference* them from your own code.

## The shared_model.py clobber guard (fail-closed)

PyRel will not silently overwrite a `shared_model.py` you have edited by hand. `pull` and `deploy` both regenerate the file and refuse to clobber local edits unless you pass `--force`:

```
shared_model.py has been edited since the last pull. Re-run with --force to
overwrite it ... (the existing file will be backed up to a timestamped
shared_model.py.<timestamp>.bak).
```

With `--force`, your current file is backed up to a timestamped `shared_model.py.<timestamp>.bak` first, then regenerated. The guard is fail-closed: it also refuses when there is no recorded baseline confirming the file is safe to overwrite.

## Static branches

For a **static branch**, a plain `rai models pull` only syncs the branch's own changes. To incorporate the parent's latest, run `rai models pull --from-parent` (see [branching.md](branching.md)).
