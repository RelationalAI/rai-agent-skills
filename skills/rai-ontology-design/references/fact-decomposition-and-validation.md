<!-- TOC -->
- [Decomposition and Atomicity](#decomposition-and-atomicity)
  - [Irreducibility check](#irreducibility-check)
  - [Minimum key span check](#minimum-key-span-check)
  - [Functional dependency as a splittability signal](#functional-dependency-as-a-splittability-signal)
  - [Redundancy check via sample data](#redundancy-check-via-sample-data)
  - [Schema equivalence for model refactoring](#schema-equivalence-for-model-refactoring)
- [Validation by Sample Data and Reading Strings](#validation-by-sample-data-and-reading-strings)
  - [Sample data validation as a design-time unit test](#sample-data-validation-as-a-design-time-unit-test)
  - [Counterexample validation for constraints](#counterexample-validation-for-constraints)
  - [Reading string validation](#reading-string-validation)
<!-- /TOC -->

## Decomposition and Atomicity

Every Property and Relationship declaration should be **irreducible** -- it cannot be split into two or more independent declarations involving the same types without information loss. Irreducibility is the single most important quality gate for the design decision sequence. Apply these checks after step 3 (Identify links) and step 4 (Identify properties) in the design sequence.

### Irreducibility check

A proposed Property or Relationship is irreducible if and only if it cannot be rephrased as two or more independent binary (or lower-arity) declarations without losing information. If it can be split, it must be split.

**How to apply:**

For each ternary-or-higher Property or Relationship, ask: "Can I express this as two independent binary declarations?" If yes, the ternary is compound and should be decomposed.

```python
# COMPOUND (fails irreducibility): "Supplier supplies Part in Quantity"
# If Supplier-Part and Part-Quantity are independent, split them:
Supplier.supplies = model.Relationship(f"{Supplier} supplies {Part}")
Part.standard_qty = model.Property(f"{Part} has standard quantity {Float:qty}")

# IRREDUCIBLE (passes check): "Food contains Nutrient in Quantity"
# The quantity depends on BOTH Food and Nutrient together -- cannot be split
Food.contains = model.Property(f"{Food} contains {Nutrient} in {Float:qty}")
```

**Decision rule:** A ternary `A-B-C` is irreducible when knowing `A-B` and `B-C` independently does NOT let you reconstruct the original `A-B-C` declaration. If it does, decompose.

### Minimum key span check

For any Property or Relationship with n fields (n > 2), the minimum set of fields needed to determine the value must span at least n-1 fields. If a single field has its own uniqueness constraint, the declaration is compound and should be split.

**How to apply:**

After declaring a ternary Property like `f"{A} does {B} with {C:value}"`, check: does any single concept among `A` and `B` uniquely determine the value? If `A` alone determines `value` (regardless of `B`), then `B` is an independent fact and should be a separate declaration.

```python
# FAILS minimum key span: if Supplier alone determines cost (regardless of Warehouse)
# Bad: ternary where single field has uniqueness
Supplier.route_cost = model.Property(f"{Supplier} ships to {Warehouse} at {Float:cost}")

# Fix: split into two independent declarations
Supplier.shipping_cost = model.Property(f"{Supplier} has {Float:shipping_cost}")
Supplier.ships_to = model.Relationship(f"{Supplier} ships to {Warehouse}")

# PASSES minimum key span: cost depends on BOTH Supplier and Warehouse
# The (Supplier, Warehouse) pair is the minimal key -- keep as ternary
Route.cost = model.Property(f"{Supplier} to {Warehouse} costs {Float:cost}")
```

### Functional dependency as a splittability signal

Within an n-ary Property or Relationship, if one non-key field functionally determines another non-key field, the declaration is compound. Use FD detection as a diagnostic: after declaring a multi-field Property, check whether any subset of fields determines other fields independently.

**How to apply:**

Given a proposed declaration with fields `{A, B, C, D}`, if `A -> C` holds independently of `B` and `D`, extract `A-C` as its own Property and reduce the original to `{A, B, D}`.

```python
# COMPOUND: Employee assigned to Project with Department and Role
# If Employee -> Department (each employee is in exactly one department),
# then Department is independent of the Project assignment
Employee.department = model.Property(f"{Employee} in {Department:department}")
Employee.assigned = model.Property(f"{Employee} on {Project} as {String:role}")

# vs. if Department depends on the Project assignment (matrix org), keep together
ProjectAssignment.info = model.Property(
    f"{Employee} on {Project} in {Department} as {String:role}"
)
```

**Signal:** If you can fill in a column value knowing only a subset of the key columns, there's a hidden FD and the association should be split.

### Redundancy check via sample data

After proposing a Property or Relationship, populate it with 3-5 sample rows from actual data. If the same value combination appears in more than one row (same values in all fields), the declaration is either compound (needs splitting) or the data has duplicates that should be resolved.

**How to apply:**

```
Proposed: Supplier supplies Part at Price
Sample population:
  (Acme, Bolt, 1.50)
  (Acme, Nut,  0.75)
  (Acme, Bolt, 1.50)  <-- duplicate! Same fact repeated

Diagnosis: Either the data has true duplicates (clean them), or there's
a hidden dimension (e.g., Date) that makes each row unique:
  Supplier.price = model.Property(f"{Supplier} supplies {Part} on {Date} at {Float:price}")
```

**Rule:** Zero repeated rows in a correct sample. If duplicates appear, either add a missing dimension or deduplicate the source data.

### Schema equivalence for model refactoring

When restructuring an existing model (splitting a concept, merging properties, replacing a ternary with a promoted junction concept), verify that the transformation is **semantics-preserving** -- the new schema can represent exactly the same data as the old one.

**Equivalence check:** For any proposed refactoring:
1. Can every value expressible in the old schema be expressed in the new one? (No information loss)
2. Can every value expressible in the new schema be expressed in the old one? (No spurious data)

If both hold, the transformation is safe. If only (1) holds, the new schema is more general (acceptable if the extra expressiveness is intended). If (1) fails, the refactoring loses information.

```python
# Refactoring: split a ternary into junction concept + property
# Old: Supplier.supplies = Property(f"{Supplier} supplies {Part} in {Float:qty}")
# New: SupplyLink = Concept("SupplyLink", identify_by={"supplier": Supplier, "part": Part})
#      SupplyLink.qty = Property(f"{SupplyLink} has {Float:qty}")

# Equivalence check:
# Old fact: (Acme, Bolt, 100) -- expressible in new as SupplyLink(Acme,Bolt).qty=100
# New fact: SupplyLink(Acme, Bolt) with no qty -- NOT expressible in old (new is more general)
# Verdict: safe refactoring (new schema is strictly more general)
```

**Decision rule:** Before committing a model restructuring, verify equivalence. If equivalence fails, document what information is gained or lost and confirm the trade-off is acceptable.

---

## Validation by Sample Data and Reading Strings

These validation techniques catch structural errors (wrong arity, wrong key, wrong multiplicity) before they propagate into downstream formulations. Apply them during and after steps 2-5 of the design decision sequence.

### Sample data validation as a design-time unit test

Every proposed concept, property, and relationship should be instantiated with at least one example row before being committed to the model. This is the single most effective way to catch design errors early.

**How to apply:**

After declaring a concept and its properties, immediately verify with sample data:

```python
# 1. Declare
Order = model.Concept("Order", identify_by={"id": Integer})
Order.amount = model.Property(f"{Order} has {Float:amount}")
Order.placed_by = model.Property(f"{Order} placed by {Customer:customer}")

# 2. Populate mentally or with test data -- verify each fact makes sense:
#    Order(id=1001) has amount 250.00          -- scalar, one value per order: correct
#    Order(id=1001) placed by Customer(id=42)  -- one customer per order: correct
#    Order(id=1001) placed by Customer(id=43)  -- TWO customers? FDError! 
#    If this can happen, placed_by should be Relationship, not Property

# 3. Run a minimal load to confirm
model.define(Order.new(id=test_table.order_id))
model.define(Order.amount(test_table.amount)).where(Order.id == test_table.order_id)
result = model.select(Order.id, Order.amount).to_df()
assert len(result) > 0, "Population check: no entities loaded"
```

**Rules:**
- Every concept must have at least one loadable entity
- Every property must produce at least one non-null value
- Every relationship must link at least one pair of entities
- If any check fails, revisit the declaration before proceeding

### Counterexample validation for constraints

To verify that a constraint (uniqueness via Property, mandatory role, business rule) is correct, construct a **counterexample** -- a fact that would violate the constraint -- and confirm it should indeed be rejected.

**How to apply:**

```
Constraint: Order.placed_by is a Property (FD: each order has exactly one customer)

Counterexample: "Order 1001 is placed by both Customer 42 and Customer 43"
Q: Should this be rejected? 
  - If YES (an order always has exactly one customer): Property is correct
  - If NO (an order can have multiple customers, e.g., group orders): 
    switch to Relationship

Constraint: model.where(Employee.age >= 18) for FullTimeEmployee subtype
Counterexample: "Employee age 16 is a FullTimeEmployee"
Q: Should this be rejected?
  - If YES: constraint is correct
  - If NO (apprenticeship programs allow minors): revise the threshold
```

**Rule:** For every constraint you encode (FD via Property, subtype filter, business rule), state one concrete violation and confirm rejection. If you cannot construct a counterexample, the constraint may be vacuous.

### Reading string validation

Every Property and Relationship already has a reading string (the `f"{Concept} has {Type:name}"` pattern). Use these reading strings -- enriched with constraint semantics -- as a self-check or domain expert validation step.

**How to apply:**

After building a section of the model, generate the full constrained verbalization and verify each statement:

```
Model verbalizations:
1. "Each Order has exactly one amount (Float)."           -- Property FD
2. "Each Order is placed by exactly one Customer."        -- Property FD (concept-valued)  
3. "Each Customer may have placed zero or more Orders."   -- Relationship (inverse)
4. "Each LineItem is identified by its Order and Product." -- compound identity
5. "No Order can have a negative amount."                 -- business rule

Review: Does statement 3 allow a Customer with zero Orders?
  - If customers must have at least one order: add a mandatory role constraint
  - If customers can exist without orders: correct as stated
```

**Enriched verbalization pattern:**
- Property (mandatory): "Each `{Concept}` has exactly one `{value_type}`"
- Property (optional): "Each `{Concept}` has at most one `{value_type}`"
- Relationship (many-to-many): "Each `{A}` may be linked to zero or more `{B}`s"
- Subtype: "Each `{Sub}` is a `{Super}` where `{condition}`"
- Compound identity: "Each `{Concept}` is identified by its `{key1}` and `{key2}`"

Use this verbalization as a checklist: read each statement aloud (or to the domain expert) and confirm it matches the business reality. Mismatches reveal modeling errors.
