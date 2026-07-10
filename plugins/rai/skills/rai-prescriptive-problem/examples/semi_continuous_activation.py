# Pattern: semi-continuous variables via binary activation indicator
# Key ideas: x_spend is continuous but must be 0 OR within [min_spend, max_spend];
# a binary x_active variable and two linking constraints enforce this; per-project
# budget aggregation and a global budget knapsack complete the formulation.

from relationalai.semantics import Float, Integer, Model, String, sum
from relationalai.semantics.reasoners.prescriptive import Problem

model = Model("semi_continuous_activation")
Concept, Property = model.Concept, model.Property

# --- Ontology (abbreviated) ---
Channel = Concept("Channel", identify_by={"id": Integer})
Channel.name = Property(f"{Channel} has {String:name}")
Channel.min_spend = Property(f"{Channel} has {Float:min_spend}")
Channel.max_spend = Property(f"{Channel} has {Float:max_spend}")

Project = Concept("Project", identify_by={"id": Integer})
Project.name = Property(f"{Project} has {String:name}")
Project.budget = Property(f"{Project} has {Float:budget}")

# Ternary: conversion rate per (channel, project) pair
Performance = Concept("Performance", identify_by={"channel_id": Integer, "project_id": Integer})
Performance.channel = Property(f"{Performance} via {Channel}")
Performance.project = Property(f"{Performance} for {Project}")
Performance.conversion_rate = Property(f"{Performance} has {Float:conversion_rate}")

# Decision concept: one allocation per performance pair
Allocation = Concept("Allocation", identify_by={"performance": Performance})
Allocation.x_spend = Property(f"{Allocation} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} is {Float:active}")
model.define(Allocation.new(performance=Performance))

total_budget = 45_000

problem = Problem(model, Float)
problem.solve_for(
    Allocation.x_spend,
    lower=0,
    name=[
        "spend",
        Allocation.performance.channel.name,
        Allocation.performance.project.name,
    ],
)
problem.solve_for(
    Allocation.x_active,
    type="bin",
    name=[
        "active",
        Allocation.performance.channel.name,
        Allocation.performance.project.name,
    ],
)

# --- Semi-continuous linking: spend is 0 or within [min, max] of channel ---
# Lower bound when active: spend >= min_spend * active  (0 when inactive)
problem.satisfy(model.require(Allocation.x_spend >= Allocation.performance.channel.min_spend * Allocation.x_active))
# Upper bound when active: spend <= max_spend * active  (0 when inactive)
problem.satisfy(model.require(Allocation.x_spend <= Allocation.performance.channel.max_spend * Allocation.x_active))

# Per-project budget
project_spend = sum(Allocation.x_spend).where(Allocation.performance.project == Project).per(Project)
problem.satisfy(model.require(project_spend <= Project.budget))

# Global budget
problem.satisfy(model.require(sum(Allocation.x_spend) <= total_budget))

# Objective: maximize expected conversions
problem.maximize(sum(Allocation.x_spend * Allocation.performance.conversion_rate))

problem.solve("highs", time_limit_sec=60)
