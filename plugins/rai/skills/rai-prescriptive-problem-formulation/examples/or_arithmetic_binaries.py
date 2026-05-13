# Pattern: y = a OR b on binaries — linear three-inequality encoding
"""
Derived-indicator audit: binary `y` should equal `a OR b` where `a` and `b` are binary
decisions. The OR has no native operator in the MIP/CSP wire — encode as three linear
inequalities:
    y >= a       (y is at least 1 when a is)
    y >= b       (y is at least 1 when b is)
    y <= a + b   (y is at most 1 when both a and b are 0; tightens y to a, b's join)

A single equality `y == a + b` is WRONG — `a + b` can be 2 but `y` is binary. A single
`y == max(a, b)` is also rejected by the wire on decision-variable operands. The three-
inequality form is the standard linear encoding and round-trips through `verify()` as
pure arithmetic.

Demonstrates:
- All three arms are load-bearing: drop any one and a non-OR assignment becomes feasible.
    - Drop `y >= a`: solver can pick `a=1, b=0, y=0` (violates OR).
    - Drop `y >= b`: solver can pick `a=0, b=1, y=0` (violates OR).
    - Drop `y <= a + b`: solver can pick `a=0, b=0, y=1` (violates OR).
- Generalizes to N-ary OR: `y >= xi` for each i, plus `y <= sum(xi)`.
- For y = a AND b on binaries: `y <= a, y <= b, y >= a + b - 1` (symmetric pattern).

Triggering pattern: "derive a flag from two (or more) other flags via OR/AND," "rule
indicator computed from sub-rules," "is-frail = is-senior OR has-chronic." Used heavily
in CSP-style rule-property-entailment audits where derived indicators are themselves
decision variables (so the property IC can compare them directly).

Distilled from `underwriting_audit` template (the `is_frail = is_senior OR has_chronic`
rule encoding).
"""

import time

import pandas as pd

from relationalai.semantics import Integer, Model, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model(f"prescriptive_or_arithmetic_binaries_{time.time_ns()}")

# --- Concept with two binary decisions `a`, `b` and a derived OR-indicator `y` ---
Row = model.Concept("Row", identify_by={"id": Integer})
row_data = pd.DataFrame([(i,) for i in range(1, 5)], columns=["id"])  # 4 rows
model.define(Row.new(model.data(row_data).to_schema()))

Row.a = model.Property(f"{Row} has {Integer:a}")
Row.b = model.Property(f"{Row} has {Integer:b}")
Row.y = model.Property(f"{Row} has {Integer:y}")

problem = Problem(model, Integer)
problem.solve_for(Row.a, type="bin", name=["a", Row.id])
problem.solve_for(Row.b, type="bin", name=["b", Row.id])
problem.solve_for(Row.y, type="bin", name=["y", Row.id])

# --- OR-arithmetic equivalence (the focal pattern) ---
# y = a OR b   ⇔   y >= a   AND   y >= b   AND   y <= a + b
y_ge_a_ic = model.require(Row.y >= Row.a)
y_ge_b_ic = model.require(Row.y >= Row.b)
y_le_sum_ic = model.require(Row.y <= Row.a + Row.b)
problem.satisfy(y_ge_a_ic)
problem.satisfy(y_ge_b_ic)
problem.satisfy(y_le_sum_ic)

# --- Demonstrate the encoding by forcing a specific (a, b) pattern and reading y back.
# Row 1: a=0, b=0 ⇒ y=0
# Row 2: a=1, b=0 ⇒ y=1
# Row 3: a=0, b=1 ⇒ y=1
# Row 4: a=1, b=1 ⇒ y=1
# Force the inputs via equality ICs; the OR-arithmetic ICs then pin y. ---
problem.satisfy(model.where(Row.id == 1).require(Row.a == 0, Row.b == 0))
problem.satisfy(model.where(Row.id == 2).require(Row.a == 1, Row.b == 0))
problem.satisfy(model.where(Row.id == 3).require(Row.a == 0, Row.b == 1))
problem.satisfy(model.where(Row.id == 4).require(Row.a == 1, Row.b == 1))

# --- Pure satisfaction: no objective ---
problem.solve("minizinc", time_limit_sec=30)
problem.solve_info().display()

# --- Display the OR truth-table reconstruction ---
print("\nOR truth-table reconstruction:")
model.select(Row.id, Row.a, Row.b, Row.y).inspect()

# --- Validate against the expected truth-table ---
df = model.select(Row.id, Row.a, Row.b, Row.y).to_df()
expected = {(0, 0): 0, (1, 0): 1, (0, 1): 1, (1, 1): 1}
for row in df.itertuples():
    key = (int(row.a), int(row.b))
    assert int(row.y) == expected[key], (
        f"Row {row.id}: a={row.a}, b={row.b}, y={row.y}, expected {expected[key]}"
    )
print("\nAll 4 rows match OR truth-table.")
