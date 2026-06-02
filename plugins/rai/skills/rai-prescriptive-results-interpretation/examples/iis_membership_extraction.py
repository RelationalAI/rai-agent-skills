# Pattern: IIS-membership extraction — localize an infeasibility with solve(conflict=True)
# and read the conflict members (constraints AND variable bounds) joined to their entities by key.
# Key ideas: conflict=True needs NO objective; conflict_status gates the read; in_conflict /
# upper_in_conflict are bare predicates used in where(); naming the constraint family per
# instance makes the entity back-pointer (floor.activity) usable for the join.
# Constraints kept to >= / <= families (the tested shape) — not equality.

from relationalai.semantics import Float, Model, String
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("iis_membership_extraction")

# --- Ontology ---
Activity = model.Concept("Activity", identify_by={"name": String})
Activity.min_required = model.Property(
    f"{Activity} requires at least {Float:min_required}"
)
Activity.max_output = model.Property(f"{Activity} caps output at {Float:max_output}")
Activity.level = model.Property(f"{Activity} level is {Float:x}")

# --- Sample data ---
# Activity "C" is engineered infeasible: its floor (>= 10) exceeds its ceiling (<= 4).
activity_data = model.data(
    [
        {"name": "A", "min_required": 1.0, "max_output": 5.0},
        {"name": "B", "min_required": 2.0, "max_output": 6.0},
        {"name": "C", "min_required": 10.0, "max_output": 4.0},
    ]
)
model.define(Activity.new(activity_data.to_schema()))

# --- Formulation (pure feasibility — no objective) ---
problem = Problem(model, Float)

# The variable's upper bound is the per-activity ceiling. Back-pointer acts.activity.
acts = problem.solve_for(
    Activity.level, name=Activity.name, lower=0, upper=Activity.max_output
)

# Floor FAMILY: a >= constraint per Activity, each instance named distinctly so the
# entity back-pointer (floor.activity) is usable for the key-join below.
floor = problem.satisfy(
    model.require(Activity.level >= Activity.min_required),
    name=["floor", Activity.name],
)

# conflict=True needs no objective — it diagnoses infeasibility, not optimality.
problem.solve("highs", conflict=True)
si = problem.solve_info()
print("status:", si.termination_status, "| conflict_status:", si.conflict_status)

if si.conflict_status == "CONFLICT_FOUND":
    # Constraints in the conflict, joined to their Activity by key:
    print("\n-- floor constraints in the conflict --")
    model.select(
        floor.activity.name.alias("activity"),
        floor.activity.min_required.alias("min_required"),
    ).where(floor.in_conflict).inspect()

    # Variable bounds in the conflict (bare predicate), joined to their Activity by key:
    print("\n-- variable upper bounds in the conflict --")
    model.select(
        acts.activity.name.alias("activity"),
        acts.activity.max_output.alias("max_output"),
    ).where(acts.upper_in_conflict).inspect()

    # Relaxing one member resolves THIS conflict; re-solve to confirm no others remain.
elif si.conflict_status == "NOT_SUPPORTED":
    print(
        "solver has no IIS support — fall back to bisection (omit one satisfy at a time)"
    )
elif si.conflict_status == "FAILED":
    print("conflict computation failed:", si.conflict_message)
