<!-- TOC -->
- [Algorithm Decision Guide](#algorithm-decision-guide)
- [Basic Statistics](#basic-statistics)
- [Neighbor Algorithms](#neighbor-algorithms)
- [Degree Algorithms](#degree-algorithms)
- [Centrality Algorithms](#centrality-algorithms)
- [Community Detection Algorithms](#community-detection-algorithms)
- [Component Algorithms](#component-algorithms)
- [Reachability](#reachability)
- [Distance Algorithms](#distance-algorithms)
- [Similarity Algorithms](#similarity-algorithms)
- [Clustering Algorithms](#clustering-algorithms)
- [Algorithm Compatibility Matrix](#algorithm-compatibility-matrix)
<!-- /TOC -->

## Algorithm Decision Guide

Start from the question, not the algorithm name.

| Question Pattern | Algorithm Family | Recommended Default |
|-----------------|-----------------|-------------------|
| "Which nodes are most important/influential overall?" | Centrality | `eigenvector_centrality()` |
| "Which nodes are bottlenecks / single points of failure?" | Centrality | `betweenness_centrality()` |
| "Which nodes receive the most flow/attention?" | Centrality | `pagerank()` (directed) |
| "How many connections does each node have?" | Centrality | `degree_centrality()` |
| "What natural clusters/groups exist?" | Community | `louvain()` (undirected) or `infomap()` (directed) |
| "Is the network fragmented? How many components?" | Components | `weakly_connected_component()` |
| "What depends on X? / What does X affect?" | Reachability | `reachable(from_=X)` or `reachable(to=X)` |
| "How far apart are two nodes?" | Distance | `distance()` |
| "What's the maximum separation in the network?" | Distance | `diameter_range()` |
| "Which **edges** are single points of failure (bridges)?" | Components | No named primitive — a single layered WCC (not a per-edge WCC loop), see [Collapsing per-scenario checks](#collapsing-per-scenario-connectivity-checks-into-one-wcc) |
| "Which nodes are structurally similar?" | Similarity | `jaccard_similarity()` |
| "Which nodes are likely to connect?" | Similarity | `adamic_adar()` or `preferential_attachment()` |
| "How tightly knit are local neighborhoods?" | Clustering | `local_clustering_coefficient()` |

---

## Basic Statistics

Use these for graph validation and sanity checks before running algorithms.

| Method | Returns | Use |
|--------|---------|-----|
| `graph.num_nodes()` | Unary relationship (scalar count) | Verify nodes were created — 0 means edge definitions don't match data |
| `graph.num_edges()` | Unary relationship (scalar count) | Verify edges were created — 0 means relationship/join path is wrong |
| `graph.num_triangles()` | Unary relationship (scalar count) | Count total unique triangles in the graph |

```python
# Quick validation after graph construction
graph.num_nodes().inspect()  # Should be > 0
graph.num_edges().inspect()  # Should be > 0

# .inspect() prints and returns None — to assert, fetch the scalar:
assert int(model.select(graph.num_edges().alias("n")).to_df()["n"].iloc[0]) > 0
```

---

## Neighbor Algorithms

Use these to explore the local neighborhood of nodes.

| Method | Returns | Description |
|--------|---------|-------------|
| `graph.neighbor()` | Binary `(node, neighbor)` | All neighbor pairs (ignoring direction) |
| `graph.inneighbor()` | Binary `(node, inneighbor)` | Nodes and their in-neighbors (directed graphs) |
| `graph.outneighbor()` | Binary `(node, outneighbor)` | Nodes and their out-neighbors (directed graphs) |
| `graph.common_neighbor()` | Ternary `(node1, node2, common)` | Common neighbor triplets |

---

## Degree Algorithms

Use these for raw connection counts per node. Different from `degree_centrality()` which normalizes by graph size.

| Method | Returns | Description |
|--------|---------|-------------|
| `graph.degree()` | Binary `(node, degree)` | Total connections per node |
| `graph.indegree()` | Binary `(node, indegree)` | Incoming connections (directed graphs) |
| `graph.outdegree()` | Binary `(node, outdegree)` | Outgoing connections (directed graphs) |
| `graph.weighted_degree()` | Binary `(node, weighted_degree)` | Sum of edge weights per node |
| `graph.weighted_indegree()` | Binary `(node, weighted_indegree)` | Sum of incoming edge weights |
| `graph.weighted_outdegree()` | Binary `(node, weighted_outdegree)` | Sum of outgoing edge weights |

```python
# Assign degree as a property on graph nodes
graph.Node.degree = graph.degree()
```

---

## Centrality Algorithms

### `eigenvector_centrality()`

**What it computes:** A node's importance based on the importance of its neighbors. A node connected to many important nodes gets a high score. Recursive: importance propagates through the network.

**When to use:**
- "Which nodes are most influential in the network overall?"
- "Which entities are best-connected to other well-connected entities?"
- Best general-purpose centrality measure when you don't have a specific bottleneck or flow question.

**Parameters:** None required.

**Requires `directed=False`.** Eigenvector centrality is defined as the principal eigenvector of the (symmetric) adjacency matrix; on a directed graph the operator is asymmetric and the recurrence may not converge — use `pagerank()` instead for directed networks.

**Output:** `(node, score)` — float score per node, normalized. Higher = more central.

```python
graph.Node.eigen_score = graph.eigenvector_centrality()
```

**Interpretation:** High eigenvector centrality means the node is connected to other high-centrality nodes — a "well-connected insider." Low centrality means peripheral.

---

### `betweenness_centrality()`

**What it computes:** How often a node lies on the shortest path between other node pairs. Nodes that bridge different parts of the network score high.

**When to use:**
- "Which nodes are critical connectors / bottlenecks?"
- "Which nodes, if removed, would most disrupt communication between other parts of the network?"
- "Which nodes bridge different clusters?"

**Parameters:** None required. **Does not support weighted graphs** — use on unweighted graphs only.

**Output:** `(node, score)` — float score per node. Higher = more "bridge-like."

```python
graph.Node.betweenness = graph.betweenness_centrality()
```

**Interpretation:** High betweenness centrality identifies gatekeepers and single points of failure. A node with high betweenness but low degree is a narrow bridge — its removal disconnects parts of the network.

**Complexity note:** O(V * E) — can be slow on very large graphs (100K+ nodes). Unweighted only.

---

### `degree_centrality()`

**What it computes:** Number of direct connections per node, normalized by graph size.

**When to use:**
- "Which nodes have the most direct relationships?"
- Good baseline / sanity check before more sophisticated centrality measures.
- Fast and simple — use when you need a quick connectivity measure.

**Parameters:** None required.

**Output:** `(node, score)` — float score, range [0, 1].

```python
graph.Node.degree = graph.degree_centrality()
```

**Interpretation:** High degree = many direct connections. Does NOT account for the quality/importance of those connections (unlike eigenvector centrality).

---

### `pagerank()`

**What it computes:** Importance based on directed link structure — a node is important if it receives many links from other important nodes. Originally designed for web page ranking.

**When to use:**
- Directed networks where flow/attention has inherent direction
- "Which nodes receive the most flow from upstream?"
- Supply chains (downstream importance), citation networks, web-like structures

**Parameters:**
- `damping` (float, default 0.85) — probability of following a link vs random jump. Standard value is 0.85; lower values spread importance more evenly.

**Output:** `(node, score)` — float score per node, sums to 1.0 across all nodes.

```python
graph.Node.pr_score = graph.pagerank()
# or with custom damping:
graph.Node.pr_score = graph.pagerank(damping=0.9)
```

**Interpretation:** High PageRank = receives importance from many/important upstream nodes. In a supply chain, high PageRank identifies nodes that many suppliers feed into.

**Note:** Most meaningful on directed graphs. On undirected graphs, PageRank degenerates toward degree centrality.

---

### Eigenvector vs. PageRank — same "importance via neighbors", opposite directionality

Both score a node by the importance of the nodes it connects to, so "which nodes are most important / central / influential?" can match either. They differ in **what kind of importance the question is about**:

- **Eigenvector (`directed=False`)** — *mutual, recursive* importance: a node is important when its neighbors are important, symmetrically. The structural-centrality reading — "well-connected to other well-connected nodes."
- **PageRank (`directed=True`)** — *directional inbound* importance: a node is important when important nodes **point at it**. The flow/attention reading — "a lot flows into it from upstream."

Match the choice to the question's intent — the two give different rankings on the same network.

---

## Community Detection Algorithms

### `louvain()`

**What it computes:** Partitions the graph into communities that maximize modularity — dense internal connections, sparse cross-community connections.

**When to use:**
- "What natural groups/clusters exist in the network?"
- General-purpose community detection — the default choice for undirected graphs.

**Requirements:** `directed=False` — **Louvain does not work on directed graphs.**

**Parameters:** None required.

**Output:** `(node, label)` — integer community label per node.

```python
graph.Node.community = graph.louvain()
```

**Interpretation:** Nodes with the same community label are more densely connected to each other than to nodes in other communities.

**Type note:** Community labels are `Int128Array` — cast with `.astype(int)` before pandas operations and before passing to `model.data()` (Int128Dtype is unrecognized by `model.data()` type inference).

**Non-deterministic:** Louvain may produce different community assignments, counts, and sizes across runs on the same data. Report results as ranges or structural assertions, not exact values.

---

### `infomap()`

**What it computes:** Finds communities by optimizing the map equation — minimizes the description length of a random walk on the graph.

**When to use:**
- Directed and/or weighted networks where Louvain isn't applicable
- Flow-based networks where community structure follows flow patterns
- Generally higher quality than Louvain on directed weighted graphs

**Requirements:** Works on directed and undirected, weighted and unweighted.

**Parameters:** None required.

**Output:** `(node, label)` — integer community label per node.

```python
graph.Node.community = graph.infomap()
```

**Non-deterministic:** Infomap uses stochastic node movement to optimize the map equation. Community assignments may differ across runs on the same data.

---

### `label_propagation()`

**What it computes:** Each node adopts the label most common among its neighbors, iterating until convergence.

**When to use:**
- Very large graphs where Louvain/infomap is too slow
- When approximate community structure is sufficient
- Quick exploratory analysis

**Requirements:** Works on any graph type.

**Parameters:** None required.

**Output:** `(node, label)` — integer label per node.

**Note:** Non-deterministic — results may vary between runs.

```python
graph.Node.community = graph.label_propagation()
```

---

## Component Algorithms

### `weakly_connected_component()`

**What it computes:** Assigns each node to its connected component (ignoring edge direction). Nodes in the same component can reach each other via some path.

**When to use:**
- "Is the network fragmented?"
- "How many disconnected subgraphs exist?"
- "Which nodes are isolated?"
- Prerequisite for bridge detection (nodes connecting different components)

**Parameters:** None required. Works on directed and undirected.

**Output:** `(node, component_id_node)` — binary relation. The `component_id` side is itself a **`Node`** (the min-id node of the component), not a raw integer.

```python
graph.Node.component = graph.weakly_connected_component()
```

**Interpretation:** All nodes with the same `component_id_node` can reach each other. A single large component suggests good connectivity; many small components suggest fragmentation.

**Type note:** Because the component ID is a Node, how it surfaces in DataFrames depends on the query pattern:
- **Shorthand / property-assignment pattern** (`graph.Node.component = graph.weakly_connected_component()`, then `model.select(Site.component).to_df()`): the component column arrives as **string hashes** (serialized entity IDs). Use `.astype(str)` if any cast is needed.
- **Direct query pattern** — use `graph.Node.ref()` for BOTH sides, then select `.id` from the component ref to get the underlying integer (min-id node). That integer comes through as `Int128` — cast with `.astype(int)` before pandas ops and before passing to `model.data()`. Using `Integer.ref()` for the component side raises `TyperError`.

---

### `is_connected()`

**What it computes:** Boolean — whether all nodes can reach all other nodes (ignoring direction).

**When to use:** Quick connectivity check before running other algorithms.

**Output:** Boolean (True/False) for the entire graph.

```python
connected = graph.is_connected()
```

---

### Collapsing per-scenario connectivity checks into one WCC

**Principle.** When you would run a connectivity algorithm (`weakly_connected_component()`, `reachable()`, `is_connected()`) once per "what if entity X is removed" scenario, don't loop — collapse all scenarios into **one** layered graph + **one** WCC. A WCC costs a near-fixed ~20–25 s per call regardless of graph size, so cost tracks the *number of calls*, not graph size; a per-scenario loop hits ~5 min at ~14 scenarios. Identify a node by `(original_node, scenario)`; scenario S's layer holds the graph as it looks under S. Layers share no nodes, so one WCC labels every scenario independently — filter to a layer to read that scenario's answer. Cost ≈ one WCC for any N. Results stay bound to your concepts for downstream rules and optimization.

**Worked example — bridge edges.** A bridge is an edge whose removal disconnects the graph (edge-side single point of failure). One scenario per edge: layer L keeps every edge *except* L. **Edge L is a bridge iff its two endpoints land in different components within layer L** — an endpoint left with no incident edges is absent from the WCC output, i.e. its own isolated component, still a bridge. Bind the result back as a `Relationship` on the edge concept. (`betweenness_centrality()` is **not** a substitute: it scores nodes, not "would removing this edge disconnect the graph" — high node betweenness ≠ bridge edge, so it can't even pre-filter candidates.)

```python
# BAD — a separate Graph + WCC per edge = N WCC calls (per-scenario cost above) → times out at ~14 edges
for excluded in candidate_edge_ids:
    g = Graph(model, directed=False, node_concept=NodeConcept)  # graph minus `excluded`, then one WCC each

# GOOD — one layered graph, one WCC
from relationalai.semantics import String
import pandas as pd

def find_bridges(model, EdgeConcept, NodeConcept, src_attr, dst_attr):
    """src_attr/dst_attr: endpoint attribute NAMES (e.g. "from_substation"); to scope, add a domain filter to BOTH where()s."""
    # Endpoints by attribute NAME via getattr — a Property object as a parameter trips type inference.
    e = EdgeConcept.ref()
    edges = model.select(
        e.id.alias("edge"),
        getattr(e, src_attr).id.alias("src"),
        getattr(e, dst_attr).id.alias("dst"),
    ).to_df()

    # node identity = (original node, excluded-edge "layer")
    Layer = model.Concept("BridgeLayerNode", identify_by={"node": String, "layer": String})
    L, O = EdgeConcept.ref(), EdgeConcept.ref()
    model.where(O.id != L.id).define(
        Layer.new(node=getattr(O, src_attr).id, layer=L.id),
        Layer.new(node=getattr(O, dst_attr).id, layer=L.id),
    )
    g = Graph(model, directed=False, weighted=False, node_concept=Layer)
    L, O = EdgeConcept.ref(), EdgeConcept.ref()
    sn, dn = Layer.ref(), Layer.ref()
    model.where(                                   # layer L = every edge O except L
        O.id != L.id,
        sn.node == getattr(O, src_attr).id, sn.layer == L.id,
        dn.node == getattr(O, dst_attr).id, dn.layer == L.id,
    ).define(g.Edge.new(src=sn, dst=dn))

    # ONE WCC (direct-query, not the `graph.Node.X = ...` shorthand). Composite-key gotcha: the
    # component rep is a layered node with no scalar .id — select cr.node/cr.layer
    # (cr.id raises `UnresolvedType ... argument 'id'`), then concatenate.
    nr, cr = g.Node.ref(), g.Node.ref()
    comps = (model.where(g.weakly_connected_component()(nr, cr))
        .select(nr.node.alias("node"), nr.layer.alias("layer"),
                cr.node.alias("cn"), cr.layer.alias("cl")).to_df())
    comps["comp"] = comps["cn"].astype(str) + "||" + comps["cl"].astype(str)   # IDs surface as str hashes

    bridges = []
    for _, r in edges.iterrows():
        cu = comps.loc[(comps["layer"] == r["edge"]) & (comps["node"] == r["src"]), "comp"]
        cv = comps.loc[(comps["layer"] == r["edge"]) & (comps["node"] == r["dst"]), "comp"]
        cu = cu.iloc[0] if len(cu) else f"__iso__{r['src']}"   # missing endpoint = isolated component
        cv = cv.iloc[0] if len(cv) else f"__iso__{r['dst']}"
        if cu != cv:
            bridges.append(r["edge"])
    return bridges

bridge_ids = find_bridges(model, EdgeConcept, NodeConcept, "from_substation", "to_substation")
EdgeConcept.is_bridge = model.Relationship(f"{EdgeConcept} is a bridge")
model.where(EdgeConcept.id.in_(bridge_ids)).define(EdgeConcept.is_bridge())
```

**Parallel edges:** let the `Multi-edges are not allowed when aggregator=None` warning fire — `aggregator="sum"` collapses parallel edges into one and would falsely flag both as bridges (removing one leaves the other, so neither is a bridge).

**Scale:** the layered graph is N× the original (N layers × ~E edges); one WCC absorbs that for typical N. If even one WCC strains the type-inference scope limit, scope the candidate/layer set with the docstring's domain filter — an optimization, not a timeout dodge.

---

## Reachability

Works on both directed and undirected graphs, but most meaningful on directed graphs. On undirected connected graphs, all nodes are trivially reachable from all others. On disconnected undirected graphs, reachable is useful for discovering the component(s) for given node(s) — especially with domain constraints via `from_=` or `to=`.

### `reachable(full=True)`

**What it computes:** All-pairs transitive closure — every `(source, target)` pair where source can reach target via directed paths. Returns the complete dependency map of the graph.

**When to use:**
- "What are all transitive dependencies across the entire network?"
- BOM analysis, full dependency mapping, transitive closure
- When you need the complete picture before filtering to specific questions

```python
reachable = graph.reachable(full=True)

src, dst = graph.Node.ref("s"), graph.Node.ref("d")
df = (
    model.where(reachable(src, dst))
    .select(src.id.alias("from_id"), dst.id.alias("to_id"))
    .to_df()
)
```

**Output:** `(source, target)` pairs — all transitively reachable node pairs in the graph.

### `reachable(from_=X)` and `reachable(to=X)`

**What it computes:** Parameterized reachability — all nodes reachable from or to a specific target.

**When to use:**
- `reachable(from_=X)` — "If X goes offline, what's affected downstream?"
- `reachable(to=X)` — "What are all the upstream dependencies of X?"
- Impact analysis, dependency tracing, supply chain propagation

**Parameters:**
- `from_=target` — specifies source node(s) for downstream reachability
- `to=target` — specifies destination node(s) for upstream reachability

The target is specified via a concept reference with a `.where()` filter:

```python
# Define target filter
CriticalSite = model.Relationship(f"{Site} is critical")
model.where(Site.name == "Main Warehouse").define(Site.is_critical())

# Downstream: what does the critical site feed?
downstream = graph.reachable(from_=Site.is_critical)

# Upstream: what feeds the critical site?
upstream = graph.reachable(to=Site.is_critical)
```

**Targeting in multi-concept graphs.** When the graph spans multiple node concepts (Pattern 1 — no `node_concept` set), `graph.Node` is a synthetic node concept distinct from any domain concept. The `from_=` / `to=` Relationship must be defined over `graph.Node`, not over a domain concept — otherwise `reachable()` returns empty because the type doesn't match the graph's node type.

```python
# Multi-concept graph: nodes drawn from ConceptA and ConceptB
graph = Graph(model, directed=True, weighted=False)
# ... define edges connecting nodes from both concepts ...

# WRONG — ConceptA.is_target won't match graph.Node
# bad_target = model.Relationship(f"{ConceptA} is target")
# model.where(ConceptA.id == X).define(bad_target())

# RIGHT — target Relationship is over graph.Node
target = model.Relationship(f"target: {graph.Node}")
n = graph.Node.ref()
model.define(target(n)).where(n == ConceptA.lookup(id=X))

downstream = graph.reachable(from_=target)
```

For single-concept graphs (Pattern 2 / 3 with a `node_concept` set), the target Relationship can be over the domain concept directly — `graph.Node` IS that concept so they're interchangeable.

**Output:** `(source, target)` pairs — binary relation of reachable node pairs.

```python
src, dst = graph.Node.ref("s"), graph.Node.ref("d")
df = (
    model.where(graph.reachable(from_=Site.is_critical)(src, dst))
    .select(src.id.alias("from"), dst.id.alias("to"))
    .to_df()
)
```

---

## Distance Algorithms

### `distance()`

**What it computes:** Shortest path length between all pairs of nodes. On weighted graphs, minimizes sum of edge weights along the path.

**When to use:**
- "How far apart are X and Y?"
- "What's the shortest route between nodes?"
- Proximity analysis

**Requirements:** Weighted graphs must have non-negative weights.

**Output:** `(start, end, length)` — ternary relation.

```python
src, dst, length = graph.Node.ref("s"), graph.Node.ref("d"), Float.ref("len")
df = (
    model.where(graph.distance(full=True)(src, dst, length))
    .select(src.id.alias("from"), dst.id.alias("to"), length.alias("distance"))
    .to_df()
)
```

**Note:** Produces O(n^2) rows. For large graphs, prefer `from_=`, `to=`, or `between=` to scope to specific node subsets instead of `full=True`.

---

### `diameter_range()`

**What it computes:** Lower and upper bounds on the graph diameter (longest shortest path between any two nodes).

**When to use:** "What's the maximum separation in the network?"

**Output:** `(lower_bound, upper_bound)` tuple.

**Constraints:** Not available for directed or weighted graphs — requires `directed=False, weighted=False`.

```python
lower, upper = graph.diameter_range()
```

---

## Similarity Algorithms

### `jaccard_similarity()`

**What it computes:** For each node pair, the ratio of shared neighbors to total neighbors. Range [0, 1].

**When to use:**
- "Which entities are most structurally similar?"
- Finding entities that play similar roles in the network

**Output:** `(node1, node2, score)` — ternary relation. Score in [0, 1].

**Warning:** O(n^2) output. Filter by minimum threshold for large graphs.

---

### `cosine_similarity()`

**What it computes:** Cosine of the angle between neighbor vectors. Weighted variant of structural similarity.

**When to use:** Similar to Jaccard but accounts for edge weights.

**Output:** `(node1, node2, score)` — score in [0, 1].

---

### `adamic_adar()`

**What it computes:** Weighted sum of shared neighbors, where rare (low-degree) shared neighbors contribute more.

**When to use:** Link prediction — "which unconnected nodes are likely to connect?"

**Output:** `(node1, node2, score)` — higher score = more likely to connect.

---

### `preferential_attachment()`

**What it computes:** Product of node degrees. High-degree nodes are more likely to form new connections.

**When to use:** Link prediction in scale-free networks (social networks, citation networks).

**Output:** `(node1, node2, score)` — higher = more likely.

---

## Clustering Algorithms

### `local_clustering_coefficient()`

**What it computes:** For each node, the fraction of its neighbors that are also connected to each other. Measures local density/tightness.

**Requirements:** `directed=False`.

**Output:** `(node, coefficient)` — float in [0, 1]. 1.0 means all neighbors are fully connected.

```python
graph.Node.clustering = graph.local_clustering_coefficient()
```

---

### `average_clustering_coefficient()`

**What it computes:** Mean of all local clustering coefficients. Single scalar summarizing graph density.

**Requirements:** `directed=False`.

**Output:** Single float.

---

### `triangle_count()`

**What it computes:** Number of triangles each node participates in.

**Output:** `(node, count)` — integer per node.

```python
graph.Node.triangles = graph.triangle_count()
```

Also available: `graph.triangle()` returns ternary `(n1, n2, n3)` of all triangles, and `graph.unique_triangle()` returns only unique triangles (each triangle appears once, not three times).

---

## Algorithm Compatibility Matrix

| Algorithm | Directed | Undirected | Weighted | Unweighted |
|-----------|----------|------------|----------|------------|
| `num_nodes()` / `num_edges()` | Yes | Yes | Yes | Yes |
| `neighbor()` | Yes | Yes | N/A | N/A |
| `inneighbor()` / `outneighbor()` | Yes | Yes | N/A | N/A |
| `degree()` / `indegree()` / `outdegree()` | Yes | Yes | N/A | N/A |
| `weighted_degree()` / variants | Yes | Yes | **Required** | N/A |
| `eigenvector_centrality()` | **No** | Yes | Yes | Yes |
| `betweenness_centrality()` | Yes | Yes | **No** | Yes |
| `degree_centrality()` | Yes | Yes | N/A | N/A |
| `pagerank()` | **Best** | Yes | Yes | Yes |
| `louvain()` | **No** | Yes | Yes | Yes |
| `infomap()` | Yes | Yes | **Best** | Yes |
| `label_propagation()` | Yes | Yes | Yes | Yes |
| `weakly_connected_component()` | Yes | Yes | N/A | N/A |
| `is_connected()` | Yes | Yes | N/A | N/A |
| `reachable()` | Yes | Yes | N/A | N/A |
| `distance()` | Yes | Yes | Yes (non-neg) | Yes |
| `diameter_range()` | No | Yes | No | Yes |
| `jaccard_similarity()` | Yes | Yes | N/A | N/A |
| `cosine_similarity()` | Yes | Yes | Yes | Yes |
| `adamic_adar()` | Yes | Yes | N/A | N/A |
| `preferential_attachment()` | Yes | Yes | N/A | N/A |
| `local_clustering_coefficient()` | No | **Required** | N/A | N/A |
| `triangle_count()` / `triangle()` | Yes | Yes | N/A | N/A |
