# Pattern: fixed-charge vehicle usage with big-M linking to assignments
# Key ideas: separate VehicleUsage concept tracks whether a vehicle is used (binary);
# big-M linking constraint ties usage indicator to assignment count; objective combines
# variable mileage cost + fixed activation cost.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("vehicle_scheduling")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Vehicle = Concept("Vehicle", identify_by={"id": Integer})
Vehicle.name = Property(f"{Vehicle} has {String:name}")
Vehicle.capacity = Property(f"{Vehicle} has {Integer:capacity}")
Vehicle.cost_per_mile = Property(f"{Vehicle} has {Float:cost_per_mile}")
Vehicle.fixed_cost = Property(f"{Vehicle} has {Float:fixed_cost}")

Trip = Concept("Trip", identify_by={"id": Integer})
Trip.name = Property(f"{Trip} has {String:name}")
Trip.distance = Property(f"{Trip} has {Integer:distance}")
Trip.load = Property(f"{Trip} has {Integer:load}")

# Decision concept: vehicle-trip assignment (full cross-product)
Assignment = Concept("Assignment")
Assignment.vehicle = Property(f"{Assignment} assigns {Vehicle}", short_name="vehicle")
Assignment.trip = Property(f"{Assignment} to {Trip}", short_name="trip")
Assignment.x_assigned = Property(f"{Assignment} is {Float:assigned}")
model.define(Assignment.new(vehicle=Vehicle, trip=Trip))

# Tracking concept: whether each vehicle is activated
VehicleUsage = Concept("VehicleUsage")
VehicleUsage.vehicle = Property(f"{VehicleUsage} for {Vehicle}", short_name="vehicle")
VehicleUsage.x_used = Property(f"{VehicleUsage} is {Float:used}")
model.define(VehicleUsage.new(vehicle=Vehicle))

AssignmentRef = Assignment.ref()
max_trips = 100  # big-M: upper bound on trips any vehicle can handle

p = Problem(model, Float)
p.solve_for(Assignment.x_assigned, type="bin",
            name=["assign", Assignment.vehicle.name, Assignment.trip.name])
p.solve_for(VehicleUsage.x_used, type="bin", name=["used", VehicleUsage.vehicle.name])

# Each trip assigned to exactly one vehicle
trip_cover = sum(AssignmentRef.x_assigned).where(AssignmentRef.trip == Trip).per(Trip)
p.satisfy(model.require(trip_cover == 1))

# Vehicle capacity: total load of assigned trips <= capacity
vehicle_load = sum(AssignmentRef.x_assigned * AssignmentRef.trip.load).where(
    AssignmentRef.vehicle == Vehicle).per(Vehicle)
p.satisfy(model.require(vehicle_load <= Vehicle.capacity))

# Big-M linking: if any trip assigned to vehicle, usage must be 1
vehicle_trips = sum(AssignmentRef.x_assigned).where(
    AssignmentRef.vehicle == VehicleUsage.vehicle).per(VehicleUsage)
p.satisfy(model.require(VehicleUsage.x_used * max_trips >= vehicle_trips))

# Objective: variable mileage cost + fixed activation cost
mileage_cost = sum(Assignment.x_assigned * Assignment.trip.distance * Assignment.vehicle.cost_per_mile)
activation_cost = sum(VehicleUsage.x_used * VehicleUsage.vehicle.fixed_cost)
p.minimize(mileage_cost + activation_cost)

p.solve("highs", time_limit_sec=60)
