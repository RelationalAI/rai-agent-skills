# Constraint Elicitation — the Full Playbook

Detail behind SKILL.md Step 7 and the constraint-vs-objective decision rule. Constraints are rarely handed to you complete: they emerge by asking the right questions before solving, and by using results to surface preferences the user couldn't articulate in the abstract. For model-structural constraint discovery (boundary/structural/multi-concept probes), see [constraint-formulation.md](constraint-formulation.md) > Constraint Discovery Patterns.

## Pre-solve: from business language to constraints

| Question to ask | What it surfaces |
|----------------|------------------|
| "What limits must the solution respect?" | Capacity constraints (budget, headcount, storage, time) |
| "What must every solution achieve?" | Forcing/requirement constraints (meet all demand, cover all shifts) |
| "What would you prefer if possible, but could live without?" | Soft goals → objective terms, not hard constraints |
| "What makes a solution completely unacceptable?" | Hard constraint violations (safety, regulatory, contractual) |
| "Are there minimum service or coverage levels?" | Lower-bound forcing constraints |

**Technique:** start with "What makes a solution unacceptable?" — it reliably surfaces hard constraints. Then "What would make one acceptable solution better than another?" — that surfaces objective terms.

## Disambiguating business language

| Business phrase | Interpretation A (constraint) | Interpretation B (objective) |
|----------------|-------------------------------|------------------------------|
| "Keep costs under $X" | Hard budget: `total_cost <= X` | Minimize cost (no hard cap) |
| "Each store should get at least 100 units" | Hard minimum: `supply[s] >= 100` | Soft target: penalize shortfall |
| "Try to balance across regions" | Hard fairness: `max - min <= threshold` | Minimize imbalance |
| "We need to cover all shifts" | Hard coverage: `sum(assign[s,w]) >= 1` per shift | Maximize coverage (allow gaps) |
| "Don't use more than 3 suppliers" | Hard cardinality: `sum(use[s]) <= 3` | Minimize active suppliers |

**Decision rule:** violating it makes the solution invalid → **constraint**; preference / nice-to-have → **objective term**. When unclear, default to soft and ask: "If the optimizer found a solution that violates this but saves 20% on cost, would that be acceptable?"

## Post-solve: iterative refinement

Pre-solve elicitation has a limit: "no constraints" often means "I can't think of any right now." Preferences are real but latent — surfaceable only through confrontation with a concrete proposal. **The first solve with minimal constraints is diagnostic, not prescriptive** — its purpose is to provoke reactions that reveal the real formulation.

**The loop:** (1) solve with current constraints; (2) present, highlighting what's most likely to provoke reaction; (3) ask targeted reaction questions; (4) disambiguate rejections into constraint types; (5) add, re-solve, repeat until acceptance.

**Presenting to surface latent preferences:**
- **Highlight large shifts from status quo** — users have unstated change-aversion; magnitude of change surfaces comfort thresholds on *rate* of change, not just levels.
- **Anchor to domain norms** — peers, industry standards, historical ranges calibrate the reaction and surface organizational bounds.
- **Show the trade-off cost** — when a value looks extreme, present what relaxing it costs in the objective; distinguishes "no, regardless of cost" from "well, if it saves that much…".
- **Flag boundary solutions** — variables pushed to a bound (zero, maximum) frequently violate unstated preferences; call them out.

**Reaction questions:**

| Question | What it surfaces |
|----------|------------------|
| "Does anything in this result feel wrong or surprising?" | Latent hard constraints |
| "Which value would you change first?" | The tightest latent preference |
| "Would you be comfortable presenting this?" | Social/organizational/reputational constraints |
| "If this were the only feasible solution, would you change your requirements?" | Hard constraint vs negotiable preference |

**Disambiguating a rejection:**
- **Absolute bound vs change bound** — "too much X" may mean X exceeds an absolute comfort level, or the jump from current state is too large; different formulations.
- **Hard vs soft** — test: "if violating this saved [meaningful amount], would that change your answer?" Hard constraints survive; soft preferences become penalty terms.
- **Specific vs vague** — "seems aggressive" needs a dimension probe: concentration, deviation from current, absolute level.

**When to stop:** the user accepts (explicitly or by shifting to implementation questions — don't probe for objections that aren't there); the user gives a specific value ("cap it at 10%" — take it directly); changes become marginal; the user starts trading constraints off against each other (the efficient frontier is found).

**Feasibility pressure:** if repeated rejections shrink the feasible region toward infeasibility, pause and present the tension explicitly — the user must prioritize. That ranking is itself elicitation.

**Document the trail:** log each constraint added and the reaction that motivated it — the "why" behind bounds that would otherwise look arbitrary, valuable for maintenance and stakeholder review.
