<!-- TOC -->
- [Optimization Problem Types](#optimization-problem-types)
- [Multi-Objective Detection](#multi-objective-detection)
- [Scenario Detection](#scenario-detection)
- [Formulation Style Detection](#formulation-style-detection)
- [Implementation Hints](#implementation-hints)
- [Structural Checklists](#structural-checklists)
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
- If unsure between two types, check which structural checklist matches more components

**Template examples by problem type:**
- Resource Allocation: `../rai-prescriptive-problem-formulation/examples/continuous_ternary_join.py` (diet/blending), `../rai-prescriptive-problem-formulation/examples/quadratic_pairwise_ref.py` (portfolio balancing)
- Network Flow: `../rai-prescriptive-problem-formulation/examples/flow_conservation.py` (network flow), `../rai-prescriptive-problem-formulation/examples/multi_concept_union_objective.py` (supply chain transport), `../rai-prescriptive-problem-formulation/examples/fixed_charge_facility.py` (facility location)
- Routing: `../rai-prescriptive-problem-formulation/examples/subtour_elimination_mtz.py` (traveling salesman)
- Scheduling/Assignment: `../rai-prescriptive-problem-formulation/examples/binary_coverage_scoped.py` (shift assignment), `../rai-prescriptive-problem-formulation/examples/epoch_filter_assignment.py` (sprint scheduling), `../rai-prescriptive-problem-formulation/examples/hinge_variable_penalty.py` (staffing with overtime), `../rai-prescriptive-problem-formulation/examples/conflict_graph_exclusion.py` (maintenance scheduling)
- Resource Allocation (multi-period): `../rai-prescriptive-problem-formulation/examples/multi_period_flow_conservation.py` (demand planning)
- Pricing: `../rai-prescriptive-problem-formulation/examples/one_hot_temporal_recurrence.py` (retail markdown)

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

This signals `rai-prescriptive-problem-formulation` to use the epsilon constraint approach (see its `multi-objective-formulation.md`) rather than defaulting to a single objective with the secondary as a fixed constraint.

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

This signals `rai-prescriptive-problem-formulation` to use scenario analysis (see its `scenario-analysis.md`) rather than solving for a single fixed parameter value.

---

## Formulation Style Detection

Within the five prescriptive problem types above, formulation can take two styles, each leaning on a different solver family. **This is a style axis cross-cutting the five problem types — not a sixth type.** Any of Resource Allocation, Network Flow / Design, Routing, Scheduling / Assignment, or Pricing can adopt either style when the decisions and data fit.

**MIP-style** (`Problem(model, Float)` + `solver="highs"` / `"gurobi"` / `"ipopt"`):
- Continuous decision variables or continuous data participating in constraints
- Linear objectives, optionally convex quadratic
- LP relaxation provides a useful quality gap on TIME_LIMIT
- Provable optimality is required

**MiniZinc-style** (`Problem(model, Integer)` + `solver="minizinc"`):
- All-integer decisions and data — a single Float variable coerces to MIP
- `min`/`max` in the objective, `count`/`all_different` over decision variables, `implies` cascades, products of decision variables
- Multi-solution enumeration (`solution_limit=K`, `Variable.values`)
- Pure satisfaction / audit / witness / counterexample / configurator / "find K feasible" framings
- Hard to verbalize: "is there any configuration where X happens" — answer is INFEASIBLE = no, OPTIMAL = yes

**Style triggers (any one is sufficient to consider MiniZinc-style):** all-integer decisions and data; `min`/`max` in objective; heavy `all_different` use; complex `implies` cascades; products of decision variables; multi-solution enumeration; audit / witness / property-check; configurator; "find K feasible." **Forcing MIP-style:** any continuous decision or data; convex QP objective; gap-reporting required on TIME_LIMIT; provable optimality required.

**Routing:** Set `minizinc_style_witness_enumeration` in the prescriptive implementation hint when the style triggers fire — particularly when the question is "find K feasible / find counterexamples / enumerate all builds satisfying" rather than minimize / maximize:

```json
"minizinc_style_witness_enumeration": {
  "mode": "enumeration",
  "k": 10,
  "framing": "Show K different facility layouts that all satisfy the affinity constraints"
}
```

`mode` values: `"enumeration"` (return K distinct feasible solutions), `"audit"` (INFEASIBLE = property holds, OPTIMAL/SOLUTION_LIMIT = counterexample found), `"optimization"` (objective set but MiniZinc-style globals/expression surface make it the natural fit).

This signals `rai-prescriptive-problem-formulation` to use MiniZinc-style formulation (see its `csp-formulation.md`) rather than defaulting to MIP-style for the problem type.

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
- Demand satisfaction: "All customer demand must be fulfilled" (`sum(x) >= demand`)
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

## Structural Checklists

After classifying the problem type, use the corresponding checklist to verify the ontology has the structural elements needed.

### Resource Allocation
Deciding how much of a divisible resource goes where.

**Key considerations:**
- Forcing constraints are critical for minimize objectives -- without demand satisfaction or coverage requirements, the solver returns all-zeros
- Balance/fairness constraints (min share per category) prevent the optimizer from concentrating all resources on the highest-return option
- Penalty-based soft constraints handle infeasibility when total demand exceeds total supply

**Structural checklist:**
- **Variables:** Continuous allocation amounts (>= 0), optional binary selection
- **Constraints:** Budget/capacity limits, minimum coverage or return targets, diversification/balance limits
- **Objective:** Minimize cost/risk or maximize return/coverage
- **Verify:** Budget constraint present? Forcing constraint ensures non-trivial allocation? Allocations sum correctly?
- **Formulation style:** MIP-style is the default — divisible-resource problems usually have continuous allocations and a linear cost objective, where LP relaxation drives quality. MiniZinc-style fits when the allocation is fully integer and you want to enumerate K different valid allocations (configurator-style: "show me 10 different valid product bundles satisfying the constraints"). See `rai-prescriptive-problem-formulation/references/csp-formulation.md` for the MiniZinc-style decision flow.

### Network Flow / Design
Moving flow through a graph, optionally selecting which infrastructure to build.

**Key considerations:**
- Flow conservation (inflow == outflow) must hold at every interior node -- missing even one node creates a "leak"
- Source and sink nodes are exceptions to conservation -- they inject/absorb flow
- When binary open/close decisions are present, linking constraints (`flow <= capacity * x_open`) are essential
- Multi-component objectives (fixed cost + variable transport cost) need `model.union()` to combine terms from different scopes

**Structural checklist:**
- **Variables:** Flow on arcs (continuous, >= 0, <= capacity), optional binary open/close for facilities/arcs
- **Constraints:** Flow conservation at interior nodes, arc capacity, source/sink limits, linking constraints (flow only if open)
- **Objective:** Minimize transport + fixed cost, or maximize total flow
- **Verify:** Every interior node has conservation constraint? Source/sink boundary conditions correct? No isolated nodes? Linking constraint prevents flow through closed arcs?
- **Formulation style:** MIP-style is the default — flow volumes are typically continuous and LP relaxation drives the gap. MiniZinc-style fits when flows are unit-valued (path-routing, packet-style) and the question is "find K feasible routings" or "enumerate all topologies satisfying capacity bounds." See `rai-prescriptive-problem-formulation/references/csp-formulation.md`.

### Routing
Determining paths or sequences for vehicles/shipments visiting locations.

**Key considerations:**
- Subtour elimination is the defining challenge -- without it, the solver finds disconnected short loops instead of a single tour
- MTZ formulation (auxiliary ordering variable `u`) is simplest but weakest LP relaxation; acceptable for moderate sizes
- Degree constraints (exactly 1 in-edge, 1 out-edge) are necessary but not sufficient -- they don't prevent subtours alone
- Symmetry breaking (fix depot node ordering) reduces search space significantly

**Structural checklist:**
- **Variables:** Binary arc selection, auxiliary ordering variables (for subtour elimination)
- **Constraints:** Visit each location exactly once, degree constraints, vehicle capacity, subtour elimination (MTZ or similar)
- **Objective:** Minimize total distance/time/cost
- **Verify:** Subtour elimination present? Depot start/end constraints? Degree constraints enforce exactly one in-edge and one out-edge?
- **Formulation style:** MIP-style is dominant for cost-objective routing — MTZ subtour elimination + LP relaxation drives the gap on TIME_LIMIT. MiniZinc-style fits when the routing problem is combinatorial with `all_different` constraints, or when the question shifts to "find K distinct tours" (witness enumeration). See `rai-prescriptive-problem-formulation/references/csp-formulation.md`.

### Scheduling / Assignment
Deciding when activities occur or which resources handle which tasks.

**Key considerations:**
- Create variables only for valid (resource, task) pairs using `where=` -- not every resource can handle every task
- Both directions need constraints: each task covered (forcing) AND each resource not overloaded (capacity)
- For time-based scheduling, precedence constraints (`start_j >= end_i` for dependent tasks) are often missing
- CP solvers (MiniZinc) may outperform MIP for highly constrained combinatorial assignment

**Structural checklist:**
- **Variables:** Binary assignment (resource-to-task), start/completion times, optional integer ordering
- **Constraints:** Each task assigned exactly once, resource capacity not exceeded, precedence ordering, time windows, no-overlap
- **Objective:** Minimize makespan, tardiness, or cost; maximize coverage
- **Verify:** Binary variables for decisions? Task coverage (each task assigned)? Resource capacity not exceeded? Time variables bounded within horizon?
- **Formulation style:** Most live use of MiniZinc-style. Slot assignment with `all_different`, precedence cascades via `implies`, multi-solution enumeration of valid schedules, and pure-satisfaction "is there any schedule covering all shifts" framings all fit MiniZinc-style naturally. MIP-style fits when the objective is a linear cost or makespan minimization with LP-relaxation value. See `rai-prescriptive-problem-formulation/references/csp-formulation.md` — particularly the integer-slot-with-sentinel and audit/witness idioms.

### Multi-Period Considerations (applies to any type)
When a problem has a temporal/period dimension, these additional structural elements apply regardless of the base type:

- The inventory/state balance equation (`state_t = state_{t-1} + inflow_t - outflow_t`) links consecutive periods -- missing it means periods are independent
- Initial conditions (starting state) must be set, otherwise the first period is unconstrained
- Terminal conditions prevent the model from "dumping" everything in the last period
- Shortage/surplus variables with penalties handle uncertainty gracefully

**Additional checklist for multi-period problems:**
- Balance constraint connects consecutive periods?
- Initial state specified?
- Terminal conditions set?
- Storage/capacity constraints per period?

### Pricing
Setting prices to optimize revenue subject to demand response and business rules.

**Key considerations:**
- The demand-price relationship is the core modeling challenge -- must be captured either as a constraint or embedded in the objective
- Markdown problems typically require monotonicity (prices can only decrease over time)
- Revenue = price * demand is bilinear; if both are variables, linearization or piecewise approximation is needed

**Structural checklist:**
- **Variables:** Price levels (continuous or discrete tiers), demand response quantities
- **Constraints:** Price bounds, markdown monotonicity, inventory/demand coupling
- **Objective:** Maximize revenue or profit
- **Verify:** Demand-price relationship captured? Price bounds from data? Revenue calculation correct?
- **Formulation style:** MIP-style by default — continuous price levels, possibly bilinear revenue terms. MiniZinc-style fits when prices are restricted to a discrete tier menu and the objective is a revenue lookup via `implies` cascade (planogram-style: prices and SKUs are all-integer, decision-indexed table lookups for revenue per chosen tier). See `rai-prescriptive-problem-formulation/references/csp-formulation.md` — particularly the implies-cascade table-lookup idiom.

---

## Feasibility Assessment Framework

When evaluating whether a problem statement is suitable for optimization, assess on two dimensions:

### 1. Data Feasibility (from the data model)
- **Entities to decide about?** Are there concepts that represent things to allocate, assign, schedule, or route?
- **Numeric attributes to optimize?** Costs, values, distances, capacities — properties with Float/Integer types
- **Constraint data?** Capacities, demands, limits, budgets — bounds that restrict decisions
- **Relationships between entities?** Connections that enable flow, assignment, or dependency constraints

### 2. Value Assessment (from the problem statement)
- **Clear decision?** Allocate, assign, schedule, route, price — an actionable verb implying choices
- **Recurring decision?** Operational decisions made repeatedly benefit most from optimization (vs one-time analysis)
- **Stakes mentioned?** Costs, efficiency, service levels, revenue — quantifiable impact
- **Output drives action?** The solution should change how resources are deployed, not just produce a report

### Verdict Scale
- **GOOD:** Both data and value are strong — proceed to formulation
- **PARTIAL:** Data exists but gaps need enrichment, OR value is clear but decision structure is ambiguous
- **POOR:** Missing fundamental data (no numeric attributes, no constraint data) or the problem isn't suitable for optimization (e.g., pure analytics, no decision)

**Key principle:** Evaluate the problem STATEMENT, not a solution. Do not suggest specific variables, constraints, or objectives at this stage — that comes in the formulation phase.
