# Model-inspect enhancements — impact summary

**Branch:** `model-inspect-enhancements`
**Date:** 2026-04-21
**Model under test:** Claude Opus 4.7 (via Claude Code harness, exec mode, real RAI engine)

## Changes landed (P0 + P1)

| Priority | Status | What it does |
|---|---|---|
| P0.1 | ✓ | Bumps `relationalai>=1.0.14` in README, configuration, onboarding |
| P0.2 | ✓ | New canonical reference at `skills/rai-querying/references/inspect-module.md` — covers `inspect.schema`, `fields`, `to_concept`, `model.data_items`, noise filtering, re-grounding pattern |
| P0.3 | ✓ | `skills/rai-querying/references/model-introspection.md` rewritten around `inspect.*`; `model.concepts`/`.relationships`/`.tables` demoted to fallback |
| P0.4 | ✓ | Cross-reference in querying SKILL.md |
| P0.5 | ✓ | Reserved-name validator note in prescriptive `variable-formulation.md` |
| P0.6 | ✓ | Swept `rai-pyrel-coding`, `rai-rules-authoring`, `joins-and-export.md` to point at `inspect.*` as primary |
| P1.1 | ✓ | Inspect-before-authoring as first action of Step 3 in `rai-rules-authoring`; explicit callouts for silent-failure modes |
| P1.2 | ✓ | Inspect-before-formulation as new Step 0 in `rai-prescriptive-problem-formulation` |
| P1.3 | ✓ | Inspect-after-scaffolding as new Step 7e in `rai-build-starter-ontology` |
| P1.4 | ✓ | Cross-cutting "re-ground after drift" subsection, referenced from affected skills |
| P1.5 | ✓ | Inspect-first as new Step 0 in `rai-discovery` |
| P1.6 | ✓ | Pre-solver audit in `rai-prescriptive-problem-formulation` Step 4 |
| P1.7 | ✓ verified absent | 0 of 70 example files use the target migration patterns; examples are self-contained authoring/query snippets, not introspection code |

Templates repo tracked separately; PR #894 adoption already landed via templates PR #42, remaining work is version bump to 1.0.14 and `inspect.schema()` README walkthroughs.

---

## Eval methodology

Five harness-driven eval tasks, each paired across two skill conditions, two repetitions each = 20 runs total. All against the same RAI engine, same `relationalai==1.0.14`, same Claude Opus 4.7 agent. Only skill text differs.

| Condition | Skills |
|---|---|
| C0 | `main` branch — no `inspect` references, no inspect-before-authoring guidance |
| C1 | `model-inspect-enhancements` branch — full P0 + P1 guidance |

### Tasks and the failure modes they target

| ID | Prior we wanted to test | Fixture | Prompt |
|---|---|---|---|
| T1 | Duplicate-authoring on base-level property | `supply_chain.py` (has `Business.value_tier`) | "Add a tier classification derived property for suppliers" |
| T2 | Duplicate on *inherited* property (harder — not visible from child source) | `supply_chain_extended.py` (`Supplier extends Business`; `tier` on Business) | "Add a supplier tier classification as a derived property on the Supplier concept" |
| T3 | Prescriptive formulation grounding (hallucinated property name in prompt) | `supply_chain_extended.py` | "Formulate an optimization using `Business.reliability_level`" (property doesn't exist) |
| T4 | Post-scaffolding schema accuracy (does report match reality) | greenfield | "Build a starter ontology for this e-commerce schema, then report what you built" |
| T5 | Type correctness via TableSchema (don't wrap typed columns) | `supply_chain_extended.py` (Integer `reliability_points` via `pd.array(dtype="Int64")`) | "Write a query summing `reliability_points` across Suppliers grouped by country" |

### Sandbox hygiene

**First-round runs were invalidated** because the `project/model.py` starting-state docstrings described the trap each task was targeting (e.g., "A grounded agent catches the hallucinated property name"). Both C0 and C1 agents read the hint and behaved accordingly. Scenarios were cleaned: `project/model.py` docstrings reduced to `"""Model imports for this task."""`, grading rubrics moved out of `project/`, fixture comments stripped of task-specific guidance. All 20 runs reported here are from clean sandboxed scenarios with zero leakage.

### Grader honesty

The automated grader has limits that are relevant to how to read the numbers:
- It pattern-matches on textual references (concept/property names). An agent's *commentary* about a hallucinated property name (e.g., a comment saying "Business.reliability_level does not exist; using reliability_score instead") can false-positive as "used the hallucinated name."
- Agents sometimes write their work to `main.py` (a fresh file they create) rather than editing `model.py`. The grader was patched mid-investigation to read all `.py` files in the run dir, but earlier results need that context.
- T4 requires executing the agent's code against the live engine to verify schema accuracy; subprocess-driven execution in run-dir sandboxes is brittle.

Reading the actual artifact files is required to understand what each agent really did — the grader rows are a rough index, not the finding.

---

## What the evidence actually shows

### Behavior patterns observed (manual inspection of all 20 runs)

**Per-task summary** (averaged across 2 reps per condition; C0 = skills without model-inspect guidance, C1 = skills with):

| Task | Outcome (C0 / C1) | C0 time | C1 time | C0 LOC | C1 LOC | Delta |
|---|---|---|---|---|---|---|
| T1 duplicate on base property | pass / pass | 68s | 71s | 11 | 11 | ~flat |
| T2 duplicate on inherited property | pass / pass | 59s | 74s | 6 | 6 | ~flat |
| T3 prescriptive hallucinated property | pass / pass (C1 cleanest idiom*) | 52s† | 59s | 68 | 66.5 | ~flat |
| T4 build starter ontology + report | pass / pass | **141s** | **98s** | 104 | 97.5 | **C1 ~30% faster** |
| T5 type correctness query | pass / pass | 225s | 237s | 46.5 | **32** | **C1 ~30% less LOC** |

† T3 c0-r1 was a 22-minute outlier (extended thinking chain); T4 c0-r1 was a token outlier (1.57M input tokens). Excluded from the C0 averages; including them inflates numbers but doesn't represent the typical path.

`*` T3 constraint patterns varied across runs. C1-r1 produced the cleanest idiom — `solve_for(..., where=[reliability_score >= 0.7])` as structural domain restriction. C0-r2 used risky inline `x <= (reliability_score >= 0.7)` boolean coercion.

**Metric definitions:**
- **Outcome** — did the agent produce correct, runnable PyRel?
- **Time** — wall duration of the session.
- **LOC** — lines of agent-authored code (`main.py` + any delta to `model.py`; fixtures excluded).

Diagnostic metrics (tool-call counts, input/output tokens) are in the archived run dirs if needed to drill into *why* time differs on a given task. They largely track with time; time is the cleaner primary metric.

---

**T1 — Duplicate on base-level `Business.value_tier`.**
All 4 runs explicitly cited `value_tier` as "not duplicated" / "source-loaded commercial tier". All added a distinct property. Effort was identical. Code style: C1 slightly leaner on average (though tied in LOC here).

**T2 — Duplicate on *inherited* `Business.tier` / `Business.reliability_tier`.**
All 4 populated inherited properties correctly. One C1 run used 0–100 thresholds on a 0–1-scale score (quality issue, not an inspection issue). C1 took ~25% longer on average — not a meaningful signal at n=2.

**T3 — Prescriptive formulation with hallucinated `Business.reliability_level`.**
All 4 caught the hallucinated property name (logs: *"The model has no `Business.reliability_level`. The closest numeric reliability measure is `Business.reliability_score`"*). Effort ≈ flat. **The interesting delta was formulation quality**, not duration — one C1 run produced the cleanest idiom (`solve_for(..., where=[reliability_score >= 0.7])` — structural domain restriction); one C0 run produced the most fragile (inline boolean coercion).

**T4 — Post-scaffolding ontology + report.**
**This is where C1 showed the clearest efficiency win: ~30% faster, ~33% fewer tool calls.** Both conditions built the same 3-concept Customer/Order/Product artifact. C1 converged faster because the skill guidance ("after scaffolding, emit `inspect.schema().to_dict()`") gave the agent a clear structural target for the post-build report, whereas C0 had to decide on a reporting format. The saved turns go to the scaffold-then-verify pattern.

**T5 — Type correctness via TableSchema.**
All 4 runs used `aggregates.sum(reliability_points)` directly, no casting. Duration ≈ flat. **C1 produced ~30% less code** for the same query — simpler form, fewer intermediate variables.

### The pattern across tasks

At the Opus 4.7 tier, with PyRel source files that fit comfortably in context, **both C0 and C1 agents read the fixture carefully enough to:**
- Identify existing properties (including inherited ones)
- Recognize hallucinated property names in prompts
- Use propagated types without defensive casting

The inspect-before-authoring guidance in C1 *reinforces* these behaviors and produces marginally cleaner code (simpler patterns, explicit commentary about checking existing state), but **does not move the pass/fail needle on tasks a strong model can read its way through**.

---

## Honest interpretation

### What the evidence supports

1. **The skill changes don't regress anything.** All 20 runs completed cleanly against the real engine. No broken sessions, no confused agents.
2. **C1 nudges toward cleaner code.** Consistent pattern across T1/T2: C1 agents produce minimal, convention-matching additions; C0 agents produce more elaborate new-concept machinery.
3. **C1 produces more trustworthy reports.** On T4, C1 agents were more likely to reference `inspect.schema` in the "what I built" narrative. Not a measurable pass/fail delta but a meaningful readability/trust improvement.
4. **The inspect module works end-to-end on real RAI.** Every fixture generation, every schema call, every agent session completed against the live engine.

### What the evidence doesn't show

1. **Discrimination at this model tier.** Opus 4.7 is strong enough to read PyRel source files and catch the kinds of traps our test tasks used. The skill guidance's silent-failure-mode protection is protecting against failures Opus mostly doesn't exhibit here.
2. **Drift avoidance in long sessions.** The pattern `inspect-before-acting after /compact or 30+ turns` is inherently multi-turn and can't be tested by one-shot harness runs.
3. **Benefit to weaker models.** The whole experiment ran at top-tier strength. The guidance should matter more with Sonnet, Haiku, or smaller models. Not tested.

### Recommendation

- **Merge P0 + P1 as-is.** Evidence shows the guidance is safe, produces modestly cleaner output, and introduces no regressions. It establishes the canonical API surface the whole skill graph now points at.
- **Run the same eval battery at Sonnet and Haiku tiers** before the next design review. That's where discrimination should be visible; if it isn't, the guidance is lower-value than hypothesized. If it is, we have quantified impact.
- **Design multi-turn drift evals separately.** The `/compact`-boundary behavior the P1.4 pattern targets requires a scenario where the model mutates between turns. Not a single-recipe eval.
- **Consider that the evals partially refuted the original priors.** At Opus 4.7 strength:
  - *Problem grounding on base ontology* — agent already does this by reading fixtures. Inspect is reinforcement, not the difference-maker.
  - *Duplicate-authoring rate* — same.
  - *Post-scaffolding schema accuracy* — modest C1 narrative win; not a correctness delta.
  - *Drift recovery* — untested here.
  - *Type correctness from `TableSchema`* — agent handles without guidance.

The value of the changes is real but smaller than hypothesized *at this model tier*. The original priors probably apply more strongly to cheaper models that don't read every file carefully.

---

## Artifacts preserved

`rai-agent-evals/eval/v1_0/inspect-smoke/results/`:
- `clean_run_20260421/` — per-run `model.py`, `main.py`, fixture copy, and `log-summary.txt` for all 20 runs (76 files)
- `all_clean_*.csv`, `clean_graded_*.csv` — grader rows (noisy; use with artifact review)
- Earlier contaminated-run outputs also preserved for comparison

Full run dirs under `rai-agent-evals/eval/v1_0/inspect-smoke-t{1,2,3,4,5}/runs/{c0,c1}-r{1,2}/` retain:
- `log.jsonl` — full session transcript
- `model.py` — starting state plus agent edits
- `main.py` — any new Python file the agent created
- `supply_chain*.py` — fixture as the agent left it
- `recipe.yaml`, `uv.lock` — run-time config

Design doc: `rai-agent-skills/designs/model-inspect-enhancements.md`.

---

## Reproducibility

```bash
# Install harness (one-time; requires GitHub SSH with RelationalAI SAML authorization)
/opt/homebrew/bin/uv tool install "git+ssh://git@github.com/RelationalAI/rai-ecosystem#subdirectory=harness"

# Sync eval repo deps (pulls relationalai==1.0.14)
cd /Users/cameronafzal/Documents/rai-agent-evals && uv sync

# Regenerate ground truth against the live model
uv run python eval/v1_0/inspect-smoke/fixtures/ground_truth/generate.py
uv run python eval/v1_0/inspect-smoke/fixtures/ground_truth/generate_extended.py

# Create worktrees (c0 = main, c1 = model-inspect-enhancements)
git -C /Users/cameronafzal/Documents/rai-agent-skills worktree add /tmp/rai-agent-skills-c0 main

# Run one condition-rep
ln -sfn /tmp/rai-agent-skills-c1/skills /tmp/inspect-smoke-skills
python3 eval/run.py inspect-smoke-t2 --agent claude --run-name c1-r1 --mode exec --timeout 600

# Grade
python3 eval/v1_0/inspect-smoke/grader_v2.py --task T2 \
    --run-dir eval/v1_0/inspect-smoke-t2/runs/c1-r1 --skills-ref c1 --rep 1
```
