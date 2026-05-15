---
name: rai-orm-from-text
description: Designs an ORM 2 conceptual model (YAML with full constraint provenance — explicit / sample / common-sense / llm-inferred / user-supplied, alethic vs deontic) from a natural-language domain description by walking the user through Halpin's Conceptual Schema Design Procedure (CSDP), then translates to PyRel. Produces a stakeholder-reviewable intermediate artifact. Use for greenfield modeling when no schema or data exists yet — not for schema-driven model recovery (rai-orm-from-schema), enriching/reviewing an already-loaded PyRel model (rai-ontology-design), or PyRel syntax reference (rai-pyrel-coding).
---

# Text-to-ORM Design
<!-- v1-SENSITIVE -->

## Summary

**What:** Conceptual Schema Design Procedure (CSDP) — a 7+1-step dialogue-driven workflow that takes a natural-language domain description (with optional sample facts and user dialogue), builds an ORM 2 conceptual model with full constraint provenance, verbalizes it for stakeholder review, and translates the confirmed model to PyRel. Output is `model.orm.yaml` + `model.verbalization.txt` + `model.py`.

CSDP is Halpin's canonical forward-design methodology. Unlike the schema-side Schema Recovery Procedure (SRP), CSDP elicits the model in conversation with a domain expert — the user provides examples and answers questions, the skill verbalizes elementary facts back to the user for confirmation, and the model emerges step by step.

**When to use:**
- Greenfield ORM design when no relational schema exists yet (requirements documents, domain descriptions, conversations with stakeholders)
- Building a fact-based conceptual model from elementary facts and sample populations
- Producing a stakeholder-reviewable intermediate artifact (the YAML) where a domain expert validates the model by reading verbalized facts rather than diagrams
- Designing models grounded in Halpin's ORM 2 vocabulary — reference modes, fact types, role names, objectification, modality (alethic vs deontic)
- Building a model that downstream tools (PyRel, NORMA, ConQuer queries) can consume

**When NOT to use:**
- An existing relational schema is the starting point — see `rai-orm-from-schema` (the schema-side companion skill)
- Enriching or reviewing a PyRel model that already loads and queries — see `rai-ontology-design`
- PyRel syntax reference (Concept, Property, Relationship, model.require, f-string patterns) — see `rai-pyrel-coding`
- Querying, graph analysis, optimization formulation — see the respective reasoner skills (`rai-querying`, `rai-graph-analysis`, `rai-prescriptive-*`)

**Overview:**
0. Open with mode choice — Guided (full dialogue, recommended) or One-shot (user provides a rich description; skill drafts in one pass)
1. Transform familiar examples into elementary facts and verbalize back for confirmation
2. Draw the fact types and apply a population check using the user's sample facts
3. Check for entity types that should be combined; note arithmetic derivations
4. Add uniqueness constraints and check the arity of each fact type
5. Add mandatory role constraints and check for logical derivations
6. Add value, set-comparison, ring, and subtyping constraints (typed library + LLM tier with opt-in spot-check)
7. Add other constraints, label modality (alethic vs deontic), commit to YAML
8. Translate the finalized YAML to PyRel via four-tier rules

## Quick Reference

| Artifact | Contents | Audience |
|---|---|---|
| `model.orm.yaml` | The designed ORM 2 model with every constraint carrying `source` + `status` + `modality` + `provenance` (dialogue turn + CSDP step). Single source of truth. | Reviewers (technical and non-technical) |
| `model.verbalization.txt` | Halpin-style controlled natural language (CNL) rendering — readable without PyRel knowledge. | Stakeholders |
| `model.py` | PyRel translation of the confirmed YAML. Includes `# DEONTIC NOTE:` for "should" rules and `# REVIEW MODALITY` markers when modality is defaulted. | Engineers |

**Five-source provenance taxonomy** — every constraint carries one:

| `source` | Meaning in text-first context | Default `status` |
|---|---|---|
| `explicit` | Stated by the user in conversation ("each person was born in exactly one country") | `confirmed` (auto) |
| `sample` | Inferred from sample populations the user provided in Step 1 | `proposed` (Halpin samples are typically small — 5–20 facts; not enough to auto-confirm) |
| `common-sense` | Typed-library lookup or ring-pattern matcher | `proposed` |
| `llm-inferred` | LLM proposal from world knowledge for novel concepts | `proposed` |
| `user-supplied` | Added at Step 7d when the user notices a missing constraint | `confirmed` (auto) |

**Core principle: propose, never assert.** The user explicitly confirms every non-explicit constraint. Verbalization is presented as a question ("is this right?"), never as an assertion.

**Halpin posture (critical):** The skill teaches CSDP as Halpin meant it — atomic facts, no attributes, populate-then-constrain. Slipping into ER vocabulary (table/column/relationship type) leaks ER mental models. Use Halpin's terms: fact type, role, object type, reference scheme, objectification. See [`references/halpin-posture.md`](references/halpin-posture.md).

## Inputs and Outputs

**Inputs (any combination):**

| Input shape | Notes |
|---|---|
| **Natural-language domain description** | Primary case. The user describes the domain. May arrive in one prompt or unfold conversationally. |
| **Sample data** (small) | Forms, reports, spreadsheets, CSV exports. Used illustratively (Halpin's CSDP populates fact types with a handful of sample fact instances, not thousands). |
| **Existing artifacts** | Glossaries, requirements docs, business-rule catalogs, sample queries. |
| **Conversation** | The user answers Claude's questions throughout CSDP. The dialogue itself is part of the input. |

**Outputs (always emitted as the triple):**
- `model.orm.yaml` — full canonical YAML; format spec in [`../rai-orm-from-schema/references/representation-format.md`](../rai-orm-from-schema/references/representation-format.md) (shared until `rai-orm-core/` promotion).
- `model.verbalization.txt` — CNL rendering; patterns in [`references/verbalization-patterns.md`](references/verbalization-patterns.md) plus shared base in the schema skill's references.
- `model.py` — PyRel translation; rules in [`../rai-orm-from-schema/references/orm-to-pyrel.md`](../rai-orm-from-schema/references/orm-to-pyrel.md).

## Instructions

**Required dependencies:** [`rai-pyrel-coding`](../rai-pyrel-coding/SKILL.md) for PyRel idioms used at Step 8. The companion schema skill [`rai-orm-from-schema`](../rai-orm-from-schema/SKILL.md) shares the YAML format spec, constraint reference, antipattern catalog, verbalization patterns, and ORM→PyRel translation — those references are loaded from there until they're promoted to `skills/rai-orm-core/` (TODO.md item #5).

**Halpin posture:** read [`references/halpin-posture.md`](references/halpin-posture.md) before running CSDP for the first time. The procedure is mechanical; the posture isn't.

**Working principle:** propose, never assert. Every constraint that isn't directly stated by the user is a *candidate* validated in conversation.

### Step 0 — Interaction-mode opener

Before eliciting examples, ask the user:

> *I can run CSDP in two modes:*
> - *Guided — we walk through Halpin's seven steps in conversation. I ask for examples, verbalize facts back to you, propose constraints, and we commit step by step. Best for high-value or unfamiliar domains.*
> - *One-shot — you give me a detailed domain description up front; I produce a draft model in one pass; you review by editing the YAML. Caveat: text-first One-shot is significantly more degraded than schema-first One-shot, because there's no DDL to anchor structure. Best for fast retargeting when you already have a rich description.*
> *Which would you prefer?*

Default to **Guided** if no answer. Record the choice in `source.mode` of the YAML.

In Guided mode the SRP pauses at three pivot points (Step 0 itself, Step 6d's LLM spot-check, Step 7's six substeps). In One-shot mode those pauses collapse — library-tier proposals auto-confirm; LLM-tier proposals stay `proposed` for the user to review by editing the YAML.

### Step 1 — Elementary facts and verbalization check

Get the user to provide concrete examples. Ask:

> *"Show me a typical case. Walk me through what a real instance looks like — a sample form, a row from a report, or just describe one concrete thing in your domain."*

For each example, verbalize it as **elementary facts** (atomic, irreducible, no compound predicates). Present each fact back to the user with explicit phrasing:

> *"From your example, I'm reading: 'John was born in Australia.' Is that an atomic fact in your domain, or is there more going on?"*

The user confirms, refines, or rejects each fact. Critical: never proceed past a fact the user hasn't explicitly confirmed.

Reference-scheme elicitation lives here too. For each entity type that emerges, ask:

> *"How is each {EntityType} identified — by name, by number, by a code?"*

Avoid attribute-thinking. The user might say "by the customer's name" — push to make this a separate reference-scheme decision: is the name a popular reference mode (e.g., `Customer(.name)`), or do customers have their own identifier?

See [`references/dialogue-patterns.md`](references/dialogue-patterns.md) for question templates that elicit examples, reference schemes, and push back on attribute thinking.

### Step 2 — Draw the fact types and apply a population check

From the elementary facts confirmed at Step 1, identify object types and predicates. Populate each fact type with the user's sample fact instances to validate the structure.

Output: `object_types` and `fact_types` sections of the YAML, populated with provenance pointing back to dialogue turns:

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

The `sample_population` lets the user double-check the fact-type shape against their examples.

### Step 3 — Combine entity types; note arithmetic derivations

Walk the model looking for entity types that should be merged (often surface as separate names for the same kind of thing) and facts that are computed from others.

Prompts:
- *"You mentioned 'Customer' and 'Buyer'. Are these the same kind of thing, or do they play different roles?"*
- *"Your example shows 'total = quantity × unit_price'. Should 'total' be a stored fact, or computed from the others?"*

Computed facts get marked with `derivation: derived` and `derivation_rule:` capturing the formula.

### Step 4 — Uniqueness constraints + check arity

For each fact type, ask: which combinations of roles can repeat, and which are unique? Verbalize the population check:

> *"In your example data, each Person was born in exactly one Country — never two. Is that always true, or could a Person have been born in multiple Countries?"*

Confirmed uniqueness becomes a `uniqueness` constraint. Verify arity — is the fact type over- or under-decomposed?

### Step 5 — Mandatory role constraints + logical derivations

For each role, ask: must every instance of the object type play that role at least once?

> *"Is it required that every Person has a Country of birth, or could a Person exist in your model without one?"*

Confirmed mandatory → `mandatory` constraint. Logical derivations (one fact implies another) get flagged here too.

### Step 6 — Value, set-comparison, ring, and subtyping constraints

This is where the constraint-inference layer applies. Substeps mirror the schema skill's Step 6:

> **6a.** Typed library lookup keyed on object-type names and primitives. Library lives in [`../rai-orm-from-schema/references/constraint-inference.md`](../rai-orm-from-schema/references/constraint-inference.md). Library hit examples: `Money` → non-negative range; `Date` → valid-date; `email` → uniqueness + format; pair `start_date`/`end_date` → `start <= end`. Each emitted with `source: common-sense, status: proposed`, surfacing the library entry id in provenance.
>
> **6b.** Ring-pattern matching on self-referential binary fact types. The same ring library used by the schema skill applies (`parent-of` → acyclic + asymmetric + irreflexive; `married-to` → symmetric + irreflexive; `reports-to` → acyclic + asymmetric + irreflexive). Multi-variant policy: one `ring` entry per variant.
>
> **6c.** LLM tier — for object types/relationships the library doesn't cover, ask the LLM to propose constraints from world knowledge. Each proposal must include `provenance.rationale_world_fact`. Without it, the proposal is rejected at emission.
>
> **6d.** **LLM spot-check** (Guided mode only; opt-in). Surface Step 6c LLM-tier proposals to the user with their rationales — not library or ring proposals (those are deterministic; the user reviews them at Step 7b in context). The user can mark obvious hallucinations as `rejected` immediately so they don't pollute Step 7's whole-model verbalization. The user can also defer all decisions to Step 7b.
>
> **6e.** Verbalize all surviving Step 6 proposals back to the user as part of preparation for the whole-model verbalization in Step 7.

Subtyping: ask the user only when their examples suggest distinct kinds with distinct roles. Push back on premature subtyping (a common new-user pitfall — see Caveat #4 in `references/dialogue-patterns.md`). A subtype is justified only when its instances play roles the supertype doesn't.

### Step 7 — Final review and modality labelling

Six substeps (mirroring the schema skill's Step 9):

> **7a.** User reviews the whole-model verbalization (the Halpin-style CNL rendering of every fact type + every constraint + every proposed inference).
> **7b.** User confirms / rejects / escalates each proposed constraint accumulated through Steps 1–6. Library-tier and ring-pattern proposals are reviewed in context here (they weren't surfaced at 6d).
> **7c.** User addresses any flagged ambiguities (over-decomposition, weird subtypes, awkward readings).
> **7d.** User adds any constraints they know but the system missed (`source: user-supplied`, auto `status: confirmed`). Free-form natural-language input; Claude paraphrases back to the structured form for confirmation.
> **7e.** User labels every confirmed non-explicit constraint as `alethic` (must — a domain rule) or `deontic` (should — a policy or norm). Defaults to `alethic` if not specified.
> **7f.** Commit confirmed + user-supplied to YAML. Rejected proposals go to `rejected_proposals` so future runs on the same domain don't re-propose them.

In One-shot mode, 7a–7e collapse: library-tier auto-confirms; LLM-tier stays `proposed`; antipattern defaults applied silently; explicit-source defaults to alethic; everything else gets a `# REVIEW MODALITY` flag.

### Step 8 — Translate to PyRel

Apply the four-tier rules from [`../rai-orm-from-schema/references/orm-to-pyrel.md`](../rai-orm-from-schema/references/orm-to-pyrel.md) to the finalized YAML. Output `model.py` with the canonical header, imports, Concept declarations, Property/Relationship declarations, subtype rules, `model.require()` calls for verbose-tier constraints, and `# DEONTIC NOTE:` comments for deontic constraints.

## Constraint Provenance and Validation Flow

Same structure as the schema skill. Every constraint carries:

```yaml
- type: <constraint-type>
  # constraint-specific fields …
  source: explicit | sample | common-sense | llm-inferred | user-supplied   # set once
  status: proposed | confirmed | rejected                                    # evolves through review
  modality: alethic | deontic                                                # set at Step 7e; default alethic
  rationale: "…"                                                             # required for non-explicit sources
  provenance:
    csdp_step: <N>                                                           # text-first specific
    dialogue_turn: <N>                                                       # text-first specific
    user_quote: "…"                                                          # the user's actual words (when applicable)
    # … plus source-specific fields (library_entry, llm_prompt_id, etc.)
```

The `csdp_step + dialogue_turn + user_quote` triple makes the YAML auditable in **dialogue terms** instead of column-and-table terms. A reviewer can trace each constraint back to where the user said something specific.

**Rules:**
- `source` is set once. Never changes.
- `status` evolves: `proposed → confirmed` (Step 7b accept) or `proposed → rejected` (Step 7b explicit reject; archived in `rejected_proposals`).
- `modality` defaults to `alethic`; deontic must be explicit (Step 7e). PyRel emits deontic as `# DEONTIC NOTE:` comments.
- `rationale` required for `source ∈ {sample, common-sense, llm-inferred, user-supplied}`.

## Halpin Posture and Dialogue Patterns

The skill teaches Halpin's *posture*, not just his *procedure*. Key dialogue moves:

- **Always verbalize as a question.** Never assert "John was born in Australia"; ask "is 'John was born in Australia' an atomic fact in your domain?"
- **Elicit reference schemes explicitly.** New users default to attribute thinking ("the customer's name is…"). Push: "is `name` how a Customer is identified, or do Customers have a separate identifier like an ID number?"
- **Push back on premature subtyping.** A subtype is justified only when its instances play roles the supertype doesn't. If "Manager" only has the same roles as "Employee" plus a few extra attributes, those are properties of Employee, not a Manager subtype.
- **Atomic facts only.** Don't accept compound facts. "Each Order has a status and a date and a customer" → break into three elementary facts.
- **Halpin terminology, not ER.** Use *fact type*, *role*, *object type*, *reference scheme*, *objectification*. Avoid *table*, *column*, *relationship type*, *attribute*.

Full vocabulary and stuck-conversation rescues in [`references/halpin-posture.md`](references/halpin-posture.md) and [`references/dialogue-patterns.md`](references/dialogue-patterns.md).

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Verbalizing a fact the user hasn't confirmed, then proceeding as if it were confirmed | Forgetting the "propose, never assert" principle | Phrase every Step-1 verbalization as a question. Wait for explicit user confirmation. |
| Asserting an inferred constraint as `confirmed` without Step 7b review | Skipping the confirmation flow in Guided mode, or assuming One-shot auto-confirms LLM-tier | LLM-tier proposals stay `proposed` always until user review. Library-tier auto-confirms only in One-shot mode. |
| Letting users describe in ER terms ("tables", "columns") without redirecting | Easier to follow the user's vocabulary than to push back | Translate gently: "you said 'columns' — in ORM we'd call those the roles or the values. Let me re-verbalize..." Reread the user's intent in Halpin terms. |
| Accepting a subtype based on attribute differences only | Common new-user mistake: confusing roles with attributes | At Step 6 subtype check, ask: "Does {Subtype} play any roles {Supertype} doesn't?" If no → not a subtype; the differences are attributes/properties. |
| Auto-confirming sample-derived constraints (Halpin samples are tiny) | Treating text-first samples like schema-first sample-probe results | Text-first samples always stay `proposed` (typically 5–20 facts; not enough to auto-confirm). User explicitly confirms at Step 7b. |
| Using Python's `and`/`or`/`not` in PyRel `model.require()` | Forgetting PyRel's boolean operator rules | Use `&` / `\|` / `model.not_()`. Triggers compile-time `[Invalid operator] Cannot use python's 'bool check'`. |
| Translating a deontic constraint to `model.require()` | Ignoring the `modality` field | Deontic emits as `# DEONTIC NOTE:` comments. `model.require` is alethic-only. |
| Asking the user to volunteer constraints at Step 6c (before they've seen the whole model) | Conflating Step 6c's LLM tier with Step 7d's user-supplied path | Step 7d is when the user adds constraints. At Step 6 they only confirm/reject what the skill proposes. |

## Examples

| Pattern | Files |
|---|---|
| Canonical small build covering elementary facts, reference schemes, uniqueness, mandatory, value constraints, and PyRel translation | [`examples/movie_catalog.dialogue.md`](examples/movie_catalog.dialogue.md) + [`.orm.yaml`](examples/movie_catalog.orm.yaml) + [`.py`](examples/movie_catalog.py) |
| Subtyping done right vs wrong — push-back on premature subtyping | [`examples/library_with_subtypes.dialogue.md`](examples/library_with_subtypes.dialogue.md) + [`.orm.yaml`](examples/library_with_subtypes.orm.yaml) |
| When to objectify a fact type | [`examples/objectification_in_enrollment.dialogue.md`](examples/objectification_in_enrollment.dialogue.md) + [`.orm.yaml`](examples/objectification_in_enrollment.orm.yaml) |
| Reference-scheme elicitation — the most-skipped CSDP step | [`examples/reference_scheme_elicitation.dialogue.md`](examples/reference_scheme_elicitation.dialogue.md) + [`.orm.yaml`](examples/reference_scheme_elicitation.orm.yaml) |

## Reference files

| File | When to load |
|---|---|
| [`references/csdp-workflow.md`](references/csdp-workflow.md) | Detailed mechanics for any CSDP step — substeps, prompts, edge cases. Load when a step's summary above isn't enough. |
| [`references/dialogue-patterns.md`](references/dialogue-patterns.md) | Conversational patterns — eliciting examples, asking for reference schemes, handling thin answers, pushing back on premature subtyping. Load at Steps 1 / 3 / 6 (subtype check) / 7d. |
| [`references/halpin-posture.md`](references/halpin-posture.md) | The underlying mindset — atomic facts, no attributes, populate-then-constrain. Load before running CSDP for the first time, and when the user defaults to ER vocabulary. |
| [`../rai-orm-from-schema/references/representation-format.md`](../rai-orm-from-schema/references/representation-format.md) | Shared YAML schema spec (will move to `skills/rai-orm-core/` in v1.5). |
| [`../rai-orm-from-schema/references/constraint-reference.md`](../rai-orm-from-schema/references/constraint-reference.md) | Shared per-constraint vocabulary (13 ORM 2 constraint types). |
| [`../rai-orm-from-schema/references/constraint-inference.md`](../rai-orm-from-schema/references/constraint-inference.md) | Shared typed library + ring matcher + LLM contract. |
| [`references/verbalization-patterns.md`](references/verbalization-patterns.md) | Text-first verbalization additions: dialogue-turn references, sample-population rendering, user-quote citation. Builds on the schema skill's [`verbalization-patterns.md`](../rai-orm-from-schema/references/verbalization-patterns.md). |
| [`../rai-orm-from-schema/references/orm-to-pyrel.md`](../rai-orm-from-schema/references/orm-to-pyrel.md) | Shared four-tier translation rules. Load at Step 8. |
