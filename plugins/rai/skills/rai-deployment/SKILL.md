---
name: rai-deployment
description: Take a built RelationalAI model to production with the `rai models` CLI — deploy it into a Snowflake schema, iterate through the dev-schema redeploy loop, monitor its refreshes, and tear it down — use when deploying a model, developing against a deployed schema, reading refresh status or debugging a failed refresh, upgrading a 1.x deployment, or removing a deployed model, not for first-time install/connect (see rai-setup), building the model (see rai-ontology, rai-pyrel), or interpreting reasoner output.
---

# RelationalAI Deployment (Path to Prod)
<!-- v1-SENSITIVE -->

Covers the path from a built RelationalAI model to production: the `rai models` CLI (schema deployment + lifecycle). Built on the [relationalai package](https://pypi.org/project/relationalai) (PyRel).

> **Early access.** Deploy mode and semantic model management — `rai models` deploy and teardown — are **early-access** features (documented in the RAI docs' early-access section); the API, messages, and defaults may still change. Op-log recording is **on by default**.

## Summary

**What:** Everything between a built model and production. You've built and validated a model; this skill ships it: deploy into a Snowflake schema, iterate on it, track every change in the op log, and tear it down safely.

**When to use:**
- Deploying a model to a Snowflake schema (`rai models deploy`) and understanding what the op log records
- Developing against a dev schema — the redeploy loop, refresh status, deploy warnings, and diagnosing a failed refresh or deploy
- Promoting a model from dev to prod (profiles, roles, CI)
- Removing a deployed model (`rai models teardown`)
- Upgrading a deployment from PyRel 1.x

**When NOT to use:**
- First-time install, `rai connect`, or `raiconfig.yaml` auth/engine tuning — see `rai-setup`
- Building or evolving the model itself (concepts, rules, queries) — see `rai-ontology`, `rai-pyrel`
- Diagnosing engine performance or failed transactions — see `rai-health`

**Overview:** Read **Quick Reference** for the command surface, then **Deploy** for the foundation and **The dev loop** for how iteration and monitoring work, then load the reference matching the task (deploy and op log, dev loop/monitoring, deploy warnings, teardown, 1.x upgrade).

---

## Prerequisites

- **`relationalai` at the minimum in `rai-setup`** (`rai --version`).
- A reachable Snowflake connection (`rai connect` passes) and a `deployment:` section naming both schemas: a **fully qualified `deployment.public_schema` (`DB.SCHEMA`)** for the model's published views and tables, and `deployment.identity.internal_schema` for its internal objects and metadata. A section missing either fails at config load, and deploy pre-flight rejects a bare `public_schema`. New projects use what `rai models init` generates (`<public_schema>_INTERNAL`); for a 1.x deployment, see **Upgrading a 1.x deployment**. For install/auth, see `rai-setup`.
- A model to deploy — a `.py` model file or package, with `model.path` set in `raiconfig.yaml` (or pass `--path`). Its outputs need a refresh schedule (`deployment.schedules` + `deployment.schedule`) or deploy refuses with "Unscheduled Outputs".
- **PyRel queries kept out of the model definition** — the model file is loaded whole at deploy time.
- **Prescriptive Problems deploy too** (preview, Snowflake only): register each with `problem.configure(...)` instead of `solve()` (`rai-prescriptive-problem` > Deploy Mode) and set the four `deployment.pat_*` fields after the one-time setup in [prescriptive-deploy-setup.md](../rai-setup/references/prescriptive-deploy-setup.md).

---

## Upgrading a 1.x deployment

1.x deployment keys fail at config load, and the first 2.0 deploy replaces public tables with views and by default deletes remote entities absent from source.
Before deploying or tearing down a 1.x model, load [references/upgrading-from-1x.md](references/upgrading-from-1x.md).

---

## Quick Reference

The **current model** is the schema named by `deployment.public_schema` in `raiconfig.yaml`. `deploy` and `teardown` target it; to change it, edit `deployment.public_schema` and `deployment.identity.internal_schema` together.

| Command | Purpose | Key options |
|---|---|---|
| `rai models init [NAME]` | Scaffold a starter project | `--name` |
| `rai models deploy` | Install model + record diff to op log | `--path` `--name` `--force` `--no-wait` `--wait-timeout` |
| `rai models list` | List models (schema, parent, type, HEAD, owner) | `--limit` |
| `rai models teardown` | Remove the current model's objects + op log (schemas kept) | `--force` |

`deploy --schema` overrides `deployment.public_schema` for that deploy; a target other than the configured model keeps its metadata in `<target>_META`, not `identity.internal_schema`. `teardown` acts on the **current model only** (no `--name`).

---

## Deploy (the foundation)

`rai models deploy` does two things: it installs the model's resources and outputs into the target schema, and — when op-log recording is on — it records the *diff* versus the previously deployed version as operations in the schema's **op log**.

```sh
rai connect                 # validate config + connectivity first
rai models deploy           # blocks until the first refresh completes
```

After a deploy, PyRel reports the count: `3 model history changes recorded.` When nothing is recorded it reports `0 model history changes recorded.`

**The op log is the model's history** — an ordered record of how it changed from one deploy to the next. `deploy` appends to it and `teardown` removes it with the model; you never edit it directly.

See [references/deploy-and-oplog.md](references/deploy-and-oplog.md) for backends and install-only behavior when the op log is off.

---

## The dev loop (develop against a dev schema)

A deployed model is a stateful Snowflake object you develop the way a dbt project develops against a dev schema: point `deployment.public_schema` and `deployment.identity.internal_schema` at schemas you own, then iterate by redeploying — edit, `rai models deploy`, read state back, repeat. Redeploying overwrites the deployed version; it *is* the iteration step. Reasoning runs asynchronously behind the model's refresh tasks, so all execution state comes back through SQL, not a live engine connection.

Validation is two-tier, and the loop should exhaust the cheap tier first:

1. **Compile/deploy time (client-side, seconds)** — deploy compiles and type-checks the model before anything is installed; type and shape errors fail fast, before any reasoner or refresh is involved.
2. **Refresh time (data-dependent)** — constraints that depend on the data (uniqueness, references, functional dependencies) only fail once a refresh runs against real rows, surfacing as a `FAILED` refresh.

Read state with `CALL <internal_schema>.REFRESH_STATUS();` (one row per schedule; the stable contract), drill into the internal schema's refresh log for block-level failures, and reach for `rai doctor report` when you need complete deploy state in one artifact. Full loop, status contract, refresh-log queries, and report interpretation: [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md).

A successful deploy can still print warnings — `[Deploy Step Skipped]` (a missing privilege), `[Dynamic table fallback]`, and, when the model file runs directly, deprecations. Read each one, tell the user what it means and whether it matters, and suggest the fix; never edit the model yourself. Before calling a deploy done, confirm the model holds rows: install and refresh are separate, and with `--no-wait` a failed first refresh still leaves the deploy reporting success over an empty model. How to read each warning: [references/deploy-warnings.md](references/deploy-warnings.md).

### Promote dev to prod

If the team already has an established Snowflake deployment workflow, keep it. Otherwise:

- **Profiles separate dev and prod configuration** — source tables, target schema, roles, and operational settings live in `raiconfig.yaml` profile overlays; deploying to dev vs. prod is switching profiles. Mechanics in `rai-setup`.
- **Role-based access locks down prod** — deploys run as a role; require a higher-privileged role for the production schema than for dev schemas, so no one deploys to prod mid-development. When day-to-day work already runs as ACCOUNTADMIN (a common proof-of-concept start state with no privilege ladder to sit under), express the separation as *isolation* instead: prod schemas owned by a dedicated deploy role granted only to CI/admin — never to developer users — and move dev onto a scoped role as a follow-up.
- **CI owns prod deploys** — developers never hold the prod role day to day; a CI job holds it, runs tests, and triggers the production deployment. The grant set a scoped deploy role needs: [references/deploy-and-oplog.md](references/deploy-and-oplog.md) § Privileges for a custom deploy role.
- **Expectation to set:** redeploys replace changed objects in place — zero-downtime upgrades for schemas with always-on consumers are not supported yet, so plan maintenance windows for prod redeploys.

---

## Teardown

`rai models teardown` drops the current model's objects and op log but keeps its schemas. It is a dry run until you add `--force`. → [references/teardown.md](references/teardown.md)

---

## Reference files

Load only the file matching the task:

| File | Load when |
|---|---|
| [references/deploy-and-oplog.md](references/deploy-and-oplog.md) | Deploying; the op log, backends, turning recording off, install-only mode; refresh schedules, output materialization, the internal schema |
| [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md) | Iterating on a deployed model; two-tier validation; `REFRESH_STATUS` contract, refresh-log queries for block-level failures, `rai doctor report` interpretation |
| [references/deploy-warnings.md](references/deploy-warnings.md) | Reading the warnings a successful deploy prints (deprecations, skipped steps, materialization fallbacks); confirming the deployed model holds rows |
| [references/teardown.md](references/teardown.md) | Removing a deployed model: dry run, `--force`, what teardown keeps |
| [references/upgrading-from-1x.md](references/upgrading-from-1x.md) | Moving a 1.x deployment to 2.0: config renames, keeping the `_META` schema, the first deploy, teardown refusals, op-log recovery |

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| `deploy` fails: "Database '...' does not exist or not authorized" | `deploy` creates the target **schema** but not its database | Create the database first — `deploy` runs `CREATE SCHEMA IF NOT EXISTS <db>.<schema>`. If the deploy role lacks `CREATE SCHEMA`, pre-create the schema and its internal schema and grant `USAGE`; deploy confirms it exists and proceeds |
| `deploy` stops at pre-flight: `is not fully-qualified (Snowflake needs <DATABASE>.<SCHEMA>)` | `deployment.public_schema` is a bare schema name | Use a fully qualified `deployment.public_schema` (`DB.SCHEMA`) |
| `deploy` fails: "Configured Prescriptive Problems require deployment.pat_secret, deployment.pat_eai, deployment.pat_user, and deployment.pat_warehouse" | A `configure()`d Problem without all four `pat_*` fields | [prescriptive-deploy-setup.md](../rai-setup/references/prescriptive-deploy-setup.md) |
| `teardown` dropped nothing | `teardown` is a dry run by default | Check `rai --version` meets the `rai-setup` minimum (older releases drop the schemas), then add `--force` |
| Deploy succeeded but the refresh shows `FAILED` | Data-dependent constraints (uniqueness, references) can only fail once a refresh runs against real rows — deploy-time validation can't catch them | Read `error` from `REFRESH_STATUS`, block detail from the refresh log; fix the model or data and redeploy — see [references/dev-loop-and-monitoring.md](references/dev-loop-and-monitoring.md) |
| Deploy fails: `Invalid expression [CAST(... )] in VALUES clause` | A `model.data(...)` table has a column mixing dates with non-date values | Load the data into a Snowflake table and bind with `model.Table("DB.SCHEMA.TABLE")` — the deploy-mode source pattern |
| Diagnosing a failed refresh from output tables alone | Execution state lives in the internal schema, not the public schema | `CALL <internal_schema>.REFRESH_STATUS();` first, then the refresh log; `rai doctor report` bundles complete state |
| `rai config explain` shows a full `deployment` block though deploy mode is off | The block always renders; deploy mode is on when a `deployment` mapping is given (in the file or the active profile), and that mapping must name `public_schema` and `identity.internal_schema`: an empty one (`deployment: {}`) fails at load with `a 'deployment:' section must name where the model deploys`, and a bare `deployment:` fails validation | `create_config().deployment_enabled` |
| Deploy reported success but queries return nothing | Install and refresh are separate steps: with `--no-wait`, deploy returns before the first refresh, which then failed | Read `REFRESH_STATUS()` and count rows per object before reporting success — see [references/deploy-warnings.md](references/deploy-warnings.md) |

---

## Related Skills
- `rai-setup` — install, `rai connect`, and `raiconfig.yaml` including profile overlays for dev/prod config (do this first)
- `rai-ontology` — build and evolve the model you deploy
- `rai-pyrel` — PyRel syntax and data loading
- `rai-prescriptive-problem` / `rai-prescriptive-results` — `configure()` and reading results after a refresh
- `rai-health` — diagnose engine performance, failed transactions, and CDC health
