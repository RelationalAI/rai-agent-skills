---
name: rai-orm-conventions
description: Applies six business-entity design rules to an ORM-derived PyRel model built with rai-orm from a denormalized relational source (one concept per entity, business-named unary flag Properties, entities built where their key is complete, links for every join hint plus shared-key subtypes, fewer cleaner properties, subsetter-friendly links). Profiles the source, turns findings and client rules into rai-orm domain notes and feedback.yaml, gives Step 10 translation rules, and lints the generated model.py. Use with rai-orm when the model will feed question answering, ontology subsetting or Terra; not a replacement for rai-orm, rai-orm-from-schema or rai-orm-verify, and never edits those skills.
---

# ORM design conventions for question-answering models

## Summary

**What:** A companion to `rai-orm` (v2). The ORM skills recover one concept per table, one property per column and flags named after raw columns. This skill steers them toward a business-entity model through their documented inputs (domain notes, `feedback.yaml`, `dropped_columns`, Step 10 manual translation), then checks the result.

**Rules** (details, evidence and translation patterns in [references/conventions.md](references/conventions.md)):

| # | Rule |
|---|---|
| R1 | One concept per business entity, not per table |
| R2 | Coded columns become business-named unary flags declared as `model.Property` |
| R3 | Build an entity from where its key is complete |
| R4 | An explicit, well-named link for every join hint; subtypes where tables share a key |
| R5 | Fewer, cleaner properties: drop constant, all-null, load/audit and PII columns; business readings |
| R6 | Subsetter-friendly: links travel with the concepts they connect |

**Never** edit files of other skills, write to the source database, or read holdout workload items or natural-language questions the user has excluded.

## Inputs

- A DuckDB file and the schema holding the source tables (read-only).
- Optional: a join-hints file (lines like `a.col can be joined with b.col`), client business rules or a glossary (`If the question mentions X, it means col = 'Y'`), column descriptions.
- The workload and other inputs `rai-orm` expects.

Run the tools with the project environment that has `duckdb` (for Terra: `.venv/bin/python`); `<skill-dir>` is this skill's directory. `lint_model.py` needs only the standard library.

## Workflow

### 1. Profile the source

```sh
python <skill-dir>/tools/profile_source.py \
  --db <source.duckdb> --schema <SCHEMA> [--join-hints <hints.txt>] \
  --out <project>/conventions/source-profile.json
```

It reports, for review:
- `rule1_merge_candidates`: well-covered tables whose primary key is the same column.
- `rule2_indicator_columns`: columns whose values are only Y/N, 0/1, T/F (with the codes seen).
- `rule3_build_from_key_column`: keys whose only identifying table covers few key values, and the tables to build from instead.
- `rule4_subtype_candidates` and `rule4_join_hints`.
- `rule5_drop_candidates` with reasons `all_null`, `constant`, `audit_or_load_name`, `pii_name`. Key and join columns are never listed.

Everything is a candidate. A sample can make a column look constant or a composite key look unique; say so when presenting findings.

### 2. Draft the entity plan and rai-orm inputs

Write these into `<project>/conventions/` and, in Guided mode, review them with the user before step 3:

1. **`entity-plan.md`**: concepts with their identifier and source tables (R1, R3), subtypes (R4), links with business readings for every join hint (R4), the flag dictionary (R2), and the drop list with a reason per column (R5).
   - Flag names and meanings come **only** from client rules, glossaries or column descriptions. A coded column with no documented meaning is left as a plain property and listed under "needs meaning", never given a guessed name.
   - When sources disagree, follow the [evidence precedence](references/conventions.md#evidence-precedence): workload SQL first, then column descriptions and data, then business rules. List every conflict, and which source won, under "Evidence conflicts".
2. **`domain-notes.md`**: the rules stated as instructions to the modeling skill, plus the entity plan. Use the template in [references/conventions.md](references/conventions.md#domain-notes-template).
3. **`feedback.yaml`** in the `rai-orm` format (`version: 1`, `items:`): `merge` for each R1 group, `wrong_grain` for each R3 entity, `missing_link` for each join hint, `rename` for each flag, and `note` items for subtypes, drops and "keep business flags; do not collapse them into enums". See the [mapping](references/conventions.md#feedback-mapping).

### 3. Run rai-orm with these inputs

Start `rai-orm` (Guided unless the user asks for One-shot) with the schema, workload, `domain-notes.md` and `feedback.yaml`. Ask it to:
- register `--emitter manual:step-10` and apply the [Step 10 translation rules](references/conventions.md#step-10-translation-rules);
- record each dropped column under `dropped_columns` with its justification in `ontology-notes.md`;
- reject refactor proposals that turn flag-dictionary flags into an enum or merge them away.

### 4. Lint the generated model

```sh
python <skill-dir>/tools/lint_model.py <project>/model.py \
  [--abbrev extra,raw,tokens] [--max-properties 40] > <project>/conventions/lint.json
```

Exit code 1 means error-level findings: unary flags declared as `Relationship`, and audit or PII properties. Warnings cover raw-column names and readings, Boolean-valued flags, attributes copied onto unrelated concepts, unlinked concepts and oversized concepts.

Fix findings through `rai-orm` (new `feedback.yaml` items, then regeneration and its verification), not by hand-editing `model.py`, so the ORM YAML, state and saved passes stay consistent. Repeat until there are no errors and every remaining warning is accepted with a reason.

### 5. Report

Summarize, per rule: what the profile found, what the plan decided, what the lint shows now, and what remains (for example "needs meaning" flags, sample caveats). Note that R6 is only partly a modeling property: if a subset step still drops links between chosen concepts, that belongs in the subsetter (e.g. Terra), not in the model.
