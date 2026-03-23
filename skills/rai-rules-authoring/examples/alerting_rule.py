# Pattern: SLA violation alerting — flags entities exceeding time-based thresholds.
# Key ideas: temporal comparison using datetime.period_milliseconds(); negation
# with model.not_() for "not yet resolved"; severity classification layered
# on top of the alert; missing-data handling with | fallback.

from relationalai.semantics import Date, Float, Integer, Model, String
from relationalai.semantics.std.datetime import datetime
from relationalai.semantics.std import numbers, aggregates
import relationalai.semantics as rai

model = Model("alerting_example")

# --- Ontology ---

Ticket = model.Concept("Ticket", identify_by={"id": Integer})
Ticket.subject = model.Property(f"{Ticket} has {String:subject}")
Ticket.created_at = model.Property(f"{Ticket} has {Date:created_at}")
Ticket.resolved_at = model.Property(f"{Ticket} has {Date:resolved_at}")
Ticket.sla_hours = model.Property(f"{Ticket} has {Integer:sla_hours}")
Ticket.priority = model.Property(f"{Ticket} has {String:priority}")

# --- Alerting Rule: SLA breach detection ---
# NL: "Flag open tickets that have exceeded their SLA deadline"

Ticket.is_sla_breach = model.Relationship(f"{Ticket} is SLA breach")

# Compute elapsed time in milliseconds
elapsed_ms = datetime.period_milliseconds(Ticket.created_at, datetime.now())
sla_ms = numbers.integer(Ticket.sla_hours * 3600000)

# Open (unresolved) tickets where elapsed time exceeds SLA
model.where(
    model.not_(Ticket.resolved_at),
    elapsed_ms > sla_ms,
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
    (Ticket.priority | "unknown").alias("priority"),
).inspect()

# --- Coverage summary ---

total = model.select(aggregates.count(Ticket)).to_df().iloc[0, 0]
breached = model.where(Ticket.is_sla_breach()).select(
    aggregates.count(Ticket)
).to_df().iloc[0, 0]
print(f"\nBreached: {breached}/{total}")
