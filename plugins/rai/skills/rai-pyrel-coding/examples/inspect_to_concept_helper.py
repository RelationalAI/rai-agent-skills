# Pattern: inspect.to_concept(obj) to write helpers that accept any DSL handle
# Key ideas: to_concept resolves Chain, Ref, FieldRef, Expression — anything
# that ultimately refers to a Concept — to the underlying Concept. Lets a
# helper function accept "any reference to a concept" without isinstance
# branching that misses subclasses. Raises by default; pass default=None for
# defensive use.

from relationalai.semantics import Model, String
from relationalai.semantics import inspect

model = Model("inspect_to_concept_helper")

Customer = model.Concept("Customer", identify_by={"id": String})
Customer.name = model.Property(f"{Customer} has {String:name}")

Order = model.Concept("Order", identify_by={"id": String})
Order.customer = model.Property(f"{Order} placed by {Customer:customer}")


# --- Reusable helper: accepts any handle to a Concept ---
def describe(handle, schema=None) -> str:
    """Return a short string describing the Concept that `handle` refers to.

    Accepts a Concept, a Chain (e.g. Order.customer), a Ref, a FieldRef, or
    an Expression — anything inspect.to_concept can resolve. `schema` is a
    pre-computed `inspect.schema(model)` (pass it in to avoid re-scanning).
    """
    concept = inspect.to_concept(handle, default=None)
    if concept is None:
        return f"<unresolvable: {handle!r}>"
    name = str(concept)
    if schema is None:
        schema = inspect.schema(model)
    info = schema[name]
    return f"{name} ({len(info.properties)} properties)"


if __name__ == "__main__":
    schema = inspect.schema(model)
    # All three inputs resolve to the same Concept:
    print(describe(Customer, schema))            # bare Concept
    print(describe(Customer.ref("c"), schema))   # Ref
    print(describe(Order.customer, schema))      # Chain → Customer
