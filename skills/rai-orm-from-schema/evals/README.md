# Testing rai-orm-from-schema

A walkthrough for running the skill end-to-end against the three benchmark fixtures, capturing outputs, and validating against the expected reference solutions.

> **Caveat:** the reference solutions in `expected/` are Claude-drafted DRAFTS pending the reviewer's line-by-line review per the Phase 1.3 lock. Until reviewed, treat them as targets-to-iterate-against, not as authoritative ground truth. See [`notes/review-list.md`](../../../notes/review-list.md) for the open review items.

---

## 1. What "testing" means here

Testing this skill means: **invoke it on a fixture, watch the SRP run end-to-end, and compare the output triple against the expected reference solution**. The skill is markdown-driven — no Python tests to run. Validation is reading-the-output level, not unit-test level.

Each test produces three artifacts:
- `model.orm.yaml` — the recovered ORM model
- `model.verbalization.txt` — Halpin-style CNL rendering
- `model.py` — PyRel translation of the confirmed YAML

These three together are what you compare against `expected/<schema>.orm.yaml`. The verbalization is the primary review surface for E5.

---

## 2. Prerequisites

| Requirement | Why | How |
|---|---|---|
| Claude Code CLI | To invoke the skill in a session | `npm i -g @anthropic-ai/claude-code` (or per the [official setup](https://docs.claude.com/claude-code)) |
| rai plugin or local skill folder | So Claude can load the skill | If you've cloned `rai-agent-skills`, the skill is at `skills/rai-orm-from-schema/`. Claude Code discovers it automatically when invoked from the repo root or via the plugin marketplace. |
| Postgres (optional) | For live-SQL testing (input kind = `sql`) | `brew install postgresql` on macOS, or any Docker image. Only needed for Step 5 sample probing on live data. |
| Internet (optional) | First-time fetch of Northwind and TPC-H DDL | Only the first time. The fixture fetch scripts pin commit hashes for reproducibility. |

---

## 3. Quick-start: smallest possible test

The fastest way to see the skill work end-to-end. Uses the [`movie_catalog` example](../examples/movie_catalog.sql) — small enough to read the full output, exercises the canonical pattern.

### Step 3.1 — Start a Claude Code session

```bash
cd /path/to/rai-agent-skills
claude
```

### Step 3.2 — Invoke the skill

In the Claude session, ask it to run the SRP on the fixture:

> Run the rai-orm-from-schema SRP against `skills/rai-orm-from-schema/examples/movie_catalog.sql`. Use One-shot mode and emit the three output files to `/tmp/movie-test/`.

Claude will:
1. Read the SKILL.md and the relevant references
2. Recognize this as a `ddl-file` input
3. Run Steps 1–10 of the SRP
4. Emit `model.orm.yaml`, `model.verbalization.txt`, `model.py` to `/tmp/movie-test/`

Expected runtime: 1–3 minutes.

### Step 3.3 — Inspect the output

```bash
ls /tmp/movie-test/
cat /tmp/movie-test/model.verbalization.txt      # primary review surface
diff /tmp/movie-test/model.orm.yaml \
     skills/rai-orm-from-schema/examples/movie_catalog.orm.yaml
```

The diff shows where Claude's run differed from the expected reference. Inspect divergences and iterate.

---

## 4. Full test cycle — all 3 fixtures, both modes

### 4.1 — Fetch the external fixtures (one-time)

```bash
cd skills/rai-orm-from-schema/evals/fixtures
bash northwind/fetch.sh
bash tpc_h/fetch.sh
# synthetic/schema.sql is hand-built and committed; no fetch needed
```

After fetch, you should have:
```
fixtures/
  northwind/schema.sql          (469 lines, DDL + ALTER TABLE)
  northwind/sample_data.sql     (3444 lines, INSERTs)
  tpc_h/schema.sql              (96 lines, DDL + spec-derived PK/FK)
  synthetic/schema.sql          (502 lines, hand-built 21 tables + sample data)
```

### 4.2 — Run each fixture, both modes

For each `<schema>` in `{movie_catalog, synthetic, northwind, tpc_h}` and each `<mode>` in `{guided, one-shot}`:

```
Run the rai-orm-from-schema SRP against <schema-path> in <mode> mode.
Emit outputs to evals/results/<YYYY-MM-DD>/<schema>-<mode>/.
```

In **Guided mode**, Claude pauses for your input at:
- **Step 0**: confirm `guided`
- **Step 6d** (opt-in): mark obvious LLM hallucinations as rejected
- **Step 9** (six substeps): confirm/reject Step 6 proposals; resolve antipattern flags; add user-supplied; label modality

In **One-shot mode**, the SRP runs end-to-end without pause. Library-tier proposals auto-confirm; LLM-tier and antipattern-default-resolutions stay `proposed` for you to edit the YAML post-hoc.

### 4.3 — Output convention

Per the cases.json convention, runs land in:

```
evals/results/<YYYY-MM-DD>/<schema>-<mode>/
  output.orm.yaml          # the recovered model
  output.verbalization.txt # CNL rendering
  output.py                # PyRel translation
  diff.md                  # E1/E2/E3/E4 verdict vs expected/<schema>.orm.yaml
```

`diff.md` is the eval-run report — Claude produces this by comparing `output.orm.yaml` against `expected/<schema>.orm.yaml` per the rubric in `cases.json`.

---

## 5. What to look for in the output

### 5.1 — Validate the YAML structurally

Every emitted `output.orm.yaml` must satisfy the 27 validation rules in [`representation-format.md`](../references/representation-format.md). Quickly:

```bash
# Smoke-test: does it parse?
python3 -c "import yaml; yaml.safe_load(open('output.orm.yaml')); print('OK')"

# Structural check (re-run the same checks the consistency pass uses):
# (You can ask Claude to run the format-spec validator from representation-format.md
# section "Validation rules" against any output file.)
```

### 5.2 — Read the verbalization

The `output.verbalization.txt` is the primary review surface. It should:
- Read like ordinary English; constraints carry provenance prefixes (`[from PK]`, `[from common-sense library, proposed]`, etc.)
- Surface antipattern flags as call-outs (`⚠ denormalized-address on Customer ...`)
- Be sufficient to validate the model **without looking at the YAML or the original schema**

If the verbalization fails this test, the model recovery has a problem with verbalization patterns rather than the underlying structure.

### 5.3 — Diff against the expected reference

```bash
diff -u evals/expected/<schema>.orm.yaml \
        evals/results/<DATE>/<schema>-<mode>/output.orm.yaml \
        | less
```

Per `cases.json` E1's equivalence rules:
- Object types match by name (modulo case)
- Fact types match by structural shape (roles in same order)
- Reading wording can differ
- Explicit-source constraints must match exactly in type, target, and provenance
- Inferred constraints judged by the correctness rubric (see PLAN.md / Activity 1)
- Declaration order and pure formatting differences are ignored

### 5.4 — Per-eval-case verdict

For each of E1–E4 in `cases.json`, mark:
- ✅ pass / ❌ fail / 🟡 partial
- For failures, write a one-line note in `diff.md` describing what diverged.

E5 (stakeholder reviewability) needs a non-PyRel reviewer — see [`reviewability_checklist.md`](reviewability_checklist.md).

---

## 6. Live-SQL testing (optional)

DDL-only testing is sufficient for E1, E2, E4 verification. **Live-SQL testing additionally exercises Step 5 sample probing** — distinct-value enumeration of encoded-enum columns, numeric ranges, NULL-rate-driven mandatory inference, frequency bounds.

### 6.1 — Load a fixture into Postgres

```bash
# One-time setup
brew install postgresql      # macOS
brew services start postgresql

# Load a fixture
createdb synthetic
psql -d synthetic -f skills/rai-orm-from-schema/evals/fixtures/synthetic/schema.sql

# Verify
psql -d synthetic -c "\dt"   # lists 21 tables
psql -d synthetic -c "SELECT COUNT(*) FROM customer;"  # 10 rows
```

### 6.2 — Run the SRP in `sql` mode

```
Run the rai-orm-from-schema SRP against the live Postgres database 'synthetic'
(connect on localhost:5432). Use Guided mode. Emit outputs to evals/results/<DATE>/synthetic-live/.
```

Claude will:
- Set `source.kind: sql, dialect: postgres`
- Query `information_schema` per `probing-strategies.md` Step 1
- Run sample probes per Step 5 — distinct values for encoded-enum columns, numeric min/max, NULL rates
- Promote sample-derived constraints from `proposed` to `confirmed` when sample size ≥ 1000 and saturation holds (won't happen for the small synthetic fixture; tiny sample sizes keep status `proposed`)

### 6.3 — Compare against the DDL-only run

The two runs (DDL-only vs live-SQL) on the same fixture should differ in:
- `source.kind`: `ddl-file` vs `sql`
- Encoded-enum value constraints: live-SQL has `provenance.sample_query` populated; DDL-only doesn't
- Status of sample-derived constraints: live-SQL with large sample → `confirmed`; DDL-only → `proposed`

If anything *else* differs (object types, fact-type structure, antipattern flags), that's a bug.

---

## 7. Testing the deontic flag (currently uncovered)

None of the three reference solutions exercises the deontic emission path. To test it manually:

1. Run any fixture in Guided mode.
2. At Step 9e (modality labelling), label one constraint `deontic` (e.g., a common-sense temporal-ordering constraint, or a user-supplied "should" rule).
3. Verify in `output.py` that the constraint emits as a `# DEONTIC NOTE:` comment, not as a `model.require()` call.

Per the consistency pass finding A4, this is a documented coverage gap. If you build a `deontic_micro` fixture in v0.2, this test becomes automatic.

---

## 8. CSV testing (degraded path)

The skill supports CSV input for prototyping. To test:

1. Convert a few synthetic-fixture tables to CSV (one per file, headers in first row):
   ```bash
   psql -d synthetic -c "COPY customer TO '/tmp/synthetic-csv/customer.csv' WITH CSV HEADER;"
   psql -d synthetic -c "COPY product TO '/tmp/synthetic-csv/product.csv' WITH CSV HEADER;"
   ```
2. Run the SRP in CSV mode:
   ```
   Run the rai-orm-from-schema SRP against the CSV files in /tmp/synthetic-csv/.
   Use One-shot mode.
   ```

Expected behaviour:
- `source.kind: csv, source.confidence: low`
- No PKs, FKs, or CHECKs in the recovered model
- Type inference from sampled values
- Step 7 may flag boolean-encoded columns and PK-candidate columns from name conventions
- All sample-derived constraints stay `proposed` — CSV input never promotes to `confirmed`

The CSV path is the most degraded; it's a stress test for "does the SRP produce a sensible partial model when half the schema info is missing?"

---

## 9. Known limitations and expected behaviour

### What the skill DOES handle (v0.1)

- DDL files in Postgres / Snowflake / MySQL / Oracle / SQLite (per `probing-strategies.md`)
- Live SQL connection (any of the above dialects)
- CSV samples (degraded `confidence: low`)
- All 13 ORM 2 constraint types
- Antipatterns: 17 detection codes per `antipattern-catalog.md`
- 4 input modes for the SRP user (Guided / One-shot, plus Step 6d opt-in spot-check)

### What the skill DOES NOT handle (v0.1)

- Multi-language readings (English only)
- Diagram rendering (no SVG/ASCII output of the ORM model)
- FORML 2 parsing (textual constraints emit as comments, not parsed)
- Cross-database FKs beyond simple flagging
- Polymorphic FKs
- Composite value types (`Address` as a record value)
- Generated-column derivation rules
- Tests in pytest format (markdown-driven only)

### What may surprise you

- **Sample size matters for promotion.** With small samples (synthetic has 10–35 rows per table), live-SQL probes don't promote to `confirmed`. They stay `proposed`. To exercise the promotion rule, load a real-scale fixture (TPC-H at SF=0.1+ or larger).
- **Step 6d is opt-in.** Even in Guided mode, if you decline the spot-check the LLM-tier proposals stay `proposed` until Step 9b.
- **Antipattern resolution defaults are conservative.** For `denormalized-address`, the default is `keep_as_is` (flag for documentation, don't restructure). For `encoded-enum-in-varchar`, the default is `promote_to_enum`. Override at Step 9c if needed.

---

## 10. Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Skill doesn't trigger when invoked | Description mismatch in your prompt | Use the exact phrase "rai-orm-from-schema" or "Schema Recovery Procedure" so the description's trigger words fire |
| Output YAML is missing object_types | The SRP halted at Step 1 (introspection failed) | Check `source.scope.probe_errors` for the actual error |
| Encoded-enum antipattern not flagged | DDL-only input: Step 5 sample probing didn't run | Run in `sql` mode against a live DB to exercise sample probing |
| `model.require()` calls fail with `[Invalid operator] Cannot use python's 'bool check'` | Translator emitted Python `and`/`or`/`not` instead of PyRel `&`/`\|`/`model.not_()` | This is a translator bug. Report it; the rule is documented in `orm-to-pyrel.md` |
| Verbalization is too long to read | Default rendering includes confirmed + proposed; rejected proposals in appendix | Ask Claude to render only the confirmed portion for your initial pass |
| TPC-H run flags antipatterns | False positive — TPC-H is the clean baseline | Investigate which flag fires; either it's a real bug or the catalog needs a tightening rule |

---

## 11. Where to put feedback

After a test cycle, capture findings in:

- `notes/phase5-dogfood-<scenario-name>.md` — per-scenario notes
- `evals/results/<DATE>/<schema>-<mode>/diff.md` — per-run E1/E2/E3/E4 verdict
- `notes/review-list.md` — for skill-level issues that should be resolved before v1-STABLE

For Activity 2 (head-to-head against `rai-build-starter-ontology`), see `notes/phase5-handoff.md` § 2.
