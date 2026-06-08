# Walkthrough: ORM + PyRel modeling via GSD (text flow)

End-to-end walkthrough for the text-first (CSDP) ORM modeling pipeline. Parallel to the schema flow ([`walkthrough.md`](walkthrough.md)) — same 5 phases, same GSD machinery — but the input is natural language and **discuss is essential at every modeling phase**.

> If you've already done the schema walkthrough, sections §1 and §6–§7 are nearly identical here; the meat is §3–§5 where the text flow differs.

---

## 1. Prerequisites (one-time, ~5 minutes)

Same as the schema walkthrough. If you've already installed GSD and symlinked the skills + integration, skip to §2.

```bash
brew install --cask claude-code

cd ~
npx --yes @opengsd/gsd-core@latest --claude

git clone -b an-orm-skill https://github.com/RelationalAI/rai-agent-skills ~/rai-skills

ln -s ~/rai-skills/skills/rai-orm-from-schema ~/.claude/skills/rai-orm-from-schema
ln -s ~/rai-skills/skills/rai-orm-from-text   ~/.claude/skills/rai-orm-from-text
ln -s ~/rai-skills/integrations/gsd           ~/.claude/gsd-rai
```

> **Reminders.** Slash commands use **hyphens** (`/gsd-plan-phase`). Install GSD without `--local` so it lives at `~/.claude/`.

---

## 2. The scenario

> *"I want to build a conceptual model for a domain I can describe but don't have a schema for. I'll dialogue with a domain expert through Claude Code, and the result should be an ORM 2 model + PyRel translation."*

We'll use the **conference-talk-tracking** fixture that ships with `rai-orm-from-text` — a small but substantive domain (5 entity types, ~10 fact types, ~20 constraints in the reference solution). The skill has both a seed description (`fixtures/synthetic_good_user/domain.md`) and a hand-written reference dialogue + reference YAML for E1 diff. That means the verifier's E1 step actually runs against a real reference, not "skipped (no reference)."

The seed description is the kind of paragraph a real user would write to start a CSDP project — a few paragraphs covering the entities, the key relationships, and a hint of constraints (uniqueness, soft vs hard rules):

```
We track academic and industry conferences. Each conference has multiple tracks
(for example, "ML Track" or "Systems Track" at DataConf 2026). Each track schedules
talks in slot order — a talk like "Embeddings at Scale" might be the third talk
in the ML Track.

Each talk is given by a speaker. ...
```

The full description is in `~/rai-skills/skills/rai-orm-from-text/evals/fixtures/synthetic_good_user/domain.md`. We'll `cp` it in §3 — exactly parallel to how the schema flow copies `schema.sql`.

> **Why use a fixture rather than writing your own?** Two reasons. First, having a reference solution means the verifier's E1 diff actually runs end-to-end — you see a real verdict, not a skip. Second, the fixture's expected dialogue (in `dialogue.md` next to `domain.md`) is the same one the eval suite uses, so the demo's discuss-phase outputs are comparable to known-good results. Substitute your own domain if you have one, but expect "E1 diff: skipped (no reference)" rather than a real verdict.

---

## 3. Step 0 — Bootstrap a project (text flow)

```bash
mkdir -p ~/tmp/orm-text-build && cd ~/tmp/orm-text-build

cp ~/rai-skills/skills/rai-orm-from-text/evals/fixtures/synthetic_good_user/domain.md .

bash ~/.claude/gsd-rai/bootstrap.sh --text domain.md
```

The `--text` flag drops the **text-flow** templates: a different `PROJECT.md` (vision says "build from dialogue"), a different `REQUIREMENTS.md` (no DDL lift rules), a different `ROADMAP.md` (the 5 phases are named `01-elementary-facts → 02-fact-types → 03-constraints → 04-verify → 05-translate`), and per-phase templates that include a `discuss:` block.

Real output:

```
✓ Created .planning/PROJECT.md         (Conceptual Schema Design Procedure (CSDP) for orm-text-build)
✓ Created .planning/REQUIREMENTS.md    (antipattern flags, dialect, modality defaults)
✓ Created .planning/ROADMAP.md         (5 phases — discuss, plan, execute, verify, ship)
✓ Created .planning/CONTEXT.md         (Halpin posture, terminology preferences)
✓ Created .planning/phases/            (5 phase plans seeded)
✓ Created .claude/agents/rai-orm-verifier.md

Flow:   Conceptual Schema Design Procedure (CSDP)
Input:  domain.md

Next:
  claude
  > /gsd:new-project
```

You can also bootstrap with **no input file**:

```bash
bash ~/.claude/gsd-rai/bootstrap.sh --text
```

That's the "I'll talk it through from scratch" mode — the domain description gets elicited entirely from the Discuss step at phase 1.

> Same "Next:" caveat as the schema walkthrough — we skip `/gsd-new-project` and go straight to phase 1's Discuss.

---

## 4. Step 1 — Enter Claude Code, go to phase 1 Discuss

```bash
claude
```

Inside Claude Code:

```
> /gsd-discuss-phase 1
```

This is the **distinguishing moment** of the text flow. Discuss isn't a checkpoint — it's the methodology. GSD spawns a fresh-context discussion subagent that reads `domain.md`, our `01-elementary-facts.md` phase template, and engages you (acting as modeler) in CSDP Step 1: *verbalize elementary facts*.

Expect a dialogue along these lines:

```
Subagent: I read your domain description. Before drawing fact types, I'd like to
ground the vocabulary in concrete examples. Can you give me 3-5 specific facts you'd
like the model to capture? Like: "Conference 'DataConf 2026' has track 'ML Track'"
— not "Conferences have tracks."

You: DataConf 2026 has the ML Track and the Systems Track. The talk "Embeddings at
Scale" is given by Alice Chen and is scheduled as the 3rd talk in the ML Track at
DataConf 2026. The talk "Optimizing Kernel I/O" is scheduled as the 1st talk in
the Systems Track.

Subagent: Good. Verbalizing back: 'Conference DataConf 2026 has Track ML Track.'
'Talk "Embeddings at Scale" is given by Speaker Alice Chen.' 'Talk "Embeddings at
Scale" is the 3rd talk in Track ML Track at Conference DataConf 2026.' That last
one is ternary — Talk, Track, Conference, plus a slot integer. Is that how you'd
say it, or do you split conference and track-position into two facts?

You: Split them. The track already belongs to a conference; once you know the track,
the conference is implied. So: "Talk X is the Nth talk in Track Y."

Subagent: Locked. I'll record the constraint "Track is identified by name within a
Conference" in CONTEXT.md so a talk's track position doesn't redundantly carry the
conference.
```

Outputs of Discuss land in:

- `.planning/phases/01-elementary-facts/DIALOGUE.md` — the transcript.
- `.planning/CONTEXT.md` — locked vocabulary updates (canonical verbs, preferred entity names, anything the expert overrode).

---

## 5. Phase 1 plan → execute → verify → ship

After Discuss closes, the rest of phase 1 is the standard GSD loop:

### Plan

```
> /gsd-plan-phase 1
```

Reads the Discuss outputs and decomposes the abstraction work for the executor.

### Execute

```
> /gsd-execute-phase 1
```

Loads `rai-orm-from-text`, runs CSDP Step 1 internally, emits a partial `model.orm.yaml` at `.planning/phases/01-elementary-facts/`:

```yaml
version: 1
source:
  kind: text-conversation
  dialogue_anchor: .planning/phases/01-elementary-facts/DIALOGUE.md
  frozen_vocab_at: "2026-06-08T..."

object_types:
  - id: conference
    name: Conference
    kind: entity
    # ... matched against the expert's vocabulary
  - id: track
    name: Track
    kind: entity
  - id: talk
    name: Talk
    kind: entity
  - id: speaker
    name: Speaker
    kind: entity

fact_instances:
  - reading: "Conference DataConf 2026 has Track ML Track."
    anchor: { dialogue: 01-elementary-facts/DIALOGUE.md, line: 14 }
  - reading: "Talk Embeddings at Scale is given by Speaker Alice Chen."
    anchor: { dialogue: 01-elementary-facts/DIALOGUE.md, line: 15 }
  # ...
```

> Note `kind: text-conversation` (not `ddl-file`) and the new `fact_instances:` section — both are the text-flow extensions of the format spec.

### Verify

```
> /gsd-verify-work 1
```

The `rai-orm-verifier` runs the format-spec rules scoped to phase 1's text-flow output. Expects something like:

```
## Verification Complete
✓ 10/10 format-spec rules applied (phase 1 text-flow scope)
✓ Object types: <N> entity
✓ Fact instances: <N> (all verbalize cleanly, all dialogue-anchored)
- E1 diff: skipped (no reference solution yet)

No issues found. Phase 1 ready to ship.
```

### Ship (optional)

```
> /gsd-ship 1
```

Same caveat as the schema walkthrough — skip if you don't want a per-phase commit. Phase 2 still works without it.

---

## 6. Phases 2–5 — same shape, every phase has a Discuss

For phases 2 and 3, **always run Discuss before Plan**:

```
> /gsd-discuss-phase 2     # CSDP Steps 2-3: draw fact types + populate
> /gsd-plan-phase 2
> /gsd-execute-phase 2
> /gsd-verify-work 2

> /gsd-discuss-phase 3     # CSDP Steps 4-6: uniqueness + mandatory + value + subtypes
> /gsd-plan-phase 3
> /gsd-execute-phase 3
> /gsd-verify-work 3
```

Phase 3 Discuss is the longest — it walks every fact type with the expert ("is this role unique? mandatory? what values are allowed?"). This is where the LLM tier surfaces its proposals (if `enable_llm_tier: yes` was locked at project init) with `rationale_world_fact:` per proposal.

For phases 4 and 5, **Discuss is optional** (Phase 4 only needs verbalization walk-through, which can happen inline in Verify; Phase 5 is mechanical PyRel emission):

```
> /gsd-plan-phase 4
> /gsd-execute-phase 4
> /gsd-verify-work 4

> /gsd-plan-phase 5
> /gsd-execute-phase 5
> /gsd-verify-work 5
```

Phase 5 emits `model.py` at the project root.

---

## 7. End state — what gets shipped

```
orm-text-build/
  domain.md                              (input, possibly extended by Discuss)
  model.orm.yaml                          (the ORM model — same format as schema flow)
  model.verbalization.txt                 (Halpin-style CNL)
  model.py                                (PyRel)
  .planning/
    PROJECT.md, REQUIREMENTS.md, ROADMAP.md, CONTEXT.md
    phases/
      01-elementary-facts/   PLAN.md DIALOGUE.md SUMMARY.md model.orm.yaml
      02-fact-types/         PLAN.md DIALOGUE.md SUMMARY.md
      03-constraints/        PLAN.md DIALOGUE.md SUMMARY.md
      04-verify/             model.verbalization.txt
      05-translate/          model.py
```

The `DIALOGUE.md` files are the auditable trail — every constraint with `source: user-supplied` traces back to a specific line in a specific DIALOGUE.md.

---

## 8. Coming back tomorrow

```bash
cd ~/tmp/orm-text-build
claude
> /gsd-resume-work
```

GSD reads `.planning/STATE.md` and resumes. The locked vocabulary, the dialogue transcripts, the partially-built YAML — all preserved in markdown.

For text flow specifically, the resume is more valuable than the schema flow: a multi-day modeling project where you talk to the expert across several sessions is the *natural* mode of CSDP. The schema flow can usually finish in one session; the text flow may not, and shouldn't be expected to.

---

## 9. Schema vs text — side by side

| | **Schema flow** | **Text flow** |
|---|---|---|
| Input | DDL / introspection dump / CSV bundle | Domain description + ongoing dialogue |
| Skill | `rai-orm-from-schema` (SRP) | `rai-orm-from-text` (CSDP) |
| Bootstrap flag | `--schema <path>` | `--text [<path>]` |
| Phase 1 name | `01-discover` | `01-elementary-facts` |
| Phase 3 name | `03-infer` | `03-constraints` |
| Verbs per phase | 4 (plan, execute, verify, ship) | 5 (discuss, plan, execute, verify, ship) for phases 1–3; 4 for phases 4–5 |
| Discuss artifact | none | `DIALOGUE.md` per phase |
| Source provenance dominant | `explicit` (DDL-lifted) | `user-supplied` (expert-confirmed) |
| Output format | YAML `source.kind: ddl-file` | YAML `source.kind: text-conversation` |
| Final outputs | `model.orm.yaml`, `model.verbalization.txt`, `model.py` | (same) |

Both flows produce the same triple of artifacts. The methodology differs; the integration's GSD-side machinery is identical.

---

## 10. What this walkthrough deliberately glosses over

- The Discuss subagent's exact prompting style — the example dialogue in §4 is illustrative, not a transcript. The real subagent's questions depend on what the expert says.
- Multi-session resume edge cases (what if Discuss from yesterday is incomplete?). The `DIALOGUE.md` files survive; resuming Discuss appends rather than restarts.
- The text-flow extensions to the format spec (`source.kind: text-conversation`, `fact_instances[]`, dialogue anchoring) are documented in `rai-orm-from-text/references/representation-format.md`. Refer there if the YAML structure in §5 surprises you.
