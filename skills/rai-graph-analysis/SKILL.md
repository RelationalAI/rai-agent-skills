---
name: rai-graph-analysis
description: Graph algorithm selection and execution on PyRel v1 models. Covers graph construction from ontology patterns, algorithm families (centrality, community, reachability, distance, similarity, components), parameter tuning, result extraction, and downstream use. Use when building or running graph analyses on RAI models.
---

# Graph Analysis
<!-- v1-SENSITIVE -->

<!-- TOC -->
- [Summary](#summary)
- [Quick Reference](#quick-reference)
- [Graph Analysis Workflow](#graph-analysis-workflow)
- [Graph Construction from Ontology](#graph-construction-from-ontology)
- [Algorithm Selection](#algorithm-selection)
- [Parameter Guidance](#parameter-guidance)
- [Result Extraction and Binding](#result-extraction-and-binding)
- [Downstream Use](#downstream-use)
- [Common Pitfalls](#common-pitfalls)
- [Examples](#examples)
- [Reference Files](#reference-files)
<!-- /TOC -->

## Summary

**What:** Graph algorithm selection and execution — building `Graph` instances from PyRel ontology patterns and running the right algorithm to answer structural questions about the data.

**When to use:**
- Building a `Graph` instance from an existing PyRel model (choosing node concept, edge construction, directed/weighted)
- Selecting which graph algorithm answers a given question (centrality, community, reachability, etc.)
- Configuring algorithm parameters (direction, weights, aggregator)
- Extracting and binding graph results to model properties
- Feeding graph outputs into downstream reasoning (optimization, rules, predictions)

**When NOT to use:**
- Discovering whether graph analysis is appropriate for a dataset — see `rai-discovery`
- PyRel syntax reference (imports, types, model patterns) — see `rai-pyrel-coding`
- Ontology design decisions (concept modeling, data mapping) — see `rai-ontology-design`
- Optimization formulation (variables, constraints, objectives) — see `rai-prescriptive-problem-formulation`
- Business rule authoring (validation, classification, alerting) — see `rai-rules-authoring`

**Overview (process steps):**
1. Identify network structure in the ontology (node concepts, edge relationships, directedness)
2. Choose a graph construction pattern (entity-level, infrastructure-level, hierarchy, bridge table)
3. Select the algorithm that answers the question (centrality, community, reachability, etc.)
4. Configure parameters (directed, weighted, aggregator, algorithm-specific)
5. Execute the graph algorithm
6. Extract results and bind to model properties for downstream use

---

## Quick Reference

```python
# Imports
from relationalai.semantics import Model, Float, Integer, String, where, define, data
from relationalai.semantics.reasoners.graph import Graph
from relationalai.semantics.std import aggregates, floats

model = Model("my_model")
```

**Note:** `where`, `define`, and `data` are available as standalone imports and as `model.where()`, `model.define()`, `model.data()` methods. Both are equivalent for single-model scripts. Use the `model.*` form when multiple Models exist — standalone functions fail with `"Multiple Models have been defined."`. See `rai-pyrel-coding` for data loading patterns with `model.data()`.

### Graph constructor

```python
# Standard construction — define edges manually with Edge.new()
graph = Graph(
    model,
    directed=True|False,          # Edge directionality
    weighted=True|False,          # Whether edges carry weights
    node_concept=MyConcept,       # Which concept forms nodes (optional — inferred from Edge defs)
    aggregator="sum",             # How parallel edge weights combine (required if weighted=True)
)
Node, Edge = graph.Node, graph.Edge

# Concept-based construction — edges derived automatically from an existing concept
graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=Account,
    edge_concept=Transaction,                      # Each Transaction instance becomes an edge
    edge_src_relationship=Transaction.payer,        # Source endpoint
    edge_dst_relationship=Transaction.payee,        # Destination endpoint
    edge_weight_relationship=Transaction.amount,    # Edge weight (required when weighted=True)
)
```

**Important:**
- `aggregator="sum"` is currently the **only supported aggregator**. It collapses multi-edges (multiple edges between the same node pair) by summing their weights. It also works on unweighted graphs to collapse multi-edges.
- When using `edge_concept`, you must also pass `node_concept`, `edge_src_relationship`, and `edge_dst_relationship`. Add `edge_weight_relationship` when the graph is weighted.
- **Weights must be floats.** Use `floats.float()` to cast from other numeric types: `weight=floats.float(Transaction.amount)`.

### Algorithm cheat sheet

| Family | Methods | Output Shape | Typical Use |
|--------|---------|-------------|-------------|
| **Basic Stats** | `num_nodes()`, `num_edges()`, `num_triangles()` | scalar | Graph validation, sanity checks |
| **Neighbors** | `neighbor()`, `inneighbor()`, `outneighbor()`, `common_neighbor()` | `(node, node)` or `(node, node, node)` | Neighborhood exploration |
| **Degree** | `degree()`, `indegree()`, `outdegree()`, `weighted_degree()`, `weighted_indegree()`, `weighted_outdegree()` | `(node, value)` | Connection counts |
| **Centrality** | `eigenvector_centrality()`, `betweenness_centrality()`, `degree_centrality()`, `pagerank()` | `(node, score)` | Importance, influence, bottlenecks |
| **Community** | `louvain()`, `infomap()`, `label_propagation()` | `(node, label)` | Natural groupings, clusters |
| **Components** | `weakly_connected_component()`, `is_connected()` | `(node, component_id)` or scalar | Fragmentation, isolation |
| **Reachability** | `reachable(from_=X)`, `reachable(to=X)` | `(source, target)` pairs | Dependency tracing, impact analysis |
| **Distance** | `distance()`, `diameter_range()` | `(start, end, length)` | Shortest paths, network diameter |
| **Similarity** | `jaccard_similarity()`, `cosine_similarity()`, `adamic_adar()`, `preferential_attachment()` | `(node1, node2, score)` | Entity comparison, link prediction |
| **Clustering** | `local_clustering_coefficient()`, `average_clustering_coefficient()`, `triangle_count()`, `triangle()`, `unique_triangle()` | `(node, value)` or `(n1, n2, n3)` | Local density, tightness |

**Key compatibility constraints:**
- `betweenness_centrality()` -- cannot use with `weighted=True`
- `louvain()` -- cannot use with `directed=True` (use `infomap()` for directed graphs)
- `reachable()` -- cannot use with `directed=False` (requires directed graph)
- `local_clustering_coefficient()` -- cannot use with `directed=True` (requires undirected)
- `triangle_count()` / `triangle()` -- cannot use with `directed=True` (requires undirected)

---

## Graph Analysis Workflow

### Step 0: Study the Existing Model

Before writing any graph or enrichment code, read the existing model file to understand:

1. **How to include base definitions** — graph scripts that extend an existing model must import it (e.g., `from my_model import model, Site, Operation`) so that all base `define()` rules are in scope. Creating a standalone `Model("same name")` reference without the base definitions will produce an empty graph because concept instances won't exist.
2. **Coding conventions** — check how the existing model references table columns (casing, naming patterns) and follow the same style. The model file is the source of truth for conventions, not external metadata tools.
3. **What's already wired** — identify which relationships and properties exist vs. what needs enrichment. Only enrich what's missing.

### Step 1: Identify Network Structure

Before building a graph, identify what forms the network in the ontology:

| Ontology Pattern | Graph Interpretation |
|-----------------|---------------------|
| Direct entity-to-entity relationship (`Business.ships_to(Business)`) | Entity-level graph — entities are nodes, relationships are edges |
| Intermediary concept with source/destination (`Operation` linking `Site` to `Site`) | Infrastructure graph — locations are nodes, operations form edges |
| Parent-child hierarchy (`Category` → `Subcategory`) | DAG — suitable for reachability and tree traversal |
| Many-to-many via bridge table (`Student` ↔ `Course` via `Enrollment`) | Dense graph — suitable for community detection |
| Self-referencing (`Component.assembly(Component)`) | Recursive graph — BOM/dependency structures |

**Key insight:** A single ontology can support multiple graph constructions. "Which suppliers are most critical?" uses a directed entity graph. "Which warehouses are central connectors?" uses an undirected infrastructure graph. The question determines which construction to use.

### Step 2: Choose Construction Pattern

See [graph-construction.md](references/graph-construction.md) for detailed patterns. The main decision axes:

1. **What are the nodes?** — The concept whose instances form graph vertices
2. **What are the edges?** — Direct relationship or derived from intermediary concept
3. **Directed or undirected?** — Directed for flow/dependency, undirected for structural analysis
4. **Weighted or unweighted?** — Weighted when edge properties (cost, volume, distance) matter

### Step 3: Select Algorithm

Match the question to the algorithm family:

| Question Type | Algorithm Family | Key Consideration |
|--------------|-----------------|-------------------|
| "Who/what is most important/influential?" | Centrality | Choose variant by importance type (see below) |
| "What natural groups exist?" | Community | Requires undirected for Louvain; infomap handles directed |
| "Is the network fragmented?" | Components | WCC for undirected; SCC future |
| "What depends on X? / What does X affect?" | Reachability | Requires directed graph |
| "How far apart are X and Y?" | Distance | Supports weighted (non-negative) |
| "Which entities are most similar?" | Similarity | Based on shared neighborhoods |
| "How tightly connected are local regions?" | Clustering | Triangle-based metrics |

**Centrality variant selection** (the most common decision):
- **Eigenvector** — global influence: a node is important if its neighbors are important. Best for: "which nodes are the most influential overall?"
- **Betweenness** — bottleneck identification: nodes that sit on many shortest paths. Best for: "which nodes are critical connectors / single points of failure?"
- **PageRank** — directed influence: importance flows along directed edges. Best for: "which nodes receive the most flow/attention?"
- **Degree** — local connectivity: count of direct connections. Best for: "which nodes have the most direct relationships?"

See [algorithm-selection.md](references/algorithm-selection.md) for full per-algorithm guidance.

### Step 4: Configure, Execute, and Bind Results

```python
# Configure — see Parameter Guidance for directed/weighted/aggregator decisions
graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")
# ... define edges ...

# Execute — assign algorithm output to graph.Node
graph.Node.centrality_score = graph.eigenvector_centrality()

# Bind — make results available on the original concept
Site.centrality_score = model.Property(f"{Site} has {Float:centrality_score}")
model.where(graph.Node == Site).define(Site.centrality_score(graph.Node.centrality_score))

# Query — extract as DataFrame
df = model.select(Site.id, Site.centrality_score).to_df()
```

See [Parameter Guidance](#parameter-guidance) for configuration details, [Result Extraction and Binding](#result-extraction-and-binding) for query patterns, and [result-extraction.md](references/result-extraction.md) for per-algorithm extraction.

---

## Graph Construction from Ontology

The question determines which construction to use — the same ontology can yield multiple valid graphs.

| Pattern | Nodes | Edges | Typical Use |
|---------|-------|-------|-------------|
| Entity-level directed | Business entities | Direct relationships (`ships_to`) | PageRank, reachability |
| Infrastructure undirected weighted | Locations/sites | Intermediary concepts (`Operation`) | Centrality, WCC, bridges |
| Co-occurrence / shared-attribute | Entities | Shared membership/purchases | Community detection |
| Hierarchy / DAG | Hierarchical entities | Parent-child | Reachability, tree traversal |
| Self-referencing | Single concept | Instance-to-instance refs | BOM, dependency graphs |
| `edge_concept` | Any | Existing interaction concept | When edges are already modeled |

### Two main edge definition approaches

**Manual edges with `Edge.new()`** — most common:

```python
# Entity-level: direct relationship between concepts
graph = Graph(model, directed=True, weighted=False, node_concept=Business)
b1, b2 = Business.ref(), Business.ref()
model.where(b1.ships_to(b2)).define(graph.Edge.new(src=b1, dst=b2))

# Infrastructure-level: edges from intermediary concept
graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")
op = Operation.ref()
model.where(
    op.source_site(site1 := Site.ref()),
    op.output_site(site2 := Site.ref()),
).define(graph.Edge.new(src=site1, dst=site2, weight=op.shipment_count))

# Co-occurrence: shared attribute (id < guard prevents duplicates)
graph = Graph(model, directed=False, weighted=True, node_concept=Customer, aggregator="sum")
left_order, right_order = Order.ref(), Order.ref()
model.where(
    left_order.product == right_order.product,
    left_order.customer.id < right_order.customer.id,
).define(graph.Edge.new(src=left_order.customer, dst=right_order.customer, weight=1.0))
```

**Concept-based edges with `edge_concept`** — when each interaction is already a concept:

```python
graph = Graph(
    model, directed=True, weighted=True, node_concept=Account,
    edge_concept=Transaction,
    edge_src_relationship=Transaction.payer,
    edge_dst_relationship=Transaction.payee,
    edge_weight_relationship=Transaction.amount,
)
# Every Transaction instance automatically becomes an edge — no Edge.new() needed
```

Requirements: must pass `node_concept` with `edge_concept`. All three of `edge_concept`, `edge_src_relationship`, `edge_dst_relationship` are required together. Add `edge_weight_relationship` when weighted.

**Filtered edges** — use `.where()` to restrict which relationships become edges:

```python
t = Transaction.ref()
model.where(t.amount >= 100.0).define(graph.Edge.new(src=t.payer, dst=t.payee))
```

For detailed patterns (multi-intermediary, hierarchy, self-referencing, multi-graph, weight construction, validation), see [graph-construction.md](references/graph-construction.md).

---

## Algorithm Selection

Start from the question, not the algorithm name:

| Question Type | Algorithm Family | Default Choice |
|--------------|-----------------|----------------|
| "Who/what is most important?" | Centrality | `eigenvector_centrality()` (global influence) |
| "Which nodes are bottlenecks?" | Centrality | `betweenness_centrality()` (bridge nodes) |
| "Which nodes receive the most flow?" | Centrality | `pagerank()` (directed networks) |
| "What natural groups exist?" | Community | `louvain()` (undirected) or `infomap()` (directed) |
| "Is the network fragmented?" | Components | `weakly_connected_component()` |
| "What depends on X?" | Reachability | `reachable(from_=X)` / `reachable(to=X)` — **requires directed** |
| "How far apart are X and Y?" | Distance | `distance()` — supports weighted (non-negative) |
| "Which entities are most similar?" | Similarity | `jaccard_similarity()` — **warning: O(n^2) output** |
| "How tightly connected locally?" | Clustering | `local_clustering_coefficient()` — **requires undirected** |

**Key constraints:**
- `louvain()` requires `directed=False`
- `reachable()` requires `directed=True`
- `local_clustering_coefficient()` and `triangle_count()` require `directed=False`
- `pagerank()` works on undirected but is most meaningful on directed

**Pre-flight compatibility check:** Before proceeding to Step 4, verify your chosen algorithm is compatible with your graph's directed/weighted settings.

| Algorithm | Cannot use with |
|-----------|----------------|
| `betweenness_centrality()` | `weighted=True` |
| `louvain()` | `directed=True` (use `infomap()` for directed) |
| `reachable()` | `directed=False` (requires directed graph) |
| `local_clustering_coefficient()` | `directed=True` (requires undirected) |
| `triangle_count()` / `triangle()` | `directed=True` (requires undirected) |

For per-algorithm deep dives (parameters, output shapes, interpretation, compatibility matrix), see [algorithm-selection.md](references/algorithm-selection.md).

---

## Parameter Guidance

| Parameter | Values | When to use |
|-----------|--------|-------------|
| `directed` | `True` | Flow/dependency networks (supply chain, org hierarchy, reachability) |
| | `False` | Co-occurrence, infrastructure connectivity, similarity |
| `weighted` | `True` | Edge property (cost, volume, distance) matters for analysis. **Weights must be floats** — use `floats.float()` to cast. |
| | `False` | Only connection existence matters |
| `aggregator` | `"sum"` | **Only supported value.** Collapses multi-edges by summing weights. Also works on unweighted graphs to collapse duplicates. |
| `node_concept` | Concept | Which concept forms nodes. Required with `edge_concept`. Optional otherwise (inferred from edges). |

**Algorithm-specific:** `reachable(from_=X)` / `reachable(to=X)` for directional reachability. `pagerank(damping=0.85)` — default 0.85 is standard.

---

## Result Extraction and Binding

### Core pattern: assign → bind → query

```python
# 1. Run algorithm — result lives on graph.Node
graph.Node.centrality_score = graph.eigenvector_centrality()

# 2. Bind to original concept (makes it available for rules, optimization, queries)
Site.centrality_score = model.Property(f"{Site} has {Float:centrality_score}")
model.where(graph.Node == Site).define(Site.centrality_score(graph.Node.centrality_score))

# 3. Query as DataFrame
df = model.select(Site.id, Site.centrality_score).to_df().sort_values("centrality_score", ascending=False)
```

### Community labels → concept entities

```python
graph.Node.community_label = graph.louvain()
Segment = model.Concept("Segment", identify_by={"id": Integer})
model.define(Segment.new(id=graph.Node.community_label))
Customer.segment = model.Relationship(f"{Customer} belongs to {Segment}")
model.where(graph.Node == Customer).define(
    Customer.segment(Segment.filter_by(id=graph.Node.community_label))
)
```

### Type handling

**Critical:** Community/component IDs return as `Int128Array`. Cast before pandas: `df["community"].astype(int)`

### Validation

```python
graph.num_nodes().inspect()  # 0 = edge definitions don't match data
graph.num_edges().inspect()  # 0 = relationship/join path is wrong
```

For per-algorithm query patterns (binary, ternary, reachability, similarity filtering, aggregation), see [result-extraction.md](references/result-extraction.md).

---

## Downstream Use

Graph outputs become model properties that other reasoning consumes:

- **Optimization:** Centrality scores as objective weights, community labels for per-group constraints
- **Rules:** Threshold-based alerting on graph metrics (e.g., `centrality < 0.1` → at-risk flag)
- **Predictions:** Community membership and centrality as predictive features
- **Multi-graph:** Run multiple `Graph()` instances on the same model for complementary perspectives (e.g., directed flow graph + undirected connectivity graph)

```python
# Graph metric feeds optimization
p.maximize(aggregates.sum(x * Site.centrality_score))

# Graph metric feeds rule
Site.is_at_risk = model.Relationship(f"{Site} is at risk")
model.where(Site.centrality_score < 0.1).define(Site.is_at_risk())
```

---

## Common Pitfalls

| Mistake | Cause | Fix |
|---------|-------|-----|
| `louvain()` fails on directed graph | Louvain requires undirected | Set `directed=False` or use `infomap()` for directed |
| Empty graph (no edges) | Edge definition doesn't match data — wrong relationship or join path | Verify edge source/destination properties exist and have data; query edge count before running algorithms |
| `Int128Array` error in pandas | Community/component IDs are Int128 | Cast: `df["col"].astype(int)` |
| Duplicate/self-loop edges | Missing guard in co-occurrence pattern | Add `left.id < right.id` to `.where()` clause |
| `aggregator` missing | Weighted graph requires aggregator for parallel edges | Add `aggregator="sum"` to constructor (only supported value) |
| Weight type error | Weights must be floats, but property is Integer/Number | Cast with `floats.float(property)` in Edge.new weight parameter |
| Centrality all equal | Graph is a complete graph or all nodes have identical connectivity | Check if graph construction is correct; may need weighted edges to differentiate |
| Similarity produces too many results | O(n^2) output for n nodes | Filter by minimum threshold or limit to top-k per node |
| Reachability on undirected graph | Reachability is meaningful only with directed edges | Set `directed=True` for reachability/impact analysis |
| Wrong node concept | Using intermediary concept as nodes instead of entity concept | Intermediary concepts form edges, not nodes — e.g., `Operation` is an edge between `Site` nodes |
| Graph results not visible on original concept | Results bound to `graph.Node` but not to the source concept | Add explicit binding: `model.where(graph.Node == MyConcept).define(...)` |
| Empty graph when extending existing model | Script creates `Model("name")` without importing base model definitions — concepts exist but have no instances | Import the base model module (e.g., `from my_model import model, Site`) so base `define()` rules are in scope |

---

## Examples

### Basic patterns (inline data, Edge.new())

| Pattern | Description | File |
|---------|-------------|------|
| Centrality | Eigenvector centrality on supply chain — infrastructure-level undirected weighted graph | [centrality_supply_chain.py](examples/centrality_supply_chain.py) |
| Community | Louvain on customer co-purchase graph — shared-attribute edge construction with `id <` guard | [community_detection_customers.py](examples/community_detection_customers.py) |
| Reachability | Upstream/downstream impact analysis — directed entity-level graph with `reachable()` | [reachability_impact_analysis.py](examples/reachability_impact_analysis.py) |
| Bridge Detection | Betweenness centrality + WCC for bridge nodes — undirected infrastructure network | [bridge_detection.py](examples/bridge_detection.py) |

### Real-world patterns (edge_concept, computed weights)

| Pattern | Description | File |
|---------|-------------|------|
| Disease Outbreak | Directed weighted graph with `edge_concept` + computed risk weight; degree centrality + indegree/outdegree | [disease_outbreak_centrality.py](examples/disease_outbreak_centrality.py) |
| Humanitarian Aid | PageRank + degree centrality on directed weighted supply chain; strategic hub categorization | [humanitarian_aid_pagerank.py](examples/humanitarian_aid_pagerank.py) |
| Wildlife Conservation | Louvain community detection on undirected `edge_concept` graph; hub identification per community | [wildlife_conservation_communities.py](examples/wildlife_conservation_communities.py) |

---

## Reference Files

| Reference | Description | File |
|-----------|-------------|------|
| Graph construction | Detailed construction patterns from ontology — entity-level, infrastructure, hierarchy, bridge, self-referencing, filtered, multi-graph | [graph-construction.md](references/graph-construction.md) |
| Algorithm selection | Per-algorithm deep dive — when to use, parameters, output shape, complexity, decision guidance | [algorithm-selection.md](references/algorithm-selection.md) |
| Result extraction | Query patterns for each algorithm output shape, model binding, DataFrame extraction, type handling | [result-extraction.md](references/result-extraction.md) |
