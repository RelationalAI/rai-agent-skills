# Predictive Task Table Builder — Guided

This is the guided (interview-style) sub-skill of `rai-predictive-task-generation`. It produces a prediction task table that can be consumed by a predictive-modeling framework (e.g. GNN): a Snowflake SQL script that materializes a single table conforming to the schema contract for the chosen task type. It's reached after the parent skill's mode routing has already selected "guided" — see [../SKILL.md](../SKILL.md) for that routing, the six-task-type quick reference, the downstream column-naming contract, and what comes next after the task table exists.

## On bare invocation

When the skill is invoked with no context (e.g. the user asks to build a task table with no further detail), display exactly this greeting and nothing else:

---

**Predictive Task Table Builder**

This skill helps you create a prediction task table for a predictive-modeling framework (e.g. GNN): a Snowflake SQL script that materialises a labelled table consumable by `rai-predictive-modeling`.

It supports six task types: binary classification, multiclass classification, multilabel classification, regression, link prediction, and repeated link prediction.

To get started, provide:

1. **Your data** — the relevant Snowflake table names, ideally as fully qualified names in the format `DATABASE.SCHEMA.TABLE`. You can provide individual tables and the database/schema containing these tables.
2. **Your task** — what you want the model to predict, recommend, classify, or otherwise learn.

You may also briefly explain what each relevant table represents, if that context is not obvious from the table names.

For example:

- *"My data is in `PROD_DB.SALES`. `ORDERS` table contains purchase events and `CUSTOMERS` table contains customer information. I want to predict which customers will churn in the next 90 days."*
- *"My data is in `REVIEWS_DB.DATA`, with `REVIEWS` and `PRODUCTS` tables. I have user–product review data and want to recommend products a user is likely to buy next."*
- *"I have two tables `SALES_DB.DATA.TRANSACTIONS` and `SALES_DB.DATA.CUSTOMERS`. I want to predict revenue per customer over the next quarter."*

⚠️ **Note:** I'll need to see some of your data (column schemas and sample rows) to build this — only share what you're comfortable including here.

---

Do not ask any follow-up questions yet. Wait for the user to describe their use case.

## What this skill does NOT do

- By default it does not run queries against Snowflake or RAI — it produces the code and the user runs it. The one exception is the opt-in automatic execution path (Step 0) — even then, only read-only discovery/validation queries run without a fresh confirmation; anything that creates or overwrites a table always requires an explicit per-query confirmation.
- It does not build features. Features are constructed by the framework downstream from the task table.
- It does not pick a task type for the user without confirmation. The task type determines the schema, so it must be settled before generating code.

## Core workflow

Follow these steps in order. Do not skip the configuration-confirmation step — it is the single most important step and the one where users most often catch problems.

### 0. Offer automatic execution (optional)

Ask both questions in this step as an ordinary chat message, never via an interactive question/picker tool (e.g. AskUserQuestion). Send the blockquote wording given below verbatim, as the entire message — do not prepend a framing lead-in sentence of your own (e.g. "Before diving in, one question about how we work through this:") and do not paraphrase it. These two questions gate whether Snowflake access is automated for the rest of the session, so they need to look and feel byte-for-byte identical across runs; varying the wording, adding a preamble, or swapping in a picker-widget all read as inconsistent.

Immediately after the user describes their use case (and before Turn 1A-i), ask exactly one yes/no question:

> Would you like me to run the read-only discovery queries directly against Snowflake instead of having you copy and paste them?

⚠️ If you say yes: letting an LLM run SQL against your database carries real risk, so please use a user/role scoped to only the database used for this task table.

Do not mention `rai-setup`, `utils_auto_execution.md`, Snowpark, or any other internal skill/reference names in this question or in any user-facing message — those are implementation details for you, not the user. If the user agrees but no connection is actually configured yet, discover that only when you try to establish the session (see below), then explain what's missing in plain terms (e.g. "I don't see a Snowflake connection configured — do you have credentials I can use, or would you rather stick with copy-paste?").

- **If the user declines (or doesn't respond to this question)**: ask one follow-up yes/no question before proceeding:

  > To validate the generated SQL, I'll need to set up a small local Python environment with `sqlglot` and `sqlfluff`. Let me know if you'd rather I skip that validation.

  - **If they agree**: proceed with the copy-paste workflow exactly as written below; validation runs normally per `utils_validation.md` (local-tool road).
  - **If they decline**: proceed with the copy-paste workflow, but skip SQL validation entirely for the rest of the session — don't create the Python environment, don't run `sqlglot`, `sqlfluff`, or `../scripts/validate_schema.py`. See the note in "Validate the SQL before returning it" below.

  Don't ask either question again this session.
- **If the user agrees** [to the automatic-execution question above]: read `utils_auto_execution.md` now and follow it for the rest of the session. It defines the read-only vs. write permission tiers and the Snowpark session pattern (set up per `rai-setup` — load that skill yourself to establish the connection; don't ask the user to go read it). Every step below that sends the user a query has a note on how it changes under auto-execution. No need to ask the validation-environment question separately in this case — `sqlglot` is always needed regardless of which validation road ends up running, so the environment gets created anyway.
- **If the environment isn't ready yet** (package not installed, no usable connection configured): don't just give up and drop to copy-paste, but also don't take over the connection setup — install the package if needed, scaffold an empty `raiconfig.yaml`, then hand it to the user to fill in with however they normally connect and stop there. Per the "Environment isn't ready" section of `utils_auto_execution.md`. Only fall back to copy-paste if the user prefers not to set it up right now, or the connection still fails after they've filled it in.

### 1. Establish source tables and grain

**This step runs in two turns. Do not collapse them into one.**

#### Turn 1A — Two messages, not one

This turn normally has two messages, sent separately and never combined — **unless the opening message already makes Message 1A-i unnecessary.**

**Skip check**: before sending anything, check whether the user's opening message already gives fully-qualified `DATABASE.SCHEMA.TABLE` names for every table needed (this is now the primary path the bare-invocation greeting asks for). If it does, skip Message 1A-i entirely and go straight to Message 1A-ii with those names. If the user only gave a `DATABASE.SCHEMA` (no specific table names) or described tables informally without confirming they're the real Snowflake names, send Message 1A-i as below — do not guess table names on their behalf.

---

**Message 1A-i — ask only the two questions. No SQL. No queries. Nothing else.**

Ask:
1. **Exact table names** — The user may have described their tables informally. Name every table they mentioned and ask whether those are the real Snowflake names. Give common alternatives as examples so the user knows what you mean.
2. **Database and schema** — Ask for the fully-qualified `DATABASE.SCHEMA` path.

That is the entire message. Stop there. Do not include SQL, queries, or anything about what comes next.

Example (adapt to the tables mentioned):

> Please confirm and provide the requested information:
>
> 1. **Table names** — you mentioned "orders" and "customers". Are those the exact names in Snowflake, or do they go by something different? For example, `orders` is sometimes called `TRANSACTIONS` or `SALES`, and `customers` might be `ACCOUNTS` or `CLIENTS`.
> 2. **Database and schema** — what's the fully-qualified location? e.g. `PROD_DB.SALES_SCHEMA`

---

**Message 1A-ii — sent only after the user replies to 1A-i, or immediately if the skip check above bypassed 1A-i.**

**If automatic execution is enabled** (Step 0), skip the copy-paste framing below: run Query 1 and Query 2 yourself via `run_sql` (per `utils_auto_execution.md`) and go straight into Turn 1B-i with the results. Still construct the same two queries — just execute them instead of printing them for the user.

Once the table names and db/schema are settled (whether confirmed via 1A-i or already given up front), send exactly **two queries** with the real names already filled in. No placeholders. The user should be able to copy-paste both directly without editing anything.

Open the message with a short (1-2 sentence) explanation of what the two queries are for before showing them — e.g. "Run these two queries and paste the results back: the first gives me the column schemas and types (to spot candidate keys and timestamp columns), and the second pulls sample rows so I can see actual values. I'll take it from there." Keep it brief; save the fuller rationale for if the user asks.

**Query 1** — all column schemas in one result, using `information_schema.columns`:

```sql
SELECT table_name, column_name, data_type, ordinal_position
FROM <DATABASE>.information_schema.columns
WHERE table_schema = '<SCHEMA>'
  AND table_name IN (<comma-quoted list of confirmed table names>)
ORDER BY table_name, ordinal_position;
```

**Query 2** — 5 sample rows from every table in one result, using `OBJECT_CONSTRUCT(*)` to handle different column shapes:

```sql
SELECT '<TABLE1>' AS tbl, OBJECT_CONSTRUCT(*) AS row_data FROM (SELECT * FROM <DB>.<SCHEMA>.<TABLE1> LIMIT 5)
UNION ALL
SELECT '<TABLE2>' AS tbl, OBJECT_CONSTRUCT(*) AS row_data FROM (SELECT * FROM <DB>.<SCHEMA>.<TABLE2> LIMIT 5)
-- one UNION ALL block per table
```

Example with confirmed names `F1_PREDICTIVE.DB_TABLES`, tables `RESULTS`, `DRIVERS`, `RACES`:

> Run these two queries and paste the results back: the first gives me the column schemas and types (to spot the candidate key and any timestamp columns), and the second pulls sample rows so I can see the actual values. I'll take it from there:
>
> ```sql
> -- Query 1: column schemas for all tables
> SELECT table_name, column_name, data_type, ordinal_position
> FROM F1_PREDICTIVE.information_schema.columns
> WHERE table_schema = 'DB_TABLES'
>   AND table_name IN ('RESULTS','DRIVERS','RACES')
> ORDER BY table_name, ordinal_position;
> ```
>
> ```sql
> -- Query 2: 5 sample rows from each table
> SELECT 'RESULTS' AS tbl, OBJECT_CONSTRUCT(*) AS row_data FROM (SELECT * FROM F1_PREDICTIVE.DB_TABLES.RESULTS LIMIT 5)
> UNION ALL
> SELECT 'DRIVERS' AS tbl, OBJECT_CONSTRUCT(*) AS row_data FROM (SELECT * FROM F1_PREDICTIVE.DB_TABLES.DRIVERS LIMIT 5)
> UNION ALL
> SELECT 'RACES'   AS tbl, OBJECT_CONSTRUCT(*) AS row_data FROM (SELECT * FROM F1_PREDICTIVE.DB_TABLES.RACES   LIMIT 5);
> ```

Do not proceed to Turn 1B until you have the results of both queries back from the user.

#### Turn 1B — Determine temporal/non-temporal mode + present inferences

This turn has three messages. **Send them separately.** Never combine them.

**Turn 1B-i — determine temporal vs. non-temporal, before table roles**

Before inferring table roles, decide whether this is a **temporal** task (the label depends on something that happens after a cutoff time) or a **non-temporal** task (the label is a static or currently-hidden attribute of the entity itself, independent of time).

Two signals to check, in order:
1. **Is the target column already present on the entity table itself?** (e.g. `BADGES.Class`, `PAPERS.field_of_study`) — this strongly suggests a non-temporal task: the label already exists in the data, and the goal is to predict/impute it using graph structure, not to forecast a future event.
2. **Does the problem statement reference a future time window** ("in the next N days", "will do X by time T", "churn", "reorder", "next purchase")? — this strongly suggests a temporal task.

Two paths:
- **Inferable**: if the description and schema together make the mode reasonably clear, state the inferred mode with one sentence of reasoning and ask the user to confirm — do not just assert it silently. Name the specific entity (e.g. "badges", "papers") when describing what attribute is being filled in — do not say the generic word "entities" there; the user already told you what the entity is, so say it back specifically. Keep to the reasoning itself; do not tack on extra qualifying clauses beyond it (e.g. do not add phrasing like "with no future event to wait for" — the "treating all dataset entities and values as valid at all times" clause already covers this). Keep the literal word "entities" in that later clause only — do not substitute the domain-specific noun there (e.g. keep "treating all dataset entities and values as valid at all times" even when the entity is "badges" or "papers").
- **Not inferable**: if the description is genuinely ambiguous, ask directly:
  > Is this a **temporal** or a **non-temporal** task?
  > - **Temporal**: the label depends on something that happens after a cutoff time. The task table will carry a cutoff timestamp per row, and an event-timestamp column drives cutoff generation.
  > - **Non-temporal**: the label is a static or hidden attribute of the entity itself, known independent of time. The task table has no cutoff column — it's a plain `(entity_id, label)` pair, split randomly rather than by date.

**Do not proceed to table roles until the user confirms (or corrects) the temporal/non-temporal mode.** This decision determines whether Turn 1B-iii includes an Event timestamp bullet, and whether the date range query (sent later, in Step 3) is needed at all.

**Turn 1B-ii — show Table roles only, wait for confirmation**

Before the table-roles list, open with a short lead-in naming which of the tables the user originally described are actually needed to build **this task table**, and why. The task table only needs the tables required to compute the label and the join key to the source concept — not the full graph, which is scoped later in `rai-predictive-modeling`. Say this explicitly so the user isn't left wondering why some of their tables don't appear below.

- If the relevant subset is smaller than everything the user mentioned, name the subset and give the one-sentence reason (e.g. "Only `BADGES` is needed for this task table — `CLASS` already lives on the entity table, so no other table is required to compute the label. Your other tables come into play later, when `rai-predictive-modeling` builds the graph."). Do this even if you already narrowed the scope earlier in Turn 1A — don't assume the reasoning carried over silently.
- If every table the user mentioned is needed to compute the label, say so briefly instead of omitting the explanation (e.g. "All three tables you mentioned are needed here: `CUSTOMERS` for the entity, `ORDERS` for the label, and `PRODUCTS` to resolve the category.").

Then read the schema and sample rows carefully and list only the **Table roles** — one line per table stating its inferred role, covering just the subset named above. Do **not** include candidate key, prediction entity, event timestamp, task type, or ambiguities yet.

For each table, the label in parentheses must use the name as it appeared in the user's description of the prediction problem (e.g. if the user said "research work", write `(Research Works)` not `(Entities)`). If a table has no direct match in the user's description, infer a short descriptive name from its content (e.g. `(Author–Paper Links)` for a join table).

End with an explicit confirmation ask: "Do these table roles look correct? Let me know if anything needs changing, and I'll continue once you confirm."

**Do not proceed to Turn 1B-iii until the user confirms (or corrects) the table roles.**

**Turn 1B-iii — show the rest of the inferences, wait for confirmation**

Once the user confirms the table roles (or you've updated them based on corrections), send the remaining inferences as a separate message. Do **not** re-list the table roles.

**Column naming rule**: whenever you reference a column in the inference summary, always use the fully-qualified form `TABLE_NAME.column_name` (e.g., `CUSTOMERS.customer_id`, not just `customer_id`). This applies to every bullet — prediction entity & key, event timestamp, and ambiguities.

Infer and state all of the following, **in this order**. If Turn 1B-i determined this is a **non-temporal** task, omit the Event timestamp bullet entirely — the remaining bullets are unaffected.

- **Prediction Entity & Key** *(verify the key before reporting — it is a hard blocker)*: state the entity table, the single column that uniquely identifies it, and the join path to the event table. The candidate key becomes the join key between the task table and the downstream source concept — the framework cannot handle composite keys. Look at the entity table's schema and identify the candidate key. Some source schemas allow a table to have more than one candidate key, and allow two tables to be related through more than one parallel FK relationship at once (e.g. table `A` has candidate keys `k1` and `k2`; table `B` references `A` via both `fk1 → k1` and `fk2 → k2`). Before reporting the key, check the entity table for additional unique-looking columns beyond the first one found, and check whether the related table has more than one FK-shaped column that could point back at the entity table. Four possible outcomes:
  - **Single clear key found**: state it and proceed. e.g., "`PAPERS.Paper_ID` (TEXT, ✓) — the prediction entity is a paper, joined to `CITATIONS` via `CITATIONS.References_Paper_ID`."
  - **Multiple valid candidate keys / multiple parallel FK relationships found**: do not silently pick one — even if one looks like the conventional surrogate key. This is two independent decisions, not one. Before asking, open with a short explanation (2-3 sentences) of *why* they're independent — don't jump straight to the numbered options with no framing:
    1. **Join path** — which FK relationship(s) correctly match rows between the two tables. Offer each individual path as its own numbered option, plus a final "any combination of the above — please specify which" option that spells out the actual combined join condition (e.g. `fk1 = k1 AND fk2 = k2`), not just the word "cross-checked" — the user should see the literal condition being proposed. Explain that this choice can affect the correctness of the computed label itself (not just which column ends up in the output): if the parallel FK columns could ever disagree for the same row, the join path picked determines which row actually gets matched.
    2. **`<entity>` identifier to expose** — which single candidate key column becomes the task table's `<entity> identifier` column, exposed downstream (e.g. "user identifier", never "exposed key" or generic "entity identifier" — see the column-naming rule above). Explain that this is independent of the join path: once rows are correctly matched, any candidate key column on the entity table is available to expose, regardless of which FK path was used to find the match — but it must ultimately match whichever column the downstream `rai-predictive-modeling` step treats as the source concept's primary key.

    Then ask both, numbered, in one message, and proceed only once the user has answered both parts. e.g.:

    > `USERS` has two candidate keys, `ID` and `SSN`, and `BADGES` references it two ways — `BADGES.USERID → USERS.ID` and `BADGES.USER_SSN → USERS.SSN`. These lead to two separate decisions: which relationship correctly matches a badge to its user (this matters if `USERID` and `USER_SSN` could ever disagree for the same row, since that changes which user gets credited), and separately, which column — `ID` or `SSN` — is exposed as the user identifier in the final task table, which only needs to match whatever column `rai-predictive-modeling` treats as `USERS`'s primary key.
    >
    > 1. **Join path** — (1) `USERID = ID`, (2) `USER_SSN = SSN`, or (3) both — `USERID = ID AND USER_SSN = SSN`?
    > 2. **User identifier to expose** — `ID` or `SSN`?
  - **No obvious key**: the table has no column that appears to uniquely identify rows. **Stop immediately.** Tell the user: "I cannot generate a task table — the entity table `<TABLE>` has no single-column candidate key. The framework requires a unique identifier per entity row to join the task table to the source concept. Can you confirm which column uniquely identifies each row, or provide a table that has one?"
  - **Composite key only** (e.g., `(CUSTOMERS.customer_id, CUSTOMERS.date)` together identify rows): **Stop immediately.** Tell the user: "I cannot generate a task table — the entity table `<TABLE>` appears to require a composite key `(col_a, col_b)` to uniquely identify rows. The framework requires a single-column join key. Options: (1) use a different table that has a surrogate key, or (2) create a deduplicated entity table with a single PK." If the user has already stated that no single-column candidate key exists, take them at their word — do not generate SQL to investigate further.
- **Task type**: based on what the user said, name the most likely type — e.g., "You mentioned churn, so I'm assuming Binary classification."
- **Event timestamp** *(temporal mode only)*: State the column and its type. Then apply exactly one of the two phrasings below — never mix them:
  - **Entity creation/submission date** (e.g. `PAPERS.Submission_Date`, `CUSTOMERS.created_at`): the column marks when the entity entered the world. Write: "`TABLE.column` (TYPE) — determines each [entity]'s lifetime; a [entity] can only receive a cutoff on or after its [submission/creation] date. The actual cutoff dates (`cutoff_ts`) will be defined by the cutoff policy." Do **not** say it "defines cutoffs" or "anchors the cutoff" — that is the cutoff policy's job.
  - **Event/transaction timestamp** (e.g. `ORDERS.order_ts`, `TRANSACTIONS.T_DAT`): the column records when individual events happened and drives rolling cutoff generation. Write: "`TABLE.column` (TYPE) — records when each [event] occurred; cutoffs will be generated from this column according to the cutoff policy."
- **Ambiguities you can't resolve**: name them explicitly — e.g., "I see both `ORDERS.created_at` and `ORDERS.updated_at` — which is the event time?" For non-temporal tasks, do not raise timestamp ambiguity here unless it calls the temporal/non-temporal decision itself into question.

**Never raise cutoff structure here.** Do not ask about single vs. rolling cutoffs, cutoff frequency, or cutoff policies at this stage — these are settled in Step 3 (Define the task spec) after the task type is confirmed. Even if the cutoff design seems ambiguous (e.g. one cutoff per entity vs. monthly snapshots), do not mention it.

Close Turn 1B-iii with an explicit confirmation ask: "Does everything above look correct? Let me know if anything needs changing, and I'll proceed once you confirm."

**Do not send the date range query yet. Wait for the user to confirm (or correct) before proceeding.**

**Turn 1B-iv does not exist as a separate turn.** The date range query is deferred to Step 3, right before the point that actually consumes it (cutoff-strategy parameters that default from the data range, or the train/val/test split boundaries). Asking for it immediately after Turn 1B-iii — before the task type, cutoff policy, or split are even settled — makes the user answer a question whose purpose isn't yet visible. Proceed straight to Step 2 as soon as the inferences are confirmed, for both temporal and non-temporal tasks. See **Step 3** for exactly where the date range query is sent and the reusable template.

Example of Turn 1B-i (determine temporal vs. non-temporal):

*Inferable case — label already lives on the entity table itself:*
> This looks like a non-temporal task: `BADGES.CLASS` is already a column on the entity table, so the goal would be to fill in this attribute for badges where it's hidden, using patterns in the data — treating all dataset entities and values as valid at all times, rather than forecasting something that happens in the future. Is that right, or did you have a temporal angle in mind, like predicting a badge's class before it's awarded?

*Not inferable case — ask directly:*
> Before I map out the tables, one thing I can't tell from the description alone: is this a **temporal** or a **non-temporal** task?
> - **Temporal**: the label depends on something that happens after a cutoff time (e.g. "will X happen in the next N days?"). The task table carries a cutoff timestamp per row.
> - **Non-temporal**: the label is a static or hidden attribute of the entity itself, independent of time. The task table is a plain `(entity_id, label)` pair, split randomly rather than by date.

Example of Turn 1B-ii (subset lead-in + table roles):

> All two tables you mentioned are needed here: `CUSTOMERS` for the entity and `TRANSACTIONS` to compute the churn label.
>
> Based on your schemas, here are the table roles — correct anything that's off:
>
> - `TRANSACTIONS` (Purchases) — one row per purchase event; "Purchases" taken directly from the user's description "predict which customers will churn based on their purchases"
> - `CUSTOMERS` (Customers) — one row per customer; "Customers" taken directly from the user's description
>
> Do these table roles look correct? Let me know if anything needs changing, and I'll continue once you confirm.

Example of Turn 1B-ii when the label lives on the entity table (subset narrower than what the user described):

> Only `BADGES` is needed for this task table — `CLASS` already lives on the entity table, so no other table is required to compute the label. Your other tables (`COMMENTS`, `POSTHISTORY`, `POSTLINKS`, `POSTS`, `USERS`, `VOTES`) come into play later, when `rai-predictive-modeling` builds the graph.
>
> Based on your schema, here's the table role — correct anything that's off:
>
> - `BADGES` (Badges) — one row per badge awarded; "Badges" taken directly from the user's description
>
> Does this table role look correct? Let me know if anything needs changing, and I'll continue once you confirm.

Example of Turn 1B-iii (remaining inferences, sent only after table roles are confirmed):

*Transaction-timestamp case (event table drives cutoffs):*
> - **Prediction Entity & Key**: `CUSTOMERS.C_CUSTOMER_ID` (TEXT, ✓) — the prediction entity is a customer, joined to `TRANSACTIONS` via `TRANSACTIONS.T_CUSTOMER_ID`
> - **Task type**: Binary classification — label = 1 if no purchase in the next N days (churn)
> - **Event timestamp**: `TRANSACTIONS.T_DAT` (DATE) — records when each purchase occurred; cutoffs will be generated from this column according to the cutoff policy.
>
> Does everything above look correct? Let me know if anything needs changing, and I'll proceed once you confirm.

*Entity-creation-date case (paper submission date bounds the lifetime):*
> - **Prediction Entity & Key**: `PAPERS.Paper_ID` (TEXT, ✓) — the prediction entity is a paper, joined to `CITATIONS` via `CITATIONS.References_Paper_ID`
> - **Task type**: Binary classification — label = 1 if the paper receives at least one citation where `CITATIONS.Submission_Date` falls in `(cutoff_ts, cutoff_ts + 6 months]`, else 0
> - **Event timestamp**: `PAPERS.Submission_Date` (DATE) — determines each paper's lifetime; a paper can only receive a cutoff on or after its submission date. The actual cutoff dates (`cutoff_ts`) will be defined by the cutoff policy.
>
> Does everything above look correct? Let me know if anything needs changing, and I'll proceed once you confirm.

*Non-temporal case (label already present on the entity, no Event timestamp bullet):*
> - **Prediction Entity & Key**: `BADGES.ID` (NUMBER, ✓) — the prediction entity is a badge
> - **Task type**: Multiclass classification — `label` = `BADGES.Class` (passed through as-is, no re-encoding)
>
> Does everything above look correct? Let me know if anything needs changing, and I'll proceed once you confirm.

For the date range query template and exactly where it fires within Step 3, see the **Date range query** subsection under "Define the task configuration" below.

Do not proceed to step 2 until the user has confirmed the inferences — for both temporal and non-temporal tasks. The date range is no longer collected at this point; see Step 3.

### 2. Pick the task type

The six supported tasks and their distinguishing questions:

| Task type | Distinguishing question | Label shape |
|---|---|---|
| Binary classification | "Will entity X do Y by time T?" with a yes/no answer | `(entity_id, cutoff_ts, label∈{0,1})` |
| Multiclass classification | "Which one of K mutually exclusive classes does entity X belong to at time T?" | `(entity_id, cutoff_ts, label)` — `label` is the raw category value, not re-encoded |
| Multilabel classification | "Which subset of K (non-exclusive) tags applies to entity X at time T?" | `(entity_id, cutoff_ts, label_vector)` or long form `(entity_id, cutoff_ts, label_id)` with multiple rows per entity |
| Regression | "What continuous value will entity X have/produce by time T?" | `(entity_id, cutoff_ts, target_value∈ℝ)` |
| Link prediction | "What are the top-K dst entities that src is most likely to interact with (including first-time) in (T, T+Δ]?" | `(src_id, cutoff_ts, LIST[dst_id])` — one row per source entity; targets are a list of positive dst PKs; framework samples negatives internally |
| Repeated link prediction | "What are the top-K dst entities that src has already interacted with and will interact with again in (T, T+Δ]?" | `(src_id, cutoff_ts, LIST[dst_id])` — same list format; dst candidate pool restricted to pairs with prior history |

If the user is unsure, ask a short clarifying question rooted in their data — e.g., "you have an `orders` table with `customer_id`, `product_id`, `order_ts` — are you predicting whether a customer will churn (binary on customer), which product they'll buy next (multiclass or link prediction on (customer, product)), or how many times they'll reorder a given product (repeated link)?"

#### Examples: data scenario → task type

Use these to anchor the clarifying question to the user's actual tables.

**Binary classification — churn**
> Tables: `customers(customer_id, created_at)`, `orders(order_id, customer_id, order_ts, total_amount)`
> Question: "Will this customer place any order in the next 90 days?"
> → Binary on `customer_id`; label = 1 if any `order_ts` falls in `(cutoff_ts, cutoff_ts + 90 days]`

**Multiclass classification — next product category**
> Tables: same + `orders.category`
> Question: "Which product category will this customer buy next?"
> → Multiclass on `customer_id`; `label` = the category of the first order after `cutoff_ts`, passed through as-is (one class per row, mutually exclusive)

**Multilabel classification — propensity tags**
> Tables: `customers`, `products(product_id, category)`, `orders(customer_id, product_id, order_ts)`
> Question: "Which product categories is this customer likely to buy in the next 30 days?" (can be more than one)
> → Multilabel on `customer_id`; one row per (customer, category) that occurs in the window, so a customer who buys in two categories gets two rows

**Regression — 90-day revenue**
> Tables: `customers`, `orders(customer_id, order_ts, revenue)`
> Question: "How much revenue will this customer generate in the next 90 days?"
> → Regression on `customer_id`; `target_value` = `SUM(revenue)` where `order_ts` ∈ `(cutoff_ts, cutoff_ts + 90 days]`

**Link prediction — recommend products to a customer**
> Tables: `customers`, `products`, `orders(customer_id, product_id, order_ts)`
> Question: "What are the top-10 products customer C is most likely to buy in the next 91 days?" (includes products never bought before)
> → One row per `(customer_id, cutoff_ts)` with `product_id` as a list of all distinct products purchased in the window. The framework ranks the full product catalogue and evaluates Precision@10, Recall@10, MAP@10.
> Use this when: the output is a ranked recommendations list and you don't control which pairs to score.

**Repeated link prediction — reorder recommendations**
> Tables: same as link prediction
> Question: "Which products that customer C has already bought will they buy again in the next 91 days?"
> → Same list format as link prediction, but the candidate pool is restricted to `(customer, product)` pairs with prior history. The framework only ranks products the customer has previously purchased.
> Use this when: the task is repurchase / reorder / re-engagement, not discovery of new items.

> ⚠ **Binary pair scoring is not a link task.** If you need to score specific `(src, dst)` pairs with a scalar yes/no label and explicit negatives (evaluated with AUC), that is not supported by `LINK_PREDICTION` or `REPEATED_LINK_PREDICTION`. Use `BINARY_CLASSIFICATION` on the source entity with the target encoded as a feature instead.

For details on each task type's schema contract, leakage rules, and worked example, read the matching reference file in `references/` only after the user has chosen a task. Do not load all six reference files up front.

- `task_binary.md`
- `task_multiclass.md`
- `task_multilabel.md`
- `task_regression.md`
- `task_link_prediction.md`
- `task_repeated_link_prediction.md`

### 3. Define the task configuration

Before writing any code, write a draft task configuration back to the user as a short bulleted block and ask them to confirm. The configuration must include every field below; if a field can't be filled, say so and ask:

- **Task type**: one of the six
- **Entity**: the unit being predicted on (e.g., `customer_id`, or `(customer_id, product_id)` for link tasks).
- **Event timestamp**: the source column used to define prediction cutoffs (e.g., `Submission_Date` in `PAPERS`, `order_ts` in `ORDERS`). Always call this field "Event timestamp" when reporting it to the user — never "Cutoff timestamp". When the entity's own submission or creation date serves as the event timestamp (e.g. `PAPERS.Submission_Date`), describe this bullet as "each paper's lifetime begins with its submission date" — not "each paper's cutoff is its submission date".
- **Label definition**: the precise event or condition that defines a positive label, written as a sentence ("a customer is positive at cutoff T if they place an order in (T, T+30 days]"). Keep this bullet strictly about the label condition itself — do not fold in explanations of why the prediction window is omitted or how `cutoff_ts` is derived; that belongs under **Temporal vs non-temporal** instead.
- **Prediction window** *(only when the label depends on a future window)*: the (T, T+Δ] window over which the label is evaluated. When the user states this as "N months" or another approximate duration, ask whether they want **90 days or 91 days (365 // 4)**. Recommend 91 days — it matches the reference implementation convention of `timedelta = pd.Timedelta(days=365 // 4)` and avoids ambiguity with calendar-month arithmetic. Never use `DATEADD('month', N, ...)` unless the user explicitly requests calendar months. Omit this field entirely when the label is already fixed at `cutoff_ts` itself (e.g. the entity's own event timestamp could serve as its cutoff, so there's no future event to wait for) — do not report an N/A placeholder for it. Use conditional phrasing here ("could serve as", "would be fixed to") rather than declarative phrasing ("is fixed to", "will be") — the cutoff policy itself is only settled in the **Cutoff strategy** step below, and the user may choose a policy that samples cutoffs differently than one-per-event. Note the reason for the omission under **Temporal vs non-temporal** below, not here.
- **Feature window** (informational, not enforced by the task table): the window the framework will use for features; relevant only because the task table must not leak from after T
- **Activity filter** (explicit decision required — every task type, not just link tasks): should the task table be restricted to source entities that were active in the Δ-day lookback before `cutoff_ts`? This only applies to temporal tasks — there's no `cutoff_ts` to measure a lookback against for non-temporal tasks, so omit this field entirely for those. The recommended default depends on the task family, and must be proposed and confirmed here, before any SQL is generated — never decided silently at Step 4:
  - **Binary / multiclass / multilabel / regression**: recommend **applying** the filter (see `task_binary.md`'s "strongly recommended" guidance) — without it, long-inactive entities can dominate or trivialize the label (e.g. a churn label that's 1 for someone who was never coming back anyway).
  - **Link / repeated-link prediction**: recommend **no filter** by default (see `task_link_prediction.md`) — many reference implementations omit it entirely; including only active entities produces a more focused model but excludes infrequent users.

  State which default you're proposing and why, and invite the user to correct it — do not apply either default silently.
- **Filters**: any additional entity filters beyond the activity filter (e.g. country = 'US', account_type = 'paid').
- **Temporal vs non-temporal**: restate the mode already confirmed in Turn 1B-i — do not ask this question again here. This field still must appear in the written config since it determines the downstream modeling step.

  - **Temporal**: the GNN samples each entity's subgraph as it existed at the cutoff timestamp, preventing future edges from leaking into training. When the Prediction window was omitted above because `cutoff_ts` could be fixed to the entity's own event timestamp, say so here using the same conditional phrasing: this would be a **feature-availability constraint** (restricting what the GNN can see), not a label-forecasting window, since the label itself is already known as of `cutoff_ts` — but the exact cutoff policy (and whether cutoffs land exactly on the event timestamp or are sampled some other way) is still to be confirmed in the **Cutoff strategy** step below.
  - **Non-temporal**: time is ignored; the GNN learns from the full static database graph.

  If the user changes their mind at this point (e.g. after seeing the rest of the config), treat it as a correction to the Turn 1B-i decision: update it, and re-check whether the Event timestamp bullet needs to be added to or removed from the confirmed inferences before continuing.

  **Hard stop only if the mode was never resolved in Turn 1B-i** (e.g. this skill invocation started mid-flow, or the user asked to skip ahead): ask the temporal question below, send the spec up to this point, and wait for the user's reply before proceeding. Do not load `utils_cutoff_policies.md` and do not mention cutoff policies at this stage.

  > Should the GNN use **temporal** or **non-temporal** mode?
  >
  > - **Temporal**: the GNN samples each entity's subgraph as it existed at `cutoff_ts` — future edges are excluded from training. Use this when the graph evolves over time and labels are observed after the cutoff (e.g. predicting a future event for a paper/customer/transaction that hasn't happened yet).
  > - **Non-temporal**: time is ignored; the GNN learns from the full graph. Use this when you have a complete historical dataset and want to predict hidden or missing labels from graph structure alone (e.g. a label exists but was not observed for some entities).

  Do not assume temporal just because the data contains timestamps or event-based edges. Temporal is the right choice only when labels are observed after `cutoff_ts` and the graph is incomplete at prediction time. For label imputation on a fixed historical graph, non-temporal with a random split is correct and avoids unnecessary complexity.

- **Cutoff strategy** *(Temporal only)*:

  - **If the user chose Non-temporal**: omit this field entirely. Do not mention cutoff policies. Proceed directly to the Split configuration field.
  - **If the user chose Temporal**: only now read `utils_cutoff_policies.md` and follow its instructions — rewrite each policy description for the session's prediction problem, present the menu, and collect the user's choice and all required parameters. **If the chosen policy's parameters default from the data range** (Policy 1 `generate_timestamp_randomly_from_range`, Policy 2 `sample_timestamp_randomly_from_range`, or Policy 4 `rolling_fixed` — each has a `cutoff_start`/`cutoff_end` that defaults to the data's start date or `MAX_SAFE_DATE`), send the **Date range query** below before finalizing those parameters. Policy 3 (`event_relative`) needs no parameters at all, so no date range is needed to configure it. Present the chosen policy and its confirmed parameters as a concise summary, then close with an explicit confirmation ask: "Does the cutoff strategy above look right?" **Do not mention or propose the split configuration until the user explicitly confirms the cutoff strategy.**

  **Hard stop — do not draft the Split configuration question yet.** Immediately after the user confirms the cutoff strategy, work through the **Prediction window vs. data density check** immediately below. Only once that check is resolved (or ruled not relevant) does the Split configuration bullet become the next thing you send.

  ##### Prediction window vs. data density check

  Unlike dataset size and class balance (which are just informational and live in Section 3 of the generated SQL, never gating anything — see "Configuration quality check" below), this check can change what actually gets generated, so it happens here, before code generation, not after.

  **First, decide whether it's relevant at all** — skip it entirely for a **tiling** configuration, where the prediction window and the cutoff cadence line up to form a recurring, non-overlapping measurement (e.g. weekly cutoffs with a 7-day window, or quarterly cutoffs with a ~91-day window). In a tiling setup, a zero/empty result for a given window is a real, valid measurement of that period, not a sign that the window is misconfigured — so the check has nothing meaningful to catch.

  - **`rolling_fixed`**: relevant only when the prediction window does **not** roughly match the cutoff `frequency` (e.g. monthly cutoffs with a 365-day window — heavy overlap, not tiling). Skip it when they do roughly match.
  - **`event_relative`** (intrinsic label): never relevant — there is no prediction window to check against.
  - **`generate_timestamp_randomly_from_range`** / **`sample_timestamp_randomly_from_range`**: **always relevant** — cutoffs are sampled per-entity independent of the window, so nothing tiles by construction. This is the common case: do not let a confirmed cutoff strategy using either policy flow straight into the Split configuration question.
  - **`custom`**: judge from the user's own description of their cutoff logic — treat it as relevant unless they've described something clearly periodic/tiling themselves.

  **If relevant**, send this as its own message with a short intro explaining plainly why it matters right now — e.g. "One more thing before we set the split boundaries — I want to check whether your [N]-day window is long enough relative to how often a typical [entity] actually [does the event], so the labels aren't mostly empty."

  ```sql
  SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_days) AS median_gap_days
  FROM (
      SELECT DATEDIFF('day', LAG(event_ts) OVER (PARTITION BY entity_id ORDER BY event_ts), event_ts) AS gap_days
      FROM DB.SCHEMA.EVENT_TABLE
  );
  ```

  **If automatic execution is enabled** (Step 0), run this query yourself via `run_sql` (per `utils_auto_execution.md`) and fold the result straight into this discussion — no need to wait for a pasted reply.

  - **If the median gap is comfortably below the prediction window**: say so in one sentence and move straight on to Split configuration — no need to dwell on it.
  - **If the median gap is close to or exceeds the prediction window**: name the risk plainly (most entities will score an empty/negative label even when they're genuinely active), explain why it hurts the model, and propose one concrete fix — widen the window, or reconsider the cutoff policy. Ask once whether they'd like to adjust.
    - If they agree, apply the change and re-confirm the affected configuration fields before moving on.
    - **If they decline, proceed as-is and do not ask again** — not later in this same configuration, and not if they revisit this task table later in the conversation. One ask is the limit.

  Then, and only then, proceed to Split configuration.

- **Split configuration** *(send as a separate message, only after cutoff strategy is confirmed and, if applicable, the prediction-window-vs-data-density check above has been resolved)*: this has two parts — the split **scenario**, then the specific boundaries/proportions for it. Never assume a scenario silently, even though three-way is the recommended default. Ask:

  > How would you like to split the task table?
  > - **Train / val / test** (default) — three-way split.
  > - **Two-way** — only two parts: `train` / `val`.
  > - **No split** — a single table, no `split` column; every row is available for training/use. Pick this only if you're handling the split yourself downstream, or don't need one at all.

  Once the scenario is confirmed, propose the specific boundaries or proportions for exactly the parts chosen — time-based cutoff dates for temporal tasks, or proportions for non-temporal/random splits — suited to the confirmed cutoff policy and data range. Skip this second half entirely if the user chose no split. **If the date range hasn't already been collected** (e.g. the chosen cutoff policy needed no data-range-derived parameters, as with `event_relative`), send the **Date range query** below now — this is the last point it can be deferred to, since split boundaries cannot be proposed without knowing the actual min/max of the data. Close with an explicit confirmation ask before proceeding. **Do not proceed to the configuration quality check or code generation until the user confirms both the split scenario and (if applicable) its boundaries/proportions.**

Do not proceed to code generation until both the cutoff strategy and the split configuration have each been confirmed in their own separate turn.

#### Date range query

Send this only at the first point above that actually needs it — not preemptively in Step 1. Send it as its own message with a short intro; do not re-list the assumptions. Use the entity/event timestamp column identified in Turn 1B-iii.

**If automatic execution is enabled** (Step 0), run this query yourself via `run_sql` (per `utils_auto_execution.md`) and fold the result straight into the cutoff-strategy or split-boundary discussion — no need to wait for a pasted reply.

The intro must explain, in a sentence or two, *why* this query is needed right now and *how* the results will be used — e.g. that `MIN`/`MAX` will anchor the default `cutoff_start`/`cutoff_end` for the chosen cutoff policy, or that they'll set the time boundaries for the train/val/test split. Name the specific downstream use for this session (which parameter or split boundary it feeds), not a generic restatement like "I need the date range."

**Double-quote check**: before writing this query, check whether the column names returned by Query 1 (Turn 1A-ii) came back in lowercase (e.g. `review_time`, `customer_id`). If they did, the source table was created with quoted identifiers — wrap every column reference in double quotes in this query and in all subsequent generated SQL.

Template (unquoted version — add quotes if column names were lowercase):

```sql
SELECT
    MIN(ts_col)                   AS first_event,
    MAX(ts_col)                   AS last_event,
    COUNT(DISTINCT entity_id_col) AS distinct_entities,
    COUNT(*)                      AS total_rows
FROM DB.SCHEMA.EVENT_TABLE;
```

Quoted version example (use when column names came back lowercase):

```sql
SELECT
    MIN("review_time")            AS first_event,
    MAX("review_time")            AS last_event,
    COUNT(DISTINCT "customer_id") AS distinct_customers,
    COUNT(*)                      AS total_rows
FROM REL_AMAZON_DB.DATA.REVIEW;
```

Example intro (cutoff parameters): "One more thing before I set the cutoff-range defaults — I need the date range of your [transactions/badges/...]: `MIN`/`MAX` will become the default `cutoff_start`/`cutoff_end` for [policy name] unless you override them."

**If automatic execution is enabled** (Step 0), run this query yourself via `run_sql` (per `utils_auto_execution.md`) and fold the result straight into whichever discussion it's feeding — no need to wait for a pasted reply.

Example intro (train/val/test split): "One more thing before I propose the train/val/test split — I need the date range of your [transactions/badges/...]: the earliest and latest [event] dates set the boundaries I'll use to divide time into train/val/test windows."

#### Configuration quality check — don't gate on it, annotate instead

After the user confirms the configuration, do not flag concerns in chat and do not ask the user to run any query before generating code. Nothing stands between configuration confirmation and code generation — proceed directly to Step 4.

The dataset-size signal this step used to evaluate inline is just an interpretation of a number the main artifact's Section 3 already computes — that becomes a one-line explanatory comment on the relevant Section 3 line when Step 4 generates the SQL, not a chat message. The prediction-window-vs-data-density signal is handled earlier now, before code generation — see "Prediction window vs. data density check" above — because unlike dataset size it can actually change what gets generated (a different window, a different cutoff policy), so it's worth resolving before, not after. Class balance is not annotated with a target range anywhere — what counts as a healthy positive rate is entirely problem-dependent (a 1% positive rate with strong signal can be a perfectly good task), so no comment asserting a universal "healthy range" belongs in generated SQL. The timedelta/docstring-mismatch signal has been dropped entirely — adapting an existing task class with a docstring/code mismatch was judged too narrow a scenario to build a standing check around.

Do not proactively suggest multi-dataset experimentation, and never ask the user whether they'd like multiple training dataset variants — not at this point, and not anywhere else in the flow. If the user brings it up unprompted, see the parent skill's [Multi-dataset experimentation](../SKILL.md#multi-dataset-experimentation) section for the pattern to follow.

### 4. Generate code

Generate **Snowflake SQL**, following the conventions in `utils_conventions.md`.

Always produce a single SQL artifact with these four sections in order:

1. **Schema** — `CREATE SCHEMA IF NOT EXISTS DB.TASK_SCHEMA` (one schema per task, named after the task)
2. **STAGING table** — DDL + INSERT with full CTE chain; includes `split` column (`'train'`/`'val'`/`'test'`)
3. **Validation queries** — run against STAGING; must report row count, nulls, and class balance per split. For temporal tasks also include a temporal leakage check. For link/repeated-link tasks also report list-length distribution (min, median, max items per row) and duplicate `(src_id, cutoff_ts)` pairs. Also include, per the "Deeper diagnostics" note below: a one-line comment on the row-count line about the ~5,000-row minimum. Report the class-balance number itself (per the base requirement above) but do not annotate it with a target range — see "Deeper diagnostics" for why. The prediction-window-vs-data-density check does **not** belong here — it's already been resolved earlier in the conversation, before code generation (see Step 3's "Prediction window vs. data density check").
4. **Split tables** — `CREATE TABLE ... AS SELECT * EXCLUDE (cutoff_<table>_<source_time_col>, split) FROM STAGING WHERE split = '...'` for TRAIN, VAL, TEST. For non-temporal tasks omit only `split`. Use Snowflake's `EXCLUDE` syntax to keep the column list maintainable. See the parent skill's [Downstream column naming contract](../SKILL.md#downstream-column-naming-contract) for the full temporal-column naming rules.

Do not merge STAGING and the split tables into one step. The user must be able to run section 3 (validation) before executing section 4. Add a comment before section 4 reading `-- Run the validation queries above before executing this section.`

**If automatic execution is enabled** (Step 0), the tiers from `utils_auto_execution.md` apply here too:
- Section 3 (validation queries) is read-only — run it yourself via `run_sql` after producing the artifact and report the results, no extra confirmation needed per query.
- Sections 1, 2, and 4 (schema creation, STAGING, split tables) are write/DDL — don't auto-run them by default, and never proactively ask to run them as part of, or immediately after, the code-generation summary. The summary ends with only the standard proactive-offer closing (`utils_output_format.md`) — no run-confirmation attached. Only once the user separately asks to execute a section (e.g. "run it", "go ahead and create the schema") do you show that section's SQL and ask an explicit "should I run this against `<DB>.<SCHEMA>` now?" before executing it via `run_sql` — unless `utils_auto_execution.md`'s narrow exception applies, in which case state what you're about to run and proceed without waiting for that per-section ask. Ask separately for STAGING and for the split tables, in that order — don't treat one confirmation as covering both, and don't infer consent for one section from having run another.

#### Deeper diagnostics — fold into Section 3, don't spin up a separate file

Signals that used to be evaluated (and flagged, or asked about) before code generation now live inside the main artifact's Section 3, not a separate file — a separate file was considered and rejected as an unnecessary second thing for the user to remember to open:

- **Dataset size** — no new query; add a one-line comment directly on the `row_count` line noting that GNNs typically need at least ~5,000 training rows to generalize, and to loosen the activity filter or extend the training cutoff range if `train` comes back lower.
- **Class balance** (binary/multilabel only) — no new query, and no annotation with a target range. Report the number (the existing per-split class-balance line already does this) but do not comment on it as healthy/unhealthy at any particular percentage — there is no universal "good" positive rate; a heavily imbalanced problem (e.g. 1% positive) can carry perfectly strong signal and produce a good model. Whether a given rate is a problem is a judgment call for the person building the model, not something to assert in a comment baked into every generated task table.

The timedelta/docstring-mismatch signal has been dropped — it only fires when the user is adapting an existing task class with a docstring that drifted from its own code, which was judged too narrow a scenario to build a standing check around.

#### Downstream column naming contract

See the parent skill's [Downstream column naming contract](../SKILL.md#downstream-column-naming-contract) for the full table (`label`/`value`/target-FK/`cutoff_<table>_<source_time_col>`) — no renaming is possible after the fact, since the downstream `rai-predictive-modeling` step binds these columns by name via a `Relationship` template.

If the source data uses a different name for the label (e.g., `churned`, `revenue`), alias it to `label` / `value` in the INSERT SELECT — do not pass the raw name through.

For the generated SQL:
- Wrap the population logic in a CTE chain, not a single nested SELECT, so the user can run intermediate CTEs to debug.
- Use `QUALIFY` instead of subquery deduplication where it improves readability.
- Keep the cutoff/anchor columns in whatever type the source event-time column actually has (`DATE`, `TIMESTAMP_NTZ`, `TIMESTAMP_TZ`, etc.) — never cast or normalize to a different type. If two source event columns disagree in type, pick one and say which; don't cast one into the other's type as a workaround.
- Comment every step with one line explaining what it does.

For **temporal tasks**, after writing the CTE chain, verify that all feature CTEs are bounded by `<= cutoff_ts` and only the label CTE reads forward. Common leaks: `MAX(event_ts)` or `LAST_VALUE` without a cutoff bound; joins to slowly-changing dimension tables without history; negative sampling drawn from the full future graph. If a potential leak is found, note it in one sentence in the Query logic section of the summary.

#### Validate the SQL before returning it

The final SQL artifact must pass validation before it is shown to the user — do not treat "the query looks right" as sufficient. **If the user opted out of validation in Step 0**, skip this step entirely — go straight to `utils_output_format.md`, which has its own note for this case. Otherwise, read `utils_validation.md` now and follow its steps in full before proceeding.

Before producing the summary, read `utils_output_format.md`.

## When to push back

- **No single-column candidate key on the entity table (hard stop)**: the task table joins to the downstream source concept via a single column. If the entity table has no single-column unique identifier — either no PK at all, or only a composite key — do not generate any SQL. Tell the user immediately and offer two remedies: identify a surrogate column that is actually unique, or create a deduplicated entity view with a single PK.
- If the user asks for "a task table" without naming a prediction problem, do not invent one. Ask.
- If the label window the user proposes overlaps with the feature window the framework will use, flag it and propose a gap.
- If the user requests link prediction and proposes adding explicit negatives to the task table, clarify that this framework samples negatives internally — the task table should contain only positive lists. If they need binary pair scoring (scalar label, AUC evaluation), redirect to Binary classification on the source entity.
- If the user asks for repeated link prediction with a count target but the underlying event table only records the most recent interaction, flag that the data doesn't support the task.
- If automatic execution (Step 0) is enabled, never run a `CREATE`/`INSERT`/write statement without a fresh, explicit confirmation for that exact statement — the standing opt-in covers reads only, not writes, unless the user's own opening message met the narrow exception in `utils_auto_execution.md`.

## What comes next: predictive modeling and training

See the parent skill's [What comes next](../SKILL.md#what-comes-next-predictive-modeling-and-training) section for the full `rai-predictive-modeling` / `rai-predictive-training` walkthrough and the task-type → downstream configuration table.

## Multi-dataset experimentation

This skill never proactively suggests or asks about multi-dataset experimentation. If the user requests it themselves, see the parent skill's [Multi-dataset experimentation](../SKILL.md#multi-dataset-experimentation) section for the pattern (fix test/val, vary train only).

## Quick reference: the six task types at a glance

See the parent skill's [Quick reference](../SKILL.md#quick-reference-the-six-task-types-at-a-glance). The reference files in `references/` are the source of truth.
