# Pattern: select(*inspect.fields(rel)) — canonical idiom for unpacking
# relationship fields in a query.
# Key ideas: inspect.fields(rel) returns a tuple[FieldRef, ...] directly usable
# in select(); handles inherited properties and alt readings correctly; excludes
# the owner field by default (pass include_owner=True to include all).

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics import inspect

model = Model("inspect_fields_unpack")

# --- Tiny ontology ---
Item = model.Concept("Item", identify_by={"id": String})
Item.name = model.Property(f"{Item} has {String:name}")
Item.quantity = model.Property(f"{Item} has {Integer:quantity}")
Item.price = model.Property(f"{Item} has {Float:price}")

Order = model.Concept("Order", identify_by={"id": String})
Order.line_items = model.Relationship(f"{Order} contains {Item}")


# --- Canonical pattern: select every field of a relationship ---
def all_line_item_fields():
    """Returns one row per (Order, line_item) with every field of line_items.

    Equivalent to manually enumerating Order.line_items["<field_a>"],
    Order.line_items["<field_b>"], but handles inherited properties and
    alt readings correctly.
    """
    return model.select(*inspect.fields(Order.line_items)).to_df()


# --- With include_owner=True to also include the Order side ---
def line_items_including_owner():
    return model.select(
        *inspect.fields(Order.line_items, include_owner=True)
    ).to_df()


if __name__ == "__main__":
    print("fields(Order.line_items):", inspect.fields(Order.line_items))
    print(
        "fields(Order.line_items, include_owner=True):",
        inspect.fields(Order.line_items, include_owner=True),
    )
