---
name: rai-deployment
description: Take a built RelationalAI model to production — deploy it into a Snowflake schema and version it through the op log (branch, collaborate, merge, and tear down with the `rai models` CLI), or deploy it as a Snowflake Intelligence (Cortex) agent. The one path-to-prod skill across deployment targets. Use when deploying a model, managing its deployed lifecycle, or operationalizing it as a Cortex agent — not for first-time install/connect (see rai-setup), building the model (see rai-ontology-design, rai-pyrel-coding), or interpreting reasoner output.
---

# RelationalAI Deployment (Path to Prod)
<!-- v1-SENSITIVE -->

Covers the path from a built RelationalAI model to production: the `rai models` CLI (schema deployment + lifecycle) and Snowflake Intelligence (Cortex) agents. Built on the [relationalai package](https://pypi.org/project/relationalai) (PyRel).

> **Early access.** Deploy mode and semantic model management — the `rai models` deploy + branch/collaborate/merge/teardown lifecycle — are **early-access** features (documented in the RAI docs' early-access section); the API, messages, and defaults may still change. Op-log recording (the basis for `branch`/`pull`/`merge`) is **off by default** today, expected to default on soon. Verified against relationalai 1.17.0; see **Prerequisites** to turn it on. (The Cortex-agent path carries its own GA/PREVIEW markers — see [references/cortex-agents.md](references/cortex-agents.md).)

## Summary

**What:** Everything between a built model and production, by either of two paths. You've built and validated a model; this skill ships it. **Schema deployment** — deploy into a Snowflake schema and manage its lifecycle: track every change in the op log, fork experiments into branches, collaborate through a shared model, promote vetted changes back with merge, and tear models down safely. **Cortex agent** — package the model as a Snowflake Intelligence agent users query in natural language.

**When to use:**
- Deploying a model to a Snowflake schema (`rai models deploy`) and understanding what the op log records
- Branching a deployed model for isolated experiments (`rai models branch`)
- Collaborating with other developers on one model (shared model, `rai models pull`)
- Promoting a branch back to its parent (`rai models merge`) or removing a model (`rai models teardown`)
- Deploying a model as a Snowflake Intelligence (Cortex) agent
- Choosing a path to prod (schema deployment vs. Cortex agent)

**When NOT to use:**
- First-time install, `rai connect`, or `raiconfig.yaml` auth/engine tuning — see `rai-setup`
- Building or evolving the model itself (concepts, rules, queries) — see `rai-ontology-design`, `rai-pyrel-coding`, `rai-querying`
- Diagnosing engine performance or failed transactions — see `rai-health`

**Overview:** Start with **Choose a path to prod** to pick the deployment target. For **schema deployment**, read **Quick Reference** for the command surface, then **Deploy** for the foundation; the lifecycle commands build on a single idea — the **op log** — so read that first, then load the reference matching the task (branching, collaboration, merge/teardown). **Always check Prerequisites before the lifecycle commands** — they refuse cleanly if op-log recording is off. For the **Cortex-agent path**, go straight to [references/cortex-agents.md](references/cortex-agents.md).

---

## Choose a path to prod

A built model reaches production by one of these paths. Pick the target, then follow the matching guidance:

- **Deploy into a Snowflake schema** — the model's resources and outputs live in a schema you deploy, version, and evolve with `rai models`. This is the default path and the foundation for branching and collaboration. Covered below; lifecycle detail in the reference files.
- **Deploy as a Snowflake Intelligence (Cortex) agent** — package the model as a Cortex agent users query in natural language. Use when the deliverable is a conversational agent rather than a deployed schema. → [references/cortex-agents.md](references/cortex-agents.md); reference implementation in [examples/deploy.py](examples/deploy.py).

The two are not exclusive: you deploy a model to a schema first, then optionally expose it as a Cortex agent.

---

## Prerequisites

- **relationalai ≥ 1.17** (`rai --version`) — this skill targets the 1.17 `rai models` surface.
- A reachable Snowflake connection (`rai connect` passes) with a **`database` set on the connection** — model-management resolves its metadata schema from it and falls back to the app name (which fails) when it's unset. For install/auth, see `rai-setup`.
- A model to deploy — a `.py` model file or package, with `model.path` set in `raiconfig.yaml` (or pass `--path`). Its outputs need a refresh schedule (`deployment.schedules` + `deployment.outputs.schedule`) or deploy refuses with "Unscheduled Outputs".
- **For `branch` / `pull` / `merge`: op-log recording must be ON.** It is **off by default** (opt-in while rolling out). Turn it on in `raiconfig.yaml`:

  ```yaml
  oplog:
    enabled: true        # required for branch / pull / merge
    backend: snowflake   # default; 'jsonl' is for local tests/demos only
  ```

  Without it, `branch`, `pull`, and `merge` refuse with `Oplog recording is disabled (config.oplog.enabled = false).` `deploy` and `teardown` still work (deploy installs the model but records no history).

---

## Quick Reference

The **current model** is the schema named by `deployment.schema` in `raiconfig.yaml`. Every lifecycle command targets it; `switch` changes it.

| Command | Purpose | Key options |
|---|---|---|
| `rai models init [NAME]` | Scaffold a starter project | `--name` |
| `rai models deploy` | Install model + record diff to op log | `--path` `--name` `--force` `--wait` |
| `rai models list` | List models (schema, parent, type, HEAD, owner) | `--limit` |
| `rai models switch NAME` | Set the current model (`deployment.schema`) | `-y/--yes` |
| `rai models branch NAME` | Zero-copy fork into a new schema | `--static` |
| `rai models pull` | Reconcile shared changes into `shared_model.py` | `--path` `--force` `--from-parent` |
| `rai models merge` | Promote branch to parent, retire branch | `--path` `--delete` `--force` |
| `rai models teardown` | Drop the current model/branch + schema + op log | `--force` `--allow-unmerged` `--allow-children` |

`--schema` exists on `deploy` but is **ignored** (RAI-51584) — set the target via `deployment.schema` / `switch`. As of 1.17, `pull` / `merge` / `teardown` act on the **current model only** (no `--name`); use `switch` to target a different one.

---

## Deploy (the foundation)

`rai models deploy` does two things: it installs the model's resources and outputs into the target schema, and — when op-log recording is on — it records the *diff* versus the previously deployed version as operations in the schema's **op log**.

```sh
rai connect                 # validate config + connectivity first
rai models deploy --wait    # --wait blocks until the first refresh completes
```

When changes are recorded, PyRel reports the count: `Recorded 3 change(s) to the snowflake oplog.` An empty diff is a no-op (`No oplog changes to record`). If you deployed owned source changes, PyRel warns you to commit them to version control.

**The op log is the model's history** — an ordered record of how it changed from one deploy to the next, and the foundation for everything below: `deploy` appends to the current model's log, `branch` forks it, `merge` appends a branch's changes onto its parent's, and collaboration uses it to keep developers in sync. You never edit it directly.

If another developer (or session) deployed since your last pull, the deploy is refused: `Remote oplog is ahead (remote seq N, local seq M). Run 'rai models pull' first.` Pull, then deploy again.

See [references/deploy-and-oplog.md](references/deploy-and-oplog.md) for backends, install-only behavior when the op log is off, and `shared_model.py` generation.

---

## The deployed lifecycle

Once a model is deployed and op-log recording is on, four flows manage it. Load the reference file for the task:

1. **Branch** — fork the current model into a new schema to experiment in isolation; the parent is untouched. Live branches track the parent; static branches freeze at the fork. → [references/branching.md](references/branching.md)
2. **Collaborate** — several developers work one model. You own your source (synced through version control); PyRel reconciles everyone's *shared* changes through the op log into a generated `shared_model.py`. → [references/collaboration.md](references/collaboration.md)
3. **Merge** — promote a branch's vetted changes back into its parent and retire the branch. → [references/merge-and-teardown.md](references/merge-and-teardown.md)
4. **Teardown** — drop a model or branch and all its data, with guards against losing unmerged work. → [references/merge-and-teardown.md](references/merge-and-teardown.md)

## Reference files

Load only the file matching the task:

| File | Load when |
|---|---|
| [references/deploy-and-oplog.md](references/deploy-and-oplog.md) | Deploying; understanding the op log, backends, op-log opt-in, install-only mode |
| [references/branching.md](references/branching.md) | `branch`, `switch`, `list`; live vs. static; `--from-parent`; single-level limit |
| [references/collaboration.md](references/collaboration.md) | Multi-developer work; owned vs. shared; `shared_model.py`; `pull`; `build_shared` |
| [references/merge-and-teardown.md](references/merge-and-teardown.md) | `merge` (preconditions, `--delete`/`--force`); `teardown` (dry-run, guards) |
| [references/cortex-agents.md](references/cortex-agents.md) | Deploying the model as a Snowflake Intelligence (Cortex) agent — deployment script, `DeploymentConfig`, tool registry, query catalog, grants, debugging |

---

## Examples

Reference implementations for the Cortex-agent path (see [references/cortex-agents.md](references/cortex-agents.md) for the full walkthrough):

| Pattern | Description | File |
|---|---|---|
| Cortex deployment script | Complete lifecycle CLI (preflight / deploy / update / status / chat / teardown) — primary reference | [examples/deploy.py](examples/deploy.py) |
| Cortex debug script | Describe the deployed agent, call each sproc directly, trace a chat turn | [examples/debug.py](examples/debug.py) |
| Model modules | Core, computed, and query modules for the zero-arg `init_tools()` pattern | [examples/model/](examples/model/) |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| `branch`/`pull`/`merge` refuse: "Oplog recording is disabled" | Op-log recording is **off by default** (opt-in while rolling out) | Set `oplog.enabled: true` in `raiconfig.yaml`. `deploy`/`teardown` work without it |
| `deploy --schema` has no effect | `--schema` is a no-op (RAI-51584) | Set the target via `deployment.schema`; change it with `rai models switch` |
| `deploy` fails: "Database '...' does not exist or not authorized" | `deploy` creates the target **schema** but not its database | Create the database first — `deploy` runs `CREATE SCHEMA IF NOT EXISTS <db>.<schema>` |
| `deploy` (op-log on) fails: "Insufficient privileges to operate on application 'RELATIONALAI'" | No `database` on the connection — model-management falls back to the app name and tries to create its metadata schema inside the app | Set `database:` on the connection in `raiconfig.yaml`; the metadata schema resolves from it (not a grant or account-enablement issue) |
| Bare `rai models merge` fails: "Model file path is required" | Merge diffs your source to confirm the branch is fully deployed | Pass `--path <model>`, or set `model.path` in config |
| `merge` refuses: "branch has not observed the parent's latest changes" | Branch isn't rebased on the parent's latest | On the branch: `rai models pull` then `rai models deploy`, then merge |
| `merge --force` doesn't get past a precondition | `--force` only affects `--delete` (drops a branch that has children) | Rebase the branch (pull + deploy) to satisfy the merge preconditions |
| "Cannot branch from '...': it is itself a branch" | Branching is single-level in early access | Branch from the base model instead |
| `pull`/`deploy` refuse to overwrite `shared_model.py` | Fail-closed guard on a hand-edited generated file | Re-run with `--force` (backs up to a timestamped `.bak`); normally let PyRel maintain it |
| `teardown` dropped nothing | `teardown` is a dry run by default | Add `--force`; use `--allow-unmerged` / `--allow-children` only when you intend to lose that work |

---

## Related Skills
- `rai-setup` — install, `rai connect`, and `raiconfig.yaml` (do this first)
- `rai-ontology-design` — build and evolve the model you deploy
- `rai-pyrel-coding` — PyRel syntax and data loading
- `rai-health` — diagnose engine performance, failed transactions, and CDC health
