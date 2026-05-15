# Dialogue Patterns

Conversational patterns for running CSDP — eliciting examples, asking for reference schemes, decomposing compound facts, handling thin answers, pushing back on premature subtyping, and rescuing stuck conversations. Load at CSDP Steps 1 / 3 / 6 (subtype check) / 7d.

The procedure (`csdp-workflow.md`) tells you what each step does. This file tells you **how to talk to the user** while doing it.

For the underlying mindset these patterns implement, see [`halpin-posture.md`](halpin-posture.md).

## Core principle: verbalize as a question

Every verbalization in CSDP is presented as a question, never as an assertion. This is the single most important dialogue rule.

### ✅ Right

> *"From your example, I'm reading: 'John was born in Australia.' Is this an atomic fact in your domain, or is there more going on?"*

> *"Each Person seems to have exactly one Country of birth in your sample data. Is that always true, or could a Person have multiple birth countries?"*

> *"You're suggesting Manager as a subtype of Employee. Does a Manager play any roles an Employee doesn't?"*

### ❌ Wrong

> *"John was born in Australia. Mary was born in Greece. Adding the fact type."*

> *"Each Person has one Country of birth. Adding uniqueness constraint."*

> *"Adding Manager as a subtype of Employee."*

The wrong examples assume confirmation. They prevent the user from catching the skill's mistakes. They also leak ER-style "let's just build the model" thinking, which obscures the user's domain knowledge.

## Pattern 1 — Eliciting examples (Step 1)

Get the user to provide concrete cases. Start broad:

> *"To start CSDP, I need a few concrete examples from your domain. Could you walk me through a typical case? A sample form, a row from a report, or just describe one specific instance — whatever's most natural for you."*

If the user gives a single example, ask for one or two more:

> *"Thanks. Can you give me one or two more examples? CSDP works by populating fact types with several sample instances. Even 3–5 examples helps validate the structure."*

If the user offers a high-level description but no concrete instance:

> *"Got it — let me make sure I understand. Could you give me one concrete example of a {EntityType} from your domain? A specific instance, with values filled in?"*

If the user provides a form or screenshot:

> *"This is helpful. Walk me through a filled-in row, please — what would a real instance look like with values populated? I'll verbalize each fact and confirm with you."*

## Pattern 2 — Verbalizing elementary facts (Step 1)

For each example the user provides, decompose into atomic facts and verbalize each:

> *"From your example, I'm reading the following elementary facts. Let me verbalize each — please confirm, correct, or reject:*
>
> *1. 'John was born in Australia.' Is this an atomic fact in your domain?*
> *2. 'John has age 35.' Is this an atomic fact?*
> *3. 'Australia is in continent Oceania.' Is this an atomic fact?*"

Wait for explicit confirmation before adding each to the model. If the user confirms with a comment ("yes, but we don't usually call it 'continent'"), incorporate the refinement into the reading:

> *"OK — so 'Australia is in region Oceania' would be the right phrasing? Let me verbalize that fact type more naturally: '{Country} is in {Region}'. Does that work?"*

## Pattern 3 — Reference-scheme elicitation (Step 1)

When a new entity type appears, ask explicitly how its instances are identified. This is the **most-skipped CSDP step** for new users — they default to attribute thinking.

> *"You mentioned 'Person'. How is each Person identified in your domain — by a name, an employee number, a national ID, or something else?"*

If the user says "by name":

> *"OK — so Person is identified by name. In Halpin's notation that's a 'popular' reference mode: each Person has a name that uniquely identifies them. Got it.*
>
> *One follow-up: are two people allowed to have the same name in your domain? If yes, name alone isn't enough — we'd need a separate identifier or a composite (name + something else)."*

If the user defaults to attribute language ("the Person's name and age"):

> *"To clarify: is 'name' how each Person is identified (so the name **is** the Person's identity), or is 'name' a property that Persons have alongside other properties? If the latter, what identifies a Person — an ID, a code?"*

Map the user's answer to one of the four reference modes:
- **popular** (single primitive identifier like `Person(.name)` or `Country(.code)`)
- **unit-based** (Halpin's `Height(cm:)` or `Salary(USD: Money)`)
- **general** (named identifier value type like `Book(ISBN)`)
- **external** (composite identifier across multiple binary fact types)

## Pattern 4 — Decomposing compound facts

When the user describes a compound predicate, break it apart:

User says: *"Each Order has a status, a date, and a customer."*

You respond:

> *"In ORM we'd treat that as three elementary facts rather than one compound one. Let me verbalize each separately:*
> - *'Each Order has status {Status}.'*
> - *'Each Order was placed at {DateTime}.'*
> - *'Each Order is placed by {Customer}.'*
>
> *Are all three atomic facts in your domain?"*

This is critical to ORM 2's posture. Compound facts hide constraint structure (you can't put a uniqueness bar on a compound predicate cleanly) and obscure the model.

## Pattern 5 — Handling thin answers

When the user gives a sparse response ("yeah, looks fine"), drill in:

> *"Thanks. To be sure I have it right, let me re-verbalize: '{Reading}.' Is that exactly how you'd describe it to a colleague who doesn't know the domain? Or would you phrase it differently?"*

If the user says "I don't know" to a constraint question:

> *"That's fair — let me mark this as 'proposed' rather than 'confirmed'. We'll revisit at Step 7 (final review) when you've seen the whole model. If by then you still don't know, we can leave it as a soft proposal and flag it as something to verify in production data later."*

Sparse users get thinner models. There's no algorithmic fix for absent domain expertise — but framing the proposed/confirmed distinction explicitly helps the user know what they're committing to.

## Pattern 6 — Pushing back on attribute thinking

The most common new-user mistake: describing entity types in terms of attributes (the ER way) rather than roles (the ORM way).

User says: *"Each Employee has a name, age, salary, department, and manager."*

You respond:

> *"In ORM we don't model 'attributes' directly — we model elementary facts. Let me verbalize each of those as a fact type:*
> - *'Employee has name {String}.'*
> - *'Employee has age {Age}.'*
> - *'Employee has salary {Money}.'*
> - *'Employee is in department {Department}.'*
> - *'Employee is managed by {Employee}.' (Note: this last one is self-referential.)*
>
> *Are all five elementary facts in your domain?"*

This isn't pedantic — the role-based decomposition surfaces structure that attribute thinking hides:
- "department" becomes a relationship to a Department entity type, not an attribute.
- "manager" becomes a self-referential fact type with named roles (manager / employee), which is where ring constraints attach.
- Each fact type gets independent uniqueness/mandatory constraints.

## Pattern 7 — Pushing back on premature subtyping (Step 6)

A subtype is justified in Halpin's framework **only when its instances play roles the supertype doesn't.** "Different attributes" isn't enough.

When the user proposes a subtype:

> *"You're suggesting Manager as a subtype of Employee. In ORM, a subtype is justified only when its instances play roles that the supertype doesn't. Let me check: does a Manager play any roles that an Employee doesn't?*
>
> *For example: 'every Manager has a budget assigned to them' — is that true, and is it true that not every Employee has a budget? If so, Manager is a real subtype. If the differences are just 'Managers earn more' or 'Managers have a job title that says manager', those are properties of Employee, not a separate subtype."*

If the user confirms a real role difference → emit the subtype.

If the user says "just different attributes" → push:

> *"Got it — in that case Manager isn't a separate ORM subtype. We can either:*
> *1. Keep Manager as a value type (Employee has a 'role' value of Manager / IC / Director).*
> *2. Use an `is_manager: Boolean` flag on Employee.*
> *3. Use a subtype-by-derivation (Manager is a derived subtype where Employee's 'role' value is 'manager') — only worth it if you'll want to put Manager-specific constraints downstream.*
>
> *Which fits your domain?"*

## Pattern 8 — Stuck-conversation rescues

### When the user says "just tell me what to do"

> *"I can — but Halpin's CSDP works best when you provide the domain semantics. I'll propose what I think the model should be, but I'll be guessing at the boundaries (what's atomic? what's required? what's a subtype?). If you can give me one example and confirm my proposed fact types, we get a much better model. Want to try one example?"*

### When the user gives contradictory information

> *"To make sure I have this right: earlier you said 'each Order has one Customer', but now you're saying 'an Order can be placed by multiple Customers in a group purchase scenario.' Is the group-purchase case common or an exception?*
>
> *If common: we should model the relationship as m:n (Order placed-by Customer, with neither side unique).*
> *If exceptional: we can model the common case (1:n) and add a separate fact type or constraint for group purchases.*"

### When the user wants to skip to the end

> *"We can speed up by switching to One-shot mode — you give me a description, I produce a draft model, you review the YAML. Caveat: text-first One-shot is significantly more degraded than Guided. Want to try it, or keep going Guided?"*

### When the user disagrees with a library proposal

> *"Got it — you're saying 'Age' shouldn't have a range constraint of 0-150 because in your domain ages can be historical (e.g., 'years since founding' for an institution). Let me mark this proposal as `rejected` and remove the range constraint. The Age object type stays as a primitive Integer."*

## Pattern 9 — Eliciting user-supplied constraints (Step 7d)

> *"Step 7d is for constraints you know but the system missed. These are typically domain rules that don't come from samples or world knowledge but from your specific organization or domain.*
>
> *Examples:*
> *- 'In our company, each Project has exactly one Project Manager.'*
> *- 'A Customer can only place an Order during business hours.'*
> *- 'Every Order with status 'SHIPPED' has a non-null shipped_at timestamp.'*
>
> *Anything come to mind? Free-form is fine — I'll paraphrase it back as a structured constraint and we'll confirm."*

Then for each rule the user provides:

> *"Got it. Translating that into structured form:*
> *  type: cardinality*
> *  scope: role*
> *  role_ref: { fact_type: project_managed_by, role: manager }*
> *  bound: { min: 1, max: 1 }*
>
> *Is that what you meant?"*

If the user's rule is ambiguous, ask ONE clarifying question. If still ambiguous after one round, emit as `type: textual` rather than guessing.

## Pattern 10 — Modality labelling (Step 7e)

For every confirmed constraint with `source ∈ {common-sense, sample, llm-inferred, user-supplied}`:

> *"This constraint is currently labelled 'alethic' (a must-rule). In ORM 2, constraints are either:*
> *- **Alethic** — necessarily true. The world doesn't allow violations. ('A person has at most one biological mother.')*
> *- **Deontic** — a should-rule. Possible violations exist but they're policy issues, not data-integrity errors. ('A customer should pay within 30 days.')*
>
> *For each constraint, tell me alethic or deontic. Defaults to alethic if you're not sure."*

Batched when many constraints share the same modality:

> *"I have 12 constraints proposed under 'common-sense' source. Would you like to label them all alethic (default), or want to mark some specifically deontic? List the deontic ones; everything else stays alethic."*

## Pattern 11 — Acknowledging Halpin posture violations

If the user describes the model using ER vocabulary throughout (tables, columns, foreign keys), don't translate silently — acknowledge the shift:

> *"I notice you're describing this in terms of tables and columns, which is natural since most data work uses that vocabulary. In ORM we model the domain in 'fact-based' terms — fact types and roles rather than tables and columns. The advantage is that the model captures domain knowledge directly, before deciding how it'll be implemented in a database.*
>
> *As we go, I'll translate your descriptions into Halpin's fact-based vocabulary. The mapping is:*
> *- Table → entity type*
> *- Column → role on a fact type*
> *- Foreign key → reference between two object types in a binary fact type*
> *- Composite primary key → external uniqueness constraint*
>
> *Sound good? Let's continue."*

This gives the user permission to use ER terms casually while you do the translation; doesn't pretend the ER-vs-ORM distinction doesn't exist.

## Pattern 12 — Closing a CSDP session

After Step 7f:

> *"We've finalized the model. To summarize:*
> *- {N} entity types, {N} fact types, {N} constraints.*
> *- {N} explicit, {N} sample, {N} common-sense, {N} llm-inferred, {N} user-supplied.*
> *- {N} alethic, {N} deontic.*
> *- Antipattern flags: {list, if any}.*
>
> *Three files are now in {path}:*
> *- `model.orm.yaml` — the canonical model with full provenance.*
> *- `model.verbalization.txt` — the readable rendering, suitable for stakeholder review.*
> *- `model.py` — the PyRel translation.*
>
> *Want me to walk through any specific part? Otherwise, you can review the verbalization with stakeholders and come back with any changes."*

## Anti-patterns to watch for

| Anti-pattern | Symptom | Fix |
|---|---|---|
| Verbalizing as assertion | "John was born in Australia." with a period, no question mark | Re-phrase: "Is 'John was born in Australia' an atomic fact?" |
| Skipping reference-scheme elicitation | New entity type appears, no question about how it's identified | Stop. Ask: "How is each {EntityType} identified?" before continuing. |
| Accepting compound predicates | User said "Order has status, date, and customer" and you wrote one fact type | Break into three; re-verbalize each as a question |
| Auto-confirming subtypes | User says "Managers are like Employees but with budgets" and you emit Manager subtype | Apply Halpin criterion: do Managers play roles Employees don't? If just "have budgets" → property, not subtype |
| Treating sample-derived constraints as confirmed | 5-fact sample shows uniqueness, you mark `confirmed` | Text-first samples always stay `proposed`. User confirms at 7b. |
| Letting attribute language slide | User says "the Customer's name" and you don't translate | Translate: "so the Customer has-name fact type. Is name how a Customer is identified, or a property the Customer has?" |
| Asserting modality without asking | Defaulting constraints to alethic silently | At 7e, ask explicitly. The user labels each. |

## When the dialogue feels "off"

If you're a few turns in and the conversation feels rushed, sparse, or off-track:

- **Pause and re-orient.** "Let me re-verbalize where we are. Currently the model has: {summary}. Does this match what you intended, or are we drifting?"
- **Ask for a fresh example.** "Could you give me one more concrete example, ideally one that's a bit edge-case? That'll surface assumptions we haven't tested."
- **Drop a step and revisit.** "If I'm overconstraining your domain, we can mark constraints as proposed-only and revisit at Step 7. Better to under-constrain than to assert wrong rules."

The skill's quality is bounded by the user's engagement; honesty about that beats forcing a thin model into a clean-looking YAML.
