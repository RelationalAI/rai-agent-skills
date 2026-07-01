# Merge and teardown

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults), and op-log recording is off by default. See `rai-deployment` § Prerequisites.

Promote a branch's changes back to its parent, and remove models safely.

Merge requires op-log recording on (see [deploy-and-oplog.md](deploy-and-oplog.md)). Teardown works regardless.

## Merge a branch back

`rai models merge` diffs the branch against its parent, appends the branch's net changes to the parent's op log, installs the merged model into the parent schema, and retires the branch. The parent is resolved automatically from the branch's lineage — you never name it.

**Precondition: the branch must sit on top of the parent's latest.** In practice, catch the branch up and re-deploy it first:

```sh
rai models switch EXPERIMENT_X
rai models pull            # catch up on the parent (or --from-parent for a static branch)
rai models deploy          # rebase the branch onto the parent's latest
rai models merge --path models/sales.py
```

Merge needs a model file to verify the branch is fully deployed: pass `--path`, or set `model.path` in config. A bare `rai models merge` fails without one (`Model file path is required (--path or config.model.path).`).

Outcome: `Merged N change(s) into the parent; branch retired.` (or `Branch had no net change over its parent; branch retired.`). A retired branch can no longer receive deploys. Merge does **not** move `deployment.schema` off the branch — `rai models switch <parent>` to keep working. After a plain merge the branch is frozen (deploys refused); after `merge --delete` its schema is gone, so the pointer dangles until you switch.

Refusals you may hit:
- Branch behind parent: `branch has not observed the parent's latest changes; run rai models pull then rai models deploy, then rai models merge.`
- Branch has undeployed changes: `this branch has local changes that are not deployed yet ...; run rai models deploy before merging.`
- Not a branch: `only a branch can be merged into a parent.`

### Delete on merge

`--delete` drops the retired branch's schema and op log in the same step:

```sh
rai models merge --delete
```

If the branch has downstream branches, `--delete` is blocked unless you also pass `--force` (which orphans them). `--force` matters only together with `--delete`; it does not override merge's own preconditions. (Branching is single-level, so a branch normally has no children — see [branching.md](branching.md).)

Prefer `--delete` for a clean lifecycle. A branch merged **without** it stays as a retired schema, which then blocks the *parent's* teardown (`'...' has downstream branches: ...`, forcing `--allow-children`, which orphans that schema and its `_META`). `merge --delete` drops the branch at merge time so the parent tears down cleanly.

## Tear down a model or branch

`rai models teardown` drops the **current model** and everything in it — its schema, its meta schema, and its op log. To tear down a different model, `rai models switch` to it first (as of 1.17 there is no `--name`).

**It is a dry run by default**: it prints exactly what would be dropped and stops. Re-run with `--force` to perform it.

```sh
rai models teardown          # dry run: shows what would be dropped
rai models teardown --force  # actually drop it
```

After teardown, `deployment.schema` is reset to the branch's parent (or cleared for a root model). Your local files — model source and `shared_model.py` — are left untouched.

### Guards (they prevent data loss)

Teardown refuses to discard work you may not have meant to. Both refusals are previewed in the dry run:

- Unmerged branch: `'...' has unmerged changes; merge it first (rai models merge) or pass --allow-unmerged.` `--allow-unmerged` discards them.
- Downstream branches: `'...' has downstream branches: ...; delete or merge them first, or pass --allow-children.` `--allow-children` orphans them.

Override only when you intend to lose that work.
