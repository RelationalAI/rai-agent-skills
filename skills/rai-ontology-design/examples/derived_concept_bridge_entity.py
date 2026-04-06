# NOTE: Includes ternary Property for PWL segments and derived Campaign concept —
# design patterns beyond the starter build (see rai-build-starter-ontology examples).
# Pattern: base model ontology with Sources class, Concepts, Properties, Relationships
# Key ideas: Sources nested class for table bindings; filter_by resolves FKs; ternary
# Property (PWL for Segment has Float); walrus := in entity creation; .alias() for inverse.

from relationalai.semantics import Float, Integer, Model, String

model = Model("Marketing Ad Spend")

# --- Source Tables (nested class convention) ---
class Sources:
    class marketing_ad_spend:
        class public:
            ad_placements = model.Table("MARKETING_AD_SPEND.PUBLIC.AD_PLACEMENTS")
            ad_pwl_segments = model.Table("MARKETING_AD_SPEND.PUBLIC.AD_PWL_SEGMENTS")

placements = Sources.marketing_ad_spend.public.ad_placements
segments = Sources.marketing_ad_spend.public.ad_pwl_segments

# --- Dimension Concepts (derived from source columns) ---
MarketingChannel = model.Concept("MarketingChannel", identify_by={"name": String})
model.define(MarketingChannel.new(name=placements.channel))

MarketingCampaign = model.Concept("MarketingCampaign", identify_by={"name": String})
model.define(MarketingCampaign.new(name=placements.campaign))

Country = model.Concept("Country", identify_by={"name": String})
model.define(Country.new(name=placements.country))

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

# --- AdPlacement: Properties + Relationships ---
AdPlacement = model.Concept("AdPlacement", identify_by={"pid": String})
AdPlacement.min_budget = model.Property(f"{AdPlacement} has {Float:min_budget}")
AdPlacement.max_budget = model.Property(f"{AdPlacement} has {Float:max_budget}")
AdPlacement.channel = model.Relationship(
    f"{AdPlacement} runs on {MarketingChannel}", short_name="ad_placement_channel")
AdPlacement.campaign = model.Relationship(
    f"{AdPlacement} belongs to {MarketingCampaign}", short_name="ad_placement_campaign")
AdPlacement.country = model.Relationship(
    f"{AdPlacement} is in {Country}", short_name="ad_placement_country")
AdPlacement.pwl = model.Relationship(
    f"{AdPlacement} has {PWL}", short_name="ad_placement_pwl")

# Walrus := in entity creation with inline property binding
model.define(
    ap := AdPlacement.new(pid=placements.placement_id),
    ap.min_budget(placements.min_budget),
    ap.max_budget(placements.max_budget),
)

# FK resolution via filter_by
model.define(AdPlacement.channel(MarketingChannel)).where(
    AdPlacement.filter_by(pid=placements.placement_id),
    MarketingChannel.filter_by(name=placements.channel),
)
model.define(AdPlacement.campaign(MarketingCampaign)).where(
    AdPlacement.filter_by(pid=placements.placement_id),
    MarketingCampaign.filter_by(name=placements.campaign),
)
model.define(AdPlacement.country(Country)).where(
    AdPlacement.filter_by(pid=placements.placement_id),
    Country.filter_by(name=placements.country),
)
model.define(AdPlacement.pwl(PWL)).where(
    AdPlacement.filter_by(pid=placements.placement_id),
    PWL.filter_by(pwl_id=placements.pwl_id),
)

# --- Cross-concept: PiecewiseLinearSegment (bridges AdPlacement -> PWL -> Segment) ---
PiecewiseLinearSegment = model.Concept("PiecewiseLinearSegment")
PiecewiseLinearSegment.to_ad_placement = model.Relationship(
    f"{PiecewiseLinearSegment} models {AdPlacement}", short_name="pls_placement")
PiecewiseLinearSegment.segment = model.Relationship(
    f"{PiecewiseLinearSegment} uses {Segment}", short_name="pls_segment")
PiecewiseLinearSegment.segment_length = model.Property(
    f"{PiecewiseLinearSegment} has {Float:segment_length}")
PiecewiseLinearSegment.marginal_return = model.Property(
    f"{PiecewiseLinearSegment} has {Float:marginal_return}")

# Entity creation via 3-way join: AdPlacement -> PWL -> Segment
model.define(
    PiecewiseLinearSegment.new(
        to_ad_placement=AdPlacement,
        segment=Segment,
        segment_length=segments.segment_length,
        marginal_return=segments.marginal_return,
    )
).where(
    AdPlacement.pwl(PWL),
    PWL.filter_by(pwl_id=segments.pwl_id),
    Segment.filter_by(sid=segments.segment),
)

# Inverse relationship via .alias()
AdPlacement.segments = PiecewiseLinearSegment.to_ad_placement.alias(
    f"{AdPlacement} has segment {PiecewiseLinearSegment}")
