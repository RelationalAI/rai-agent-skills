# Usage Guide — rai-orm-from-text

What the skill can do, what options are available, and how to invoke it. For the full procedural definition Claude reads, see [`SKILL.md`](SKILL.md). For testing, see [`evals/README.md`](evals/README.md). The companion schema skill is [`rai-orm-from-schema`](../rai-orm-from-schema/SKILL.md).

---

## What the skill does

Walks a domain expert through **Halpin's Conceptual Schema Design Procedure (CSDP)** to build an **ORM 2 conceptual model** (YAML with full constraint provenance) from a natural-language domain description and dialogue with the user. Produces a stakeholder-reviewable **verbalization** (Halpin-style controlled natural language), and translates the confirmed model to **PyRel** for use with the RelationalAI platform.

The pipeline is CSDP: 7+1 steps from elicitation of elementary facts through to PyRel emission. The skill emphasizes **Halpin posture** (atomic facts, no attributes, populate-then-constrain, verbalize-as-question), not just the procedure.

---

## Inputs

| Input shape | What you provide | Notes |
|---|---|---|
| **Natural-language domain description** | A text description of what you're modelling — entities, relationships, rules, examples | Primary case. May arrive in one prompt or unfold conversationally. |
| **Sample fact instances** | A handful of concrete examples (5–20 facts, Halpin-style) | Drives the population check at Step 2. Small samples on purpose — too many obscure the structure. |
| **Existing artifacts** | Glossaries, requirements docs, business-rule catalogs, sample queries, forms, reports, spreadsheets | Anything textual that informs the domain. |
| **Conversation** | The user answers Claude's questions throughout CSDP | The dialogue itself is part of the input. Quality scales with engagement. |

Unlike `rai-orm-from-schema`, there is no `kind: ddl-file` / `kind: sql` / `kind: csv` distinction — `source.kind` is always `text-conversation` (with optional `artifacts:` list for files the user provided). `confidence` is always `standard` (text-first has a domain expert in the loop; there's no "low-confidence" mode equivalent to the schema skill's CSV-only case).

---

## Outputs

The skill always emits the same triple:

| File | Contents | Audience |
|---|---|---|
| `model.orm.yaml` | The designed ORM 2 model — every constraint carries `source` + `status` + `modality` + `provenance` (CSDP step + dialogue turn + user quote). Single source of truth. | Reviewers |
| `model.verbalization.txt` | Halpin-style CNL rendering — readable without PyRel knowledge. The primary review surface for non-PyRel stakeholders. | Domain experts |
| `model.py` | PyRel translation of the confirmed YAML. Includes `# DEONTIC NOTE:` for "should" rules and `# REVIEW MODALITY` markers when modality is defaulted. | Engineers |

---

## Interaction modes

You pick the mode at CSDP **Step 0**. The choice is recorded in `model.orm.yaml`'s `source.mode` field.

### Guided mode (default and strongly recommended for text-first)

Claude pauses for your input at three pivot points:

| Pivot | What you do |
|---|---|
| **Step 0** | Confirm `guided` |
| **Step 1 + 3 + 4 + 5 + 6** | Throughout CSDP, answer Claude's questions: provide examples, confirm verbalized facts, decide uniqueness/mandatory/value/subtype constraints. The "conversation" is the whole point of text-first. |
| **Step 6d (opt-in)** | Mark obvious LLM hallucinations as `rejected` before they pollute Step 7's whole-model verbalization |
| **Step 7** | Six substeps: review the whole-model verbalization, confirm/reject Step-6 proposals, resolve flagged ambiguities, add user-supplied constraints, label modality, commit |

Steps 2 and 8 are non-interactive — Claude runs them autonomously between user-decision moments.

**Best for:** new modeling work, domains where the user is in conversation with the skill, when you want full Halpin posture (verbalize-and-confirm at every step).

### One-shot mode (degraded for text-first)

The user provides a rich description up front; Claude produces a draft model in one pass; user reviews by editing the YAML. **Significantly more degraded than schema-first One-shot** because text-first has no DDL to anchor structure — the model quality depends entirely on the richness of the initial description.

| Step | One-shot behaviour |
|---|---|
| 1 | Parse the description for elementary facts; verbalize back in the YAML as `sample_population` entries; no dialogue |
| 2–5 | Run autonomously based on the description |
| 6a (library) | Auto-confirm |
| 6b (ring patterns) | Auto-confirm |
| 6c (LLM tier) | Stay `proposed` |
| 6d (spot-check) | Skipped entirely |
| 6e (verbalize) | Same as Guided |
| 7a–e | Skipped (verbalization still emitted to the file); explicit → `alethic`; everything else inherits `alethic` + `# REVIEW MODALITY` flag |
| 7f (commit) | Standard write |

**Best for:** retargeting a previously-designed model to a new domain when the user can write a thorough description; fast iteration when the user will edit the YAML by hand. **Not recommended** for new modeling work — Guided is dramatically better for text-first.

---

## What you can control at each step

### Step 0 — Interaction-mode opener

Pick Guided or One-shot. Default = Guided.

### Step 1 — Elementary facts

You provide examples (forms, sample data, concrete instances). Claude verbalizes each as an elementary fact and asks you to confirm. You can:
- Confirm the verbalization as-is
- Refine the wording (e.g., "say 'is in' rather than 'belongs to'")
- Reject the fact entirely (e.g., "no, that's actually two facts, not one")
- Ask to skip the example and start over with a different one

Reference-scheme elicitation happens here too. For each emerging entity type, you decide whether the identifier is `popular` (single-column PK-like), `unit-based` (Halpin's `Height(cm:)` shorthand), `general` (string identifier like ISBN), or `external` (composite identifier).

### Step 3 — Combining entity types

For each pair of similar-named types Claude flags, you confirm whether they should merge.

### Step 4 — Uniqueness

For each fact type, you confirm which combinations of roles are unique. Verbalization is presented as a population check ("in your data, each Person has at most one Country of birth — always?").

### Step 5 — Mandatory

For each role, you confirm whether participation is required.

### Step 6 — Constraint inference

| Substep | Your role |
|---|---|
| 6a (library) | Non-interactive — library hits are auto-emitted as `proposed`. You review at 7b. |
| 6b (ring patterns) | Same — auto-emitted as `proposed`. |
| 6c (LLM tier) | Non-interactive — LLM proposals emitted as `proposed` with `rationale_world_fact`. |
| 6d (spot-check) | **Guided mode, opt-in.** Surface only the LLM-tier batch. You can mark obvious hallucinations as `rejected` immediately. |
| 6e (verbalize) | Non-interactive — prepares Step 7's whole-model verbalization. |

Subtype check at Step 6 is interactive: when Claude proposes a subtype, you push back on premature subtyping using Halpin's role-based criterion (a subtype is justified only when its instances play roles the supertype doesn't).

### Step 7 — Final review

Six substeps where you have full agency:

| Substep | What you do |
|---|---|
| 7a | Read the whole-model verbalization |
| 7b | Confirm / reject / escalate each proposed constraint from Steps 1–6 (auto-batched when ≥5 proposals in a category) |
| 7c | Resolve any flagged ambiguities (e.g., "this fact type looks over-decomposed") |
| 7d | Add constraints you know but the system missed — free-form natural language; Claude paraphrases back as structured form for confirmation |
| 7e | Label every confirmed non-explicit constraint as `alethic` (must) or `deontic` (should) |
| 7f | Commit (auto) |

### Step 8 — PyRel translation

Deterministic given the finalized YAML. See [`../rai-orm-from-schema/references/orm-to-pyrel.md`](../rai-orm-from-schema/references/orm-to-pyrel.md).

---

## Constraint sources

| Source | Meaning | Default status |
|---|---|---|
| `explicit` | Stated explicitly by the user in conversation | `confirmed` (auto) |
| `sample` | Inferred from sample populations the user provided in Step 1 | `proposed` always — text-first samples are too small to auto-confirm (Halpin's CSDP uses 5–20 facts) |
| `common-sense` | Typed-library lookup or ring-pattern matcher | `proposed` |
| `llm-inferred` | LLM proposal from world knowledge for novel concepts | `proposed` |
| `user-supplied` | Added by you at Step 7d | `confirmed` (auto) |

The library used for `common-sense` is shared with the schema skill: [`../rai-orm-from-schema/references/constraint-inference.md`](../rai-orm-from-schema/references/constraint-inference.md).

---

## What the skill can do (concrete capabilities)

✅ **Walk a user through Halpin's 7-step CSDP** with verbalize-then-confirm at every step.

✅ **Elicit reference schemes explicitly** — popular, unit-based, general, external — rather than letting users default to attribute thinking.

✅ **Push back on premature subtyping** using Halpin's role-based criterion.

✅ **Use atomic-fact decomposition** — break compound predicates into elementary facts during Step 1.

✅ **Halpin-grounded vocabulary** — fact type, role, object type, reference scheme, objectification, modality. ER vocabulary (table/column/attribute/relationship type) is translated back to Halpin terms.

✅ **Five-source constraint provenance** with dialogue-turn audit trail — every constraint traces back to a CSDP step, a dialogue turn, and (where applicable) the user's actual words.

✅ **Alethic vs deontic modality** — labeled by the user at Step 7e; PyRel emits deontic as `# DEONTIC NOTE:` comments.

✅ **Antipattern flagging** — over-decomposed fact types, attribute-as-subtype confusion, redundant entity types, denormalized-attribute clusters. Flag-then-resolve at Step 7c.

✅ **Stakeholder-reviewable artifact** — the verbalization references the user's own words via `user_quote` provenance, making it especially traceable in text-first workflows.

---

## What the skill does NOT do (v0.1 scope)

❌ **Schema-driven recovery** — use `rai-orm-from-schema` if you have an existing relational schema.

❌ **Multi-language conversations** — English only.

❌ **Diagram rendering** — no SVG/ASCII output. Verbalization is text-only.

❌ **FORML 2 parsing** — textual constraints stored verbatim; no formal-language interpretation.

❌ **Composite value types** (`Address` as a record) — primitive value types only.

❌ **Real-time validation against a database** — text-first has no live data source. Population checks are against the small sample facts the user provides.

❌ **Pytest test suite or Python package** — markdown-driven only.

---

## Invocation patterns

The skill is invoked by asking Claude in a session that has access to this skill. Sample prompts:

### Full Guided run

```
Run the rai-orm-from-text CSDP. I want to model a small university domain
covering students, courses, and enrolments. Use Guided mode. I'll provide
examples as we go.
```

### One-shot with a rich description

```
Run rai-orm-from-text in One-shot mode against the following domain
description. Emit outputs to /tmp/library-model/.

[paste a multi-paragraph description here]
```

### Resume from a partial YAML

```
I have a partial model at /tmp/uni-csdp/model.orm.yaml from a previous
session. Pick up CSDP at Step 6 — propose value, ring, and subtype
constraints, then walk me through Step 7 review.
```

### Just elementary-fact verbalization (Step 1 only)

```
Run only CSDP Step 1 against my domain description. I want to see the
elementary facts you'd extract before committing to the full CSDP.
```

### Generate verbalization only (no PyRel)

```
Run CSDP Steps 1-7 only against my description, then stop and emit just
the verbalization. Skip Step 8 (PyRel translation).
```

(Step 8 produces PyRel from the finalized YAML; if you want to validate the model with a stakeholder before committing to PyRel, stopping at Step 7 is the right cut.)

---

## Workflow integration

| Upstream of this skill | What it expects |
|---|---|
| (None — text/dialogue is the input) | A domain description + your engagement |

| Downstream of this skill | What downstream consumes |
|---|---|
| `rai-pyrel-coding` | The emitted `model.py` for further development |
| `rai-querying` / `rai-graph-analysis` / `rai-prescriptive-*` | Build queries / graphs / optimizations on the designed model |
| `rai-ontology-design` | Enrich or evolve the designed model |
| `rai-orm-from-schema` | If you later need to compare the designed model against an existing schema for the same domain, the schema skill produces a comparable YAML |

For the full skill workflow chain, see the repo-level [`CLAUDE.md`](../../CLAUDE.md).

---

## Related artifacts

| File | Purpose |
|---|---|
| [`SKILL.md`](SKILL.md) | The procedural definition Claude reads when invoked |
| [`PLAN.md`](PLAN.md) | Build plan, design decisions, phases (lessons from v1 baked in) |
| [`references/csdp-workflow.md`](references/csdp-workflow.md) | Full CSDP, prompt-by-prompt |
| [`references/dialogue-patterns.md`](references/dialogue-patterns.md) | Conversational patterns for eliciting facts, reference schemes, etc. |
| [`references/halpin-posture.md`](references/halpin-posture.md) | The Halpin mindset (atomic facts, no attributes, populate-then-constrain) |
| [`references/verbalization-patterns.md`](references/verbalization-patterns.md) | Text-first verbalization additions on top of the shared CNL patterns |
| [`evals/README.md`](evals/README.md) | How to test the skill |
| [`evals/cases.json`](evals/cases.json) | Eval case definitions (T-E1 through T-E5) |
| [`../rai-orm-from-schema/`](../rai-orm-from-schema/) | The companion schema-side skill (shares YAML format, constraint reference, PyRel translation) |
