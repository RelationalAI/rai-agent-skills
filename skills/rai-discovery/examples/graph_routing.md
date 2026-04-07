# Graph Routing Examples

Discovery-to-routing walkthroughs for graph reasoner questions. Each example shows: question → ontology signal → reasoner classification → implementation hint → modeling needs → handoff.

---

## "Which warehouses are most critical to supply chain resilience?"

### Ontology signals
- `Site` concept with `Operation` linking `source_site` → `output_site` → network topology
- `Operation.capacity_per_day` → weighted edges available
- Multiple site types (FACTORY, WAREHOUSE, DISTRIBUTION_CENTER) → heterogeneous network

### Reasoner classification: Graph (centrality)
- "Most critical" + network topology → centrality analysis
- NOT prescriptive — question is about understanding structure, not making decisions

### Implementation hint
```json
{"algorithm": "eigenvector_centrality", "graph_construction": {"node_concept": "Site",
  "directed": false, "weighted": true,
  "edge_definition": "Operation linking source_site to output_site, weight=shipment_count"},
 "output_binding": "(node, centrality_score)"}
```

### Modeling needs (→ rai-ontology-design)
- Graph construction: undirected `SiteDependencyGraph` with Site as nodes, Operation as edges
- Derived properties: `count_is_source` / `count_is_destination` for edge weights
- PyRel: `Graph(model, directed=False, weighted=True, node_concept=Site)`

### Reasoner handoff (→ graph workflow)
- `SiteDependencyGraph.eigenvector_centrality()` → returns `(site, centrality_score)`
- Filter non-relevant site types (STORE, OFFICE)
- Output: `Site.centrality_score` available for downstream prescriptive use (e.g., weight allocation by warehouse importance)

### Reference
`hero-user-journey/src/hero_user_journey/queries/q11_critical_warehouse_centrality.py`

---

## "Which suppliers do high-value customers depend upon?"

### Ontology signals
- `Business` concept with `ships_to` relationship (Business → Business) → directed dependency chain
- `Business.is_high_value_customer` derived property → target filter available
- 4-tier supply chain (Supplier → Manufacturer → Warehouse → Customer) → multi-hop reachability needed

### Reasoner classification: Graph (reachability, upstream)
- "Depend upon" + directed relationships → upstream reachability
- Multi-hop (not just direct suppliers) → graph traversal, not SQL join
- NOT predictive — question is about current structure, not future outcomes

### Implementation hint
```json
{"algorithm": "reachable", "graph_construction": {"node_concept": "Business",
  "directed": true, "weighted": false,
  "edge_definition": "Business.ships_to relationship"},
 "target_filter": "Business.is_high_value_customer",
 "output_binding": "(supplier, customer) reachable pairs"}
```

### Modeling needs (→ rai-ontology-design)
- Graph construction: directed `BusinessGraph` with Business as nodes, `ships_to` as edges
- Derived relationship: `Business.ships_to` from Shipment (supplier_business → customer_business)
- Target concept: `is_high_value_customer` filter (TYPE='BUYER' AND value_tier='HIGH')
- PyRel: `Graph(model, directed=True, weighted=False, node_concept=Business)`

### Reasoner handoff (→ graph workflow)
- Define target: `model.Relationship("Target Customer")` filtered to high-value
- `BusinessGraph.reachable(to=target_customer)` → returns `(source, target)` pairs
- Filter `source.type == "SUPPLIER"` for upstream suppliers only
- Output: per-customer supplier dependency list with reliability scores

### Reference
`hero-user-journey/src/hero_user_journey/queries/q5_high_value_customer_dependency.py`

---

## "If WaferTech Taiwan goes offline, which products and customers are impacted?"

### Ontology signals
- Same directed `BusinessGraph` as Q5 (Business → Business via `ships_to`)
- Parameterized by supplier name → impact analysis for a specific entity
- SKU and Shipment concepts with quantity data → can quantify impact

### Reasoner classification: Graph (reachability, downstream)
- "Goes offline" + "what's affected" → downstream reachability from a specific node
- Same graph as Q5, but traversal direction is reversed (`from_=` instead of `to=`)
- Impact quantification (quantity at risk) requires joining graph results back to Shipment/SKU data

### Implementation hint
```json
{"algorithm": "reachable", "graph_construction": {"node_concept": "Business",
  "directed": true, "weighted": false,
  "edge_definition": "Business.ships_to relationship"},
 "target_filter": "Business.name == 'WaferTech Taiwan' (parameterized)",
 "output_binding": "(source_supplier, affected_customer) reachable pairs"}
```

### Modeling needs (→ rai-ontology-design)
- Same `BusinessGraph` as upstream reachability — no additional graph construction needed
- Join path to SKU: `customer.receives_shipment.SKU` for product impact
- Join path to quantities: `Shipment.quantity` for volume at risk

### Reasoner handoff (→ graph workflow)
- Define target: `model.Relationship("Target Supplier")` filtered by name
- `BusinessGraph.reachable(from_=target_supplier)` → returns all downstream entities
- Join to Customer and SKU concepts for impact quantification
- Output: affected customers with products at risk and quantity exposure

### Cumulative discovery note
This question pairs naturally with prescriptive: "Given the impact of WaferTech going offline, how should we re-source components to minimize cost?" (graph → prescriptive chain). The reachability output identifies which alternatives are available.

### Reference
`hero-user-journey/src/hero_user_journey/queries/q6_at_risk_customers_skus.py`
