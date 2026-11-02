<!-- TOC -->
- [Optimization Problem Types](#optimization-problem-types)
- [Multi-Objective Detection](#multi-objective-detection)
- [Scenario Detection](#scenario-detection)
- [Formulation Style Detection](#formulation-style-detection)
- [Implementation Hints](#implementation-hints)
- [Structure notes by problem type](#structure-notes-by-problem-type)
  - [Resource Allocation](#resource-allocation)
  - [Network Flow / Design](#network-flow--design)
  - [Routing](#routing)
  - [Scheduling / Assignment](#scheduling--assignment)
  - [Pricing](#pricing)
<!-- /TOC -->

## Optimization Problem Types

Classify each prescriptive suggestion into one of these types. Use both **semantic signals** (from the problem statement) and **structural signals** (from the ontology/formulation).

These are the ONLY allowed problem types. Every suggestion must use exactly one of these values:

| Type | Semantic Signals | Structural Signals |
|------|-----------------|-------------------|
| **Resource Allocation** | "allocate", "distribute", "budget", "blend", "portfolio", "mix" | Continuous variables summing to a total; budget/capacity constraints; no graph structure |
| **Network Flow / Design** | "ship", "transport", "route flow", "supply chain", "facility", "build/open" | Edge/arc concepts with source/destination; flow conservation constraints; optional binary open/close |
| **Routing** | "visit", "tour", "sequence", "path", "TSP", "delivery route" | Binary arc selection; degree constraints (1 in, 1 out); subtour elimination |
| **Scheduling / Assignment** | "assign", "schedule", "shift", "who does what", "when", "sprint" | Binary assignment variables; coverage + capacity constraints; time windows or precedence |
| **Pricing** | "price", "markdown", "discount", "revenue optimization" | Price variables; demand-response coupling; monotonicity constraints |

**Note:** "Multi-period" is an attribute of a problem, not a type. A multi-period inventory problem is Resource Allocation; a multi-period scheduling problem is Scheduling / Assignment. Classify by the core decision structure, not the temporal dimension.

**Disambiguation rules:**
- If the problem has **graph structure** (source -> destination edges): Network Flow/Design or Routing, not Resource Allocation
- If the decision is **binary assignment** (who does what): Scheduling/Assignment, even if it minimizes cost
- If the problem has **both** network structure **and** binary facility selection: Network Design (not just flow)
- If unsure between two types, check which type's structural signals match more components

**Template examples by problem type:**
- Resource Allocation: `../rai-prescriptive-problem/examples/continuous_ternary_join.py` (diet/blending), `../rai-prescriptive-problem/examples/quadratic_pairwise_ref.py` (portfolio balancing)
- Network Flow: `../rai-prescriptive-problem/examples/flow_conservation.py` (network flow), `../rai-prescriptive-problem/examples/multi_concept_added_objective.py` (supply chain transport), `../rai-prescriptive-problem/examples/fixed_charge_facility.py` (facility location)
- Routing: `../rai-prescriptive-problem/examples/subtour_elimination_mtz.py` (traveling salesman)
- Scheduling/Assignment: `../rai-prescriptive-problem/examples/binary_coverage_scoped.py` (shift assignment), `../rai-prescriptive-problem/examples/epoch_filter_assignment.py` (sprint scheduling), `../rai-prescriptive-problem/examples/hinge_variable_penalty.py` (staffing with overtime), `../rai-prescriptive-problem/examples/conflict_graph_exclusion.py` (maintenance scheduling)
- Resource Allocation (multi-period): `../rai-prescriptive-problem/examples/multi_period_flow_conservation.py` (demand planning)
- Pricing: `../rai-prescriptive-problem/examples/one_hot_temporal_recurrence.py` (retail markdown)

---

## Multi-Objective Detection

Detect when a prescriptive problem has competing objectives that warrant a Pareto frontier rather than a single-point solution.

**Structural test:** If improving objective A naturally worsens B under the same constraints, they are in tension → flag for multi-objective. If both can improve simultaneously → not competing → combine into single objective.

**Explicit signals (user intent):**
- The user states two distinct goals with different directions (minimize one, maximize another)
- The user asks about tradeoffs, frontiers, or the cost of improving one metric
- The user wants to compare operating points rather than get a single answer

**Implicit signals (problem structure):**
- Penalty term bundling two concerns: `minimize(cost + PENALTY * unmet)` → cost and service are competing
- Constraint that represents a goal: `return >= 15%` → could be an objective to explore, not a fixed bound
- Two goals mentioned separately, even if the user hasn't framed them as competing

**Common tension patterns:**

| Primary | Secondary | Tension |
|---------|-----------|---------|
| Cost | Performance/quality/coverage | Improving coverage requires more expensive options |
| Risk | Return | Higher return requires riskier allocations |
| Speed/throughput | Fairness/balance | Maximizing throughput concentrates on best performers |
| Quantity | Quality | Producing more dilutes quality given fixed resources |

**Routing:** Set `competing_objectives` in the prescriptive implementation hint:

```json
"competing_objectives": {
  "primary": "minimize cost",
  "secondary": "maximize coverage",
  "tension": "improving coverage requires more expensive routes"
}
```

This signals `rai-prescriptive-problem` to use the epsilon constraint approach (see its `multi-objective-formulation.md`) rather than defaulting to a single objective with the secondary as a fixed constraint.

---

## Scenario Detection

Detect when a prescriptive problem should explore how the solution changes under different parameter assumptions.

**Structural test:** If a key constraint parameter could plausibly take different values and the user would benefit from seeing how the solution shifts → flag for scenario analysis.

**Explicit signals (user intent):**
- The user asks what happens under different conditions (budget levels, demand forecasts, capacity limits)
- The user wants to compare solutions across parameter levels
- The user frames the problem around uncertainty or planning for multiple cases

**Implicit signals (problem structure):**
- A key constraint parameter (budget, demand, capacity, service level) is a single fixed value but represents uncertainty or a choice the user hasn't committed to
- Multiple values already present in the data for a parameter (e.g., regional budgets, seasonal demand)
- The optimal decision likely changes meaningfully across plausible parameter ranges

**Which pattern to flag:**

| Situation | Pattern | Why |
|-----------|---------|-----|
| Parameters vary but problem structure stays the same | Scenario Concept (one solve, all scenarios) | Budget, demand, threshold levels — same variables and constraints |
| Entity subsets change between scenarios | Loop + where= (separate solve per scenario) | Remove a supplier, solve per region — problem structure differs |

**Routing:** Set `scenario_parameter` in the prescriptive implementation hint:

```json
"scenario_parameter": {
  "parameter": "budget",
  "values": "varies across regions or levels",
  "pattern": "scenario_concept"
}
```

This signals `rai-prescriptive-problem` to use scenario analysis (see its `scenario-analysis.md`) rather than solving for a single fixed parameter value.

---

## Formulation Style Detection

Formulation style is an axis cutting across the five problem types above — **not a sixth type**. MIP-style (`Problem(model, Float)` + HiGHS / Gurobi / Ipopt) is the default; the style choice belongs to `rai-prescriptive-problem` > MIP-style vs CSP-style. Discovery only flags the CSP-style (`Problem(model, Integer)` + MiniZinc) signals:

- All-integer decisions and data — a single Float variable or Float data rules CSP-style out
- `all_different`-shaped requirements ("all distinct", "no two share a value")
- "Find K feasible" / enumerate valid configurations — multi-solution enumeration is a MiniZinc capability
- Audit / witness / counterexample framings — the answer is the termination status (`INFEASIBLE` = the property holds)

When the signals are inconclusive, the **Formulation style** note under each problem type below gives that type's default.

**Routing:** Set `csp_style_witness_enumeration` in the prescriptive implementation hint when the style triggers fire — particularly when the question is "find K feasible / find counterexamples / enumerate all builds satisfying" rather than minimize / maximize:

```json
"csp_style_witness_enumeration": {
  "mode": "enumeration",
  "k": 10,
  "framing": "Show K different facility layouts that all satisfy the affinity constraints"
}
```

`mode` values: `"enumeration"` (return K distinct feasible solutions), `"audit"` (INFEASIBLE = property holds, OPTIMAL/SOLUTION_LIMIT = counterexample found), `"optimization"` (objective set but CSP-style globals/expression surface make it the natural fit).

This signals `rai-prescriptive-problem` to use CSP-style formulation (see its `csp-formulation.md`) rather than defaulting to MIP-style for the problem type.

---

## Implementation Hints

For each prescriptive suggestion, provide an implementation hint with these fields. Note: these are internal technical fields used by downstream tools -- the user sees the `statement` and `description` fields, which must use business language.

### decision_scope
Identify WHERE decisions are made. Include brief context about the decision structure, not just a bare concept name. Each suggestion should have a distinct scope description -- even if the same concept, describe what different decision is being made.
- Example: "How much to ship along each transportation route" (not just "Operation")
- Example: "Which technician handles each maintenance task in each period" (not just "TechnicianMachinePeriod")
- Check if a relationship already exists before suggesting a cross-product
- Only use cross-product (X x Y) when no relationship exists between the concepts

### forcing_requirement
The most important field. A MINIMIZE objective with no forcing constraint always yields zero -- the solver sets everything to 0 for minimum cost. Identify what real-world requirement forces activity:
- Demand satisfaction: "All customer demand must be fulfilled" (`sum(Flow.x) >= demand`)
- Coverage requirements: "Every shift must have at least one worker assigned"
- Assignment requirements: "Each task must be handled by exactly one resource"
- Look for Demand/Order/Requirement concepts with quantity fields -- these often define forcing constraints

### objective_property
Which model property to optimize. Should reference an actual property name from the ontology, but describe it naturally in the statement: "transportation cost per unit" rather than "OPERATION.COST_PER_UNIT".

### Gap identification (prescriptive-specific)

The formulation layer vs model layer boundary for optimization:

| Layer | Examples | Has source table? |
|-------|----------|-------------------|
| **Base model** | Customer, Site, Order with properties from schema | Yes -- loaded from data |
| **Formulation** | FulfillmentAssignment, production_quantity, total_cost expression | No -- created during problem setup |

Every MODEL_GAP fix must reference a specific source table and column. Decision variables, cross-product concepts, and computed expressions are formulation layer -- NOT model gaps.

---

## Structure notes by problem type

Per problem type: the PyRel-specific structure notes and the default formulation style.

### Resource Allocation
Deciding how much of a divisible resource goes where.

- **Formulation style:** MIP-style is the default — divisible-resource problems usually have continuous allocations and a linear cost objective, where LP relaxation drives quality. CSP-style fits when the allocation is fully integer and you want to enumerate K different valid allocations (configurator-style: "show me 10 different valid product bundles satisfying the constraints"). See `rai-prescriptive-problem/references/csp-formulation.md` for the CSP-style decision flow.

### Network Flow / Design
Moving flow through a graph, optionally selecting which infrastructure to build.

**Key considerations:**
- When binary open/close decisions are present, linking constraints (`flow <= capacity * x_open`) are essential
- Multi-component objectives (fixed cost + variable transport cost) add separately keyed sums from each scope, defaulting each potentially empty total to zero

- **Formulation style:** MIP-style is the default — flow volumes are typically continuous and LP relaxation drives the gap. CSP-style fits when flows are unit-valued (path-routing, packet-style) and the question is "find K feasible routings" or "enumerate all topologies satisfying capacity bounds." See `rai-prescriptive-problem/references/csp-formulation.md`.

### Routing
Determining paths or sequences for vehicles/shipments visiting locations.

- **Formulation style:** MIP-style is dominant for cost-objective routing — MTZ subtour elimination + LP relaxation drives the gap on TIME_LIMIT. CSP-style fits when the routing problem is combinatorial with `all_different` constraints, or when the question shifts to "find K distinct tours" (witness enumeration). See `rai-prescriptive-problem/references/csp-formulation.md`.

### Scheduling / Assignment
Deciding when activities occur or which resources handle which tasks.

- Create variables only for valid (resource, task) pairs using `where=` -- not every resource can handle every task
- **Formulation style:** Most live use of CSP-style. Slot assignment with `all_different`, precedence cascades via `implies`, multi-solution enumeration of valid schedules, and pure-satisfaction "is there any schedule covering all shifts" framings all fit CSP-style naturally. MIP-style fits when the objective is a linear cost or makespan minimization with LP-relaxation value. See `rai-prescriptive-problem/references/csp-formulation.md` — particularly the integer-slot-with-sentinel and audit/witness idioms.

### Pricing
Setting prices to optimize revenue subject to demand response and business rules.

- **Formulation style:** MIP-style by default — continuous price levels, possibly bilinear revenue terms. CSP-style fits when prices are restricted to a discrete tier menu and the objective is a revenue lookup via `implies` cascade (planogram-style: prices and SKUs are all-integer, decision-indexed table lookups for revenue per chosen tier). See `rai-prescriptive-problem/references/csp-formulation.md` — particularly the implies-cascade table-lookup idiom.
