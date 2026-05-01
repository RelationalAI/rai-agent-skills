# NOTE: Includes ternary Property for PWL segments and derived Project concept —
# design patterns beyond the starter build (see rai-build-starter-ontology examples).
# Pattern: base model ontology with Sources class, Concepts, Properties, Relationships
# Key ideas: Sources nested class for table bindings; filter_by resolves FKs; ternary
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
PWL.segment = model.Relationship(f"{PWL} has segment {Segment}", short_name="pwl_segment")
model.define(PWL.new(pwl_id=segments.pwl_id))

# Wire PWL segment data (ternary: PWL + Segment -> Float values)
model.define(
    PWL.segment(Segment),
    PWL.seg_len(Segment, segments.segment_length),
    PWL.slope(Segment, segments.marginal_return),
).where(
    PWL.filter_by(pwl_id=segments.pwl_id),
    Segment.filter_by(sid=segments.segment),
)

# --- Allocation: Properties + Relationships ---
Allocation = model.Concept("Allocation", identify_by={"pid": String})
Allocation.min_budget = model.Property(f"{Allocation} has {Float:min_budget}")
Allocation.max_budget = model.Property(f"{Allocation} has {Float:max_budget}")
Allocation.channel = model.Relationship(
    f"{Allocation} runs on {Channel}", short_name="allocation_channel")
Allocation.project = model.Relationship(
    f"{Allocation} belongs to {Project}", short_name="allocation_project")
Allocation.country = model.Relationship(
    f"{Allocation} is in {Country}", short_name="allocation_country")
Allocation.pwl = model.Relationship(
    f"{Allocation} has {PWL}", short_name="allocation_pwl")

# Walrus := in entity creation with inline property binding
model.define(
    ap := Allocation.new(pid=allocs.allocation_id),
    ap.min_budget(allocs.min_budget),
    ap.max_budget(allocs.max_budget),
)

# FK resolution via filter_by
model.define(Allocation.channel(Channel)).where(
    Allocation.filter_by(pid=allocs.allocation_id),
    Channel.filter_by(name=allocs.channel),
)
model.define(Allocation.project(Project)).where(
    Allocation.filter_by(pid=allocs.allocation_id),
    Project.filter_by(name=allocs.project),
)
model.define(Allocation.country(Country)).where(
    Allocation.filter_by(pid=allocs.allocation_id),
    Country.filter_by(name=allocs.country),
)
model.define(Allocation.pwl(PWL)).where(
    Allocation.filter_by(pid=allocs.allocation_id),
    PWL.filter_by(pwl_id=allocs.pwl_id),
)

# --- Cross-concept: PiecewiseLinearSegment (bridges Allocation -> PWL -> Segment) ---
PiecewiseLinearSegment = model.Concept("PiecewiseLinearSegment")
PiecewiseLinearSegment.to_allocation = model.Relationship(
    f"{PiecewiseLinearSegment} models {Allocation}", short_name="pls_allocation")
PiecewiseLinearSegment.segment = model.Relationship(
    f"{PiecewiseLinearSegment} uses {Segment}", short_name="pls_segment")
PiecewiseLinearSegment.segment_length = model.Property(
    f"{PiecewiseLinearSegment} has {Float:segment_length}")
PiecewiseLinearSegment.marginal_return = model.Property(
    f"{PiecewiseLinearSegment} has {Float:marginal_return}")

# Entity creation via 3-way join: Allocation -> PWL -> Segment
model.define(
    PiecewiseLinearSegment.new(
        to_allocation=Allocation,
        segment=Segment,
        segment_length=segments.segment_length,
        marginal_return=segments.marginal_return,
    )
).where(
    Allocation.pwl(PWL),
    PWL.filter_by(pwl_id=segments.pwl_id),
    Segment.filter_by(sid=segments.segment),
)

# Inverse relationship via .alias()
Allocation.segments = PiecewiseLinearSegment.to_allocation.alias(
    f"{Allocation} has segment {PiecewiseLinearSegment}")
