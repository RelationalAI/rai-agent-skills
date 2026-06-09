# NOTE: Includes ternary Property for PWL segments and derived Project concept —
# design patterns beyond the starter build (see rai-build-starter-ontology examples).
# Pattern: base model ontology with Sources class, Concepts, Properties, Relationships
# Key ideas: Sources nested class for table bindings; lookup resolves FKs; ternary
# Property (PWL for Segment has Float); walrus := in entity creation; .alias() for inverse.

from relationalai.semantics import Float, Integer, Model, String

model = Model("Resource Allocation")

# --- Source Tables (nested class convention) ---
class Sources:
    class resource_allocation:
        class public:
            allocations = model.Table("RESOURCE_ALLOCATION.PUBLIC.ALLOCATIONS")
            allocation_pwl_segments = model.Table("RESOURCE_ALLOCATION.PUBLIC.ALLOCATION_PWL_SEGMENTS")

allocs = Sources.resource_allocation.public.allocations
segments = Sources.resource_allocation.public.allocation_pwl_segments

# --- Dimension Concepts (derived from source columns) ---
Channel = model.Concept("Channel", identify_by={"name": String})
model.define(Channel.new(name=allocs.channel))

Project = model.Concept("Project", identify_by={"name": String})
model.define(Project.new(name=allocs.project))

Country = model.Concept("Country", identify_by={"name": String})
model.define(Country.new(name=allocs.country))

Segment = model.Concept("Segment", identify_by={"sid": Integer})
model.define(Segment.new(sid=segments.segment))

# --- PWL: ternary properties (PWL for Segment has Float) ---
PWL = model.Concept("PWL", identify_by={"pwl_id": String})
PWL.seg_len = model.Property(f"{PWL} for {Segment} has {Float:seg_len}")
PWL.slope = model.Property(f"{PWL} for {Segment} has {Float:slope}")
PWL.segment = model.Relationship(f"{PWL} has segment {Segment}")
model.define(PWL.new(pwl_id=segments.pwl_id))

# Wire PWL segment data (ternary: PWL + Segment -> Float values)
pwl = PWL.ref()
segment = Segment.ref()
model.define(
    pwl.segment(segment),
    pwl.seg_len(segment, segments.segment_length),
    pwl.slope(segment, segments.marginal_return),
).where(
    pwl.lookup(pwl_id=segments.pwl_id),
    segment.lookup(sid=segments.segment),
)

# --- Allocation: Properties + Relationships ---
Allocation = model.Concept("Allocation", identify_by={"pid": String})
Allocation.min_budget = model.Property(f"{Allocation} has {Float:min_budget}")
Allocation.max_budget = model.Property(f"{Allocation} has {Float:max_budget}")
Allocation.channel = model.Relationship(
    f"{Allocation} runs on {Channel}")
Allocation.project = model.Relationship(
    f"{Allocation} belongs to {Project}")
Allocation.country = model.Relationship(
    f"{Allocation} is in {Country}")
Allocation.pwl = model.Relationship(
    f"{Allocation} has {PWL}")

# Walrus := in entity creation with inline property binding
model.define(
    ap := Allocation.new(pid=allocs.allocation_id),
    ap.min_budget(allocs.min_budget),
    ap.max_budget(allocs.max_budget),
)

# FK resolution via lookup
allocation = Allocation.ref()
channel = Channel.ref()
model.define(allocation.channel(channel)).where(
    allocation.lookup(pid=allocs.allocation_id),
    channel.lookup(name=allocs.channel),
)
allocation = Allocation.ref()
project = Project.ref()
model.define(allocation.project(project)).where(
    allocation.lookup(pid=allocs.allocation_id),
    project.lookup(name=allocs.project),
)
allocation = Allocation.ref()
country = Country.ref()
model.define(allocation.country(country)).where(
    allocation.lookup(pid=allocs.allocation_id),
    country.lookup(name=allocs.country),
)
allocation = Allocation.ref()
pwl = PWL.ref()
model.define(allocation.pwl(pwl)).where(
    allocation.lookup(pid=allocs.allocation_id),
    pwl.lookup(pwl_id=allocs.pwl_id),
)

# --- Cross-concept: PiecewiseLinearSegment (bridges Allocation -> PWL -> Segment) ---
PiecewiseLinearSegment = model.Concept("PiecewiseLinearSegment")
PiecewiseLinearSegment.to_allocation = model.Relationship(
    f"{PiecewiseLinearSegment} models {Allocation}")
PiecewiseLinearSegment.segment = model.Relationship(
    f"{PiecewiseLinearSegment} uses {Segment}")
PiecewiseLinearSegment.segment_length = model.Property(
    f"{PiecewiseLinearSegment} has {Float:segment_length}")
PiecewiseLinearSegment.marginal_return = model.Property(
    f"{PiecewiseLinearSegment} has {Float:marginal_return}")

# Entity creation via 3-way join: Allocation -> PWL -> Segment
allocation = Allocation.ref()
pwl = PWL.ref()
segment = Segment.ref()
model.define(
    PiecewiseLinearSegment.new(
        to_allocation=allocation,
        segment=segment,
        segment_length=segments.segment_length,
        marginal_return=segments.marginal_return,
    )
).where(
    allocation.pwl(pwl),
    pwl.lookup(pwl_id=segments.pwl_id),
    segment.lookup(sid=segments.segment),
)

# Inverse relationship via .alias()
Allocation.segments = PiecewiseLinearSegment.to_allocation.alias(
    f"{Allocation} has segment {PiecewiseLinearSegment}")
