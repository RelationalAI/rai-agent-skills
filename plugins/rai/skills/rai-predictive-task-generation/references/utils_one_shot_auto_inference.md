# Auto-inference rules

**This file is new content owned by the `one-shot` sub-skill — unlike the other reference files this skill points to (the `utils_*.md` and `task_*.md` files in this same `references/` folder), it is not a reuse of anything from the parent skill or the `guided` sub-skill.** Everything here exists specifically to replace a question the parent skill would ask with a deterministic default.

## Discovery query templates (Step 2)

### Candidate-key uniqueness check

For each confirmed table, guess the primary-key column by naming convention (`<table>_id`, `id`, or the first ordinal column from the schema query), then run:

```sql
SELECT
    COUNT(*)                      AS total_rows,
    COUNT(DISTINCT <guessed_pk>)  AS distinct_pk_values
FROM <DB>.<SCHEMA>.<TABLE>;
```

`total_rows == distinct_pk_values` confirms the guessed column is a valid single-column candidate key. If they differ, or the guessed column doesn't exist, treat this table as having **no obvious key** per ONE_SHOT.md Step 3a until the schema is inspected further — do not guess a second time before falling back to the hard-stop question.

### Aggregate temporal stats

Only needed if the description plausibly implies a temporal task. Use the best-guess event table/column from the description; re-derive silently from the schema result if the guess turns out wrong — never send a second query round just to fix a wrong guess.

```sql
WITH ts_stats AS (
    SELECT
        MIN(<ts_col>)                    AS first_event,
        MAX(<ts_col>)                    AS last_event,
        COUNT(DISTINCT <ts_col>)         AS distinct_ts_values,
        COUNT(DISTINCT <entity_id_col>)  AS distinct_entities,
        COUNT(*)                         AS total_rows
    FROM <DB>.<SCHEMA>.<EVENT_TABLE>
),
per_entity_ts AS (
    SELECT <entity_id_col> AS eid, COUNT(DISTINCT <ts_col>) AS distinct_ts_per_entity
    FROM <DB>.<SCHEMA>.<EVENT_TABLE>
    GROUP BY 1
),
gap_stats AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_days) AS median_gap_days
    FROM (
        SELECT DATEDIFF('day', LAG(<ts_col>) OVER (PARTITION BY <entity_id_col> ORDER BY <ts_col>), <ts_col>) AS gap_days
        FROM <DB>.<SCHEMA>.<EVENT_TABLE>
    )
),
activity_stats AS (
    SELECT
        COUNT(DISTINCT CASE WHEN <ts_col> >= DATEADD('day', -<lookback_days>, (SELECT last_event FROM ts_stats)) THEN <entity_id_col> END) AS active_entities,
        (SELECT distinct_entities FROM ts_stats) AS total_entities
    FROM <DB>.<SCHEMA>.<EVENT_TABLE>
)
SELECT
    (SELECT * FROM ts_stats)                                 AS ts_stats,
    (SELECT AVG(distinct_ts_per_entity) FROM per_entity_ts)  AS avg_distinct_ts_per_entity,
    (SELECT median_gap_days FROM gap_stats)                  AS median_gap_days,
    (SELECT active_entities FROM activity_stats)             AS active_entities_in_lookback,
    (SELECT total_entities FROM activity_stats)              AS total_entities;
```

`<lookback_days>` = the candidate prediction window (91 unless the user gave a different duration — see below).

## Prediction window default (Step 5)

Default to **91 days** (`365 // 4`), matching the `guided` sub-skill's own stated convention. Convert an explicit user-given duration using this table — never ask the parent skill's 90-vs-91 clarifying question:

| User said | Use |
|---|---|
| An explicit day count (e.g. "45 days") | Exactly that number |
| "N months" where N is divisible by 3 (e.g. "3 months", "6 months", "a year") | `(N / 3) × 91` days |
| "N months" otherwise (e.g. "2 months", "5 months") | `N × 30` days |
| No duration given, forward-looking label | 91 days |
| Label fixed at `cutoff_ts` itself (intrinsic-label case) | Omit the field entirely — see ONE_SHOT.md Step 5 |

## Cutoff strategy selection (Step 5)

Apply mechanically; never present a menu, and never ask a question to choose between policies — every branch below resolves silently, including the two policies without generic silent defaults (5 and 6; see rules 5–6). Pull each policy's parameter definitions and defaults from `utils_cutoff_policies.md` (its Policies 1–5 sections) — never its "How to present to the user" menu instructions, which don't apply here.

1. **Non-temporal task** → omit the cutoff strategy field entirely.
2. **Intrinsic/fixed label** (the label is already determined at/before the entity's own event timestamp — same test as `utils_cutoff_policies.md`'s Step B rule 1, e.g. a badge's `CLASS` fixed the moment it's awarded) → **Policy 3, `event_relative`**. No parameters.
3. **Forward-looking label** (the common case — a label evaluated over a window after cutoff) → default **Policy 2, `sample_timestamp_randomly_from_range`**:
   - `min_cutoffs_per_entity` = 3, `max_cutoffs_per_entity` = 5 (per `utils_cutoff_policies.md`'s documented defaults)
   - `cutoff_start` = the entity's own event timestamp (or discovered data-start if no per-entity lifetime applies)
   - `cutoff_end` = `MAX_SAFE_DATE` = discovered data-end minus the prediction window
   - `min_lifespan_days` = 0
   - **Feasibility check**: if `avg_distinct_ts_per_entity` (from the Step 2 aggregate query) is below `min_cutoffs_per_entity` (3), there isn't enough real-date variety to sample from — fall back to **Policy 1, `generate_timestamp_randomly_from_range`** instead, with `min/max_cutoffs_per_year` = 3/5 and the same date-range defaults.
4. **Policy 4, `rolling_fixed`** — only if the user's own wording contains explicit standardized-snapshot or cohort-comparison language: "quarterly", "monthly cohort", "same date for everyone", "compare cohorts", "benchmark". Infer `frequency` from the wording if a cadence is named, default to `quarterly` otherwise. `cutoff_start` = data start, `cutoff_end` = `MAX_SAFE_DATE`.
5. **Policy 5, `calendar_aware`** — silently auto-picked, never asked about, but *only* when the user's own wording names a rule concrete enough to map mechanically. A vague sense that "this sounds calendar-ish" is not enough — require a literal match to one of:
   - A named weekday/month-boundary preset: "every Monday" → `every_monday`; "first of the month" → `first_of_month`; "last business day of the month" → `last_business_day_of_month`; "quarter start" / "start of each quarter" → `quarter_start`.
   - A named trading calendar: "market open days" / "trading days" paired with a named exchange (e.g. "NYSE", "Euronext", "LSE") → `market_open_days` restricted to that exchange.
   - A named floating/lunar calendar stated explicitly: `EASTER`, `RAMADAN`, `CHINESE_NEW_YEAR`, `US_THANKSGIVING`, or an equivalent the user names outright.
   - An explicit seasonal window: the user states *both* a start and end `MM-DD` (or an unambiguous equivalent, e.g. "June through August") *and* a frequency → `{type: seasonal_window, start, end, frequency}`, using the user's own dates/frequency verbatim, never invented ones.

   `dates_to_exclude` defaults to `None`; only set it when the user's own wording separately names a holiday calendar or explicit exclusion list to subtract. `cutoff_start`/`cutoff_end` take the same defaults as the other policies (entity's own event timestamp / `MAX_SAFE_DATE`).

   **If the description doesn't literally match one of the above, do not pick Policy 5** — silently fall through to rule 3 (or rule 4, if its cohort trigger already fired) instead of guessing a calendar rule from weaker signal.
6. **Policy 6 (custom) is never reachable from this skill, in any form — not even as a question.** It requires five open-ended parameters (anchor, sampling method, filters, ...) that have no safe default and can't be mapped from wording alone the way Policy 5's presets can. Anything that doesn't match rules 2–5 above falls through to rule 3's forward-looking default; there is no case in one-shot mode where Policy 6 is chosen or asked about.

State the chosen policy, its parameters, and a one-sentence reason (grounded in the session's actual label/entity semantics, mirroring `utils_cutoff_policies.md`'s own reasoning style) in the Assumptions list — never as a menu, never as a question.

## Activity filter default (Step 5, all task types)

Never ask about this — every task type gets a mechanical default, and that default is **no activity filter**, full stop, regardless of task type or temporal mode.

- **Non-temporal tasks (any type)**: omit the activity filter entirely. There is no `cutoff_ts` to measure a lookback against — time isn't part of the schema at all for non-temporal tasks, so "active before cutoff" isn't a meaningful concept here.
- **Temporal tasks (any type — binary, multiclass, multilabel, regression, link, repeated link)**: default to **no filter**. Do not apply one on the theory that the task family would generically benefit from tighter class balance or denser signal — that's a real tradeoff (it changes which entities the label is even evaluated on) and it is not this skill's call to make silently.
- **Exception — only when the user's own opening description explicitly scopes the population this way**: if the description itself qualifies the entities by recency/engagement — e.g. "predict which **active** users will churn," "recommend products to **engaged** customers," "users who have been active in the last 30 days" — apply a lookback activity filter (require at least one event in `(cutoff_ts - lookback, cutoff_ts]`, using the same lookback length as the prediction window). This fires only because the user already told you the population is scoped this way in their own words; it is never inferred from the task type or from the data's activity distribution alone.
- **Regardless of which default applies for any task type**, always state the measured activity fraction in the Assumptions list (from the Step 2 `activity_stats` block) — even when no filter was applied — so a skewed inactive tail is still catchable at a glance even without a filter to hide it.

Note: this deliberately diverges from `task_binary.md`'s "strongly recommended" framing for an activity filter. That guidance is written for the guided skill, where the user sees and confirms the choice explicitly; this skill's whole premise is inferring silently, and a filter changes label semantics (which entities the model is even evaluated on) enough that it shouldn't be applied without the user having said so themselves.

## Split configuration defaults (Step 5)

Default to **three-way train/val/test**, no scenario question.

- **Temporal tasks**: boundaries at the 70th/85th percentile of the eligible `[cutoff_start, cutoff_end]` range — train ≤ 70th percentile, val 70th–85th, test 85th–100th.
- **Non-temporal tasks**: 70/15/15 proportions via a deterministic hash-bucket assignment on `entity_id`, e.g. `MOD(ABS(HASH(entity_id)), 100)` bucketed at 70/85 — reproducible without a random-seed discussion.

Report per-split row counts (and class balance where cheap to compute) in the final summary so a systematically skewed split — e.g. across a seasonality shift or a growing entity base — is catchable at a glance even though the boundaries were picked without asking.

## Configuration quality check thresholds (Step 6)

Two threshold-triggered signals, applied as fix-and-state rather than flag-and-ask — same as the `guided` sub-skill's non-blocking checks.

**Before applying any fix below, check whether the parameter it would touch was stated explicitly by the user or picked by this skill as a default.** The prediction window is the one both fixes below can touch, and it is very often user-stated (e.g. "in the next 1 month", "within 45 days") rather than defaulted. If the fix would change a user-stated value, do not apply it — not even as a test-and-revert experiment to check whether it would have helped — skip straight to reporting the signal as an unresolved caveat, same as if the one allowed adjustment attempt had already failed. This restriction applies only to the specific value the user stated; e.g. if the user gave a window but said nothing about the activity filter, the filter is still eligible for auto-fix.

**Prediction window vs. data density is skipped entirely for a tiling configuration** — same rule as the `guided` sub-skill's Step 3 check. If Policy 4 (`rolling_fixed`) was chosen and its `frequency` roughly matches the prediction window (e.g. quarterly cutoffs with a ~91-day window, or a weekly cadence with a 7-day window — the "predict sales every week" shape), a zero/empty result for a given window is a real, valid measurement of that period, not evidence the window is too short. Skip the check and don't estimate `median_gap_days` against the window at all in this case. Policies 1–2 (`generate_timestamp_randomly_from_range` / `sample_timestamp_randomly_from_range`) are always eligible for this check — cutoffs are sampled per-entity independent of the window, so nothing tiles by construction. Policy 3 (`event_relative`) never reaches this check, since the intrinsic-label case has no prediction window to begin with.

| Signal | Threshold | Auto-fix (one attempt only, and only on skill-inferred parameters — see above) |
|---|---|---|
| Prediction window vs. data density (skip if tiling — see above) | Window < `median_gap_days` (from Step 2) | Widen the window to roughly `2 × median_gap_days`, rounded to a sensible day count — only if the window was defaulted, not user-stated. |
| Dataset size | Estimated rows (`distinct_entities × expected_cutoffs_per_entity`) < ~5,000 | Loosen the activity filter if one was applied, or extend the cutoff date range. |

If a signal is still out of range after the one adjustment attempt — or immediately, because the only applicable fix would touch a user-stated parameter — stop adjusting and report it as an unresolved caveat in the summary rather than looping or blocking. Word every pre-generation estimate as "estimated" — these are proxies computed before the label query exists.

**Class balance is not a threshold-triggered signal here.** Report the estimated positive rate in Assumptions as information (per the Split-configuration note above), but never auto-fix the window or activity filter because of it, and never surface it as an unresolved caveat either. There is no universal healthy range for a positive rate — a heavily imbalanced task (e.g. 1% positive) can carry strong signal and produce a good model — so a value outside any particular band isn't itself evidence of a problem to correct. The post-generation class-balance step in `utils_output_format.md` (reused unchanged) states the real computed rate the same way: plainly, without a verdict.
