# Ontology Examination

Guidance for producing a descriptive inventory of an ontology model — both its modeled content and available unmapped data.

## Model Description Principles
When describing an ontology model:
- Focus on what's useful for optimization: numeric properties (costs, quantities, capacities, rates), structural relationships, existing rules/constraints
- Use domain language, not technical model language (e.g., "Campaign represents ad campaigns with budget and targeting" not "Campaign concept with 5 properties")
- Include relationship semantics (madlib descriptions) when available — these convey domain meaning better than raw relationship names
- Highlight numeric properties by name — these are the building blocks for objective functions and constraint bounds
- Note existing model rules and uniqueness constraints — these encode business logic that formulation must respect

## Unmapped Data Classification
When examining unmapped data (columns in source tables not yet modeled in the ontology), classify them into these categories:

### Optimization-Relevant Numerics
Numeric/quantitative columns useful for optimization — costs, quantities, capacities, rates, weights, scores. Group by theme.
- Example: "8 cost/quantity columns across Shipment and Operation (unit_cost, quantity, weight)"

### Relationship Candidates
FK/ID columns suggesting missing relationships between concepts. Group by target entity pattern.
- Example: "5 FK columns pointing to Customer, Site, SKU (customer_id in 3 tables, site_id in 2 tables)"

### Temporal Columns
Date/timestamp columns available for time-based filtering or temporal analysis.
- Example: "12 date columns across 6 tables (order_date, ship_date, due_date patterns)"

### Not-Needed Patterns
Audit/metadata columns that can likely be ignored for optimization: created_by, updated_at, row_hash, ETL timestamps.

## Classification Principles
- Provide PATTERN-LEVEL summaries, not per-column enumeration
- Group columns by theme/purpose
- Include counts and representative table.column examples for each pattern
- Focus on what's actionable for optimization: numerics and relationships matter most
- If there are no unmapped columns, say so explicitly
