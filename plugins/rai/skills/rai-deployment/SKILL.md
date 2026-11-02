---
name: rai-deployment
description: Take a built RelationalAI model to production — deploy it into a Snowflake schema, iterate on it through the dev-schema redeploy loop, monitor its refreshes, and version it through the op log (branch, collaborate, merge, and tear down with the `rai models` CLI), or deploy it as a Snowflake CoWork (Cortex) agent. The one path-to-prod skill across deployment targets. Use when deploying a model, developing against a deployed schema, reading refresh status or debugging a failed refresh, managing the deployed lifecycle, or operationalizing the model as a Cortex agent — not for first-time install/connect (see rai-setup), building the model (see rai-ontology, rai-pyrel), or interpreting reasoner output.
---

# RelationalAI Deployment (Path to Prod)
<!-- v1-SENSITIVE -->

Covers the path from a built RelationalAI model to production: the `rai models` CLI (schema deployment + lifecycle) and Snowflake CoWork (Cortex) agents. Built on the [relationalai package](https://pypi.org/project/relationalai) (PyRel).

> **Early access.** Deploy mode and semantic model management — the `rai models` deploy + branch/collaborate/merge/teardown lifecycle — are **early-access** features (documented in the RAI docs' early-access section); the API, messages, and defaults may still change. Op-log recording (the basis for `branch`/`pull`/`merge`) is **on by default** since relationalai 1.28.0 (opt-in before that). Verified against relationalai 1.25.0; see **Prerequisites**. (The Cortex-agent path carries its own GA/PREVIEW markers — see [references/cortex-agents.md](references/cortex-agents.md).)

## Summary

**What:** Everything between a built model and production, by either of two paths. You've built and validated a model; this skill ships it. **Schema deployment** — deploy into a Snowflake schema and manage its lifecycle: track every change in the op log, fork experiments into branches, collaborate through a shared model, promote vetted changes back with merge, and tear models down safely. **Cortex agent** — package the model as a Snowflake CoWork agent users query in natural language.

**When to use:**
- Deploying a model to a Snowflake schema (`rai models deploy`) and understanding what the op log records
- Developing against a dev schema — the redeploy loop, refresh status, deploy warnings, and diagnosing a failed refresh or deploy
- Promoting a model from dev to prod (profiles, roles, CI)
- Branching a deployed model for isolated experiments (`rai models branch`)
- Collaborating with other developers on one model (shared model, `rai models pull`)
- Promoting a branch back to its parent (`rai models merge`) or removing a model (`rai models teardown`)
- Deploying a model as a Snowflake CoWork (Cortex) agent
- Choosing a path to prod (schema deployment vs. Cortex agent)

**When NOT to use:**
- First-time install, `rai connect`, or `raiconfig.yaml` auth/engine tuning — see `rai-setup`
- Building or evolving the model itself (concepts, rules, queries) — see `rai-ontology`, `rai-pyrel`
- Diagnosing engine performance or failed transactions — see `rai-health`

**Overview:** Start with **Choose a path to prod** to pick the deployment target. For **schema deployment**, read **Quick Reference** for the command surface, then **Deploy** for the foundation and **The dev loop** for how iteration and monitoring work; the lifecycle commands build on a single idea — the **op log** — so read that first, then load the reference matching the task (dev loop/monitoring, branching, collaboration, merge/teardown). **Always check Prerequisites before the lifecycle commands** — they refuse cleanly if op-log recording is off. For the **Cortex-agent path**, go straight to [references/cortex-agents.md](references/cortex-agents.md).

---

## Choose a path to prod

A built model reaches production by one or both of these paths:

- **Deploy into a Snowflake schema** — the model's resources and outputs live in a schema you deploy, version, and evolve with `rai models`. This is the default path and the foundation for branching and collaboration. Covered below; lifecycle detail in the reference files.
- **Deploy as a Snowflake CoWork (Cortex) agent** — put a Cortex agent users query in natural language on top of a model already deployed to a schema. The agent reads that deployment over SQL; it needs no RAI engine. Use when the deliverable is a conversational agent. → [references/cortex-agents.md](references/cortex-agents.md); reference implementation in [examples/deploy.py](examples/deploy.py).

The agent path builds on the schema path: deploy the model to a schema first, then expose it as a Cortex agent.

---

## Prerequisites

- **relationalai ≥ 1.25.0** (`rai --version`) — verified against 1.25.0; the `rai models` surface is unchanged since 1.20, so installs back to 1.20.1 still match this skill.
- A reachable Snowflake connection (`rai connect` passes) and a **fully qualified `deployment.schema` (`DB.SCHEMA`)** — model management co-locates its metadata schema with the model's database. (Bare or unset, it falls back to the connection's `database`, then the app name — which fails.) For install/auth, see `rai-setup`.
- A model to deploy — a `.py` model file or package, with `model.path` set in `raiconfig.yaml` (or pass `--path`). Its outputs need a refresh schedule (`deployment.schedules` + `deployment.outputs.schedule`) or deploy refuses with "Unscheduled Outputs".
- **PyRel queries kept out of the model definition** — the model file is loaded whole at deploy time.
- **Prescriptive Problems deploy too** (preview, Snowflake only): register each with `problem.configure(...)` instead of `solve()` (`rai-prescriptive-problem` > Deploy Mode) and set the four `deployment.pat_*` fields after the one-time setup in [prescriptive-deploy-setup.md](../rai-setup/references/prescriptive-deploy-setup.md).
- **For `branch` / `pull` / `merge` and Cortex agents: op-log recording must be ON.** It is on by default since relationalai 1.28.0; on earlier releases, or where a config sets it false, turn it on in `raiconfig.yaml`:

  ```yaml
  oplog:
    enabled: true        # default since 1.28.0; required for branch / pull / merge
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

`deploy --schema` overrides `deployment.schema` for that deploy (working since 1.18; earlier releases ignored it — RAI-51584). As of 1.20, `pull` / `merge` / `teardown` act on the **current model only** (no `--name`); use `switch` to target a different one.

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

## The dev loop (develop against a dev schema)

A deployed model is a stateful Snowflake object you develop the way a dbt project develops against a dev schema: point `deployment.schema` at a schema you own, then iterate by redeploying — edit, `rai models deploy`, read state back, repeat. Redeploying overwrites the deployed version; it *is* the iteration step. Reasoning runs asynchronously behind the model's refresh tasks, so all execution state comes back through SQL, not a live engine connection.

Validation is two-tier, and the loop should exhaust the cheap tier first:

1. **Compile/deploy time (client-side, seconds)** — deploy compiles and type-checks the model before anything is installed; type and shape errors fail fast, before any reasoner or refresh is involved.
2. **Refresh time (data-dependent)** — constraints that depend on the data (uniqueness, references, functional dependencies) only fail once a refresh runs against real rows, surfacing as a `FAILED` refresh.

Read state with `CALL <db>.<schema>_META.REFRESH_STATUS();` (one row per schedule; the stable contract), drill into the meta schema's refresh log for block-level failures, and reach for `rai doctor report` when you need complete deploy state in one artifact. Full loop, status contract, refresh-log queries, and report interpretation: [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md).

A successful deploy can still print warnings — `[Deploy Step Skipped]` (a missing privilege), `[Dynamic table fallback]`, and, when the model file runs directly, deprecations. Read each one, tell the user what it means and whether it matters, and suggest the fix; never edit the model yourself. Before calling a deploy done, confirm the model holds rows: install and refresh are separate, and without `--wait` a failed first refresh still leaves the deploy reporting success over an empty model. How to read each warning: [references/deploy-warnings.md](references/deploy-warnings.md).

### Promote dev to prod

If the team already has an established Snowflake deployment workflow, keep it. Otherwise:

- **Profiles separate dev and prod configuration** — source tables, target schema, roles, and operational settings live in `raiconfig.yaml` profile overlays; deploying to dev vs. prod is switching profiles. Mechanics in `rai-setup`.
- **Role-based access locks down prod** — deploys run as a role; require a higher-privileged role for the production schema than for dev schemas, so no one deploys to prod mid-development. When day-to-day work already runs as ACCOUNTADMIN (a common proof-of-concept start state with no privilege ladder to sit under), express the separation as *isolation* instead: prod schemas owned by a dedicated deploy role granted only to CI/admin — never to developer users — and move dev onto a scoped role as a follow-up.
- **CI owns prod deploys** — developers never hold the prod role day to day; a CI job holds it, runs tests, and triggers the production deployment. The grant set a scoped deploy role needs: [references/deploy-and-oplog.md](references/deploy-and-oplog.md) § Privileges for a custom deploy role.
- **Expectation to set:** redeploys replace changed objects in place — zero-downtime upgrades for schemas with always-on consumers are not supported yet, so plan maintenance windows for prod redeploys.

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
| [references/deploy-and-oplog.md](references/deploy-and-oplog.md) | Deploying; the op log, backends, turning recording off, install-only mode; refresh schedules, output materialization, the meta schema |
| [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md) | Iterating on a deployed model; two-tier validation; `REFRESH_STATUS` contract, refresh-log queries for block-level failures, `rai doctor report` interpretation |
| [references/deploy-warnings.md](references/deploy-warnings.md) | Reading the warnings a successful deploy prints (deprecations, skipped steps, materialization fallbacks); confirming the deployed model holds rows |
| [references/branching.md](references/branching.md) | `branch`, `switch`, `list`; live vs. static; `--from-parent`; single-level limit |
| [references/collaboration.md](references/collaboration.md) | Multi-developer work; owned vs. shared; `shared_model.py`; `pull`; `build_shared` |
| [references/merge-and-teardown.md](references/merge-and-teardown.md) | `merge` (preconditions, `--delete`/`--force`); `teardown` (dry-run, guards) |
| [references/cortex-agents.md](references/cortex-agents.md) | Deploying the model as a Snowflake CoWork (Cortex) agent — model deployment prerequisites, deployment script, `AgentConfig`, `DefaultTool`, query catalog, grants, debugging |

---

## Examples

Reference implementations for the Cortex-agent path (see [references/cortex-agents.md](references/cortex-agents.md) for the full walkthrough):

| Pattern | Description | File |
|---|---|---|
| Cortex deployment script | Complete lifecycle CLI (preflight / deploy / update / status / chat / teardown) — primary reference | [examples/deploy.py](examples/deploy.py) |
| Cortex debug script | Describe the deployed agent, call each sproc directly, trace a chat turn | [examples/debug.py](examples/debug.py) |
| Model modules | Table-sourced core, computed, and query modules — deployable with `rai models deploy --path <package>/model` and served by the zero-arg `init_tools()` | [examples/model/](examples/model/) |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| `branch`/`pull`/`merge` refuse: "Oplog recording is disabled" | `oplog.enabled: false` in config, or relationalai < 1.28.0 (where recording was opt-in) | Set `oplog.enabled: true` in `raiconfig.yaml`. `deploy`/`teardown` work without it |
| `deploy` fails: "Database '...' does not exist or not authorized" | `deploy` creates the target **schema** but not its database | Create the database first — `deploy` runs `CREATE SCHEMA IF NOT EXISTS <db>.<schema>`. If the deploy role lacks `CREATE SCHEMA`, pre-create the schema (and its `_META` meta schema, when op-log recording is on) and grant `USAGE`; deploy confirms it exists and proceeds |
| `deploy` (op-log on) fails: "Insufficient privileges to operate on application 'RELATIONALAI'" | `deployment.schema` is bare or unset and the connection has no `database` — model management falls back to the app name and tries to create its metadata schema inside the app | Use a fully qualified `deployment.schema` (`DB.SCHEMA`), or set `database:` on the connection (not a grant or account-enablement issue) |
| Bare `rai models merge` fails: "Model file path is required" | Merge diffs your source to confirm the branch is fully deployed | Pass `--path <model>`, or set `model.path` in config |
| `merge` refuses: "branch has not observed the parent's latest changes" | Branch isn't rebased on the parent's latest | On the branch: `rai models pull` then `rai models deploy`, then merge |
| `merge --force` doesn't get past a precondition | `--force` only affects `--delete` (drops a branch that has children) | Rebase the branch (pull + deploy) to satisfy the merge preconditions |
| "Cannot branch from '...': it is itself a branch" | Branching is single-level in early access | Branch from the base model instead |
| `pull`/`deploy` refuse to overwrite `shared_model.py` | Fail-closed guard on a hand-edited generated file | Re-run with `--force` (backs up to a timestamped `.bak`); normally let PyRel maintain it |
| `deploy` fails: "Configured Prescriptive Problems require deployment.pat_secret, deployment.pat_eai, deployment.pat_user, and deployment.pat_warehouse" | A `configure()`d Problem without all four `pat_*` fields | [prescriptive-deploy-setup.md](../rai-setup/references/prescriptive-deploy-setup.md) |
| `teardown` dropped nothing | `teardown` is a dry run by default | Add `--force`; use `--allow-unmerged` / `--allow-children` only when you intend to lose that work |
| Deploy succeeded but the refresh shows `FAILED` | Data-dependent constraints (uniqueness, references) can only fail once a refresh runs against real rows — deploy-time validation can't catch them | Read `error` from `REFRESH_STATUS`, block detail from the refresh log; fix the model or data and redeploy — see [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md) |
| Deploy fails: `Invalid expression [CAST(... )] in VALUES clause` | A `model.data(...)` table has a date or datetime column, on relationalai < 1.35.3 (RAI-54840). From 1.35.3 only a column mixing dates with non-date values still fails | Upgrade to ≥ 1.35.3, or load the data into a Snowflake table and bind with `model.Table("DB.SCHEMA.TABLE")` — the deploy-mode source pattern |
| Diagnosing a failed refresh from output tables alone | Execution state lives in the meta schema, not the model schema | `CALL <meta schema>.REFRESH_STATUS();` first, then the refresh log; `rai doctor report` bundles complete state |
| `rai config explain` shows a full `deployment` block though deploy mode is off | The block always renders; deploy mode is on when a `deployment` mapping is given (in the file or the active profile), even an empty one (`deployment: {}`; a bare `deployment:` fails validation) | `create_config().deployment_enabled` |
| Deploy after a `teardown` fails on a local/remote op-log mismatch | `teardown` drops the remote op log but leaves the local replay state in `.rai/<schema>/` | Delete `.rai/<schema>/` so the next deploy starts as a new root |
| Deploy reported success but queries return nothing | Install and refresh are separate steps: without `--wait`, deploy returns before the first refresh, which then failed; or the refresh tasks cannot run (`[Refresh Tasks Cannot Run]`, with or without `--wait`) | Read `REFRESH_STATUS()` and count rows per object before reporting success — see [references/deploy-warnings.md](references/deploy-warnings.md) |

---

## Related Skills
- `rai-setup` — install, `rai connect`, and `raiconfig.yaml` including profile overlays for dev/prod config (do this first)
- `rai-ontology` — build and evolve the model you deploy
- `rai-pyrel` — PyRel syntax and data loading
- `rai-prescriptive-problem` / `rai-prescriptive-results` — `configure()` and reading results after a refresh
- `rai-health` — diagnose engine performance, failed transactions, and CDC health
