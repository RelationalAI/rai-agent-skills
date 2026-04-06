<!-- TOC -->
- [Enrichment Patterns](#enrichment-patterns)
  - [When enrichment is needed vs. when the existing model suffices](#when-enrichment-is-needed-vs-when-the-existing-model-suffices)
  - [Feasibility Classification: READY / MODEL_GAP / DATA_GAP](#feasibility-classification-ready--model_gap--data_gap)
  - [Variable pattern selection for enrichment](#variable-pattern-selection-for-enrichment)
  - [Common problem types and their enrichments](#common-problem-types-and-their-enrichments)
  - [Decision concepts as ontology extensions](#decision-concepts-as-ontology-extensions)
  - [Promoting relationships to concepts](#promoting-relationships-to-concepts)
  - [Cross-product concept creation](#cross-product-concept-creation)
  - [Filtered cross-products](#filtered-cross-products)
  - [Multi-hop relationship enrichment](#multi-hop-relationship-enrichment)
<!-- /TOC -->

## Enrichment Patterns

Enrichment means adding properties, relationships, or concepts to the base ontology so an optimization problem can be formulated. Enrichment is always driven by what the problem needs, not by scanning column names for optimization keywords.

### When enrichment is needed vs. when the existing model suffices

| Situation | Action |
|-----------|--------|
| Problem needs a property that already exists on a concept | No enrichment; use the property directly (`existing` pattern) |
| Problem needs a new decision property on a concept that already has entities | Add the property (`extended_property` pattern) |
| Problem needs to pair two concepts that have no relationship | Create a junction/decision concept (`extended_concept` pattern) |
| Problem needs a data property not yet mapped from the schema | Map the unmapped column to a property on the appropriate concept |

### Feasibility Classification: READY / MODEL_GAP / DATA_GAP

Rate each problem's feasibility using these actionable categories:

| Label | Meaning | What happens next |
|-------|---------|-------------------|
| **READY** | All required data is present in the model. | Proceed to formulation immediately. |
| **MODEL_GAP** | Data exists in the schema but isn't mapped to the model. | Auto-enrichable via `model_gap_fixes`. Proceed after enrichment. |
| **DATA_GAP** | Required data doesn't exist in any table. | Blocked -- needs IT/data team to provide the data. |

**Classification decision tree** (apply to each missing item):
1. Does the data exist in a Snowflake/database table but isn't mapped to the model? -- **MODEL_GAP** (auto-enrichable)
2. Is it a business parameter the user would typically specify (budget, threshold, target %)? -- **parameter_gap** (user input at solve time -- does not affect feasibility label)
3. Is it historical/transactional data that must come from a database? -- **DATA_GAP** (blocks formulation)

**Examples:**
- "Need Site.capacity" and SITE table has CAPACITY column -- MODEL_GAP
- "Need daily budget limit" -- parameter_gap (user provides $X) -- feasibility stays READY or MODEL_GAP
- "Need historical demand patterns" and no table has this data -- DATA_GAP

**Why this matters for workflows:**
- **MODEL_GAP**: The LLM proposes a concrete enrichment fix (concept, property name, source table/column). The system auto-applies it or presents it for user approval.
- **DATA_GAP**: The LLM flags the gap clearly and explains what data is needed, but cannot auto-fix it. Data gaps block formulation of any component that depends on the missing data.
- **parameter_gap**: User-provided business parameters (budget limits, service level targets, etc.) that can be input at solve time. These never block problem selection.

### Variable pattern selection for enrichment

1. **Check existing relationships first.** If Product already has `Product.factory`, add `production_quantity` to Product -- do not create a FactoryProduct cross-product.
2. **Use `extended_property`** when the concept already has entities and an existing relationship to related concepts.
3. **Use `extended_concept`** when no relationship exists between the concepts being paired, OR when an existing relationship needs its own attributes (see [Promoting relationships to concepts](#promoting-relationships-to-concepts) below).

### Common problem types and their enrichments

**Allocation / Fulfillment** (e.g., assigning demand to supply points):
- Typically needs a cross-product decision concept linking demand and supply (e.g., `FulfillmentAssignment` connecting `Demand` to `Site`)
- Binary or continuous decision variable (`assigned`, `flow_quantity`)
- Denormalize cost/priority properties onto the decision concept

**Scheduling** (e.g., assigning tasks to time slots or resources):
- Cross-product of tasks and resources/slots if no relationship exists
- Binary variable (`is_assigned`)
- May need time-indexed multiarity properties for multi-period models

**Routing / Network flow** (e.g., shipping goods through a network):
- If an `Operation` or `Arc` concept already connects nodes, use `extended_property` for flow
- Otherwise create a flow concept connecting origin to destination
- Flow conservation constraints require inflow/outflow aggregations

**Portfolio / Selection** (e.g., choosing a subset of items):
- Add a continuous or binary decision property to the existing item concept
- Usually `extended_property` since items already exist with data

**Template examples by problem type:**
- Allocation: `../../rai-prescriptive-problem-formulation/examples/fixed_charge_facility.py`, `../../rai-prescriptive-problem-formulation/examples/semi_continuous_activation.py`
- Scheduling: `../../rai-prescriptive-problem-formulation/examples/binary_coverage_scoped.py`, `../../rai-prescriptive-problem-formulation/examples/hinge_variable_penalty.py`
- Routing/Network: `../../rai-prescriptive-problem-formulation/examples/flow_conservation.py`, `../../rai-prescriptive-problem-formulation/examples/multi_concept_union_objective.py`
- Portfolio/Selection: `../../rai-prescriptive-problem-formulation/examples/quadratic_pairwise_ref.py`, `../../rai-prescriptive-problem-formulation/examples/coupled_binary_knapsack.py`
- Pricing: `../../rai-prescriptive-problem-formulation/examples/one_hot_temporal_recurrence.py`
- Resource Allocation (multi-period): `../../rai-prescriptive-problem-formulation/examples/multi_period_flow_conservation.py`

### Decision concepts as ontology extensions

When a prescriptive problem is formulated, it creates decision concepts (e.g., `FulfillmentAssignment`, `ProductionPlan`) that extend the ontology -- they are not throwaway code artifacts. After solving, these concepts carry solution values that persist in the graph and can be referenced by other reasoners, queries, and applications.

**What this means for enrichment:**
- Decision concepts are part of the ontology growth story, not just the formulation layer
- After solving, `ProductionPlan.quantity = 150 for SKU_1 at Site_A` is a fact in the ontology
- Other reasoners (predictive, graph) can read decision concept values
- The ontology is richer after optimization -- it contains "what should happen," not just "what exists"

This does not change the gap classification (decision concepts are still formulation-layer, not MODEL_GAP), but it reframes their purpose: they are ontology extensions, not temporary solver artifacts.

### Promoting relationships to concepts

Sometimes a relationship between two concepts needs its own properties -- a grade on an enrollment, a cost on an assignment, a date on a membership. When this happens, **promote the relationship to a concept** with compound identity. The promoted concept acts as both a link between the participating concepts and an entity that carries its own data.

**When promotion is needed:**
1. When no relationship exists between two concepts being paired (the `extended_concept` case already documented)
2. **Also** when a relationship DOES exist but needs its own attributes

The current `extended_concept` guidance ("use only when no relationship exists") is a sufficient but not necessary condition. Promotion is also needed when a relationship carries data.

```python
# Relationship exists (Student enrolled in Course) but needs attributes
# Promote the enrollment relationship into an Enrollment concept
Enrollment = model.Concept("Enrollment", identify_by={"student": Student, "course": Course})
Enrollment.grade = model.Property(f"{Enrollment} has {Float:grade}")
Enrollment.enrollment_date = model.Property(f"{Enrollment} has {Date:enrollment_date}")

# The promoted concept maintains 1:1 correspondence with the relationship:
# every Enrollment entity corresponds to exactly one (Student, Course) pair
# and vice versa -- compound identify_by enforces this
```

**1:1 correspondence rule:** The promoted concept must maintain a 1:1 mapping with the underlying relationship instances. Using compound `identify_by` with the participating concepts enforces this -- each unique pair of participants maps to exactly one entity. Without this, you risk creating entities that don't correspond to valid relationships (e.g., phantom enrollments without a real student-course link).

**Decision rule:**
- Relationship has no attributes: use `model.Relationship()` directly
- Relationship has 1 attribute: use an N-ary Property (e.g., `f"{A} to {B} costs {Float:cost}"`)
- Relationship has 2+ attributes: promote to a junction concept with compound identity

### Cross-product concept creation

When you need `extended_concept`, follow this pattern:

```python
# 1. Define the decision concept with relationships to existing concepts
FulfillmentAssignment = model.Concept("FulfillmentAssignment")
FulfillmentAssignment.demand = model.Relationship(
    f"{FulfillmentAssignment} fulfills {CustomerDemand:demand}"
)
FulfillmentAssignment.site = model.Relationship(
    f"{FulfillmentAssignment} from {Site:site}"
)
FulfillmentAssignment.assigned = model.Property(
    f"{FulfillmentAssignment} active {Float:assigned}"
)

# 2. Create entities by cross-product
model.define(FulfillmentAssignment.new(demand=CustomerDemand, site=Site))

# 3. Register the decision property
p.solve_for(
    FulfillmentAssignment.assigned, type="bin",
    name=["assign", FulfillmentAssignment.demand.id, FulfillmentAssignment.site.id]
)
```

**Complete cross-product examples:** See `../../rai-prescriptive-problem-formulation/examples/binary_coverage_scoped.py` and `../../rai-prescriptive-problem-formulation/examples/fixed_charge_facility.py`.

**Critical rules for cross-product concepts:**
- Use `Relationship` (not `Property` with `_id` suffix) to connect to existing concepts
- Relationship targets must be concepts that actually exist in the base model
- Denormalize objective-relevant properties (cost, weight, priority) onto the decision concept because property chaining does not work in solver expressions
- All referenced concepts must have loaded data

### Filtered cross-products

When only a subset of pairings is valid, add a `.where()` clause:

```python
model.define(SiteProduction.new(sku=SKU, site=Site)).where(SKU.site == Site)
```

This avoids creating unnecessary entities and keeps the problem size manageable.

### Data Binding for Enriched Relationships

A relationship enrichment is incomplete without data binding. After declaring:

```python
Order.customer = model.Relationship(f"{Order} assigned to {Customer:customer}")
```

You MUST also add a `define()` rule to populate it:

```python
source = model.Table("DB.SCHEMA.ORDERS")
model.define(
    Order.filter_by(id=source.ORDER_ID)
    .customer(Customer.filter_by(id=source.CUSTOMER_ID))
)
```

Without the `define()`, the relationship exists in the schema but has zero data — any `.where()` join using it will silently return zero matches.

### Multi-hop relationship enrichment

RAI doesn't support multi-hop traversals directly (e.g., `Demand.customer.site`). When you need a property accessible only through an intermediate concept, create a derived property or relationship on the source concept.

**When needed:** An expression references `FromConcept.link.property` where `link` is a relationship to an intermediate concept.

**Choose the pattern based on the target type:**

| Target type | Pattern | API |
|-------------|---------|-----|
| Scalar (Float, Integer, String, Date) | Property + `.ref()` | `model.Property()` + `model.define()` |
| Entity (another Concept) | Relationship + `.set()` | `model.Relationship()` + `model.define()` |

#### Scalar target — Property + .ref()

Use when the final property resolves to a scalar value (number, string, date).

```python
# Need: MachinePeriod.machine.failure_probability (Float)
# Create: MachinePeriod.machine_failure_probability

MachinePeriod.machine_failure_probability = model.Property(
    f"{MachinePeriod} has {Float:machine_failure_probability}"
)
MPRef = MachinePeriod.ref()
MRef = Machine.ref()
model.define(
    MPRef.machine_failure_probability(MRef.failure_probability)
).where(MPRef.machine(MRef))
```

**Rules:**
- `model.Property()` requires an f-string (`f"..."`). Without the `f` prefix, `{Concept}` and `{Type:name}` are literal text, causing `[Unknown Concept]` errors at runtime.
- Use the correct type annotation (Float, Integer, String) matching the target property's declared type.
- Use `.ref()` aliases for BOTH the source and intermediate concepts in the `define().where()` statement.

#### Entity target — Relationship + .set()

Use when the final property resolves to another concept entity.

```python
# Need: Demand.customer.site (Site entity)
# Create: Demand.customer_site

Demand.customer_site = model.Relationship(
    f"{Demand} located at {Site:customer_site}"
)
model.define(
    Demand.customer_site.set(Demand.customer.site)
).where(Demand)
```

**Rules:**
- Use `model.Relationship()` referencing the target Concept type.
- Use `.set()` to compose the traversal chain.

#### Table-based join (when concepts lack direct relationships)

Use when the source and intermediate concepts don't have a direct relationship but are connected through underlying tables.

```python
# Need: Demand.customer_site (but only table FKs connect them)

Demand.customer_site = model.Relationship(f'{Demand} has {Site:customer_site}')
model.define(Demand.customer_site(Site)).where(
    Demand.id == TABLE__DEMAND.id,
    TABLE__DEMAND.customer_id == TABLE__CUSTOMER.id,
    Site.id == TABLE__CUSTOMER.site_id
)
```

**Steps:**
- Find the `FromConcept.link` relationship to understand which table/FK links to the intermediate concept
- Find the intermediate concept's `target_property` relationship to understand the next hop
- Compose a join through both tables using actual table/column names from the schema

---
