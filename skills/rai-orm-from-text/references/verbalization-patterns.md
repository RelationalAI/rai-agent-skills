# Verbalization Patterns — Text-First Additions

Text-first additions on top of the shared verbalization patterns in [`../../rai-orm-from-schema/references/verbalization-patterns.md`](../../rai-orm-from-schema/references/verbalization-patterns.md). The base patterns (object types, fact types, constraints, provenance prefixes, antipattern call-outs) are identical between the two skills; this file documents three text-first-specific additions:

1. **Dialogue-turn references** in provenance prefixes
2. **Sample-population rendering** within fact type paragraphs
3. **User-quote citation** for `source: explicit | user-supplied` constraints

Load at CSDP Steps 6e (verbalize proposals) and 7a (whole-model verbalization).

## 1. Dialogue-turn references

Every constraint in a text-first YAML carries `provenance.csdp_step` and `provenance.dialogue_turn`. The verbalization can render these inline so the reviewer can trace each claim back to where it came from in the conversation.

### Patterns

Schema-side prefix (for comparison):

> *[from common-sense library, proposed] Parenthood is acyclic.*

Text-first prefix:

> *[from common-sense library, proposed; CSDP step 6, turn 18] Parenthood is acyclic.*

For explicit constraints from user statements:

> *[from user statement, confirmed; turn 4] Each Person was born in exactly one Country.*

For user-supplied (Step 7d) constraints:

> *[user-supplied at Step 7d, turn 42] Each Project has exactly one Project Manager.*

### When to include dialogue-turn references

- Always in the **canonical** verbalization for review (Step 7a output).
- Optionally elided in a **stakeholder-summary** verbalization if the audience doesn't need audit trails.

The verbalization renderer reads a `style: audit | summary` field from the run config (default `audit`). In `summary` style, drop the turn references.

## 2. Sample-population rendering

Text-first fact types carry `sample_population:` arrays — the user's actual examples from Step 1. Rendering them in the verbalization makes the population check visible.

### Pattern (canonical, in `audit` style)

```
Person was born in Country.
Each Person was born in exactly one Country. [from user statement, confirmed; turn 4]

Sample facts (user-provided at Step 1):
  John was born in Australia.
  Mary was born in Greece.
  Carlos was born in Spain.
```

### Pattern (summary style)

```
Person was born in Country.
Each Person was born in exactly one Country.

Sample facts: 3 examples confirmed (John/Australia, Mary/Greece, Carlos/Spain).
```

### When to expand vs compress

- **Expand fully** when sample size ≤ 5. The user can scan all examples.
- **Compress** when sample size > 5. Show first 3 + count. Available in full in the YAML's `sample_population`.

### Verbalization rules

- Sample facts use the fact type's `reading`, with each role filled in by the sample value.
- The `Person` value type rendering: if it's a primitive, use the value directly. If it's an entity, use the entity's reference-scheme-based identifier (e.g., a Customer's name if reference mode is `popular` with `value_type: customer_name`).
- Quote-style: single quotes around string values is enough; integers/dates are bare.

## 3. User-quote citation

For constraints with `source: explicit | user-supplied`, the YAML carries `provenance.user_quote` — the user's actual words. The verbalization can cite the quote inline.

### Pattern

> *[from user statement at turn 4] Each Person was born in exactly one Country. (User said: "Each person has one country of birth, no exceptions.")*

The quote is in parentheses to keep the constraint sentence parseable; the trace makes the verbalization auditable in conversation terms.

### When to include the quote

- Always for **`source: explicit`** constraints — the quote is the *evidence* for the constraint.
- Always for **`source: user-supplied`** constraints — the user added the rule, the quote captures their original phrasing.
- Optionally for **`source: common-sense | llm-inferred` constraints that the user *confirmed* at Step 7b** — the confirmation might have a user quote attached (e.g., "yes, that's right" or "yes but only in retail").

### Length cap

If the user quote is > 200 characters, truncate with `…` and link to the full quote in the YAML:

> *[from user statement at turn 12] Each Order has at most 50 line items. (User said: "OK so each order has at most fifty line items — we capped that in the system five years ago because…" [truncated; full quote in `model.orm.yaml`])*

## Provenance prefix table (text-first)

Combining schema-skill prefixes with text-first additions:

| `source` | `status` | Prefix template |
|---|---|---|
| `explicit` | `confirmed` | `[from user statement, confirmed; turn N]` |
| `sample` | `confirmed` | (rare in text-first — would require very high confidence; typically stays proposed) |
| `sample` | `proposed` | `[from sample population, proposed; turn N]` |
| `common-sense` | `confirmed` | `[from common-sense library, confirmed; CSDP step N]` |
| `common-sense` | `proposed` | `[from common-sense library, proposed; CSDP step N]` |
| `llm-inferred` | `confirmed` | `[from LLM inference, confirmed at Step 7b; turn N]` |
| `llm-inferred` | `proposed` | `[from LLM inference, proposed]` |
| `user-supplied` | `confirmed` | `[user-supplied at Step 7d, turn N]` |

When `modality: deontic`:

> *[user-supplied at Step 7d, turn 42; deontic — should rule, possibly violated] Each Customer should pay within 30 days.*

## Worked snippet (text-first verbalization)

For a small movie-catalog CSDP run, the canonical verbalization output reads (excerpts):

```
=== Model overview ===
Designed via CSDP on 2026-05-14, 47 dialogue turns, mode=guided.

=== Object Types ===

Movie is identified by MovieId.
[from user statement, confirmed; turn 3] Movie is identified by movie-id.
(User said: "Each movie has a unique numeric ID, we generate them on creation.")

Director is identified by DirectorName.
[from user statement, confirmed; turn 7] Director is identified by name.
(User said: "Directors are identified by their full name — we don't have an ID system for them.")

(Independent — instances may exist without playing any elementary fact roles.)
[from common-sense, confirmed at Step 7b; CSDP step 6] Director is independent.

=== Fact Types ===

Movie has title.
[from user statement, confirmed; turn 4] Each Movie has exactly one title.
(User said: "Movies have one canonical title in our catalog.")

Sample facts (user-provided at Step 1):
  Movie #1 has title 'The Departed'.
  Movie #2 has title 'Inception'.
  Movie #3 has title 'Parasite'.

Movie directed by Director.
[from user statement, confirmed; turn 5] Each Movie is directed by exactly one Director.
(User said: "Sole-director credit only in our catalog — for co-directed films we pick one.")
[from common-sense library, proposed; CSDP step 6] Each Director directs at least one Movie.

Sample facts:
  The Departed directed by Martin Scorsese.
  Inception directed by Christopher Nolan.
  Parasite directed by Bong Joon-ho.

Movie has rating Rating.
[from user statement, confirmed; turn 8] Rating must be one of: G, PG, PG-13, R, NC-17.
(User said: "MPAA ratings only — we use the five-tier system.")

=== Top-level Constraints ===

[user-supplied at Step 7d, turn 39; deontic — should rule]
Movies should be released no later than 5 years after production began. (Soft business rule for our catalog freshness; not enforced.)

=== Antipattern Flags ===

(None — clean CSDP run.)

=== Appendix: Rejected Proposals ===

[from LLM inference, rejected at Step 7b, turn 33] Each Director has at most one nationality.
Reason: "Dual citizens exist in our catalog — Christopher Nolan is British/American."
```

The verbalization is dialogue-first: every constraint traces back to a turn, and many cite the user's actual words. This is the primary review surface — a stakeholder can read it without seeing the YAML or the original conversation, and validate or challenge each claim.

## Differences from schema-side verbalization

| Element | Schema-side | Text-first |
|---|---|---|
| Header | "Model from PUBLIC, introspected at TIMESTAMP via DDL." | "Designed via CSDP on DATE, N dialogue turns, mode=guided." |
| Provenance prefix | `[from PK]`, `[from UNIQUE]`, `[from common-sense library, proposed]` | Adds `CSDP step N` and `turn N` to most prefixes |
| Sample populations | Not present (live-DB sample probes show up in constraints, not as readable populations) | Rendered as named examples (max 3-5 visible; rest in YAML) |
| User quotes | Not applicable (no user in the loop) | Inline citation when source is `explicit` or `user-supplied` |
| Antipattern call-outs | Schema antipatterns (denormalized address, encoded enum, etc.) | Different antipattern set (over-decomposition, attribute-as-subtype, redundant entity types) — text-first antipatterns documented in csdp-workflow.md Step 7c |

## Halpin-compatibility checks

The verbalization should pass two tests:

1. **The "domain expert read-aloud" test.** Hand the verbalization to someone who knows the domain but not ORM 2 / PyRel / SQL. They should be able to read each sentence and either confirm or challenge it. If a sentence references a Halpin term the reviewer doesn't know (e.g., "objectification"), simplify or add a brief inline gloss.

2. **The "round-trip" test.** Take the verbalization, hand it to an ORM-trained modeler with no access to the YAML, and ask them to reconstruct the model. The reconstructed model should match the original modulo formatting. If structure is missing (e.g., a constraint exists in the YAML but doesn't appear in the verbalization), the verbalization is incomplete.

Both tests should pass on every Step 7a output. If they don't, fix the verbalization, not the YAML.
