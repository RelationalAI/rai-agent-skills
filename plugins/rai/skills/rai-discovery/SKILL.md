---
name: rai-discovery
description: Discover questions to answer or problems to solve. Surfaces what the data can support, classifies by reasoner type, and routes to the right workflow. Use before choosing a reasoner workflow or when scoping what to build next.
---

# Question Discovery
<!-- v1-SENSITIVE -->

## Summary

**What:** Multi-reasoner question discovery from ontology models. Surfaces what the data can answer, classifies by reasoner type, and routes to the right workflow.

**When to use:**
- Suggesting questions a given ontology can answer
- Analyzing a user's question to determine reasoner type and feasibility
- Classifying whether a question needs prescriptive, graph, predictive, or rules reasoning
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
6. Route the selected question to the appropriate reasoner workflow

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
| **DATA_GAP** | Data doesn't exist | Blocks the question |

---

## Discovery Workflow

Question discovery is the analyst's springboard into data-driven reasoning. The ontology reveals what questions the data can answer -- the analyst learns what's possible before choosing what to pursue.

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
- For each suggestion, distinguish what's ready to pursue, what needs model enrichment (auto-fixable), and what needs new data (blocks the question)
- Suggest questions across reasoner types when the data supports it -- don't default to only one type

### Presenting the discovery landscape

Present suggestions as a landscape of what the data can answer -- across reasoner types -- not as a menu of one kind of question.

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
- If a question spans two categories, consider a multi-reasoner chain
- **Competing objectives?** If the problem has two measurable goals in tension (improving one worsens the other) — flag `competing_objectives` in the prescriptive hint. See `prescriptive.md` § Multi-Objective Detection for the checklist.
- **Parameter variations?** If a key constraint parameter could plausibly vary and the user would benefit from comparing solutions across levels — flag `scenario_parameter` in the prescriptive hint. See `prescriptive.md` § Scenario Detection for the checklist.

For detailed question types, classification signals, and structural checklists per reasoner, see the reasoner-specific reference files: `prescriptive.md`, `graph.md`, `predictive.md`, `rules.md`.

---

## Multi-Reasoner Chaining

Some questions require multiple reasoners in sequence. Each stage's output enriches the ontology, enabling the next stage.

### Chaining principles

1. **Each stage enriches the same ontology.** Outputs (predictions, scores, flags, allocations) become queryable properties. The ontology grows through use — it accumulates knowledge from each reasoner.
2. **Each stage must be independently valuable.** If a downstream stage fails or isn't needed, the upstream results still stand on their own.
3. **The user's question drives stage selection.** Chains aren't fixed pipelines — the agent identifies which stages are needed based on what the user asks and what the ontology can support.
4. **Stages follow a natural progression:** understand structure (graph) and validate data (rules) → predict what will happen (predictive) → decide what to do (prescriptive). Not every chain uses all stages.
5. **Later stages reference earlier outputs as data.** Predicted values become constraint parameters. Centrality scores become allocation weights. Rule flags become filters. The handoff is always through the ontology.

### Common chain patterns

| Chain | Pattern | What flows between stages |
|-------|---------|---------------------------|
| Predictive → Prescriptive | Predict parameters, then optimize | Forecasted values become constraint/objective data |
| Graph → Prescriptive | Discover structure, then optimize over it | Centrality scores, cluster labels become weights/filters |
| Rules → Prescriptive | Validate/classify, then optimize given compliance | Flags and classifications constrain the feasible set |
| Rules → Graph | Flag entities, then analyze their structural role | Flagged nodes become the focus of graph analysis |
| Graph → Predictive | Extract structural features, then predict | Centrality, component membership become prediction features |
| Predictive → Rules | Predict outcomes, then enforce thresholds | Predicted scores are evaluated against business rules |

### Suggesting chained questions

- State the full chain in the `statement` field: "Forecast regional demand (predictive), then optimize warehouse allocation to minimize stockouts (prescriptive)"
- Tag with `reasoners: ["predictive", "prescriptive"]` (ordered by execution sequence)
- Implementation hint includes per-stage detail: what each stage needs and what it produces for the next stage

### Inter-stage handoff

- Stage N output becomes Stage N+1 input context — always through ontology properties
- If Stage N produces derived data (predictions, graph metrics, rule flags), Stage N+1 may need model enrichment to incorporate it
- Each stage should be independently valuable — if Stage 2 fails, Stage 1 results are still useful

### Implementation pattern

Each stage enriches the shared ontology with new properties. Downstream stages consume those properties as if they were base data.

- **Enrichment write-back:** A stage's output becomes a new `Property` or `Relationship` on an existing concept via `model.define()`. Downstream stages reference it like any other property.
- **DataFrame bridge:** When a stage produces results as a pandas DataFrame (e.g., from an external API), load into the model via `model.data()` and bind with `model.define()`.
- **Fallback operator (`|`):** Allows downstream stages to degrade gracefully when an upstream enrichment is missing for some entities — e.g., `Entity.predicted_value | Entity.current_value`.

---

## Cumulative Discovery

Each reasoner adds new concepts and properties to the ontology. Discovery should surface not just what's answerable now, but what becomes answerable after earlier stages run.

### Reasoner output enables new questions

| Stage 1 Output | What It Adds to Ontology | Stage 2 Questions Unlocked |
|----------------|--------------------------|---------------------------|
| Graph centrality | `node.centrality_score` | Predictive: centrality as feature. Prescriptive: weight allocation by node importance. |
| Graph reachability | impact_count, affected flags | Prescriptive: minimize disruption to high-impact nodes. Rules: alert on critical dependencies. |
| Graph WCC / community | WCC: `(node, component_id_node)` membership (access `.id` to get its identifying value; cast to `int` only for integer-identified nodes); community: `node.community_label` (int) | Prescriptive: optimize within-cluster vs cross-cluster. Rules: flag isolated components. |
| Predictive forecasting | `Forecast.predicted_value` | Prescriptive: optimize against predicted demand/delays. |
| Predictive classification | `Entity.risk_probability` | Rules: flag above threshold. Prescriptive: incorporate risk as constraint. |

### How to suggest cumulative questions

When generating suggestions:
1. First, identify questions answerable with the current ontology (standard discovery)
2. Then, for graph/predictive suggestions, ask: "What additional questions does this output enable?"
3. Present second-order questions with a clear dependency: "After running [Stage 1], this becomes answerable"

Second-order questions are expansion opportunities, not alternatives. The analyst sees: "Here's what you can do now. Here's what opens up if you also run graph analysis."

### The cumulative narrative

The ontology grows through use:
- **Start:** what exists (base model from data)
- **After graph:** + what's connected, what's central, what's clustered
- **After predictive:** + what will happen, what's at risk
- **After prescriptive:** + what should we do, what's optimal
- **After rules:** + what's valid, what's compliant, what's flagged

Each layer makes the next more powerful. Question discovery should convey this progression — show users what opens up after each stage.

---

## Feasibility Framework

Shared across all reasoners. Classify each suggestion's data readiness:

- **READY**: All required data is in the model. Can proceed directly to the reasoner workflow.
- **MODEL_GAP**: Data exists in the schema (tables/columns) but isn't mapped to the model. Auto-fixable via `enrich_ontology`. Each gap should reference a specific `source_table` and `source_column` — without these, the enrichment tool cannot generate the correct `define()` rule.
- **DATA_GAP**: Required data doesn't exist in any table. Blocks the question. Include only if the domain has very limited potential -- flag what data would be needed.

**Order suggestions by feasibility:** READY first, then MODEL_GAP. Prefer suggestions that can proceed without manual data collection.

### Classification decision tree

1. All needed data is already in the model ("Already in model" in schema info)? → **READY**
2. Needed data exists in schema as unmapped column ("Available for enrichment")? → **MODEL_GAP** (include `model_gap_fixes` with `source_table`/`source_column`)
3. Business parameter the user provides (budget, threshold, target %)? → **parameter_gap** (informational, doesn't change feasibility)
4. Data not in any table? → **DATA_GAP**

If the schema shows NO unmapped columns, there are no model_gaps — all suggestions should be READY. Decision variables, cross-product concepts, and computed expressions are created during formulation — they are NOT model_gaps.

### Gap identification rules

Model gaps are ONLY for data in the schema but not in the model. Decision variables, cross-products, and computed expressions are NOT model gaps (formulation layer). Check "Available for enrichment" columns in schema info. Each gap must specify `source_table` and `source_column`.

For full gap classification rules (property vs relationship gaps, boundary between base model and reasoner workflow), see `rai-ontology-design` § Model Gap Identification.

---

## Question Selection

Selecting the right question is "Phase 0" -- before any reasoner workflow begins. A poor choice wastes all downstream effort.

### The feasibility-value intersection

Focus on questions at the intersection of **available data** (feasible) and **useful answers** (valuable). Work forwards from what data exists and backwards from what decisions/insights matter.

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

### Question selection scoring

For each candidate, score on a 1-5 scale:

| Criterion | What to assess |
|-----------|---------------|
| Data availability | How much required data exists today? |
| Data quality | How reliable is the data? |
| Decision/insight frequency | How often is this needed? |
| Impact | What is the cost of not having this answer? |
| Implementation path | Can the answer be acted upon? |

Prioritize questions scoring high on BOTH data AND value dimensions.

### Common anti-patterns

- **"Perfect Data" Trap:** Waiting for ideal data before starting. Start with available data; use sensitivity analysis to identify critical gaps.
- **"Boil the Ocean" Trap:** Trying to answer everything at once. Start with one question, one scope, one time period.
- **"Solution Looking for a Question" Trap:** Forcing a reasoner where simpler approaches work. Ask: "What is wrong with a simple rule or heuristic here?"
- **"Data Rich, Insight Poor" Trap:** Lots of data but unclear what to answer. Start with the decision/question, work backwards to required data.

### Pre-workflow checklist

Before starting any reasoner workflow, confirm:

- [ ] Can I access the required data today?
- [ ] Is the data complete enough to generate meaningful results?
- [ ] Who specifically will use this output?
- [ ] What will they do differently because of it?
- [ ] Is this the smallest useful version of the question?
- [ ] Can the results be validated against known cases?

---

## Variety Heuristics

When suggesting questions, explore different aspects of the domain where the data supports it:
- Different reasoner types (don't suggest only optimization if graph/predictive questions are viable)
- Different decision structures (assignment vs selection vs sizing vs sequencing)
- Different objectives/questions (cost vs coverage vs structure vs prediction)
- Different constraint emphases (capacity-driven vs demand-driven vs coverage-driven)

**Cross-domain coverage:** If the model's concepts span multiple distinct business domains, spread suggestions across them rather than clustering in one area. Identify domains semantically from concept names and relationships (e.g., concepts prefixed with "Jira" vs "GitHub" vs "RAI" suggest different domains). Aim for at least one suggestion per domain before doubling up on any.

If the domain is narrow (e.g., only budget allocation data), it's fine to suggest variations on the same theme with different objectives or constraints -- as long as each is grounded in the actual ontology and represents a meaningfully different business question.

Vary the business question itself, not just constraints -- use different objectives that reference different properties from the model.

---

## Enrichment Handoff

When the user selects a question with **MODEL_GAP** feasibility:

1. The next step is `enrich_ontology`, not the reasoner workflow
2. Show the specific gaps and their source tables/columns from `model_gap_fixes`
3. After enrichment, re-assess feasibility -- it should now be READY
4. Then proceed to the reasoner workflow via Post-Discovery Routing

For graph questions, enrichment may also include constructing derived relationships needed for graph edges (e.g., a `ships_to` relationship derived from Shipment data, or operation-based site connectivity).

---

## Post-Discovery Routing

After the user selects a question, route to the appropriate reasoner workflow based on the `reasoners` tag.

### Presenting suggestions vs. routing metadata

Discovery output serves two audiences: the **user** (who evaluates which questions to pursue) and the **downstream reasoner workflow** (which needs structured routing metadata). Keep these separate:

- **User-facing**: Present suggestions in natural language — statement, feasibility, what it means for the business, what's needed next. No JSON, no implementation hints, no internal field names.
- **Internal routing**: The suggestion schema below is for machine-to-machine handoff when the user selects a question and you invoke a reasoner workflow. Do not surface it in conversation unless the user asks for technical detail.

### Suggestion output schema

Each suggestion includes a `reasoners` field — an ordered list specifying the execution sequence. Single-reasoner questions have one entry; chained questions list stages in order.

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
| **prescriptive** | `decision_scope`, `forcing_requirement`, `objective_property`, `decision_variable`, `scenario_parameter`, `competing_objectives` |
| **graph** | `algorithm`, `graph_construction` (`node_concept`, `directed`, `weighted`, `edge_definition`), `target_filter`, `output_binding` |
| **rules** | `rule_type`, `source_concept`, `condition_properties`, `join_path`, `threshold`, `output_type`, `output_property`, `downstream_use` |
| **predictive** | `type`, `mode` (`pre_computed` or `rai_predictive`), `target_concept`, `target_property`, `feature_properties`, `output_concept`, `pre_computed_table` |

**For chained questions**, use a `stages` array in `implementation_hint`:

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

**After discovery, load these skills before writing code:**

1. **Formulation skill** for the chosen reasoner type (e.g., `rai-prescriptive-problem-formulation`, `rai-graph-analysis`)
2. **`rai-querying`** + **`rai-pyrel-coding`** for v1 syntax, imports, and query patterns

Discovery covers *what* to ask. Coding skills cover *how* to write it. Skipping step 2 leads to hallucinated APIs and wrong imports.

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| Suggesting questions with no data backing | Skipping feasibility check before proposing | Use READY/MODEL_GAP/DATA_GAP classification; verify data exists before suggesting |
| All suggestions are the same reasoner type | Only considering optimization use cases | Check ontology for graph structure, temporal features, rule patterns -- not just optimization |
| Chained question with unclear handoff | Missing interface specification between stages | Each stage must define inputs and outputs explicitly |
| Missing forcing requirement (prescriptive) | Overlooking mandatory constraint in prescriptive questions | See `prescriptive.md` for forcing constraint and implementation hint guidance |
| All suggestions cluster in one domain | Not surveying the full concept space | Spread across distinct business domains present in concept names |
| Confusing model gaps with reasoner-layer constructs | Treating computed outputs as missing data | Decision variables, predictions, graph metrics have no source table -- they're not model gaps |
| Suggesting DATA_GAP questions as top choices | Prioritizing novelty over feasibility | Order by feasibility: READY first, MODEL_GAP second, DATA_GAP only if domain is very narrow |

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
| Rules routing | Discovery scenario walkthrough for classification, validation, and derivation rules | [rules_routing.md](examples/rules_routing.md) |
| Predictive routing | Discovery scenario walkthrough for predictive modeling | [predictive_routing.md](examples/predictive_routing.md) |
| Chained routing | Discovery scenario walkthrough for multi-reasoner pipelines | [chained_routing.md](examples/chained_routing.md) |
