# Pattern: sub-concept predicate marker + solve_for(Sub.prop) — Rules→CSP scoping
"""
Patient cohort recruitment: select exactly K=5 patients from a pool of 10 to form a study cohort.
Decision is keyed by a sub-concept (EligiblePatient ⊂ Patient), not by every Patient — the solver
only declares decision variables for the rows the eligibility predicate admitted.

Demonstrates:
- Sub-concept predicate marker: EligiblePatient = model.Concept("EligiblePatient", extends=[Patient])
  populated via model.define(EligiblePatient(Patient)).where(<eligibility predicate>)
- A decision Property declared on the parent concept (Patient.is_in_cohort) — the property
  exists on every Patient declaratively, but solve_for keyed by the sub-concept only creates
  variables for the eligible rows
- The scoping is structural, not cosmetic: ineligible patients have no decision variable, so
  the cohort-size constraint cannot accidentally count them
- Pure-satisfaction MiniZinc-style: find K satisfying members; no objective

Triggering pattern: "select K of these that meet criteria," "form a cohort," "pick a subset
satisfying property X." Cleaner than a binary x_eligible flag per Patient when the candidate pool
is genuinely smaller than the parent concept — the Rules layer (the sub-concept's define rule)
shrinks the decision space before the CSP layer touches it.

Distilled from patient_cohort_recruitment.
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, count, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_subconcept_solve_for_{time.time_ns()}")

COHORT_SIZE = 5
MIN_SCORE = 60  # eligibility threshold

# --- Concept and inline data ---
Patient = model.Concept("Patient", identify_by={"id": Integer})
Patient.score = model.Property(f"{Patient} has {Integer:score}")
Patient.age = model.Property(f"{Patient} has {Integer:age}")

patient_data = pd.DataFrame(
    [
        (1, 80, 45),
        (2, 55, 50),
        (3, 90, 38),
        (4, 65, 60),
        (5, 70, 42),
        (6, 45, 28),
        (7, 75, 55),
        (8, 50, 33),
        (9, 88, 47),
        (10, 72, 52),
    ],
    columns=["id", "score", "age"],
)
model.define(Patient.new(model.data(patient_data).to_schema()))

# --- Sub-concept: eligibility marker, populated by the Rules layer ---
EligiblePatient = model.Concept("EligiblePatient", extends=[Patient])
model.define(EligiblePatient(Patient)).where(Patient.score >= MIN_SCORE)

# --- Decision property: declared on the parent concept, scoped to the sub-concept via solve_for ---
Patient.is_in_cohort = model.Property(f"{Patient} is in cohort if {Integer:in_cohort}")

problem = Problem(model, Integer)
problem.solve_for(
    EligiblePatient.is_in_cohort,
    type="bin",
    name=["cohort", EligiblePatient.id],
)

# --- Constraint: exactly COHORT_SIZE eligible patients in the cohort ---
problem.satisfy(model.require(sum(EligiblePatient.is_in_cohort) == COHORT_SIZE))

# --- Constraint: at least 3 cohort members have age >= 40 (balance requirement) ---
problem.satisfy(
    model.require(
        count(
            EligiblePatient,
            (EligiblePatient.is_in_cohort == 1) & (EligiblePatient.age >= 40),
        )
        >= 3
    )
)

# --- Pure satisfaction: no objective ---
problem.solve("minizinc", time_limit_sec=30)
si = problem.solve_info()
si.display()

if si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT", "LOCALLY_SOLVED"):
    print(f"\nSelected cohort of {COHORT_SIZE}:")
    model.select(
        EligiblePatient.id,
        EligiblePatient.score,
        EligiblePatient.age,
        EligiblePatient.is_in_cohort,
    ).where(EligiblePatient.is_in_cohort > 0.5).inspect()
elif si.termination_status == "INFEASIBLE":
    print(
        "\nNo cohort of this size satisfies the eligibility and age-balance constraints."
    )
else:
    print(f"\nSolver did not converge (status={si.termination_status}).")
