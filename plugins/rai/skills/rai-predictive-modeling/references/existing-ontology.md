# Building on an Existing Ontology

When an ontology built with `rai-ontology` already exists for the source data, build the predictive layer **on top of that model** instead of starting a new `Model`. The ontology has already resolved what a fresh pipeline would have to rediscover: which tables exist, their keys and types, which columns link which tables, and data conventions such as soft-delete flags. A fresh model starts from only the task table's key and tends to stay at the one or two tables that key reaches. In one evaluation, a fresh two-table model scored ROC AUC 0.51 on a churn task. The same task scored 0.66–0.73 once the neighbouring concepts the ontology had already mapped were added to the graph.

## Detect the ontology

Look for it before Phase 1 of [auto-discovery.md](auto-discovery.md):

- **This session:** `rai-ontology` ran earlier, or a model module was written or imported in this conversation.
- **The project:** a Python module that builds a `Model(...)` and binds concepts to the source schema with `model.Table(...)`, often named after the domain.

If one exists, say so in the discovery summary and build on it. There are two exceptions, and both follow the standard flow in [SKILL.md](../SKILL.md) instead:
- **The user named specific source tables:** use exactly those, with a standalone model over them.
- **The user prefers a standalone model.**

## Steps

1. **Import the ontology's model and concepts in a separate module.** For example, `from <ontology_module> import model, Customer, Order` in `<domain>_predictive.py`. Keeping the predictive layer separate means the ontology still loads on its own for queries and rules, without the task tables. Everything that follows (task concepts, edges, `PropertyTransformer`) is declared on the same `model`. `PropertyTransformer` requires all its concepts to come from one model.

2. **Inventory the ontology.** Use `inspect.schema(model)` (see `rai-pyrel`'s `references/inspect-module.md`) to list each concept's identity, its properties with types, and its relationships. Base the plan on what is registered, not on what the module's names suggest.

3. **Map the task key to one concept.** The task relationship's head must be a single concept, so check where the task table's join key values resolve. Count the matches of the task keys against each candidate concept, in the same way you would probe a foreign key.
   - **The key resolves to one concept:** use that concept as the node.
   - **The key is only an attribute** (for example a string column present on several tables, with no concept of its own): add a node concept whose identity is that key, populated from the union of every column that carries it.
   - **The key spans several concepts that are the same entity** (for example current and archived copies held in separate tables): add one unifying node concept, populated from all of those sources.

   Check the coverage of each split separately. Train and test rows can fall in different concepts.

4. **Propose the graph from the ontology's links.** Follow [auto-discovery.md](auto-discovery.md) § Proposing the Source Graph, walking the ontology's concept-to-concept `Property` and `Relationship` links in both directions instead of raw tables. That means hop 1 preselected, hop 2 proposed, a leakage note per row, and archived or twin concepts grouped into one row. Present the result in the same summary table for the user to confirm.
   - **Merged node:** when the node is a concept you added to merge several concepts (step 3), walk from each concept it merges as well, and treat their links as the node's own. The ontology's detail concepts point at the concepts the node was built from, so the merged concept usually has few links of its own. A walk that starts only from it misses most of the graph.
   - **Stay inside the ontology:** don't add tables it does not map. State the scope in the summary ("tables outside the ontology were not considered") so the user can widen it.

5. **Define edges on scalar keys.** Ontology links are usually entity-typed (`Order.customer = model.Property(f"{Order} placed by {Customer:customer}")`). The featurizer joins node tables on scalar key columns, and in practice an entity-typed link did not export as a join key. Where the ontology has only the entity-typed link, add a scalar key property bound from the same source column, and write the edge on it:

   ```python
   from relationalai.semantics import Integer
   from relationalai.semantics.reasoners.graph import Graph
   from relationalai.semantics.reasoners.predictive import PropertyTransformer
   from sales_ontology import model, Customer, Order, src  # existing ontology module

   Order.customer_id = model.Property(f"{Order} has {Integer:customer_id}")  # scalar key for the edge
   model.define(Order.lookup(id=src.orders.id).customer_id(src.orders.customer_id))

   gnn_graph = Graph(model, directed=True, weighted=False)
   model.define(gnn_graph.Edge.new(src=Order, dst=Customer)).where(Order.customer_id == Customer.id)
   ```

   For `RelFM`, keep the graph acyclic; see § Reuse for RelFM in [SKILL.md](../SKILL.md).

6. **Select features as an allow-list.** `PropertyTransformer` auto-infers every field it is not told about. An ontology concept carries every mapped column, including values recorded after the outcome being predicted (final states, end or deletion timestamps, lifecycle flags), and those would leak the label. Pass each graph concept in `drop=`, which sets "drop" as the default for that concept's unmentioned fields, then list the features to keep by type. Explicitly listed fields override the concept-level default.

   ```python
   pt = PropertyTransformer(
       integer=[Order.quantity],
       category=[Order.channel],
       datetime=[Order.created_at],
       time_col=[Order.created_at],
       drop=[Customer, Order],  # every other field of these concepts is dropped
   )
   ```

   Only concepts that take part in the graph are exported, so the rest of a large ontology does not enter the dataset.

7. **Check graph concepts for multi-valued binary `Relationship`s.** When it exports a concept, `PropertyTransformer` adds a uniqueness requirement to each binary `Relationship` that is not a `Property` (`field_annotations` in the SDK). A one-to-many link declared on a graph concept would therefore conflict with that requirement. Represent it as a graph edge between the two concepts instead.

## What stays the same

Task table concepts, the task relationships, temporal settings (`at {Type:<slot>}`, `time_col`, `has_time_column=True`) and the estimator calls are unchanged. Build them as described in [SKILL.md](../SKILL.md) and [task-relationships.md](task-relationships.md), on the ontology's `model`.
