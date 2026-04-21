---
name: dev-quality-skills-review
description: Reviews RAI agent skills for structure, content quality, prompt engineering,
  boundaries, examples, and agent usability. Use when creating, reviewing, or auditing
  skills in rai-agent-skills or rai-agent-skills-private.
---

# RAI Skills Review

## Litmus Test: Agent Usability

The ultimate quality gate. Everything below serves this — if an agent can't discover, navigate, adapt, and execute from the skill alone, the skill isn't done.

- [ ] **Discovery**: Given a realistic user task, does the skill's `description` cause it to trigger (and not trigger for unrelated tasks)?
- [ ] **Navigation**: Can an agent find the right section/example within the skill in 1-2 lookups (not wandering)?
- [ ] **Pattern adaptation**: Given a novel problem, can an agent locate a relevant example pattern and adapt it to a new domain without hallucinating API calls?
- [ ] **Self-sufficiency**: Can an agent go from skill content to working code without needing external docs, clarification, or guessing?
- [ ] **Negative test**: Does the skill clearly redirect the agent when the task is out of scope (via "When NOT to use" pointers)?

---

## Structure

- [ ] YAML frontmatter with `name` and `description` (description is one line, trigger-ready, third-person)
- [ ] `SKILL.md` at root, `references/` for deep-dive, `examples/` if applicable
- [ ] `## Summary` with What, When to use, When NOT to use, Overview
- [ ] `## Quick Reference` near top — tables/code blocks, not prose
- [ ] `## Common Pitfalls` table (Mistake / Cause / Fix)
- [ ] `## Examples` table linking to example files
- [ ] `## Reference files` with "when to use" framing
- [ ] Stability classification (`v1-STABLE` or `v1-SENSITIVE`) below title

---

## Content Quality

- [ ] SKILL.md body under 500 lines
- [ ] One term per concept throughout (no synonym alternation)
- [ ] Examples don't contradict any documented rule/pattern
- [ ] Reference files use same API style as SKILL.md
- [ ] Progressive disclosure: metadata (L1) -> instructions (L2) -> bundled resources (L3)
- [ ] References one level deep from SKILL.md (no deep nesting)
- [ ] Degrees of freedom match task fragility (narrow bridge = specific; open field = general)
- [ ] **No explaining the obvious**: omit what the agent already knows (general concepts, standard libraries, common protocols) — every token should earn its place
- [ ] **Concise over exhaustive**: stepwise guidance with a working example beats encyclopedic coverage — if content covers every edge case, check whether most are better left to agent judgment
- [ ] **Defaults over menus**: when multiple tools/approaches apply, one is the default with brief escape hatch — not equal-weight lists of options
- [ ] **Short, generic parentheticals**: keep inline "e.g." examples short and generic. Drop overly-specific example phrases unless they disambiguate a rule — when in doubt, cut them.

---

## Prompt Engineering

- [ ] Explicit instructions with specific decision criteria — no "use your judgment"
- [ ] Every major rule explains WHY (runtime error, trivial solution, etc.)
- [ ] Positive framing: state what to do, not just what to avoid
- [ ] CRITICAL/MUST reserved for genuine compile/runtime failures only (not section headers)
- [ ] Each piece of guidance stated once in one authoritative location
- [ ] **No hardcoded domain enumerations**: no domain-specific laundry lists in prose or pattern definitions ("price ticks, sensor readings, KPIs…"). State the heuristic or shape distinction principled so the agent adapts to the user's data. One concise illustrative phrase is fine; a list is not.
- [ ] Hallucination guard: instruct to verify references against provided context
- [ ] Examples demonstrate correct pattern, not just anti-patterns
- [ ] **Procedures over declarations**: skill teaches *how to approach* a class of problems, not *what to produce* for a specific instance — the method should generalize even when individual details are specific

---

## Boundaries

- [ ] MECE within skill (no content duplication across files)
- [ ] MECE across skills (no overlap; boundary drawn in "When NOT to use")
- [ ] Every `##` section falls within scope defined by Summary
- [ ] Cross-references use skill name only (e.g., `rai-pyrel-coding`), point to existing skills

---

## Instruction Patterns

- [ ] **Validation loops**: for tasks with verifiable output, skill instructs the agent to validate its own work before moving on (run validator → fix → re-validate)
- [ ] **Reference load triggers are specific**: references say *when* to load (e.g., "if the API returns non-200") — not generic "see references/ for details"

---

## PyRel Examples

- [ ] One canonical example per pattern (variants only when justified)
- [ ] Every example file linked from Examples table or inline text
- [ ] Short patterns (< 10 lines) inline; larger examples in separate files
- [ ] Example files are self-contained (copy-paste-execute)
- [ ] Pattern-focused — strip unrelated setup boilerplate
- [ ] **Adaptable**: examples use generic enough names/structure that an agent can map them to a novel domain

---

## Validation

- [ ] `./scripts/test.sh -v` passes (syntax, imports, cross-refs, template compliance)
- [ ] All code blocks parse with `ast.parse`
- [ ] All imports resolve
- [ ] All skill/reference/example links resolve
