<!-- TOC -->
- [Modeler Export Format](#modeler-export-format)
  - [Latest format (2026-02+)](#latest-format-2026-02)
  - [Key conventions in the latest format](#key-conventions-in-the-latest-format)
  - [Multi-field Relationships with short_name](#multi-field-relationships-with-short_name)
  - [filter_by() as primary data-binding pattern](#filter_by-as-primary-data-binding-pattern)
  - [Legacy format (alpha exports)](#legacy-format-alpha-exports)
  - [Format detection](#format-detection)
- [Model Composition](#model-composition)
  - [Layered pattern: base -> derived -> graph -> app](#layered-pattern-base---derived---graph---app)
  - [Each layer adds to the Concepts object](#each-layer-adds-to-the-concepts-object)
  - [Composition in the app orchestrator](#composition-in-the-app-orchestrator)
  - [Rules for model composition](#rules-for-model-composition)
<!-- /TOC -->

## Modeler Export Format

The modeler generates Python code that defines a data model. Understanding this format is essential for parsing uploaded models and generating enrichments that integrate cleanly.

**Two formats exist.** The prescriptive assistant must handle both:
1. **Latest format (2026-02+)**: Top-level `model = Model("Name")`, all Relationship, `Sources` class, `filter_by()`, `model.define()`.
2. **Legacy format (alpha)**: `initialize(model: Model)` function, `_Concept` prefix, standalone `define()`, `Concepts`/`SourceTables` classes, `BASE_SCHEMA`.

### Latest format (2026-02+)

```python
"""PyRel model: Tastybytes"""
from relationalai.semantics import Model, Date, DateTime, Integer, Number, String

model = Model("Tastybytes")

# ── Source Tables ────────────────────────────────────────────────
class Sources:
    class tastybytes:
        class raw_pos:
            menu = model.Table("TASTYBYTES.RAW_POS.MENU")
            order_detail = model.Table("TASTYBYTES.RAW_POS.ORDER_DETAIL")
        class raw_customer:
            customer_loyalty = model.Table("TASTYBYTES.RAW_CUSTOMER.CUSTOMER_LOYALTY")

# ── Concepts ─────────────────────────────────────────────────────
MenuItem = model.Concept("MenuItem", identify_by={"menu_item_id": Integer})
model.define(MenuItem.new(menu_item_id=Sources.tastybytes.raw_pos.menu.menu_item_id))

Customer = model.Concept("Customer", identify_by={"customer_id": Integer})
model.define(Customer.new(customer_id=Sources.tastybytes.raw_customer.customer_loyalty.customer_id))

# ── Properties & Relationships ───────────────────────────────────
MenuItem.pricing = model.Relationship(
    f"{MenuItem} has cost of goods $ {Number.size(38,4):cost_of_goods} and sale price $ {Number.size(38,4):sale_price}",
    short_name="menu_item_pricing"
)
model.define(
    MenuItem.filter_by(menu_item_id=Sources.tastybytes.raw_pos.menu.menu_item_id)
    .pricing(Sources.tastybytes.raw_pos.menu.cost_of_goods_usd, Sources.tastybytes.raw_pos.menu.sale_price_usd)
)

# Concept-to-concept relationship (FK via filter_by)
Order.customer = model.Relationship(f"{Order} was placed by {Customer}", short_name="order_customer")
model.define(
    Order.filter_by(order_id=Sources.tastybytes.raw_pos.order_header.order_id)
    .customer(Customer.filter_by(customer_id=Sources.tastybytes.raw_pos.order_header.customer_id))
)
```

### Key conventions in the latest format

| Convention | Example | Notes |
|------------|---------|-------|
| **Top-level model** | `model = Model("Name")` | No `initialize()` function, no return value |
| **Direct types in identify_by** | `identify_by={"id": Integer}` | No wrapper type concepts (no `ConceptID = Concept("ConceptID", extends=[String])`) |
| **`Sources` class** | `class Sources: class db: class schema: table = model.Table(...)` | Mirrors DB.SCHEMA.TABLE hierarchy as nested classes |
| **ALL Relationship** | `model.Relationship(f"...")` | Even scalar properties use Relationship, not Property |
| **`model.define()`** | `model.define(Concept.new(...))` | Model method, not standalone `define()` |
| **`filter_by()` binding** | `model.define(C.filter_by(key=src.col).prop(src.val))` | Replaces `define().where()` pattern |
| **Multi-field Relationship** | `f"{C} has {String:name} and {Float:cost}"` | Groups related fields with `short_name` |
| **`Number.size(p,s)`** | `{Number.size(38,4):price}` | Precision-typed decimals for Snowflake NUMBER columns |
| **`short_name` parameter** | `short_name="order_customer"` | Programmatic handle; used as key in `model.relationship_index` |
| **Bare concept names** | `MenuItem`, `Customer` | No underscore prefix; top-level module variables |

### Multi-field Relationships with short_name

The latest format groups related properties into a single Relationship. Each typed field in the f-string becomes a named attribute:

```python
Customer.profile = model.Relationship(
    f"{Customer} has first name {String:first_name}, last name {String:last_name}, "
    f"gender {String:gender}, birthday {Date:birthday_date}",
    short_name="customer_profile"
)
```

**`short_name`** is the programmatic name used for:
- Accessing the relationship: `model.relationship_index["customer_profile"]`
- Code readability: the relationship's full natural-language reading can be long, but `short_name` stays concise

**Property vs Relationship in the latest format:** The modeler uses Relationship for everything. This is valid — Property is a subclass of Relationship that adds a functional dependency (uniqueness) constraint. Using Relationship-only forgoes FD enforcement but avoids `FDError` on non-functional data. For optimization models where the LLM generates code, Relationship-only is safer.

### filter_by() as primary data-binding pattern

The latest format uses `filter_by()` instead of `where()` for ALL data binding:

```python
# Entity creation (identify_by keys from source)
model.define(MenuItem.new(menu_item_id=Sources.table.menu_item_id))

# Scalar property binding (filter_by on the key, then property call)
model.define(
    MenuItem.filter_by(menu_item_id=Sources.table.menu_item_id)
    .pricing(Sources.table.cost_of_goods_usd, Sources.table.sale_price_usd)
)

# FK resolution (filter_by on both sides)
model.define(
    Order.filter_by(order_id=Sources.table.order_id)
    .customer(Customer.filter_by(customer_id=Sources.table.customer_id))
)
```

**Why `filter_by()` over `where()`:** `filter_by()` is declarative and concise — one call per data binding, no separate variable creation. `model.where()` is still valid and needed for computed properties and conditional logic, but for source-table data binding, `filter_by()` is the canonical pattern.

### Legacy format (alpha exports)

Older modeler exports and some hand-written models use this structure:

```python
from relationalai.semantics import Model, define, String, Integer, Float, Date

def initialize(model: Model):
    Concept, Relationship, Property = model.Concept, model.Relationship, model.Property

    TABLE__SITE = model.Table("DB.SCHEMA.SITE")

    _Site = Concept("Site")
    _Site.id = Property(f"{_Site} has id {String:id}")
    _Site.name = Relationship(f"{_Site} has {String:name}")

    define(_Site.new(id=TABLE__SITE.id))
    define(_Site.name(TABLE__SITE.name)).where(_Site.id == TABLE__SITE.id)

    class Concepts:
        Site = _Site

    class SourceTables:
        class DB:
            class SCHEMA:
                SITE = TABLE__SITE

    BASE_SCHEMA = { ... }

    return Concepts, SourceTables, BASE_SCHEMA
```

**Key differences from latest:** `initialize()` function wrapper, standalone `define()`, `_Concept` underscore prefix, `Concepts`/`SourceTables` container classes, `BASE_SCHEMA` dict, Property for identity attributes.

The prescriptive assistant's parser must handle both formats. Key detection signals:
- Latest: `model = Model(` at top level, `class Sources:`, `short_name=`, `Number.size(`
- Legacy: `def initialize(model`, `class Concepts:`, standalone `define(`

### Format detection

| Signal | Latest (2026-02+) | Legacy (alpha) |
|--------|-------------------|----------------|
| Entry point | `model = Model("Name")` at top level | `def initialize(model: Model):` |
| define() | `model.define(...)` | standalone `define(...)` |
| Concept naming | `MenuItem` (bare) | `_MenuItem` (underscore prefix) |
| Table organization | `class Sources:` nested | `TABLE__NAME = Table(...)` flat |
| Return value | None | `return Concepts, SourceTables, BASE_SCHEMA` |
| Property usage | None (all Relationship) | Property for identity, Relationship for rest |

---

## Model Composition

Real-world models are built in layers. The modeler export provides the base model, and derived models add business logic, inverse relationships, computed properties, and graph structure on top.

### Layered pattern: base -> derived -> graph -> app

```
base model (generated_enriched.py)
    Concepts: Site, SKU, Business, Supplier, Customer, Operation, Demand, Shipment
    Data loading from Snowflake tables
    Forward relationships (from FK columns)
    Inverse relationships via .alt()

derived model (derived_model.py)
    Derived concepts: Region, Bridge, HighValueCustomer
    Inverse relationships via explicit model.define()
    Computed properties: count_is_destination, count_is_source
    Unary flags: Shipment.is_delayed

graph layer (graphs.py)
    Graph edges from relationships
    Weighted edges from computed properties

app orchestrator (app_model.py)
    Composes all layers into a single model
    Passes Concepts object through each layer
```

### Each layer adds to the Concepts object

```python
def initialize_derived_model(model, concepts):
    """Add derived concepts and relationships to an existing model."""
    Supplier = concepts.Supplier
    Shipment = concepts.Shipment

    # Add inverse relationship
    Supplier.shipment = Shipment.supplier.alt(f"{Supplier} has shipment {Shipment}")

    # Add derived concept
    Region = model.Concept("Region")
    model.define(Region.new(id=Site.region_id))
    concepts.Region = Region  # Attach to concepts for downstream layers

    # Add unary flag
    Shipment.is_delayed = model.Relationship(f"{Shipment} is delayed")
    model.define(Shipment.is_delayed()).where(Shipment.delay_days > 0)

    # Add computed property
    Site.count_is_destination = model.Relationship(
        f"{Site} has count of incoming shipments {Integer:count_is_destination}"
    )
    site, op = Site.ref(), Operation.ref()
    model.where(
        Operation.destination_site(op, site),
        Operation.type(op, "SHIP")
    ).define(Site.count_is_destination(site, aggs.count(op).per(site)))
```

### Composition in the app orchestrator

```python
from relationalai.semantics import Model
from .generated_enriched import initialize as init_base
from .derived_model import initialize_derived_model
from .graphs import initialize_graphs

model = Model("supply_chain")
Concepts, SourceTables, BASE_SCHEMA = init_base(model)
initialize_derived_model(model, Concepts)
initialize_graphs(model, Concepts)
```

### Rules for model composition

- **Base model owns identity**: Only the base model creates entities with `.new()`. Derived layers filter or extend, never redefine identity.
- **Derived layers use `.ref()`**: When joining across concepts, use `.ref()` to create aliases.
- **Attach to Concepts object**: New derived concepts must be added to the `concepts` object (`concepts.Region = Region`) so downstream layers can access them.
- **Inverse relationships belong in derived layers**: The base model defines forward relationships (from FK data). Inverse relationships are derived and belong in a separate layer.
- **Use `model.define()` and `model.where()`** in derived layers, not standalone `define()`/`where()` — derived layers operate on a shared model object.

---
