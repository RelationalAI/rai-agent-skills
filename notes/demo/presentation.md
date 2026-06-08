---
marp: true
paginate: true
size: 16:9
header: ""
footer: "Internal demo"
style: |
  /*
   * RelationalAI Marp theme — inline for portability.
   *
   * Brand palette extracted from RAI Service Review.pptx:
   *   navy            #070F4D   (title-slide background)
   *   coral / orange  #EA664D   (brand mark + accents)
   *   white           #FFFFFF
   *   text dark       #0F1632   (body text on white)
   *   muted grey      #5C6470
   *
   * Typography: bold Helvetica/Arial display headings.
   * Assets in ./assets/ — referenced via background-image.
   *
   * Render:
   *   marp presentation.md            # HTML preview
   *   marp presentation.md --pdf      # PDF
   *   marp presentation.md --pptx     # PowerPoint
   *   marp -s .                       # live server
   */

  /* ---------- defaults: white content slide ---------- */
  section {
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    background: #FFFFFF;
    color: #0F1632;
    font-size: 22px;
    line-height: 1.45;
    padding: 56px 64px 48px 64px;
    background-image: url('./assets/logo-dark-small.png');
    background-repeat: no-repeat;
    background-position: top 28px right 64px;
    background-size: 180px auto;
  }
  section h1 {
    color: #0F1632;
    font-weight: 800;
    font-size: 36px;
    border-bottom: none;
    margin: 16px 0 18px 0;
    letter-spacing: -0.5px;
  }
  section h2 {
    color: #EA664D;
    font-weight: 600;
    font-size: 22px;
    margin: 12px 0 8px 0;
  }
  section h3 {
    color: #5C6470;
    font-weight: 500;
    font-size: 19px;
    margin: 10px 0 6px 0;
  }
  section ul, section ol { margin: 6px 0; padding-left: 24px; }
  section li { margin: 5px 0; }
  section strong { color: #EA664D; font-weight: 700; }
  section em { color: #0F1632; font-style: italic; }
  section code {
    background: #F4F4F6;
    color: #0F1632;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.9em;
    font-family: 'Menlo', 'Consolas', monospace;
  }
  section pre code {
    background: #F4F4F6;
    color: #0F1632;
    padding: 12px;
    border-radius: 4px;
    display: block;
    font-size: 0.85em;
    border-left: 3px solid #EA664D;
  }
  section table {
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 19px;
    width: 100%;
  }
  section th {
    background: #070F4D;
    color: #FFFFFF;
    padding: 6px 10px;
    text-align: left;
    font-weight: 700;
  }
  section td {
    padding: 5px 10px;
    border-bottom: 1px solid #E5E7EB;
    vertical-align: top;
  }
  section blockquote {
    border-left: 4px solid #EA664D;
    padding: 4px 12px;
    margin: 12px 0;
    color: #4B4B4B;
    font-style: italic;
  }
  section footer { color: #5C6470; font-size: 0.7em; }
  section::after { color: #5C6470; font-size: 0.7em; }

  /* ---------- title slide ---------- */
  section.title {
    background: #070F4D !important;
    color: #FFFFFF !important;
    padding: 0 !important;
    background-image:
      url('./assets/logo-white.png'),
      url('./assets/title-decoration.png') !important;
    background-repeat: no-repeat, no-repeat !important;
    background-position:
      top 36px left 64px,
      center right -40px !important;
    background-size:
      220px auto,
      auto 88% !important;
  }
  section.title > * {
    margin-left: 64px !important;
    max-width: 50% !important;
  }
  section.title h1 {
    color: #FFFFFF !important;
    border-bottom: none !important;
    font-weight: 800 !important;
    font-size: 50px !important;
    letter-spacing: -0.5px !important;
    line-height: 1.15 !important;
    margin: 280px 0 12px 64px !important;
    max-width: 50% !important;
  }
  section.title h2 {
    color: #EA664D !important;
    font-weight: 400 !important;
    font-style: italic !important;
    font-size: 22px !important;
    margin: 0 0 4px 64px !important;
    max-width: 50% !important;
  }
  section.title p {
    color: #FFFFFF !important;
    font-size: 18px !important;
    margin-left: 64px !important;
  }
  section.title strong {
    color: #FFFFFF !important;
    font-weight: 700 !important;
  }
  section.title footer { display: none !important; }
  section.title::after { display: none !important; }

  /* ---------- dense slide variant (tighter table + body) ---------- */
  section.dense { font-size: 19px; }
  section.dense table { font-size: 16px; }
  section.dense th, section.dense td { padding: 4px 8px; }
---

<!-- _class: title -->
<!-- _paginate: false -->

# Integrating ORM to PyRel with GSD

## A walkthrough

**RelationalAI · Internal demo**

---

# (a) Terry Halpin's approach

**Object-Role Modeling (ORM 2)** — fact-based, attribute-free conceptual modeling.

- Inherits from NIAM (1970s); refined by Halpin from ~2001
- **No attributes** — facts are atomic sentences with named roles
- **Verbalization first-class** — every element renders as ordinary English
- Stakeholders validate by *reading*, not by interpreting diagrams

> *"Each Customer has email EmailAddress. Each Customer has at most one EmailAddress."*

One model → verbalises, diagrams, and translates to relational, UML, XSD, or **PyRel**.

---

# (a) The CSDP — 7 steps

Halpin's *Conceptual Schema Design Procedure*, optimised for domain-expert dialogue:

1. **Elementary facts** — verbalise concrete examples as atomic sentences
2. **Draw fact types + population check** — predicates with roles; populate
3. **Combine + derive** — merge redundant types; flag arithmetic derivations
4. **Uniqueness + arity** — which role(s) unique; correct decomposition
5. **Mandatory + logical derivations** — must-played roles; logically-implied facts
6. **Value + set-comparison + subtyping** — enums, ranges, subset/exclusion, subtypes
7. **Other + final review** — frequency, ring, deontic; modality labelling

> *Populate before you constrain.* Sample population = evidence; constraints = conjectures.

---

# Our ORM/PyRel skills

Two complementary Claude skills, built over the past weeks:

| Skill | Input | Workflow |
|---|---|---|
| **rai-orm-from-schema** | Existing relational schema (DDL · live DB · CSV) | Schema Recovery Procedure — 10 steps |
| **rai-orm-from-text** | Natural-language dialogue with a domain expert | Halpin's CSDP — 7+1 steps |

**Both produce the same triple:** `model.orm.yaml` · `model.verbalization.txt` · `model.py` (PyRel)

## Loading them in Claude Code

```bash
# Skills currently live on a branch (not yet on main):
git clone -b an-orm-skills https://github.com/RelationalAI/rai-agent-skills ~/rai-skills

# Symlink into Claude Code's discovery path:
ln -s ~/rai-skills/skills/rai-orm-from-schema ~/.claude/skills/rai-orm-from-schema
ln -s ~/rai-skills/skills/rai-orm-from-text   ~/.claude/skills/rai-orm-from-text

# Then in any project:
claude
> Use rai-orm-from-schema to recover an ORM model from ./schema.sql
```

---

# (b) GSD — Git. Ship. Done.

**Spec-driven development framework** wrapping AI coding agents (Claude, Cursor, Gemini, Codex, …).

**The three problems it targets:**

- **Context rot** — quality degrades as AI sessions grow long
- **No cross-session memory** — context resets every conversation
- **No verification** that what was built actually works

**The mechanism:** fresh-context subagents per task, persistent state in markdown, a verify step before *done*.

**Traction:** ~59k stars · used at Amazon, Google, Shopify, Webflow · 1100+ markdown templates (Node.js is just install plumbing).

---

# (b) GSD — the phase loop

Each milestone repeats five steps:

| Phase | Command | Output |
|---|---|---|
| **Discuss** | `/gsd:discuss-phase` | Locked decisions → `CONTEXT.md` |
| **Plan** | `/gsd:plan-phase` | Decomposed work → `PLAN.md` |
| **Execute** | `/gsd:execute-phase` | Fresh-context subagents build the artifact |
| **Verify** | `/gsd:verify-work` | UAT + diagnosis → `UAT.md` + fix plans |
| **Ship** | `/gsd:ship` | PR opened, phase archived |

Project state lives in `.planning/` (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md) — survives session boundaries.

---

# Using GSD — install once, run per-project

## One-time install

```bash
npx --yes @opengsd/gsd-core@latest --claude
```

Drops slash commands at `~/.claude/commands/gsd/` and workflows at `~/.claude/gsd-core/`.

## Per-project loop

```bash
cd my-orm-project
claude
> /gsd-new-project          # creates .planning/ — vision, requirements, roadmap
> /gsd-plan-phase 1         # decomposes phase 1 into PLAN.md
> /gsd-execute-phase 1      # fresh-context subagents do the work
> /gsd-verify-work 1        # UAT + diagnostics
> /gsd-ship 1               # PR + archive
```

State in `.planning/` survives session boundaries — `claude` next week resumes where you left off.

---

<!-- _class: dense -->

# The ORM phase pipeline — same shape, two flows

Both flows run as **5 phases** through GSD's loop. The methodology's fine-grained steps (10 SRP, 7+1 CSDP) live *inside* each phase's executor.

> **The 5-phase decomposition is ours, not Halpin's.** SRP has 10 steps, CSDP has 7+1. We grouped them into 5 phases each, then aligned the phase numbers — a UX choice for parallel demos and shared mental model, not a methodology claim.

| # | Schema flow (SRP) | SRP steps | Text flow (CSDP) | CSDP steps |
|---|---|---|---|---|
| 1 | discover | 1–3 (object + fact types) | elementary-facts | 1 (verbalize + populate) |
| 2 | lift-explicit | 4 (PK/FK/UNIQUE/NN/CHECK → constraints) | fact-types | 2–3 (draw + combine + derive) |
| 3 | infer | 5–7 (probe + library + LLM + antipatterns) | constraints | 4–6 (UC + mandatory + value + subtypes) |
| 4 | verify | 8–9 (verbalize + accept/reject) | verify | 7 (final review + modality) |
| 5 | translate | 10 (PyRel) | translate | 8 (PyRel) |

## Per-phase verb sequence — schema *skips* Discuss; text keeps it

| Flow | Verbs per phase | Why |
|---|---|---|
| **Schema** | `plan → execute → verify → ship` (4) | Deterministic. Lift rules are locked at project init; nothing to discuss per phase. |
| **Text** | `discuss → plan → execute → verify → ship` (5) | CSDP Steps 1, 4, 6 *are* dialogue. Discuss is the methodology, not a checkpoint. |

> Asymmetry follows the evidence: SRP reads it from the schema; CSDP elicits it from the expert.

---

<!-- _class: dense -->

# (c) Three ways to make the skills available

For Claude Code to use a skill, its content has to live in a directory Claude scans — `.claude/skills/<name>/`. Three ways to get it there:

| | **a) Copy ad-hoc** | **b) Per-project install** | **c) User-global install** |
|---|---|---|---|
| **What the user does** | Manually copy/paste the skill into a prompt or a project folder when needed | `git clone` our repo + symlink the skill into *this* project's `.claude/skills/` | Install once via the Claude Code plugin marketplace |
| **Skill lives at** | Wherever — even just pasted text | `<project>/.claude/skills/<name>/` | `~/.claude/skills/<name>/` |
| **Per-project work** | Heavy — repeat every time | Medium — once per project, then scaffold `.planning/` | Light — just scaffold `.planning/` |
| **Available today?** | Yes | **Yes — current path** | Not yet — needs skills merged to `main` first |

The only real differences are **where the skill lives** and **how often you do setup**. The integration work itself (templates, phase mappings, verifier agent) is *identical* in all three.

---

# What we're actually building

The integration we're designing is **the same regardless of delivery option.** Every GSD project that does ORM work needs the same per-project content:

- A set of project-state templates tailored to ORM modeling
- A mapping from our skills' steps onto GSD's phase loop
- A verification agent the Verify phase invokes
- A small bootstrap script that sets everything up

The three options on the previous slide are just delivery vehicles for the same content.

**Option (c) is gated by one thing** — the skills need to land on the main branch. Once merged, the plugin install path enables (c) automatically. Until then, (b) is the working path.

---

<!-- _class: dense -->

# Demo — schema flow (the commands)

## Setup (one-time)

```bash
brew install --cask claude-code
npx --yes @opengsd/gsd-core@latest --claude         # GSD globally, no --local
git clone -b an-orm-skill <repo> ~/rai-skills       # our skills + integration
ln -s ~/rai-skills/skills/rai-orm-from-schema ~/.claude/skills/rai-orm-from-schema
ln -s ~/rai-skills/integrations/gsd           ~/.claude/gsd-rai
```

## Per project (live demo)

```bash
mkdir ~/tmp/orm-build && cd ~/tmp/orm-build
cp ~/rai-skills/skills/rai-orm-from-schema/evals/fixtures/synthetic/schema.sql .
bash ~/.claude/gsd-rai/bootstrap.sh --schema schema.sql      # seeds .planning/ + agent
claude
> /gsd-plan-phase 1     /gsd-execute-phase 1     /gsd-verify-work 1
> /gsd-plan-phase 2     /gsd-execute-phase 2     /gsd-verify-work 2
> /gsd-plan-phase 3     /gsd-execute-phase 3     /gsd-verify-work 3
> /gsd-plan-phase 4     /gsd-execute-phase 4     /gsd-verify-work 4
> /gsd-plan-phase 5     /gsd-execute-phase 5     /gsd-verify-work 5
```

**Outputs at end:** `model.orm.yaml` · `model.verbalization.txt` · `model.py`

> **Skip `/gsd-new-project`** — our bootstrap *is* the init. `/gsd-new-project` would create generic templates; our bootstrap pre-populates them with ORM-specialized content (lift rules, Halpin posture, phase-to-step mapping) plus drops the verifier agent into `.claude/agents/`. Running both is redundant; GSD refuses anyway because `.planning/` is already populated.
>
> **Skip `/gsd-ship N`** to avoid a commit + PR per phase during demos. Phase 2 still plans after an un-shipped phase 1.

---

<!-- _class: dense -->

# Demo — text flow (the commands)

## Setup

Same as the schema flow plus `ln -s ~/rai-skills/skills/rai-orm-from-text ~/.claude/skills/rai-orm-from-text`.

## Per project (live demo)

```bash
mkdir ~/tmp/orm-text-build && cd ~/tmp/orm-text-build
cp ~/rai-skills/skills/rai-orm-from-text/evals/fixtures/synthetic_good_user/domain.md .
bash ~/.claude/gsd-rai/bootstrap.sh --text domain.md         # text variant
claude
> /gsd-discuss-phase 1  /gsd-plan-phase 1  /gsd-execute-phase 1  /gsd-verify-work 1
> /gsd-discuss-phase 2  /gsd-plan-phase 2  /gsd-execute-phase 2  /gsd-verify-work 2
> /gsd-discuss-phase 3  /gsd-plan-phase 3  /gsd-execute-phase 3  /gsd-verify-work 3
> /gsd-plan-phase 4     /gsd-execute-phase 4     /gsd-verify-work 4   # discuss optional
> /gsd-plan-phase 5     /gsd-execute-phase 5     /gsd-verify-work 5
```

**Input:** conference-talk-tracking domain (5 entity types, ~10 fact types, ~20 constraints — a real eval fixture with a reference solution at `evals/expected/synthetic_good_user.orm.yaml`, so the verifier's E1 diff actually runs).

**Outputs at end:** same triple — `model.orm.yaml` · `model.verbalization.txt` · `model.py`

> Discuss is **mandatory** at phases 1–3 (CSDP Steps 1, 4, 6 are dialogue). Each Discuss writes a `DIALOGUE.md` — the auditable trail for every `source: user-supplied` constraint.
>
> **Skip-new-project** and **skip-ship** apply identically to the text flow — same reasons as schema. Bootstrap *is* the init; Ship is the commit/PR step you skip for demo runs.
