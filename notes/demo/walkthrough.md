# Walkthrough: ORM + PyRel modeling via GSD (schema flow)

End-to-end walkthrough for the schema-first ORM modeling pipeline. The text-first walkthrough is in [`walkthrough-text.md`](walkthrough-text.md).

---

## 1. Prerequisites (one-time, ~5 minutes)

```bash
# Claude Code itself
brew install --cask claude-code

# GSD — install globally so it's available from any project
cd ~
npx --yes @opengsd/gsd-core@latest --claude

# Confirm GSD landed at ~/.claude/
ls ~/.claude/commands/gsd/ | head
ls ~/.claude/gsd-core/

# Our ORM skills + GSD integration (today — branch clone; later — plugin marketplace)
git clone -b an-orm-skill https://github.com/RelationalAI/rai-agent-skills ~/rai-skills

ln -s ~/rai-skills/skills/rai-orm-from-schema ~/.claude/skills/rai-orm-from-schema
ln -s ~/rai-skills/skills/rai-orm-from-text   ~/.claude/skills/rai-orm-from-text
ln -s ~/rai-skills/integrations/gsd           ~/.claude/gsd-rai
```

After this, every project you start has GSD's slash commands and our ORM skills available.

> **Two gotchas worth knowing.** First, GSD's slash commands use **hyphens** (`/gsd-plan-phase`), not colons. Second, `npx ... --claude --local` installs GSD to the *current directory's `.claude/`* — useful for trying it in isolation, awkward for a demo. Use plain `--claude` for a global install.

---

## 2. The scenario

> *"I have a relational schema in `./schema.sql`. I want an ORM 2 conceptual model + PyRel translation, verified against our quality rules."*

We'll use the synthetic e-commerce fixture from `~/rai-skills/skills/rai-orm-from-schema/evals/fixtures/synthetic/schema.sql` — 21 tables, several deliberate antipatterns.

---

## 3. Step 0 — Bootstrap a project

```bash
mkdir -p ~/tmp/orm-build && cd ~/tmp/orm-build
cp ~/rai-skills/skills/rai-orm-from-schema/evals/fixtures/synthetic/schema.sql .

bash ~/.claude/gsd-rai/bootstrap.sh --schema schema.sql
```

Our bootstrap script drops ORM-tailored templates into `.planning/` and the verifier agent into `.claude/agents/`. Real output:

```
✓ Created .planning/PROJECT.md         (Schema Recovery Procedure (SRP) for orm-build)
✓ Created .planning/REQUIREMENTS.md    (antipattern flags, dialect, modality defaults)
✓ Created .planning/ROADMAP.md         (5 phases — plan, execute, verify, ship)
✓ Created .planning/CONTEXT.md         (Halpin posture, terminology preferences)
✓ Created .planning/phases/            (5 phase plans seeded)
✓ Created .claude/agents/rai-orm-verifier.md

Flow:   Schema Recovery Procedure (SRP)
Input:  schema.sql

Next:
  claude
  > /gsd:new-project
```

No phase-loop work has happened yet — only files. You can edit any of the templates before proceeding.

> **Note on the "Next:" hint.** The bootstrap currently suggests `/gsd:new-project`, but for the schema flow we actually go straight to `/gsd-plan-phase 1` (see §4). `/gsd-new-project` would conflict with the `.planning/` content the bootstrap just created.

---

## 4. Step 1 — Enter Claude Code, skip `new-project`

```bash
claude
```

Inside Claude Code:

```
> /gsd-plan-phase 1
```

**We skip `/gsd-new-project`** because our bootstrap already populated `.planning/` and `/gsd-new-project` refuses to re-initialize a project that already has those files. The bootstrap *is* the project init for our integration.

GSD spawns a fresh-context planner subagent. It reads PROJECT.md + REQUIREMENTS.md + CONTEXT.md + the schema + our pre-seeded `.planning/phases/01-discover/PLAN.md`, refines the plan, and either extends or honors that file.

---

## 5. Steps 2–N — the phase loop in action

GSD's per-phase verb sequence is **discuss → plan → execute → verify → ship**. In the schema flow shown here, **discuss is skipped** — the lift rules (PK → preferred UC, NOT NULL → mandatory, CHECK → value constraint) are deterministic from the defaults locked in `CONTEXT.md`. Nothing to discuss per phase. So each phase runs on four verbs: **plan → execute → verify → ship**.

> The text-first flow keeps all five verbs. CSDP Step 1 ("verbalize elementary facts with the expert") and Step 4 ("confirm uniqueness") are dialogue — no deterministic substitute. Asymmetry reflects where each methodology gets its evidence: SRP from the schema, CSDP from the expert.

Concrete view of **phase 1** (discover):

### Plan

```
> /gsd-plan-phase 1
```

A planner subagent decomposes the work and writes `.planning/phases/01-discover/PLAN.md`. Our pre-seeded template (with `verbs:`, `skill:`, `srp_steps:` headers) survives as the planning anchor.

### Execute

```
> /gsd-execute-phase 1
```

A fresh-context executor loads the `rai-orm-from-schema` skill and runs SRP Steps 1–3. Output appears in `.planning/phases/01-discover/`:

```
model.orm.yaml          (object types + binary fact types, no constraints yet)
```

A real run on the synthetic fixture produces a YAML starting like:

```yaml
version: 1
source:
  kind: ddl-file
  dialect: ansi
  scope:
    tables: ["*"]
  introspected_at: "2026-06-08T00:00:00Z"
  confidence: standard
  mode: one-shot

object_types:
  - id: string
    name: String
    kind: value
    primitive: String
  # ... value types lazily, then entity types
```

You see a high-level summary in the terminal but not the per-token chatter — that's contained in the subagent's fresh context.

### Verify

```
> /gsd-verify-work 1
```

This is where the **`rai-orm-verifier` agent earns its keep**. It walks the format-spec rules and emits the GSD-contract completion marker:

```
## Verification Complete
✓ 13/13 format-spec rules applied (phase 1 scope)
✓ Object types: <N entity> + <N value>
✓ Fact types: <N>
- Constraints: empty (as expected for phase 1)
- E1 diff: skipped (no reference solution yet — first run on this schema)

No issues found. Phase 1 ready to ship.
```

If anything had failed, the verifier emits `## Issues Found` with diagnoses instead.

### Ship

```
> /gsd-ship 1
```

Phase 1 gets committed to git and archived under `.planning/phases/01-discover/SHIPPED.md`. Roadmap status updates.

> If you're just trying the demo and don't want a commit per phase, you can skip `/gsd-ship N`. The next `/gsd-plan-phase N+1` still works; GSD just sees the previous phase as "not yet shipped."

### Repeat for phases 2–5

Same four verbs each. Highlights of later phases:

- **Phase 2 (lift-explicit)** extends the YAML with `source: explicit` constraints from the DDL.
- **Phase 3 (infer)** is where sample probes, the common-sense library, and (if enabled) the LLM tier propose additional constraints.
- **Phase 4 (verify)** prints the full verbalization and walks you through accepting or rejecting any remaining proposals.
- **Phase 5 (translate)** emits `model.py` (PyRel) at the project root.

---

## 6. End state — what gets shipped

After `/gsd-ship 5`, your project contains:

```
orm-build/
  schema.sql                              (input, unchanged)
  model.orm.yaml                          (output — the ORM model)
  model.verbalization.txt                 (output — Halpin-style CNL)
  model.py                                (output — PyRel)
  .planning/
    PROJECT.md, REQUIREMENTS.md, ROADMAP.md, CONTEXT.md
    phases/
      01-discover/    PLAN.md SUMMARY.md SHIPPED.md model.orm.yaml
      02-lift-explicit/  ...
      03-infer/          ...
      04-verify/         model.verbalization.txt
      05-translate/      model.py
```

GSD also opens a PR if the project is a git repo, with a summary of the E1 verdict (passed / failed / partial) and the antipattern catalog (which warnings fired, what default resolutions were applied).

---

## 7. Coming back tomorrow

```bash
cd ~/tmp/orm-build
claude
> /gsd-resume-work
```

GSD reads the `.planning/` state and tells you where you left off (e.g., "you finished phase 3, ready for `/gsd-plan-phase 4`"). The skill context, the locked decisions in CONTEXT.md, the antipattern flags from Phase 3 — all preserved in markdown. The conversation state is gone (Claude doesn't remember yesterday) but the *project state* survives.

This is GSD's whole value proposition over a single long Claude session.

---

## 8. What this walkthrough deliberately glosses over

- **The verifier's E1 diff** needs an `evals/expected/<name>.orm.yaml` to diff against; for a first-time run on a new schema, there isn't one — the verifier reports "no reference; skipping E1" rather than failing. After human review of the first run, that emitted YAML *becomes* the reference solution for future runs.
- **CSDP path** (text-first) follows the same five-phase shape — `bootstrap.sh --text` instead of `--schema`, different REQUIREMENTS.md template — but uses the **full five verbs per phase**. Steps 1, 4, and 6 of CSDP are dialogue with a domain expert, so discuss is not optional there. See [`walkthrough-text.md`](walkthrough-text.md).
- **PR opening** assumes the project is a git repo; if it's not, `/gsd-ship` just commits locally without a PR.
- **Skip-ship demo flow.** A pragmatic demo skips every `/gsd-ship N` to avoid PRs for throwaway runs. Nothing else in the integration breaks.
