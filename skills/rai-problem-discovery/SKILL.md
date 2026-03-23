---
name: rai-problem-discovery
description: Guides exploration of what problems an RAI ontology can solve, classifies each by reasoner type, and assesses data readiness. Use before choosing a reasoner workflow or when scoping what to build next.
---

# Problem Discovery
<!-- v1-SENSITIVE -->

## Summary

**What:** Multi-reasoner problem and question discovery from ontology models. Surfaces what the data can answer, classifies by reasoner type, and routes to the right workflow.

**When to use:**
- Suggesting problems/questions for a given ontology
- Analyzing a user's problem statement to determine reasoner type and feasibility
- Classifying whether a problem needs prescriptive, graph, predictive, or rules reasoning
- Identifying multi-reasoner chains (e.g., predict demand then optimize allocation)
- Assessing data feasibility before committing to a workflow

**When NOT to use:**
- Formulating optimization variables, constraints, objectives — see `rai-prescriptive-problem-formulation`
- PyRel syntax and coding patterns — see `rai-pyrel-coding`
- Ontology modeling or enrichment — see `rai-ontology-design`
- Solver execution and diagnostics — see `rai-prescriptive-solver-management`
- Post-solve interpretation — see `rai-prescriptive-results-interpretation`

**Overview:**
1. Analyze the ontology to identify what the data can support
2. Classify each opportunity by reasoner type (prescriptive, graph, predictive, rules)
3. Identify multi-reasoner chains where applicable
4. Assess feasibility (READY / MODEL_GAP / DATA_GAP)
5. Present ranked suggestions to the user
6. Route the selected problem to the appropriate reasoner workflow

---

## Quick Reference

| Signal in Ontology | Reasoner | Question Pattern |
|--------------------|----------|-----------------|
| Constrained resources, costs, capacities | **Prescriptive** | "What should we do?" — allocate, schedule, route |
| Network topology, graph structure | **Graph** | "What patterns exist?" — centrality, clusters, paths |
| Temporal data, features, historical outcomes | **Predictive** | "What will happen?" — forecast, classify |
| Threshold/status fields, business rules | **Rules** | "Is this valid?" — compliance, classification |

| Feasibility | Meaning | Next Step |
|-------------|---------|-----------|
| **READY** | All data in model | Proceed to reasoner workflow |
| **MODEL_GAP** | Data in schema, not mapped | Enrich ontology first |
| **DATA_GAP** | Data doesn't exist | Blocks the problem |

---

## Discovery Workflow

Problem discovery is the analyst's springboard into data-driven reasoning. The ontology reveals what problems the data can support -- the analyst learns what's possible before choosing what to pursue.

### Steps

1. **Analyze the ontology** — what concepts, relationships, and data exist? Look for network topology (graph), temporal patterns (predictive), constrained decisions (prescriptive), threshold/status fields (rules).
2. **Classify by reasoner** — for each opportunity, determine which reasoner(s) apply (→ Reasoner Classification). Tag with `reasoners` field.
3. **Identify chains** — where one reasoner's output enables another (→ Multi-Reasoner Chaining, Cumulative Discovery).
4. **Assess feasibility** — READY / MODEL_GAP / DATA_GAP for each suggestion (→ Feasibility Framework).
5. **Generate ranked suggestions** — with implementation hints per reasoner type (→ reference files: `prescriptive.md`, `graph.md`, `predictive.md`, `rules.md`).
6. **User selects** — route to the appropriate reasoner workflow (→ Post-Discovery Routing). If MODEL_GAP, enrich first (→ Enrichment Handoff).

### Your role

- Analyze the ontology to surface opportunities grounded in actual data
- Write the `statement` field as a business question the analyst can evaluate -- not a technical formulation
  - GOOD: "Allocate inventory across warehouses to minimize stockouts while staying within budget"
  - GOOD: "Schedule technicians to maintenance tasks to minimize downtime and balance workload"
  - BAD: "Minimize sum(OPERATION.COST_PER_UNIT * OPERATION.X_FLOW) subject to SITE.CAPACITY"
  - BAD: "Optimize Shipment.quantity across Operation edges"
- Maintain full technical specificity in `implementation_hint` fields -- these drive downstream workflow and must reference actual concept/property names
- For each suggestion, distinguish what's ready to pursue, what needs model enrichment (auto-fixable), and what needs new data (blocks the problem)
- Suggest problems across reasoner types when the data supports it -- don't default to only one type

### Presenting the discovery landscape

Present suggestions as a landscape of what the data can answer -- across reasoner types -- not as a menu of one kind of problem.

Frame suggestions by the type of question they answer:
- "Here's what we can tell you about structure and connectivity" (graph)
- "Here's what we can predict" (predictive)
- "Here's what we can optimize" (prescriptive)
- "Here's what we can validate/enforce" (rules)

Connect each suggestion to the decision or insight it enables, not just the analysis it performs:
- NOT: "Run centrality analysis on the supply network"
- YES: "Identify which warehouses are critical connectors -- so you know where disruptions would cascade and where to invest in redundancy"

---

## Reasoner Classification

Each suggestion must be tagged with one or more reasoner types. Use these signals to classify:

| Signal | Primary Reasoner | Question Pattern |
|--------|-----------------|------------------|
| Optimizing decisions over constrained resources | **Prescriptive** | "What should we do?" — allocate, schedule, route, price |
| Understanding structure, connectivity, influence | **Graph** | "What patterns exist?" — who is central, what clusters exist, shortest path |
| Predicting outcomes from features | **Predictive** | "What will happen?" — forecast, classify, detect anomalies |
| Enforcing business rules and logical constraints | **Rules** | "Is this valid?" — compliance, classification, derivation |

**Disambiguation rules:**
- "What should we do?" → prescriptive (optimization)
- "What patterns/structure exist?" → graph
- "What will happen / what category?" → predictive
- "Is this correct / does this comply?" → rules
- If a problem spans two categories, consider a multi-reasoner chain

For detailed problem types, classification signals, and structural checklists per reasoner, see the reasoner-specific reference files: `prescriptive.md`, `graph.md`, `predictive.md`, `rules.md`.

---

## Multi-Reasoner Chaining

Some problems benefit from multiple reasoners in sequence. Each stage's output feeds the next stage's input.

| Chain | Pattern | Example |
|-------|---------|---------|
| Predictive -> Prescriptive | Predict parameters, then optimize | Forecast demand -> optimize inventory allocation |
| Graph -> Prescriptive | Discover structure, then optimize over it | Identify supply network clusters -> optimize routing within clusters |
| Rules -> Predictive | Validate/classify, then predict | Flag compliant transactions -> predict approval likelihood |
| Graph -> Predictive | Extract features from structure, then predict | Compute centrality scores -> predict churn |
| Predictive -> Rules | Predict outcomes, then enforce rules | Predict risk scores -> flag violations above threshold |

**How to suggest chained problems:**
- State the full chain in the `statement` field: "Forecast regional demand (predictive), then optimize warehouse allocation to minimize stockouts (prescriptive)"
- Tag with `reasoners: ["predictive", "prescriptive"]` (ordered by execution sequence)
- Implementation hint includes per-stage detail: what each stage needs and what it produces for the next stage

**Inter-stage handoff:**
- Stage 1 output becomes Stage 2 input context (e.g., predicted demand values feed prescriptive constraint data)
- If Stage 1 produces derived data (predictions, graph metrics), Stage 2 may need model enrichment to incorporate it
- Each stage should be independently valuable -- if Stage 2 fails, Stage 1 results are still useful

---

## Cumulative Discovery

Each reasoner adds new concepts and properties to the ontology. Discovery should surface not just what's solvable now, but what becomes solvable after earlier stages run.

### Reasoner output enables new problems

| Stage 1 Output | What It Adds to Ontology | Stage 2 Problems Unlocked |
|----------------|--------------------------|---------------------------|
| Graph centrality | `node.centrality_score` | Predictive: centrality as feature. Prescriptive: weight allocation by node importance. |
| Graph reachability | impact_count, affected flags | Prescriptive: minimize disruption to high-impact nodes. Rules: alert on critical dependencies. |
| Graph WCC / community | `node.component_id`, `node.community_label` | Prescriptive: optimize within-cluster vs cross-cluster. Rules: flag isolated components. |
| Predictive forecasting | `Forecast.predicted_value` | Prescriptive: optimize against predicted demand/delays. |
| Predictive classification | `Entity.risk_probability` | Rules: flag above threshold. Prescriptive: incorporate risk as constraint. |

### How to suggest cumulative problems

When generating suggestions:
1. First, identify problems solvable with the current ontology (standard discovery)
2. Then, for graph/predictive suggestions, ask: "What additional problems does this output enable?"
3. Present second-order problems with a clear dependency: "After running [Stage 1], this becomes solvable"

Second-order problems are expansion opportunities, not alternatives. The analyst sees: "Here's what you can do now. Here's what opens up if you also run graph analysis."

### The cumulative narrative

The ontology grows through use:
- **Start:** what exists (base model from data)
- **After graph:** + what's connected, what's central, what's clustered
- **After predictive:** + what will happen, what's at risk
- **After prescriptive:** + what should we do, what's optimal

Each layer makes the next more powerful. Discovery should convey this progression.

---

## Feasibility Framework

Shared across all reasoners. Classify each suggestion's data readiness:

- **READY**: All required data is in the model. Can proceed directly to the reasoner workflow.
- **MODEL_GAP**: Data exists in the schema (tables/columns) but isn't mapped to the model. Auto-fixable via `enrich_ontology`. Each gap should reference a specific `source_table` and `source_column` — without these, the enrichment tool cannot generate the correct `define()` rule.
- **DATA_GAP**: Required data doesn't exist in any table. Blocks the problem. Include only if the domain has very limited potential -- flag what data would be needed.

**Order suggestions by feasibility:** READY first, then MODEL_GAP. Prefer suggestions that can proceed without manual data collection.

### Classification decision tree

1. All needed data is already in the model ("Already in model" in schema info)? → **READY**
2. Needed data exists in schema as unmapped column ("Available for enrichment")? → **MODEL_GAP** (include `model_gap_fixes` with `source_table`/`source_column`)
3. Business parameter the user provides (budget, threshold, target %)? → **parameter_gap** (informational, doesn't change feasibility)
4. Data not in any table? → **DATA_GAP**

If the schema shows NO unmapped columns, there are no model_gaps — all suggestions should be READY. Decision variables, cross-product concepts, and computed expressions are created during formulation — they are NOT model_gaps.

### Gap identification rules

Check the schema info provided in the prompt context:

**If there are "Available for PROPERTY enrichment" or "Available for RELATIONSHIP enrichment" columns:**
- Property gaps (gap_type="property") -- unmapped scalar columns (costs, capacities, quantities). Each must specify `source_table` and `source_column`.
- Relationship gaps (gap_type="relationship") -- unmapped FK columns (typically ending in _ID). Each must specify `source_table` and `source_column`.

**Business parameters the user provides** (budget, threshold, target %):
- These are parameter_gap -- informational only, doesn't change feasibility classification. The user supplies these at solve time.

**If the schema shows NO unmapped columns (everything is "Already in model"):**
- There are no model_gaps. All suggestions should be READY.
- Decision variables, extended concepts, and cross-product relationships are formulation constructs -- they are NOT model_gaps.

**What is NOT a model gap:**
- Decision variables (e.g., quantity_to_allocate) -- created during formulation
- Extended/cross-product concepts (e.g., Worker x Shift) -- created during formulation
- Computed properties (e.g., total_cost = qty * unit_cost) -- defined as expressions
- Predictions, graph metrics, derived classifications -- created by reasoner output

**The boundary:** If a proposed enrichment has no source table, it belongs to the reasoner workflow (formulation layer, prediction pipeline, etc.), not the base model.

| Layer | Examples | Has source table? |
|-------|----------|-------------------|
| **Base model** | Customer, Site, Order with properties from schema | Yes -- loaded from data |
| **Reasoner workflow** | allocation_qty, predicted_demand, centrality_score, compliance_flag | No -- created by reasoner |

---

## Problem Selection

Selecting the right problem is "Phase 0" -- before any reasoner workflow begins. A poor choice wastes all downstream effort.

### The feasibility-value intersection

Focus on problems at the intersection of **available data** (feasible) and **useful answers** (valuable). Work forwards from what data exists and backwards from what decisions/insights matter.

**Data feasibility green flags:**
- Data already used for reporting/analytics
- Clear ownership and regular refresh cycles
- Entities and relationships well-defined
- Historical data available for validation

**Data feasibility red flags:**
- "We should have that data somewhere..."
- Key parameters require manual estimation
- Data exists but in incompatible formats
- Critical relationships not captured in existing data

**Answer value green flags:**
- Clear pain point with current process
- Decision or insight needed frequently (daily/weekly)
- Quantifiable cost of current approach
- Stakeholder actively asking for solution

**Answer value red flags:**
- "It would be nice to know..."
- No clear decision-maker or consumer
- Answer requires organizational changes to act on
- Benefits are diffuse or hard to measure

### Problem selection scoring

For each candidate, score on a 1-5 scale:

| Criterion | What to assess |
|-----------|---------------|
| Data availability | How much required data exists today? |
| Data quality | How reliable is the data? |
| Decision/insight frequency | How often is this needed? |
| Impact | What is the cost of not having this answer? |
| Implementation path | Can the answer be acted upon? |

Prioritize problems scoring high on BOTH data AND value dimensions.

### Common anti-patterns

- **"Perfect Data" Trap:** Waiting for ideal data before starting. Start with available data; use sensitivity analysis to identify critical gaps.
- **"Boil the Ocean" Trap:** Trying to answer everything at once. Start with one question, one scope, one time period.
- **"Solution Looking for a Problem" Trap:** Forcing a reasoner where simpler approaches work. Ask: "What is wrong with a simple rule or heuristic here?"
- **"Data Rich, Insight Poor" Trap:** Lots of data but unclear what to answer. Start with the decision/question, work backwards to required data.

### Pre-workflow checklist

Before starting any reasoner workflow, confirm:

- [ ] Can I access the required data today?
- [ ] Is the data complete enough to generate meaningful results?
- [ ] Who specifically will use this output?
- [ ] What will they do differently because of it?
- [ ] Is this the smallest useful version of the problem?
- [ ] Can the results be validated against known cases?

---

## Variety Heuristics

When suggesting problems, explore different aspects of the domain where the data supports it:
- Different reasoner types (don't suggest only optimization if graph/predictive questions are viable)
- Different decision structures (assignment vs selection vs sizing vs sequencing)
- Different objectives/questions (cost vs coverage vs structure vs prediction)
- Different constraint emphases (capacity-driven vs demand-driven vs coverage-driven)

**Cross-domain coverage:** If the model's concepts span multiple distinct business domains, spread suggestions across them rather than clustering in one area. Identify domains semantically from concept names and relationships (e.g., concepts prefixed with "Jira" vs "GitHub" vs "RAI" suggest different domains). Aim for at least one suggestion per domain before doubling up on any.

If the domain is narrow (e.g., only budget allocation data), it's fine to suggest variations on the same theme with different objectives or constraints -- as long as each is grounded in the actual ontology and represents a meaningfully different business question.

Vary the business question itself, not just constraints -- use different objectives that reference different properties from the model.

---

## Enrichment Handoff

When the user selects a problem with **MODEL_GAP** feasibility:

1. The next step is `enrich_ontology`, not the reasoner workflow
2. Show the specific gaps and their source tables/columns from `model_gap_fixes`
3. After enrichment, re-assess feasibility -- it should now be READY
4. Then proceed to the reasoner workflow via Post-Discovery Routing

For graph problems, enrichment may also include constructing derived relationships needed for graph edges (e.g., a `ships_to` relationship derived from Shipment data, or operation-based site connectivity).

---

## Post-Discovery Routing

After the user selects a problem, route to the appropriate reasoner workflow based on the `reasoners` tag.

### Suggestion output schema

Each suggestion includes a `reasoners` field — an ordered list specifying the execution sequence. Single-reasoner problems have one entry; chained problems list stages in order.

```json
{
  "statement": "Identify which warehouses are critical connectors in the supply network",
  "reasoners": ["graph"],
  "feasibility": "READY",
  "implementation_hint": {
    "algorithm": "eigenvector_centrality",
    "graph_construction": {
      "node_concept": "Site",
      "directed": false,
      "weighted": true,
      "edge_definition": "Operation linking source_site to output_site"
    },
    "output_binding": "(node, centrality_score)"
  }
}
```

**Implementation hint fields vary by reasoner:**

| Reasoner | Fields |
|----------|--------|
| **prescriptive** | `decision_scope`, `forcing_requirement`, `objective_property`, `decision_variable`, `scenario_parameter` |
| **graph** | `algorithm`, `graph_construction` (`node_concept`, `directed`, `weighted`, `edge_definition`), `target_filter`, `output_binding` |
| **rules** | `rule_type`, `source_concept`, `condition_properties`, `join_path`, `threshold`, `output_type`, `output_property`, `downstream_use` |
| **predictive** | `type`, `mode` (`pre_computed` or `rai_predictive`), `target_concept`, `target_property`, `feature_properties`, `output_concept`, `pre_computed_table` |

**For chained problems**, use a `stages` array in `implementation_hint`:

```json
{
  "statement": "Identify critical supply nodes, then optimize allocation weighted by importance",
  "reasoners": ["graph", "prescriptive"],
  "feasibility": "READY",
  "implementation_hint": {
    "stages": [
      {
        "reasoner": "graph",
        "algorithm": "eigenvector_centrality",
        "graph_construction": { "node_concept": "Site", "directed": false, "weighted": true },
        "output_binding": "Site.centrality_score"
      },
      {
        "reasoner": "prescriptive",
        "decision_scope": "Site.allocation_quantity",
        "objective_property": "maximize weighted_allocation (centrality_score * quantity)"
      }
    ]
  }
}
```

### Reasoner workflows

| Reasoner | Workflow | Status |
|----------|----------|--------|
| **prescriptive** | `suggest_variables` -> `suggest_constraints` -> `suggest_objective` -> `validate_formulation` -> `solve_problem` | LIVE |
| **graph** | `suggest_graph_analysis` -> `configure_graph` -> `run_graph_algorithm` -> results | LIVE |
| **rules** | `suggest_rules` -> `define_rules` -> `evaluate_rules` -> results | LIVE |
| **predictive** | `define_features` -> `configure_model` -> `train` -> `evaluate` | PLANNED |

### add_to_formulation routing

`add_to_formulation` inspects the selected problem's `reasoners` field and routes to the appropriate workflow:

**Single-reasoner routing:**
- `["prescriptive"]` → `suggest_variables` -> `suggest_constraints` -> `suggest_objective` -> `validate_formulation` -> `solve_problem`
- `["graph"]` → `suggest_graph_analysis` -> `configure_graph` -> `run_graph_algorithm` -> results
- `["rules"]` → `suggest_rules` -> `define_rules` -> `evaluate_rules` -> results

**Chained routing** (execute stages sequentially):
- `["graph", "prescriptive"]` →
  - Stage 1: `configure_graph` -> `run_graph_algorithm` -> results
  - Bridge: `enrich_ontology` (add graph outputs as model properties)
  - Stage 2: `suggest_variables` -> ... -> `solve_problem`
- `["rules", "prescriptive"]` →
  - Stage 1: `define_rules` -> `evaluate_rules` -> results
  - Bridge: rule outputs become constraint filters for optimization
  - Stage 2: `suggest_variables` -> ... -> `solve_problem`

Each stage is independently valuable — if Stage 2 fails, Stage 1 results are still useful.

For chained problems, complete each stage in order. After Stage N completes, enrich the model with its output if needed, then proceed to Stage N+1.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Suggesting problems with no data backing | Skipping feasibility check before proposing | Use READY/MODEL_GAP/DATA_GAP classification; verify data exists before suggesting |
| All suggestions are the same reasoner type | Only considering optimization use cases | Check ontology for graph structure, temporal features, rule patterns -- not just optimization |
| Chained problem with unclear handoff | Missing interface specification between stages | Each stage must define inputs and outputs explicitly |
| Missing forcing requirement (prescriptive) | Overlooking mandatory constraint in prescriptive problems | See `prescriptive.md` for forcing constraint and implementation hint guidance |
| All suggestions cluster in one domain | Not surveying the full concept space | Spread across distinct business domains present in concept names |
| Confusing model gaps with reasoner-layer constructs | Treating computed outputs as missing data | Decision variables, predictions, graph metrics have no source table -- they're not model gaps |
| Suggesting DATA_GAP problems as top choices | Prioritizing novelty over feasibility | Order by feasibility: READY first, MODEL_GAP second, DATA_GAP only if domain is very narrow |

---

## Reference files

| Reference | Description | File |
|-----------|-------------|------|
| Prescriptive | Optimization problems — minimize cost, maximize coverage, scheduling | [prescriptive.md](references/prescriptive.md) |
| Graph | Graph analytics — centrality, community detection, shortest path | [graph.md](references/graph.md) |
| Predictive | Predictive modeling — forecasting, classification, anomaly detection | [predictive.md](references/predictive.md) |
| Rules | Business rules — compliance, validation, classification from known facts | [rules.md](references/rules.md) |

---

## Examples

| Pattern | Description | File |
|---------|-------------|------|
| Prescriptive routing | Discovery scenario walkthrough for optimization problems | [prescriptive_routing.md](examples/prescriptive_routing.md) |
| Graph routing | Discovery scenario walkthrough for graph analytics | [graph_routing.md](examples/graph_routing.md) |
| Predictive routing | Discovery scenario walkthrough for predictive modeling | [predictive_routing.md](examples/predictive_routing.md) |
| Chained routing | Discovery scenario walkthrough for multi-reasoner pipelines | [chained_routing.md](examples/chained_routing.md) |
