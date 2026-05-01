# Domain Constraints

Domain constraints control which subset of an output relationship gets materialized. Load this file when you hit a `full=True`-guard error from an algorithm like `preferential_attachment`, `common_neighbor`, `jaccard_similarity`, `reachable`, or `triangle`, or when you need to scope `degree`/`distance`/`reachable` to a specific subset of nodes or node pairs.

## Why domain constraints matter

For some relationships, full materialization is tractable. For example, `outdegree` is linear in the number of nodes/edges — materializing it fully is typically reasonable. But other relationships can be expensive or intractable to materialize in full. For example, `preferential_attachment` is quadratic in the number of nodes, and `common_neighbor` can be cubic — full materialization rapidly becomes infeasible as the graph grows.

Even for relationships that are tractable to materialize in full, applications often need only a small subset. If you only need the `outdegree` of a single node, paying the cost of materializing the full relationship is wasteful. Domain constraints let you specify which subset to materialize.

## Which relationships support domain constraints

Not all relationships support domain constraints, and those that do support different keyword arguments. **Check the docstring for a given relationship** (in the graph library source or documentation) to confirm which domain constraint modes it supports at this time.

General patterns by relationship shape:

| Relationship Shape | Examples | Typical Domain Constraint Keywords |
|---------------|----------|-----------------------------------|
| Node → value (binary) | `degree()`, `neighbor()`, `local_clustering_coefficient()`, `weakly_connected_component()`, `degree_centrality()` | `of` |
| Node-pair (binary) | `reachable()` | `full`, `from_`, `to`, `between` |
| Node-pair (ternary) | `jaccard_similarity()`, `preferential_attachment()`, `distance()`, `common_neighbor()` | `full`, `from_`, `to`, `between` |
| Scalar / global | `num_nodes()`, `eigenvector_centrality()`, `pagerank()`, `louvain()` | None — computed in full by nature |

## The `full` keyword

Relationships that are typically expensive enough to materialize in full that doing so is a footgun (e.g. preferential attachment, reachable, common_neighbor, triangle) will **error with guidance** if called without domain-constraint keyword arguments. To override this guard and compute the full relationship, pass `full=True`:

## Domain constraint keyword patterns

Each keyword argument takes a `Relationship` containing the nodes or node pairs to constrain to:

| Keyword | Argument Type | Meaning | Example |
|---------|--------------|---------|---------|
| `of=R` | Unary Relationship (nodes) | Constrain to nodes in `R` | `graph.degree(of=seed_nodes)` |
| `from_=R` | Unary Relationship (nodes) | Constrain source / first-argument nodes | `graph.reachable(from_=seed_nodes)` |
| `to=R` | Unary Relationship (nodes) | Constrain destination / second-argument nodes | `graph.reachable(to=target_nodes)` |
| `from_=R1, to=R2` | Two unary Relationships | Separately constrain both axes | `graph.distance(from_=sources, to=targets)` |
| `between=R` | Binary Relationship (node pairs) | Jointly constrain to specific node pairs | `graph.distance(between=node_pairs)` |
| `full=True` | Boolean | Override guard; compute full relationship | `graph.jaccard_similarity(full=True)` |

## Example: constrained similarity

```python
# Define the nodes of interest
seeds = model.Relationship(f"{graph.Node} is a seed node")
model.where(...).define(seeds(graph.Node))

# Compute similarity only from seed nodes to all other nodes — not all O(n^2) pairs
similarity_relationship = graph.jaccard_similarity(from_=seeds)
```
