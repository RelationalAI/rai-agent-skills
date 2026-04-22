# Pattern: inspect.schema(model) to report what actually registered
# Key ideas: ModelSchema is a frozen dataclass; supports dict-style lookup by
# concept name; .to_dict() for JSON-safe serialization. Real TableSchema types
# propagate through Concept.new(table.to_schema()) in v1.0.14+ — concrete types
# (Integer, String, Date) appear instead of Any.

import json

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics import inspect

model = Model("inspect_schema_summary")

# --- Tiny ontology for demonstration ---
Customer = model.Concept("Customer", identify_by={"id": String})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.score = model.Property(f"{Customer} has {Float:score}")

Order = model.Concept("Order", identify_by={"id": String})
Order.amount = model.Property(f"{Order} has {Float:amount}")
Order.item_count = model.Property(f"{Order} has {Integer:item_count}")
Order.customer = model.Relationship(f"{Order} placed by {Customer}")


# --- Pattern 1: print a human-readable summary of the whole model ---
def schema_summary():
    schema = inspect.schema(model)
    for concept in schema.concepts:
        # Filter reasoner-internal concepts (underscore-prefixed)
        if concept.name.startswith("_"):
            continue
        print(f"{concept.name}:")
        for prop in concept.properties:
            print(f"  .{prop.name}: {prop.type_name}")


# --- Pattern 2: dict-style access for a specific concept ---
def customer_properties():
    schema = inspect.schema(model)
    customer_info = schema["Customer"]
    return {p.name: p.type_name for p in customer_info.properties}


# --- Pattern 3: does a property already exist? (inspect-before-authoring) ---
def has_property(concept_name: str, member_name: str) -> bool:
    schema = inspect.schema(model)
    return any(p.name == member_name for p in schema[concept_name].properties)


# --- Pattern 4: JSON-safe dump for user-facing reports ---
def dump_schema_json() -> str:
    return json.dumps(inspect.schema(model).to_dict(), indent=2, sort_keys=True)


if __name__ == "__main__":
    schema_summary()
    print()
    print("Customer properties:", customer_properties())
    print("has Customer.email?", has_property("Customer", "email"))
    print("has Customer.name?", has_property("Customer", "name"))
