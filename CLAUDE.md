# CLAUDE.md

> **What this file is:** working orientation notes for Claude Code sessions — patterns observed in the existing skills, plus pointers. **Not** formal repo policy. The authoritative sources are `README.md`, the existing skill folders themselves, and `contrib/dev-quality-skills-review/SKILL.md`. Where this file and those sources disagree, those sources win.

## What This Repo Is

A collection of skills that teach AI coding agents how to use the RelationalAI (PyRel v1) platform. Per the README, skills encode expert knowledge — heuristics, workflows, and patterns — distributed as folders agents discover at runtime. The README's mental model: **Skills (knowledge) + Tools/APIs (actions)**, with the agent reading skills and calling tools.

Distributed as a plugin via `.claude-plugin/marketplace.json` (current version in that file). Licensed Apache 2.0.

## Validation

Run the quality review checklist in `contrib/dev-quality-skills-review/SKILL.md` against any new or modified skill. This is the authoritative quality gate — it covers structure, content, prompt engineering, boundaries, examples, and agent usability.

Python code blocks in markdown should parse with `ast.parse` (anti-patterns explicitly marked `# WRONG:` are exempt). Skill/reference/example cross-links should resolve.

## Skill Anatomy — what's common, what's flexible

**Required for any skill:**
- The folder lives at `skills/rai-<name>/`.
- `SKILL.md` at the folder root with YAML frontmatter (`name`, `description`) and a markdown body.
- The plugin manifest references the skill so it ships in the distribution.

**Common patterns (most skills use these, not all):**
- `references/` — deep-dive markdown files loaded on demand.
- `examples/` — illustrative Python files.

**Other directories used in this repo today:**
- `evals/` — eval cases as data files (`rai-ontology-design/evals/evals.json`).
- Skill folders may also include any other assets the skill needs — schemas, fixtures, generated reports — provided they earn their keep.

**For skills that ship functional code (not just illustration):**
This is allowed. The Anthropic Skills system supports executable assets that Claude invokes via Bash, MCP tools, or CLI commands. If a skill ships a real translator, validator, or library, those go in `tools/` (or a Python package directory under the skill folder), and SKILL.md tells Claude how to invoke them. Document the rules in `references/` as a fallback path so Claude can apply them inline if the tool isn't available.

**SKILL.md sections — common shape (not mandatory):**
1. YAML frontmatter: `name` and `description` (one line, answers WHAT it does and WHEN to invoke it)
2. Stability tag below title: `<!-- v1-STABLE -->` or `<!-- v1-SENSITIVE -->`
3. `## Summary` — What, When to use, When NOT to use, Overview
4. `## Quick Reference` — tables and code blocks, not prose
5. Detailed sections (numbered or heading-based)
6. `## Common Pitfalls` — table with Mistake / Cause / Fix columns
7. `## Examples` — table linking to example files
8. `## Reference files` — with "when to use" framing

**Length:** SKILL.md is loaded into Claude's context every time the skill activates, so keep it lean — push deep content to `references/`. Most existing skills are 300–500 lines. Larger is fine when justified by procedural density; smaller is fine for focused skills. No hard cap.

## Key Conventions

**Naming:** Skills use `rai-` prefix, kebab-case. Concepts/classes are PascalCase. Properties/methods are snake_case. Files are kebab-case.

**Boundaries:** Skills are MECE (mutually exclusive, collectively exhaustive). Each skill has explicit "When NOT to use" pointers to adjacent skills. Cross-references use skill name only (e.g., `rai-pyrel-coding`), never file paths.

**Content:** One term per concept throughout (no synonym alternation). CRITICAL/MUST reserved for genuine compile/runtime failures only. Reference files stay one level deep from SKILL.md. When content moves to a reference file, SKILL.md retains an inline summary + a load-trigger pointer.

**Examples:** Pattern-centric and domain-neutral — concept/property names should be generic enough to map to any domain. One canonical example per pattern. Short patterns (< 10 lines) inline; larger examples in separate files. Example files should be self-contained where possible.

**Description field:** Must answer both (1) WHAT the skill does and (2) WHEN to invoke it, in a single sentence. Include a negative boundary when scope could overlap with an adjacent skill.

## Skill Workflow Chain

Skills compose in a natural workflow progression:

- **Setup:** rai-onboarding -> rai-configuration
- **Development:** rai-pyrel-coding (foundational syntax, referenced by all other skills)
- **Ontology:** rai-build-starter-ontology -> rai-ontology-design -> rai-rules-authoring
- **Reasoning router:** rai-discovery (classifies questions, routes to the appropriate reasoner)
- **Reasoners:** rai-querying, rai-graph-analysis, rai-prescriptive-problem-formulation -> rai-prescriptive-solver-management -> rai-prescriptive-results-interpretation
- **Operations:** rai-cortex-integration, rai-health-skill
- **Schema modeling (in development):** rai-orm-from-schema
- **Conceptual modeling from text (in development):** rai-orm-from-text (Halpin CSDP)

## Version Bumps

Plugin version lives in `.claude-plugin/marketplace.json` under `plugins[0].version`. Bump it when publishing skill changes.
