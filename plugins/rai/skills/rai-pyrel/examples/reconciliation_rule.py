# Pattern: Reconciliation rule — compares values from two sources and flags discrepancies.
# Key ideas: delta computation between matched records; tolerance-based discrepancy flag;
# severity classification on the delta magnitude.

from relationalai.semantics import Float, Integer, Model, String
from relationalai.semantics.std import math

model = Model("reconciliation_rule")

# --- Ontology ---

# Each Match links a record from Source A to its counterpart in Source B
Match = model.Concept("Match", identify_by={"id": Integer})
Match.source_a_amount = model.Property(f"{Match} has {Float:source_a_amount}")
Match.source_b_amount = model.Property(f"{Match} has {Float:source_b_amount}")
Match.description = model.Property(f"{Match} has {String:description}")

# --- Sample data ---
match_source = model.data([
    {"ID": 1, "SRC_A": 100.00, "SRC_B": 100.00, "DESC": "exact match"},
    {"ID": 2, "SRC_A": 250.00, "SRC_B": 249.95, "DESC": "minor delta"},
    {"ID": 3, "SRC_A": 1000.00, "SRC_B": 1150.00, "DESC": "major delta"},
    {"ID": 4, "SRC_A": 5000.00, "SRC_B": 3500.00, "DESC": "critical delta"},
])
model.define(
    m := Match.new(id=match_source.ID),
    m.source_a_amount(match_source.SRC_A),
    m.source_b_amount(match_source.SRC_B),
    m.description(match_source.DESC),
)

# --- Reconciliation Rule ---
# NL: "Flag matched records where the two source amounts differ by more than $0.01"

# Step 1: Compute delta between the two sources
Match.delta = model.Property(f"{Match} has {Float:delta}")
model.define(Match.delta(Match.source_a_amount - Match.source_b_amount))

# Step 2: Flag discrepancies exceeding tolerance
Match.has_discrepancy = model.Relationship(f"{Match} has discrepancy")
model.where(math.abs(Match.delta) > 0.01).define(Match.has_discrepancy())

# Step 3 (optional): Classify discrepancy severity
Match.discrepancy_severity = model.Property(f"{Match} has {String:discrepancy_severity}")
model.where(
    Match.has_discrepancy(),
    math.abs(Match.delta) >= 1000,
).define(Match.discrepancy_severity("critical"))
model.where(
    Match.has_discrepancy(),
    math.abs(Match.delta) >= 100,
    math.abs(Match.delta) < 1000,
).define(Match.discrepancy_severity("major"))
model.where(
    Match.has_discrepancy(),
    math.abs(Match.delta) < 100,
).define(Match.discrepancy_severity("minor"))

# --- Query results ---

from relationalai.semantics.std import aggregates

print("Discrepancies found:")
model.where(Match.has_discrepancy()).select(
    Match.id.alias("match_id"),
    Match.source_a_amount.alias("source_a"),
    Match.source_b_amount.alias("source_b"),
    Match.delta.alias("delta"),
    Match.discrepancy_severity.alias("severity"),
).inspect()

# --- Coverage check ---

total_matches = model.select((aggregates.count(Match) | 0).alias("count")).to_df().iloc[0, 0]
discrepancy_count = model.where(Match.has_discrepancy()).select(
    (aggregates.count(Match) | 0).alias("count")
).to_df().iloc[0, 0]
print(f"\nDiscrepancies: {discrepancy_count}/{total_matches}")
