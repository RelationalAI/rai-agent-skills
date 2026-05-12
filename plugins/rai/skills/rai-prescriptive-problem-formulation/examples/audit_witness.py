# Pattern: pure-satisfaction audit — INFEASIBLE = property holds, OPTIMAL/SOLUTION_LIMIT = counterexample found
"""
Salary policy audit: is there any subset of K=3 employees whose total salary exceeds a budget cap?
- INFEASIBLE => no such triple exists => policy holds (PASS)
- OPTIMAL / SOLUTION_LIMIT => at least one triple found => policy violated (FAIL); extract up to MAX_WITNESSES

Demonstrates:
- Audit-verdict mapping: termination_status drives the conclusion, NOT objective_value or num_points
- num_points() == 0 does NOT prove the property holds — solver may have crashed or timed out;
  always check termination_status first
- Multi-witness enumeration via solution_limit
- Status-gated extraction
- Pure-satisfaction MiniZinc-style: no objective, only constraints

Triggering pattern: "is there any X where Y happens," "find counterexamples," "audit / witness check,"
"is this policy violated." Outcome lives in the status, not the objective.

Distilled from underwriting_audit.
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_audit_witness_{time.time_ns()}")

K = 3  # subset size to check for the budget breach
BUDGET_CAP = 250_000  # any K-subset summing above this is a violation
MAX_WITNESSES = 5  # cap on counterexamples returned for the report

# --- Concept and inline data ---
Employee = model.Concept("Employee", identify_by={"id": Integer})
Employee.salary = model.Property(f"{Employee} has {Integer:salary}")

employee_data = pd.DataFrame(
    [
        (1, 80_000),
        (2, 75_000),
        (3, 90_000),
        (4, 110_000),
        (5, 60_000),
        (6, 95_000),
        (7, 70_000),
        (8, 100_000),
    ],
    columns=["id", "salary"],
)
model.define(Employee.new(model.data(employee_data).to_schema()))

# --- Decision: select which K employees form the candidate violating triple ---
Employee.x_flagged = model.Property(f"{Employee} is {Integer:flagged}")

problem = Problem(model, Integer)
flag_var = problem.solve_for(
    Employee.x_flagged,
    type="bin",
    name=["flag", Employee.id],
    populate=False,
)

# --- Constraint: exactly K employees flagged ---
problem.satisfy(model.require(sum(Employee.x_flagged) == K))

# --- Constraint: the flagged subset's total salary breaches the cap ---
# Mask each salary by the flagged binary: per-employee contribution is salary when
# flagged (binary == 1) and 0 otherwise.
problem.satisfy(
    model.require(sum(Employee.salary * Employee.x_flagged) >= BUDGET_CAP + 1)
)

# --- Solve as pure satisfaction (no objective) ---
problem.solve("minizinc", solution_limit=MAX_WITNESSES, time_limit_sec=30)
si = problem.solve_info()
si.display()

# --- Audit verdict from termination_status ---
if si.termination_status == "INFEASIBLE":
    verdict = "PASS"
    print(
        f"\nVerdict: {verdict} — no subset of {K} employees exceeds ${BUDGET_CAP:,} together."
    )
elif si.termination_status in ("OPTIMAL", "SOLUTION_LIMIT"):
    verdict = "FAIL"
    n_points = si.num_points or 0
    print(f"\nVerdict: {verdict} — {n_points} violating triple(s) found:")
    val = Integer.ref()
    for sol_idx in range(n_points):
        df = (
            model.select(
                Employee.id.alias("employee"),
                Employee.salary.alias("salary"),
                val.alias("flagged"),
            )
            .where(flag_var.values(sol_idx, val), val > 0.5)
            .to_df()
        )
        total = int(df["salary"].astype(int).sum().item())
        print(f"\n  Witness {sol_idx}: total = ${total:,}")
        print(df.to_string(index=False))
else:
    verdict = "INCONCLUSIVE"
    print(
        f"\nVerdict: {verdict} — solver did not exhaust the search (status={si.termination_status}). "
        "Do not interpret as PASS."
    )
