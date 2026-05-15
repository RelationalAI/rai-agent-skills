# synthetic_good_user fixture

## What this is

A hand-written multi-turn CSDP dialogue between a domain expert and the skill. Used for T-E1 (reference-solution match) and T-E3 (question-asking quality) evals.

**Domain:** small conference-talk-tracking system (Conference → Track → Talk → Speaker).

**User profile:** a "good" user — engaged, gives examples, answers clarifying questions, distinguishes alethic from deontic, applies the Halpin role-based subtype criterion correctly.

## Files

| File | Purpose |
|---|---|
| `dialogue.md` | The multi-turn dialogue script — 11 turns, covers Steps 0–7 of CSDP |
| `README.md` | This file |

## Source

Hand-crafted by Claude during the rai-orm-from-text build (2026-05-14). Not derived from any external source (no Halpin Workbook excerpt). The dialogue is original and the domain is generic enough to be public-domain.

## What this fixture exercises

- Step 0: Guided mode opener
- Step 1: elementary-fact decomposition, **reference scheme elicitation** for four entity types (one `general`, three `external` composites)
- Step 2: fact-type drawing + population check with sample facts
- Step 4: uniqueness on every fact type plus external UCs
- Step 5: mandatory roles distinguished from optional roles
- Step 6: library hits (year-range, count-non-negative, email-format) + one LLM proposal (deferred to Step 7)
- Step 6 subtype check: **rejection of attribute-based subtyping** (Keynote vs regular Talk) — replaced with TalkType value enum
- Step 7b: rejection of an LLM-proposed soft heuristic (counter-example given)
- Step 7d: user-supplied constraints including one **alethic** (max 50 talks) and one **deontic** (talk duration ≤ 60 minutes)
- Step 7e: explicit modality labelling

## Expected reference solution

See `../../expected/synthetic_good_user.orm.yaml` for the canonical reference output. Diff your CSDP run against it for T-E1 verdicts.

## How to use this fixture

In Guided-mode testing, follow the dialogue script: read the user turns to Claude, accept Claude's questions, respond as the script says. The skill should produce structurally-equivalent output to `expected/synthetic_good_user.orm.yaml`.

In One-shot mode, concatenate the user turns into a single description and feed to the skill. Note that One-shot is significantly degraded for text-first; expected output is sparser.
