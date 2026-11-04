"""Cross-product decision concepts with constrained cartesian via `.where()`.

NOTE: Demonstrates cross-product decision concepts and constrained cartesian joins —
advanced patterns for optimization modeling beyond the starter build.

Patterns: CSV data loading, enumeration concept from a code + description pair
shared by two sources (MachineType), generated Period concept, compound identity,
cross-product decision concepts (Technician x Machine x Period) constrained via `.where()`,
`.ref()` for derived properties, conditional binary flags.
"""
from relationalai.semantics import Float, Integer, Model, String

model = Model("Machine Maintenance")

# --- Sample Data ---
machines_data = model.data([
    {"machine_id": "M1", "machine_type": "CNC", "machine_type_desc": "CNC machining center",
     "facility": "Plant-A", "location": "Chicago",
     "failure_probability": 0.12, "maintenance_duration_hours": 4},
    {"machine_id": "M2", "machine_type": "LTH", "machine_type_desc": "Lathe",
     "facility": "Plant-A", "location": "Chicago",
     "failure_probability": 0.08, "maintenance_duration_hours": 3},
    {"machine_id": "M3", "machine_type": "CNC", "machine_type_desc": "CNC machining center",
     "facility": "Plant-B", "location": "Detroit",
     "failure_probability": 0.15, "maintenance_duration_hours": 5},
])
technicians_data = model.data([
    {"technician_id": "T1", "base_location": "Chicago", "hourly_rate": 75.0, "max_weekly_hours": 40},
    {"technician_id": "T2", "base_location": "Detroit", "hourly_rate": 80.0, "max_weekly_hours": 40},
])
qual_data = model.data([
    {"technician_id": "T1", "machine_type": "CNC"},
    {"technician_id": "T1", "machine_type": "LTH"},
    {"technician_id": "T2", "machine_type": "CNC"},
])
avail_data = model.data([
    {"technician_id": "T1", "period": 1, "available": 1.0},
    {"technician_id": "T1", "period": 2, "available": 0.5},
    {"technician_id": "T2", "period": 1, "available": 1.0},
    {"technician_id": "T2", "period": 2, "available": 1.0},
])

# --- Enumeration concept: machine type ---
# The machine-type code is shared by the machines and qualifications sources, and the
# machines source folds its description in next to it (code + description pair). So it
# is a concept identified by the code, with the description as its property, populated
# from both sources -- not a String repeated on each, and never the description alone.
MachineType = model.Concept("MachineType", identify_by={"code": String})
MachineType.description = model.Property(f"{MachineType} has {String:description}")
model.define(MachineType.new(
    code=machines_data.machine_type, description=machines_data.machine_type_desc))
model.define(MachineType.new(code=qual_data.machine_type))  # code-only source, same concept

# --- Base entities ---
Machine = model.Concept("Machine", identify_by={"machine_id": String})
Machine.machine_type = model.Property(f"{Machine} has type {MachineType:machine_type}")
Machine.facility = model.Property(f"{Machine} at {String:facility}")
Machine.location = model.Property(f"{Machine} in {String:location}")
Machine.failure_probability = model.Property(
    f"{Machine} has failure probability {Float:failure_probability}")
Machine.maintenance_duration_hours = model.Property(
    f"{Machine} requires {Integer:maintenance_duration_hours} hours")
model.define(Machine.new(
    machines_data.to_schema(exclude=["machine_type", "machine_type_desc"]),
    machine_type=MachineType.lookup(code=machines_data.machine_type),
))

Technician = model.Concept("Technician", identify_by={"technician_id": String})
Technician.base_location = model.Property(f"{Technician} based in {String:base_location}")
Technician.hourly_rate = model.Property(f"{Technician} has hourly rate {Float:hourly_rate}")
Technician.max_weekly_hours = model.Property(
    f"{Technician} has max weekly hours {Integer:max_weekly_hours}")
model.define(Technician.new(technicians_data.to_schema()))

# Qualification: compound identity linking technician to machine type
Qualification = model.Concept("Qualification",
    identify_by={"technician": Technician, "machine_type": MachineType})
model.define(Qualification.new(
    technician=Technician.lookup(technician_id=qual_data.technician_id),
    machine_type=MachineType.lookup(code=qual_data.machine_type),
))

# Period: discrete planning horizon (no source table — generated)
Period = model.Concept("Period", identify_by={"pid": Integer})
model.define(Period.new(pid=model.data([{"pid": t} for t in range(1, 5)])["pid"]))

# --- Cross-product concepts for decision space ---

# TechnicianPeriod: availability per period (with derived capacity)
TechnicianPeriod = model.Concept("TechnicianPeriod",
    identify_by={"technician": Technician, "period": Period})
TechnicianPeriod.capacity_hours = model.Property(
    f"{TechnicianPeriod} has available hours {Float:capacity_hours}")

TcInit = Technician.ref()
PrInit = Period.ref()
model.define(TechnicianPeriod.new(
    technician=TcInit, period=PrInit,
    capacity_hours=avail_data.available * TcInit.max_weekly_hours
)).where(
    TcInit.technician_id == avail_data.technician_id,
    PrInit.pid == avail_data.period,
)

# TechnicianMachinePeriod: restricted to qualified pairs only
TechnicianMachinePeriod = model.Concept("TechnicianMachinePeriod",
    identify_by={"technician": Technician, "machine": Machine, "period": Period})
TechnicianMachinePeriod.same_location = model.Property(
    f"{TechnicianMachinePeriod} same location flag {Integer:same_location}")

# Constrained cross-product — only qualified (tech, machine) pairs
QualRef = Qualification.ref()
model.define(TechnicianMachinePeriod.new(
    technician=Technician, machine=Machine, period=Period
)).where(
    QualRef.technician(Technician),
    QualRef.machine_type(Machine.machine_type),  # joins through MachineType, not on text
)

# Derived property: co-location flag
TmpRef = TechnicianMachinePeriod.ref()
TmpTech = Technician.ref()
TmpMach = Machine.ref()
model.where(
    TmpRef.technician(TmpTech), TmpRef.machine(TmpMach),
    TmpTech.base_location == TmpMach.location
).define(TmpRef.same_location(1))
model.where(
    TmpRef.technician(TmpTech), TmpRef.machine(TmpMach),
    TmpTech.base_location != TmpMach.location
).define(TmpRef.same_location(0))
