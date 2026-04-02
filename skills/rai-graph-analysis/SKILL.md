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
1. Study the existing model — understand base definitions, coding conventions, and what's already wired
2. Start from the question — identify which concepts and relationships are relevant, and what kinds of analysis best speak to the question
3. Determine which relevant concepts should constitute nodes in the graph
4. Determine what edges would best capture the information relevant to the question and the planned analysis
5. Figure out how to derive those edges from the relevant relationships (sometimes a pass-through, often involving filters or more substantial logic)
6. Choose which Graph constructor pattern fits given the node/edge decisions
7. Select the specific algorithm(s) best suited to the question
8. Execute, extract results, and blend back into the model for downstream use

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

### Graph constructor — three patterns

**Pattern 1: No existing node or edge concepts** — the most common pattern. Use when nodes are drawn from multiple concepts, or when not all instances of a concept should be nodes. Edges are defined manually with `Edge.new()`.

```python
graph = Graph(
    model,
    directed=True|False,          # Edge directionality
    weighted=True|False,          # Whether edges carry weights
)
Node, Edge = graph.Node, graph.Edge
# Define nodes and edges manually with Edge.new(src=..., dst=...)
```

**Pattern 2: Existing node concept, manual edges** — use when a single concept covers all desired nodes and you want all instances as nodes (including isolated nodes with no edges). Isolated nodes can also be added explicitly via `model.define(Node(my_instance))`.

```python
graph = Graph(
    model,
    directed=True|False,
    weighted=True|False,
    node_concept=MyConcept,       # All instances of MyConcept become nodes; graph.Node is bound to MyConcept
)
Node, Edge = graph.Node, graph.Edge
# graph.Node IS MyConcept — properties assigned to graph.Node are directly available on MyConcept
# Define edges manually with Edge.new(src=..., dst=...)
```

**Pattern 3: Existing node concept + edge concept** — use when each interaction is already modeled as its own concept with source/destination relationships. Rather than deriving new nodes and edges, `graph.Node`, `graph.Edge`, `graph.EdgeSrc`, `graph.EdgeDst`, and `graph.EdgeWeight` bind directly to the provided concepts and relationships — avoiding extra computation, which matters for large graphs.

```python
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
- When using `edge_concept`, you must also pass `node_concept`, `edge_src_relationship`, and `edge_dst_relationship`. Add `edge_weight_relationship` when the graph is weighted.
- **Weights must be floats.** Use `floats.float()` to cast from other numeric types: `weight=floats.float(Transaction.amount)`.

### `Graph` constructor `aggregator` parameter guidance

`aggregator` is an optional parameter to the `Graph` constructor that defaults to `None`. When it is `None`, if the graph's edge definitions imply, or explicitly include, a multi-edge (multiple edges between the same pair of nodes), the graph logic will emit warnings.

`aggregator="sum"` is currently the only supported alternative. It collapses multi-edges by summing their weights. It also works on unweighted graphs to collapse multi-edges.

**When to use:** Only add `aggregator="sum"` when your graph construction is expected to produce multiple edges between the same node pair (e.g., co-occurrence patterns where multiple shared attributes each generate an edge, or intermediary concepts where multiple operations connect the same two sites).

**When NOT to use:** If your edge definitions are expected to produce at most one edge per node pair, omit the aggregator. Using it unnecessarily can mask data issues, semantic errors, or implementation mistakes — unexpected multi-edges often indicate, e.g., a bug in the edge derivation logic rather than valid data to be summed, or data with unexpected or incorrect elements.

### Algorithm cheat sheet

| Family | Methods | Output Shape | Typical Use |
|--------|---------|-------------|-------------|
| **Basic Stats** | `num_nodes()`, `num_edges()`, `num_triangles()` | scalar | Graph validation, sanity checks |
| **Neighbors** | `neighbor()`, `inneighbor()`, `outneighbor()`, `common_neighbor()` | `(node, node)` or `(node, node, node)` | Neighborhood exploration |
| **Degree** | `degree()`, `indegree()`, `outdegree()`, `weighted_degree()`, `weighted_indegree()`, `weighted_outdegree()` | `(node, value)` | Connection counts |
| **Centrality** | `eigenvector_centrality()`, `betweenness_centrality()`, `degree_centrality()`, `pagerank()` | `(node, score)` | Importance, influence, bottlenecks |
| **Community** | `louvain()`, `infomap()`, `label_propagation()` | `(node, label)` | Natural groupings, clusters |
| **Components** | `weakly_connected_component()`, `is_connected()` | `(node, component_id)` or scalar | Fragmentation, isolation |
| **Reachability** | `reachable(full=True)`, `reachable(from_=X)`, `reachable(to=X)` | `(source, target)` pairs | Dependency tracing, impact analysis |
| **Distance** | `distance()`, `diameter_range()` | `(start, end, length)` | Shortest paths, network diameter |
| **Similarity** | `jaccard_similarity()`, `cosine_similarity()`, `adamic_adar()`, `preferential_attachment()` | `(node1, node2, score)` | Entity comparison, link prediction |
| **Clustering** | `local_clustering_coefficient()`, `average_clustering_coefficient()`, `triangle_count()`, `triangle()`, `unique_triangle()` | `(node, value)` or `(n1, n2, n3)` | Local density, tightness |

**Key compatibility constraints:**
- `betweenness_centrality()` -- cannot use with `weighted=True`
- `louvain()` -- cannot use with `directed=True` (use `infomap()` for directed graphs)
- `local_clustering_coefficient()` -- cannot use with `directed=True` (requires undirected)

---

## Graph Analysis Workflow

### Step 1: Study the Existing Model

Before writing any graph or enrichment code, read the existing model file to understand:

1. **How to include base definitions** — graph scripts that extend an existing model must import it (e.g., `from my_model import model, Site, Operation`) so that all base `define()` rules are in scope. Creating a standalone `Model("same name")` reference without the base definitions will produce an empty graph because concept instances won't exist.
2. **Coding conventions** — check how the existing model references table columns (casing, naming patterns) and follow the same style. The model file is the source of truth for conventions, not external metadata tools.
3. **What's already wired** — identify which relationships and properties exist vs. what needs enrichment. Only enrich what's missing.

### Steps 2–5: From Question to Nodes and Edges

Start from the question, not the ontology. The question determines which concepts become nodes, what edges you need, and how to derive them.

**Step 2 — Scope the question:**
- State the question clearly — what property of the data's network structure are you trying to understand?
- Identify which concepts and relationships in the ontology are relevant to the question
- In broad strokes, what kinds of graph analysis over those concepts and relationships best speak to the question?

**Step 3 — Identify the nodes:**
- Which of the relevant concepts should constitute nodes — the actors or objects you want to rank, group, or trace?

**Step 4 — Determine the edges:**
- What edges would best capture the information relevant to the question and the planned analysis?
- Does direction matter? Direction often matters for flow, dependency, or causality. Undirected is often appropriate for co-membership or symmetric relationships. Consider whether directionality is semantically meaningful for your question.
- Note: The edges you need are informed both by the question and by the algorithm you plan to apply.

**Step 5 — Derive edges from relationships:**
- Sometimes an existing relationship maps directly to edges (the rules are essentially pass-through).
- Often, edges must be derived from one or more relationships less directly — involving filters, joins, or more substantial logic.
- Scan the ontology for the structural signals below to find how to build the edges you need.

**Key principle:** A single ontology can support multiple graph constructions. Different questions about the same data lead to different node/edge choices. The question always comes first — the ontology is the source of available structure, not the driver.

**Recognizing edge sources in the ontology:**

Once you know what nodes and edges you need, scan the ontology for these structural signals to find them:

| Ontology Signal | What to Look For | How It Becomes Edges |
|-----------------|-----------------|---------------------|
| **Direct relationship** | Concept A has a relationship to Concept B (or to itself) | The relationship itself is an edge — use `Edge.new(src=a, dst=b)` |
| **Intermediary concept** | A concept C with two relationships pointing to the same node type (e.g., `source` and `destination` both referencing Concept A) | Each instance of C becomes an edge between the two endpoints — use `Edge.new()` or `edge_concept` |
| **Shared attribute** | Two instances of Concept A both relate to the same instance of Concept B (e.g., two users sharing an address, two customers ordering the same product) | Co-occurrence — entities sharing an attribute are connected. Requires `id <` guard to prevent duplicates |
| **Parent-child** | A concept with a relationship to its own type named `parent`, `contains`, `reports_to`, or similar hierarchical terms | Directed edges from parent to child — use for reachability and tree traversal |
| **Self-referencing** | A concept with a relationship back to itself (e.g., `subcomponent`, `depends_on`, `follows`) | Instance-to-instance edges within one concept — may contain cycles |
| **Multi-concept co-occurrence** | Multiple distinct attributes shared between entities (e.g., shared address OR shared phone OR shared email) | Each shared attribute type creates edges — combine in a single graph for richer connectivity |

**Tip:** When the ontology has an interaction concept with source/destination relationships and edge-relevant properties (volume, weight, intensity), prefer `edge_concept` over manual `Edge.new()` — it's more concise and ensures every instance is included.

### Step 6: Choose Construction Pattern

Map the ontology signal you identified in Steps 2–5 to a construction pattern and decide how to implement it:

| Ontology Signal (from Steps 2–5) | Construction Pattern | Edge Method | Example |
|-------------------------------|---------------------|-------------|---------|
| Direct relationship | Entity-level | `Edge.new(src=a, dst=b)` | [Graph Construction from Ontology](#graph-construction-from-ontology) |
| Intermediary concept | Infrastructure-level | `Edge.new()` from intermediary, or `edge_concept` if concept has src/dst/weight | [centrality_supply_chain.py](examples/centrality_supply_chain.py), [edge_concept_pagerank.py](examples/edge_concept_pagerank.py) |
| Shared attribute | Co-occurrence | `Edge.new()` with `id <` guard | [community_derived_concept.py](examples/community_derived_concept.py) |
| Multi-concept co-occurrence | Multi-attribute co-occurrence | Multiple `Edge.new()` calls (one per shared attribute) | [graph_rules_integration.py](examples/graph_rules_integration.py) |
| Parent-child / Self-referencing | Hierarchy or recursive | `Edge.new(src=parent, dst=child)` | [graph-construction.md](references/graph-construction.md) |

Then decide the remaining axes:

1. **Directed or undirected?** — Directed for flow/dependency, undirected for structural analysis
2. **Weighted or unweighted?** — Weighted when edge properties (cost, volume, distance) matter for the question
3. **`Edge.new()` or `edge_concept`?** — Prefer `edge_concept` when the interaction is already modeled as a concept with src/dst relationships

See [graph-construction.md](references/graph-construction.md) for detailed patterns including filtered edges, multi-graph, and weight construction.

### Step 7: Select Algorithm

Match the question to the algorithm family:

| Question Type | Algorithm Family | Key Consideration |
|--------------|-----------------|-------------------|
| "Who/what is most important/influential?" | Centrality | Choose variant by importance type (see below) |
| "What natural groups exist?" | Community | Requires undirected for Louvain; infomap handles directed |
| "Is the network fragmented?" | Components | WCC for undirected; SCC future |
| "What are all transitive dependencies?" | Reachability | `reachable(full=True)` for all-pairs closure |
| "What depends on X? / What does X affect?" | Reachability | `reachable(from_=X)` / `reachable(to=X)` — most meaningful on directed |
| "How far apart are X and Y?" | Distance | Supports weighted (non-negative) |
| "Which entities are most similar?" | Similarity | Based on shared neighborhoods |
| "How tightly connected are local regions?" | Clustering | Triangle-based metrics |

**Centrality variant selection** (the most common decision):
- **Eigenvector** — global influence: a node is important if its neighbors are important. Best for: "which nodes are the most influential overall?"
- **Betweenness** — bottleneck identification: nodes that sit on many shortest paths. Best for: "which nodes are critical connectors / single points of failure?"
- **PageRank** — directed influence: importance flows along directed edges. Best for: "which nodes receive the most flow/attention?"
- **Degree** — local connectivity: count of direct connections. Best for: "which nodes have the most direct relationships?"

See [algorithm-selection.md](references/algorithm-selection.md) for full per-algorithm guidance.

### Step 8: Configure, Execute, and Bind Results

```python
# Configure — see Parameter Guidance for directed/weighted/aggregator decisions
# aggregator="sum" used here because multiple Operations can connect the same Site pair
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

### Two main edge definition approaches (Patterns 1–2 vs Pattern 3)

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
| "What are all transitive dependencies?" | Reachability | `reachable(full=True)` — all-pairs transitive closure |
| "What depends on X?" | Reachability | `reachable(from_=X)` / `reachable(to=X)` — **most meaningful on directed** |
| "How far apart are X and Y?" | Distance | `distance()` — supports weighted (non-negative) |
| "Which entities are most similar?" | Similarity | `jaccard_similarity()` — **warning: O(n^2) output** |
| "How tightly connected locally?" | Clustering | `local_clustering_coefficient()` — **requires undirected** |

**Key constraints:**
- `louvain()` requires `directed=False`
- `local_clustering_coefficient()` requires `directed=False`
- `pagerank()` works on undirected but is most meaningful on directed
- `reachable()` works on both directed and undirected, but is most meaningful on directed

**Pre-flight compatibility check:** Before proceeding to Step 8, verify your chosen algorithm is compatible with your graph's directed/weighted settings.

| Algorithm | Cannot use with |
|-----------|----------------|
| `betweenness_centrality()` | `weighted=True` |
| `louvain()` | `directed=True` (use `infomap()` for directed) |
| `local_clustering_coefficient()` | `directed=True` (requires undirected) |

For per-algorithm deep dives (parameters, output shapes, interpretation, compatibility matrix), see [algorithm-selection.md](references/algorithm-selection.md).

---

## Parameter Guidance

| Parameter | Values | When to use |
|-----------|--------|-------------|
| `directed` | `True` | Flow/dependency networks (supply chain, org hierarchy, reachability) |
| | `False` | Co-occurrence, infrastructure connectivity, similarity |
| `weighted` | `True` | Edge property (cost, volume, distance) matters for analysis. **Weights must be floats** — use `floats.float()` to cast. |
| | `False` | Only connection existence matters |
| `aggregator` | `"sum"` | **Only supported value.** Collapses multi-edges by summing weights. Only use when multi-edges are expected — see [Aggregator guidance](#aggregator-guidance). |
| `node_concept` | Concept | Which concept forms nodes. Required with `edge_concept`. Optional otherwise (inferred from edges). |

**Algorithm-specific:** `reachable(full=True)` for all-pairs reachability; `reachable(from_=X)` / `reachable(to=X)` for directional reachability. `pagerank(damping=0.85)` — default 0.85 is standard.

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

### Shorthand: assign to graph.Node with `node_concept`

When `node_concept` is set (e.g., `node_concept=User`), `graph.Node` IS the concept — assigning to `graph.Node` directly creates the property on the concept without a separate binding step:

```python
# graph.Node IS User when node_concept=User — property is automatically available on User
graph.Node.community = graph.weakly_connected_component()

# Query directly via User — no explicit binding needed
df = model.select(User.name, User.community).to_df()
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
| `aggregator` missing | Weighted graph with multi-edges requires aggregator for parallel edges | Add `aggregator="sum"` — but only when multi-edges are expected (see [Aggregator guidance](#aggregator-guidance)) |
| Weight type error | Weights must be floats, but property is Integer/Number | Cast with `floats.float(property)` in Edge.new weight parameter |
| Centrality all equal | Graph is a complete graph or all nodes have identical connectivity | Check if graph construction is correct; may need weighted edges to differentiate |
| Similarity produces too many results | O(n^2) output for n nodes | Filter by minimum threshold or limit to top-k per node |
| Reachability on undirected connected graph gives trivial results | On undirected connected graphs, all nodes are reachable from all others — results aren't useful | Set `directed=True` for meaningful reachability/impact analysis. (On disconnected undirected graphs, reachable can still be useful for discovering components for specific nodes.) |
| Wrong node concept | Using intermediary concept as nodes instead of entity concept | Intermediary concepts form edges, not nodes — e.g., `Operation` is an edge between `Site` nodes |
| Graph results not visible on original concept | Results bound to `graph.Node` but not to the source concept | Add explicit binding: `model.where(graph.Node == MyConcept).define(...)` |
| TyperError with large models | Many entities (200+) with Relationships in same model as Graph cause `TyperError` in type inference | Keep large datasets (historical shipments, transactions) as pandas DataFrames for Python-side analysis; only load entities the Graph actually needs into RAI. This is a **local execution** limitation — Snowflake-backed models handle larger schemas. |
| Empty graph when extending existing model | Script creates `Model("name")` without importing base model definitions — concepts exist but have no instances | Import the base model module (e.g., `from my_model import model, Site`) so base `define()` rules are in scope |

---

## Examples

Each example targets a distinct combination of edge construction, topology, algorithm, and result pattern.

| Primary Pattern | Construction | Topology | Algorithms | Result Pattern | File |
|----------------|-------------|----------|------------|----------------|------|
| Infrastructure `Edge.new()` | Intermediary concept (Operation) creates edges | Undirected, weighted | Eigenvector centrality | Simple property binding | [centrality_supply_chain.py](examples/centrality_supply_chain.py) |
| Co-occurrence `Edge.new()` | Shared-attribute edges with `id <` guard | Undirected, unweighted | WCC + betweenness | Hybrid risk: graph metric + domain attribute | [co_occurrence_clustering.py](examples/co_occurrence_clustering.py) |
| `edge_concept` + computed weight | Interaction concept as edges, multi-factor weight | Directed, weighted | PageRank + degree centrality | Multi-algorithm classification | [edge_concept_pagerank.py](examples/edge_concept_pagerank.py) |
| Directed reachability | `edge_concept` for dependency chain | Directed, unweighted | Reachability (4 modes) + betweenness | Graph + ontology enrichment | [reachability_impact_analysis.py](examples/reachability_impact_analysis.py) |
| Louvain → derived concept | Co-occurrence edges, community labels become entities | Undirected, weighted | Louvain + degree centrality | Community → concept + hub-per-community | [community_derived_concept.py](examples/community_derived_concept.py) |
| Graph + rules combo | Multi-concept co-occurrence (shared address/phone/email) | Undirected, unweighted | WCC | Layered Relationship flags on graph results | [graph_rules_integration.py](examples/graph_rules_integration.py) |
| Identity graph self-join | Self-join edges from shared identifiers (phone, email) | Undirected, unweighted | WCC | Identity cluster detection | [identity_graph_wcc.py](examples/identity_graph_wcc.py) |
| Multi-graph same model | Multiple Graph instances on same node concept | Weighted + unweighted | Eigenvector + betweenness | Parallel graph views, separate Edge defs | [multi_graph_same_model.py](examples/multi_graph_same_model.py) |

---

## Reference Files

| Reference | Description | File |
|-----------|-------------|------|
| Graph construction | Detailed construction patterns from ontology — entity-level, infrastructure, hierarchy, bridge, self-referencing, filtered, multi-graph | [graph-construction.md](references/graph-construction.md) |
| Algorithm selection | Per-algorithm deep dive — when to use, parameters, output shape, complexity, decision guidance | [algorithm-selection.md](references/algorithm-selection.md) |
| Result extraction | Query patterns for each algorithm output shape, model binding, DataFrame extraction, type handling | [result-extraction.md](references/result-extraction.md) |
