# Chained Routing Examples

Discovery-to-routing walkthroughs for multi-reasoner chains. Each example shows how one reasoner's output enables the next, and how discovery should suggest the full chain of questions.

---

## Graph → Prescriptive: "Identify critical warehouses, then optimize allocation weighted by importance"

### Discovery framing
Two questions that form a cumulative chain:

**Question A (graph, standalone):** "Which warehouses are most critical to supply chain resilience?"
- Feasibility: READY (network topology exists)
- Output: `Site.centrality_score` enriches the ontology

**Question B (prescriptive, depends on A):** "Allocate inventory across warehouses weighted by network importance"
- Feasibility: depends on graph output — only solvable after centrality scores exist
- Uses `Site.centrality_score` as a weight in the allocation objective or constraint

### How discovery presents this
```
1. [Graph] Identify which warehouses are critical connectors (READY)
2. [Prescriptive] Allocate inventory weighted by warehouse importance
   → available after running #1 (centrality scores feed allocation weights)
```

### Chain mechanics
- **Stage 1:** Run `eigenvector_centrality()` on SiteDependencyGraph → `Site.centrality_score` added to ontology
- **Enrichment bridge:** centrality scores are now queryable properties on Site
- **Stage 2:** Prescriptive formulation uses `Site.centrality_score` as allocation weight — higher centrality warehouses get priority in allocation

---

## Predictive → Prescriptive: "Forecast supplier delays, then optimize re-sourcing given predicted reliability"

### Discovery framing
Two questions that form a sequential chain:

**Question A (predictive):** "Which suppliers will likely have the most delayed shipments next quarter?"
- Feasibility: READY (DelayPrediction table exists as pre-computed predictions)
- Output: `DelayPrediction.predicted_delay_prob` per supplier per quarter

**Question B (prescriptive, uses A's output):** "Given predicted delays, how should we re-source to minimize cost while maintaining reliability?"
- Feasibility: READY (prediction data + operation costs + demand all in model)
- Uses `predicted_delay_prob` as the reliability parameter in constraints

### How discovery presents this
```
1. [Predictive] Identify which suppliers are predicted to delay next quarter (READY)
2. [Prescriptive] Optimize sourcing to minimize cost given predicted reliability (READY)
   → uses predicted delay probabilities as reliability constraint
```

### Chain mechanics
- **Stage 1:** Query `DelayPrediction` concept for target quarter → supplier risk ranking
- **Stage 2:** Prescriptive formulation references `DelayPrediction.predicted_delay_prob` as reliability parameter
  - Scenario 1: soft penalty — `reliability_weight * sum(flow * (1 - reliability_score))`
  - Scenario 2: hard threshold — exclude suppliers where `predicted_delay_prob > threshold`
  - Scenario 3: parameter sweep across threshold values → cost-vs-reliability tradeoff

---

## Graph → Graph → Prescriptive: "Map network structure, assess impact, then optimize contingency"

### Discovery framing
A three-stage chain where each question builds on the previous:

**Question A (graph):** "Which warehouses are bridges between supply chain clusters?"
- WCC + bridge detection → identifies single points of failure

**Question B (graph):** "If a critical supplier goes offline, which customers and products are affected?"
- Downstream reachability from at-risk supplier → quantifies impact

**Question C (prescriptive):** "Re-source components to minimize cost while covering all affected customers"
- Optimization problem scoped by the impact set identified by graph analysis

### How discovery presents this
```
1. [Graph] Identify bridge warehouses and isolated clusters (READY)
2. [Graph] Assess downstream impact if key supplier goes offline (READY)
3. [Prescriptive] Optimize re-sourcing for affected supply chain (READY)
   → scope informed by #1 (critical nodes) and #2 (affected entities)
```

### Chain mechanics
- **Stage 1:** `weakly_connected_component()` identifies clusters; Bridge concept flags connectors
- **Stage 2:** `reachable(from_=target_supplier)` maps the blast radius of a supplier disruption
- **Stage 3:** Prescriptive formulation uses Stages 1+2 to: (a) force redundancy for bridge nodes, (b) constrain re-sourcing to reachable alternatives only
