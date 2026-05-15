# T-E5 — Stakeholder Reviewability Checklist (text-first)

The fifth eval is qualitative: hand the verbalization (and ONLY the verbalization) to a non-PyRel stakeholder who knows the domain. Have them fill in this checklist. Pass = at least one stakeholder reports they can validate the model without help.

This is the text-first analog of the schema skill's [reviewability_checklist.md](../../rai-orm-from-schema/evals/reviewability_checklist.md), adapted for the dialogue-driven CSDP workflow.

---

## Setup

Before handing this to a reviewer:

1. Pick one of the T-E1 fixtures (a Workbook exercise or the synthetic good-user case).
2. Run CSDP against it and produce the three artifacts.
3. Hand the reviewer **only the verbalization file** plus this checklist. The verbalization should stand on its own.

The reviewer should NOT be familiar with PyRel, ORM 2 notation, Halpin's textbook, or the original dialogue (just the verbalization). Ideal: someone who knows the modelled domain in business terms.

---

## Reviewer instructions

Read the verbalization file end-to-end. Mark each item with yes / no / partial. Add notes where relevant. Total time: 30–60 minutes for a typical CSDP output.

### Section 1: Comprehension

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 1.1 | Did you understand the **object types** without looking up jargon? | | |
| 1.2 | For each fact type, was it clear which entity types are involved and what role each plays? | | |
| 1.3 | Were **role names** (e.g., `parent`/`child`, `manager`/`employee`) easy to interpret? | | |
| 1.4 | Did the **subtypes** read naturally — e.g., "PhysicalProduct is a kind of Product"? | | |
| 1.5 | Did the **objectified entities** (where present) make sense — was it clear when a relationship became an entity in its own right (e.g., Enrolment)? | | |

### Section 2: Constraint validation

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 2.1 | Could you tell which constraints came from **user statements** (your colleagues' actual words) vs which came from inference? | | |
| 2.2 | The provenance prefixes (`[from user statement, confirmed; turn N]`, etc.) — were they clear? | | |
| 2.3 | Were **user quotes** cited inline helpful, or distracting? | | |
| 2.4 | Did you encounter a **proposed constraint** that you'd reject as wrong for the domain? Note which. | | |
| 2.5 | Did you encounter a constraint you'd want to add (a domain rule the model missed)? Note which. | | |
| 2.6 | Were **alethic** vs **deontic** constraints clearly distinguished? | | |

### Section 3: Sample populations

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 3.1 | Did the rendered sample facts (under each fact type) help you validate the structure? | | |
| 3.2 | Were the sample populations **representative** of your domain, or did they feel cherry-picked? | | |
| 3.3 | Are there obvious sample facts you'd add to make the populations more realistic? | | |

### Section 4: Halpin posture

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 4.1 | Did the verbalization read in natural language ("Each Movie has exactly one title") rather than in technical ORM/SQL jargon? | | |
| 4.2 | Were any compound facts present that should have been decomposed into separate elementary facts? | | |
| 4.3 | Did any subtype distinction feel like it was based on attributes rather than real role differences (e.g., "Manager" vs "IC" only because of salary)? | | |
| 4.4 | Were reference schemes (how each entity type is identified) clearly stated? | | |

### Section 5: Coverage and gaps

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 5.1 | Are there relationships between entities you'd expect that the verbalization doesn't mention? | | |
| 5.2 | Are there constraints you take for granted in your domain that the verbalization misses? | | |
| 5.3 | Are there entities mentioned that **shouldn't** be there (e.g., over-decomposed concepts, audit-style entities)? | | |
| 5.4 | Did the verbalization use any term in a way that conflicts with how you understand the domain? | | |

### Section 6: Overall reviewability verdict

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 6.1 | Did you need to look at the YAML, the original CSDP dialogue, or PyRel docs to understand the model? | | |
| 6.2 | If your engineering team translated this verbalization into a PyRel model, would you trust the translation? | | |
| 6.3 | Would you sign off on this model as-is? If no, list the **specific** items you'd want changed before sign-off. | | |

---

## Pass criteria

The model passes T-E5 when:
- 6.1 = "no" (reviewer didn't need the YAML, dialogue, or PyRel docs)
- 6.3 = "yes" *or* the changes the reviewer flags are concrete and addressable
- The aggregate yes-count across Sections 1–5 is high enough that the reviewer's overall confidence is high

If the reviewer flags fundamental comprehension issues (multiple "no"s in Section 1) or Halpin-posture failures (multiple "no"s in Section 4), the verbalization or the underlying CSDP run needs revision before T-E5 retests.

---

## Reviewer signature

| Field | Value |
|---|---|
| Fixture reviewed | (workbook_exercise_1 / synthetic_good_user / etc.) |
| Reviewer name | |
| Reviewer's domain expertise | |
| Date | |
| Pass / fail / partial | |
| Notes | |
