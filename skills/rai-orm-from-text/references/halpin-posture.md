# Halpin Posture

The mindset behind Halpin's CSDP. Load before running CSDP for the first time. Re-read when the user defaults to ER vocabulary, when subtype proposals get sloppy, or when the model starts drifting toward attribute-thinking.

The procedure (`csdp-workflow.md`) and the dialogue patterns (`dialogue-patterns.md`) implement Halpin's methodology. This file explains the *why* — the underlying ORM 2 posture that, if internalized, makes the procedure work and, if missed, makes it produce ER-style output dressed in ORM 2 clothes.

## The five pillars

### 1. Atomic facts only

Every claim about the domain is decomposed into elementary facts — atomic, irreducible predicates connecting object types.

**Atomic:** *"John was born in Australia."* Cannot be split without losing meaning.

**Not atomic:** *"John (35, Australian) was born in 1990."* Three claims fused: age, citizenship, birth year.

The decomposition surfaces structure that compound facts hide. A uniqueness constraint goes on roles of an atomic fact type; you can't sensibly put a uniqueness bar on a compound predicate. A mandatory constraint applies to a role; if the role doesn't exist as such (because it was fused into a compound), you can't constrain it.

**Procedural implication:** at Step 1, every example the user provides gets decomposed before being verbalized back. If the user says *"each Order has a status, date, and customer"*, you don't write one fact type; you write three.

### 2. No attributes — only fact types and roles

Object types don't have attributes. They participate in fact types via roles.

The ER tradition is: "Employee has attributes name, age, salary, department". ORM 2's rephrasing is: "Employee plays roles in five fact types: has-name, has-age, has-salary, in-department, managed-by".

Why it matters:

| ER attribute thinking | ORM 2 role thinking | Why ORM 2 wins |
|---|---|---|
| "Employee.department is a foreign key" | "Employee is in Department" (binary fact type) | Constraint can attach to the role; readable as English |
| "Employee.manager_id self-references Employee" | "Employee is managed by Employee" (self-referential, with named roles employee/manager) | Self-reference is first-class; ring constraints attach naturally |
| "Order has many OrderLines" | "OrderLine for Order" (with composite identity if objectified) | Objectification (the relationship-as-entity pattern) is direct, not bolted on |
| "Composite primary key (order_id, product_id)" | External uniqueness across binary fact types | The constraint is at the fact-type level where it belongs |

**Procedural implication:** when the user says "Customer has fields name, email, phone" don't write `customer.fields = [name, email, phone]` or `customer.attributes = ...`. Verbalize:
- *"Customer has name."*
- *"Customer has email."*
- *"Customer has phone."*

Each is a separate fact type with its own uniqueness, mandatory, and value constraints.

### 3. Populate before constraining

Halpin's CSDP populates each fact type with sample fact instances **before** asking about uniqueness, mandatory, or value constraints. The populations make the constraint questions concrete.

Without populations, asking "is the Person role unique on the born-in fact type?" is abstract. With populations:

```
Person born-in Country:
  John     Australia
  Mary     Greece
  Carlos   Spain
```

The question becomes: *"In your sample, each Person has at most one Country. Does that hold in general, or could a Person have multiple birth Countries?"*

The population is the user's reality. The constraint question is *checking* the population, not proposing a constraint from thin air.

**Procedural implication:** Step 4 (uniqueness) cannot proceed without Step 2's populations. If the user gave no examples at Step 1, you cannot do Step 4 well — push back: "I need a few sample facts before asking about uniqueness — could you give me 3–5 examples?"

### 4. Verbalize then validate (never assert)

ORM 2's controlled natural language (CNL) is the user-facing surface. The model exists in the user's head as English sentences ("each Order is placed by exactly one Customer"). The YAML and PyRel are downstream artifacts.

CSDP's discipline is to verbalize the proposed model back to the user — not as a statement of fact, but as a question.

**Right:** *"I'm reading: 'Each Order is placed by exactly one Customer.' Is that exactly true in your domain, or are there exceptions?"*

**Wrong:** *"Each Order is placed by exactly one Customer. Moving on."*

The wrong form assumes the user agrees. The right form lets the user catch errors.

**Procedural implication:** every fact type emitted at Step 2, every constraint emitted at Steps 4/5/6, and every relationship merge proposed at Step 3 gets verbalized back as a question. Confirmation is explicit.

### 5. Subtypes are role-based, not attribute-based

A subtype is justified in ORM 2 **only when its instances play roles the supertype doesn't.** "Different attributes" isn't enough.

| Justification | ORM 2 subtype? |
|---|---|
| "Managers earn more than ICs" | No — salary is a value the Employee already has; the difference is in the value range, not in the role |
| "Every Manager has a budget assigned; ICs don't" | Yes — Manager plays the has-budget role, IC doesn't |
| "Cars have wheels, motorcycles don't" | No — both might have wheels; a count or type value differentiates them, not a role difference |
| "Cars have a body-style, motorcycles have an engine displacement" | Yes — each subtype plays a role the other doesn't |

The role-based criterion sounds pedantic but it's the single best heuristic for catching over-subtyping. ER models tend to introduce a subtype for every distinguishable attribute combination; ORM 2 keeps the hierarchy flatter and pushes the variation into value spaces or properties.

**Procedural implication:** at the Step 6 subtype check, when the user (or the LLM tier) proposes a subtype, ask: *"Does {Subtype} play any roles {Supertype} doesn't?"* If no → reject the subtype; emit a value or property instead.

## Halpin vocabulary cheat sheet

When the user uses ER vocabulary, translate to Halpin vocabulary while continuing the conversation. Don't lecture; just shift the words:

| ER term (what users say) | Halpin term (what you use back) |
|---|---|
| table, entity table | entity type (or object type) |
| reference table, lookup table | value type (or sometimes entity type) |
| column, attribute, field | role (or value, depending on side) |
| primary key | reference scheme, preferred internal UC |
| composite primary key | external uniqueness constraint |
| foreign key | binary fact type connecting two entity types |
| relationship, relationship type | fact type (always — there are unary, binary, ternary, n-ary fact types) |
| cardinality (1:1, 1:n, m:n) | uniqueness constraint pattern |
| optional column | role without mandatory constraint |
| required (NOT NULL) column | role with mandatory constraint |
| CHECK constraint | value constraint (range, enumeration) |
| ENUM type | value type with object-type-scope value constraint (or `model.Enum` in PyRel) |
| junction table | either binary m:n fact type or objectified fact type |
| associative entity | objectified fact type |
| derived column, computed column | derived fact type (with derivation rule) |

The point isn't to be pedantic — it's to keep the user's intent visible in fact-based terms. Once the user sees the translation a few times, they'll start using Halpin's terms themselves.

## Why Halpin posture matters

A skill that produces "ORM-shaped YAML" without Halpin posture produces ER models with renamed boxes. The fact types might have proper structure, but the constraint analysis stays attribute-driven, the subtype hierarchy explodes, and the verbalization reads like SQL schema documentation rather than natural language.

Halpin's whole methodology hinges on **modeling the domain in natural language first, then mechanically deriving the structural model from the language.** If you skip the natural-language step, you're back to ER with extra vocabulary.

CSDP's seven steps are designed around this. Step 1 forces atomic decomposition. Step 2 forces population. Step 3 forces synonym/derivation discovery in domain terms. Steps 4–6 derive constraints from the populated fact types, not from imagined data shape. Step 7 verifies the whole model in CNL.

When this works, the user can validate the entire model by reading the verbalization to a stakeholder who knows the domain. That's the goal — the stakeholder confirms or challenges each sentence. No SQL, no ER diagrams, no Halpin notation needed.

## Common posture failures and recovery

### Failure: "let me just describe the data shape"

User says: *"I have Customers, each with an email, name, and phone. Customers place Orders, which have items..."*

This is ER-style data-shape description. **The skill's job is to honor the user's intent while reframing in fact-based terms.** Don't say "stop, that's wrong." Translate:

> *"OK. In ORM I'd model that as:*
> *- Customer (entity type, identified by — what? email? a customer ID?)*
> *- Customer has-name {String} — is the name unique per Customer?*
> *- Customer has-email {EmailAddress}*
> *- Customer has-phone {String}*
> *- Order placed-by Customer*
> *- Order contains OrderLine* — *or maybe OrderLine for Order...*
>
> *Before we go deeper, a question I always ask: how is each Customer identified? By the customer-id, by the email, by the name?"*

This continues the conversation in Halpin terms without arguing about vocabulary.

### Failure: "every Manager is an Employee, every Employee is a Person"

User proposes a deep subtype hierarchy. **Apply the role-based criterion at each level:**

- Does Employee play roles Person doesn't? (e.g., has-salary, in-department) → yes → subtype justified.
- Does Manager play roles Employee doesn't? (e.g., manages, has-budget-of) → if yes, subtype; if no, just a value/property.

If the user pushes back ("but Managers are conceptually different from ICs"), ask for one concrete role that differentiates them:

> *"Got it. What's one fact about a Manager that wouldn't be true of every Employee? For example: 'every Manager manages someone' — is that always true in your domain? If so, that's a role difference and Manager is a proper subtype."*

### Failure: "compound fact, compound fact, compound fact"

User keeps describing facts as compounds. **Decompose patiently. Don't move on until atomic.**

User: *"Each customer places orders with various items at different times for different shipping addresses."*

You: *"That packs in several elementary facts. Let me decompose:*
> *- 'Customer places Order.'*
> *- 'Order contains LineItem.' (or 'LineItem for Order' if we objectify)*
> *- 'LineItem is for Product.'*
> *- 'Order placed-at DateTime.'*
> *- 'Order ships-to Address.'*
>
> *Are these the atomic facts? Or should I split any further?"*

### Failure: user disengages

User stops giving examples or starts saying "yeah, whatever, just do what you think."

**Don't proceed silently.** Acknowledge the engagement drop:

> *"I notice we're moving faster than I'd like for a CSDP run. Some of what I'll propose will be best-guesses without your confirmation — and the resulting model will reflect that. Two options:*
> *1. Slow down and confirm explicitly — I'll re-verbalize at each step.*
> *2. I'll continue as best-effort and mark everything as `proposed`; you review the YAML afterward.*
>
> *Which fits your time budget?"*

## How posture interacts with the tooling

The skill's YAML format, constraint library, and PyRel translator are all designed around Halpin posture. Examples:

- **`source: explicit`** means "the user said it." Constraints with this source carry `user_quote` provenance — the user's actual words. This makes the YAML auditable in dialogue terms.
- **`source: sample`** means "visible in the user's small sample population." Halpin populations are small by design; the `proposed`-only status prevents tooling from auto-confirming sample-derived constraints.
- **Modality** (alethic vs deontic) is asked at Step 7e because Halpin treats deontic constraints as first-class. The PyRel translator emits deontic as `# DEONTIC NOTE:` comments rather than `model.require()` — preserving the should-not-must distinction.
- **Reference modes** (popular / unit-based / general / external) are Halpin's vocabulary directly. Eliciting which mode each entity type uses forces the user to think about identity, not just attributes.
- **Constraint placement** (inline vs top-level) follows the scope rule from the format spec — single-fact-type scope inline, cross-fact-type or object-type scope top-level. This mirrors Halpin's diagram conventions (constraints attach to specific fact-type roles or span fact types with dotted-line connectors).

The tooling preserves posture. Bypassing it — by, say, auto-confirming everything in One-shot mode without dialogue — produces a structurally-valid YAML that has none of Halpin's epistemic discipline.

## When to re-read this file

- Before running CSDP for the first time in a session.
- When the user describes the domain using ER vocabulary throughout.
- When the user proposes more than two subtypes per supertype.
- When the user accepts every proposed constraint without pushback.
- When the verbalization reads like SQL schema documentation rather than natural language.

If any of those happen, pause and re-orient. The procedure can recover; bad posture can't.
