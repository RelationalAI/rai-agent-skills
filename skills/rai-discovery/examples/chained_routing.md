# Chained Routing Examples

Discovery-to-routing walkthroughs for multi-reasoner chains. Each example shows how one reasoner's output enables the next, and how discovery should suggest the full chain of questions.

---

## Graph → Prescriptive: "Identify critical hubs, then optimize allocation weighted by importance"

### Discovery framing
Two questions that form a cumulative chain:

**Question A (graph, standalone):** "Which hubs are most critical to network resilience?"
- Feasibility: READY (network topology exists)
- Output: `Node.centrality_score` enriches the ontology

**Question B (prescriptive, depends on A):** "Allocate resources across hubs weighted by network importance"
- Feasibility: depends on graph output — only solvable after centrality scores exist
- Uses `Node.centrality_score` as a weight in the allocation objective or constraint

### How discovery presents this
```
1. [Graph] Identify which hubs are critical connectors (READY)
2. [Prescriptive] Allocate resources weighted by hub importance
   → available after running #1 (centrality scores feed allocation weights)
```

### Chain mechanics
- **Stage 1:** Run `eigenvector_centrality()` on NodeDependencyGraph → `Node.centrality_score` added to ontology
- **Enrichment bridge:** centrality scores are now queryable properties on Node
- **Stage 2:** Prescriptive formulation uses `Node.centrality_score` as allocation weight — higher centrality hubs get priority in allocation

---

## Predictive → Prescriptive: "Forecast entity risks, then optimize re-allocation given predicted reliability"

### Discovery framing
Two questions that form a sequential chain:

**Question A (predictive):** "Which entities will likely have the most at-risk activities next period?"
- Feasibility: READY (RiskPrediction table exists as pre-computed predictions)
- Output: `RiskPrediction.predicted_risk_prob` per entity per period

**Question B (prescriptive, uses A's output):** "Given predicted risks, how should we re-allocate to minimize cost while maintaining reliability?"
- Feasibility: READY (prediction data + activity costs + demand all in model)
- Uses `predicted_risk_prob` as the reliability parameter in constraints

### How discovery presents this
```
1. [Predictive] Identify which entities are predicted to be at risk next period (READY)
2. [Prescriptive] Optimize allocation to minimize cost given predicted reliability (READY)
   → uses predicted risk probabilities as reliability constraint
```

### Chain mechanics
- **Stage 1:** Query `RiskPrediction` concept for target period → entity risk ranking
- **Stage 2:** Prescriptive formulation references `RiskPrediction.predicted_risk_prob` as reliability parameter
  - Scenario 1: soft penalty — `reliability_weight * sum(flow * (1 - reliability_score))`
  - Scenario 2: hard threshold — exclude entities where `predicted_risk_prob > threshold`
  - Scenario 3: parameter sweep across threshold values → cost-vs-reliability tradeoff

---

## Graph → Graph → Prescriptive: "Map network structure, assess impact, then optimize contingency"

### Discovery framing
A three-stage chain where each question builds on the previous:

**Question A (graph):** "Which nodes are bridges between network clusters?"
- WCC + bridge detection → identifies single points of failure

**Question B (graph):** "If a critical entity goes offline, which downstream entities and resources are affected?"
- Downstream reachability from at-risk entity → quantifies impact

**Question C (prescriptive):** "Re-allocate components to minimize cost while covering all affected entities"
- Optimization problem scoped by the impact set identified by graph analysis

### How discovery presents this
```
1. [Graph] Identify bridge nodes and isolated clusters (READY)
2. [Graph] Assess downstream impact if a key entity goes offline (READY)
3. [Prescriptive] Optimize re-allocation for affected portion of the network (READY)
   → scope informed by #1 (critical nodes) and #2 (affected entities)
```

### Chain mechanics
- **Stage 1:** `weakly_connected_component()` identifies clusters; Bridge concept flags connectors
- **Stage 2:** `reachable(from_=target_entity)` maps the blast radius of an entity disruption
- **Stage 3:** Prescriptive formulation uses Stages 1+2 to: (a) force redundancy for bridge nodes, (b) constrain re-allocation to reachable alternatives only
