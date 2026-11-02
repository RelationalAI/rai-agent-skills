# Deploy warnings: read them, explain them, suggest the fix

> **Early access** — the `rai models` deploy/lifecycle surface may change (API, messages, defaults). See `rai-deployment` § Prerequisites.

A deploy that reports success still tells you things. Skipped steps and materialization fallbacks
arrive on a successful run and are easy to scroll past; deprecations may not show at all (§1). This
file is how to read them.

**The rule: deploy output is read, not just relayed.** After every deploy, classify what came back, tell
the user what each item means and whether it matters, and suggest the change. Do not apply the
change yourself, do not retry, and do not rewrite the model on the user's behalf.

## 1. Deprecation warnings

```
energy.py:351: DeprecationWarning: Substation.filter_by(...) is deprecated. Use Substation.lookup(...) instead.
```

Nothing is broken and nothing is blocked; the call will stop working in a future release.

**Say:** which call is deprecated, what replaces it, and the file and line. Offer the edit; make it
only if asked. If the same deprecation appears many times, say how many and list the distinct call
sites, not every occurrence.

`rai models deploy` loads the model as a module, where Python hides `DeprecationWarning` by
default; these show when the model file is run directly (`python model.py`) or in a notebook. No
deprecation in deploy output does not mean none exist — to surface them on a deploy, run it with
`PYTHONWARNINGS=default::DeprecationWarning`.

## 2. Permission warnings — a step was skipped

```
[Deploy Step Skipped] The deploying role lacks a privilege this step needs, so it was skipped.
  Impact: Refresh runs won't emit trace events or span attributes, so you won't see refresh traces. Grant MODIFY TRACE LEVEL ON ACCOUNT to the deploying role to enable them.
  Statement: ALTER PROCEDURE … SET TRACE_LEVEL = 'ALWAYS'
  <Snowflake error>
```

The deploy succeeded with something missing. The message already carries the impact and the remedy.
The sibling `LOG_LEVEL` step names MODIFY LOG LEVEL ON ACCOUNT (refresh logs). Each refresh
procedure warns separately, so the same grant can appear more than once — name each distinct grant
once. If the reason reads `This step failed and was skipped.` instead, it was not a privilege
problem: quote the Snowflake error that follows.

**Say:** the deploy succeeded, what capability is absent (event-table logs or traces only;
`REFRESH_STATUS` and the refresh log still work), and that an admin has to grant the named
privilege — the developer usually cannot. Do not retry the step, and do not suggest running the
deploy under a different role unless the user raises it.

## 3. Dynamic-table fallback — the one worth understanding

```
[Dynamic table fallback] Table 'SUPPLY_CHAIN.TMP_SUPPLY_CHAIN.Region' was configured as a
DYNAMIC TABLE but its query has no base-table reference. Snowflake requires dynamic tables to
reference at least one stored relation. Falling back to a plain TABLE.
```

A plain `TABLE` loses incremental refresh. Whether the warning can be rewritten away depends on
the cause:

| warning | cause | rewritable? | what to tell the user |
|---|---|---|---|
| `[Dynamic table fallback]` … no base-table reference | the concept is populated from inline `model.data()` | **Yes** | Bind it to a source table and it becomes incremental. |
| `[Dynamic table fallback]` … no base-table reference | the concept is a fixed set of constants or an enum | **No — by design** | Nothing to be incremental about; the table is tiny. The fallback is expected. |
| `[Recursive table fallback]` | an explicit materialization override on an output that is part of a recursive computation | **Yes — in config** | Recursive outputs must be plain tables. Change the override to `table` or remove it. Without an override, PyRel materializes them as tables and does not warn. |
| `[Volatile object materialized]` | the definition reads `datetime.now()` | Only by removing `now()` | Each refresh computes the value once per run, which is usually the intent. Report it; don't rewrite. |

To tell the first two apart, look at the concept's definition in the model: literal
`model.data(...)` versus a fixed constant or enum set.

## 4. After a successful deploy, check the model actually holds data

The most expensive silent state is not a warning at all: **a deploy can report success and the
model can contain no rows.** Install and refresh are separate: without `--wait`, deploy returns once
the model is installed, so a first refresh that then fails leaves the deploy reading as a success.
(`--wait` raises `Refresh task … failed` instead.) `[Refresh Tasks Cannot Run]` means the same
outcome with or without `--wait`: the tables exist but nothing refreshes them (on a redeploy, they
stay at their old contents) — relay the grant it names and the manual-refresh `CALL` it prints.
`[Refresh Task Privileges Unverified]` means PyRel could not confirm the grant; if the tables stay
empty, that grant is the first suspect.

After any deploy, before telling the user it worked:

1. Read the refresh state — [dev-loop-and-monitoring.md](dev-loop-and-monitoring.md) § Reading
   refresh state.
2. Count rows in the deployed objects. Any concept at zero rows that should not be empty is the
   headline, not a footnote.

Report shape: *"Deployed 28 objects, but the first refresh failed — `Shipment` and `Business` are
empty. The model installed but does not answer questions about shipments yet."*

## What this does not cover

- Rewriting the model. Suggest; do not edit.
- Fixing PyRel code-generation defects. If generated SQL fails to execute, that is a platform bug —
  capture the statement and the error, and say so.
- A catalogue of every warning the platform can emit. Most other deploy warnings
  (`[Change Tracking Not Enabled]`, `[Refresh Auto-Suspend]`, `[Multiple Refresh Schedules]`, …)
  state their own impact and fix — relay them under the same rule. Anything you cannot explain,
  quote it and say plainly that you do not know what it means.
