---
name: rai-prescriptive-problem-formulation
description: Formulates optimization problems from ontology models covering decision variables, constraints, objectives, and common patterns. Use when building, reviewing, or debugging a formulation.
---

# Problem Formulation
<!-- v1-SENSITIVE -->

## Summary

**What:** Optimization formulation — decision variables, constraints, objectives, and common problem patterns. Assumes a problem has already been selected via discovery.

**When to use:**
- Formulating variables, constraints, and objectives for a selected problem
- Reviewing or validating an existing formulation
- Translating business requirements into mathematical formulation
- Debugging formulations that would produce trivial or infeasible solutions (missing constraints, conflicting bounds, wrong aggregation scope)
- Choosing between variable types (continuous, integer, binary)
- Designing multi-concept coordination (flow networks, selection + quantity)

**When NOT to use:**
- Post-solve diagnosis of solutions that look wrong (all zeros, infeasible status, concentrated values) — see `rai-prescriptive-results-interpretation`
- Question discovery (what can this ontology answer, reasoner classification) — see `rai-discovery`
- PyRel syntax (imports, types, property patterns, stdlib) — see `rai-pyrel-coding`
- Ontology modeling or model enrichment (concept design, gap classification) — see `rai-ontology-design`
- Solver execution and diagnostics (solver selection, parameters, numerical stability) — see `rai-prescriptive-solver-management`
- Aggregation syntax (count/sum/per patterns) — see `rai-querying`

**Overview:**
1. Define decision variables (type, bounds, scope, naming)
2. Define constraints (forcing, capacity, balance, linking; validate interactions)
3. Define objective (direction, coefficients, multi-component handling)
4. Validate the complete formulation (structure, completeness, feasibility, data)
5. Simplify (static parameters, goals vs constraints, grouped constraints)

---

## Quick Reference — Problem API

```python
from relationalai.semantics.reasoners.prescriptive import Problem

problem = Problem(model, Float)
```

| Method | Signature | Purpose |
|--------|-----------|---------|
| `solve_for` | `(expr, where=, populate=True, name=, type=, lower=, upper=, start=)` | Declare decision variable. Returns `ProblemVariable` (a Concept usable in `model.define()`, `model.select()`, `.ref()`). `type`: `"cont"`, `"int"`, `"bin"` |
| `satisfy` | `(expr, name=)` | Add constraint. Returns `ProblemConstraint` (a Concept). |
| `minimize` | `(expr, name=)` | Set minimization objective. Returns `ProblemObjective` (a Concept). |
| `maximize` | `(expr, name=)` | Set maximization objective. Returns `ProblemObjective` (a Concept). |
| `solve` | `(solver, time_limit_sec=, ...)` | Execute solve. Solvers: `"highs"`, `"minizinc"`, `"ipopt"`, `"gurobi"` |
| `verify` | `(*fragments)` | Post-solve constraint verification |
| `Variable.values` | `(sol_index, value_ref)` | Property on `ProblemVariable`. Extracts solution values at `sol_index` (0-based), binding each value to `value_ref` (a `Float.ref()` or `Integer.ref()`). Use inside `model.select(...).where(var.values(sol_index, value_ref))`. Primary pattern for `populate=False` workflows. |
| `display` | `(part=)` | Print formulation summary |

---

## Formulation Workflow

**Interaction mode:** Before starting, ask the user which mode they prefer:
- **Guided** — present your proposed variables, constraints, and objective at each step and confirm before proceeding. Best when the user has domain context to share — problem framing involves subjective judgment (what's a hard constraint vs. a soft goal, how to scope variables, which business rules matter most).
- **One-shot** — produce the best formulation you can in a single pass. Best when the user wants speed and will review/iterate after.

After a question is selected (from question discovery) and the ontology is enriched (if needed), build the formulation in this order:

### Step 1: Define Variables
What decisions are being made? What can the solver control?
- Start with the base model context — examine concepts, properties, relationships (Variable Context Integration)
- Identify the primary decision entity first, then auxiliary/aggregation variables (Variable Principles)
- Choose variable types (continuous/integer/binary) and set bounds from data (Advanced Variable Patterns)
- For minimize objectives, include a slack/unmet variable to avoid infeasibility

### Step 2: Define Constraints
What rules must the solution satisfy?
- Start with model structure + user goals (Constraint Context Integration)
- Add forcing constraints first — these prevent trivial zero solutions for minimize objectives
- Add capacity/resource constraints from data properties
- Add flow conservation if the model has network structure
- Derive parameters from data ranges, not arbitrary values (Parameter Derivation from Data)

### Step 3: Define Objective(s)
What are we optimizing?
- Start with user's stated goal — map business language to minimize/maximize (Objective Context Integration)
- Reference defined variables and data properties in the expression
- Check for trivial solution risk: "If all variables = 0, are all constraints satisfied?" If yes, Step 2 needs a forcing constraint.
- **Competing objectives?** If the formulation has a penalty term bundling two concerns (cost + penalty×slack), or a constraint that represents a competing goal (return ≥ threshold), consider whether the user wants to explore the tradeoff rather than fix a single point. See [multi-objective-formulation.md](references/multi-objective-formulation.md) for the epsilon constraint approach.
- **Parameter sensitivity / what-if?** If key constraints use fixed values that could vary (budget, demand, service level), use the Scenario Concept pattern — parameterize the constraint, index the decision variable by Scenario, and solve all scenarios in a single solve. This keeps results in the ontology and avoids manual re-solve loops. See [scenario-analysis.md](references/scenario-analysis.md).

### Step 4: Validate
Is the formulation complete and correct?
- Every variable appears in at least one constraint or the objective
- Every constraint references at least one decision variable
- Forcing constraints exist for minimize objectives
- Join paths in `.where()` clauses connect to actual data
- Bounds are consistent (lower <= upper)

### Step 5: Simplify (iterate)
Can we reduce complexity without losing correctness?
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for hard requirements
- Group-level constraints over pairwise/granular combinations

### Step 6: Present, React, Refine
Is the formulation complete — including constraints the user couldn't articulate upfront?
- Solve and present the result to the user (see Constraint Elicitation > Post-Solve: Iterative Refinement)
- Use the result as an elicitation tool to surface latent preferences
- Disambiguate rejections into constraint types, add them, re-solve
- Repeat until the user accepts or feasibility pressure forces prioritization

Steps 1-5 produce the best formulation you can build from what the user has told you. Step 6 discovers what they couldn't tell you until they saw a concrete result. Most real-world formulations require at least one pass through Step 6.

For detailed patterns for each step, see [variable-formulation.md](references/variable-formulation.md), [constraint-formulation.md](references/constraint-formulation.md), and [objective-formulation.md](references/objective-formulation.md).

---

## Formulation Principles

These are overarching principles that apply to all optimization formulations regardless of problem type or solver.

1. **Context-aware:** Suggestions must be tailored to the specific model's entities, not generic templates.
2. **Specific, not generic:** Provide formulations with actual entity names, not abstract examples.
3. **Rationale-driven:** Explain WHY each element makes sense for THIS problem.
4. **Goal-aligned:** If the user provided goals, ensure every formulation element supports those goals.
5. **Valid variations welcome:** There is no single "right answer." Multiple valid approaches exist for most problems. Different valid formulations are acceptable and encouraged, as long as they are grounded in the model and feasible.
6. **All decision variables must be used:** Every variable must appear in at least one constraint or the objective. Variables that appear nowhere are useless -- the solver can set them to anything, which almost always indicates a bug.

---

## Business Language Framing

When presenting variables, constraints, and objectives to the user, describe them in business terms first ("ensure each customer's demand is met," "don't exceed warehouse capacity"), then provide the technical formulation. The analyst selects based on business understanding; the code is generated behind the scenes. Never force users to think in mathematical terms -- business language in, business language out, with valid PyRel as the executable bridge.

**Natural language rule for all user-facing text:** Use domain-natural language in every `description`, `rationale`, `business_mapping`, problem `statement`, and explanation field. Technical `Concept.property` references confuse business users — translate them to readable phrases:
- `Operation.cost_per_unit` -> "cost per unit for each operation"
- `sum(Shipment.quantity)` -> "total shipment volume"
- `Site.capacity` -> "each site's available capacity"
- `UnmetDemand.x_slack` -> "unmet demand quantity"
- `sum(Assignment.x_assigned).per(Worker)` -> "number of assignments per worker"

Code snippets in `solver_registration`, `expression`, and `entity_creation` fields remain technical (valid PyRel). But every field the user reads should sound like a business analyst wrote it, not a database query.

---

## Constraint Elicitation

Constraints are rarely handed to you complete. They emerge through two complementary phases: asking the right questions before solving, and using results to surface preferences the user couldn't articulate in the abstract. This section covers user-facing elicitation techniques. For model-structural constraint discovery (boundary probes, structural probes, multi-concept probes), see [constraint-formulation.md](references/constraint-formulation.md) > Constraint Discovery Patterns.

### Pre-Solve: From Business Language to Constraints

Non-OR users rarely describe their problem in terms of "constraints" and "objectives." Use these diagnostic questions to surface the formulation elements:

| Question to ask | What it surfaces |
|----------------|-----------------|
| "What limits must the solution respect?" | Capacity constraints (budget, headcount, storage, time) |
| "What must every solution achieve?" | Forcing/requirement constraints (meet all demand, cover all shifts) |
| "What would you prefer if possible, but could live without?" | Soft goals → objective terms, not hard constraints |
| "What makes a solution completely unacceptable?" | Hard constraint violations (safety, regulatory, contractual) |
| "Are there minimum service or coverage levels?" | Lower-bound forcing constraints |

**Technique:** Start with "What makes a solution unacceptable?" — this reliably surfaces hard constraints. Then ask "What would make one acceptable solution better than another?" — this surfaces objective terms.

#### Disambiguating Business Language

Common business phrases are ambiguous between constraint and objective. Always clarify before formulating.

| Business phrase | Interpretation A (constraint) | Interpretation B (objective) |
|----------------|-------------------------------|------------------------------|
| "Keep costs under $X" | Hard budget: `total_cost <= X` | Minimize cost (no hard cap) |
| "Each store should get at least 100 units" | Hard minimum: `supply[s] >= 100` | Soft target: penalize shortfall in objective |
| "Try to balance across regions" | Hard fairness: `max - min <= threshold` | Minimize imbalance in objective |
| "We need to cover all shifts" | Hard coverage: `sum(assign[s,w]) >= 1` for all s | Maximize coverage (allow gaps) |
| "Don't use more than 3 suppliers" | Hard cardinality: `sum(use[s]) <= 3` | Minimize number of active suppliers |

**Decision rule:** If violating it makes the solution invalid or unacceptable → **constraint**. If it is a preference or "nice to have" → **objective term**. When unclear, default to soft (objective) and ask the user: "If the optimizer found a solution that violates this but saves 20% on cost, would that be acceptable?"

### Post-Solve: Iterative Refinement

Pre-solve elicitation has a fundamental limit: users cannot always articulate preferences until they see a concrete result that violates them. "No constraints" often means "I can't think of any right now," not "anything goes." Preferences may be real but latent — only surfaceable through confrontation with a specific proposal.

**Principle: Use results as an elicitation tool.** The first solve with minimal constraints is diagnostic, not prescriptive — its purpose is to provoke reactions that reveal the real formulation. This is Step 6 of the Formulation Workflow.

**The refinement loop:**

1. Solve with current constraints (initially minimal)
2. Present the result, highlighting aspects most likely to provoke a reaction
3. Ask targeted reaction questions to surface latent preferences
4. When the user rejects an aspect, disambiguate what type of constraint it implies
5. Add the constraint, re-solve, repeat until the user accepts

**Skill routing within the loop:** Steps 1 and 5 involve solving — use `rai-prescriptive-solver-management` for solver execution. If the result is technically wrong (infeasible, all-zero, solver error), route to `rai-prescriptive-results-interpretation` for diagnosis — it will route back here once the issue is classified as a missing constraint or incomplete formulation. This skill governs steps 2-4: the result is *optimal and technically valid*, but the user's reaction reveals the formulation is incomplete.

**Presenting results to surface latent preferences:**

Don't just show optimal values. Frame them to make implicit preferences visible:
- **Highlight large shifts from status quo** — users often have unstated change-aversion. Showing the magnitude of change surfaces comfort thresholds on rate of change, not just absolute levels.
- **Anchor to domain norms** — reference what peers, industry standards, or historical ranges look like. This calibrates the user's reaction and surfaces social or organizational bounds they haven't stated.
- **Show the trade-off cost** — when a value looks extreme, present what relaxing it would cost in the objective. This distinguishes hard constraints ("no, regardless of cost") from soft preferences ("well, if it saves that much...").
- **Flag boundary solutions** — when the solver pushes a variable to its bound (zero, maximum), call it out explicitly. Boundary solutions frequently violate unstated preferences.

**Post-solve reaction questions:**

| Question | What it surfaces |
|----------|-----------------|
| "Does anything in this result feel wrong or surprising?" | Latent hard constraints |
| "Which value would you change first?" | The tightest latent preference |
| "Would you be comfortable acting on this / presenting this?" | Social, organizational, or reputational constraints beyond personal preference |
| "If this were the only feasible solution, would you change your requirements?" | Whether the discomfort is a hard constraint or a negotiable preference |

**Disambiguating the rejection:**

When a user rejects an aspect of the result, the rejection is ambiguous. Before adding a constraint, determine:
- **Absolute bound vs. change bound** — "too much X" could mean X exceeds an absolute comfort level, or that the jump from the current state is too large. These are different constraints with different formulations.
- **Hard constraint vs. soft preference** — test with: "If violating this saved [meaningful amount] on [objective], would that change your answer?" Hard constraints survive this test; soft preferences don't — and should become objective penalty terms instead.
- **Specific vs. vague** — if the rejection is vague ("this seems aggressive"), probe which dimension: concentration, deviation from current, absolute level, or something else entirely. Each maps to a different constraint type.

**When to stop iterating:**
- The user accepts the result — explicitly, or by shifting to implementation questions. If the user accepts on the first pass, Step 6 is done; do not probe for objections that aren't there.
- The user provides a specific value ("just cap it at 10%") — take the bound directly, no need to run the disambiguation protocol.
- Changes between iterations become marginal
- The user starts making trade-offs between constraints — this signals the efficient frontier has been found and the remaining decisions are genuinely preferential

**Feasibility pressure:** If repeated rejections shrink the feasible region toward infeasibility, pause and present the tension explicitly: these preferences conflict, and the user must prioritize. This is itself a form of constraint elicitation — forcing a ranking among competing bounds.

**Documenting the trail:** Keep a running log of each constraint added and the user reaction that motivated it. This captures the "why" behind bounds that would otherwise look arbitrary in the final formulation — valuable for model maintenance and stakeholder review.

---

## Business-to-Formulation Mapping

Derive the mapping from the ontology structure and the user's stated goals. The ontology's concepts, properties, and relationships tell you what can be controlled (variables), what has limits (constraints), and what the user wants to achieve (objective). Steps 1-3 of the Formulation Workflow provide the process for this.

---

## Multi-Concept Coordination

If you suggest MULTIPLE cross-product/junction concepts, coordinate them as follows:

**1. Flow Networks** -- If concepts represent flow at different stages:
   - Source concept (e.g., ProductionQuantity at factories)
   - Transport concept (e.g., ShipmentQuantity on routes)
   - Destination concept (e.g., FulfillmentQuantity at customers)

   These typically need conservation constraints: inflow = outflow at pure transshipment nodes, or inventory balance at storage nodes.
   **In rationale**: Note which base entity will need a balance constraint.

**2. Selection + Quantity** -- If one concept is binary (use/don't use) and another is continuous quantity on related entities:

   These typically need linking: quantity <= capacity * selection
   **In rationale**: Note the linking relationship needed.

**3. Shared Base Entities** -- If multiple decision concepts connect to the SAME base entity (e.g., both touch Site via relationships):

   These often need a balance/conservation constraint at that entity.
   **In rationale**: Explicitly state "Links to [OtherConcept] via [SharedBase]"

**NOTE**: Without linking constraints, multiple decision concepts may produce:
- Trivial solutions (all zeros -- concepts optimized independently)
- Unbounded solutions (no coupling between flows)
- Inconsistent solutions (flows don't balance)

This is often unintended, but not always wrong — the user may intentionally leave variables unlinked. Flag it as something to verify, not as an error.

**RECOMMENDED in rationale for multi-concept suggestions:**
- State how concepts relate to each other
- Identify shared base entities
- Note what type of linking constraint may be needed

---

## Formulation Simplification

Users often propose formulations that seem natural from a business perspective but create unnecessary complexity. Key simplification heuristics:
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for hard requirements
- Group-level constraints over pairwise/granular combinations

For detailed heuristics, examples, and the over-specification recognition table, see [formulation-simplification.md](references/formulation-simplification.md).

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| All-zero solution on minimize | Missing forcing constraints (demand satisfaction, coverage) | Add `sum(x).per(Entity) >= Entity.demand` or equivalent |
| Infeasible after adding constraints | Conflicting bounds or over-specified assignments | Organize constraints into essential/full tiers; add incrementally |
| Variables created but unused in objective | `solve_for` registered but objective references different properties | Verify objective expression includes all decision variable properties |
| Wrong aggregation scope | `.per(Y)` but Y not joined to the summed concept | Add explicit relationship join in `.where()` |
| Big-M too loose -> slow solve | Using arbitrary `999999` instead of data-driven bound | Use `M = capacity` or `M = max_demand` from entity properties |
| Missing forcing requirement | MINIMIZE objective with no forcing constraint yields zero | Always identify what real-world requirement forces positive activity |
| Constraint references unwired relationship | Relationship declared but no `define()` data binding | Verify all relationships in `.where()` joins have `define()` rules. Unwired relationships cause TyperError or silently match zero entities. |
| `problem.satisfy()` or `model.define()` in a Python loop | Defining constraints per entity in a for loop instead of declaratively | Use vectorized `.where().define()` or `problem.satisfy()` with `.per()`. See `rai-pyrel-coding` Common Pitfalls for before/after examples |
| `Duplicate relationship` / `FDError` on re-solve | Solving multiple scenarios with `populate=True` (default) writes conflicting results to the graph | Use `populate=False` + `Variable.values()` to extract results. Create a fresh `Problem` per loop iteration. See [known-limitations.md](references/known-limitations.md) > Re-Solve Behavior. |
| `TyperError` at solve time with concept-type `identify_by` | Cross-product concept using `identify_by={"a": ConceptA, "b": ConceptB}` passes queries but fails during `problem.solve()` type inference | Use flat identity keys (String or Integer). Encode composite keys as strings (e.g., `f"{a_id}_{b_id}"`) or use separate primitive properties for each dimension |
| `.per(Concept.property)` silently ignored in solver constraints | Property-value grouping (e.g., `.per(Slot.group_name)`) doesn't translate to solver constraints — produces all-zero "optimal" solution | Use entity-level `.per(ParentConcept)` with a relationship join: create a parent concept for the grouping dimension and link via Relationship, then group with `.per(Parent).where(Child.parent(Parent))` |
| Forcing constraint added when objective already penalizes inaction | Adding `>= 1` forcing alongside a cost-penalty objective over-constrains the problem — turns an OPTIMAL-with-cost-tradeoff into INFEASIBLE. Distinct from rows above where forcing IS needed (no penalty mechanism) | Check: does the objective already penalize zero activity? If yes, forcing is redundant. Only add forcing constraints explicitly required by the problem statement |
| Infeasible but not caught before solve | Feasibility arithmetic not validated — e.g., 50 entities need service, 4 periods, max 5/period = 20 slots < 50 needed | Before formulating, verify: `entity_count / periods / capacity_per_period` fits. If not, adjust parameters or confirm the problem allows partial coverage |
| Linear objective over continuous decision variables collapses to one entity | LP pushes to the boundary — without a per-entity upper cap the max-coefficient entity absorbs all budget/weight. Symptom: "+X% lift" headlines masking a single-winner solution. | Add a per-entity upper cap (e.g., `w_i <= 3 * current_i`), switch to a concave objective (`sqrt`, `log`), or piecewise-linear saturation curves. |
| `solve_for(where=expr)` raises `[Invalid operator] Cannot use python's 'bool check'` | `where` argument is iterated as a tuple; passing a bare expression triggers PyRel's `__bool__` guard | Wrap in a list: `where=[Concept.prop >= threshold, ...]` |

For detailed unwired relationship symptoms, checks, and code examples, see [constraint-formulation.md](references/constraint-formulation.md) > Unwired Relationships (Detailed).

---

## Examples

For all example problems and the patterns they demonstrate, see [examples-index.md](references/examples-index.md).

---

When reviewing an existing formulation, see [formulation-analysis-context.md](references/formulation-analysis-context.md).

---

## Known Limitations

### Multi-component objectives with `model.union()`

Do not use `+` to combine cost terms from independent concept groups — this causes `AssertionError: Union outputs must be Vars`. Use `model.union()` instead.

**Critical:** Each branch of `model.union()` must be a **per-entity expression** (bound to a concept), NOT a fully-aggregated scalar. Keep costs at concept level and let the outer `sum()` aggregate:

```python
# CORRECT: per-entity cost expressions inside model.union()
problem.minimize(sum(model.union(
    FreightGroup.holding_cost * sum(x_inv).per(FreightGroup).where(...),  # per-FreightGroup
    Arc.transport_cost * Arc.x_flow,                                       # per-Arc
    Factory.unit_cost * Factory.x_production,                              # per-Factory
)))

# WRONG: scalar sums inside model.union()
problem.minimize(sum(model.union(
    sum(x * FreightGroup.cost),   # scalar — causes AssertionError
    sum(Arc.x_flow * Arc.cost),   # scalar — causes AssertionError
)))
```

For parametric (time-indexed) variables, use `sum(var).per(Concept).where(...)` to aggregate over time while keeping per-entity:
```python
prod_cost = ProdCapacity.production_cost * sum(x_prod).per(ProdCapacity).where(
    ProdCapacity.x_production(t, x_prod))
```

`model.union()` collects ALL matching values from each branch (set union semantics). This is distinct from `|` (pipe), which picks the first successful branch (ordered fallback).

**Additional v1 pitfalls with parametric variables:**
- **`name=[]` must NOT traverse relationships** — use identity fields (e.g., `ProdCapacity.site_id`) not `ProdCapacity.site.name` (causes FD violation)
- **Cross-concept joins need distinct attribute names** — if two concepts both have `site_id` as `identify_by`, rename one (e.g., `wk_site_id`) to avoid ambiguity
- **Only one objective supported** — HiGHS rejects multiple `minimize()`/`maximize()` calls
- **Bi-objective via epsilon constraint**: To optimize two competing objectives, use the epsilon constraint loop — convert the secondary objective to a parameterized constraint and sweep it across the feasible range. Each iteration is a standard single-objective Problem. See [multi-objective-formulation.md](references/multi-objective-formulation.md).

For constraint naming with lists, re-solve behavior (multi-scenario patterns), `| 0` fallback limitation, and numpy type casting, see [known-limitations.md](references/known-limitations.md).

### PyRel is additive — nothing can be removed or modified in-place

PyRel's model and problem APIs are **append-only**. Every call to `model.define()`, `model.Property()`, `model.Concept()`, `problem.solve_for()`, `problem.satisfy()`, `problem.minimize()`/`problem.maximize()` **adds** to the model or problem. There is no API to remove, replace, or modify any existing element.

**This applies to the entire stack:**
- **Attributes/properties:** Adding a new `model.Property()` or `model.Relationship()` grows the model. You cannot delete or rename an existing property.
- **Concepts:** New `model.Concept()` calls add concepts. Existing concepts cannot be removed.
- **Variables:** Each `problem.solve_for()` registers an additional decision variable. You cannot unregister one.
- **Constraints:** Each `problem.satisfy()` accumulates. Adding a "corrected" version does not replace the original — both remain active, and the tighter one binds.
- **Objectives:** Only one `problem.minimize()` or `problem.maximize()` per Problem.

**Practical impact:**
- To change constraints or variables, you must create a **new Problem** and re-register all elements from scratch.
- Multi-scenario optimization must use a new `Problem` per scenario.
- Model-level changes (new properties, concepts) persist across all subsequent Problems on that model — plan the model schema before building formulations.

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Variable formulation | Types, bounds, scope, entity creation, slack variables, context integration | [variable-formulation.md](references/variable-formulation.md) |
| Constraint formulation | Forcing, capacity, balance, linking, `.where()` scoping, parameter derivation | [constraint-formulation.md](references/constraint-formulation.md) |
| Objective formulation | Direction, multi-component, penalty terms, scenario formulation | [objective-formulation.md](references/objective-formulation.md) |
| Problem patterns & validation | Common patterns (assignment, flow, knapsack) and the validation checklist | [problem-patterns-and-validation.md](references/problem-patterns-and-validation.md) |
| Global constraints | `all_different`, `implies`, SOS1/SOS2 syntax, solver requirements, CP vs MIP guide | [global-constraints.md](references/global-constraints.md) |
| Scenario analysis | Scenario Concept vs Loop + where= patterns, decision matrix, code examples | [scenario-analysis.md](references/scenario-analysis.md) |
| Formulation simplification | Static vs dynamic parameters, goals vs constraints, grouped constraints, over-specification | [formulation-simplification.md](references/formulation-simplification.md) |
| Multi-objective formulation | Approach selection, epsilon constraint method, tension heuristics, pitfalls | [multi-objective-formulation.md](references/multi-objective-formulation.md) |
| Examples index | All example problems with patterns demonstrated | [examples-index.md](references/examples-index.md) |
| Formulation analysis context | Naming conventions, alias handling, expression parsing, aggregation patterns for review | [formulation-analysis-context.md](references/formulation-analysis-context.md) |
| Known limitations (secondary) | Constraint naming, re-solve behavior, `\| 0` fallback limitation, numpy type casting | [known-limitations.md](references/known-limitations.md) |
