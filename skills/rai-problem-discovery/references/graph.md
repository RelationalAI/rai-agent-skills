<!-- TOC -->
- [Graph Question Types](#graph-question-types)
- [Graph Implementation Hints](#graph-implementation-hints)
- [When Graph vs Other Reasoners](#when-graph-vs-other-reasoners)
- [Graph Construction Patterns](#graph-construction-patterns)
- [Multi-Graph Awareness](#multi-graph-awareness)
- [Output Concepts](#output-concepts)
- [Data Sufficiency Signals](#data-sufficiency-signals)
- [Graph-Specific Feasibility Criteria](#graph-specific-feasibility-criteria)
- [Execution Skill Handoff](#execution-skill-handoff)
<!-- /TOC -->

## Graph Question Types

The RAI Graph reasoner (`relationalai.semantics.reasoners.graph.Graph`) analyzes structure, connectivity, and influence within relationship networks in the ontology.

| Type | Question Pattern | Ontology Signal | RAI Algorithms |
|------|-----------------|-----------------|----------------|
| **Centrality** | "Who/what is most influential/connected/critical?" | Hub concepts with many relationships, weighted edges | `eigenvector_centrality()`, `betweenness_centrality()`, `degree_centrality()`, `pagerank()` |
| **Community Detection** | "What natural groups/clusters exist?" | Dense relationship networks, many-to-many relationships | `louvain()`, `infomap()`, `label_propagation()`, `triangle_community()` |
| **Connected Components** | "Which components are isolated? How fragmented is the network?" | Network with potential disconnected regions | `weakly_connected_component()`, `is_connected()` |
| **Reachability (upstream)** | "What depends on X?" "Who supplies Y?" | Directed relationships, dependency topology | `reachable(to=target)` on directed graph |
| **Reachability (downstream)** | "If X goes offline, what's affected?" | Same directed topology, impact framing | `reachable(from_=target)` on directed graph |
| **Distance / Pathfinding** | "How far apart are X and Y?" "Shortest path?" | Source→destination relationships, weighted edges | `distance()`, `diameter_range()` |
| **Similarity / Link Prediction** | "Which entities are most alike?" "Who should be connected?" | Concepts with overlapping neighborhoods | `jaccard_similarity()`, `cosine_similarity()`, `adamic_adar()`, `preferential_attachment()` |
| **Bridge Detection** | "Which nodes are critical connectors? Single points of failure?" | Network where node removal could disconnect components | WCC + derived Bridge concept (cross-boundary analysis) |
| **Clustering Coefficient** | "How tightly connected are local neighborhoods?" | Dense local clusters | `local_clustering_coefficient()`, `average_clustering_coefficient()`, `triangle_count()` |

**Disambiguation rules:**
- "Most critical/important" + network context → centrality (eigenvector, betweenness, or PageRank depending on graph type)
- "If X goes offline" → reachability (downstream from X on directed graph), then possibly → prescriptive for re-optimization
- "Natural groups" → community detection (louvain for undirected, infomap for directed/weighted); "isolated clusters" → WCC
- "Shortest path" with no optimization constraints → graph `distance()`; "cheapest route visiting ALL nodes" → prescriptive (TSP)
- "Similar to" or "most alike" → similarity methods (jaccard, cosine); not predictive clustering
- "Critical connector" or "single point of failure" → bridge detection via WCC, not just centrality

---

## Graph Implementation Hints

For each graph suggestion, provide an implementation hint with these fields:

### algorithm
Which RAI Graph method to use. Maps directly to `Graph` instance methods:
- Centrality: `eigenvector_centrality`, `betweenness_centrality`, `degree_centrality`, `pagerank`
- Community: `louvain` (undirected only), `infomap` (directed + weighted), `label_propagation`
- Components: `weakly_connected_component`, `is_connected`
- Reachability: `reachable` (with `from_=` or `to=` parameter)
- Distance: `distance` (supports weighted graphs, non-negative weights)
- Similarity: `jaccard_similarity`, `cosine_similarity`, `adamic_adar`

### graph_construction
How to build the `Graph` instance:
- **node_concept**: Which concept forms graph nodes (e.g., `Business`, `Site`)
- **directed**: `True` for dependency/flow analysis, `False` for network structure analysis
- **weighted**: `True` if edge weights are available and relevant
- **edge_definition**: How edges are constructed — from a direct relationship or via an intermediary concept

### target_filter (for reachability)
Which subset of nodes to reach to/from. Defined as a `model.Relationship` with a `.where()` filter.

### output_binding
How results are bound via `Graph.Node.ref()`:
- Centrality: `(node, score)` — ternary relation
- WCC: `(node, component_id)` — component_id is min node ID in component
- Reachability: `(source, target)` — binary relation of reachable pairs
- Community: `(node, community_label)` — binary relation
- Distance: `(start, end, length)` — ternary relation
- Similarity: `(node1, node2, score)` — ternary relation

---

## When Graph vs Other Reasoners

- Graph structure exists AND question is about understanding that structure → **graph**
- Graph structure exists AND question is about optimizing decisions over it → **prescriptive** (or graph → prescriptive chain)
- No explicit graph structure (only tabular entity-property data) → probably **not graph**
- "Find shortest path" with no constraints → graph `distance()`; "Find cheapest route visiting all nodes" → prescriptive (TSP/routing)
- "Most important node" + network context → graph (centrality); "allocate more to important nodes" → graph → prescriptive chain
- FK chains forming implicit paths (A → B → C) → graph may be viable — construct edges from FK traversals

**Common chains involving graph:**
- Graph → Prescriptive: compute centrality/reachability, then optimize decisions weighted by those metrics
- Graph → Predictive: extract graph features (centrality, community membership), then use as predictive model inputs
- Graph → Rules: identify structural properties (bridges, isolated components), then apply rules for alerting

---

## Graph Construction Patterns

A single ontology can yield multiple `Graph` instances. The question determines which construction is appropriate.

### Entity-level directed graph
Nodes are business entities, edges are direct relationships. Suited for reachability, dependency tracing, PageRank.
```python
graph = Graph(model, directed=True, weighted=False, node_concept=Business)
define(graph.Edge.new(src=Business.ref(), dst=Business.ships_to(Business.ref())))
```

### Infrastructure-level undirected weighted graph
Nodes are physical locations, edges derived from operational relationships. Suited for centrality, WCC, community detection, bridge analysis.
```python
graph = Graph(model, directed=False, weighted=True, node_concept=Site)
define(
    graph.Edge.new(src=site1, dst=site2, weight=site1.shipment_count)
).where(Operation.source_site(op, site1), Operation.destination_site(op, site2))
```

### Key insight
The same ontology may need both constructions. "Which suppliers do customers depend on?" uses a **directed entity graph**. "Which warehouses are critical connectors?" uses an **undirected infrastructure graph**. Discovery should identify which perspective fits each question.

---

## Multi-Graph Awareness

A single ontology can yield multiple `Graph` instances, each answering different questions. Discovery should surface ALL viable graph perspectives, not just the first match.

**Example:** A supply chain model with `Business`, `Site`, and `Operation` concepts supports:
1. **Directed business graph** (`Business` → `Business` via `ships_to`) — for PageRank, reachability, dependency tracing
2. **Undirected infrastructure graph** (`Site` ↔ `Site` via `Operation`) — for centrality, WCC, bridge detection, community
3. **Customer co-purchase graph** (if customer/order data exists) — for community detection

Each graph answers fundamentally different questions. When suggesting graph problems, check all potential graph constructions and suggest from each where appropriate.

---

### How to identify graph potential from ontology
- Concepts that act as edges (Operation, Route, Connection) with source/destination properties → infrastructure-level graph
- Direct entity-to-entity relationships (ships_to, manages, follows) → entity-level graph
- Hierarchy (parent→child, category→subcategory) → tree/DAG for reachability
- Same-type instance references (BOM: component → assembly) → recursive graph
- Many-to-many bridge tables → dense graph for community detection

---

## Output Concepts

Graph reasoning adds properties to the ontology that downstream reasoners can consume:

| Algorithm | Output | Downstream Use |
|-----------|--------|----------------|
| Centrality | `node.centrality_score` (float) | Prescriptive: weight allocation by importance. Predictive: use as feature. |
| WCC | `node.component_id` (int) | Prescriptive: optimize within-cluster vs cross-cluster. Rules: flag isolated components. |
| Reachability | `(source, target)` pairs | Prescriptive: constrain to reachable alternatives. Rules: alert on high-impact dependencies. |
| Community | `node.community_label` | Prescriptive: per-community optimization. Predictive: community as feature. |
| Distance | `(start, end, length)` | Prescriptive: use as cost parameter. Predictive: use as feature. |
| Similarity | `(node1, node2, score)` | Predictive: similar entities as collaborative filtering. Rules: flag anomalous dissimilarity. |
| Bridge | `is_bridge` flag (derived) | Prescriptive: add redundancy for critical connectors. Rules: flag single points of failure. |

These outputs are available for cumulative discovery — problems that weren't feasible before graph analysis may become feasible after.

---

## Data Sufficiency Signals

What ontology patterns indicate graph reasoning potential:

- **Explicit relationship concepts**: Route, Operation, Link concepts with source/destination properties → high confidence
- **Direct entity relationships**: `ships_to`, `manages`, `follows` → entity-level graph
- **FK chains forming paths**: Entity A → Entity B → Entity C → multi-hop traversal viable
- **Edge weights available**: Cost, distance, capacity, count properties → enables weighted centrality and pathfinding
- **Multiple connected components likely**: Regional boundaries, heterogeneous entity types → WCC/community detection
- **Directed flow present**: Supply chain, approval chain, reporting structure → reachability analysis
- **Many-to-many relationships**: Membership, collaboration, co-occurrence → dense graph for community detection

**Minimum viable ontology for graph:** At least one concept pair connected by a relationship forming a non-trivial network (more than a simple lookup/dimension table). For centrality/community: 10+ nodes with varied connectivity. For reachability: directed edges with multi-hop paths.

---

## Graph-Specific Feasibility Criteria

Beyond the standard READY / MODEL_GAP / DATA_GAP classification, graph suggestions require additional feasibility checks:

| Criterion | Check | Impact |
|-----------|-------|--------|
| **Minimum network density** | Are there enough nodes with varied connectivity? | Centrality on 3 nodes or a complete graph is trivial — all nodes score equally |
| **Algorithm/direction compatibility** | Does the suggested algorithm work with the graph's directionality? | `louvain()` requires undirected; `reachable()` requires directed. Flag if mismatch. |
| **Weight availability** | Does the model have numeric edge properties for weighted algorithms? | Weighted centrality/distance needs edge weights — if unavailable, suggest unweighted alternative or flag as MODEL_GAP |
| **Edge construction feasibility** | Can edges actually be constructed from the ontology relationships? | Intermediary concepts need source/destination properties; co-occurrence needs shared attribute |
| **Multi-hop path existence** | For reachability/distance: do directed paths span multiple hops? | Single-hop relationships give trivial reachability — need multi-hop chains |
| **Data volume** | Are there enough entities to produce meaningful graph structure? | < 5 nodes: trivial results. 10-100: good for all algorithms. 100K+: betweenness/similarity may be slow |

When assessing feasibility, include these in the analysis and downgrade to MODEL_GAP or DATA_GAP as appropriate.

---

## Execution Skill Handoff

After selecting a graph suggestion from discovery, the execution workflow uses the `rai-graph-analysis` skill for graph construction, algorithm selection, parameter configuration, and result extraction.

**Discovery** (`rai-problem-discovery` + this reference file) answers: "What graph questions can this data answer?"
**Execution** (`rai-graph-analysis`) answers: "How do I build the graph, run the algorithm, and extract results?"

The implementation hint from discovery provides the starting point for execution:
- `algorithm` → maps to `rai-graph-analysis` Algorithm Selection guidance
- `graph_construction` → maps to `rai-graph-analysis` Graph Construction from Ontology patterns
- `output_binding` → maps to `rai-graph-analysis` Result Extraction and Binding patterns
