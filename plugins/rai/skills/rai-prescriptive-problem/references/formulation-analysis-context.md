# Formulation Analysis Context

Conventions to know when reviewing an existing formulation, so correct code is not flagged:

- Decision-variable attributes carry an `x_` prefix (`Food.x_amount`); the Property f-string names the slot without it (`f"{Food} has {Float:amount}"`). Access always goes through the Python attribute, refs included: `F = Food.ref(); F.x_amount`. `F.amount` is an undeclared relationship (PyRel warns "Potential relationship typo"), not the variable.
- Only properties registered with `solve_for()` are decision variables. A computed property (`model.define(...)`) need not appear in any constraint.
- Local aliases (`Al = Allocation.ref()`), module-level constants and Python variables holding expressions (`total = sum(...)`) are ordinary Python and valid inside constraints.
- `.per()` / `.where()` aggregation scope: `rai-pyrel`.
