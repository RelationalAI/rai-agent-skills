<!-- TOC -->
- [Output Shapes by Algorithm](#output-shapes-by-algorithm)
- [Querying Results via DataFrame](#querying-results-via-dataframe)
- [Binding Results to Model Concepts](#binding-results-to-model-concepts)
- [Creating Concept Entities from Graph Outputs](#creating-concept-entities-from-graph-outputs)
- [Type Handling](#type-handling)
- [Filtering and Aggregating Results](#filtering-and-aggregating-results)
- [Combining Graph Results with Ontology Joins](#combining-graph-results-with-ontology-joins)
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
| `weakly_connected_component()` | Binary | `(node, component_id_node)` | `Node.ref(), Node.ref()` (the component ID is itself the min-id node of the component) |
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

### Shorthand: assign to graph.Node with `node_concept`

When `node_concept` is set (e.g., `node_concept=User`), `graph.Node` IS the concept — assigning to `graph.Node` directly creates the property on the concept without a separate binding step:

```python
# graph.Node IS User when node_concept=User — property is automatically available on User
graph.Node.component = graph.weakly_connected_component()

# Query directly via User — no explicit binding needed.
# Note: WCC stores a Node per user; User.component serializes as a string hash in to_df().
df = model.select(User.name, User.component).to_df()
```

Use this shorthand when you need a simple property binding. Use the explicit three-step pattern (declare `model.Property`, bind via `define()`) when you need more control (e.g., custom property type declarations, or binding results to a concept different from `node_concept`).

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

**WCC components cannot be turned into a new concept via the shorthand pattern** the way Louvain labels can. `graph.weakly_connected_component()` returns a Node-typed relation, so `graph.Node.component_id` is itself a Node — not an integer — and `NetworkComponent.new(id=graph.Node.component_id)` fails type inference regardless of whether `NetworkComponent.id` is declared `Integer` or `String`.

Two workable alternatives:

1. **Use the existing Node as the component entity.** A component is already represented by its min-id node. You can attach per-component properties to `Site` directly, using the component_id node as a grouping key:

   ```python
   graph.Node.component_id = graph.weakly_connected_component()
   # Now query "how many sites in the same component as Site X?" etc.
   ```

2. **Round-trip through pandas** to create a separate `NetworkComponent` concept with integer IDs:

   ```python
   node_ref, comp_ref = graph.Node.ref(), graph.Node.ref()
   rows = (
       model.select(node_ref.id.alias("node_id"), comp_ref.id.alias("comp_id"))
       .where(graph.weakly_connected_component()(node_ref, comp_ref))
       .to_df()
   )
   rows["comp_id"] = rows["comp_id"].astype(int)          # Int128 -> int
   comp_df = rows[["comp_id"]].drop_duplicates().rename(columns={"comp_id": "id"})
   comp_data = model.data(comp_df)
   NetworkComponent = model.Concept("NetworkComponent", identify_by={"id": Integer})
   model.define(NetworkComponent.new(id=comp_data.id))
   ```

The Louvain / Infomap pattern above works directly because community labels are integer-valued, not node-valued.

---

## Type Handling

### Int128Array from RAI (Louvain, Infomap, and direct-query WCC)

Integer graph outputs — Louvain / Infomap community labels, and WCC component IDs accessed via the **direct query** pattern (`select(comp_ref.id, ...)`) — return as `Int128Array` in DataFrames. This type is incompatible with most pandas operations and with `model.data()` type inference (Int128Dtype maps to `"Any"` instead of `"Integer"`, causing `TyperError`).

**Always cast Louvain/Infomap/direct-query-WCC integer columns before further use:**

```python
df["community"] = df["community"].astype(int)      # louvain / infomap
df["component_int"] = df["component_int"].astype(int)  # WCC via direct query on comp_ref.id
```

**Failure symptoms without casting:**
- `TyperError` from `model.data()` type inference (Int128Dtype → `"Any"`)
- `TypeError` on pandas groupby, merge, or comparison operations
- Silent wrong results on equality checks
- JSON serialization errors

### WCC via shorthand — string hashes, not integers

`graph.weakly_connected_component()` is different from Louvain/Infomap: its output side is a **Node**, not an integer. When accessed via the shorthand `graph.Node.component = graph.weakly_connected_component()` and queried with `model.select(Site.component).to_df()`, the column arrives as **string hashes** (serialized entity IDs like `'hQFeq4Qx/oM955jyw1adGg'`) with `dtype=str`.

```python
graph.Node.component = graph.weakly_connected_component()
df = model.select(Site.id, Site.component).to_df()
df["component"] = df["component"].astype(str)   # OK — already strings
# df["component"] = df["component"].astype(int) # ValueError: invalid literal for int()
```

To get an integer component ID from WCC, use the direct query pattern (select `comp_ref.id`, cast to int).

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

### Combining graph results with ontology joins

Graph algorithm results can be joined with non-graph ontology relationships in a single `where()` clause. This is the key pattern for enriching graph output with domain context — e.g., "which facilities are reachable AND what products do they produce?"

```python
# Downstream reachability enriched with Product data in one query
downstream = graph.Node.ref()
impact_df = (
    where(
        reachable_from(target, downstream),       # graph result
        Product.facility(downstream),              # ontology join: facility has products
    )
    .select(distinct(
        downstream.name.alias("facility"),
        Product.name.alias("product_at_risk"),
        aggregates.sum(Product.quantity).per(downstream, Product).alias("units_at_risk"),
    ))
    .to_df()
)
```

The pattern works with any algorithm output. For centrality:

```python
# Top-central nodes enriched with their department info
node, score = graph.Node.ref("n"), Float.ref("s")
df = (
    where(
        graph.eigenvector_centrality()(node, score),
        node.department,                           # ontology join
        score > 0.5,                               # threshold filter
    )
    .select(
        node.name.alias("name"),
        node.department.name.alias("dept"),
        score.alias("centrality"),
    )
    .to_df()
)
```

**When to use:** Whenever the graph answer alone isn't enough — you need to cross-reference reachable/central/community nodes with their products, orders, SKUs, or other domain relationships to answer the real business question.

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
