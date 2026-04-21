# Model-inspect enhancements for rai-agent-skills

**Branch:** `model-inspect-enhancements`
**Status:** P0 + P1 complete; P1.7 verified absent; evals in progress
**Date:** 2026-04-20

## Implementation progress

| Priority | Status | Notes |
|---|---|---|
| P0.1 — version bump | ✓ complete | `relationalai>=1.0.14` in README, configuration, onboarding |
| P0.2 — inspect-module.md reference | ✓ complete | New shared reference at `skills/rai-querying/references/inspect-module.md` |
| P0.3 — rewrite model-introspection.md | ✓ complete | `inspect.*` headlined, lower-level fallback retained |
| P0.4 — cross-reference in querying SKILL.md | ✓ complete | — |
| P0.5 — reserved-name validator note | ✓ complete | `rai-prescriptive-problem-formulation/references/variable-formulation.md` |
| P0.6 — sweep old introspection callouts | ✓ complete | `rai-pyrel-coding`, `rai-rules-authoring`, `joins-and-export.md` updated |
| P1.1 — inspect-before-authoring in rules-authoring | ✓ complete | Step 3 first action + silent-failure-mode callouts |
| P1.2 — inspect-before-formulation in prescriptive | ✓ complete | New Step 0 in SKILL.md |
| P1.3 — inspect-after-scaffolding in build-starter | ✓ complete | New Step 7e emits `inspect.schema()` summary |
| P1.4 — cross-cutting re-ground after drift | ✓ complete | Subsection in `inspect-module.md`, referenced from affected skills |
| P1.5 — inspect-first in discovery | ✓ complete | New Step 0 in SKILL.md |
| P1.6 — pre-solver audit in prescriptive | ✓ complete | Added to Step 4 |
| P1.7 — migrate every example | ✓ verified absent | 0 of 70 example files use the target patterns; no code changes needed |
| P2.1–P2.5 | deferred | Lower-leverage items; revisit after eval cycle |

## Context

Two PyRel PRs landed in `relationalai` v1.0.14 (released 2026-04-16) that change what the agent can lean on when reasoning about RAI models:

- **[PR #894](https://github.com/RelationalAI/PyRel/pull/894)** — Problem introspection defs; `solve_for()` / `satisfy()` / `minimize()` / `maximize()` now return queryable Concept subtypes (`ProblemVariable`, `ProblemConstraint`, `ProblemObjective`). `variable_values()` soft-deprecated in favor of `Variable.values(sol_idx, val)`. `load_point(k>0)` removed. Reserved-name validator on `solve_for()`.
- **[PR #838](https://github.com/RelationalAI/PyRel/pull/838)** — New public `relationalai.semantics.inspect` module with three functions: `schema(model)`, `to_concept(obj)`, `fields(rel)`. Adds `model.data_items` to track inline `model.data()` sources. Propagates `TableSchema` column types through `Concept.new(table.to_schema())` (was `Any` before).

### What's already in the skills

A prior sweep added `ProblemVariable` / `Variable.values` guidance across the three prescriptive skills (16 files reference the new API). **No deprecated symbols** (`variable_values`, `load_point`, `_numeric_type`, `_make_name`) appear anywhere in the skills repo.

### What's missing

- Zero references to `relationalai.semantics.inspect` anywhere in the skills.
- `skills/rai-querying/references/model-introspection.md` still teaches manual field unpacking and `model.concepts` / `model.relationships` / `model.tables` as the only introspection paths.
- No mention of `model.data_items` — agents using `model.tables` alone will miss inline `model.data()` sources.
- Version floor `relationalai>=1.0.3` in `skills/rai-configuration/SKILL.md:31` — too low for v1.0.14 APIs.
- PR #894's reserved-name validator isn't called out; users will hit it without warning.

## Goal

Bring the skills up to v1.0.14, and go beyond documentation: use the new `inspect` module to close known agent failure modes (ungrounded claims, duplicated authoring, drift in long sessions, broken field unpacking).

## Non-goals

- Filtering library-internal concepts from `schema()` output — PR #838 flags this as future work. Skills should teach the filter, not wait.
- A convenience `model.schema()` method — also future work per PR #838. Don't prescribe.

## Hypothesis being tested

> Skill guidance that directs the agent to call `inspect.*` before authoring / querying produces higher-grounding, higher-pass-rate outputs than the current skills — *especially* on long sessions, inherited-property unpacking, and models with inline `data()` sources.

## Failure modes targeted

These are the concrete outcomes the rollout should reduce:

1. **Hallucinated surface** — concept/property/relationship that doesn't exist.
2. **Wrong type inferred** — writing code against `Any` when a real type (`Integer`, `String`) is now propagated through `TableSchema`.
3. **Duplicated authoring** — adding a rule/property that already exists.
4. **Broken field unpacking** — mis-unpacking an inherited or alt-reading relationship in `select()`.
5. **Missed data source** — model uses inline `model.data()` but agent only reasons about `model.tables`.
6. **Handle-type confusion** — helper breaks across Chain / Ref / FieldRef / Expression inputs.
7. **Stale-state drift** — model mutated mid-session, agent continues from cached assumptions.
8. **Reserved-name collision** (PR #894) — decision-variable field names that shadow `ProblemVariable`'s intrinsic surface.

### Where `inspect` helps most (from the agent's perspective)

The failure modes above are not equal in impact. Ranked by where `inspect` moves the needle most for an agent actually executing these skills:

1. **Authoring pre-check (high frequency × silent failure).** Rules and property authoring happens constantly, and hallucinated surface + wrong-type-inference + duplicated-authoring all fail *silently* — plausible code that compounds into downstream errors. `inspect.schema()[concept]` before authoring closes all three in one call. Highest priority for skill guidance. Applies to both rules-authoring and the prescriptive-authoring analogue (see #2).
2. **Prescriptive formulation grounding on base ontology (silent failure, authoring-time).** Prescriptive work is almost always layered on an existing model: `solve_for` / `satisfy` / `minimize` / `maximize` reference concepts, properties, and relationships from the base ontology. Today the agent routinely writes `Customer.tier` into a constraint when the real property is `Customer.category`; the solver happily returns nonsense. `inspect.schema()[Customer]` *before* formulation catches this. This is the prescriptive analogue of #1, separate from the downstream pre-solver audit.
3. **Post-action verification (high trust impact).** Today, "I added X" is a claim about intent. With types now propagating through `Concept.new(table.to_schema())` and the schema queryable, the agent can report what *actually registered*. Different kind of statement, and the one users should be getting.
4. **Long-session re-grounding (compounding cost).** Past ~30 turns or after a compact, the agent's mental model is lossy. `inspect.schema().to_dict()` is a cheap re-sync that's faster than re-reading files and closes entire classes of downstream errors. Cross-cutting pattern — not specific to one skill.
5. **Field unpacking and handle-type resolution (loud failures, medium frequency).** Real wins but these fail *loudly* (wrong columns, thrown errors), so they self-correct. Worth codifying as canonical idioms but lower urgency than #1–#4.
6. **Data source discovery, reserved-name collisions.** Low frequency. Important to cover once; not worth heavy skill real estate.

**Design implication:** push hardest on #1–#4, where current behavior is silently wrong. The loud-failure items will get caught by users anyway — those are idiom cleanups, not risk reductions.

### When `inspect` overhead isn't worth it

`inspect` calls cost turns and tokens. Skill guidance should recognize when to skip:

- **Greenfield authoring** — nothing in the model to inspect yet. Don't make the agent inspect an empty or near-empty schema.
- **Short single-shot tasks** — no drift to recover from; inspect adds a turn without payoff.
- **Highly templated work** — when patterns are dictated by a template, re-deriving them via `inspect` is wasted motion.

The eval's turn-count guardrail exists to catch regressions here.

## Skill changes — prioritized

### P0 — Core docs + version bump (do first)

| # | Change | Files |
|---|--------|-------|
| P0.1 | Bump required version | `skills/rai-configuration/SKILL.md:31` (`>=1.0.3` → `>=1.0.14`); `skills/rai-onboarding/SKILL.md:36` and `:70` (add `>=1.0.14` to the install commands); add a "Requires `relationalai>=1.0.14`" note to `README.md`. Only these three files carry install commands today — re-grep before landing to catch any added since. |
| P0.2 | New shared reference: **`skills/rai-querying/references/inspect-module.md`** | Covers `inspect.schema(model)`, `inspect.to_concept(obj)`, `inspect.fields(rel)`; noise-filtering pattern (library-internal concepts); `ms["Person"]` targeted-access for large schemas; `model.data_items` vs `model.tables` |
| P0.3 | Update `skills/rai-querying/references/model-introspection.md` | Headline `inspect.*` as recommended API; keep `model.concepts` / `model.relationships` / `model.tables` as lower-level fallback; replace manual field-unpacking section with `select(*inspect.fields(rel))` as canonical idiom; note `model.data_items` |
| P0.4 | Cross-reference in `skills/rai-querying/SKILL.md` | One line in the introspection subsection pointing to P0.2 |
| P0.5 | Reserved-name validator note | `skills/rai-prescriptive-problem-formulation/references/variable-formulation.md` — list of reserved attributes on `ProblemVariable` so users avoid the error preemptively |
| P0.6 | Sweep old introspection callouts | Grep for `model.concepts` / `model.relationships` / `model.tables` across all skills. Any skill text that presents these as *the* introspection API gets a pointer to `inspect.*` as primary. Skills that just use them in passing (a single example) can stay. Prevents dual-surface confusion after P0.3. |

### P1 — Cascading unlocks (highest-leverage behavior change)

Ordering reflects the impact ranking above: P1.1 and P1.2 target the two authoring-time silent-failure modes (rules and prescriptive); P1.3 is the trust win; P1.4 is cross-cutting re-grounding; P1.5–P1.7 follow.

| # | Change | Targets |
|---|--------|---------|
| P1.1 | "Inspect-before-authoring" step in **`rai-rules-authoring`** | Pre-author check: run `inspect.schema()[concept_name]` to detect existing properties before proposing a new one. Closes the #1 silent-failure mode: duplicated authoring, hallucinated surface, wrong-type inference. Highest-leverage item in the rollout. |
| P1.2 | "Inspect-before-formulation" step in **`rai-prescriptive-problem-formulation`** | Before authoring `solve_for` / `satisfy` / `minimize` / `maximize` over an existing model, run `inspect.schema()[concept]` on every concept / relationship referenced by the formulation. Confirms names and types against the base ontology so constraints don't silently reference hallucinated members. Distinct from (and upstream of) the pre-solver audit in P1.6. |
| P1.3 | "Inspect-after-scaffolding" step in **`rai-build-starter-ontology`** | After generating the ontology, emit `inspect.schema().to_dict()` summary for the user. Converts "I added X" from a claim about intent to a report of what actually registered. Biggest trust win. |
| P1.4 | Cross-cutting "re-ground before acting on stale assumptions" pattern | Add a short shared note (referenced from `rai-rules-authoring`, `rai-querying`, `rai-prescriptive-*`): after a `/compact`, after 30+ turns, or when resuming work on an existing model, run `inspect.schema()` before acting. Framed as a session-hygiene pattern, not tied to one skill. |
| P1.5 | "Inspect-first" step in **`rai-discovery`** | Start a discovery run with `inspect.schema()` to ground "what does the model support" on reality. |
| P1.6 | Pre-solver audit in **`rai-prescriptive-problem-formulation`** | After formulation, before solving: use `inspect.schema()` to confirm `ProblemVariable` / `ProblemConstraint` / `ProblemObjective` got registered as intended. Downstream complement to P1.2. |
| P1.7 | Migrate every example across every skill to v1.0.14 patterns | **Verified absent (2026-04-20).** Audit of all 70 `examples/*.py` across 14 skills found 0 files using the target patterns (manual field unpacking, `model.concepts`/`relationships`/`tables` iteration, `isinstance(x, Chain\|Ref\|FieldRef)`). Examples are self-contained model-authoring and query snippets; introspection patterns live in reference docs (already migrated in P0.2/P0.3/P0.6). Same "no targets" finding as templates T3. No code changes needed for P1.7. |

### P2 — Lower-leverage, bundle in the same sweep

| # | Change | Targets |
|---|--------|---------|
| P2.1 | `inspect.to_concept(obj)` for reusable helpers | `skills/rai-pyrel-coding` |
| P2.2 | Pre-build validation via `inspect.fields(rel)` | `skills/rai-graph-analysis` |
| P2.3 | Schema-diff pattern for review workflows | `skills/rai-ontology-design` |
| P2.4 | Pre-deploy audit — dump exposed surface | `skills/rai-cortex-integration` |
| P2.5 | Schema dump as diagnostic artifact | `skills/rai-health-skill` |

## Eval plan

Runs out of `rai-agent-evals/reasoner_workflow_evals/`, reusing `base_ontologies/` fixtures.

### Phase 0 — Smoke eval (1 day to build, 1 day to run)

**Fixtures (3 ontologies)**

- `base_ontologies/supply_chain.py` (existing) — targets inheritance + alt-reading unpacking.
- `base_ontologies/manufacturing.py` (existing) — control case, simpler model.
- **New fixture with inline `model.data()` calls** — targets `data_items` blind spot. Minimal: extend `manufacturing.py` (or a copy of it) with 1–2 inline `model.data(pd.DataFrame(...))` sources in addition to its existing tables, so `inspect.schema()` output has both. ~20 LOC added. Owner: first engineer on the eval build.

**Tasks (5 per fixture = 15 total)**

1. *"Add a derived property that classifies X into tiers."* → pass: compiles, runs, not a duplicate of existing property.
2. *"Write a query that selects all fields of relationship R."* → pass: columns equal `inspect.fields(R)` ground truth.
3. *"List every property on Concept C, including inherited."* → pass: set equality against ground truth.
4. *"List all data sources in this model."* → pass: covers both `tables` and `data_items`.
5. *"Write a helper `describe(handle)` that accepts Chain, Ref, or FieldRef and prints the underlying concept name."* → pass: runs on all three input types.

**Conditions**

- **C0**: skills as-is today (baseline).
- **C1**: skills with P0 + P1 changes applied.

Both conditions run against `relationalai==1.0.14`. The version bump is held constant; only skill text differs. Otherwise tasks that rely on `data_items` or `inspect.*` can't even execute under C0, which would confound the comparison.

**Reps:** 5 per (task, condition) → 150 runs. Fits in one batch.

**Ground truth**

Ground truth for each fixture is produced *once* by the eval harness calling `inspect.schema(model).to_dict()` and committed alongside the fixture. The agent under test is *not* graded against its own `inspect.*` output — it's graded against the frozen snapshot. The harness, not the agent, is the source of truth.

**Metrics**

- **Primary — pass rate** per task, per condition.
- **Secondary — grounding rate**: for each artifact produced by the agent, extract every dotted reference of the form `<Concept>.<member>` and every bare concept-name token that appears in `select()` / `define()` / `where()` / `ref()` call sites. A reference is *grounded* if its concept and member both appear in the fixture's ground-truth `schema().to_dict()`; stdlib names (e.g. `std.aggregates.*`) and Python builtins are excluded. Grounding rate = grounded / total references. Extractor is a small regex + AST pass, ~50 LOC.
- **Guardrail — turn count per run.** Flag if C1 pass rate ≤ C0 + 10 pts but turn count is up ≥ 25%.

**Kill criterion**

If C1 doesn't beat C0 by ≥15 points on grounding rate *or* ≥10 points on pass rate, redesign P1 guidance before touching P2.

**Ship criterion**

Merge P0+P1 to `main` when C1 beats C0 by ≥15 points on grounding rate *and* ≥10 points on pass rate, with turn-count guardrail not tripped. Proceed to P2 in a follow-up branch.

### Phase 1 — Failure-mode targeted (only if Phase 0 clears the kill criterion)

Add fixtures and tasks for remaining failure modes:

- **Type propagation** — fixture where `New(table.to_schema())` column types matter. Task: "sum column X." Grade: treats X as `Integer` without unnecessary conversion.
- **Drift detection** — multi-turn task; mutate model between turns; grade: does agent re-inspect or act on stale assumptions?
- **Prescriptive formulation grounding** — fixture has a base ontology with concepts and properties that *almost* match plausible names (e.g. `Customer.category` where the agent might guess `Customer.tier`). Task: "minimize total cost subject to tier-based availability constraints." Grade: does the agent inspect before authoring and reference real properties, or does it hallucinate `tier` and proceed?
- **Alt-reading unpacking** — fixture with alt readings. Task: query using the alt reading.
- **Reserved-name collision (PR #894)** — ask the agent to build a decision variable with a field shadowing `name`/`upper`. Grade: anticipates the validator error.

### Phase 2 — Per-skill ablation (only after Phase 1 shows generalizable gain)

- `rai-rules-authoring`: duplicate-rule rate.
- `rai-build-starter-ontology`: schema accuracy after scaffolding.
- `rai-prescriptive-problem-formulation`: formulation grounding rate (P1.2) *and* pre-solver audit catch rate (P1.6) — measured separately so we know which of the two upstream/downstream checks is doing the work.

### Infrastructure

- Add fixture Q&A entries to `reasoner_workflow_evals/eval_qas/`.
- Commit ground-truth `inspect.schema().to_dict()` snapshots per fixture for automated grading.
- Extend `eval/run.py` (or thin wrapper) to load fixture → run agent → grade against snapshot.
- **No LLM-as-judge in Phase 0.** Add only if Phase 1 needs semantic grading.

### Smoke eval mechanics

Built on the existing `rai-agent-evals` harness — no new plumbing.

**Scenario tree**

```
rai-agent-evals/eval/v1_0/inspect-smoke/
  fixtures/
    supply_chain.py
    manufacturing.py
    manufacturing_with_data.py   # manufacturing + 1-2 inline model.data() sources
    ground_truth/
      *.json                     # inspect.schema(model).to_dict() per fixture, committed
  tasks/
    t{1..5}_<name>/              # 5 task types × 3 fixtures = 15 task dirs
      project/
        model.py                 # imports fixture
        recipe.yaml              # prompt = the task
  grader.py
```

**C0 vs C1 = two git refs, one scenario tree**

`recipe.yaml` `skills: path:` points at a worktree of `rai-agent-skills`. `SKILLS_REF=c0|c1` env var selects `main` or `model-inspect-enhancements`. No scenario duplication.

**Runner**

Thin shell wrapper over `eval/run.py`:
```
for task in inspect-smoke/tasks/*; do
  for rep in 1..5; do
    for ref in c0 c1; do
      SKILLS_REF=$ref ./eval/run.py inspect-smoke/tasks/$(basename $task) \
        --agent claude --mode exec --run-name $ref-r$rep
    done
  done
done
```
150 runs, all headless (`--mode exec`). Parallelize if supported; serial runs ~1–3 min each.

**Per-task graders**

- **T1 add derived property:** import produced `model.py`, run, confirm property exists, diff against ground-truth property list for duplicates.
- **T2 select all fields:** run produced query, compare column set to `inspect.fields(rel)` ground truth.
- **T3 list inherited properties:** parse agent output, set-equality against ground-truth inherited set.
- **T4 list data sources:** must cover both `tables` and `data_items` in ground truth.
- **T5 describe helper:** harness invokes produced helper with prepared Chain/Ref/FieldRef handles, checks output.

Grounding-rate extractor is one regex+AST pass over the produced `.py`, shared across all tasks.

**Report**

Group `results.csv` by `(task_id, skills_ref)`; emit C0-vs-C1 per-task table with pass rate, grounding rate, turn count, 95% CI over 5 reps. Write to `reasoner_workflow_evals/results/inspect-smoke-<date>.md`. Flag kill/ship criteria automatically.

**Smallest viable first cut**

Before the full 150-run grid, run **1 task × 1 fixture × 2 refs × 2 reps = 4 runs** manually to pressure-test fixture loading, skills-path switching, and grader I/O. ~10 minutes of work, catches harness bugs early.

**Costs and watch-outs**

- ~1M tokens total ballpark (150 runs × 5–10k each). Budget before kicking off.
- Keep `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` so memory doesn't leak between runs.
- Copy the tight `allowed_tools` allowlist from `mvd/recipe.yaml`.
- `--timeout 600` for exec mode caps runaway sessions.

### Watch-outs

- **Selection bias.** Every fixture in Phase 0 shouldn't be inspect-favorable. Include one small flat model.
- **Tool-use as metric.** Don't grade "called `inspect.*`". Grade outcomes; use tool-call counts as diagnostic only.
- **Reps.** 5 is the floor; bump to 8–10 on the headline comparison if variance is high.
- **Skill routing stays fixed.** P0/P1 changes must be text-only inside targeted skills, so the delta measures guidance quality, not routing.
- **Eval bias toward loud failures.** The Phase 0 tasks (query correctness, helper correctness) mostly catch loud failures. The silent-failure modes `inspect` targets most (duplicate authoring, stale-state drift) need the Phase 1 tasks to evaluate properly — don't treat a clean Phase 0 as proof the silent-failure guidance is working.

## Related unlocks in `templates/` (separate repo, separate branch)

Tracked here because they round out the model-inspect story, but **lands in a different branch of the `templates/` repo** — not in scope for the `rai-agent-skills` PR.

**Status as of re-audit against `origin/main`.** PR #894 (queryable `ProblemVariable` / `Variable.values`) has **already been adopted** via templates PR #42 ("Upgrade prescriptive templates to SDK 1.0.13 patterns"). No `variable_values()` remains; `Variable.values(...)` is in use; `problem` rename applied. Stale Graph+prescriptive interop text in `energy_grid_planning` and `machine_maintenance` READMEs was patched in commits `37494f5` and `75558aa`.

The **remaining** template work is narrower and specifically about PR #838 (the new `inspect` module):

### Remaining template changes

| # | Change | Targets |
|---|--------|---------|
| T1 | Bump `relationalai>=1.0.14` in `pyproject.toml` | All templates — current pins are mixed (1.0.3 / 1.0.8 / 1.0.12 / 1.0.13); none on 1.0.14 yet. Prerequisite to unlock `inspect.*`. |
| T2 | Add `inspect.schema(model)` README walkthroughs | Simpler templates (`diet`, `ad_spend_allocation`, `production_planning`, +1–2 more) — teaches customers the introspection pattern on compact examples. Zero usage anywhere today. |

**Verified absent (no work needed):**
- Manual field unpacking — `inspect.fields(rel)` has no targets.
- `isinstance(x, Chain|Ref|FieldRef)` patterns — `inspect.to_concept(obj)` has no targets.
- `model.concepts` / `.relationships` / `.tables` direct access.

### Coordination

- Skills examples and template walkthroughs should converge on identical `inspect.*` idioms. Same author handling both surfaces keeps them aligned.
- Template work runs on its own branch, kicked off once skills P0 lands so canonical patterns are documented first.
- Scope is much smaller than originally estimated — version bump is the only repo-wide change; `inspect.schema()` README walkthroughs are the only new content.

## Sequencing (skills repo)

1. Land P0 (version bump + inspect-module docs + old-surface sweep). ~half day.
2. Build Phase 0 harness against current skills (capture C0). ~1 day.
3. Land P1.1–P1.6 (cascading skill-text unlocks, ordered by impact). ~1 day.
4. Land P1.7 (comprehensive example migration across every skill). ~1–2 days; largest chunk of work.
5. Run Phase 0 C1 condition. ~0.5 day.
6. **Decision point:** hit ship criterion → merge P0+P1, move P2 to follow-up. Hit kill criterion → redesign P1.

Template-repo work tracks in parallel on its own branch — kicks off once skills P0 lands so canonical patterns are documented first.

## Open questions

- Which repo owns the reusable `inspect-patterns` reference if P0.2 grows beyond `rai-querying` scope? (Current plan: keep it in `rai-querying/references/` and cross-link.)
- Do we need one new fixture for `data_items`, or can we extend an existing one with an inline `model.data()` call? (Prefer extend, to keep fixture count low.)
- Should the Phase 0 grader be committed to `rai-agent-evals` or live in a scratch branch until Phase 1 is approved?
