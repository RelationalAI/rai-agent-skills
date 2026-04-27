# Pattern: SLA violation alerting — flags entities exceeding threshold-based conditions.
# Key ideas: comparing measured elapsed value to a per-entity threshold; negation
# with model.not_() for "not yet resolved"; severity classification layered
# on top of the alert.

from relationalai.semantics import Integer, Model, String
from relationalai.semantics.std import aggregates

model = Model("alerting_rule")

# --- Ontology ---

Ticket = model.Concept("Ticket", identify_by={"id": Integer})
Ticket.subject = model.Property(f"{Ticket} has {String:subject}")
Ticket.elapsed_hours = model.Property(f"{Ticket} has {Integer:elapsed_hours}")
Ticket.sla_hours = model.Property(f"{Ticket} has {Integer:sla_hours}")
Ticket.resolved = model.Relationship(f"{Ticket} is resolved")
Ticket.priority = model.Property(f"{Ticket} has {String:priority}")

# --- Sample data ---
ticket_source = model.data([
    {"ID": 1, "SUBJECT": "Login broken",   "ELAPSED": 40,  "SLA": 24,  "RESOLVED": False, "PRIORITY": "critical"},
    {"ID": 2, "SUBJECT": "Slow dashboard", "ELAPSED": 60,  "SLA": 48,  "RESOLVED": False, "PRIORITY": "high"},
    {"ID": 3, "SUBJECT": "Typo in UI",     "ELAPSED": 20,  "SLA": 168, "RESOLVED": False, "PRIORITY": "low"},
    {"ID": 4, "SUBJECT": "Fixed already",  "ELAPSED": 100, "SLA": 24,  "RESOLVED": True,  "PRIORITY": "high"},
])
model.define(
    t := Ticket.new(id=ticket_source.ID),
    t.subject(ticket_source.SUBJECT),
    t.elapsed_hours(ticket_source.ELAPSED),
    t.sla_hours(ticket_source.SLA),
    t.priority(ticket_source.PRIORITY),
)
model.where(ticket_source.RESOLVED == True).define(
    Ticket.filter_by(id=ticket_source.ID).resolved()
)

# --- Alerting Rule: SLA breach detection ---
# NL: "Flag open tickets where elapsed time exceeds SLA"

Ticket.is_sla_breach = model.Relationship(f"{Ticket} is SLA breach")

# Open (unresolved) tickets where elapsed exceeds SLA
model.where(
    model.not_(Ticket.resolved()),
    Ticket.elapsed_hours > Ticket.sla_hours,
).define(Ticket.is_sla_breach())

# --- Severity classification on breached tickets ---
# NL: "Critical-priority breaches are urgent; all others are warnings"

Ticket.breach_severity = model.Property(f"{Ticket} has {String:breach_severity}")

model.where(
    Ticket.is_sla_breach(),
    Ticket.priority == "critical",
).define(Ticket.breach_severity("urgent"))

model.where(
    Ticket.is_sla_breach(),
    Ticket.priority != "critical",
).define(Ticket.breach_severity("warning"))

# --- Query breached tickets ---

print("SLA breaches:")
model.where(Ticket.is_sla_breach()).select(
    Ticket.id.alias("ticket_id"),
    Ticket.subject.alias("subject"),
    Ticket.breach_severity.alias("severity"),
    Ticket.priority.alias("priority"),
).inspect()

# --- Coverage summary ---

total = model.select((aggregates.count(Ticket) | 0).alias("count")).to_df().iloc[0, 0]
breached = model.where(Ticket.is_sla_breach()).select(
    (aggregates.count(Ticket) | 0).alias("count")
).to_df().iloc[0, 0]
print(f"\nBreached: {breached}/{total}")
