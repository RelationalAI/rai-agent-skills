# Graph Routing Examples

Discovery-to-routing walkthroughs for graph reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "Which entities are most critical to network resilience?"

### Ontology signals
- `Node` concept with `Activity` linking `source_node` → `target_node` → network topology
- `Activity.capacity_per_period` → weighted edges available
- Multiple node types (e.g., PRODUCER, HUB, CONSUMER) → heterogeneous network

### Reasoner classification: Graph (centrality)
- "Most critical" + network topology → centrality analysis
- NOT prescriptive — question is about understanding structure, not making decisions

### Implementation hint
```json
{"algorithm": "eigenvector_centrality", "graph_construction": {"node_concept": "Node",
  "directed": false, "weighted": true,
  "edge_definition": "Activity linking source_node to target_node, weight=activity_count"},
 "output_binding": "(node, centrality_score)"}
```

### Modeling needs (→ rai-ontology-design)
- Graph construction: undirected `NodeDependencyGraph` with Node as nodes, Activity as edges
- Derived properties: `count_is_source` / `count_is_target` for edge weights
- PyRel: `Graph(model, directed=False, weighted=True, node_concept=Node)`

### Reasoner handoff (→ graph workflow)
- `NodeDependencyGraph.eigenvector_centrality()` → returns `(node, centrality_score)`
- Filter non-relevant node types if needed
- Output: `Node.centrality_score` available for downstream prescriptive use (e.g., weight allocation by node importance)

---

## "Which upstream entities do high-priority targets depend upon?"

### Ontology signals
- `Entity` concept with `provides_to` relationship (Entity → Entity) → directed dependency chain
- `Entity.is_high_priority_target` derived property → target filter available
- Multi-tier dependency chain (e.g., Source → Intermediary → Hub → Target) → multi-hop reachability needed

### Reasoner classification: Graph (reachability, upstream)
- "Depend upon" + directed relationships → upstream reachability
- Multi-hop (not just direct providers) → graph traversal, not SQL join
- NOT predictive — question is about current structure, not future outcomes

### Implementation hint
```json
{"algorithm": "reachable", "graph_construction": {"node_concept": "Entity",
  "directed": true, "weighted": false,
  "edge_definition": "Entity.provides_to relationship"},
 "target_filter": "Entity.is_high_priority_target",
 "output_binding": "(provider, target) reachable pairs"}
```

### Modeling needs (→ rai-ontology-design)
- Graph construction: directed `EntityGraph` with Entity as nodes, `provides_to` as edges
- Derived relationship: `Entity.provides_to` from Allocation (source_entity → target_entity)
- Target concept: `is_high_priority_target` filter (e.g., role='CONSUMER' AND priority_tier='HIGH')
- PyRel: `Graph(model, directed=True, weighted=False, node_concept=Entity)`

### Reasoner handoff (→ graph workflow)
- Define target: `model.Relationship("Target Entity")` filtered to high-priority
- `EntityGraph.reachable(to=target_entity)` → returns `(source, target)` pairs
- Filter `source.role == "PROVIDER"` for upstream providers only
- Output: per-target provider dependency list with reliability scores

---

## "If a key provider goes offline, which downstream entities and resources are impacted?"

### Ontology signals
- Same directed `EntityGraph` as the upstream example (Entity → Entity via `provides_to`)
- Parameterized by entity name → impact analysis for a specific node
- `Resource` and `Allocation` concepts with quantity data → can quantify impact

### Reasoner classification: Graph (reachability, downstream)
- "Goes offline" + "what's affected" → downstream reachability from a specific node
- Same graph as the upstream example, but traversal direction is reversed (`from_=` instead of `to=`)
- Impact quantification (quantity at risk) requires joining graph results back to Allocation/Resource data

### Implementation hint
```json
{"algorithm": "reachable", "graph_construction": {"node_concept": "Entity",
  "directed": true, "weighted": false,
  "edge_definition": "Entity.provides_to relationship"},
 "target_filter": "Entity.name == '<key provider>' (parameterized)",
 "output_binding": "(source_provider, affected_target) reachable pairs"}
```

### Modeling needs (→ rai-ontology-design)
- Same `EntityGraph` as upstream reachability — no additional graph construction needed
- Join path to Resource: `target.receives_allocation.Resource` for resource impact
- Join path to quantities: `Allocation.quantity` for volume at risk

### Reasoner handoff (→ graph workflow)
- Define target: `model.Relationship("Target Provider")` filtered by name
- `EntityGraph.reachable(from_=target_provider)` → returns all downstream entities
- Join to downstream entities and Resource concepts for impact quantification
- Output: affected targets with resources at risk and quantity exposure

### Cumulative discovery note
This question pairs naturally with prescriptive: "Given the impact of the key provider going offline, how should we re-allocate to minimize cost?" (graph → prescriptive chain). The reachability output identifies which alternatives are available.
