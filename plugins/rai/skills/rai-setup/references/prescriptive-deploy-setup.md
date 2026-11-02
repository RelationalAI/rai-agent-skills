# Prescriptive Deploy Setup (PAT, EAI, grants)

> **Preview.** Needs `relationalai>=1.30.3` (the setup page says 1.30.1, but deployed refreshes
> first write solver results in 1.30.3). Snowflake only.

One-time setup so a **configured** Problem (`problem.configure(...)`, see
`rai-prescriptive-problem`) can run inside a deployed model's refresh. Without it,
`rai models deploy` fails at plan time:
`Configured Prescriptive Problems require deployment.pat_secret, deployment.pat_eai,
deployment.pat_user, and deployment.pat_warehouse; missing: ...`

Each refresh reads a programmatic access token (PAT) from a Snowflake secret, through a function
the deploy binds to an external access integration (EAI), and the solve runs as the token's
user, restricted to one role (`<PAT_ROLE>`).

## Setup

The SQL is on RelationalAI's Early Access page
[Set up model deployment](https://private.relational.ai/early-access/model-deploy-setup), which
opens without a login. Fetch it and run its scripts as written, most of them as ACCOUNTADMIN,
rather than writing your own. Through `snow sql` or SnowSQL, put each procedure body between
`AS $$` and `$$` and run each anonymous `BEGIN … END;` block as `EXECUTE IMMEDIATE $$ … $$;`.
Read each procedure's result: the model-role procedure reports a failed app grant as a
`WARNING` in it, not as an error.

**Restrict the PAT to the role that deploys the model** (`<MODEL_ROLE>`, also `deployment.role`
and the connection `role`). A different deploying role owns the refresh tasks and the token
function, so it also needs `USAGE` on the EAI and on the secret's database and schema, and `READ`
on the secret, granted again after every rotation. Any role holding `<PAT_ROLE>` can read the
plaintext token; give no other role `READ` on the secret.

Create the deployment schema as the deploying role, then grant on it, then deploy: those grants
must be in before the first refresh (on 1.36.0 the meta-schema grants can only follow the deploy,
below). Create only the schema; the deploy creates its own tables and will not overwrite objects
it did not create.

**Network policy.** Snowflake accepts a PAT login only under a network policy, and the one that
applies to the PAT user must let in the solver's compute pools. Never open public IP access or
allow all compute pools to get past a failure, and never attach an authentication policy that
lets PAT logins skip the network policy.

## Config

```yaml
deployment:
  role:          <MODEL_ROLE>
  schema:        <DEPLOYMENT_DB>.<DEPLOYMENT_SCHEMA>
  pat_secret:    <DB>.<SCHEMA>.<SECRET>        # fully qualified, unquoted
  pat_eai:       <EAI>
  pat_user:      <PAT_USER>                    # the token's owner, not whoever runs the CLI
  pat_warehouse: <PAT_WAREHOUSE>
```

PyRel checks only that the fields are present, paired (`pat_secret` with `pat_eai`, `pat_user`
with `pat_warehouse`) and well-formed, never the token or its grants. A role-restricted session
ignores secondary roles, so `<PAT_WAREHOUSE>` must be usable by `<PAT_ROLE>` itself.

## Rotation

Rotate by re-running the page's token procedure with the same arguments, as the same identity.
It recreates the secret, which drops every other grant on it, so re-grant `READ` to a deploying
role other than `<PAT_ROLE>` after each run. No redeploy is needed: each refresh reads the secret.
Rotation keeps the old token valid for a grace period, so if it may have leaked, first remove it
and its rotated copy (`SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER <PAT_USER>`, then
`ALTER USER <PAT_USER> REMOVE PROGRAMMATIC ACCESS TOKEN <name>`).

## Troubleshooting

| Symptom | Check |
|---|---|
| `deployment.pat_secret must be fully qualified as <database>.<schema>.<secret_name>`, or `deployment.pat_eai must be an unquoted Snowflake identifier` | Three unquoted identifier parts for `pat_secret`, one for `pat_eai` |
| `Secret '<name>' does not exist or operation not authorized` at deploy, or `002001 ... Object '<secret>' does not exist or not authorized` in a refresh | The deploying role lacks `READ` on the secret, typically after a rotation. Check as that role with `USE SECONDARY ROLES NONE`; default secondary roles can hide the gap |
| `[Unknown Table] Failed to fetch schema for table '<...>'` | The deploying role lacks `USAGE` on the source database or schema, or `SELECT` on the table |
| `Unknown user-defined function <app>.API.USE_INDEX` | The model role lacks the app's `RAI_USER` application role: its setup procedure returned a `WARNING`, for example for an app installed under another name |
| `Prescriptive reasoner already exists but does not match requested configuration` | A reasoner with that name exists at another size or settings; match `reasoners.prescriptive.size`, or name another |
| The solve fails with a generic `connector.other` | The error alone does not separate a PAT, network-policy or grant cause. Look in the PAT user's query history (`INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(USER_NAME => '<PAT_USER>')`, as ACCOUNTADMIN) for a grant `<PAT_ROLE>` or the app lacks (`USAGE` on `<PAT_WAREHOUSE>`, or on 1.36.0 the meta schema, below), in login history for a failed PAT login, and on a development-mode app in the service log for its owner role lacking the app's caller grants (the page's development-mode note) |
| Refresh fails at the solver with `job could not be created (RAIERR:1000)` | Seen when the PAT was removed or expired: check `SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER <PAT_USER>`, then rotate and refresh; no redeploy |
| A PAT login fails with `390432 Network policy is required` | No network policy applies to the PAT user |

## As of relationalai 1.36.0 (expected to change before GA)

- A Problem's own tables (variables, constraints, solver results, `solve_info`) live in
  `<meta_schema>`: `<DEPLOYMENT_SCHEMA>_META` unless `deployment.meta_schema` names another.
- The app needs caller grants there too. Schema-wide on `<meta_schema>`: caller `USAGE`,
  `INHERITED CALLER SELECT` on all tables and views, and `INHERITED CALLER READ, WRITE` on all
  stages (a large result is loaded through a temporary stage there). Per table:
  `CALLER INSERT, DELETE, TRUNCATE` on each solver result table (`SOLVERRESULT…` in
  `SHOW TABLES IN SCHEMA <meta_schema>`). Never grant `INSERT`, `DELETE` or `TRUNCATE` there
  schema-wide: the refresh runs the SQL stored in `<meta_schema>._INTERNAL_PLAN` with the
  deploying role's full privileges. A separate `<PAT_ROLE>` also needs its own `USAGE`, `SELECT`
  on all tables and views, and `INSERT, DELETE, TRUNCATE` on each result table, but no stage
  privilege. The result tables appear at the first deploy and a new Problem adds more, so grant
  after deploying, re-check after each redeploy, then refresh
  (`EXECUTE TASK <meta_schema>.REFRESH_<SCHEDULE>`).
- Upgrading from an earlier release: redeploy, grant, then refresh. Until the grants exist the
  solve fails with `connector.other`, and the PAT user's query history shows `Schema
  '<meta_schema>' does not exist or not authorized. This executable runs with restricted
  caller's rights`.
- A deploying role without account-level `EXECUTE TASK` fails the deploy with `Could not start
  the model's refresh tasks` (earlier releases warned `Refresh Tasks Cannot Run`, and nothing
  refreshed): grant it, or make every schedule manual-only, then deploy again.
- `rai models deploy --wait` blocks until the first refresh ends; without it, deploy returns
  first. A pending PyRel change makes waiting the default and deprecates `--wait`.
