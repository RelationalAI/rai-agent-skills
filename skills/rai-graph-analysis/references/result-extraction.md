<!-- TOC -->
- [Output Shapes by Algorithm](#output-shapes-by-algorithm)
- [Querying Results via DataFrame](#querying-results-via-dataframe)
- [Binding Results to Model Concepts](#binding-results-to-model-concepts)
- [Creating Concept Entities from Graph Outputs](#creating-concept-entities-from-graph-outputs)
- [Type Handling](#type-handling)
- [Filtering and Aggregating Results](#filtering-and-aggregating-results)
- [Result Validation](#result-validation)
<!-- /TOC -->

## Output Shapes by Algorithm

| Algorithm | Output Type | Relation | Variables |
|-----------|-----------|----------|-----------|
| `eigenvector_centrality()` | Binary | `(node, score)` | `Node.ref(), Float.ref()` |
| `betweenness_centrality()` | Binary | `(node, score)` | `Node.ref(), Float.ref()` |
| `degree_centrality()` | Binary | `(node, score)` | `Node.ref(), Float.ref()` |
| `pagerank()` | Binary | `(node, score)` | `Node.ref(), Float.ref()` |
| `louvain()` | Binary | `(node, label)` | `Node.ref(), Integer.ref()` |
| `infomap()` | Binary | `(node, label)` | `Node.ref(), Integer.ref()` |
| `label_propagation()` | Binary | `(node, label)` | `Node.ref(), Integer.ref()` |
| `weakly_connected_component()` | Binary | `(node, component_id)` | `Node.ref(), Integer.ref()` |
| `reachable()` | Binary | `(source, target)` | `Node.ref(), Node.ref()` |
| `distance()` | Ternary | `(start, end, length)` | `Node.ref(), Node.ref(), Float.ref()` |
| `jaccard_similarity()` | Ternary | `(node1, node2, score)` | `Node.ref(), Node.ref(), Float.ref()` |
| `cosine_similarity()` | Ternary | `(node1, node2, score)` | `Node.ref(), Node.ref(), Float.ref()` |
| `adamic_adar()` | Ternary | `(node1, node2, score)` | `Node.ref(), Node.ref(), Float.ref()` |
| `local_clustering_coefficient()` | Binary | `(node, coeff)` | `Node.ref(), Float.ref()` |
| `triangle_count()` | Binary | `(node, count)` | `Node.ref(), Integer.ref()` |

---

## Querying Results via DataFrame

### Binary results: `(node, value)`

Pattern for centrality, community, components, clustering:

```python
node, score = graph.Node.ref("n"), Float.ref("s")
df = (
    model.where(graph.eigenvector_centrality()(node, score))
    .select(
        node.id.alias("node_id"),
        node.name.alias("node_name"),  # include identifying properties
        score.alias("centrality_score"),
    )
    .to_df()
    .sort_values("centrality_score", ascending=False)
)
```

For community/component labels (integer output):

```python
node, label = graph.Node.ref("n"), Integer.ref("lbl")
df = (
    model.where(graph.louvain()(node, label))
    .select(
        node.id.alias("node_id"),
        label.alias("community_label"),
    )
    .to_df()
)
# Cast Int128 before further pandas operations
df["community_label"] = df["community_label"].astype(int)
```

### Ternary results: `(node1, node2, value)`

Pattern for distance, similarity:

```python
src, dst, length = graph.Node.ref("s"), graph.Node.ref("d"), Float.ref("len")
df = (
    model.where(graph.distance()(src, dst, length))
    .select(
        src.id.alias("from_id"),
        dst.id.alias("to_id"),
        length.alias("distance"),
    )
    .to_df()
)
```

### Binary pair results: `(source, target)`

Pattern for reachability:

```python
src, dst = graph.Node.ref("s"), graph.Node.ref("d")
df = (
    model.where(graph.reachable(from_=target_filter)(src, dst))
    .select(
        src.id.alias("source_id"),
        dst.id.alias("target_id"),
    )
    .to_df()
)
```

---

## Binding Results to Model Concepts

Graph results live on `graph.Node`. To use them as properties on the original concept, bind explicitly:

### Float property binding (centrality, clustering)

```python
# Step 1: Run algorithm — result lives on graph.Node
graph.Node.centrality_score = graph.eigenvector_centrality()

# Step 2: Declare property on original concept
Site.centrality_score = model.Property(f"{Site} has {Float:centrality_score}")

# Step 3: Bind via graph.Node identity
model.where(graph.Node == Site).define(
    Site.centrality_score(graph.Node.centrality_score)
)

# Now Site.centrality_score is available to queries, rules, and optimization
```

### Integer property binding (community, component)

```python
graph.Node.community_label = graph.louvain()

Site.community_label = model.Property(f"{Site} has {Integer:community_label}")
model.where(graph.Node == Site).define(
    Site.community_label(graph.Node.community_label)
)
```

### Why binding matters

Without binding, graph results are only accessible via `graph.Node` queries. Binding makes them available as first-class concept properties — queryable, usable in rules, referenceable in optimization constraints and objectives.

---

## Creating Concept Entities from Graph Outputs

### Community labels → Segment concept

Turn community labels into proper concept entities for richer downstream use:

```python
# Run community detection
graph.Node.community_label = graph.louvain()

# Create segment concept from labels
CustomerSegment = model.Concept("CustomerSegment", identify_by={"id": Integer})
model.define(CustomerSegment.new(id=graph.Node.community_label))

# Attach segment to customer via relationship
Customer.segment = model.Relationship(f"{Customer} belongs to {CustomerSegment}")
model.where(graph.Node == Customer).define(
    Customer.segment(CustomerSegment.filter_by(id=graph.Node.community_label))
)

# Now you can query per-segment aggregates
segment_stats = (
    model.where(Customer.segment == CustomerSegment, Order.customer == Customer)
    .select(
        CustomerSegment.id.alias("segment_id"),
        aggregates.count(Customer).per(CustomerSegment).alias("customers"),
        aggregates.sum(Order.amount).per(CustomerSegment).alias("revenue"),
    )
    .to_df()
)
```

### Component IDs → Component concept

Same pattern for WCC components:

```python
graph.Node.component_id = graph.weakly_connected_component()

NetworkComponent = model.Concept("NetworkComponent", identify_by={"id": Integer})
model.define(NetworkComponent.new(id=graph.Node.component_id))

Site.network_component = model.Relationship(f"{Site} in {NetworkComponent}")
model.where(graph.Node == Site).define(
    Site.network_component(NetworkComponent.filter_by(id=graph.Node.component_id))
)
```

---

## Type Handling

### Int128Array from RAI

Community labels, component IDs, and other integer graph outputs return as `Int128Array` in DataFrames. This type is incompatible with most pandas operations.

**Always cast before pandas operations:**

```python
df["community"] = df["community"].astype(int)
df["component_id"] = df["component_id"].astype(int)
```

**Failure symptoms without casting:**
- `TypeError` on groupby, merge, or comparison operations
- Silent wrong results on equality checks
- JSON serialization errors

### Float scores

Centrality and similarity scores are standard Python floats — no casting needed.

### Node references

When extracting results, always select identifying properties (`.id`, `.name`) from nodes, not the node reference itself:

```python
# Good: select identifying property
node.id.alias("node_id")

# Bad: selecting the node reference directly gives internal IDs
node.alias("node")  # internal reference, not useful
```

---

## Filtering and Aggregating Results

### Top-N by score

```python
# Top 10 most central nodes
node, score = graph.Node.ref("n"), Float.ref("s")
df = (
    model.where(graph.eigenvector_centrality()(node, score))
    .select(node.id.alias("id"), node.name.alias("name"), score.alias("centrality"))
    .to_df()
    .sort_values("centrality", ascending=False)
    .head(10)
)
```

### Per-community aggregates

```python
node, label = graph.Node.ref("n"), Integer.ref("lbl")
community_sizes = (
    model.where(graph.louvain()(node, label))
    .select(
        label.alias("community"),
        aggregates.count(node).per(label).alias("size"),
    )
    .to_df()
)
community_sizes["community"] = community_sizes["community"].astype(int)
```

### Filtered similarity (threshold)

```python
n1, n2, score = graph.Node.ref("a"), graph.Node.ref("b"), Float.ref("s")
df = (
    model.where(
        graph.jaccard_similarity()(n1, n2, score),
        score > 0.5,  # only high-similarity pairs
    )
    .select(n1.id.alias("node1"), n2.id.alias("node2"), score.alias("similarity"))
    .to_df()
)
```

### Reachability count

```python
# Count how many nodes are reachable from each node
src, dst = graph.Node.ref("s"), graph.Node.ref("d")
reach_counts = (
    model.where(graph.reachable(from_=target_filter)(src, dst))
    .select(
        src.id.alias("source"),
        aggregates.count(dst).per(src).alias("downstream_count"),
    )
    .to_df()
)
```

---

## Result Validation

After running an algorithm, verify results make sense before using them downstream:

### Check for degenerate results

```python
# All centrality scores equal → graph may be trivially connected or empty
scores = df["centrality"].unique()
if len(scores) == 1:
    print("Warning: all centrality scores are identical — graph may be trivial")

# All nodes in same community → graph may be fully connected
communities = df["community"].unique()
if len(communities) == 1:
    print("Warning: only one community found — graph may be too dense")
```

### Check coverage

```python
# Verify all expected nodes got results
expected_count = model.select(aggregates.count(Site)).to_df().iloc[0, 0]
actual_count = len(df)
if actual_count < expected_count:
    print(f"Warning: {expected_count - actual_count} nodes missing from results")
    # Likely: disconnected nodes or nodes with no edges
```

### Sanity check reachability

```python
# Downstream reach should be subset of all nodes
total_nodes = model.select(aggregates.count(graph.Node)).to_df().iloc[0, 0]
reach_count = len(df)
print(f"Reachable: {reach_count}/{total_nodes} nodes")
```
