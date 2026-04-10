# Pattern: semi-continuous variables via binary activation indicator
# Key ideas: x_spend is continuous but must be 0 OR within [min_spend, max_spend];
# a binary x_active variable and two linking constraints enforce this; per-campaign
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

Campaign = Concept("Campaign", identify_by={"id": Integer})
Campaign.name = Property(f"{Campaign} has {String:name}")
Campaign.budget = Property(f"{Campaign} has {Float:budget}")

# Ternary: conversion rate per (channel, campaign) pair
Effectiveness = Concept("Effectiveness", identify_by={"channel_id": Integer, "campaign_id": Integer})
Effectiveness.channel = Property(f"{Effectiveness} via {Channel}")
Effectiveness.campaign = Property(f"{Effectiveness} for {Campaign}")
Effectiveness.conversion_rate = Property(f"{Effectiveness} has {Float:conversion_rate}")

# Decision concept: one allocation per effectiveness pair
Allocation = Concept("Allocation", identify_by={"effectiveness": Effectiveness})
Allocation.x_spend = Property(f"{Allocation} has {Float:spend}")
Allocation.x_active = Property(f"{Allocation} is {Float:active}")
model.define(Allocation.new(effectiveness=Effectiveness))

total_budget = 45_000

problem = Problem(model, Float)
x_spend_var = problem.solve_for(
    Allocation.x_spend,
    lower=0,
    name=[
        "spend",
        Allocation.effectiveness.channel.name,
        Allocation.effectiveness.campaign.name,
    ],
)
x_active_var = problem.solve_for(
    Allocation.x_active,
    type="bin",
    name=[
        "active",
        Allocation.effectiveness.channel.name,
        Allocation.effectiveness.campaign.name,
    ],
)

# --- Semi-continuous linking: spend is 0 or within [min, max] of channel ---
# Lower bound when active: spend >= min_spend * active  (0 when inactive)
problem.satisfy(
    model.require(
        Allocation.x_spend
        >= Allocation.effectiveness.channel.min_spend * Allocation.x_active
    )
)
# Upper bound when active: spend <= max_spend * active  (0 when inactive)
problem.satisfy(
    model.require(
        Allocation.x_spend
        <= Allocation.effectiveness.channel.max_spend * Allocation.x_active
    )
)

# Per-campaign budget
campaign_spend = sum(Allocation.x_spend).where(
    Allocation.effectiveness.campaign == Campaign).per(Campaign)
problem.satisfy(model.require(campaign_spend <= Campaign.budget))

# Global budget
problem.satisfy(model.require(sum(Allocation.x_spend) <= total_budget))

# Objective: maximize expected conversions
problem.maximize(sum(Allocation.x_spend * Allocation.effectiveness.conversion_rate))

problem.solve("highs", time_limit_sec=60)
