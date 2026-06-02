# Pattern: marginals-by-key extraction — read LP/QP duals off the returned objects and
# join each to its entity through the back-pointer key (never by parsing a name string).
# Key ideas: solve(sensitivity=True) populates reduced_cost / shadow_price / basis_status;
# they read straight off the solve_for() / satisfy() returns like .name (single-valued);
# naming each constraint-family instance distinctly (name=["cap", Resource.name]) makes the
# constraint's entity back-pointer (cap.resource) usable for the join.

from relationalai.semantics import Float, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("marginals_by_key_extraction")

# --- Ontology ---
Activity = model.Concept("Activity", identify_by={"name": String})
Activity.profit = model.Property(f"{Activity} has profit {Float:profit}")
Activity.level = model.Property(f"{Activity} level is {Float:x}")

Resource = model.Concept("Resource", identify_by={"name": String})
Resource.capacity = model.Property(f"{Resource} has capacity {Float:capacity}")

# Usage is ternary (Activity x Resource -> rate); the value field must be LAST.
Activity.usage = model.Property(f"{Activity} uses {Resource} at rate {Float:rate}")

# --- Sample data ---
activity_data = model.data(
    [
        {"name": "A", "profit": 4.0},
        {"name": "B", "profit": 5.0},
    ]
)
model.define(Activity.new(activity_data.to_schema()))

resource_data = model.data(
    [
        {"name": "machine", "capacity": 40.0},
        {"name": "labor", "capacity": 30.0},
    ]
)
model.define(Resource.new(resource_data.to_schema()))

usage_raw = model.data(
    [
        {"activity": "A", "resource": "machine", "rate": 2.0},
        {"activity": "A", "resource": "labor", "rate": 1.0},
        {"activity": "B", "resource": "machine", "rate": 1.0},
        {"activity": "B", "resource": "labor", "rate": 2.0},
    ],
    columns=["activity", "resource", "rate"],
)
ResRef = Resource.ref()
model.where(
    Activity.name(usage_raw.activity),
    ResRef.name(usage_raw.resource),
).define(Activity.usage(ResRef, usage_raw.rate))

# --- Formulation ---
problem = Problem(model, Float)

# Continuous variable per Activity; back-pointer acts.activity (lowercased type name).
acts = problem.solve_for(Activity.level, name=Activity.name, lower=0)

# Per-Resource usage, grouped with .per(Resource).
rate = Float.ref()
usage = sum(rate * Activity.level).where(Activity.usage(Resource, rate)).per(Resource)

# Constraint FAMILY: one capacity limit per Resource, each instance named distinctly
# so the entity back-pointer (cap.resource) is usable for the key-join below.
cap = problem.satisfy(
    model.require(usage <= Resource.capacity), name=["cap", Resource.name]
)

# sensitivity=True requires an objective (duals are objective marginals).
problem.maximize(sum(Activity.profit * Activity.level))

# Request duals on the solve itself — a solve option, not a post-processing re-solve.
problem.solve("highs", sensitivity=True)
si = problem.solve_info()
print("status:", si.termination_status, "| sensitivity:", si.sensitivity)

if si.termination_status == "OPTIMAL":
    print(f"objective (total profit): {si.objective_value:.4f}")

    # reduced_cost / basis_status read straight off the variable, joined to Activity by key:
    print("\n-- activity marginals --")
    model.select(
        acts.activity.name.alias("activity"),
        acts.reduced_cost.alias("reduced_cost"),
        acts.basis_status.alias("basis_status"),
    ).inspect()

    # shadow_price read off the constraint family, joined to its Resource by key:
    print("\n-- resource shadow prices --")
    model.select(
        cap.resource.name.alias("resource"),
        cap.resource.capacity.alias("capacity"),
        cap.shadow_price.alias("shadow_price"),
    ).inspect()
