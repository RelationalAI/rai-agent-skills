<!-- TOC -->
- [Construction Patterns Overview](#construction-patterns-overview)
- [Entity-Level Directed Graph](#entity-level-directed-graph)
- [Infrastructure-Level Undirected Weighted Graph](#infrastructure-level-undirected-weighted-graph)
- [Co-Occurrence / Shared-Attribute Graph](#co-occurrence--shared-attribute-graph)
- [Hierarchy / DAG](#hierarchy--dag)
- [Self-Referencing Graph](#self-referencing-graph)
- [Filtered Graphs](#filtered-graphs)
- [Multi-Graph from Same Ontology](#multi-graph-from-same-ontology)
- [Edge Weight Construction](#edge-weight-construction)
- [Pre-Construction Validation](#pre-construction-validation)
<!-- /TOC -->

## Construction Patterns Overview

Graph construction maps ontology structure to a `Graph` instance. The question determines which construction to use — the same ontology can yield multiple valid graphs.

| Pattern | Nodes | Edges | Typical Algorithms |
|---------|-------|-------|-------------------|
| Entity-level directed | Business entities | Direct relationships | PageRank, reachability |
| Infrastructure undirected weighted | Locations/sites | Intermediary concepts | Eigenvector centrality, WCC, bridges |
| Co-occurrence / shared-attribute | Entities | Shared membership/purchases | Louvain, community detection |
| Hierarchy / DAG | Hierarchical entities | Parent-child relationships | Reachability, distance |
| Self-referencing | Single concept type | Instance-to-instance references | Dependency analysis, BOM traversal |

---

## Entity-Level Directed Graph

**Ontology signal:** Direct relationship between instances of the same concept type, or between two entity concepts with inherent directionality.

**Same-concept edges:**

```python
# Business → Business via ships_to
graph = Graph(model, directed=True, weighted=False, node_concept=Business)

b1, b2 = Business.ref(), Business.ref()
model.where(b1.ships_to(b2)).define(
    graph.Edge.new(src=b1, dst=b2)
)
```

**Cross-concept edges:**

```python
# Supplier → Manufacturer (directed supply relationship)
graph = Graph(model, directed=True, weighted=False)

s, m = Supplier.ref(), Manufacturer.ref()
model.where(s.supplies(m)).define(
    graph.Edge.new(src=s, dst=m)
)
```

**Weighted variant:**

```python
# Business → Business with shipment volume as weight
graph = Graph(model, directed=True, weighted=True, node_concept=Business, aggregator="sum")

b1, b2 = Business.ref(), Business.ref()
model.where(b1.ships_to(b2)).define(
    graph.Edge.new(src=b1, dst=b2, weight=b1.shipment_volume)
)
```

---

## Infrastructure-Level Undirected Weighted Graph

**Ontology signal:** An intermediary concept (Operation, Route, Link, Connection) that connects two instances of a node concept via source/destination properties.

```python
# Sites connected via Operations
graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

op = Operation.ref()
site1, site2 = Site.ref(), Site.ref()
model.where(
    op.source_site(site1),
    op.output_site(site2),
).define(
    graph.Edge.new(src=site1, dst=site2, weight=op.shipment_count)
)
```

**Multiple intermediary concepts:**

If two different concepts connect the same node type (e.g., both `Shipment` and `Transfer` link `Warehouse` to `Warehouse`), define edges from both:

```python
# Edges from Shipments
ship = Shipment.ref()
model.where(ship.origin(w1 := Warehouse.ref()), ship.destination(w2 := Warehouse.ref())).define(
    graph.Edge.new(src=w1, dst=w2, weight=ship.volume)
)

# Edges from Transfers
xfer = Transfer.ref()
model.where(xfer.from_warehouse(w1 := Warehouse.ref()), xfer.to_warehouse(w2 := Warehouse.ref())).define(
    graph.Edge.new(src=w1, dst=w2, weight=xfer.quantity)
)
# aggregator="sum" combines weights from all sources
```

---

## Co-Occurrence / Shared-Attribute Graph

**Ontology signal:** Two entities share a common attribute via a bridge concept (orders for the same product, students in the same course, authors on the same paper).

```python
# Customers connected by shared product purchases
graph = Graph(model, directed=False, weighted=True, node_concept=Customer, aggregator="sum")

left_order, right_order = Order.ref(), Order.ref()
model.where(
    left_order.product == right_order.product,
    left_order.customer.id < right_order.customer.id,  # prevent duplicates + self-loops
).define(
    graph.Edge.new(
        src=left_order.customer,
        dst=right_order.customer,
        weight=1.0,
    )
)
```

**Critical: the `id <` guard** prevents:
- Self-loops (customer connected to themselves)
- Duplicate edges (A->B and B->A counted separately)

Without it, the graph has 2x the edges and self-loops that distort algorithms.

**Weighted co-occurrence:**

To weight by shared-attribute count (e.g., number of shared products), the `weight=1.0` per match combined with `aggregator="sum"` naturally produces this — each shared product adds 1.0 to the edge weight.

For weighted by value (e.g., total shared purchase amount):

```python
model.where(
    left_order.product == right_order.product,
    left_order.customer.id < right_order.customer.id,
).define(
    graph.Edge.new(
        src=left_order.customer,
        dst=right_order.customer,
        weight=left_order.amount + right_order.amount,
    )
)
```

---

## Hierarchy / DAG

**Ontology signal:** Parent-child relationship — organizational structure, category taxonomy, BOM.

```python
# Category tree
graph = Graph(model, directed=True, weighted=False, node_concept=Category)

parent, child = Category.ref(), Category.ref()
model.where(child.parent(parent)).define(
    graph.Edge.new(src=parent, dst=child)
)
```

**Direction convention:** Edge from parent to child (top-down). This makes `reachable(from_=root)` return all descendants, and `reachable(to=leaf)` returns all ancestors.

**Multi-level hierarchy with intermediate concepts:**

```python
# Division → Department → Team (three concepts)
org_graph = Graph(model, directed=True, weighted=False)

model.where(Department.division(div := Division.ref())).define(
    graph.Edge.new(src=div, dst=Department)
)
model.where(Team.department(dept := Department.ref())).define(
    graph.Edge.new(src=dept, dst=Team)
)
```

---

## Self-Referencing Graph

**Ontology signal:** A concept with a relationship to itself (component assemblies, recursive dependencies, social follows).

```python
# Component → Component (BOM structure)
graph = Graph(model, directed=True, weighted=False, node_concept=Component)

parent, child = Component.ref(), Component.ref()
model.where(parent.subcomponent(child)).define(
    graph.Edge.new(src=parent, dst=child)
)
```

**Cycle handling:** Self-referencing graphs may have cycles. Reachability handles cycles correctly (terminates). Distance on cyclic graphs computes shortest paths.

---

## Edge from Existing Concept (`edge_concept`)

**Ontology signal:** Each interaction is already modeled as its own concept (Transaction, Payment, Shipment) with source/destination relationships and optional weight properties.

Instead of manually defining edges with `Edge.new()`, use `edge_concept` to derive edges automatically from an existing concept:

```python
from relationalai.semantics.std import floats

graph = Graph(
    model,
    directed=True,
    weighted=True,
    node_concept=Account,
    edge_concept=Transaction,
    edge_src_relationship=Transaction.payer,
    edge_dst_relationship=Transaction.payee,
    edge_weight_relationship=Transaction.amount,  # Required when weighted=True
)
# Every Transaction instance automatically becomes an edge — no Edge.new() needed
```

**When to use:** When your model already has a concept representing each interaction. This avoids manual edge definition and ensures every instance of the concept is included.

**Requirements:**
- Must pass `node_concept` when using `edge_concept`
- Must pass all three: `edge_concept`, `edge_src_relationship`, `edge_dst_relationship`
- Add `edge_weight_relationship` when `weighted=True`
- **Weights must be floats** — use `floats.float()` to cast from Integer/Number types

**You can still add additional edges** with `Edge.new()` alongside `edge_concept`:

```python
# Additional edges beyond what edge_concept provides
model.define(graph.Edge.new(src=account1, dst=account2))
```

---

## Filtered Graphs

Build graphs from subsets of the ontology by adding conditions to edge definitions.

**Filter by edge property:**

```python
# Only include operations above a threshold
graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")

op = Operation.ref()
model.where(
    op.source_site(site1 := Site.ref()),
    op.output_site(site2 := Site.ref()),
    op.shipment_count > 100,  # filter: only significant operations
).define(
    graph.Edge.new(src=site1, dst=site2, weight=op.shipment_count)
)
```

**Filter by node property:**

```python
# Only include active sites
model.where(
    op.source_site(site1 := Site.ref()),
    op.output_site(site2 := Site.ref()),
    site1.status == "active",
    site2.status == "active",
).define(
    graph.Edge.new(src=site1, dst=site2, weight=op.shipment_count)
)
```

**Filter by relationship subtype:**

```python
# Only include "primary" supplier relationships
model.where(
    b1.ships_to(b2 := Business.ref()),
    b1.supplier_type == "primary",
).define(
    graph.Edge.new(src=b1, dst=b2)
)
```

---

## Multi-Graph from Same Ontology

A single model can support multiple independent graph analyses. Each `Graph()` instance is separate.

```python
# Graph 1: Directed business dependency (for PageRank, reachability)
business_graph = Graph(model, directed=True, node_concept=Business)
# ... define business edges

# Graph 2: Undirected site infrastructure (for centrality, community)
site_graph = Graph(model, directed=False, weighted=True, node_concept=Site, aggregator="sum")
# ... define site edges

# Graph 3: Customer co-purchase (for community detection)
customer_graph = Graph(model, directed=False, weighted=True, node_concept=Customer, aggregator="sum")
# ... define co-purchase edges

# Each graph's algorithms run independently
business_graph.Node.pagerank_score = business_graph.pagerank()
site_graph.Node.centrality_score = site_graph.eigenvector_centrality()
customer_graph.Node.community_label = customer_graph.louvain()
```

**When to use multiple graphs:** When different questions require different perspectives on the same data. Supply chain analysis might need both a directed flow graph (reachability) and an undirected connectivity graph (centrality) on the same network.

---

## Edge Weight Construction

### From a property on the intermediary concept

```python
# Weight = shipment volume
graph.Edge.new(src=site1, dst=site2, weight=op.shipment_volume)
```

### From a computed expression

```python
# Weight = cost per unit * quantity
graph.Edge.new(src=site1, dst=site2, weight=op.cost_per_unit * op.quantity)
```

### Constant weight (unweighted semantics on a weighted graph)

```python
# All edges equal weight — effectively unweighted
graph.Edge.new(src=site1, dst=site2, weight=1.0)
```

### Inverted weight (for "closer = stronger" semantics)

```python
# Weight = 1/distance — nearby nodes get higher edge weight
graph.Edge.new(src=site1, dst=site2, weight=1.0 / op.distance)
```

**Warning:** Ensure no zero-distance values to avoid division by zero.

---

## Pre-Construction Validation

Before running algorithms, verify the graph is well-formed using the built-in statistics methods:

### Check node and edge counts

```python
# Quick validation — inspect prints results directly
graph.num_nodes().inspect()  # Should be > 0
graph.num_edges().inspect()  # Should be > 0

# Or extract as DataFrame for programmatic checks
node_count = graph.num_nodes().to_df().iloc[0, 0]
edge_count = graph.num_edges().to_df().iloc[0, 0]
print(f"Graph has {node_count} nodes and {edge_count} edges")
```

**If `num_edges` is 0:** No edges were defined. Check that:
- `define()` was called for `Edge.new()` declarations
- Conditional `.where()` filters aren't filtering out all edges
- If using `edge_concept`, instances of that concept have been defined

**If `num_nodes` is 0:** No nodes were defined. Check that:
- Edge definitions connect to valid concept instances
- If using `node_concept`, instances of that concept have been defined

### Verify connectivity

```python
graph.is_connected().inspect()
# If False: some algorithms may produce per-component results
# WCC can identify the components
```

