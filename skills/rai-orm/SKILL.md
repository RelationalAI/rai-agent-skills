---
name: rai-orm
description: Entry point for building an ORM 2 conceptual model and its PyRel translation from whatever the user has — a relational schema, a domain description, and optionally a workload (SQL query logs, natural-language questions, or question+SQL pairs) — by choosing the route through the ORM skills and sequencing them. Use when the user wants an ORM-staged model and it is not yet clear which ORM skill applies, or when a workload is available to drive and verify the model — not for the modeling procedures themselves (rai-orm-from-schema, rai-orm-from-text), workload evidence extraction (rai-orm-from-workload), or the PyRel rewrite check (rai-orm-verify).
---

# ORM Modeling — Entry Point and Router
<!-- v1-SENSITIVE -->

## Summary

**What:** A thin router over the ORM skills. It finds out which inputs the user has, picks one route, sets the interaction mode once, and runs the skills of that route in order. It does no modeling of its own: every modeling decision is made inside the skill that owns it.

**When to use:**
- The user wants an ORM 2 model (and its PyRel translation) and has not said which ORM skill to use
- The user has a workload — SQL query logs, natural-language questions, or question+SQL pairs — besides a schema or a description
- The user wants proof that the model can answer their questions, not only that it loads

**When NOT to use:**
- The route is already known and has no workload — go straight to `rai-orm-from-schema` or `rai-orm-from-text`
- Greenfield builds that go direct to PyRel without an ORM stage — see `rai-build-starter-ontology`
- Enriching or reviewing a PyRel model that already loads and queries — see `rai-ontology-design`
- Deciding which reasoner answers a business question — see `rai-discovery`

**Overview:**
1. Intake — list what the user has
2. Choose the mode once (Guided or One-shot)
3. Pick the route from the routing table
4. Run the skills of the route in order, passing each one's outputs to the next
5. Close with one summary across the route

## Quick Reference

**The ORM skills:**

| Skill | Job | Runs |
|---|---|---|
| `rai-orm-from-schema` | Schema Recovery Procedure (SRP): schema → ORM model → PyRel | modeling |
| `rai-orm-from-text` | Halpin's CSDP as a dialogue: description → ORM model → PyRel | modeling |
| `rai-orm-from-workload` | Workload → `workload.digest.yaml`, evidence the modeling skills take as proposals | before modeling |
| `rai-orm-verify` | Rewrites the workload in PyRel against the model and repairs the model until it can | after modeling |

**Workload modalities:**

| Modality | What the user gives | Used as evidence for | Verification oracle |
|---|---|---|---|
| `sql` | Query logs, no questions | joins, row grain, enum-like filters, repeated expressions | the SQL result on the source data |
| `questions` | Natural-language questions, no SQL | business terms, synonyms, expected concepts | the user reviews a sample |
| `pairs` | Question+SQL pairs, kept together | all of the above plus which phrase means which column, join or filter | the SQL result, plus the question's wording |

Pairs are never split into separate question and SQL lists. The alignment between the two halves is the part neither half carries alone.

**Routing table:**

| The user has | Route |
|---|---|
| Schema (live DB, DDL, CSV), no workload | `rai-orm-from-schema` |
| Description only, no schema, no workload | `rai-orm-from-text` |
| Schema + workload (any modality) | `rai-orm-from-workload` → `rai-orm-from-schema` → `rai-orm-verify` |
| Description + questions, no schema | `rai-orm-from-text` (questions enter CSDP Step 1 as artifacts) → `rai-orm-verify` |
| Schema + description | `rai-orm-from-schema`; the description is offered at SRP Step 9d as user-supplied rules |
| SQL or pairs, but no schema | Ask for the DDL or a connection. A model is not recovered from queries alone in v0.1. |
| A PyRel model that already loads | Not an ORM route — see `rai-ontology-design` |

## Instructions

### Step 1 — Intake

Ask once, in one message, which of these the user has. Do not ask about items the user already mentioned.

> *To pick the right path I need to know what you have:*
> - *a schema: a live database connection, a DDL file, or CSV samples?*
> - *a written description of the domain, a glossary, or documentation?*
> - *a workload: SQL queries people run, questions people ask, or questions with their SQL?*
> - *is the data reachable, so queries can be run read-only?*

Record the answers. Two of them change later behavior:
- **Is the data reachable?** It decides the verification oracle in `rai-orm-verify` (execution match, or a structural check).
- **Will part of the workload be used later to evaluate the model or a system built on it?** If yes, only the remaining part may be given to the ORM skills. Say so and ask the user to hand over only that part.

### Step 2 — Mode, chosen once

Ask the Guided / One-shot question of the first modeling skill on the route (SRP Step 0 or CSDP Step 0). Default to Guided. The choice holds for the whole route: each skill on the route records it in `source.mode` and skips its own Step 0.

### Step 3 — Route

Pick the first matching row of the routing table and tell the user the route in one line before starting, for example: *"Route: workload evidence, then schema recovery, then the PyRel rewrite check."*

### Step 4 — Run the route

Run each skill to completion before the next. Hand-offs:

| From | To | What is passed |
|---|---|---|
| `rai-orm-from-workload` | `rai-orm-from-schema` | `workload.digest.yaml` (optional SRP input) |
| `rai-orm-from-workload` | `rai-orm-from-text` | the digest's `terms` (CSDP Step 1 artifacts) |
| `rai-orm-from-schema` / `rai-orm-from-text` | `rai-orm-verify` | `model.orm.yaml`, `model.py`, and the same workload file |
| `rai-orm-verify` | the modeling skill | model defects, as proposals with `source: workload`, committed through SRP Step 9f or CSDP Step 7f |

The loop between `rai-orm-verify` and the modeling skill is owned by `rai-orm-verify`; this skill only starts it.

### Step 5 — Close

One summary for the route: the model's counts (object types, fact types, constraints by source), and, when a workload was given, the verification result (items rewritten in PyRel, items verified, residual by failure class). State plainly what was not verified.

## Common Pitfalls

| Mistake | Cause | Fix |
|---|---|---|
| Modeling inside this skill | Treating the router as a procedure | Hand off; this skill has no Step that edits the YAML |
| Splitting pairs into two lists | Treating pairs as two inputs | Pass the pairs file as is, with modality `pairs` |
| Asking the mode question at every skill | Each skill has its own Step 0 | Ask once at Step 2; later skills inherit it |
| Feeding evaluation items to the modeling | The user gave the whole file | Ask at intake; pass only the part not held back for evaluation |
| Skipping `rai-orm-verify` because the model loads | "Loads and lints" taken as done | With a workload, the route ends at the rewrite check |

## Examples

| Situation | Route taken |
|---|---|
| A warehouse with DDL, no declared keys, and a query history export | `rai-orm-from-workload` (`sql`) → `rai-orm-from-schema` → `rai-orm-verify` (execution match) |
| A warehouse with DDL and 100 golden question+SQL pairs | `rai-orm-from-workload` (`pairs`) → `rai-orm-from-schema` → `rai-orm-verify` (execution match, 20% of the pairs held out of the repair loop) |
| A domain description and a list of questions the business wants answered | `rai-orm-from-text` → `rai-orm-verify` (user reviews a sample) |
| A DDL file only | `rai-orm-from-schema` |
