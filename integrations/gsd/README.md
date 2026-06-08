# `integrations/gsd/` — GSD integration for the RAI ORM skills

This integration wires our two ORM skills — `rai-orm-from-schema` and `rai-orm-from-text` — into the [GSD](https://github.com/open-gsd/gsd-core) (Git. Ship. Done.) phase loop. The result: each phase of an ORM modeling project is plan-able, executable, verifiable, and shippable from inside `claude` without you having to remember the SRP / CSDP step sequence.

> **Walkthrough-first.** The canonical "what does this look like end-to-end" document is [`../../notes/demo/walkthrough.md`](../../notes/demo/walkthrough.md). The contents of this directory exist to make that walkthrough run.

---

## What ships here

| Path | What it is |
|---|---|
| `README.md` | This file |
| `bootstrap.sh` | One-shot script that drops the templates into a project's `.planning/` |
| `agents/rai-orm-verifier.md` | Custom subagent invoked by `/gsd:verify-work`. Runs the 27 format-spec rules + (optional) E1 diff against a reference solution. |
| `templates/project/schema/*.tmpl` | Project-level `.planning/` templates for schema-input projects (SRP) |
| `templates/project/text/*.tmpl` | Project-level `.planning/` templates for text-input projects (CSDP) |
| `templates/phases/schema/*.md` | Per-phase template files (5 phases: discover, lift-explicit, infer, verify, translate) |
| `templates/phases/text/*.md` | Per-phase template files (5 phases: elementary-facts, fact-types, constraints, verify, translate) |

The integration is **markdown + one shell script**. No Node, no Python, no build step.

---

## Install (one-time)

You need three things on the machine: Claude Code, GSD, and our skills.

```bash
# 1. Claude Code itself (skip if already installed)
brew install --cask claude-code

# 2. GSD (installs slash commands + workflows into ~/.claude)
npx @opengsd/gsd-core@latest --claude --local

# 3. Our skills + this integration (today: branch clone; later: plugin marketplace)
git clone -b an-orm-skill https://github.com/RelationalAI/rai-agent-skills ~/rai-skills

ln -s ~/rai-skills/skills/rai-orm-from-schema ~/.claude/skills/rai-orm-from-schema
ln -s ~/rai-skills/skills/rai-orm-from-text   ~/.claude/skills/rai-orm-from-text
ln -s ~/rai-skills/integrations/gsd           ~/.claude/gsd-rai
```

After this, every project you start has GSD's slash commands, our ORM skills, and the bootstrap script available.

---

## Use (per project)

```bash
mkdir orm-build && cd orm-build
cp /path/to/your/schema.sql .

# Drop the schema-flow templates into ./.planning/ and the verifier into ./.claude/agents/
bash ~/.claude/gsd-rai/bootstrap.sh --schema schema.sql
```

Or for the text-first flow:

```bash
mkdir orm-build && cd orm-build
echo "We sell books to customers. Each order has a date..." > domain.md

bash ~/.claude/gsd-rai/bootstrap.sh --text domain.md
```

Then enter Claude Code and run the GSD phase loop:

```bash
claude
> /gsd:new-project
> /gsd:plan-phase 1
> /gsd:execute-phase 1
> /gsd:verify-work 1
> /gsd:ship 1
# ... repeat for phases 2 through 5
```

The full walkthrough — including the verifier output, the resume-tomorrow story, and what the bootstrap actually prints — is in [`../../notes/demo/walkthrough.md`](../../notes/demo/walkthrough.md).

---

## Phase pipeline

Both flows ship as **five phases**. The verb sequence per phase differs:

| Flow | Per-phase verbs | Why |
|---|---|---|
| **Schema (SRP)** | `plan → execute → verify → ship` | Deterministic. Lift rules (PK→preferred UC, NOT NULL→mandatory, CHECK→value) follow from defaults locked at `/gsd:new-project`. Nothing to discuss per phase. |
| **Text (CSDP)** | `discuss → plan → execute → verify → ship` | Dialogue. CSDP Steps 1, 4, 6 are conversations with the domain expert. Discuss is the methodology, not a checkpoint. |

The per-phase template files declare which verbs apply via a top-line `verbs:` marker.

### Schema (SRP) → 5 phases

| Phase | SRP step(s) | Output |
|---|---|---|
| 1 — discover | Steps 1-3 (inventory + object/fact types) | Partial `model.orm.yaml`: object types + binary fact types, no constraints |
| 2 — lift-explicit | Step 4 | YAML extended with explicit-source UC / mandatory / value constraints |
| 3 — infer | Steps 5-7 (probe + library + LLM tier + antipatterns) | YAML extended with sample / common-sense / llm-inferred constraints; antipatterns flagged |
| 4 — verify | Steps 8-9 (verbalize + user decisions) | Verbalization shown; user confirms; verifier runs 27 rules + E1 diff |
| 5 — translate | Step 10 | Final `model.py` |

### Text (CSDP) → 5 phases

| Phase | CSDP step(s) | Output |
|---|---|---|
| 1 — elementary-facts | Step 1 (verbalize + populate) | Locked vocabulary + sample fact instances |
| 2 — fact-types | Steps 2-3 (draw + combine + derive) | YAML: candidate object types + binary fact types |
| 3 — constraints | Steps 4-6 (uniqueness + mandatory + value + subtyping) | YAML extended with constraints |
| 4 — verify | Step 7 (final review + modality labelling) | Verbalization; user labels alethic/deontic; verifier runs |
| 5 — translate | Step 8 | Final `model.py` |

---

## The verifier agent

`agents/rai-orm-verifier.md` is a standard Claude Code subagent file. When `/gsd:verify-work` is invoked, GSD spawns this agent in a fresh context. The agent:

1. Reads the phase output (`model.orm.yaml` in the phase directory).
2. Runs the 27 format-spec validation rules from `representation-format.md`.
3. If a reference solution exists at `evals/expected/<name>.orm.yaml`, runs the E1 diff.
4. Counts `warning:` flags against any expected antipattern counts.
5. Emits a `## Verification Complete` block (per GSD's agent-contracts convention) with pass/fail per rule.

**On first runs (no reference solution yet):** the verifier reports `E1 diff: skipped (no reference)` rather than failing. After human review of the first emitted YAML, that output becomes the reference for future runs.

---

## What this integration deliberately does **not** do

- It does **not** vendor GSD. GSD installs separately via `npx`.
- It does **not** modify our skills' `SKILL.md` files. The skills are loaded as-is by Claude Code.
- It does **not** ship its own slash commands. All orchestration uses GSD's existing `/gsd:*` commands.
- It does **not** depend on Node, Python, or a templating engine beyond `sed`.

---

## Known gaps (resolve after first end-to-end run)

These don't block the templates from being usable, but they may need adjustment after the first real run against GSD:

1. **PLAN.md seeding.** Whether `/gsd:plan-phase N` reads our `templates/phases/.../<N>-*.md` as a pre-seed for `PLAN.md`, or whether the planner subagent should be told (via PROJECT.md) to load it as guidance. The phase files include enough structure to work either way.
2. **Verifier discovery.** Whether GSD's `verify-work` workflow auto-discovers our `rai-orm-verifier` from `.claude/agents/`, or whether the agent has to be referenced from `.planning/config.json`. The agent file is in standard Claude Code subagent format either way.
3. **6d spot-check UX.** When the inference phase fires the LLM-tier spot-check, whether the user sees it inline in `/gsd:execute-phase 3` or as a separate prompt. Phase 3's template documents what should happen; the exact surfacing is GSD's call.

See `notes/demo/walkthrough.md` §9 for the wider TBD list.
