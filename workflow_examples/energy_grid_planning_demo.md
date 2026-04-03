# Runbook: Energy Grid Planning

An AI-assisted grid planner processes 10 hyperscaler interconnection requests against ERCOT's 12-substation Texas grid, chaining demand forecasting, structural vulnerability analysis, regulatory compliance, and investment optimization into a single decision pipeline.

---

## Pre-Demo Setup

- [ ] Energy dataset loaded in Snowflake (`ENERGY.PUBLIC` — 12 tables) or CSV fallback in `data/`
- [ ] `raiconfig.yaml` pointed at the target Snowflake account
- [ ] Claude Code open in a clean folder with RAI skills available
- [ ] Template file ready as fallback: `templates/v1/energy_grid_planning/energy_grid_planning.py`

---

## Workflow

Steps are sequential — each depends on prior steps. Steps without a skill are presentation-only.

| # | Step | Skill | Prompt | Expected Output |
|---|------|-------|--------|-----------------|
| 1 | Ontology | `/rai-build-starter-ontology` | "Connect to the ENERGY database in RAI_PROD_PM and build an ontology for grid infrastructure planning." | 13 concepts from 12 tables. 12 substations, 15 generators, 18 transmission lines, 10 DC requests (2,930 MW). |
| 2 | Visualize | — | "Show the ontology as an ASCII diagram." | Concept map with Substation as central hub — Generator, TransmissionLine, DataCenterRequest, SubstationUpgrade, DemandForecast all relate to it. |
| 3 | Discovery | `/rai-discovery` | "What questions can we answer with this ontology? We're evaluating data center interconnection requests." | 4 reasoning paths: demand forecasting (predictive), grid topology (graph), compliance (rules), investment optimization (prescriptive). |
| 4 | Explore: generation mix | `/rai-querying` | "What's our current generation mix by fuel type? How much renewable capacity do we have vs fossil?" | 15 generators, 8,135 MW total. Nuclear leads (2,560 MW, 31.5%), then gas (2,290 MW, 28.1%), wind (1,250 MW, 15.4%), coal (1,020 MW, 12.5%), solar (630 MW, 7.7%), battery (300 MW), hydro (85 MW). Renewable: 2,265 MW (28%). Key takeaway: only 28% renewable penetration — requests with 100% low-carbon mandates (Google, Crusoe) face a structural constraint. |
| 5 | Explore: capacity headroom | `/rai-querying` | "Which substations have the most and least spare capacity right now, before any new DC load?" | Tightest: Houston Ship Channel (69.4% utilized, 550 MW headroom), Austin Energy (68.9%, 280 MW), DFW (68.8%, 500 MW). Most spare: Midland-Permian (38.2%, 680 MW headroom), Lubbock (44.3%, 390 MW). DFW has only 500 MW headroom but 1,100 MW of DC requests stacked on it. |
| 6 | Explore: DC request landscape | `/rai-querying` | "Summarize the 10 DC requests — total MW per substation, revenue per MW, and low-carbon requirements." | 2,930 MW total, $528M/yr revenue across 6 substations. DFW most stacked (1,100 MW, 3 requests: Google $195K/MW, xAI $210K/MW, Lambda $150K/MW). xAI is highest revenue ($210K/MW/yr, $105M/yr total). Google and Crusoe require 100% low-carbon. Revenue concentration: top 3 substations (DFW, Houston, San Antonio) account for 78% of requested MW. |
| 7 | Predict | `/rai-querying` | "Which substations are losing headroom fastest? How does that affect data center approvals?" | DFW breaches: 1,700 MW predicted vs 1,600 MW capacity at 24 months (54.6% growth). 1,100 MW of requests stacked on it (Google 400, xAI 500, Lambda 200). |
| 8 | Graph: topology | `/rai-graph-analysis` | "Which data center requests target critical substations given grid topology, regions, and structural importance?" | 1 connected component. 3 regions (North Texas, West Texas, Gulf Coast). Top 3 critical: DFW, Houston, San Antonio. 7 of 10 requests target those 3. |
| 9 | Graph: N-1 contingency | `/rai-graph-analysis` | "Which transmission lines are single points of failure, and what's the worst-case load at risk from a single line failure?" | Bridge detection + N-1 screening on 12 substations, 20 transmission lines. Identifies bridge lines whose removal fragments the grid. Articulation substations (removal disconnects the grid) flagged. Congestion analysis: lines >80% utilization ranked by risk. Congested bridges (high utilization AND structural vulnerability) are highest-priority reinforcement targets for upgrade investment in Step 11. |
| 10 | Rules | `/rai-rules-authoring` | "Check each request against capacity (using predicted load), low-carbon mandate, and structural risk." | All 10 pass low-carbon. 2 compliant: Crusoe (Midland) and Oracle (Corpus Christi). 8 flagged on capacity + structural risk. |
| 11 | Optimize | `/rai-prescriptive-problem-formulation` | "Which data centers to approve and which upgrades to fund across 5 budget levels ($200M-$600M)? Maximize revenue given investment level scenarios and capacity, low carbon, and risk constraints." | Pareto frontier — see below. |
| 12 | Results | `/rai-prescriptive-results-interpretation` | "Show the investment frontier and explain tradeoffs — approved DCs, selected upgrades, MW connected, and revenue at each level." | Knee at $300M. Google and Lambda never approved (DFW full). |
| 13 | Dispatch | `/rai-prescriptive-problem-formulation` | "Given the $300M approved DCs, what's the optimal unit commitment schedule? Which generators run in each period to meet total load at minimum cost while respecting ramp rates and maintenance windows?" | Unit commitment across 24 hourly demand periods for 15 generators. Binary commit/startup decisions + continuous dispatch MW. Constraints: demand balance, min/max output, ramp rates, min up/down time, maintenance lockout. Objective: minimize startup + dispatch cost. Shows which generators cycle on/off, where reserve margins are thin, and the operational cost of serving the 1,500 MW approved DC load on top of existing demand. |

### Pareto Frontier (Steps 11–12)

| Budget | DCs | MW | Revenue/yr | Net Value |
|--------|-----|----|------------|-----------|
| $200M | 4 (Microsoft, CoreWeave, Crusoe, Oracle) | 1,000 | $174M | $165M |
| **$300M** | **5 (+xAI Colossus)** | **1,500** | **$279M** | **$264M** |
| $400M | 6 (+Meta) | 1,800 | $329M | $310M |
| $500M | 7 (+Amazon) | 2,080 | $376M | $355M |
| $600M | 8 (+Apple) | 2,330 | $420M | $395M |

**Knee: $300M** — xAI Colossus ($105M/yr) unlocks, $995K marginal/$M. Never approved: Google (400 MW), Lambda (200 MW) — DFW physically full.

---

## Data Reference

**Substations with DC requests:**

| Substation | Location | Capacity | DC Requests | DC MW |
|------------|----------|----------|-------------|-------|
| SUB-001 | Houston | 1,800 MW | Microsoft (350), Meta (300) | 650 MW |
| SUB-002 | DFW | 1,600 MW | Google (400), xAI (500), Lambda (200) | 1,100 MW |
| SUB-003 | San Antonio | 1,200 MW | Amazon (280), Apple (250) | 530 MW |
| SUB-004 | Austin | 900 MW | CoreWeave (320) | 320 MW |
| SUB-005 | Midland | 1,100 MW | Crusoe (180) | 180 MW |
| SUB-007 | Corpus Christi | 800 MW | Oracle (150) | 150 MW |

**ERCOT regions:** North Texas (DFW, Austin, Waco) | West Texas (Midland, Lubbock, El Paso, Amarillo, Abilene) | Gulf Coast (Houston, San Antonio, Corpus Christi, Brownsville)

**DFW breach:** 1,600 MW capacity, 1,700 MW predicted (24mo), 54.6% growth, 1,100 MW DC requests on top. Google and Lambda permanently infeasible.

**Upgrades:** 10 available, $630M total, 2,900 MW capacity.
