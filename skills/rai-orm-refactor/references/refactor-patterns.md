# Refactor patterns

Choose a pattern after reading the entity's identifier, roles, constraints and source bindings. Test every affected item using existing elements before proposing replacements. Names follow schema/domain terminology; query wording alone cannot justify an entity. `rai-pyrel-coding` and `rai-querying` own runnable syntax; `rai-orm-verify` owns semantic acceptance.

## Query-as-concept

**Symptom:** A derived entity is named for a filter, aggregate, ranking or one workload item; it contributes no independently meaningful identity or roles.

**Test:** Remove it from the scaffold inventory and reproduce every use by walking existing entities and applying the filter, aggregate or ranking. Check whether the domain nevertheless treats the result as an entity with its own lifecycle, reference scheme or incoming roles.

**Change:** Remove the entity and use the path. If its calculation is reusable, propose a named derived fact type on the business entity rather than a new entity per calculation.

**Verify:** All outputs, grouping keys, NULL behavior, source populations and duplicate counts survive. Update dependent constraints and saved rewrites through regenerated YAML. Keep legitimate single-item entities; support is a hint, not the test.

## Per-value flags to an enumerated value type

**Symptom:** Many Boolean facts encode the alternative values of one categorical property.

**Test:** Establish that the alternatives are mutually exclusive and describe one dimension; determine whether they are exhaustive and how missing/unknown values work. Scaffold each classification test using an existing categorical fact or other surviving evidence. The business entity survives this test; the suspect is its flag family. If the flags are the only evidence, record the blocked path rather than inventing a categorical field to complete the test.

**Change:** Replace redundant flags with one categorical fact type and an enumerated value type, retaining the source binding/derivation. Values come from authorized schema/domain evidence, not workload literals. Independent flags stay independent; a multivalued classification may need a relationship instead of a single enum property.

**Verify:** Exclusivity, completeness, multi-true rows, all-false rows, NULL versus false, query membership tests and mandatory/value constraints. A counted four-flag explosion does not prove these conditions. Keep flags when a single category would lose information.

## Table mirrors

**Symptom:** A table-bound concept has the same business identity as another, connected by a 1:1 key link, and exists only to match storage layout.

**Test:** Check key correspondence, mandatory participation, population differences and whether either concept has independent identity or lifecycle. Use surviving facts to scaffold all uses after removing the candidate entity; a unique attribute reachable only through that entity is a blocked step until a justified modeling change exists. Distinguish equal keys from equal populations; a directory table and a registration table can differ despite matching identifiers.

**Change:** Merge into one business entity with correctly scoped facts/bindings. Preserve justified population membership as a domain fact or relationship, not a flag per query. If there is independent identity or a distinct event grain, keep the entities and their link.

**Verify:** Counts on each original population, absent related rows, uniqueness, optional attributes, join kinds and any composite identity. A confirmed 1:1 binary is a candidate, not proof that both sides can collapse.

## Duplicated or historical families to a subtype or temporal relationship

**Symptom:** Several entities have the same property signature, or a current/historical family repeats the same business entity with extra version columns.

**Test:** Compare identifiers, units, role meanings and populations, not only names or signatures. Determine whether instances are the same entity in different roles, genuinely distinct kinds with specialized roles, or observations at different times. Scaffold uses through existing shared entities and temporal facts; if those facts are absent, keep the family until a supported modeling change supplies them.

**Change:** Merge synonyms; use a subtype only for a kind with distinct roles and a compatible reference scheme. Preserve history with a temporal relationship or objectified state whose identifier includes the relevant time/version role; avoid overwriting versions on the enduring entity.

**Verify:** Subtype participation, disjoint/exhaustive assumptions, inherited references, validity intervals, point-in-time answers, historical row counts and current selection. Identical primitive properties do not make two entity kinds interchangeable.

## Derived concept to derived fact type

**Symptom:** A computed concept merely attaches a measure or predicate to an existing business entity.

**Test:** Scaffold the derivation using surviving entities, roles and operators. Check whether the computed thing has independent identity or additional roles; if so, entity status may be justified. Inspect every downstream dependency and constraint, including uses outside the workload.

**Change:** Attach the derivation to a fact type with `derivation: derived` and its derivation rule. Prefer a path-local expression when the computation is not reusable. Preserve source evidence and record `provenance.origin: refactor` on the changed construct and proposal ledger.

**Verify:** Grouping grain, denominator behavior, optional values, cached versus computed semantics and materialized storage assumptions. The generated model expresses the derivation and its constraints; rewriting a query alone is insufficient.

## Junction objectification

**Symptom:** An association entity mirrors a pure junction table, or several query-shaped association entities repeat the same participating roles.

**Test:** Check whether the association has its own attributes, incoming roles, independent existence or time-qualified identity. Scaffold participant traversal over surviving association facts; check spanning uniqueness before reducing arity. An attributed enrollment is not a disposable pure junction. If objectification is the only access to a needed role, record a blocked path.

**Change:** A pure association may become an elementary m:n fact type. Retain or introduce objectification when the association itself plays roles or bears attributes, with an external reference scheme over its identifying roles. Consolidate duplicated association families only when their grains agree.

**Verify:** Composite identity, role names for repeated entity types, association multiplicity, attributes and temporal qualifiers, `objectified_as` links, external uniqueness role references and participation constraints. Regenerate from the modeling skill; do not hand-edit an association away in Python.
