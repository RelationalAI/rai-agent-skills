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
1. Ground in the base ontology via `relationalai.semantics.inspect.schema(model)` — concepts, properties, types, relationships you're about to reference
2. Define decision variables (type, bounds, scope, naming)
3. Define constraints (forcing, capacity, balance, linking; validate interactions)
4. Define objective (direction, coefficients, multi-component handling)
5. Validate the complete formulation (structure, completeness, feasibility, data) — includes pre-solver audit that decision variables / constraints / objectives registered correctly
6. Solve and refine — diagnose surprising results via targeted `display(ref)` / `verify` / `solve_info`, simplify once correct, re-solve
7. Post-solve refinement — present results, surface user reactions, iterate on the formulation (see Workflow Step 7)

---

## Quick Reference — Problem API

```python
from relationalai.semantics.reasoners.prescriptive import Problem
from relationalai.semantics.std import aggregates as aggs

problem = Problem(model, Float)

# Decision variable — prefer scoped form (where=[...]) over unscoped.
# Capture the returned ref for targeted diagnostics later (problem.display(x_flow), etc).
x_flow = problem.solve_for(
    Lane.flow,
    where=[Lane.active],
    name=["item_id", "src_id"],
    lower=0.0,
    type="cont",
)

# Constraint — capture the ref to inspect just this constraint's grounded form
cap = problem.satisfy(
    model.require(
        aggs.sum(Lane.flow).per(Source).where(Lane.from_source(Source)) <= Source.capacity
    ),
    name=["cap", Source.id],   # name=[Entity.id] makes display rows identifiable
)

# Objective
cost = problem.minimize(aggs.sum(Lane.flow * Lane.unit_cost))
```

| Method | Signature | Purpose |
|--------|-----------|---------|
| `solve_for` | `(expr, where=, populate=True, name=, type=, lower=, upper=, start=)` | Declare decision variable. Returns `ProblemVariable` (a Concept usable in `model.define()`, `model.select()`, `.ref()`, and as `display(part=)` argument). `type`: `"cont"`, `"int"`, `"bin"` |
| `satisfy` | `(expr, name=)` | Add constraint. Returns `ProblemConstraint` — capture this ref to inspect the constraint's grounded form via `problem.display(ref)`. |
| `minimize` | `(expr, name=)` | Set minimization objective. Returns `ProblemObjective` — capture for targeted `display(ref)`. |
| `maximize` | `(expr, name=)` | Set maximization objective. Returns `ProblemObjective` — capture for targeted `display(ref)`. |
| `solve` | `(solver, time_limit_sec=, print_format=, ...)` | Execute solve. Solvers: `"highs"`, `"minizinc"`, `"ipopt"`, `"gurobi"`. `print_format` (`"moi"`, `"latex"`, `"mof"`, `"lp"`, `"mps"`, `"nl"`) populates `solve_info().printed_model` |
| `solve_info` | `()` | Post-solve summary (`termination_status`, `objective_value`, `solve_time_sec`, `num_points`, `error`, `printed_model`). Has `.display()` method. |
| `verify` | `(*fragments)` | Post-solve check that the returned solution satisfies the original `Fragment`s at IC strictness (tighter than solver tolerance). Pass the original `model.require(...)` values, not `ProblemConstraint` refs. |
| `display` | `(part=None, *, limit=None, print_output=True)` | Print materialized formulation. `display()` shows everything. `display(ref)` (the ref returned by `solve_for`/`satisfy`/`minimize`/`maximize`) shows just that component. `display(model.select(ref).where(<filter>))` shows the filtered subset. `display(ref, limit=N)` or `display(limit=N)` caps each table at top-N rows by `.name` ascending — summary counts stay true. |
| `num_variables` / `num_constraints` / `num_min_objectives` / `num_max_objectives` | `()` | Engine-queryable counts; usable inside `model.require(...)` to assert formulation cardinality before solve |
| `Variable.values` | `(sol_index, value_ref)` | Property on `ProblemVariable`. Extracts solution values at `sol_index` (0-based), binding each value to `value_ref` (a `Float.ref()` or `Integer.ref()`). Use inside `model.select(...).where(var.values(sol_index, value_ref))`. Primary pattern for `populate=False` workflows. |
| `problem.variables` / `problem.constraints` / `problem.objectives` | (attributes) | Lists of registered refs in declaration order — iterate to walk an unfamiliar Problem |

---

## Formulation Workflow

**Interaction mode:** Before starting, ask the user which mode they prefer:
- **Guided** — present your proposed variables, constraints, and objective at each step and confirm before proceeding. Best when the user has domain context to share — problem framing involves subjective judgment (what's a hard constraint vs. a soft goal, how to scope variables, which business rules matter most).
- **One-shot** — produce the best formulation you can in a single pass. Best when the user wants speed and will review/iterate after.

After a question is selected (from question discovery) and the ontology is enriched (if needed), build the formulation in this order:

### Step 1: Ground in the base ontology

Prescriptive formulations reference concepts, properties, and relationships from an existing model. Before writing `solve_for` / `satisfy` / `minimize` / `maximize`, confirm every name and type you're about to use against the real schema:

```python
from relationalai.semantics import inspect

schema = inspect.schema(model)

# Every concept referenced in the formulation
for name in referenced_concepts:
    assert name in schema, f"Concept {name} not in model"
    props = schema[name].properties
    # surface any properties used in bounds, constraints, or the objective
```

Catches two silent-failure modes that account for most prescriptive errors:

1. **Hallucinated surface** — `Customer.tier` in a constraint when the real property is `Customer.category`. Solver happily runs on wrong variables and returns nonsense.
2. **Wrong-type inference** — using an `Integer` property as if it were `Float` (or vice versa) when the type now propagates from `TableSchema`. Silent coercion masks incorrect bound derivation.

**When to skip:** this step is cheap but not free. Skip on small greenfield models or one-shot formulations where the model fits in a single code block you just wrote.

### Step 2: Define Variables
What decisions are being made? What can the solver control?
- Start with the base model context — examine concepts, properties, relationships (Variable Context Integration)
- Identify the primary decision entity first, then auxiliary/aggregation variables (Variable Principles)
- Choose variable types (continuous/integer/binary) and set bounds from data (Advanced Variable Patterns)
- For minimize objectives, include a slack/unmet variable to avoid infeasibility

### Step 3: Define Constraints
What rules must the solution satisfy?
- Start with model structure + user goals (Constraint Context Integration)
- Add forcing constraints first — these prevent trivial zero solutions for minimize objectives
- Add capacity/resource constraints from data properties
- Add flow conservation if the model has network structure
- Derive parameters from data ranges, not arbitrary values (Parameter Derivation from Data)

### Step 4: Define Objective(s)
What are we optimizing?
- Start with user's stated goal — map business language to minimize/maximize (Objective Context Integration)
- Reference defined variables and data properties in the expression
- Check for trivial solution risk: "If all variables = 0, are all constraints satisfied?" If yes, Step 3 needs a forcing constraint.
- **Competing objectives?** If the formulation has a penalty term bundling two concerns (cost + penalty×slack), or a constraint that represents a competing goal (return ≥ threshold), consider whether the user wants to explore the tradeoff rather than fix a single point. See [multi-objective-formulation.md](references/multi-objective-formulation.md) for the epsilon constraint approach.
- **Parameter sensitivity / what-if?** If key constraints use fixed values that could vary (budget, demand, service level), use the Scenario Concept pattern — parameterize the constraint, index the decision variable by Scenario, and solve all scenarios in a single solve. This keeps results in the ontology and avoids manual re-solve loops. See [scenario-analysis.md](references/scenario-analysis.md).

### Step 5: Validate
Is the formulation complete and correct?
- Every variable appears in at least one constraint or the objective
- Every constraint references at least one decision variable
- Join paths in `.where()` clauses connect to actual data
- Bounds are consistent (lower <= upper)
- **Trivial-solution gate (run before presenting or solving):** substitute every decision variable with its objective-preferred bound (typically zero for minimize) and evaluate against the actual input data, not abstractly. If every constraint still holds and the objective is at its preferred end, the solver will return that trivial point as optimal — the formulation is wrong, not merely under-specified. The non-obvious failure is a forcing constraint that exists in the formulation but is vacuous against the current data (its `where=` predicate matches no rows); see the *Missing forcing requirement* and *Wrong aggregation scope* rows in Common Pitfalls for related modes. Do not present a formulation that fails this gate — a non-OR user will accept it, run it, and conclude optimization "doesn't work." If the gate's outcome depends on the input data, state that dependence with row-count evidence.
- **Data-driven feasibility precheck:** when constraint bounds derive from input data, verify the constraint system admits at least one feasible point given that data. Aggregate at the **constraint's natural disaggregation level** — per-entity for per-entity constraints, per-group for grouped ones; a single global total can mask per-slice infeasibility (`Σ supply ≥ Σ demand` may hold while every per-entity slice fails). Run the check as PyRel aggregation queries (see `rai-querying`) so it pushes down to the warehouse (e.g., Snowflake) without pulling rows. If lower-bound exceeds upper-bound at any slice, the formulation is infeasible by construction; surface to the user before solve. See [examples/presolve_feasibility_gate.py](examples/presolve_feasibility_gate.py).

**Pre-solver audit:** before calling `problem.solve(...)`, run a three-part check (a–c below).

**(a) Registration.** `solve_for` / `satisfy` / `minimize` / `maximize` register concepts named `Variable`, `Constraint`, `Objective` (plus a per-solve `Variable_<id>` subconcept for each decision variable). They appear in `inspect.schema(model).concepts`:

```python
from relationalai.semantics import inspect

schema = inspect.schema(model)
variables   = [c for c in schema.concepts if "Variable" in c.extends]
constraints = [c for c in schema.concepts if c.name == "Constraint" or "Constraint" in c.extends]
objectives  = [c for c in schema.concepts if c.name == "Objective"  or "Objective"  in c.extends]

# Confirm one Variable_<id> per solve_for call, one Constraint_<id> per satisfy,
# one Objective_<id> per minimize/maximize.
```

**(b) Binding cardinality.** Registration does NOT mean the variable binds to any rows. A `solve_for(..., where=[always_false])` still registers a `Variable_<id>` subconcept but has zero bindings — the solver will run on an empty decision set. Check each `Variable_<id>` for non-empty binding:

```python
for var_concept in variables:
    resolved = model.concept_index[var_concept.name]
    n = len(model.select(resolved).to_df())
    if n == 0:
        # The where= clause excluded every row. Fix the predicate
        # (wrong property name, wrong threshold, missing join) and re-check.
        raise ValueError(f"{var_concept.name} has 0 bindings")
```

**(c) Coefficient presence.** Properties referenced as objective or constraint coefficients must be populated by `model.define(...)` — declared-but-unbound coefficient Properties yield silent zero-coefficient terms; the solver returns OPTIMAL with a vacuous objective. Distinct from (b): (b) catches empty *decision-variable scope*, (c) catches unbound *coefficient data*. Both surface as OPTIMAL with `obj=0`.

```python
for coef_prop in objective_coefficient_properties:
    n = len(model.select(coef_prop).to_df())
    if n == 0:
        raise ValueError(f"Coefficient {coef_prop} is unbound — objective term silently zero")
```

**(d) Constraint binding cardinality.** Capture each `satisfy()` return value at declaration time, then verify the constraint grounded on the expected number of groupings before solving. Distinct from (b)/(c): (b) catches empty variable scope from a `where=` predicate, (c) catches unbound coefficients, (d) catches per-grouping bodies that PyRel dropped (per the `satisfy()` docstring; empty-body groupings are dropped) because a referenced bound was empty for some entities — the *exact* mode that returns OPTIMAL with the missing entities silently unconstrained.

```python
cap_constr = problem.satisfy(model.require(usage <= Entity.cap), name=["cap", Entity.id])
if len(model.select(cap_constr).to_df()) != len(model.select(Entity).to_df()):
    raise AssertionError("cap_constr short — Entity.cap unpopulated for some entities")
```

For the full pattern (drill-in with `display(cap_constr, limit=10)` before raising, multi-Concept counts, and the per-failure-mode lookup) see [diagnostic-workflow.md](references/diagnostic-workflow.md) and [rai-prescriptive-solver-management/references/pre-solve-validation.md](../rai-prescriptive-solver-management/references/pre-solve-validation.md).

Together, (a)–(d) are the downstream complement to Step 1's base-ontology grounding: Step 1 verifies the *inputs* to formulation exist; Step 5 verifies the *outputs* registered correctly, bound to data, weighted by populated coefficients, and grounded on the right number of groupings.

For runtime grounding inspection (does each constraint disaggregate as intended? does the objective expand with non-zero coefficients?) use targeted `problem.display(ref)` — see Step 6.

When the formulation fails to generate or compile (before a solve is even attempted), look up the root cause in the unified failure taxonomy at `rai-prescriptive-results-interpretation/references/failure-taxonomy.md` (`generates` and `compiles` levels).

### Step 6: Solve and refine (iterate)

The agent's debugging loop. Each `solve_for` / `satisfy` / `minimize` / `maximize` returns a ref (`ProblemVariable` / `ProblemConstraint` / `ProblemObjective`); capturing it at write time enables targeted inspection.

**Solve and triage:**
- `si = problem.solve_info(); si.display()` — always run first. Inspect `termination_status`, `objective_value`, `error`.
- Branch by status: `INFEASIBLE` → walk constraints (below); `OPTIMAL` with suspicious values → check for unbound coefficients or vacuous forcing constraints; `OPTIMAL` with right shape → `problem.verify(*original_fragments)` if tolerance-sensitive.

**Diagnose with targeted display:**
- `problem.display(var_ref)` — bounds and entity tuples per instance; catches `where=` over- or under-scoping
- `problem.display(constr_ref)` — grounded sums per row; catches `.per()` mis-scoping (the silent OPTIMAL trap), redundant or contradictory constraints, and per-grouping bodies dropped per the `satisfy()` docstring when a referenced bound was empty for some entities (Step 5 (d) catches this statically; targeted display localizes which rows survived)
- `problem.display(obj_ref)` — expanded objective; catches unbound coefficients (silent zero terms)
- `for c in problem.constraints: problem.display(c)` — when one of many constraints is the offender (typical for INFEASIBLE)
- For sampling very-large constraints (`display(ref, limit=N)`, `display(limit=N)`, Fragment-filter form), see [rai-prescriptive-solver-management/references/formulation-display.md](../rai-prescriptive-solver-management/references/formulation-display.md) > Targeted Inspection.

**Simplify once correct:**
- Static parameters over dynamic calculations
- Objective terms for goals; constraints for hard requirements
- Group-level constraints over pairwise/granular combinations

Loop until the result is correct, fast enough, and defensible enough to take to Step 7. See [diagnostic-workflow.md](references/diagnostic-workflow.md) for failure-mode-by-failure-mode guidance and [formulation-simplification.md](references/formulation-simplification.md) for the simplification patterns in depth.

### Step 7: Present, React, Refine
Is the formulation complete — including constraints the user couldn't articulate upfront?
- Solve and present the result to the user (see Constraint Elicitation > Post-Solve: Iterative Refinement)
- Use the result as an elicitation tool to surface latent preferences
- Disambiguate rejections into constraint types, add them, re-solve
- Repeat until the user accepts or feasibility pressure forces prioritization

Steps 1-6 produce the best formulation you can build from what the user has told you. Step 7 discovers what they couldn't tell you until they saw a concrete result. Most real-world formulations require at least one pass through Step 7.

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

**Natural language rule for all user-facing text:** Use domain-natural language in every `description`, `rationale`, `business_mapping`, problem `statement`, and explanation field. Technical `Concept.property` references confuse business users — translate them to readable phrases (e.g., `sum(X.quantity).per(Entity)` → "total X quantity per entity"; `Entity.capacity` → "each entity's available capacity").

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

**Principle: Use results as an elicitation tool.** The first solve with minimal constraints is diagnostic, not prescriptive — its purpose is to provoke reactions that reveal the real formulation. This is Step 7 of the Formulation Workflow.

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
- The user accepts the result — explicitly, or by shifting to implementation questions. If the user accepts on the first pass, Step 7 is done; do not probe for objections that aren't there.
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
| Constraint references unwired relationship | Relationship declared but no `define()` data binding | Verify all relationships in `.where()` joins have `define()` rules. Unwired relationships silently match zero entities — the constraint is dropped and the solver returns OPTIMAL with a vacuous objective. |
| Per-entity constraint silently drops for entities missing the bound data | `.per(Entity)` with a bound that's empty for some entities — PyRel relational semantics drop empty-body groupings (`satisfy()` docstring). Solver returns OPTIMAL with the missing entities effectively unconstrained. | Capture the constraint ref: `cap_constr = problem.satisfy(model.require(...), name=["cap", Entity.id])`. After `solve_for`/`satisfy` (before solving), check cardinality: `len(model.select(cap_constr).to_df()) == len(model.select(Entity).to_df())`. If short, populate the missing values, coalesce to a default (`Entity.bound \| 0.0`), or join via a fully-populated relationship. Use `problem.display(cap_constr)` (or `problem.display(cap_constr, limit=10)` for large constraints) to inspect the surviving rows by name. |
| `problem.satisfy()` or `model.define()` in a Python loop | Defining constraints per entity in a for loop instead of declaratively | Use vectorized `.where().define()` or `problem.satisfy()` with `.per()`. See `rai-pyrel-coding` Common Pitfalls for before/after examples |
| `Duplicate relationship` / `FDError` on re-solve | Solving multiple scenarios with `populate=True` (default) writes conflicting results to the graph | Use `populate=False` + `Variable.values()` to extract results. Create a fresh `Problem` per loop iteration. See [known-limitations.md](references/known-limitations.md) > Re-Solve Behavior. |
| Forcing constraint added when objective already penalizes inaction | Adding `>= 1` forcing alongside a cost-penalty objective over-constrains the problem — turns an OPTIMAL-with-cost-tradeoff into INFEASIBLE. Distinct from rows above where forcing IS needed (no penalty mechanism) | Check: does the objective already penalize zero activity? If yes, forcing is redundant. Only add forcing constraints explicitly required by the problem statement |
| Infeasible but not caught before solve | Feasibility arithmetic not validated — e.g., 50 entities need service, 4 periods, max 5/period = 20 slots < 50 needed | Before formulating, verify: `entity_count / periods / capacity_per_period` fits. If not, adjust parameters or confirm the problem allows partial coverage |
| Linear objective over continuous decision variables collapses to one entity | LP pushes to the boundary — without a per-entity upper cap the max-coefficient entity absorbs all budget/weight. Symptom: "+X% lift" headlines masking a single-winner solution. | Add a per-entity upper cap (e.g., `w_i <= 3 * current_i`), switch to a concave objective (`sqrt`, `log`), or piecewise-linear saturation curves. |
| `solve_for(where=expr)` errors on PyRel's `__bool__` guard | `where` argument is iterated as a tuple; passing a bare expression triggers Python truthiness, which PyRel rejects | Wrap in a list: `where=[Concept.prop >= threshold, ...]` |
| `problem.satisfy(<expr>)` raises `TypeError` complaining it expects a `Fragment` | Bare comparison expression passed to `problem.satisfy()` instead of the result of `model.require(...)` | Wrap with `model.require(<expr>)` or use `model.where(<scope>).require(<expr>)`. See [constraint-formulation.md](references/constraint-formulation.md) > Style 1/Style 2 |
| `solve_for(concept_ref.property)` raises `TypeError` about Chain start | First arg requires bare `Concept.property` — refs are valid only inside `where=[...]`. Symmetric instinct from using refs in scope clauses doesn't extend to the variable declaration itself | Pass bare `Concept.property` to `solve_for(...)`; reserve refs for `where=[...]` joins |

For detailed unwired relationship symptoms, checks, and code examples, see [constraint-formulation.md](references/constraint-formulation.md) > Unwired Relationships (Detailed).

---

## Examples

For all example problems and the patterns they demonstrate, see [examples-index.md](references/examples-index.md).

---

When reviewing an existing formulation, see [formulation-analysis-context.md](references/formulation-analysis-context.md).

---

## Known Limitations

### Multi-component objectives with `model.union()`

The cleanest pattern for combining cost terms across independent concept groups is `model.union()` with one per-entity expression per branch and an outer `sum()`:

```python
problem.minimize(sum(model.union(
    ResourceGroup.holding_cost * sum(x_inv).per(ResourceGroup).where(...),  # per-ResourceGroup
    Arc.transport_cost * Arc.x_flow,                                        # per-Arc
    Factory.unit_cost * Factory.x_production,                               # per-Factory
)))
```

For parametric (time-indexed) variables, use `sum(var).per(Concept).where(...)` to aggregate over time while keeping per-entity:
```python
prod_cost = ProdCapacity.production_cost * sum(x_prod).per(ProdCapacity).where(
    ProdCapacity.x_production(t, x_prod))
```

`model.union()` collects ALL matching values from each branch (set union semantics). This is distinct from `|` (pipe), which picks the first successful branch (ordered fallback).

**Additional v1 pitfalls with parametric variables:**
- **`name=[]` parts must resolve to scalars** — see [variable-formulation.md](references/variable-formulation.md) > Variable naming (`name=[]`).
- **Cross-concept joins need distinct attribute names** — if two concepts both have `site_id` as `identify_by`, rename one (e.g., `wk_site_id`) to avoid ambiguity
- **Only one objective supported** — HiGHS rejects multiple `minimize()`/`maximize()` calls
- **Bi-objective via epsilon constraint**: To optimize two competing objectives, use the epsilon constraint loop — convert the secondary objective to a parameterized constraint and sweep it across the feasible range. Each iteration is a standard single-objective Problem. See [multi-objective-formulation.md](references/multi-objective-formulation.md).

For constraint naming with lists, re-solve behavior (multi-scenario patterns), `| 0` fallback limitation, and numpy type casting, see [known-limitations.md](references/known-limitations.md).

### Problem is additive — solve_for / satisfy / minimize accumulate

`Problem` inherits PyRel's append-only behavior (see `rai-pyrel-coding` > Definitions). Every `problem.solve_for()`, `problem.satisfy()`, `problem.minimize()`/`maximize()` **adds** to the Problem — there is no remove/replace API.

- **Variables:** Each `solve_for()` registers an additional decision variable.
- **Constraints:** Each `satisfy()` accumulates. Adding a "corrected" version does not replace the original — both remain active, and the tighter one binds.
- **Objectives:** Only one `minimize()` or `maximize()` per Problem.

**Practical impact:**
- To remove or weaken an existing constraint or variable, create a **new Problem** and re-register only the elements you want.
- Re-calling `problem.solve()` on the same Problem is safe: it re-runs the solver against the current (accumulated) formulation and updates variable values. Use this when you want to add more constraints/variables and re-solve. Use a new Problem only when you want to *remove* something.
- Multi-scenario optimization where the constraint set differs per scenario should use a new Problem per scenario. If only parameter values change, the Scenario Concept pattern (one Problem, one solve, scenario as a data dimension) is preferred — see [scenario-analysis.md](references/scenario-analysis.md).
- Model-level additions (new properties, concepts) persist across all subsequent Problems on that model — plan the model schema before building formulations.

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
| Diagnostic workflow | Capture-ref pattern, targeted `display(ref)`, sampling large constraints (`limit=N` / Fragment filter), `solve_info` triage, `verify`, INFEASIBLE walk, trivial-OPTIMAL localization | [diagnostic-workflow.md](references/diagnostic-workflow.md) |
| Fix generation guidelines | Root cause taxonomy, grounding rules, join path fixes, trivial/infeasible fix strategies | [fix-generation-guidelines.md](references/fix-generation-guidelines.md) |
| Examples index | All example problems with patterns demonstrated | [examples-index.md](references/examples-index.md) |
| Formulation analysis context | Naming conventions, alias handling, expression parsing, aggregation patterns for review | [formulation-analysis-context.md](references/formulation-analysis-context.md) |
| Known limitations (secondary) | Constraint naming, re-solve behavior, `\| <literal>` fallback limitation, numpy type casting | [known-limitations.md](references/known-limitations.md) |
