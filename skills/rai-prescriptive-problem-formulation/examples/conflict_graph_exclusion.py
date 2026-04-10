# Pattern: conflict-graph mutual exclusion via Conflict concept + dual .ref()
# Key ideas: Conflict concept links two Machine refs; ScheduleA/ScheduleB refs enforce
# that conflicting machines cannot share a time slot; exactly-one assignment per machine.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("conflict_graph_exclusion")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Machine = Concept("Machine", identify_by={"id": Integer})
Machine.name = Property(f"{Machine} has {String:name}")
Machine.maintenance_hours = Property(f"{Machine} has {Integer:maintenance_hours}")
Machine.failure_cost = Property(f"{Machine} has {Float:failure_cost}")

TimeSlot = Concept("TimeSlot", identify_by={"id": Integer})
TimeSlot.day = Property(f"{TimeSlot} on {String:day}")
TimeSlot.crew_hours = Property(f"{TimeSlot} has {Integer:crew_hours}")
TimeSlot.cost_multiplier = Property(f"{TimeSlot} has {Float:cost_multiplier}")

# Conflict concept: pairs of machines that cannot share a slot
Conflict = Concept("Conflict")
Conflict.machine1 = Property(f"{Conflict} between {Machine}", short_name="machine1")
Conflict.machine2 = Property(f"{Conflict} and {Machine}", short_name="machine2")

# --- Decision concept: schedule assignments ---
Schedule = Concept("Schedule")
Schedule.machine = Property(f"{Schedule} for {Machine}", short_name="machine")
Schedule.slot = Property(f"{Schedule} in {TimeSlot}", short_name="slot")
Schedule.x_assigned = Property(f"{Schedule} is {Float:assigned}")
model.define(Schedule.new(machine=Machine, slot=TimeSlot))

ScheduleRef = Schedule.ref()
ScheduleA = Schedule.ref()
ScheduleB = Schedule.ref()

problem = Problem(model, Float)
x_assigned_var = problem.solve_for(
    Schedule.x_assigned,
    type="bin",
    name=["sched", Schedule.machine.name, Schedule.slot.day],
)

# Constraint: each machine scheduled exactly once
problem.satisfy(
    model.require(
        sum(ScheduleRef.x_assigned).where(ScheduleRef.machine == Machine).per(Machine)
        == 1
    )
)

# Constraint: crew hours per slot not exceeded
problem.satisfy(
    model.require(
        sum(ScheduleRef.x_assigned * ScheduleRef.machine.maintenance_hours)
        .where(ScheduleRef.slot == TimeSlot)
        .per(TimeSlot)
        <= TimeSlot.crew_hours
    )
)

# Constraint: conflicting machines cannot share the same slot (dual ref pattern)
problem.satisfy(
    model.require(ScheduleA.x_assigned + ScheduleB.x_assigned <= 1).where(
        ScheduleA.machine == Conflict.machine1,
        ScheduleB.machine == Conflict.machine2,
        ScheduleA.slot == ScheduleB.slot,
    )
)

# Objective: minimize total maintenance cost
problem.minimize(
    sum(
        Schedule.x_assigned
        * Schedule.machine.failure_cost
        * Schedule.slot.cost_multiplier
    )
)

problem.solve("highs", time_limit_sec=60)
