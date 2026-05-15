# rai-orm-from-text — Build Plan (v2, draft, paused)

> **Companion to [the schema-first plan](../rai-orm-from-schema/PLAN.md)** (v1, ✅ shipped as plugin v1.0.10 on 2026-05-06, pending E1 validation runs). This document is v2 — the text-first skill: input is a natural-language domain description (with optional sample data and stakeholder dialogue), output is an ORM YAML model and PyRel code.

> **Status (updated 2026-05-06):** v1 has shipped its build artifacts (SKILL.md + 8 references + 4 example triples + 3 reference solutions + USAGE.md + evals/README.md + eval cases). Awaiting the reviewer's review of the reference-solution drafts and the Activity 2 head-to-head review. Construction of v2 starts only after that review confirms the YAML+ORM intermediate architecture earns its keep. Until then, this plan captures lessons learned from v1 so they're back-ported here at the source.

> **Scope discipline (mirrors schema):** v2 will match the existing-skill pattern in this repo — `SKILL.md` + `references/` (markdown) + `examples/` (illustrative) + `evals/` + `USAGE.md`. Claude does the work in-session. **No Python package, no CLI, no MCP server, no pytest.** Architecture decisions (YAML format, five-source provenance, alethic/deontic, Halpin fidelity) inherit directly from the schema plan via `skills/rai-orm-core/` (per TODO.md item #5) — only the workflow and inputs differ.

---

## Lessons from v1 (rai-orm-from-schema, 2026-04-24 → 2026-05-06)

These aren't speculative — they're things we actually ran into during the schema-skill build. Carrying them forward saves rediscovery cost in v2.

### Architecture / process lessons

1. **Phase 1 lock notes pay for themselves.** v1 produced 8 lock notes (`notes/phase1-*.md`) that captured Halpin-grounded design decisions before code. They were referenced repeatedly during Phases 2–4. v2 should produce equivalents — at minimum: `phase1-pyrel-findings.md` (PyRel coverage check), `phase1-halpin-findings.md` (CSDP-focused), `phase1-yaml-format-text-extensions.md` (text-first YAML additions), `phase1-synthetic-dialogue-spec.md`, `phase1-csdp-workflow.md` (the 7 steps with substeps locked), `phase1-skill-description.md`.
2. **Write `USAGE.md` alongside `SKILL.md`.** v1 added `USAGE.md` late as a user-facing capabilities reference — separate from `SKILL.md` (Claude's procedural definition) and `evals/README.md` (testing). Three-doc split worked. v2 should plan for `USAGE.md` from Phase 2.
3. **Write `evals/README.md` as part of Phase 4.** Testing guide for the human running the skill against fixtures. v1 wrote it in Phase 4; v2 should plan for it.
4. **Two consistency passes catch real issues.** v1 ran two validation passes (23 checks total) and surfaced 7 issues including stale folder structure in PLAN.md. Mirror this discipline.

### YAML format lessons

5. **Step 0 = interaction-mode opener.** v1 added an explicit Step 0 (Guided vs One-shot) before the workflow's substantive steps. v2 should do the same — `mode: guided | one-shot` recorded in `source.mode` of the YAML.
6. **LLM-tier spot-check is narrow, opt-in, Guided-only.** v1 evolved a refined design at SRP Step 6c: rather than full review of LLM proposals at the end, surface them ONCE early (Step 6d) so obvious hallucinations don't pollute the verbalization. Library-tier proposals stay non-interactive (rationale is deterministic). v2 has the same structural need at the CSDP equivalent — see CSDP Step 6 expansion below.
7. **Five-source taxonomy worked.** `explicit | sample | common-sense | llm-inferred | user-supplied` covered every constraint origin we encountered in v1. No reason to deviate in v2; semantics adjust per the existing decisions section.
8. **Inline-vs-top-level scope rule for constraints worked.** Constraints scoped to a single fact type live inline; cross-fact-type or object-type-scope constraints live top-level. v1's representation-format.md has the placement table; reuse via `rai-orm-core`.
9. **`provenance.warning: <antipattern-code>` pattern worked.** Antipatterns flag in place rather than restructuring the model. The user's resolution decision lives in `provenance.resolution`. Same pattern in v2 — text-first antipattern catalog is smaller (no schema-derived antipatterns) but the wire format is identical.

### Eval / validation lessons

10. **Reference-solution authorship: Claude drafts under Halpin-grounding constraints, the reviewer reviews line-by-line.** v1's Phase 1.3 lock resolved the circularity concern (Pre-Impl Risk #2). The reviewed file is ground truth, not the draft. v2 inherits this protocol.
11. **One synthetic + several externals.** v1 used Northwind + TPC-H (real) + a hand-built synthetic. v2's analog: 3–5 Halpin Workbook exercises (real, paraphrased) + 1 hand-built synthetic dialogue covering specific antipattern flavors.
12. **Fetch scripts > committed external content for licensing.** v1's TPC-H DDL is governed by TPC EULA, not the repo's Apache 2.0. We sidestepped redistribution by using `fetch.sh` + `.gitignore`. **For v2:** if any benchmark dialogue is excerpted from Halpin's published Workbook, the same logic applies — paraphrase, don't reproduce; cite under fair use; don't commit large excerpts verbatim.
13. **Per-fixture README + commit-hash pinning.** Each external fixture gets a README with source URL, pinned commit, license, and any local modifications.
14. **Reviewability checklist (E5) is qualitative.** Stakeholder fills in a markdown checklist after reading the verbalization. v1 has the template — reuse for v2 with text-first-specific additions.

### Discoverability lessons

15. **CLAUDE.md and README.md need updates when shipping a new skill.** v1 added itself to CLAUDE.md's "Skill Workflow Chain" but is *not* yet in README.md's skill table. v2 should plan for both updates as part of Phase 5.
16. **Plugin version bump is a single-line edit when ready.** Per CLAUDE.md and the schema-skill experience: bump `.claude-plugin/marketplace.json` `plugins[0].version` from current to `<next>` as part of v2's Phase 5.
17. **Run `dev-quality-skills-review` checklist as a Phase 5 deliverable.** v1 produced `notes/phase5-quality-review.md` (40 ✅ / 1 🟡 / 1 ➖ / 0 ❌). Same audit applies to v2.

### Known issues inherited from v1 (open at handoff)

These are unresolved at v1 ship; v2 will inherit them. Resolution affects v2's reference solutions too.

| # | Issue | Where it shows up in v2 |
|---|---|---|
| L1 | Library-entry id mismatch — YAMLs use slug ids; `constraint-inference.md` keys by match strings without explicit ids | Same library is shared via `rai-orm-core`; same mismatch surfaces |
| L2 | `fact_type_pair` undocumented — used in v1's irreflexive ring on `INVENTORY_TRANSFER` from/to | Less likely in text-first (no INVENTORY_TRANSFER analog) but same shape may emerge for "sibling" relationships |
| L3 | Top-level `value` + `role_ref` hybrid form undocumented for role-scope value constraints on primitive value types | Same need exists in text-first when a primitive role has a tighter range than its object type |
| L4 | No deontic constraints in any v1 reference solution | v2 reference solutions should include a deontic constraint to close this coverage gap |
| L5 | 12 elided fact types in v1's synthetic.orm.yaml (CustomerAddress + Warehouse address columns) | Adopt completeness discipline in v2: no ELIDED markers in reference solutions |

---

## Strategic Rationale — Why Text-First (and Why After Schema)

Halpin originally designed CSDP (Conceptual Schema Design Procedure) for the text-first case — a domain expert and a modeler working through sample facts in conversation, building up an ORM model from elementary facts. It's the canonical Halpin workflow and the case where ORM's "verbalize first, model second" methodology is most distinctive.

**Why it's the v2 case:**
- More LLM-driven, less deterministic input. The skill's quality depends heavily on dialogue quality with the user.
- No DDL-derived ground truth. Every constraint is either user-stated, sample-derived, common-sense, LLM-inferred, or user-supplied — no `explicit` constraints from a schema.
- Harder to benchmark. There's no equivalent of "run rai-build-starter-ontology on the same schema" — text input doesn't have an obvious comparison skill in this repo.

**Why we wait for v1.** Building v2 first would mean betting the YAML+ORM intermediate architecture on the harder case before validating it on the easier one. The schema-first skill provides the cheaper validation: it can be benchmarked side-by-side against `rai-build-starter-ontology` on the same input. If reviewers find the YAML+ORM artifact useful there, we have grounded confidence to invest in the text-first build. If not, the architecture itself needs revisiting before v2 is worth the effort.

**Comparison for v2 is harder.** No direct head-to-head equivalent. Plausible Activity 2 candidates: (a) compare with-skill vs without-skill (Claude given the same user input, with and without the skill activated); (b) compare with-skill against a hand-built ORM model produced by an experienced Halpin-style modeler given the same dialogue. Both manual, low-N.

---

## Decisions

### Inherited from the schema-first plan

YAML intermediate, **five-source / three-status constraint provenance** (`explicit | sample | common-sense | llm-inferred | user-supplied`), typed-library + LLM constraint inference, alethic/deontic modality, top-level `version: 1` field, Halpin copyright discipline, `rai-pyrel-coding` alignment. All shared content lives in `skills/rai-orm-core/` (promoted there at the start of this skill's Phase 1, per TODO.md item #5).

### Specific to this skill

| # | Decision | Date |
|---|---|---|
| T1 | **Text-to-ORM is the primary direction** (forward design — starting from a domain description and constructing a conceptual model in dialogue with the user). Schema-to-ORM (reverse engineering from existing structure) is `rai-orm-from-schema`'s lane. | draft |
| T2 | **CSDP, not SRP.** Halpin's seven-step Conceptual Schema Design Procedure is the canonical workflow for forward ORM design. We follow it closely (S12 / Halpin fidelity applies). | draft |
| T3 | **Verbalization is throughout the workflow, not just at the end.** Claude verbalizes elementary facts back to the user in CSDP Step 1, re-verbalizes proposals in later steps, and produces the final whole-model verbalization for Step 7's quality review. Same template patterns as schema skill (shared in `rai-orm-core`). | draft |
| T4 | **Sample-data eliciting (not probing).** Claude asks the user "show me an example" or "tell me about a typical case" rather than running cardinality probes. Halpin's CSDP Step 1 is built around examples. | draft |
| T5 | **Boundary with `rai-orm-from-schema`** must be explicit. The differentiator: text-first when no schema exists yet (greenfield design); schema-first when an existing structure needs recovering. Both produce the same YAML+ORM artifact format. | draft |
| T6 | **Skill name:** `rai-orm-from-text`. | 2026-04-28 |
| T7 | **Pass-bar is intrinsic; build is independent of `rai-orm-from-schema`'s modeling content.** We don't read its output on benchmarks during construction. We do reuse the shared markdown in `rai-orm-core` (representation format, ORM → PyRel rules, constraint library, verbalization patterns). PyRel idioms come from `rai-pyrel-coding`; ORM idioms from Halpin. | draft |
| T8 | **`confidence: standard` always.** Text input means a domain expert is in the loop — there's no "low-confidence" mode equivalent to the schema skill's CSV-only case. (Quality varies with dialogue depth, but that's a different concern than schema absence; see Caveats.) | draft |
| T9 | **No code abstraction layer.** Claude reads the rules from `references/` (and `rai-orm-core/`'s shared references) and applies them in-session. Dialogue is conducted in conversation with the user. | draft |
| T10 | **Benchmark fixtures: drawn from Halpin's textbook examples** (`notes/orm-resources/books/ORM_Workbook_clean.pdf` has worked exercises). Each canonical exercise becomes a benchmark: the input is the dialogue-style prompt, the reference solution is the textbook answer (paraphrased, S12 copyright). Three to five exercises chosen for breadth. | draft |
| T11 | **Promote shared assets to `rai-orm-core/` as Phase 1 task** (per TODO.md item #5). This is the trigger condition that activates the deferred shared-library promotion. After promotion, both skills consume the shared markdown via cross-folder references. | draft |
| T12 | **Halpin fidelity, especially.** Inherited from the schema plan's S12 but more critical here: CSDP is Halpin's procedure, the verbalization grammar is Halpin's CNL, the constraint vocabulary is Halpin's. Originality discipline still applies — examples are ours, paraphrasing is fine, reproduction of Halpin's text or diagrams is not. | draft |
| T13 | **Step 0 — interaction-mode opener** (Guided vs One-shot). Inherited from v1's design refinement. Recorded in `source.mode`. **Caveat:** One-shot is even more degraded for text-first than for schema (no DDL to lift constraints from); user input must be unusually rich for One-shot to produce a useful model. Default = Guided. | inherited from v1 (2026-05-04) |
| T14 | **LLM spot-check at the LLM-proposal step** (CSDP Step 6c equivalent). Narrow, Guided-only, opt-in. Surfaces ONLY LLM-tier proposals (not library / pattern proposals); user marks obvious hallucinations as `rejected` immediately so they don't pollute Step 7's whole-model verbalization. Maps directly to v1's Step 6d. | inherited from v1 (2026-05-04) |
| T15 | **`USAGE.md` alongside `SKILL.md`.** User-facing capabilities reference, separate from `SKILL.md` (Claude's procedure) and `evals/README.md` (testing). Three-doc split locked in v1; mirrored here. | inherited from v1 (2026-05-06) |
| T16 | **Two consistency passes before the reviewer review.** v1's discipline of running structural + cross-reference validation twice (23 total checks) caught real issues — adopted as a v2 Phase 5 step. | inherited from v1 (2026-05-06) |

---

## Inputs and Outputs

**Input** — the user provides any combination of:

| Input shape | Notes |
|---|---|
| **Natural-language domain description** | Primary case. The user describes what they're modeling: entities, relationships, rules, examples. May arrive in one prompt or unfold conversationally. |
| **Sample data** (small) | Forms, reports, spreadsheets, CSV exports. Used illustratively (not exhaustively) — Halpin's CSDP populates fact types with a handful of sample fact instances, not thousands. |
| **Existing artifacts** | Glossaries, requirements docs, business-rule catalogs, sample queries — anything textual. |
| **Conversation** | The user answers Claude's questions throughout CSDP. The dialogue itself is part of the input. |

**Output:**
- `model.orm.yaml` — ORM model with full provenance.
- `model.py` — PyRel code, generated by Claude applying the translation rules from `rai-orm-core/references/orm-to-pyrel.md`.
- `model.verbalization.txt` — natural-language verbalization for stakeholder review.

---

## Workflow: the Conceptual Schema Design Procedure (CSDP)

The "thing being taught" by the skill. Halpin's canonical seven steps, prefixed by an interaction-mode opener (T13):

> **0. Interaction-mode opener** (Guided only; One-shot starts at Step 1). Claude prompts the user: *"I can run this in two modes: Guided (we walk through CSDP step by step) or One-shot (you give me a detailed domain description and I produce a draft model in one pass; you review by editing the YAML). Which would you prefer?"* Default = Guided if no answer. Recorded in `source.mode`.
>
> 1. **Transform familiar examples into elementary facts; check.** Get the user to provide concrete examples (sample reports, forms, typical cases). Verbalize each example as elementary facts (atomic, irreducible). Confirm with the user.
> 2. **Draw the fact types and apply a population check.** From the elementary facts, identify object types and predicates. Populate fact types with the sample fact instances to validate the structure.
> 3. **Check for entity types that should be combined; note arithmetic derivations.** Look for redundant or merge-able entity types. Mark facts that are computed from others.
> 4. **Add uniqueness constraints; check arity of fact types.** For each fact type, identify which roles are unique. Verify each fact type's arity is correct (not over- or under-decomposed).
> 5. **Add mandatory role constraints; check for logical derivations.** For each role, determine whether participation is mandatory. Mark facts implied by combinations of others.
> 6. **Add value, set-comparison, and subtyping constraints.** Restrict allowed values; express subset/equality/exclusion across fact types; define subtypes where applicable. (Full mechanics under "CSDP Step 6 expansion" below — includes the constraint-inference substeps and the Guided-only LLM spot-check inherited from v1's Step 6d.)
> 7. **Add other constraints and final checks.** Frequency, ring, deontic. Run the quality review with the user, including any user-supplied constraints they noticed during verbalization. (Full mechanics under "CSDP Step 7 expansion" below; includes Guided vs One-shot mode behavior.)

How Claude executes this: reads CSDP from SKILL.md, walks the user through each step in conversation, applies markdown-documented rules from `rai-orm-core/references/` for constraint inference and translation. No bundled scripts.

### CSDP Step 6 expansion (constraint inference) — inherits v1 SRP Step 6 design

Step 6 ("Add value, set-comparison, and subtyping constraints") expands into five substeps mirroring v1's SRP Step 6:

> **6a.** Auto-propose constraints from the **typed library** (shared with v1 via `rai-orm-core/references/constraint-inference.md`) keyed on object-type names and primitive types.
>
> **6b.** Auto-propose **ring constraints** from structural patterns. Self-referential binary fact types match the same library entries v1 uses.
>
> **6c.** Ask the LLM tier to propose further constraints from world knowledge for object types/relationships the library doesn't cover. Each proposal must include `provenance.rationale_world_fact` (mandatory; rejected at emission without it).
>
> **6d.** **LLM spot-check** (Guided mode only; opt-in). Surface ONLY Step 6c LLM-tier proposals (not library or ring) so obvious hallucinations don't pollute Step 7's whole-model verbalization. The user can defer all decisions to Step 7b. **Why narrow:** library and ring are reviewed in context at Step 7; only LLM tier benefits from early filtering.
>
> **6e.** Verbalize all surviving Step 6 proposals back to the user — input to Step 7's whole-model verbalization.

In One-shot mode, 6d is skipped; LLM proposals stay `proposed` for the user to review by editing the YAML.

---

## Constraint Provenance and Inference

Inherits the five-source / three-status taxonomy from the schema plan. The mechanics are shared (in `rai-orm-core`); only the source semantics differ for text-first input.

**Core principle: propose, never assert.** Same as schema skill.

```yaml
constraints:
  - type: uniqueness
    roles: [Person, Country]
    source: explicit          # explicit | sample | common-sense | llm-inferred | user-supplied
    status: confirmed
    rationale: "User stated: 'each person was born in exactly one country'."
```

### `source:` field — five values, semantics adjusted for text-first

1. **`explicit`** — Stated explicitly by the user in conversation. The user said *"each customer has exactly one shipping address"* or *"orders are placed by exactly one person"*. No DDL — the verbalization itself is the source. Auto-`status: confirmed`.
2. **`sample`** — Inferred from sample populations the user provided in CSDP Step 1. *"In your example data, each `Person` had exactly one `Email`."* Sample size is small (Halpin's typical exercise uses 5–20 sample facts), so coverage is partial. Stays `proposed` unless the user explicitly confirms.
3. **`common-sense`** — Same as schema: typed library + relationship-pattern proposer. Library is shared in `rai-orm-core`. Auto-`status: proposed`.
4. **`llm-inferred`** — Same as schema: Claude proposes from world knowledge for novel cases. Highest hallucination risk.
5. **`user-supplied`** — Added during the final review (CSDP Step 7e) when the user notices domain knowledge the system missed. Auto-`status: confirmed`.

**`status:` field — three values.** Identical to the schema plan; defined in `rai-orm-core/references/representation-format.md`.

### Alethic vs. deontic modality

ORM 2's modality distinction. Same as schema skill. The user labels modality at confirmation time (Step 7e of the CSDP, below). Alethic constraints become hard rules; deontic constraints emit as `# DEONTIC NOTE:` comments in PyRel.

### CSDP Step 7 expansion

Step 7 ("Other constraints and final checks") expands into six substeps. (CSDP Steps 1–6 are separate top-level steps that produce proposals; Step 7 is the final review-and-finalize moment.)

> 7a. User reviews the whole-model verbalization (the canonical readings for every fact type and constraint).
> 7b. User confirms / rejects / escalates each proposed constraint accumulated through Steps 1–6.
> 7c. Auto-propose any remaining ring, frequency, and deontic constraints from the typed library / pattern proposer / LLM tier.
> 7d. User adds any constraints they know but the system missed (`source: user-supplied`, auto `status: confirmed`).
> 7e. User labels every confirmed constraint as alethic or deontic.
> 7f. Commit confirmed + user-supplied to YAML. Rejected proposals go in `rejected_proposals` so we don't re-propose them.

**Guided vs One-shot mode.** Forward design is fundamentally interactive — One-shot mode is degraded for this skill compared to schema-first. In Guided mode the substeps run as a real conversation. In One-shot mode the user's domain description must be detailed enough that Claude can carry the whole CSDP through to a draft YAML; the user then reviews/edits the YAML directly.

### Risks of the inference layer

Same risks as the schema plan, plus one text-first-specific:
- All the schema-plan risks: cultural/legal variation, LLM hallucination, stale common sense, over-constraining, foundational-ontology rigor.
- **Sample-population poverty.** Halpin's CSDP traditionally uses small populations (5–20 facts). A constraint that holds across 20 samples can fail at row 21. The `sample` source must stay `proposed` unless the user explicitly confirms — never auto-promote on text-skill samples (cf. schema skill which can promote on live-DB samples).

Domain-specific (organization-policy) constraints are a separate v1.5 extension via a per-deployment `domain_library.yaml`. Tracked in TODO.md item #6.

---

## YAML Representation Format

Same custom YAML as schema skill. Format spec lives in `rai-orm-core/references/representation-format.md`. Text-first-specific shape additions:

```yaml
version: 1

source:
  kind: text-conversation       # text-conversation | requirements-doc | mixed
  session_id: csdp_2026_05_03_movies   # arbitrary identifier for the dialogue session
  artifacts:                    # optional pointers to user-provided text artifacts
    - "user-prompt.md"
    - "sample-form.png"
  started_at: "2026-05-03T10:15:00Z"
  confidence: standard          # always 'standard' for text-first (T8)

object_types:
  - name: Person
    kind: entity
    reference:
      mode: popular             # Halpin's "popular reference mode" (e.g., name)
      from: { object_type: PersonName }
    provenance:
      origin: csdp-step-1
      verbalization: "Person identified by name"

fact_types:
  - reading: "{Person} was born in {Country}"
    roles: [Person, Country]
    constraints:
      - type: uniqueness
        roles: [Person]
        source: explicit
        status: confirmed
        rationale: "User stated: 'each person was born in exactly one country'."
        provenance: { csdp_step: 1, dialogue_turn: 4 }
      - type: mandatory
        role: Person
        source: explicit
        status: confirmed
        rationale: "User confirmed: 'every person has a birth country'."
        provenance: { csdp_step: 5, dialogue_turn: 12 }
```

Provenance for text-first traces back to *which CSDP step* the constraint emerged in and *which dialogue turn* the user confirmed (or rejected) it. Makes the YAML auditable in dialogue terms instead of column-and-table terms.

---

## ORM → PyRel Translation

Same as schema skill. Uses the shared `rai-orm-core/references/orm-to-pyrel.md` translation rules — three-tier (mechanical / heuristic / not-translated). Halpin-copyright discipline (T12).

---

## Caveats

Caveats specific to text-first construction:

1. **Conversation-driven means output depends on user engagement quality.** A user who says "I want to model my e-commerce site" without elaboration will get a thin model. Skill must explicitly ask for examples, populations, edge cases — and stop when answers run out.
2. **Halpin's CSDP is a methodology, not just a checklist.** Following the steps mechanically without the underlying mindset (atomic facts, no attributes, populate before constraining) produces ER-style output dressed in ORM clothes. The skill must teach the *posture*, not just the procedure.
3. **Reference scheme elicitation is hard.** New users default to attribute thinking. CSDP Step 1 must elicit reference schemes explicitly (*"how is each Person identified — name, employee number, social security?"*) rather than assuming.
4. **Subtype over-use.** Users often suggest subtypes prematurely. CSDP Step 6's subtype check is where the skill must push back: are these distinguishable in roles, or just attribute differences?
5. **Sample populations are too small to prove constraints.** Always treat `sample` constraints as `proposed`. Never auto-promote on text-first samples (T8 / risks).
6. **Pretend-verbalization risk.** Claude might verbalize a fact the user hasn't actually confirmed, then proceed as if confirmed. Verbalization must always be presented as a *question* (*"is this right?"*) not an *assertion* in CSDP Steps 1, 4, 5, 6.
7. **Halpin-canonical terminology.** Use "fact type," "role," "object type," "reference scheme" — not "table," "column," "relationship type." Slipping into ER vocabulary leaks ER mental models.
8. **Build-time contamination risk.** Implementer must avoid reading `rai-orm-from-schema`'s output on schema benchmarks during construction (per T7). Reading the shared `rai-orm-core/` references is fine and required.

---

## Evals and Benchmark

Two distinct activities, run at different times.

### Activity 1 — Build-time evals (the v0.2 gate)

Same shape as the schema plan's Activity 1, adapted for text-first.

**Reference solutions.** Drawn from Halpin's textbook exercises (T10). For each chosen exercise, build the expected ORM YAML by carefully transcribing the textbook's worked solution (paraphrased, T12 copyright). Stored in `evals/expected/<exercise>.orm.yaml`. Authorship/review plan locked in Phase 1 (Pre-Implementation Risk #2): same circularity concern as schema skill — Claude can't both author the references and grade against them.

**Eval cases:**

| # | What we measure | Method |
|---|---|---|
| **T-E1** | Reference-solution match | Diff our skill's YAML output against `expected.orm.yaml`. Same equivalence rules as schema skill's E1. |
| **T-E2** | Constraint coverage | Count constraints by `source` category. Targets vary per exercise (since Halpin's exercises emphasize different constraint types). |
| **T-E3** | Question-asking quality | Did Claude ask appropriate clarifying questions during ambiguous CSDP steps? Especially: did it elicit reference schemes (cf. Caveat #3), did it push back on premature subtyping (cf. Caveat #4)? Manual review. |
| **T-E4** | Halpin posture adherence | Does the output use Halpin terminology and atomic-fact framing throughout, or does it slip into ER vocabulary? Manual review. |
| **T-E5** | Stakeholder reviewability | Same as schema skill — hand the YAML to a non-PyRel reviewer; can they validate by reading verbalizations? |

**Constraint correctness rubric.** Same as schema skill — must hold in the dialogue (user explicitly confirmed, or trivially derivable from sample populations) AND must be intentional (a real domain rule, not a coincidence of the small sample).

**v0.2 pass-bar:** T-E1 must pass on 3+ chosen Halpin exercises; T-E2 coverage targets met per exercise; T-E3 and T-E4 pass on manual review; T-E5 passes with at least one stakeholder.

### Activity 2 — Post-v0.2 head-to-head

Comparison is harder than the schema skill's case (no direct competing skill in this repo). Two plausible candidates:

1. **With-skill vs without-skill.** Run Claude on the same domain description, once with rai-orm-from-text activated and once without. Compare the resulting models for completeness, Halpin-fidelity, and reviewability.
2. **Skill vs human Halpin-expert.** A human ORM-trained modeler is given the same dialogue session. Compare the two models manually.

Both are manual, low-N. The eval-runner / benchmark-runner scripts that earlier drafts proposed are stretch goals (TODO.md S6).

### Benchmark exercises (drawn from Halpin's Workbook, T10)

| Exercise | Why |
|---|---|
| **TBD** | Pick 3–5 from `notes/orm-resources/books/ORM_Workbook_clean.pdf` during Phase 1. Selection criteria: cover binary + ternary fact types, uniqueness + mandatory + value constraints, at least one objectification case, at least one subtyping case. |

---

## Pre-Implementation Risks (Watch-Out List)

Risks to internalize before kicking off Phase 1. Mostly mirror the schema plan; differences flagged.

1. **`rai-pyrel-coding` coverage.** Same risk as schema skill. *Mitigated by Phase 1's first task — read `rai-pyrel-coding` end-to-end before locking architecture decisions. (Likely already done during schema-skill Phase 1; verify nothing changed.)*

2. **Reference-solution circularity.** Same as schema skill. *Mitigated by Phase 1's authorship/review-plan task — must be locked before Phase 4. Halpin's textbook solutions are the natural ground truth here, but transcribing them faithfully (without Claude paraphrasing in ways that drift) needs the reviewer review.*

3. **Synthetic-dialogue fixtures.** For T-E3 (question-asking quality) and degradation tests, we need synthetic *dialogues* — multi-turn user inputs of varying quality. *Mitigated by Phase 1's synthetic-dialogue-spec task: design 3–5 dialogue scenarios (good user, sparse user, hostile user, novice user) before Phase 4.*

4. **Dialogue-quality dependence (text-first specific).** Output quality depends on user engagement. There's no mitigation that makes this robust — a sparse user gets a thin model. The risk is *acknowledging* this honestly: the skill should ask increasingly pointed questions when answers are thin, but ultimately can't make up for an absent domain expert.

5. **Halpin posture, not just procedure.** A real risk that the skill teaches CSDP mechanically without the underlying ORM mindset (cf. Caveat #2). *Mitigated by Phase 1's source-material grounding — read Halpin's books on the philosophy, not just the procedure.*

6. **Bad-content cascade (ongoing discipline).** Same as schema skill.

7. **Inherited design ambiguities from v1.** Five known issues open at v1 ship (L1–L5 in the Lessons section above). v2's reference solutions can resolve them at the source. *Mitigated by tracking each in v2's Phase 1 task list and resolving before Phase 4.*

8. **Halpin Workbook copyright (text-first specific).** Benchmark exercises drawn from `notes/orm-resources/books/ORM_Workbook_clean.pdf` cannot be reproduced verbatim per S12. *Mitigated by paraphrasing the prompt-and-solution pairs and citing the source page; if scale grows, follow v1's TPC-H model — fetch script + per-fixture README + `.gitignore`.*

9. **Synthetic dialogue specification ambiguity.** Unlike v1's synthetic schema (where antipatterns are concrete column patterns), a synthetic *dialogue* depends on user-input quality variations. Easy to under-specify. *Mitigated by Phase 1 task — write `notes/phase1-synthetic-dialogue-spec.md` covering 3–5 user types (good/sparse/hostile/novice) before Phase 4 builds them.*

10. **Deontic-coverage gap (inherited from v1).** v1's reference solutions emit no deontic constraints. v2 should plan at least one deontic constraint in at least one reference solution to close this coverage gap. *Mitigated by Phase 1 task — flag deontic-emission as a Phase 4 acceptance criterion.*

---

## Build Plan — Five Phases

**Phase 1 — Spec, source-material grounding, and `rai-orm-core` promotion (4–5 days).**

Phase 1 produces lock notes (one per task) following the v1 pattern (`notes/phase1-*.md`). Each lock note becomes the authoritative source for its area; subsequent phases lift from there.

- **1.1 — `rai-pyrel-coding` re-verification.** Re-read the skill (already read during schema-skill Phase 1; check for changes). Output: confirm `notes/phase1-pyrel-findings.md` is still accurate or write a delta note.
- **1.2 — Halpin source-material grounding (CSDP focus).** Read `books/ORM_Fundamentals_clean.pdf` chapters on CSDP, elementary fact decomposition, reference schemes, and verbalization (skip mapping/relational chapters — handled by `rai-orm-core`). Read `books/ORM_Workbook_clean.pdf` worked exercises. Output: `notes/phase1-csdp-halpin-findings.md` covering CSDP semantics, Halpin's posture guidance, and worked-exercise inventory.
- **1.3 — Reference-solution authorship and review (Pre-Impl Risk #2).** Lock the protocol — same as v1 (Claude drafts under Halpin-grounding constraints; the reviewer reviews line-by-line). For Workbook-derived solutions, paraphrase per S12/T12 copyright discipline.
- **1.4 — Synthetic-dialogue fixture spec.** Output: `notes/phase1-synthetic-dialogue-spec.md` covering 3–5 user types (good / sparse / hostile / novice) with multi-turn prompt sequences. Each scenario plants specific antipattern-flavor opportunities.
- **1.5 — YAML format text-first extensions.** Output: `notes/phase1-yaml-format-text-extensions.md` covering text-first additions to the v1 YAML spec — `source.kind: text-conversation`, `provenance.csdp_step`, `provenance.dialogue_turn`, deontic-emission requirement (closes L4 from Lessons).
- **1.6 — CSDP workflow lock.** Output: `notes/phase1-csdp-workflow.md` — full 7+1 steps with substeps, Step 6 expansion, Step 7 expansion, and Halpin-posture guidance per step.
- **1.7 — Pick benchmark exercises from Workbook** (T10): 3–5 covering binary + ternary fact types, uniqueness + mandatory + value constraints, at least one objectification case, at least one subtyping case, at least one **deontic** constraint (closes L4 from Lessons). Output: `notes/phase1-benchmark-exercises.md`.
- **1.8 — Skill description text.** Output: `notes/phase1-skill-description.md` with frontmatter + Summary section locked verbatim for Phase 2.
- **1.9 — `rai-orm-core` promotion.** Move `references/representation-format.md`, `references/constraint-reference.md`, `references/constraint-inference.md`, `references/verbalization-patterns.md`, `references/orm-to-pyrel.md` from `skills/rai-orm-from-schema/references/` to a new `skills/rai-orm-core/references/`. Update cross-references in both skill folders. Resolve L1, L2, L3 from Lessons during this promotion (library entry ids, `fact_type_pair` documentation, role-scope value-constraint hybrid form).

**Phase 2 — SKILL.md + USAGE.md skeleton (3–4 days).**
- Frontmatter and stability tag (`v1-SENSITIVE`).
- Summary / "When to use" / "When NOT to use" — tight redirect to `rai-orm-from-schema` for users who already have a schema.
- Step 0 — interaction-mode opener (Guided vs One-shot; note: One-shot is degraded for text-first per T9, T13).
- CSDP workflow with concrete prompts per step (probably 2× the size of v1's SRP section because CSDP is more interactive).
- Constraint provenance & validation flow.
- Common pitfalls (the Caveats list above, expanded with concrete examples).
- ORM → PyRel mapping (cross-reference to `rai-orm-core`'s shared rules; gap list per text-first).
- Examples table, reference files table.
- **`USAGE.md` (T15):** alongside `SKILL.md`. Inputs / outputs / modes / per-step user options / constraint sources / antipatterns / capabilities and non-capabilities / invocation patterns. Mirror the structure of v1's `USAGE.md`.

**Phase 3 — References and Examples (4–5 days).**

*References (markdown, loaded by Claude on demand):*
- `references/csdp-workflow.md` — full CSDP, prompt-by-prompt with Halpin posture guidance and Step 0 / Step 6 expansion / Step 7 expansion expanded.
- `references/dialogue-patterns.md` — conversational patterns: how to elicit examples, push back on premature subtyping, ask for reference schemes, handle thin answers.
- `references/halpin-posture.md` — the underlying mindset (atomic facts, no attributes, populate-then-constrain) with examples of slipping into ER thinking and how to catch it.
- (Shared, in `rai-orm-core/references/`): representation-format.md, constraint-reference.md, constraint-inference.md, verbalization-patterns.md, orm-to-pyrel.md.

*Examples (illustrative pattern files):*
- `examples/movie_catalog.dialogue.md` + `.orm.yaml` + `.py` — small, illustrative; the canonical example, hand-built dialogue showing the CSDP flow.
- `examples/library_with_subtypes.dialogue.md` + `.orm.yaml` — subtyping done right (and wrong, in a "what to avoid" version).
- `examples/objectification_in_enrollment.dialogue.md` + `.orm.yaml` — when to objectify a fact type.
- `examples/reference_scheme_elicitation.dialogue.md` + `.orm.yaml` — focused on Caveat #3.

**Phase 4 — Evals (3–4 days).**
- `evals/cases.json` — T-E1 through T-E5 case definitions (mirror v1's structure exactly; see `skills/rai-orm-from-schema/evals/cases.json`).
- `evals/expected/<exercise>.orm.yaml` — paraphrased Halpin Workbook solutions (per the authorship/review plan locked in Phase 1.3). Each solution includes at least one deontic constraint where the exercise admits one (closes L4).
- `evals/fixtures/<exercise-or-scenario>/dialogue.md` — fixture per exercise / synthetic scenario. README per fixture (mirroring v1's per-fixture README pattern, T17 lesson 13).
- `evals/reviewability_checklist.md` (T-E5; mirror v1's structure).
- `evals/README.md` — testing guide for the human running the skill against fixtures (T15 lesson 3).
- **Eval-run output convention** — same as v1: `evals/results/<YYYY-MM-DD>/<exercise>/{output.orm.yaml, output.py, output.verbalization.txt, diff.md}`.
- Manual eval methodology — Claude runs the skill on each exercise, writes outputs to the convention above, then produces the diff against the reference.

**Phase 5 — Integration and dogfooding (ongoing).**
- **5.1 — Two consistency passes** (T16 lesson 4). Output: `notes/phase5-consistency-pass.md` mirroring v1's pattern (structural checks, link integrity, format-spec compliance, terminology).
- **5.2 — `dev-quality-skills-review` audit** (lesson 17). Run the checklist at `contrib/dev-quality-skills-review/SKILL.md` against v2; record verdict in `notes/phase5-quality-review.md`.
- **5.3 — Plugin version bump** in `.claude-plugin/marketplace.json` (per CLAUDE.md and lesson 16).
- **5.4 — README.md and CLAUDE.md updates** (lesson 15). Add v2 to the README skill table; update CLAUDE.md's "Skill Workflow Chain" section.
- **5.5 — Activity 2 evaluation** — with-skill vs without-skill, or vs Halpin-expert. Decide between the two during Phase 5.
- **5.6 — Real-world dogfooding** — run on actual RAI scenarios; capture feedback in `notes/phase5-dogfood-<scenario>.md`.

**Total rough estimate:** ~3–4 weeks of focused work to v0.2, including review cycles. Slightly longer than v1's ~2.5–3 weeks because (a) CSDP is procedurally larger than SRP, (b) `rai-orm-core` promotion adds Phase 1 work, (c) Halpin reading volume is larger, (d) dialogue-fixture authoring is heavier than DDL fixtures.

---

## Folder Structure (final, matches existing-skill pattern)

```
skills/rai-orm-from-text/
  SKILL.md
  USAGE.md                              # T15 — operational guide alongside SKILL.md (lesson 2)
  PLAN.md                               # this file
  references/
    csdp-workflow.md
    dialogue-patterns.md
    halpin-posture.md
  examples/
    movie_catalog.dialogue.md
    movie_catalog.orm.yaml
    movie_catalog.py
    library_with_subtypes.dialogue.md
    library_with_subtypes.orm.yaml
    objectification_in_enrollment.dialogue.md
    objectification_in_enrollment.orm.yaml
    reference_scheme_elicitation.dialogue.md
    reference_scheme_elicitation.orm.yaml
  evals/
    cases.json
    reviewability_checklist.md
    README.md                           # testing guide (lesson 3)
    expected/
      <exercise-1>.orm.yaml
      <exercise-2>.orm.yaml
      <exercise-3>.orm.yaml
    fixtures/
      <exercise-1>/                     # per-exercise subdir (mirrors v1 lesson 13)
        dialogue.md
        README.md                       # source attribution + paraphrase notes (Halpin Workbook citation)
      synthetic_good_user/
        dialogue.md
        README.md
      synthetic_sparse_user/
        dialogue.md
        README.md
      synthetic_novice_user/
        dialogue.md
        README.md
    results/                            # runtime eval-run outputs (per Phase 4 convention; gitignored)

skills/rai-orm-core/                    # shared library (promoted at start of this skill's Phase 1.9)
  SKILL.md                              # minimal — "shared core, not directly invoked"
  references/
    representation-format.md
    constraint-reference.md
    constraint-inference.md
    verbalization-patterns.md
    orm-to-pyrel.md
```

Same shape as the schema skill, plus `USAGE.md` + `evals/README.md` (lessons from v1) and the freshly-promoted `rai-orm-core/`. No `tools/`, no `pyproject.toml`, no `tests/`.

---

## Residual Open Questions

- **Diagram rendering** — out of scope for v2. Skip.
- **NORMA `.orm` XML export** — defer.
- **Guizzardi-critique mention in scope text** — include one sentence (same as schema skill).
- **Boundary aggressiveness** in "When NOT to use" text — permissive in v2, sharpen after Activity 2 review.
- **Activity 2 candidate** — with-skill vs without-skill, or vs Halpin-expert? Decide during Phase 5; affects the v0.2 release narrative.
- **`rai-orm-core` promotion ordering** — v1 shipped without promoting shared assets (references stay in `skills/rai-orm-from-schema/references/`). v2 Phase 1.9 promotes them. **Decision needed:** does v1 get re-pointed at `rai-orm-core` after promotion (touches a v1-SENSITIVE skill that's awaiting validation), or does v2 reference them via `../rai-orm-from-schema/references/` until v1 is v1-STABLE? Recommended: **promote then re-point both skills atomically as part of Phase 1.9** — keeps the architecture clean. the reviewer confirms during v2 kickoff.
- **Inherited issues from v1** (L1–L5 in Lessons section) — resolve at the source during Phase 1.9 or carry forward into v2's reference solutions.

(Other deferred items — `domain_library.yaml`, the over-engineering stretch goals — tracked in [`../../notes/TODO.md`](../../notes/TODO.md).)

---

## Summary

`rai-orm-from-text` is v2 — the text-first skill that walks a domain expert through Halpin's CSDP to produce an ORM model from natural-language input. Construction starts after the schema-first skill ships v0.1 (now done as plugin v1.0.10, awaiting the reviewer's review of reference solutions and Activity 2 head-to-head) and the architecture validates. **Architecture:** inherits everything from the schema plan via `rai-orm-core` (YAML format, five-source provenance, alethic/deontic, translation rules, constraint library, verbalization patterns) plus four additions inherited from v1's evolution (Step 0 mode opener, Step 6 expansion with Guided-only LLM spot-check, `USAGE.md` operational guide alongside `SKILL.md`, `evals/README.md` testing guide); only the workflow (CSDP) and inputs (text/dialogue) differ. **Mechanism:** Claude reads the skill and walks the user through CSDP in conversation — no Python package, no CLI, no MCP. **Build discipline (T7):** independent of `rai-orm-from-schema`'s output on schema benchmarks; reuses shared `rai-orm-core/` markdown. **Pass-bar (T7):** intrinsic, defined by Halpin Workbook reference solutions and the T-E1 to T-E5 eval cases. **Estimate:** ~3–4 weeks to v0.2, including review cycles and the `rai-orm-core` promotion step.
