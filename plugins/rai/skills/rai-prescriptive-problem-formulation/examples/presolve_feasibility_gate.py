# Pattern: pre-solve gate via aggregation queries — trivial-solution detection
# (row-count of forcing-binding entities) + per-scope feasibility precheck
# (aggregate lower-bound vs upper-bound at the constraint's natural scope).
# Key ideas: aggs.count() and aggs.sum().per() push aggregation into the model
# layer, so the gate runs against source-table-backed data (e.g., Snowflake)
# without pulling rows. Disaggregation by the binding key catches per-slice
# infeasibility that aggregate totals would mask.

from relationalai.semantics import Float, Integer, Model, String, distinct
from relationalai.semantics.std import aggregates as aggs

model = Model("presolve_feasibility_gate")

# --- Ontology: Need (forcing side) and Resource (capacity side). Shared
#     'kind' is the natural disaggregation level when sourcing matches by kind.
Need = model.Concept("Need", identify_by={"id": Integer})
Need.qty = model.Property(f"{Need} requires {Float:qty}")
Need.kind = model.Property(f"{Need} has {String:kind}")

Resource = model.Concept("Resource", identify_by={"id": Integer})
Resource.available = model.Property(f"{Resource} has {Float:available}")
Resource.kind = model.Property(f"{Resource} has {String:kind}")

# --- Inline data: per-kind shortage (kind A) hides inside aggregate totals.
model.define(
    Need.new(id=1, qty=80.0, kind="A"),
    Need.new(id=2, qty=80.0, kind="A"),
    Need.new(id=3, qty=10.0, kind="B"),
    Resource.new(id=10, available=20.0, kind="A"),   # A supply 20  vs A demand 160 — short
    Resource.new(id=11, available=200.0, kind="B"),  # B supply 200 vs B demand 10  — surplus
)
# Globally: 170 demand vs 220 supply (looks fine). Per-kind: A short by 140.

# ════════════════════════════════════════════════════════════════════════
# GATE 1 — Trivial-solution check (row-count of forcing-binding entities)
# ════════════════════════════════════════════════════════════════════════
# Substitute every decision variable with its objective-preferred bound (zero
# for minimize). For each forcing constraint, count rows where it binds. A
# forcing constraint Σ x.per(Need) >= Need.qty binds for rows where Need.qty>0.
binding = model.select(
    aggs.count(Need).where(Need.qty > 0).alias("forcing_binding_rows")
).to_df()
print(f"[Gate 1] Forcing-binding Need rows: {binding.iloc[0, 0]}")
# 0  → forcing vacuous, zero is feasible/optimal → DO NOT PRESENT
# >0 → forcing has bite, trivial-solution risk cleared

# ════════════════════════════════════════════════════════════════════════
# GATE 2 — Per-scope feasibility precheck (natural disaggregation level)
# ════════════════════════════════════════════════════════════════════════
# Aggregate lower-bound (forcing) and upper-bound (capacity) sides at the
# binding scope. Per-kind here; global totals would mask per-kind shortage.
demand = model.select(
    distinct(
        Need.kind.alias("kind"),
        aggs.sum(Need.qty).per(Need.kind).alias("total_demand"),
    )
).to_df()
supply = model.select(
    distinct(
        Resource.kind.alias("kind"),
        aggs.sum(Resource.available).per(Resource.kind).alias("total_supply"),
    )
).to_df()

report = demand.merge(supply, on="kind", how="outer").fillna(0.0)
report["status"] = [
    "OK" if s >= d else f"INFEASIBLE (short {d - s:g})"
    for d, s in zip(report["total_demand"], report["total_supply"])
]
print("[Gate 2] Per-kind feasibility:")
print(report.to_string(index=False))
# Any INFEASIBLE row → surface to user with row-count evidence; do not solve
# until the user resolves the slice (relax filter, allow partial coverage,
# adjust scope, or confirm intentional shortfall).
