# E5 — Stakeholder Reviewability Checklist

The fifth eval in `cases.json` is *qualitative*: hand the recovered model to a non-PyRel stakeholder and ask whether they can validate the model by reading the verbalization alone. This file is the checklist the stakeholder fills in.

**v0.1 pass-bar:** at least one stakeholder reports they can validate without help.

---

## Setup

Before handing this to a reviewer:

1. Pick one of the three benchmark schemas (synthetic recommended — most patterns to exercise).
2. Run the SRP against it and produce the three artifacts:
   - `output.orm.yaml` — the recovered model
   - `output.verbalization.txt` — the CNL rendering (the primary review surface)
   - (optional) `output.py` — PyRel translation, for reviewers curious about downstream
3. Hand the reviewer **only the verbalization file** plus this checklist. Withhold the YAML and the original schema unless the reviewer asks. The point of E5 is that the verbalization should stand on its own.

The reviewer should NOT be familiar with PyRel, ORM 2 notation, or Halpin's textbook. Ideal: a domain expert (someone who knows the data model in business terms) without ORM/PyRel training.

---

## Reviewer instructions

Read the verbalization file end-to-end. Mark each item below with yes / no / partial. Add notes where relevant. Total time: 30–60 minutes for a ~20-table schema.

### Section 1: Comprehension

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 1.1 | Did you understand the **object types** without looking up jargon? | | |
| 1.2 | For each fact type, was it clear which entity types are involved? | | |
| 1.3 | Were **role names** (e.g., `parent`/`child`, `from`/`to`) easy to interpret? | | |
| 1.4 | Did the **subtypes** (if any) read naturally — e.g., "PhysicalProduct is a kind of Product"? | | |
| 1.5 | Were the **objectified entities** (e.g., OrderItem, Enrolment) clearly distinguished from pure relationships? | | |

### Section 2: Constraint validation

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 2.1 | Could you tell which constraints came from the **schema (PK/FK/NOT NULL)** vs which came from inference? | | |
| 2.2 | The constraint provenance prefixes (`[from PK]`, `[from common-sense library, proposed]`, etc.) — were they clear? | | |
| 2.3 | Did you encounter a **proposed constraint** that you, knowing the domain, would **reject**? Note which. | | |
| 2.4 | Did you encounter a constraint you'd want to add (a domain rule the model missed)? Note which. | | |
| 2.5 | Were **alethic** vs **deontic** constraints clearly distinguished? Did the deontic notation make sense? | | |

### Section 3: Antipattern callouts

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 3.1 | The antipattern callouts (`⚠ denormalized-address on Customer`, etc.) — did they help you spot real issues? | | |
| 3.2 | Did any antipattern flag look like a **false positive** in your domain? | | |
| 3.3 | Was the **default resolution** for each antipattern reasonable? Would you override it? | | |

### Section 4: Coverage and gaps

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 4.1 | Are there relationships between entities that you'd expect but the verbalization doesn't mention? | | |
| 4.2 | Are there constraints you take for granted that the verbalization misses? (e.g., "every Order must have at least one OrderItem") | | |
| 4.3 | Are there entities mentioned in the verbalization that **shouldn't** be there? (e.g., audit/log tables that aren't domain-meaningful) | | |
| 4.4 | Did the verbalization use any term in a way that conflicts with how you understand the domain? | | |

### Section 5: Overall reviewability verdict

| # | Question | Y/N/Partial | Notes |
|---|---|---|---|
| 5.1 | Did you need to look at the YAML, the original schema, or PyRel docs to understand the model? | | |
| 5.2 | If your engineering team translated this verbalization into a PyRel model, would you trust the translation? | | |
| 5.3 | Would you sign off on this model as-is? If no, list the **specific** items you'd want changed before sign-off. | | |

---

## Pass criteria

The model passes E5 when:
- 5.1 = "no" (reviewer didn't need the YAML or schema).
- 5.3 = "yes" *or* the changes the reviewer flags are concrete and addressable (not "everything is unclear").
- The aggregate yes-count across Sections 1–4 is high enough that the reviewer's overall confidence is high (informal — judged by the reviewer themselves).

If the reviewer flags fundamental comprehension issues (multiple "no"s in Section 1), the verbalization needs revision before E5 retests.

---

## Reviewer signature

| Field | Value |
|---|---|
| Schema reviewed | (synthetic / northwind / tpc_h) |
| Reviewer name | |
| Reviewer's domain expertise | |
| Date | |
| Pass / fail / partial | |
| Notes | |
