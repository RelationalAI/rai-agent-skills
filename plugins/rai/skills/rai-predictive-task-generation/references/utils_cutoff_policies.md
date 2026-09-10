# Cutoff Policies

This file defines the six supported cutoff policies.

## What is a cutoff policy?

A cutoff policy is the rule that decides **when** in time the model is asked to make a prediction for each entity.

Every training example in the task table is a snapshot: "as of date T, here is everything we know about this entity — now predict what happens in the next N days." The cutoff policy determines how those dates T are chosen across the dataset.

The choice of policy directly shapes what the model learns:
- A policy tied to the creation event trains a model that predicts outcomes at birth.
- A policy that samples across the entity's lifespan trains a model that can predict at any point in time.
- A policy based on fixed calendar dates trains a model evaluated at standardised, comparable snapshots.

Choosing the right policy is not a technical detail — it is the same as choosing the prediction question itself.

## Before presenting the menu

### Step A — rewrite for session

Always show all six policies. Rewrite each policy's description, "best for" cell,
and "how the user invokes it" phrases to reference the actual entity name, event
timestamp column, and prediction question for this session. Do not show generic
placeholders. Do not exclude any policy.

### Step B — decide whether a policy is strongly recommended for this session

Do not default to Policy 1 automatically, and do not strongly recommend a policy
just because the label happens to fit one of the other policy descriptions. A
strong recommendation is reserved for exactly one case:

- **Is the label a fixed/intrinsic property of the entity that is already
  determined at (or before) the entity's own event timestamp** — i.e. it is not a
  forward-looking outcome observed over a window after cutoff, and there is no
  reason to evaluate the entity at any other point in its life? (e.g. a badge's
  `CLASS` is fixed the moment the badge is awarded; there is nothing to gain by
  sampling a cutoff earlier or later than `BADGES.DATE`.) → strongly recommend
  **Policy 3 (`event_relative`)**.

**In every other case, do not tag any policy as strongly recommended** — including
when the user has already stated a preference for one cutoff per entity, or for
cutoffs anchored to the entity's own event timestamp. A forward-looking label
(one evaluated over a window after cutoff) is not intrinsic, even if the user
wants a single cutoff per entity; that stated preference is a legitimate reason
to expect the user to pick Policy 3 themselves, not a basis for the skill to
recommend it on their behalf. Present all six policies neutrally and let the
user choose.

When a strong recommendation does apply, state the tag next to that policy's
**name**, not in its "Best for" cell, and add one sentence above the tables
explaining why, grounded in the session's actual label/entity semantics (not a
generic restatement of the policy description).

Only after completing Steps A and B, show the menu and wait for the user's reply.

---

## How to present to the user

Always present the menu as markdown tables — never as a numbered list or prose. Show all six policies (rewritten for the session). Whether it's one table or two depends on the Step B outcome:

**If Step B found a strong recommendation** (intrinsic-label case only): split the recommended policy out into its own single-row table above the rest, with `(strongly recommended)` appended after its name in the **Policy** column — never in "Best for". Between the two tables, add the phrase `Alternative policies` on its own line. Number the rows **sequentially 1–6 in display order** — recommended policy first, then the remaining five in their usual relative order — so the `#` column ascends from top to bottom across both tables. Do not reuse each policy's fixed section number from this file (e.g. `event_relative` is "Policy 3" in the headings below, but displays as `1` in the menu whenever it's the session's recommended pick).

| # | Policy | Best for |
|---|---|---|
| 1 | event_relative (strongly recommended) | <rewrite for session> |

Alternative policies

| # | Policy | Best for |
|---|---|---|
| 2 | generate_timestamp_randomly_from_range | <rewrite for session> |
| 3 | sample_timestamp_randomly_from_range | <rewrite for session> |
| 4 | rolling_fixed | <rewrite for session> |
| 5 | calendar_aware | <rewrite for session> |
| 6 | custom | <rewrite for session> |

(The example above assumes `event_relative` was the Step B pick, so it is renumbered to `1`; the other five keep their relative order — `generate_timestamp_randomly_from_range`, `sample_timestamp_randomly_from_range`, `rolling_fixed`, `calendar_aware`, `custom` — renumbered `2`–`6`. `calendar_aware` (Policy 5) is never the Step B pick — see its own section below — so it always appears in the alternatives table, never split out.)

**If Step B found no strong recommendation** (the common case): show a single table with all six policies in their fixed file order, numbered 1–6 to match this file's own Policy numbers. Do not tag any row, and do not split out a table.

| # | Policy | Best for |
|---|---|---|
| 1 | generate_timestamp_randomly_from_range | <rewrite for session> |
| 2 | sample_timestamp_randomly_from_range | <rewrite for session> |
| 3 | event_relative | <rewrite for session> |
| 4 | rolling_fixed | <rewrite for session> |
| 5 | calendar_aware | <rewrite for session> |
| 6 | custom | <rewrite for session> |

Type a number (1–6) as shown in the table, a policy name, or describe what you want. Resolve a numeric reply against the displayed table for that session.

---

## How to present the chosen policy's parameters

Once a policy is chosen, always present its parameters as a table — never as prose or a bullet list — with three columns: **Parameter**, **Default**, **Description** (all taken verbatim from that policy's own parameters table below). Keep this table form even for policies with only one parameter. `time_unit` is always listed first, before any other parameter, regardless of how future edits reorder the rest of a policy's table.

---

## Policy 1 — generate_timestamp_randomly_from_range

**Description**: Each entity gets a randomly generated set of synthetic cutoffs
across its lifespan. Each entity's target cutoff count is drawn once, uniformly
between `min_cutoffs_per_entity` and `max_cutoffs_per_entity`, capped by however
many distinct cutoffs its eligible window can actually support at the chosen time
granularity.

**When to recommend**: When the prediction question applies at any point in the
entity's life, not just at creation — i.e. the label is a forward-looking outcome
that could in principle be evaluated from many different points in the entity's
history, not a property already fixed at a single moment. See Step B rule 2.

**Parameters** — confirm each with the user before generating SQL:

| Parameter | Default | Description |
|---|---|---|
| `time_unit` | Inferred from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data) | The unit used to interpret every duration-valued parameter in this policy (e.g. `min_lifespan`) |
| `min_cutoffs_per_entity` | 3 | Lower bound of the randomly sampled target cutoff count per entity |
| `max_cutoffs_per_entity` | 5 | Upper bound of the randomly sampled target cutoff count per entity |
| `cutoff_start` | Entity's event timestamp | Earliest possible cutoff per entity |
| `cutoff_end` | `MAX_SAFE_DATE` (data end − prediction window) | Latest possible cutoff |
| `dates_to_exclude` | `None` (every date in `[cutoff_start, cutoff_end]` is eligible) | Optional dates to exclude from the eligible set — given either as a named (holiday) calendar (e.g. `US_FEDERAL_HOLIDAYS`, `UK_BANK_HOLIDAYS`) or an explicit list of dates, provided manually or sourced from an existing database table/column. Always a blocklist: matching dates are removed from `[cutoff_start, cutoff_end]` before synthetic cutoffs are generated. |
| `min_lifespan` | 0 | Entities whose lifespan, measured in `time_unit`, is below this threshold are excluded |
| `no_eligible_window_action` | `exclude` | What happens to an entity whose own event timestamp already falls after `cutoff_end` — the eligible range `[cutoff_start, cutoff_end]` is empty, so zero cutoffs are possible. Only `exclude` is meaningful here, since there's nothing to include. |
| `below_min_action` | `exclude` | What happens to an entity whose eligible range is non-empty but can't fit `min_cutoffs_per_entity` distinct cutoffs at the chosen time granularity: `exclude` (drop the entity entirely) or `include_partial` (keep it with however many distinct cutoffs its window can support) |

**Implementation note**: Each qualifying entity is assigned a random target cutoff
count, drawn uniformly between `min_cutoffs_per_entity` and `max_cutoffs_per_entity`
and capped by however many distinct cutoffs its eligible window
`[cutoff_start, cutoff_end]` can support. That many synthetic cutoff timestamps are
then generated **without replacement** — the target count is a guarantee, not an
upper bound, so an implementation must not draw candidate timestamps independently
and deduplicate afterward, since that can silently under-produce cutoffs (most
severely when the window is only as large as the target count itself, where every
draw must land on a distinct day for the count to be met at all). A safe pattern
splits entities into two branches rather than applying one oversample-and-dedupe
pass to everyone: entities whose eligible window is narrow (smaller than however
many candidates the wide-window branch oversamples, e.g. under 20 if that branch
draws 20 independent candidates) must enumerate every distinct candidate timestamp
in the window directly — via a row generator sized to the window, so every possible
value is guaranteed to be produced — rather than relying on random draws that could
miss one. Entities with a comfortably wider window may use oversample-and-dedupe
(draw more independent random candidates than needed, then `DISTINCT` and rank via
`ROW_NUMBER() OVER (PARTITION BY entity ORDER BY RANDOM())`, keeping the first
`target_cutoff_count`), since collisions there are negligible. Applying
oversample-and-dedupe uniformly — including to narrow-window entities near the
`below_min_action` boundary — risks silently under-producing cutoffs for exactly the
entities with the fewest candidates to spare; the narrow-window branch exists to
close that gap. Entities whose own event timestamp is already after
`cutoff_end` (empty eligible range) are handled per `no_eligible_window_action`.
Entities whose eligible range can't fit `min_cutoffs_per_entity` distinct cutoffs
are handled per `below_min_action`: dropped entirely if `exclude`, or kept with
their shorter list of cutoffs if `include_partial`.

**How the user invokes it**: `1`, `generate_timestamp_randomly_from_range`, or any phrase expressing multiple
random cutoffs — rewrite examples using the session's entity name.

---

## Policy 2 — sample_timestamp_randomly_from_range

**Description**: Like `generate_timestamp_randomly_from_range`, but cutoff dates
are not generated synthetically — they are drawn by random sampling from the set of
distinct real timestamp values within the eligible range. Each entity receives between
`min_cutoffs_per_entity` and `max_cutoffs_per_entity` cutoffs, sampled without
replacement from those real timestamp values that fall in `[cutoff_start, cutoff_end]`.
Whether those real values are drawn from the whole table or only from this entity's own
event history is controlled by `per_entity_dates` — see the parameters below.

The key difference from Policy 1: cutoffs are always anchored to real event dates in
the data (e.g. actual submission dates that exist in the table) rather than arbitrary
points on a continuous timeline. This avoids cutoffs at moments when nothing happened
and keeps the model's prediction context aligned with observable events.

**When to recommend**: When the event timestamp column has a discrete set of meaningful
values (e.g. submission dates, transaction dates, posting dates) and you want cutoffs
to coincide only with real events — not synthetic interpolated timestamps.

**Parameters** — confirm each with the user before generating SQL:

| Parameter | Default | Description |
|---|---|---|
| `time_unit` | Inferred from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data) | The unit used to interpret every duration-valued parameter in this policy (e.g. `min_lifespan`) |
| `per_entity_dates` | `False` | If `True`, eligible cutoff dates are restricted to this entity's own event history instead of the whole table. If `False` (default), dates of all entities are considered. |
| `min_cutoffs_per_entity` | 3 | Minimum number of cutoffs to sample per entity |
| `max_cutoffs_per_entity` | 5 | Maximum number of cutoffs to sample per entity |
| `cutoff_start` | Entity's event timestamp | Earliest eligible timestamp value to sample from |
| `cutoff_end` | `MAX_SAFE_DATE` (data end − prediction window) | Latest eligible timestamp value to sample from |
| `dates_to_exclude` | `None` (every real timestamp value in `[cutoff_start, cutoff_end]` is eligible) | Optional dates to exclude from the sampling pool — given either as a named (holiday) calendar or an explicit list of dates, provided manually or sourced from an existing database table/column. Real timestamp values matching an excluded date are removed before sampling. |
| `min_lifespan` | 0 | Entities whose span from first to last eligible timestamp, measured in `time_unit`, is below this threshold are excluded (hard filter, based on time span) |
| `no_eligible_window_action` | `exclude` | What happens to an entity whose own event timestamp already falls after `cutoff_end` — the eligible range `[cutoff_start, cutoff_end]` is empty, so zero cutoff dates are possible. Only `exclude` is meaningful here, since there's nothing to include. |
| `below_min_action` | `exclude` | What happens to an entity whose eligible range is non-empty but contains fewer than `min_cutoffs_per_entity` distinct real dates: `exclude` (drop the entity entirely) or `include_partial` (keep it with whatever eligible dates it has) |

**Implementation note**: The SQL implementation joins the entity to the distinct
timestamp values that fall within `[cutoff_start, cutoff_end]`, drawn from the whole
event table when `per_entity_dates = False`, or restricted to that entity's own rows
(joined on the entity's foreign key) when `per_entity_dates = True`. Each qualifying
entity is then assigned a random target cutoff count, drawn uniformly between
`min_cutoffs_per_entity` and `max_cutoffs_per_entity` and capped by however many
eligible dates it actually has, and a `SAMPLE` or `ROW_NUMBER() / RAND()` pattern
draws that many rows per entity without replacement. This target-count randomization
applies identically regardless of `per_entity_dates` — it operates only on however
many eligible dates each entity has, not on where those dates were sourced from.
Entities whose own event timestamp is already after `cutoff_end` (empty eligible
range) are handled per `no_eligible_window_action`. Entities with a non-empty range
but fewer than `min_cutoffs_per_entity` eligible dates are handled per
`below_min_action`: dropped entirely if `exclude`, or kept with their full (shorter)
list of eligible dates if `include_partial`.

**How the user invokes it**: `2`, `sample_timestamp_randomly_from_range`, or phrases
like "sample from real dates", "use actual submission dates as cutoffs", "only cut
at dates that exist in the data" — rewrite these examples using the session's entity
and event timestamp column name.

---

## Policy 3 — event_relative

**Description**: One cutoff per entity, set at the entity's own event timestamp.
The model always predicts "from the moment the entity was created."

**When to recommend**: When the prediction question is inherently tied to the moment
of creation or submission — most strongly when the label itself is a fixed/intrinsic
property of the entity that is already determined at (or before) that moment, so
there is no other point in the entity's life worth evaluating it at (e.g. classifying
a badge by its `CLASS`, which is set the instant the badge is awarded). See Step B
rule 1.

**Parameters**:

| Parameter | Default | Description |
|---|---|---|
| `time_unit` | Inferred from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data) | The unit used to interpret every duration-valued parameter in this policy (e.g. `min_lifespan`) |
| `event_timestamp` | The event timestamp column identified in Step 1 (e.g. `PAPERS.Submission_Date`, `CUSTOMERS.created_at`) | The column whose value defines `cutoff_ts` for each entity — i.e., the single cutoff is set to this column's value |
| `cutoff_end` | `MAX_SAFE_DATE` (data end − prediction window) | Latest possible cutoff — entities whose own event timestamp falls after this value are excluded, since there is no eligible cutoff for them |
| `min_lifespan` | 0 | Entities whose lifespan — measured in `time_unit`, from their own event timestamp to `cutoff_end` — is below this threshold are excluded |
| `dates_to_exclude` | `None` (the entity's own event timestamp is always used, regardless of calendar) | Optional dates to exclude — a named (holiday) calendar or an explicit list of dates (manual or table-sourced). If the entity's event timestamp falls on an excluded date, the entity is excluded — no cutoff is generated for it. |

**How the user invokes it**: `3`, `event_relative`, or any phrase that expresses
predicting from the moment of creation — rewrite these examples using the session's
entity and event timestamp so the user recognises them.

---

## Policy 4 — rolling_fixed

**Description**: A fixed calendar of cutoff dates is generated first; every entity
that existed at each date gets a row. All entities are evaluated at the same
timestamps.

**When to recommend**: When the goal is standardised snapshots — benchmarking at
fixed calendar points or comparing cohorts at the same absolute date.

**Parameters** — confirm each with the user before generating SQL:

| Parameter | Default | Description |
|---|---|---|
| `time_unit` | Inferred from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data) | The unit used to interpret every duration-valued parameter in this policy (e.g. `activity_filter`'s lookback) |
| `frequency` | `quarterly` | `daily`, `weekly`, `monthly`, `quarterly`, `yearly` |
| `cutoff_start` | Data start date | First cutoff date |
| `cutoff_end` | `MAX_SAFE_DATE` | Last cutoff date |
| `dates_to_exclude` | `None` (every date at the chosen `frequency` is eligible) | Optional dates to exclude from the generated fixed-frequency dates — same semantics as Policy 5's `dates_to_exclude`: a named (holiday) calendar or an explicit list of dates (manual or table-sourced). |
| `min_lifespan` | 0 | Entities whose lifespan, measured in `time_unit`, is below this threshold are excluded |
| `no_eligible_window_action` | `exclude` | What happens to an entity whose own event timestamp already falls after `cutoff_end` — the eligible range `[cutoff_start, cutoff_end]` is empty, so zero cutoffs are possible. Only `exclude` is meaningful here, since there's nothing to include. |
| `activity_filter` | None | Optional: only include entities active in the N `time_unit` before cutoff |

**Rewrite note**: when displaying the `min_lifespan` and `no_eligible_window_action` rows to the user, replace the generic "entity" / "event timestamp" wording in their Description cells with the session's actual entity name and event timestamp column (e.g. "presentations" and `PRESENTATIONS.Submission_Time`) — do not show the generic placeholder wording verbatim.

**Row count warning**: Estimate rows as `n_entities × n_periods` and warn the user if
the estimate exceeds 5M rows before generating SQL.

**How the user invokes it**: `4`, `rolling_fixed`, or phrases like "quarterly cutoffs",
"fixed calendar", "same dates for all" — rewrite using the session's entity name.

---

## Policy 5 — calendar_aware

**Description**: Cutoffs are locked to recurring calendar milestones — e.g. every Monday, the 1st of every month, the last business day of the month, quarter starts, market-open days on a specific exchange, a recurring seasonal window, a floating/lunar calendar (e.g. Easter, Ramadan), or any other calendar the user defines — rather than sampled per entity or tied to an event timestamp. The user supplies the rule; every generated cutoff conforms to it.

**When to recommend**: When the prediction question is inherently tied to a recurring calendar or business rhythm (e.g. "evaluate every Monday," "evaluate at market open on trading days") rather than to entity-specific event times or arbitrary/random sampling. **Never strongly recommended** — regardless of label semantics, this policy is always offered as an explicit user choice, never tagged by Step B.

**Parameters** — confirm each with the user before generating SQL:

| Parameter | Default | Description |
|---|---|---|
| `time_unit` | Inferred from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data) | The unit used to interpret any duration-valued parameter in this policy |
| `rule` | None — required | Either a named preset (`every_monday`, `first_of_month`, `last_business_day_of_month`, `quarter_start`, `market_open_days`); a named market/trading calendar identifier (e.g. `NYSE`, `Euronext`, `LSE`) restricting cutoffs to that exchange's open days; a fixed recurring window given as `{type: "seasonal_window", start: "MM-DD", end: "MM-DD", frequency: "daily" \| "weekly" \| "monthly"}` (recurs every year between `start` and `end` — explicit `start`/`end` required, since season boundaries vary by hemisphere and convention); a floating/lunar named calendar (e.g. `EASTER`, `RAMADAN`, `CHINESE_NEW_YEAR`, `US_THANKSGIVING`) whose date shifts year to year and is resolved via a per-year lookup rather than fixed month-day arithmetic; or any other calendar the user defines, given as an explicit list of dates — provided manually or sourced from an existing database table/column, mirroring how `dates_to_exclude` can be sourced |
| `dates_to_exclude` | None (every calendar day matching `rule` is eligible) | Optional dates to exclude from the days matching `rule` — given either as a named (holiday) calendar (e.g. `US_FEDERAL_HOLIDAYS`) or an explicit list of dates, provided manually or sourced from an existing database table/column. Always a blocklist — for restricting cutoffs to a market's open days or other recurring calendar, use `rule` instead. |
| `cutoff_start` | Entity's event timestamp | Earliest possible cutoff |
| `cutoff_end` | `MAX_SAFE_DATE` (data end − prediction window) | Latest possible cutoff |

**Collect both of these before generating any SQL**:

1. **Rule** — named preset, market/trading calendar, seasonal window, floating/lunar calendar, or fully custom calendar (list or table-sourced)
2. **Dates to exclude** — none, or an explicit blocklist: a named holiday calendar, or specific dates (manually listed or sourced from a database table/column)

**How the user invokes it**: `5`, `calendar_aware`, or any description that expresses a recurring calendar rule (specific weekdays, month-start, trading days) rather than event-relative or random sampling — rewrite examples using the session's entity name.

---

## Policy 6 — custom

**Description**: The user defines their own cutoff sampling logic.

**How the user invokes it**: `6`, `custom`, or any description that does not match
policies 1–5.

**Collect all five of these before generating any SQL**:

1. **Time unit** — what unit should duration-valued parameters (offsets, filters, thresholds) be expressed in? Infer a reasonable default from the granularity of the session's event timestamps (e.g. `days` for daily-cadence data, `minutes` for intraday/minute-level data).
2. **Anchor** — what date does each cutoff derive from?
3. **Sampling method** — fixed offsets, random, or event-triggered, and however many cutoffs per entity that implies (e.g. a fixed count for fixed-offset/random sampling, or one per qualifying event for event-triggered)?
4. **Filters (optional)** — any entity-level conditions that must hold at cutoff time; defaults to `None` (no additional filter) if not specified.
5. **Dates to exclude (optional)** — any (holiday) calendar or explicit list of dates to exclude, provided manually or sourced from a database table/column?
