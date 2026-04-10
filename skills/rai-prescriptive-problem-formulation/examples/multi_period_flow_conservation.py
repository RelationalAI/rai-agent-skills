# Pattern: multi-period flow conservation with time-indexed multiarity variables
# Key ideas: std.common.range() creates integer periods; multiarity properties bind
# (entity, time, value) triples; model.where() with adjacent-period refs (t, t-1)
# gives a single declarative balance constraint; model.union() combines per-entity
# costs from different concepts into one objective.

from relationalai.semantics import Float, Integer, Model, String, std, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("multi_period_flow_conservation")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Site = Concept("Site", identify_by={"id": Integer})
Site.name = Property(f"{Site} has {String:name}")

SKU = Concept("SKU", identify_by={"id": Integer})
SKU.name = Property(f"{SKU} has {String:name}")

# Junction: per-(site, sku) production capacity and initial stock
SiteSKU = Concept("SiteSKU", identify_by={"site_id": Integer, "sku_id": Integer})
SiteSKU.max_prod = Property(f"{SiteSKU} has {Float:max_prod}")
SiteSKU.prod_cost = Property(f"{SiteSKU} has {Float:prod_cost}")
SiteSKU.hold_cost = Property(f"{SiteSKU} has {Float:hold_cost}")
SiteSKU.init_inv = Property(f"{SiteSKU} has {Float:init_inv}")

# Weekly demand loaded as a flat concept (pre-aggregated from date-filtered orders)
WeeklyDemand = Concept("WeeklyDemand", identify_by={"site_id": Integer, "sku_id": Integer, "week": Integer})
WeeklyDemand.qty = Property(f"{WeeklyDemand} has {Float:qty}")

# --- Inline data ---
site_data = model.data([(1, "Plant_A"), (2, "Plant_B")], columns=["id", "name"])
model.define(Site.new(site_data.to_schema()))

sku_data = model.data([(1, "Widget"), (2, "Gadget")], columns=["id", "name"])
model.define(SKU.new(sku_data.to_schema()))

ss_data = model.data(
    [
        (1, 1, 50.0, 5.0, 0.5, 20.0),
        (1, 2, 40.0, 8.0, 0.6, 15.0),
        (2, 1, 60.0, 4.0, 0.4, 10.0),
    ],
    columns=["site_id", "sku_id", "max_prod", "prod_cost", "hold_cost", "init_inv"],
)
model.define(SiteSKU.new(ss_data.to_schema()))

# Demand for a few weeks (not every week needs demand; weeks without demand have zero demand implicitly)
wd_rows = []
for site_id, sku_id, demands in [
    (1, 1, {1: 10.0, 3: 15.0, 5: 20.0, 8: 25.0, 11: 10.0}),
    (1, 2, {2: 12.0, 4: 18.0, 7: 10.0, 10: 14.0, 13: 8.0}),
    (2, 1, {1: 8.0, 4: 12.0, 6: 15.0, 9: 20.0, 12: 10.0}),
]:
    for wk, qty in demands.items():
        wd_rows.append((site_id, sku_id, wk, qty))
wd_data = model.data(wd_rows, columns=["site_id", "sku_id", "week", "qty"])
model.define(WeeklyDemand.new(wd_data.to_schema()))

# --- Time periods via std.common.range() ---
num_weeks = 13
weeks = std.common.range(1, num_weeks + 1)
t = Integer.ref()

# --- Decision variables (multiarity: time-indexed) ---
SiteSKU.x_prod = Property(f"{SiteSKU} in week {Integer:t} produces {Float:production}")
SiteSKU.x_inv = Property(f"{SiteSKU} at end of week {Integer:t} has inventory {Float:inv}")
x_prod, x_inv = Float.ref(), Float.ref()

problem = Problem(model, Float)
x_prod_var = problem.solve_for(
    SiteSKU.x_prod(t, x_prod),
    type="cont",
    lower=0,
    upper=SiteSKU.max_prod,
    name=["prod", SiteSKU.site_id, SiteSKU.sku_id, t],
    where=[t == weeks],
)
x_inv_var = problem.solve_for(
    SiteSKU.x_inv(t, x_inv),
    type="cont",
    lower=0,
    name=["inv", SiteSKU.site_id, SiteSKU.sku_id, t],
    where=[t == std.common.range(0, num_weeks + 1)],
)  # week 0 = initial

# --- Initial condition: inventory at week 0 = starting stock ---
x_inv0 = Float.ref()
problem.satisfy(model.where(SiteSKU.x_inv(0, x_inv0)).require(x_inv0 == SiteSKU.init_inv))

# --- Flow conservation: inv[t] = inv[t-1] + produced[t] - demand[t] ---
x_inv_prev, x_inv_curr = Float.ref(), Float.ref()
problem.satisfy(
    model.where(
        SiteSKU.x_inv(t, x_inv_curr),
        SiteSKU.x_inv(t - 1, x_inv_prev),
        SiteSKU.x_prod(t, x_prod),
        WeeklyDemand.site_id == SiteSKU.site_id,
        WeeklyDemand.sku_id == SiteSKU.sku_id,
        WeeklyDemand.week == t,
        t >= 1,
    ).require(x_inv_curr == x_inv_prev + x_prod - WeeklyDemand.qty)
)

# --- Objective: minimize production + holding cost via model.union() ---
prod_cost_term = SiteSKU.prod_cost * sum(x_prod).per(SiteSKU).where(SiteSKU.x_prod(t, x_prod))
hold_cost_term = SiteSKU.hold_cost * sum(x_inv).per(SiteSKU).where(SiteSKU.x_inv(t, x_inv), t >= 1)
problem.minimize(sum(model.union(prod_cost_term, hold_cost_term)))

problem.solve("highs", time_limit_sec=60)
