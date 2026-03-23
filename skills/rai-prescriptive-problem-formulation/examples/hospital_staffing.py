# Pattern: overtime/hinge variable + skill-filtered aggregation
# Key ideas: overtime >= total_hours - regular_hours (hinge/max-with-zero);
# skill-filtered coverage uses .where() condition on nurse skill level;
# unmet demand as penalty term creates soft constraint for infeasible demand.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("hospital_staffing")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Nurse = Concept("Nurse", identify_by={"id": Integer})
Nurse.name = Property(f"{Nurse} has {String:name}")
Nurse.skill_level = Property(f"{Nurse} has {Integer:skill_level}")
Nurse.hourly_cost = Property(f"{Nurse} has {Float:hourly_cost}")
Nurse.regular_hours = Property(f"{Nurse} has {Integer:regular_hours}")
Nurse.overtime_multiplier = Property(f"{Nurse} has {Float:overtime_multiplier}")
Nurse.x_overtime_hours = Property(f"{Nurse} has {Float:overtime_hours}")

Shift = Concept("Shift", identify_by={"id": Integer})
Shift.name = Property(f"{Shift} has {String:name}")
Shift.duration = Property(f"{Shift} has {Integer:duration}")
Shift.min_nurses = Property(f"{Shift} has {Integer:min_nurses}")
Shift.min_skill = Property(f"{Shift} has {Integer:min_skill}")
Shift.patient_demand = Property(f"{Shift} has {Integer:patient_demand}")
Shift.patients_per_nurse_hour = Property(f"{Shift} has {Float:patients_per_nurse_hour}")
Shift.x_patients_served = Property(f"{Shift} has {Float:patients_served}")
Shift.x_unmet_demand = Property(f"{Shift} has {Float:unmet_demand}")

Availability = Concept("Availability", identify_by={"nurse_id": Integer, "shift_id": Integer})
Availability.nurse = Property(f"{Availability} for {Nurse}")
Availability.shift = Property(f"{Availability} in {Shift}")
Availability.available = Property(f"{Availability} is {Integer:available}")

# --- Decision concept ---
Assignment = Concept("Assignment", identify_by={"availability": Availability})
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(availability=Availability))

AssignmentRef = Assignment.ref()
overflow_penalty_per_patient = 20

p = Problem(model, Float)
p.solve_for(Assignment.x_assigned, type="bin",
            name=["assigned", Assignment.availability.nurse.name, Assignment.availability.shift.name])
p.solve_for(Nurse.x_overtime_hours, type="cont", name=["ot", Nurse.name], lower=0)
p.solve_for(Shift.x_patients_served, type="cont", name=["pt", Shift.name], lower=0)
p.solve_for(Shift.x_unmet_demand, type="cont", name=["ud", Shift.name], lower=0)

# Constraint: only assign available nurses
p.satisfy(model.require(Assignment.x_assigned <= Assignment.availability.available))

# Constraint: minimum nurses per shift
shift_staff = sum(AssignmentRef.x_assigned).where(AssignmentRef.availability.shift == Shift).per(Shift)
p.satisfy(model.require(shift_staff >= Shift.min_nurses))

# Constraint: skill-filtered coverage — at least one nurse meeting skill threshold
skilled_coverage = sum(AssignmentRef.x_assigned).where(
    AssignmentRef.availability.shift == Shift,
    AssignmentRef.availability.nurse.skill_level >= Shift.min_skill,
).per(Shift)
p.satisfy(model.require(skilled_coverage >= 1))

# Constraint: overtime = hinge(total_hours - regular_hours)
total_hours = sum(AssignmentRef.x_assigned * AssignmentRef.availability.shift.duration).where(
    AssignmentRef.availability.nurse == Nurse
).per(Nurse)
p.satisfy(model.require(Nurse.x_overtime_hours >= total_hours - Nurse.regular_hours))

# Constraint: unmet demand >= demand - served (soft constraint via penalty)
p.satisfy(model.require(Shift.x_unmet_demand >= Shift.patient_demand - Shift.x_patients_served))

# Objective: minimize overtime cost + overflow penalty
overtime_cost = sum(Nurse.x_overtime_hours * Nurse.hourly_cost * Nurse.overtime_multiplier)
overflow_penalty = overflow_penalty_per_patient * sum(Shift.x_unmet_demand)
p.minimize(overtime_cost + overflow_penalty)

p.solve("highs", time_limit_sec=60)
