# Testing rai-orm-from-text

A walkthrough for running the skill end-to-end against the benchmark dialogue fixtures, capturing outputs, and validating against the expected reference solutions.

> **Caveat:** the reference solutions in `expected/` are Claude-drafted DRAFTS pending review per the Phase 1.3 lock. Until reviewed, treat them as targets-to-iterate-against, not as authoritative ground truth.

For the schema-side companion skill's testing guide, see [`../../rai-orm-from-schema/evals/README.md`](../../rai-orm-from-schema/evals/README.md). The structure here mirrors the schema-skill testing guide; the differences are text-first-specific (dialogue fixtures instead of DDL fixtures, Halpin posture in the qualitative reviews).

---

## 1. What "testing" means here

Testing this skill means: **invoke CSDP on a dialogue fixture, walk through the steps (or run One-shot for stress testing), and compare the output triple against the expected reference solution.**

Each test produces three artifacts:
- `output.orm.yaml` — the designed ORM model
- `output.verbalization.txt` — Halpin-style CNL rendering
- `output.py` — PyRel translation

These three together are what you compare against `expected/<fixture>.orm.yaml`. The verbalization is the primary review surface for T-E5.

---

## 2. Prerequisites

| Requirement | Why | How |
|---|---|---|
| Claude Code CLI | To invoke the skill | `npm i -g @anthropic-ai/claude-code` |
| Local clone of `rai-agent-skills` | So Claude can load the skill from disk | Clone the repo; the skill is at `skills/rai-orm-from-text/` |
| A reviewer for T-E3, T-E4, T-E5 | These three evals require qualitative human judgment | You + at least one domain-expert stakeholder |

Unlike `rai-orm-from-schema`, no database or external fixture fetches are required — dialogue fixtures are plain markdown files committed to the repo.

---

## 3. Quick-start: smallest possible test

The fastest way to see the skill work. Uses the [`movie_catalog` example](../examples/movie_catalog.dialogue.md) — small enough to read the full output.

### Step 3.1 — Start a Claude Code session

```bash
cd /path/to/rai-agent-skills
claude
```

### Step 3.2 — Invoke the skill in Guided mode (the recommended way)

In the Claude session:

> Run the rai-orm-from-text CSDP. I want to model a small movie-catalog domain. Use Guided mode. I'll provide examples and answer your questions.

Claude walks you through Steps 0–7. You provide examples (you can copy from `examples/movie_catalog.dialogue.md` if you want to replicate the canonical run, or invent your own).

After Step 7f, the skill emits the three output files.

### Step 3.3 — Compare against the canonical example

```bash
diff /tmp/movie-test/model.orm.yaml \
     skills/rai-orm-from-text/examples/movie_catalog.orm.yaml
```

Differences will exist (your dialogue will diverge from the canonical) — the goal isn't byte-equality, it's structural similarity.

---

## 4. Full test cycle — fixtures × modes

### 4.1 — Fixtures

The committed fixtures (under `evals/fixtures/`) are dialogue scripts — multi-turn conversations the skill can run against:

- `workbook_exercise_1/dialogue.md` — Halpin Workbook exercise 1 (paraphrased per S12)
- `workbook_exercise_2/dialogue.md` — exercise 2
- `workbook_exercise_3/dialogue.md` — exercise 3 (exercises objectification + subtyping)
- `synthetic_good_user/dialogue.md` — synthetic "engaged user" dialogue
- (optional, future) `synthetic_sparse_user/dialogue.md`, `synthetic_novice_user/dialogue.md` — degradation tests for T-E3

Each fixture has a `README.md` with provenance (where the exercise came from, what role it plays in the eval suite).

### 4.2 — Run each fixture, both modes

For each `<fixture>` and each `<mode>` in `{guided, one-shot}`:

```
Run rai-orm-from-text against the dialogue at
skills/rai-orm-from-text/evals/fixtures/<fixture>/dialogue.md
in <mode> mode. Emit outputs to evals/results/<YYYY-MM-DD>/<fixture>-<mode>/.
```

In **Guided** mode, you (the eval runner) play the user — answering Claude's questions following the fixture's intended path. Variance is expected; the goal is to test whether Claude reaches the same structural model given the same user input.

In **One-shot** mode, the fixture is fed as a single description (concatenate the user's turns into one prompt), and Claude drafts in one pass.

### 4.3 — Output convention

Per the cases.json convention:

```
evals/results/<YYYY-MM-DD>/<fixture>-<mode>/
  output.orm.yaml          # the designed model
  output.verbalization.txt # CNL rendering
  output.py                # PyRel translation
  diff.md                  # T-E1/T-E2/T-E3/T-E4 verdict vs expected/<fixture>.orm.yaml
```

`diff.md` is the eval-run report.

---

## 5. What to look for in the output

### 5.1 — Validate the YAML structurally

```bash
python3 -c "import yaml; yaml.safe_load(open('output.orm.yaml')); print('OK')"
```

Then check format-spec compliance using the same checklist documented in [`../../rai-orm-from-schema/references/representation-format.md`](../../rai-orm-from-schema/references/representation-format.md) (27 validation rules).

### 5.2 — Read the verbalization (the heart of T-E5)

The verbalization should:
- Read like ordinary English with constraint provenance prefixes
- Cite user quotes inline for `source: explicit` and `source: user-supplied` constraints
- Render sample populations under each fact type (up to 3-5 visible)
- Surface antipattern flags where present

This is what you'd hand to a domain-expert stakeholder for T-E5.

### 5.3 — Halpin posture audit (T-E4)

Open the verbalization and check:
- **Atomic facts**: every fact type is a single atomic predicate (no "X has A, B, and C" compound)
- **No attribute thinking**: object types have roles (not "attributes" or "fields")
- **Role-based subtypes**: each subtype's emission has a role-difference justification, not "different attributes"
- **Halpin vocabulary**: fact_type, role, object_type, reference_scheme, objectification — never table/column/junction

If the verbalization uses ER vocabulary or surfaces compound facts, the skill is leaking posture. Iterate.

### 5.4 — Diff against expected

```bash
diff -u evals/expected/<fixture>.orm.yaml \
        evals/results/<DATE>/<fixture>-<mode>/output.orm.yaml \
        | less
```

Per cases.json T-E1's equivalence rules:
- Object types match by name (modulo case)
- Fact types match by structural shape; reading wording may differ
- Explicit-source constraints must match in type, target, and provenance
- Inferred constraints judged by correctness rubric
- Halpin posture honored throughout

---

## 6. Stakeholder reviewability test (T-E5)

For at least one fixture per eval cycle:

1. Run CSDP, produce the verbalization.
2. Hand the verbalization (and `evals/reviewability_checklist.md`) to a domain-expert stakeholder who knows the fixture's domain but is NOT familiar with PyRel / ORM / Halpin.
3. Have them fill in the checklist.
4. Pass = at least one stakeholder reports they can validate without help.

This is the most expensive eval — it requires a human in the loop. Schedule it once per fixture per major iteration.

---

## 7. Known limitations and expected behavior

### What CSDP DOES handle (v0.2)

- Dialogue-driven design through Halpin's seven steps + Step 0 mode opener + Step 6d LLM spot-check
- All 13 ORM 2 constraint types (uniqueness, mandatory, value, ring, frequency, etc.)
- Five-source constraint provenance with dialogue-turn audit trail
- Alethic vs deontic modality (Step 7e labels each constraint)
- Objectification (Halpin's `!` marker; junction-as-entity pattern)
- All four reference modes (popular / unit-based / general / external)
- Halpin posture: atomic decomposition, role-based subtypes, reference-scheme elicitation

### What CSDP does NOT handle (v0.2)

- **Multi-language dialogues** — English only
- **Diagram rendering** — verbalization is text-only
- **FORML 2 parsing** — textual constraints stored verbatim
- **Composite value types** (`Address` as a record) — primitives only
- **Real-time data validation** — text-first has no live data source
- **Multi-user dialogues** — one user per CSDP session in v0.2
- **Session persistence across days** — informally supported via YAML checkpoint, not formally session-aware

### What may surprise you

- **One-shot mode is significantly more degraded** than schema-first One-shot. CSDP is built around dialogue; without it, the model quality depends entirely on the richness of the initial description. Use Guided.
- **Sample-derived constraints always stay `proposed`.** Halpin samples are 5–20 facts; not enough to auto-confirm. User must explicitly confirm at Step 7b.
- **Subtype proposals are aggressively challenged.** The skill applies the Halpin role-based criterion; if a proposed subtype doesn't play roles its supertype doesn't, it gets rejected and replaced with a value enum + optional deontic policy.

---

## 8. Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Skill doesn't trigger | Description mismatch in your prompt | Use exact phrase "rai-orm-from-text" or "CSDP" |
| Verbalization is missing user quotes | The dialogue fixture didn't populate `user_quote` provenance | Add `user_quote:` fields to the relevant constraints in the YAML |
| CSDP gets stuck at Step 1 (user can't decompose into elementary facts) | Compound facts not being properly broken apart | Re-read `references/dialogue-patterns.md` Pattern 4 (decomposing compound facts) |
| Subtype emitted that shouldn't be | Halpin role-based criterion bypassed | Manually edit the YAML; flag the criterion check at Step 6 if it should fire automatically |
| LLM-tier proposes obvious hallucinations | LLM tier broader scope than expected | Use Step 6d spot-check to reject early; tighten the LLM tier's bounded scope in `references/constraint-inference.md` (Section 6c) |
| `model.require()` PyRel emission uses Python `and`/`or` | Translator bug | Report it; rule is documented in `../rai-orm-from-schema/references/orm-to-pyrel.md` |
| Verbalization uses "table" / "column" | Posture leak | Re-read `references/halpin-posture.md`; iterate on the run |

---

## 9. Where to put feedback

After a test cycle, capture findings in:

- `notes/phase5-dogfood-<scenario-name>.md` — per-scenario notes
- `evals/results/<DATE>/<fixture>-<mode>/diff.md` — per-run T-E1/T-E2/T-E3/T-E4 verdict
- `notes/review-list.md` (when one exists for v2) — for skill-level issues
