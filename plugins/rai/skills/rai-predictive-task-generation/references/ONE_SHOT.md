# Predictive Task Builder One-Shot

This is the low-question sub-skill of `rai-predictive-task-generation`, sibling to `guided`. It produces the same kind of output — a Snowflake SQL script that materializes a labelled task table conforming to the schema contract for one of six task types — but instead of confirming every decision along the way, it infers and decides almost everything itself from the user's description and the data, and shows its work in one consolidated summary at the end. It reuses the `guided` sub-skill's and the parent's reference files directly (the `task_*.md` and `utils_*.md` files in this same `references/` folder) for anything that's already mechanical or evergreen; it only adds new content for the parts that are genuinely about *deciding with fewer questions*.

## On bare invocation

When the skill is invoked with no context, display exactly this greeting and nothing else:

---

**Predictive Task Builder One-Shot**

This is the fast, low-question version of the Predictive Task Table Builder. It requires a live Snowflake connection (via `raiconfig.yaml`) — I'll connect automatically if one is configured in this repo, or help you set one up if not.

To get started, provide:

1. **Your data** — either the fully qualified table names (`DATABASE.SCHEMA.TABLE`) or the database and schema containing the relevant tables.
2. **The task you want to solve .** — what you want to predict, recommend, classify, or otherwise learn.

For example:

- *"My data is in `PROD_DB.SALES`, with `ORDERS` and `CUSTOMERS` tables. I want to predict which customers will churn in the next 90 days."*
- *"My data is in `REVIEWS_DB.DATA`. I have user–product review data and want to recommend products a user is likely to buy next."*

I will inspect the available data and infer the necessary configuration. I will only ask follow-up questions when something is genuinely ambiguous or unsafe to infer.

⚠️ **Note:** this mode needs to see some of your data and connects to Snowflake automatically — use `guided` mode instead if you'd rather review each step yourself.

⚠️ **Note:** letting an LLM run SQL against your database carries real risk, so please use a user/role scoped to only the database used for this task table.

---

Do not ask any follow-up questions yet. Wait for the user to describe their use case.

## What this skill does NOT do

- It does not skip the two hard invariants: a fresh, explicit per-statement confirmation before any `CREATE`/`INSERT`/write (subject to `utils_auto_execution.md`'s narrow exception), and a targeted inline question at the specific hard-stop points listed under **When to push back** below.
- It does not present configuration as a series of confirmable turns. Every decision below Step 1 is made autonomously and surfaced once, together, in the final summary — with an open invitation to change any of it.
- It does not offer or mention multi-dataset experimentation at any point — it's applied only if the user explicitly asks for it.
- It does not build features — same as the parent skill, features are constructed downstream by the framework.
- It does not offer a copy-paste fallback — a live Snowflake connection is a hard prerequisite (Step 0); without one, redirect the user to the `guided` sub-skill.

## Core workflow

### 0. Required: establish a live Snowflake connection

This skill has no copy-paste mode — a live Snowflake connection is a hard prerequisite, not an opt-in. Shuttling discovery/validation queries back and forth with the user for every step would reintroduce exactly the back-and-forth this skill exists to avoid, so low-touch, one-shot behavior is only possible with direct access. Attempt the connection immediately, without asking permission to try:

(The bare-invocation greeting above already discloses this to the user — both the data-sharing and the execution-risk points — before this step runs. Writes still always ask for a fresh, explicit confirmation before running; this step only automates reads.)

- Resolve/reuse this repo's Python venv per `utils_python_environment.md`, installing `relationalai>=1.20.1` if missing (mechanical, no confirmation needed).
- Attempt a Snowpark session per `utils_auto_execution.md`'s setup pattern (load `rai-setup` yourself to establish the connection), then validate it with one trivial query.
- **If it works**: say so in one plain sentence before continuing — e.g. "I found a Snowflake connection and pulled your schema automatically — here's what I found:" — and use it for all read-only discovery for the rest of the session, following `utils_auto_execution.md`'s read/write permission tiers exactly.
- **If it doesn't work** (package install failure, no config found, connection fails): follow `utils_auto_execution.md`'s "Environment isn't ready" playbook — install the package if needed, scaffold an empty `raiconfig.yaml` if none exists, then hand it to the user to fill in and **stop**. Tell the user plainly that this skill needs a working Snowflake connection to run, and that you'll continue as soon as it's configured. **Do not fall back to copy-paste.** If the user would rather not set up a connection right now, point them at the `guided` sub-skill instead, which supports copy-paste.

Unlike a one-off opt-in question, this is a standing prerequisite for the skill to run at all — so it's checked unconditionally at the start of every session, not something the user is asked about.

**Writes require a fresh, explicit per-statement confirmation by default.** This does not change under this skill — restated, including its narrow exception, from `utils_auto_execution.md`'s permission-tier table.

### 1. Parse the opening message

Check whether the user's opening message already gives fully-qualified `DATABASE.SCHEMA.TABLE` names for every table needed.

- **If yes**: skip straight to Step 2.
- **If no**: ask exactly one combined question — not the parent skill's two-part turn:

  > Quick thing before I dig in: what's the fully-qualified `DATABASE.SCHEMA` for these tables, and are `<table1>`, `<table2>`... the exact Snowflake names, or do they go by something else (e.g. `TRANSACTIONS`/`SALES` for "orders")?

  Wait for the reply before proceeding. This is the one follow-up question that can't be avoided when the user hasn't already supplied the location.

### 2. Discovery — one combined wave

A live session is guaranteed by this point — Step 0 either connected or the skill already stopped before reaching here. Run everything below yourself via `run_sql`, silently, and go straight to Step 3 with the results — no query block is ever shown to the user:

1. **Schema** — one `information_schema.columns` query across all confirmed tables (same shape as the parent skill's Query 1).
2. **Sample rows** — 5 rows per table via `OBJECT_CONSTRUCT(*)` (same shape as the parent skill's Query 2).
3. **Candidate-key uniqueness check** — one `COUNT(*), COUNT(DISTINCT <guessed_pk>)` per table, guessing the PK by naming convention (`<table>_id`, `id`, or the first ordinal column), so the Step 3a hard-stop check doesn't need a second round-trip.
4. **Aggregate temporal stats** (only include this block if the description plausibly implies a temporal task): date range, distinct-timestamp cardinality, and median inter-event gap, using the best-guess event table/column from the description. See `utils_one_shot_auto_inference.md` for the exact query template.

If the best-guess event table/column turns out wrong once results come back, re-derive silently from the schema result — do not re-run queries just to fix a wrong guess.

### 3. Silent inference

Do all of the following without presenting them as separate confirmable turns. Carry every decision straight into a running "Assumptions I made" list for the final summary (Step 9) — do not send any of this for confirmation first.

**3a. Candidate key (hard stop preserved)** — using the Step 2 uniqueness check:
- Single clear unique column → proceed silently, record it in Assumptions.
- **No obvious key, or only a composite key** → **stop immediately**, exactly as the parent skill does: *"I cannot generate a task table — the entity table `<TABLE>` has no single-column candidate key. The framework requires a unique identifier per entity row to join the task table to the source concept. Can you confirm which column uniquely identifies each row, or provide a table that has one?"* (or the composite-key variant, offering the same two remedies). Do not generate any SQL or continue inference until this is resolved.

**3b. Temporal vs. non-temporal** — apply the same two signals the parent skill uses:
1. Is the target column already present on the entity table itself? → suggests non-temporal.
2. Does the description reference a future time window ("in the next N days", "churn", "reorder")? → suggests temporal.

Decide silently and record the one-sentence reasoning in Assumptions — do not ask for confirmation.

**Lower the bar for "conflicting" here relative to the parent skill.** Treat it as a hard stop — not a silent guess — whenever *both* signals are present at all, even weakly: a label column already exists on the entity table **and** the description contains any future-tense or window language, even non-explicit (not just an exact "in the next N days" phrase — words like "eventually", "will", "becomes", "over time" count too). Getting this wrong changes the entire schema shape (cutoff column, split strategy, everything downstream), so the threshold for asking is deliberately lower than elsewhere in this skill. When it fires, ask the parent's exact question once:

> Is this a **temporal** or a **non-temporal** task?
> - **Temporal**: the label depends on something that happens after a cutoff time. The task table will carry a cutoff timestamp per row, and an event-timestamp column drives cutoff generation.
> - **Non-temporal**: the label is a static or hidden attribute of the entity itself, known independent of time. The task table has no cutoff column — it's a plain `(entity_id, label)` pair, split randomly rather than by date.

Then resume silently with the answer folded into the rest of inference.

**3c. Table roles, entity & key, event timestamp** — infer exactly as the parent skill's Turn 1B-ii/iii do: which subset of tables is actually needed to compute the label and the join key (not the full graph), role labels taken from the user's own wording, fully-qualified `TABLE.column` naming throughout. Carry straight into Assumptions rather than sending for confirmation.

**3d. Label definition** — state the precise event/condition that defines a positive label as a sentence, same as the parent skill's Step 3 field.

**3e. Non-blocking ambiguities** — if something is unclear but doesn't rise to a hard stop (e.g. two plausible timestamp columns), pick the more likely one using the same reasoning the parent skill would use to justify a choice, and record both the pick and the alternative in Assumptions (e.g. "used `ORDERS.order_ts` rather than `updated_at` because...").

### 4. Task type

The six supported tasks and their distinguishing questions (same as the `guided` sub-skill):

| Task type | Distinguishing question | Label shape |
|---|---|---|
| Binary classification | "Will entity X do Y by time T?" with a yes/no answer | `(entity_id, cutoff_ts, label∈{0,1})` |
| Multiclass classification | "Which one of K mutually exclusive classes does entity X belong to at time T?" | `(entity_id, cutoff_ts, label)` — `label` is the raw category value, not re-encoded |
| Multilabel classification | "Which subset of K (non-exclusive) tags applies to entity X at time T?" | `(entity_id, cutoff_ts, label_vector)` or long form `(entity_id, cutoff_ts, label_id)` with multiple rows per entity |
| Regression | "What continuous value will entity X have/produce by time T?" | `(entity_id, cutoff_ts, target_value∈ℝ)` |
| Link prediction | "What are the top-K dst entities that src is most likely to interact with (including first-time) in (T, T+Δ]?" | `(src_id, cutoff_ts, LIST[dst_id])` — one row per source entity; targets are a list of positive dst PKs; framework samples negatives internally |
| Repeated link prediction | "What are the top-K dst entities that src has already interacted with and will interact with again in (T, T+Δ]?" | `(src_id, cutoff_ts, LIST[dst_id])` — same list format; dst candidate pool restricted to pairs with prior history |

**Decide silently when the description clearly indicates one of the six.** Load only the matching reference file (`task_<type>.md`) and proceed.

**Link vs. repeated-link prediction — default silently, never ask.** Default to **plain link prediction** (discovery) whenever the description could go either way. Only pick **repeated-link prediction** when the user's own **opening** description of the task explicitly signals repeat/reorder intent — phrasing like "buy again", "reorder", "repurchase", "re-engage", "products they've already bought", "will buy again". A generic description ("recommend products", "what will they buy next", "products a user is likely to buy") defaults to plain link prediction even if the data itself shows a lot of repeat interactions — the schema signal must never flip the default, only the user's own wording in the opening message does. If the user clarifies or corrects this later in the conversation, honor that over the opening-message default. Record the pick and the one-sentence trigger (the exact phrase that triggered repeated-link, or "no repeat/reorder signal in the opening description" for plain link) in Assumptions — never as a question.

**Hard stop, one inline question, when genuinely ambiguous** — in particular:

- **Explicit negatives requested for a link task** — clarify inline that this framework samples negatives internally; if the user needs scalar pair-scoring with explicit negatives (AUC evaluation), redirect to binary classification on the source entity instead of building a link-prediction table.
- **Repeated link prediction requested but the event table only records the most recent interaction per pair, not full history** — stop and flag that the data doesn't support the task; do not silently substitute a different task type.
- **Any other case where the description doesn't map cleanly to one of the six shapes** — ask a short clarifying question rooted in the user's actual tables, same style as the parent skill's Step 2 examples, then resume.

### 5. Autonomous task configuration

Fill every field the parent skill's Step 3 requires, deciding instead of asking. Full decision-rule detail (parameter defaults, thresholds, formulas) lives in `utils_one_shot_auto_inference.md` — this section states the rules, that file has the mechanics.

- **Entity, Event timestamp, Label definition**: carried from Step 3, restated using the parent skill's phrasing conventions (e.g. conditional phrasing — "could serve as" — when the prediction window is omitted because the label is fixed at `cutoff_ts` itself).
- **Prediction window**: default **91 days** (`365 // 4`) unless the user gave an explicit duration. Never ask the 90-vs-91 question — see `utils_one_shot_auto_inference.md` for the exact day-count conversion table for "N months"-style descriptions. Omit entirely when the label is already fixed at `cutoff_ts` (intrinsic-label case).
- **Feature window**: informational only, same as the parent skill — state it, don't ask about it.
- **Activity filter** (all task types, never asked about): the default is **no activity filter**, full stop, regardless of task type or temporal mode — see `utils_one_shot_auto_inference.md` for the full rule, including the one exception (the user's own opening description explicitly scopes the population by recency/engagement, e.g. "active users"). This deliberately diverges from `task_binary.md`'s "strongly recommended" guidance, which is written for the `guided` sub-skill where the user sees and confirms the choice explicitly — a filter changes label semantics enough that this skill doesn't apply it silently. **Always state the measured activity fraction in Assumptions, whichever way the default landed** — this is the one number that lets the user catch a skewed inactive tail at a glance without an extra question being asked.
- **Filters**: only apply ones the user explicitly stated; never invent additional entity filters.
- **Temporal vs. non-temporal**: restate the Step 3b decision; never re-ask.
- **Cutoff strategy** (temporal tasks only): apply the rule in `utils_one_shot_auto_inference.md` mechanically, using `utils_cutoff_policies.md` **only for each policy's parameter defaults and definitions — never its menu-presentation instructions.** In short: non-temporal → omit entirely; intrinsic/fixed label → Policy 3 `event_relative`, no parameters; forward-looking label → Policy 2 `sample_timestamp_randomly_from_range` by default, falling back to Policy 1 `generate_timestamp_randomly_from_range` only if there aren't enough distinct real timestamps per entity to sample from; Policy 4 `rolling_fixed` only on explicit benchmark/cohort-comparison wording; Policy 5 `calendar_aware` only when the wording literally names a mappable calendar rule (a named weekday, "quarter start", a named exchange, a named holiday, ...), falling through to Policy 2/1 otherwise; Policy 6 (custom) is never reachable in one-shot mode. State the chosen policy, its parameters, and the one-sentence reason in Assumptions.
- **Split configuration**: default to **three-way train/val/test**, no scenario question. Boundaries come from the formulas in `utils_one_shot_auto_inference.md` (percentile-of-range for temporal tasks, deterministic hash-bucket for non-temporal). Report per-split row counts in the summary so a bad split is catchable at a glance.

### 6. Configuration quality check — auto-apply, don't ask

Check two threshold-triggered signals — prediction-window-vs-data-density and dataset size (see `utils_one_shot_auto_inference.md` for exact thresholds) — plus report class balance as information only, never as a threshold (no universal rate is "healthy," so it never triggers a fix or a caveat — see `utils_one_shot_auto_inference.md`'s note). **Skip the density check entirely for a tiling configuration** (e.g. `rolling_fixed` with a frequency that roughly matches the window, like weekly cutoffs with a 7-day window) — same rule as `guided`'s Step 3 check, see `utils_one_shot_auto_inference.md` for the exact condition. Dataset size is checked here too, live. This differs from `guided` only in *mechanism*, not in which signals matter: `guided` surfaces the density check as one confirm-once question before generation and defers dataset size into an annotated SQL comment after; one-shot checks both live, before generating any SQL, using the connection Step 0 already guarantees, and silently auto-fixes rather than asking — since one-shot's whole premise is deciding without a back-and-forth. Fix-and-state, not flag-and-ask:

- **Hard boundary — never auto-fix a value the user stated themselves.** Every fix in this step (widening a window, loosening a filter, extending a date range, ...) may only touch parameters this skill inferred silently (Step 3/5's defaults). If the parameter under adjustment was explicitly given by the user in their own words — most commonly an explicit prediction window duration ("in the next 1 month", "45 days") — do not adjust it, and do not even test-and-revert it to see whether it would help. Skip straight to reporting the signal as an unresolved caveat instead, exactly as if the one adjustment attempt had already failed. The reasoning holds regardless of outcome: a user who skims the summary after being told "fixed" would believe they got the task they asked for even if the value they stated was silently changed underneath them.
- If there's a clear automatic fix among the parameters this skill *did* infer (e.g. widen a window that was defaulted rather than stated, loosen an over-strict activity filter), apply it **once** and state what changed and why in the summary.
- If the signal is still out of range after one adjustment attempt — or immediately, when the hard boundary above applies — stop adjusting and note it as an unresolved caveat in the summary instead of blocking.
- Word every pre-generation estimate as "estimated," never "confirmed" — these are proxies computed before the label query exists. The real check is the post-generation class-balance step reused unchanged from `utils_output_format.md`.
- **Never** ask "would you like to adjust?" here. Either fix it and say what changed, or note it as a caveat — both go in the final summary, not as a mid-flow question.

### 7. Generate code

Follow `utils_conventions.md` and the matching task-type reference file (`task_<type>.md`) exactly as the `guided` sub-skill does — these are schema-contract/worked-example references with no dependency on how many interview turns happened. Same four-section SQL artifact (Schema → STAGING → Validation queries → Split tables), same `EXCLUDE`-based split-table generation (drop `cutoff_<table>_<source_time_col>` and `split` for temporal tasks, `split` only for non-temporal), same downstream column-naming contract (`label`/`value`/`cutoff_<table>_<source_time_col>`/`<table>_<source_time_col>`/etc.) — see the parent skill's [Downstream column naming contract](../SKILL.md#downstream-column-naming-contract).

**Writes get a fresh, explicit confirmation by default.** Section 3 (validation queries) is read-only and runs automatically — a live session is guaranteed by Step 0. Sections 1, 2, and 4 (schema creation, STAGING, split tables) get a fresh, explicit "should I run this against `<DB>.<SCHEMA>` now?" confirmation before executing — ask separately for STAGING and for the split tables, in that order — unless `utils_auto_execution.md`'s narrow exception applies, in which case state what you're about to run and proceed.

There is no "user declined validation" branch in this skill — validation always runs (Step 8), since Step 0 never asks the opt-out question the parent skill does.

### 8. Validate

Reuse `utils_validation.md` as-is — it's already fully mechanical given a settled config: resolve `sqlglot` via `utils_python_environment.md`, then use the EXPLAIN road (a live session is guaranteed by Step 0, so the local-tool road never applies here), fix and re-run until clean. No changes needed for this skill.

### 9. Output: consolidated summary

Reuse `utils_output_format.md`'s 3-section summary format (Configuration / Query logic / How to run) exactly as written, but **prepend an "Assumptions I made" section** carrying everything Steps 3, 4, 5, and 6 above decided without asking:

> **Assumptions I made** — each with one line of reasoning:
> - Temporal vs. non-temporal: ...
> - Table roles: ...
> - Entity & key: ...
> - Event timestamp: ...
> - Task type: ...
> - Prediction window: ...
> - Activity filter (+ measured activity fraction, whichever way the default landed): ...
> - Cutoff strategy + parameters: ...
> - Split boundaries + per-split row counts: ...
> - Any quality-check auto-adjustments applied, and any unresolved caveats.
>
> Let me know if you'd like to change any of these — I can regenerate the SQL with the correction.

Note: `utils_output_format.md`'s "user opted out of validation in Step 0" branch and its "EXPLAIN road didn't run" caveat are both unreachable here — a live session is guaranteed by Step 0, so the EXPLAIN road always runs and there's never anything to caveat. The post-generation class-balance follow-up (asking the user to paste back the real computed positive rate for binary/multilabel tasks) still applies unchanged — run that query yourself and report the result directly instead of asking, same pattern as the rest of this skill.

Never mention or offer multi-dataset experimentation, in the summary or anywhere else — not even as a closing "just ask" line. If the user brings it up unprompted, see the parent skill's [Multi-dataset experimentation](../SKILL.md#multi-dataset-experimentation) section for the pattern to follow.

## When to push back

- **No single-column candidate key on the entity table (hard stop)**: do not generate any SQL. Tell the user immediately and offer two remedies: identify a surrogate column that is actually unique, or create a deduplicated entity view with a single PK.
- **Genuinely ambiguous temporal vs. non-temporal** (per the lowered bar in Step 3b): ask the one targeted question, then resume.
- **Genuinely ambiguous task type** (outside of link vs. repeated-link, which is never asked — see Step 4's default rule): ask a short clarifying question, then resume.
- If the user requests link prediction and proposes adding explicit negatives, clarify that this framework samples negatives internally; redirect to binary classification if they need scalar pair-scoring with AUC evaluation.
- If the user asks for repeated link prediction but the event table only records the most recent interaction, flag that the data doesn't support the task.
- If the user asks for "a task table" without naming a prediction problem, do not invent one — ask.
- **Writes require confirmation by default, with one narrow exception** (see `utils_auto_execution.md`): never run a `CREATE`/`INSERT`/write statement without a fresh, explicit confirmation for that exact statement, regardless of how much of the rest of the flow ran autonomously.

## What comes next: predictive modeling and training

Same two-step downstream pipeline regardless of which sub-skill built the task table — see the parent skill's [What comes next](../SKILL.md#what-comes-next-predictive-modeling-and-training) section for the full `rai-predictive-modeling` / `rai-predictive-training` walkthrough and the task-type → downstream configuration table.

## Quick reference: the six task types at a glance

See the parent skill's [Quick reference](../SKILL.md#quick-reference-the-six-task-types-at-a-glance).
