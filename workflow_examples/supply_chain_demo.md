# Runbook: Supply Chain

Live demo building a multi-reasoner analytical pipeline from raw Snowflake tables to optimized allocation with scenario analysis.

---

## Pre-Demo Setup

- [ ] Supply chain dataset loaded in Snowflake (`SUPPLY_CHAIN.MVD2` — 8 tables)
- [ ] `raiconfig.yaml` pointed at the target Snowflake account
- [ ] Claude Code open in a clean folder with RAI skills available

Pre-run step 1 before recording. Video starts with results on screen.

---

## Workflow

Steps are sequential — each depends on prior steps. Steps without a skill are presentation-only.

| # | Step | Skill | Prompt | Expected Output |
|---|------|-------|--------|-----------------|
| 1 | Connect (pre-run) | — | "What data is in SUPPLY_CHAIN.MVD2 tables in the RAI_PROD_PM Snowflake account?" | 8 tables: site, business, operation, sku, demand, shipment, delay_prediction, plus inventory in ENRICHMENT. |
| 2 | Ontology | `/rai-build-starter-ontology` | "Build an ontology on this data in a single file" | 9 concepts (Site, Business, Operation, SKU, Demand, Shipment, DelayPrediction + derived relationships). 31 sites, 32 businesses, ~70 operations, 10 SKUs, 20 demand orders. |
| 3 | Discover | `/rai-discovery` | "What questions can I answer with this ontology?" | Network criticality (graph), supplier risk classification (rules), cost-optimized allocation (prescriptive), scenario stress-testing. |
| 4 | Explore: delivery performance | `/rai-querying` | "What's our on-time delivery rate by region and quarter? Which suppliers have the worst track record?" | 37/262 shipments late (14.1%). By origin region: AMERICAS 19.0%, EMEA 18.8%, APAC 10.3%. Q4-2024 worst quarter (25.0% late). Worst suppliers: West Coast DC (7 late), East Coast DC (5), TechAssembly Co (4). |
| 5 | Explore: demand exposure | `/rai-querying` | "Which SKUs have the most open HIGH-priority demand, and which buyers are waiting?" | 90 HIGH-priority demands. Top SKUs by volume: Silicon Wafer 300mm (21,876 units), Display Glass Panel (7,872), NAND Flash Memory Die (7,292). Top buyers: ChipTech Industries (29,168 units), TechAssembly Co (16,407), DisplayCorp (7,872). Finished goods (ProPhone X1, ProTab T1) have smaller but high-stakes orders from MegaCorp and TechGiant. |
| 6 | Explore: network shape | `/rai-querying` | "How many operations connect each region, and what's the total capacity flowing between regions?" | 47 operations. Intra-APAC dominates (18 ops, 62,400 units/day). Intra-EMEA: 13 ops, 10,610 units/day. Intra-Americas: 10 ops, 3,040 units/day. Only 6 cross-region operations (2,500 units/day total) — the network is regionally concentrated with narrow inter-region links. |
| 7 | Graph: centrality | `/rai-graph-analysis` | "Which sites are most critical to the network?" | 2 connected components. Top critical: S004 TechAssembly Factory (APAC, 0.50), S006 West Coast DC (0.39), S003 PowerCell Facility (0.37). |
| 8 | Graph: supplier impact | `/rai-graph-analysis` | "If PowerCell (B003) goes offline, which downstream buyers and products are impacted?" | Downstream reachability on the Business-to-Business shipment graph. Traces B003 through component manufacturers, assemblers, and warehouses to end buyers. High-value buyers (MegaCorp, TechGiant) exposed via transitive dependencies. SKU004 (ProPhone X1) and SKU005 (ProTab T1) supply chains at risk — battery pack input from PowerCell feeds both finished goods at TechAssembly. |
| 9 | Rules | `/rai-rules-authoring` | "Which suppliers should we avoid?" | 37/262 shipments late (14%). B003 PowerCell Ltd = "watch" (reliability 0.81). 9 escalated HIGH-priority demands. |
| 10 | Optimize | `/rai-prescriptive-problem-formulation` | "What's the cheapest way to allocate inventory across the network to meet all demand while reducing reliance on risky suppliers?" | Baseline: OPTIMAL, cost $1,865, 8 active flows, all demand satisfied. |
| 11 | Scenario | `/rai-prescriptive-results-interpretation` | "What if S004 TechAssembly goes offline?" | S004 offline: $3,515 (+88.5%), flow reroutes. Watch->Avoid: $1,865 (0.0% change). |
| 12 | Visualize | — | "Show me the network with flows and risks using ascii" | ASCII network with flow volumes, flagged suppliers, disruption impact. |

---

## Data Reference

**Sites:** 31 total — factories, distribution centers, offices, stores across APAC and Americas.

| Site | Name | Type | Region | Centrality |
|------|------|------|--------|------------|
| S004 | TechAssembly Factory | Factory | APAC | 0.50 (highest) |
| S006 | West Coast DC | Distribution Center | Americas | 0.39 |
| S003 | PowerCell Facility | Factory | APAC | 0.37 |

**Key suppliers:**

| Business | Name | Reliability | Risk Class |
|----------|------|-------------|------------|
| B003 | PowerCell Ltd | 0.81 | watch |
| B005 | GlobalBuild Inc | 0.85 | reliable |
| B001 | ChipTech Industries | 0.95 | reliable |

**Shipments:** 262 historical, 37 late (14%). B006: 7 late (worst).

**Optimization baselines:**

| Scenario | Cost | Change | Demand Met |
|----------|------|--------|------------|
| Baseline | $1,865 | — | All |
| S004 offline | $3,515 | +88.5% | All |
| Watch->Avoid | $1,865 | 0.0% | All |
