# Automatic SQL execution (opt-in)

This skill defaults to copy-paste: every query is handed to the user to run in their own Snowflake session, and the skill waits for pasted-back results. Some users would rather let the agent run the read-only discovery/validation queries itself, against a Snowpark session, so they don't have to shuttle SQL back and forth.

This reference documents that opt-in path. It is loaded only after the user has agreed to it — never load or act on it speculatively.

## What this is (and isn't)

- This is **not** an MCP server integration. There is no Snowflake MCP tool involved.
- It is a Snowpark **Python session**, set up exactly as described in the `rai-setup` skill (`create_config().get_session(...)`), that the agent runs directly via its Python/Bash execution tools.
- The mechanism is identical to the one `rai-predictive-modeling`'s auto-discovery flow uses to query Snowflake during schema discovery.

## When to offer this

Offer it once, near the start of Step 1 (before Turn 1A-i), as a single yes/no question — never assume it. See the "Step 0" block in `GUIDED.md`. (The `one-shot` sub-skill has no opt-in question here — its own Step 0 makes a live connection a hard, unconditional prerequisite instead.) If the user has already said yes earlier in the conversation, don't ask again; if they said no, don't ask again either — just proceed with copy-paste for the rest of the session unless they bring it up.

If the user agrees but a working Snowflake connection can't be established, don't just report the error and quietly drop back to copy-paste — offer to fix it. See "Environment isn't ready" below.

## Two permission tiers — do not blur them

Opting in unlocks **read-only** auto-execution only. It does **not** authorize writes. Treat every query in this skill as one of:

| Tier | Statement types | Behavior once opted in |
|---|---|---|
| **Read-only** | `SELECT`, `SHOW`, `DESCRIBE`, anything reading `information_schema` | Run automatically, no per-query confirmation. This covers: Query 1 (column schemas), Query 2 (sample rows), the date range query, the prediction-window-vs-data-density check (when relevant — see `GUIDED.md`'s Step 3), and the Step 4 validation queries. |
| **Write / DDL** | `CREATE SCHEMA`, `CREATE TABLE`, `CREATE OR REPLACE TABLE`, `INSERT`, anything that creates or overwrites objects | **Default: never** auto-run on the read-only opt-in alone. Always show the exact SQL and ask an explicit "shall I run this now?" before executing — every time, not just once. These statements create or overwrite real tables in the user's Snowflake account, which is a hard-to-reverse, shared-system change. **Narrow exception**: if the user's own *opening* message — not their answer to the Step 0 read-only question — explicitly states that writes may also run without further confirmation (e.g. "you don't need to ask me again before each statement, just proceed"), treat that as standing, session-scoped consent for writes too. State plainly what you're about to run immediately before running it — never run a write silently, even under this exception. A vague "get started" or "go ahead" does **not** qualify: the user's own words must unambiguously cover *every subsequent statement*, not just permission to begin. |

This mirrors the read vs. write action guidance elsewhere: local reversible reads can run freely once permitted; anything that mutates shared state normally gets a fresh confirmation each time, regardless of standing opt-ins — unless the user's own words have already, explicitly, covered writes too, per the exception above.

⚠️ Per-statement confirmation reduces the risk of an LLM running SQL against a real database but doesn't eliminate it, so recommend a user/role scoped to only the database used for the task table (per `GUIDED.md`'s and `ONE_SHOT.md`'s Step 0 disclosures), not broader account access.

## Resolving a Python environment — scoped to this repo only

Read `utils_python_environment.md` and follow it now, resolving/installing
`relationalai>=1.20.1` specifically (lazily — only at this point, once the user has
actually opted into auto-execution; don't install it speculatively). If a venv already
exists in this repo (e.g. because `utils_validation.md` already set one up for
`sqlglot`), reuse that same venv — don't create a second one.

From then on, every command in this reference — `rai init`/`rai connect` and the
session setup below — must run through whichever venv's `bin/python` you resolved (or
its `bin/rai`), never a bare `python3`/`pip`. Remember the path for the rest of the
session so you only resolve it once.

## Setting up the session

Follow `rai-setup` to establish the connection (existing `raiconfig.yaml` / `~/.snowflake/config.toml`, or walk the user through creating one). `create_config()` resolves `raiconfig.yaml` relative to the current working directory, not the repo root by path — run the session setup below (and every subsequent `run_sql` call) from the repo root where the config file actually lives, or `create_config()` will report it as missing even though it exists. Then set up the session once per conversation, using the venv's interpreter resolved above, and reuse it:

```python
# run with the resolved venv's bin/python, not a bare python3
import json

from relationalai.config import SnowflakeConnection, create_config
from snowflake import snowpark

session: snowpark.Session = create_config().get_session(SnowflakeConnection)


def run_sql(query: str) -> list[dict]:
    """Execute a SQL statement and return rows as a list of dicts."""
    with open("/tmp/sql_execution_log.jsonl", "a") as f:
        f.write(json.dumps({"sql": query}) + "\n")
    rows = session.sql(query).collect()
    return [row.as_dict() for row in rows]
```

The log line runs unconditionally, before execution — so a statement that fails to execute is still recorded. This is what lets eval verifiers inspect every statement the agent actually ran, without having to parse arbitrary agent-written Python out of the trajectory.

Use `run_sql` for every read-only query in this skill instead of printing it for the user to copy-paste. Present the returned rows the same way you would have summarized pasted-back results — don't dump raw Python objects into chat.

## Applying it to each step

- **Turn 1A-ii (column schemas + sample rows)**: run Query 1 and Query 2 via `run_sql`, then go straight into Turn 1B-i (temporal/non-temporal decision) with the results — skip the "paste results back" language entirely.
- **Date range query (Step 3)**: whenever that subsection says to send the date range query, run it yourself via `run_sql` instead and fold the result straight into the cutoff-strategy or train/val/test-split discussion it's feeding — no need to wait for a pasted reply.
- **Prediction window vs. data density check (Step 3)**: when `GUIDED.md`'s relevance rule says this check applies, run it yourself via `run_sql` and fold the result straight into that discussion — no need to wait for a pasted reply. Still ask the one confirmation question if the result shows a mismatch (widen the window / reconsider the policy?) — auto-execution covers *running the query*, not deciding the answer on the user's behalf. If they decline the suggested fix, proceed and don't ask again, same as the manual case.
- **Step 4 validation queries**: run them via `run_sql` and report row counts / nulls / class balance / leakage checks directly. Still show the validation SQL in the artifact — the user may want to rerun it later or hand it to someone else.
- **Step 4 Schema / STAGING / Split tables**: always write-tier. Show the SQL, then ask "Should I run this against `<DB>.<SCHEMA>` now?" and wait for an explicit yes before calling `run_sql`. Ask separately for STAGING and for the split tables — confirming STAGING doesn't imply consent for the split tables, since the skill's own convention is that validation happens between the two. Execute an approved section statement-by-statement via `run_sql`, selecting statements by their `CREATE`/`INSERT` target — never by substring-matching the artifact text (a split-table CTAS contains `FROM ...STAGING`, so a "staging" substring filter sweeps in the split tables). State the targets about to run before executing.

## Environment isn't ready

When the user agrees to auto-execution, actually attempt to establish the session before assuming anything is missing — don't ask setup questions preemptively. If `create_config()` / `get_session()` fails, diagnose *why*, but keep your own involvement minimal — how to connect to Snowflake (which authenticator, which credentials, which config file) is the user's decision, not yours to guess, infer, or engineer around. Never say something like "the rai-setup skill failed" — the user doesn't know that skill exists; describe the problem in plain terms.

**Never debug this by reading `relationalai`'s own source code** (its config-discovery logic, error-handling internals, etc.). Treat the library as a black box: run `create_config()` / `get_session()` / `rai connect`, read the error message it prints, and act on that message alone. If a config file's discovery behaves unexpectedly (e.g. a file exists but the library still reports it as missing), that is itself the reportable problem — hand it to the user as "I found `<path>` but the connection still isn't picking it up" rather than opening the library's source to figure out why. Likewise, don't probe a credentials file's contents, permissions, or byte count beyond a plain existence check (`test -f` / `os.path.exists`) — it isn't yours to inspect.

One exception to "act on the message alone": on newer `relationalai` versions (confirmed on 1.25.0), `create_config()` can print a benign warning like `[config.unknown-field] Unknown config field 'reasoners....' — ignoring` for config fields older versions didn't have. This is not a connection failure — it's the library tolerating a config file written for a different version. Don't chase it as one; check whether the session actually came back and the trivial validation query (below) actually ran before concluding anything is wrong.

1. **`ImportError` / package not found** — the `relationalai` package isn't installed anywhere usable in this repo. This is a mechanical, no-judgment-call fix: tell the user ("I need the `relationalai` Python package to connect directly — want me to install it?") and, if they agree, resolve the venv per "Resolving a Python environment" above (reuse this repo's own venv if it has one, otherwise create `<repo_root>/.venv`) and install into it. Re-attempt the session, through that same venv's interpreter, after installing.
2. **No usable connection** — no `raiconfig.yaml`, or an existing config PyRel can't use as-is (e.g. a CLI config missing a required field). Run `rai init` to scaffold a fresh `raiconfig.yaml` (or write the minimal template below if `rai init` isn't available). Do **not** try to auto-discover or copy credentials from `~/.snowflake/config.toml`, `~/.dbt/profiles.yml`, or anywhere else, and do not guess which authenticator the user wants — that's the connection method the user needs to choose. Tell the user the file now exists with placeholder values, and ask them to fill in the correct values for their own setup, in the file, however they normally connect (username/password, key pair, SSO, etc.). Then stop and wait — don't keep editing the file yourself.

   ```yaml
   default_connection: sf
   connections:
     sf:
       type: snowflake
       authenticator: username_password
       account: my_account
       warehouse: my_warehouse
       user: my_user
       password: {{ env_var('SNOWFLAKE_PASSWORD') }}
   ```
3. **Connection configured but `rai connect` fails** — run `rai connect` once to get the concrete error and show it to the user verbatim. You may point at the matching row in `rai-setup`'s Common Pitfalls table if one obviously applies, but the fix is the user's call — don't start iterating on the file yourself (swapping authenticators, adding env vars, hunting for keys, etc.) and don't go spelunking in the library's source to explain the error. Ask what they'd like to change, or whether they'd rather fall back to copy-paste.
4. **After the user says the file is ready — or after fixing the Python environment — always validate before proceeding**: retry `create_config().get_session()` and run one trivial query (e.g. `SELECT CURRENT_ACCOUNT()`) through it. A config file existing, or a venv having the package installed, is not sufficient evidence the connection works — only a query that actually returns a row counts as validated. If it works, proceed with auto-execution for the rest of the session. If it still fails, show the new error and let the user decide the next move — don't loop through fix attempts on your own.
5. **If the user doesn't want to set this up right now**, fall back to copy-paste for the rest of the session — don't keep re-prompting.

Installing the package into this repo's venv is a mechanical, low-risk action — fine to do once the user agrees, no further confirmation needed. Everything else in this section is the user's call: scaffold the file, then get out of the way. Never ask the user to paste a password, key, or passphrase into chat, and never write one into the file yourself — they edit the file directly.

Never fabricate query results. If a read-only query fails for a reason other than session setup (typo, missing table, permission error), surface the actual error and let the user decide whether to fix the query or fall back to running it themselves.
