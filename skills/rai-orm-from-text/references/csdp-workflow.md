# Conceptual Schema Design Procedure (CSDP) — Full Workflow

The complete 7+1-step CSDP with substeps, mechanics, edge cases, mode behavior, and prompt templates. Load when a step's summary in SKILL.md isn't enough.

CSDP is Halpin's canonical methodology for designing an ORM 2 model from scratch via dialogue with a domain expert. Unlike the SRP (`rai-orm-from-schema`'s schema-recovery procedure), CSDP is **forward design** — the user provides examples and answers questions, the skill verbalizes elementary facts back for confirmation, and the model emerges step by step.

Cross-references:
- Halpin posture (the mindset CSDP depends on) → [`halpin-posture.md`](halpin-posture.md)
- Conversational patterns (eliciting examples, reference schemes, etc.) → [`dialogue-patterns.md`](dialogue-patterns.md)
- YAML output shape per step → [`../../rai-orm-from-schema/references/representation-format.md`](../../rai-orm-from-schema/references/representation-format.md)
- Per-constraint vocabulary → [`../../rai-orm-from-schema/references/constraint-reference.md`](../../rai-orm-from-schema/references/constraint-reference.md)
- Constraint-inference library → [`../../rai-orm-from-schema/references/constraint-inference.md`](../../rai-orm-from-schema/references/constraint-inference.md)
- Verbalization templates → [`verbalization-patterns.md`](verbalization-patterns.md) + [`../../rai-orm-from-schema/references/verbalization-patterns.md`](../../rai-orm-from-schema/references/verbalization-patterns.md)
- PyRel translation rules → [`../../rai-orm-from-schema/references/orm-to-pyrel.md`](../../rai-orm-from-schema/references/orm-to-pyrel.md)

## Workflow shape

| Step | Title | User interaction? |
|---|---|---|
| 0 | Interaction-mode opener | Guided: yes |
| 1 | Elementary facts + verbalization check | yes — the heart of CSDP |
| 2 | Draw fact types + population check | no (autonomous between user turns) |
| 3 | Combine entity types; note arithmetic derivations | yes |
| 4 | Uniqueness constraints + arity check | yes |
| 5 | Mandatory role constraints + logical derivations | yes |
| 6 | Value, set-comparison, ring, subtyping (with 6d LLM spot-check) | Guided: yes at 6d (opt-in) + subtype check |
| 7 | Final review + modality + commit | Guided: yes (six substeps) |
| 8 | Translate to PyRel | no |

Text-first is dialogue-driven throughout; user-interaction is distributed across steps rather than concentrated like the schema-skill's SRP.

## Step 0 — Interaction-mode opener (Guided only; One-shot starts at Step 1)

In One-shot mode this step is skipped — the user has provided a description and CSDP runs autonomously.

In Guided mode, Claude prompts:

> *I can run CSDP in two modes:*
> - *Guided — we walk through Halpin's seven steps in conversation. I ask for examples, verbalize facts back to you, propose constraints, and we commit step by step. Best for high-value or unfamiliar domains.*
> - *One-shot — you give me a detailed domain description up front; I produce a draft model in one pass; you review by editing the YAML. Caveat: text-first One-shot is significantly more degraded than schema-first One-shot. Best for fast retargeting when you already have a rich description.*
> *Which would you prefer?*

Default = Guided if no answer is given.

The user's choice is recorded in `source.mode` of the YAML.

## Step 1 — Elementary facts and verbalization check

**Input:** the user's initial domain description plus whatever the user provides in response to prompts.

**Output:** confirmed elementary facts, captured as a candidate `fact_types` list with sample populations.

**The most important step of CSDP.** Halpin's methodology hinges on elementary-fact decomposition: every claim about the domain becomes an atomic, irreducible fact. Get this wrong and every later step compensates badly.

### Mechanics

For each example the user provides (a sample form, a row from a report, a concrete description), Claude:
1. Identifies object types appearing in the example.
2. Decomposes the example into elementary facts (atomic predicates connecting object types).
3. Verbalizes each elementary fact back to the user **as a question**.
4. Waits for explicit user confirmation before adding the fact to the candidate model.
5. For each new entity type, elicits the reference scheme (popular / unit-based / general / external).

### Critical posture (see `halpin-posture.md`)

- **Atomic decomposition.** Don't accept "Each Order has a status, a date, and a customer." Break into: "Each Order has a status. Each Order has a date. Each Order is placed by a Customer."
- **Verbalize as a question.** Never assert; always ask.
- **Reference-scheme elicitation.** When a new entity type appears, ask "how is each {EntityType} identified — by a number, by a name, by a code?" Push back on attribute-thinking.
- **Don't accept compound predicates.** "X has Y and Z" is two facts.

### Prompt templates

> *"Show me a typical case. Walk me through what a real instance looks like — a sample form, a row from a report, or just describe one concrete thing in your domain."*

After parsing an example:

> *"From your example, I'm reading the following elementary facts. Let me verbalize each one — please confirm or correct:*
> - *'John was born in Australia.' Is this an atomic fact in your domain?*
> - *'John has age 35.' Is this an atomic fact?*
> - *'Australia is in continent Oceania.' Is this an atomic fact?*"

For reference-scheme elicitation:

> *"You mentioned 'Person'. How is each Person identified in your domain — by a name, an employee number, a national ID, or something else?"*

If the user defaults to attribute language ("the Person's name"):

> *"Got it — is 'name' how each Person is identified (so the Person is the name), or is 'name' a property that Persons have? If the latter, what identifies a Person?"*

### Edge cases

- **User gives a single example and stops.** Ask for one more: "Can you give me one or two more examples? CSDP works by populating fact types with several sample instances — even 3–5 helps validate the structure."
- **User describes in ER terms ("the Customer table has columns name, email...").** Translate gently: "those would be roles or values in ORM. Let me verbalize: 'Customer has name'. 'Customer has email'. Are these atomic facts?"
- **User uses compound predicates.** Break them apart: "You said 'each Order has a status and a customer'. In ORM we'd treat these as separate elementary facts. Let me verbalize: 'Each Order has a status'. 'Each Order is placed by a Customer'. Confirm both?"
- **User can't decide on a reference scheme.** Stay tentative: "Let's mark this as `popular` for now — we can revisit if we discover a separate identifier later in CSDP."

### YAML output shape

```yaml
fact_types:
  - id: person_born_in_country
    reading: "{Person} was born in {Country}"
    roles: [{ object_type: person, role_name: person }, { object_type: country, role_name: country }]
    sample_population:
      - { person: "John", country: "Australia" }
      - { person: "Mary", country: "Greece" }
    provenance:
      csdp_step: 1
      dialogue_turn: 4
      user_quote: "John was born in Australia, Mary was born in Greece."
```

Sample populations capture exactly what the user said (5–20 facts typical) so Step 2's population check is concrete.

## Step 2 — Draw fact types + population check

**Input:** confirmed elementary facts from Step 1.

**Output:** structurally-valid `object_types` and `fact_types` lists in the YAML.

**No user interaction.** Claude processes Step 1's output and emits the YAML structure.

### Mechanics

For each elementary fact confirmed at Step 1:
1. Identify object types (entity types and value types) appearing in the fact.
2. Identify the predicate (the "reading template").
3. Group facts by predicate to form fact types.
4. Each fact type gets `roles[]` derived from the predicate; the sample population is the set of user-confirmed elementary facts.

### Population check

Re-verbalize the model using the sample populations:

> *"Based on Step 1, your model has these fact types and sample populations:*
> - *Person born in Country: {John in Australia, Mary in Greece, Carlos in Spain}*
> - *Person has age Age: {John 35, Mary 28, Carlos 42}*
>
> *In Step 4 we'll add uniqueness constraints. Before that — does each population look right? Any duplicates that shouldn't be there, any facts I'm missing?"*

This is preparation for Step 4 — it surfaces over-decomposition or missed facts before constraints get applied.

## Step 3 — Combine entity types; note arithmetic derivations

**Input:** Step 2 output.

**Output:** merged entity types where appropriate; derived facts marked with `derivation: derived`.

### Mechanics

Walk the object_types list looking for:
- **Synonym entity types.** "Customer" and "Buyer" might be the same kind of thing. Ask: "Are 'Customer' and 'Buyer' the same kind of thing in your domain, or do they play different roles?"
- **Arithmetic derivations.** Facts computed from others. Ask: "You mentioned 'total = quantity × unit_price'. Should 'total' be a stored fact, or computed from the others?"
- **Logical derivations.** Step 5 catches these too, but flag candidates here.

### YAML changes

Merging entity types:
- One entity type is kept, the other removed.
- Fact types referencing the removed type are updated to reference the kept type.

Derived facts:
```yaml
fact_types:
  - id: order_total
    reading: "{Order} has total {Money}"
    derivation: derived
    derivation_rule: "For each Order, total = sum(line.quantity * line.unit_price for line in order.lines)."
    storage: computed
    provenance:
      csdp_step: 3
      dialogue_turn: 14
```

### Edge cases

- **User refuses to merge two seemingly-identical types.** Trust them — they know the domain. Add a `provenance.user_note: "user kept distinct"` annotation.
- **Derivation rule references object types not yet in the model.** Either elicit those object types now or flag the rule as `derivation_rule_pending` and revisit at Step 7.

## Step 4 — Uniqueness constraints + arity check

**Input:** Step 3 output.

**Output:** YAML constraints with `source: explicit, status: confirmed` where the user explicitly states uniqueness, or `source: sample, status: proposed` where it's only visible in the sample population.

### Mechanics

For each fact type, present the population check:

> *"In your sample data for 'Person was born in Country':*
> - *John → Australia*
> - *Mary → Greece*
> - *Carlos → Spain*
>
> *Each Person was born in exactly one Country. Is that always true in your domain, or could a Person have been born in multiple Countries?"*

The user confirms uniqueness on `person` (the typical "1:n" pattern) or pushes back (e.g., "yes, but technically a dual-citizen has two birth countries"). Confirmed → `source: explicit, status: confirmed`. Sample-only (user says "yes, that holds in the sample but I'm not sure in general") → `source: sample, status: proposed`.

For each role pair, also ask: "Can the same combination appear twice?" (covers the m:n and n:1 patterns).

### Arity check

For each fact type, ask the user:
- Are there roles missing? ("Should 'born in' also record when the birth happened?")
- Are there roles that don't belong? ("Is 'currency' really part of 'is paid by'?")

### YAML output shape

```yaml
fact_types:
  - id: person_born_in_country
    reading: "{Person} was born in {Country}"
    roles: [{ object_type: person, role_name: person }, { object_type: country, role_name: country }]
    constraints:
      - type: uniqueness
        roles: [person]
        source: explicit
        status: confirmed
        rationale: "User stated: 'each person was born in exactly one country'."
        provenance:
          csdp_step: 4
          dialogue_turn: 18
          user_quote: "Each person was born in exactly one country."
```

## Step 5 — Mandatory role constraints + logical derivations

**Input:** Step 4 output.

**Output:** mandatory constraints for confirmed-required roles; logical-derivation flags.

### Mechanics

For each role, ask the user:

> *"Is it required that every {ObjectType} plays this role? In your domain, can a {ObjectType} exist without {predicate}?"*

Examples:
- "Is it required that every Person has a Country of birth?"
- "Is it required that every Order has at least one OrderItem?"

The user confirms (mandatory) or denies (optional). Confirmed → `source: explicit, status: confirmed`.

### Logical derivations

If the user notes that one fact implies another ("if a Person is an Adult then their age is at least 18"), flag this for Step 7c as a candidate logical-derivation rule. CSDP doesn't formalize logical derivations until Step 7; here we just collect candidates.

### YAML output shape

```yaml
fact_types:
  - id: person_born_in_country
    constraints:
      - type: mandatory
        role: person
        source: explicit
        status: confirmed
        rationale: "User stated: 'every person has a birth country'."
        provenance:
          csdp_step: 5
          dialogue_turn: 21
          user_quote: "Every person has a birth country."
```

## Step 6 — Value, set-comparison, ring, and subtyping constraints

**Input:** Steps 1–5 output.

**Output:** additional constraints with `source: common-sense | llm-inferred, status: proposed`. Substeps mirror the schema skill's Step 6.

### 6a — Library lookup

For each object type, value type, and binary fact type, match against the typed library in [`../../rai-orm-from-schema/references/constraint-inference.md`](../../rai-orm-from-schema/references/constraint-inference.md). Examples:
- Object type `Money`/`Age`/`Count`/`Duration` → non-negative range.
- Object type `Date` → must-be-valid-date.
- Pair `*_started_at` and `*_ended_at` on same entity → value-comparison `start <= end`.
- Value type with name matching `email` → uniqueness + format constraints.

Each emitted with `source: common-sense, status: proposed`, with `provenance.library_entry` pointing to the slug id and `rationale` restating the assumption.

### 6b — Ring-pattern matching

For every binary fact type with both roles on the same object type (or supertype), match the reading and role names against the ring library:
- `parent of` / role names `parent` & `child` → `acyclic` + `asymmetric` + `irreflexive`
- `reports to` / role names `manager` & `employee` → `acyclic` + `asymmetric` + `irreflexive`
- `married to` (under monogamy) → `symmetric` + `irreflexive` + functional UC

Multi-variant policy: each matched pattern emits multiple `ring` entries (one per variant) per the schema skill's policy.

### 6c — LLM tier

For object types/relationships not covered by 6a or 6b, ask the LLM to propose constraints from world knowledge. Every LLM-proposed constraint MUST carry `provenance.rationale_world_fact` (mandatory; rejected at emission without it).

Bounded scope (v0.1): LLM tier proposes only value (range/enum), ring (when 6b didn't fire), subset/exclusion (cross-fact-type), mandatory/mandatory-disjunctive, and frequency.

### 6d — LLM spot-check (Guided mode only, opt-in)

Mechanics mirror the schema skill's Step 6d. Surface ONLY Step 6c LLM-tier proposals — library (6a) and ring (6b) proposals are NOT surfaced here (they're reviewed in context at Step 7b). The user can:
- Mark obvious hallucinations as `rejected` immediately (move to `rejected_proposals`)
- Reject the whole batch and defer review to Step 7b
- Defer everything to Step 7b (skip the spot-check entirely)

In One-shot mode, 6d is skipped.

### Subtype check (interactive, throughout Step 6)

Subtypes are the place new users most often make mistakes. The Halpin criterion: **a subtype is justified only when its instances play roles the supertype doesn't.**

When the user (or the LLM) proposes a subtype, ask:

> *"You're suggesting {Subtype} as a kind of {Supertype}. In your domain, does a {Subtype} play any roles that a {Supertype} doesn't? For example: 'every {Subtype} has X' where X isn't true of every {Supertype}?"*

If the user says "yes, every Manager has a budget assigned to them, and not every Employee does" → that's a real role difference → subtype justified.

If the user says "Managers earn more and have a title" → those are values/properties, not roles → push back: "Those sound like properties of Employee, not a separate subtype. Would you keep Manager as a subtype, or fold those into Employee with a 'manager' flag?"

See [`dialogue-patterns.md`](dialogue-patterns.md) for the full subtype-rescue dialogue.

### 6e — Verbalize Step 6 proposals

Render all surviving Step 6 proposals using the templates in [`verbalization-patterns.md`](verbalization-patterns.md). The verbalization feeds Step 7's whole-model presentation.

## Step 7 — Final review and modality labelling

**Input:** Steps 1–6 output.

**Output:** finalized YAML — proposals confirmed/rejected, user-supplied constraints added, modality labels applied.

### Substeps (six, matching schema-skill Step 9)

> **7a.** User reviews the whole-model verbalization (every fact type + every constraint + every proposed inference).
>
> **7b.** User confirms / rejects / escalates each proposed constraint from Steps 1–6. Library-tier and ring-pattern proposals are reviewed in context here (they weren't surfaced at 6d). Batched when ≥5 proposals in a category.
>
> **7c.** User resolves flagged ambiguities raised through CSDP (over-decomposed fact types, weird subtypes, redundant entity types, attribute-vs-role confusion).
>
> **7d.** User adds constraints they know but the system missed. Free-form natural-language input; Claude paraphrases back as structured form for confirmation. Examples: "each country has exactly one capital", "each project has exactly one project manager in our company".
>
> **7e.** User labels every confirmed non-explicit constraint as `alethic` or `deontic`. Defaults to `alethic` if not specified. Modality matters: alethic constraints become `model.require()` in PyRel; deontic constraints become `# DEONTIC NOTE:` comments.
>
> **7f.** Commit confirmed + user-supplied to YAML. Rejected proposals go to `rejected_proposals` so future runs on the same domain don't re-propose them.

### Mode behavior

| Substep | Guided mode | One-shot mode |
|---|---|---|
| 7a | User reads verbalization | Skipped (verbalization still emitted to the file) |
| 7b | Interactive (auto-batch ≥ 5) | Library-tier auto-confirms; LLM-tier and sample stay `proposed` |
| 7c | Interactive | Flagged ambiguities remain in YAML for the user to resolve post-hoc |
| 7d | Interactive | Skipped |
| 7e | Interactive | Explicit-source → `alethic`; everything else inherits `alethic` + `# REVIEW MODALITY` flag |
| 7f | Standard write | Standard write |

## Step 8 — Translate to PyRel

**Input:** finalized YAML from Step 7f.

**Output:** `model.py` containing the PyRel translation.

**Mechanics:** apply the four-tier rules from [`../../rai-orm-from-schema/references/orm-to-pyrel.md`](../../rai-orm-from-schema/references/orm-to-pyrel.md) to each YAML entry. Identical to the schema skill's Step 10.

**Output structure:**
1. Header comment with strict-mode reminder.
2. Imports from `relationalai.semantics`.
3. `model = Model(...)` declaration.
4. Concept declarations.
5. Property/Relationship declarations.
6. Subtype `define...where` rules.
7. `model.require()` calls (verbose-tier constraints).
8. `# DEONTIC NOTE:` comments for deontic constraints.
9. `# REVIEW MODALITY` flags carried over from One-shot mode.

**No user interaction.**

## Inputs / outputs at a glance

| Step | Input | Output | User interaction? |
|---|---|---|---|
| 0 | — | mode: `guided` \| `one-shot` | Guided: yes |
| 1 | description + examples | confirmed elementary facts | yes (heart of CSDP) |
| 2 | Step 1 | YAML object_types + fact_types | no |
| 3 | Step 2 | merged entity types; derivation flags | yes |
| 4 | Step 3 | uniqueness constraints | yes |
| 5 | Step 4 | mandatory constraints | yes |
| 6 | Step 5 | proposed constraints (common-sense / llm-inferred) + subtype decisions | yes (subtype check + 6d spot-check) |
| 7 | Step 6 | finalized YAML | Guided: yes (six substeps) |
| 8 | finalized YAML | model.py | no |

## Risks and discipline

| Risk | Defense |
|---|---|
| Verbalizing a fact the user hasn't confirmed | Step 1 protocol: every verbalization is a question, never an assertion |
| Letting users describe in ER terms | Translate gently to Halpin terms; reread their intent in fact-based language |
| Premature subtyping | Subtype check at Step 6 uses Halpin's role-based criterion |
| Halpin samples are too small to prove constraints | `sample`-source constraints always stay `proposed` — never auto-confirm |
| LLM hallucination at the 6c tier | `rationale_world_fact` discipline; 6d opt-in spot-check; Step 7b final review |
| Dialogue quality varies | Sparse users get thin models. Acknowledge this; ask increasingly pointed questions; stop when answers run out. |

## Open questions deferred to v1.5

1. **Multi-language CSDP.** Halpin's CNL extends to other languages; v0.1 is English only.
2. **CSDP step persistence across sessions.** Saving partial progress (Step 4 reached, but Step 5 not yet) is informally supported by checkpointing the YAML; formal session-state lives in `source.session_id` but isn't required to round-trip.
3. **Multi-user CSDP.** Two stakeholders in dialogue with the skill simultaneously; v0.1 assumes one domain expert.
