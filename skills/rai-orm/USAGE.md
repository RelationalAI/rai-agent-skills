# Usage guide: the rai-orm v2 family

## What the family does and when to use it

The family turns a database schema or domain description into an ORM 2 conceptual model and its PyRel translation. ORM here means Object-Role Modeling: named business concepts, facts, identifiers and constraints that you can review in plain English. With a workload, the family checks whether the model can answer your questions, repairs general defects and assesses whether the ontology can be simplified while preserving checked answers.

Start with `rai-orm` when you want the whole flow or want to improve an existing ORM model. The router selects the owning skills, keeps their state and reports remaining work. Use `rai-orm-from-schema` directly for schema recovery without a workload, or `rai-orm-from-text` for domain dialogue without a schema. For an existing PyRel file without ORM YAML, use the [manual recovery path](references/hot-start.md#python-without-yaml) or `rai-ontology-design`.

These are agent skills with local helper tools, not a single command that automatically builds and verifies an ontology. Ask your agent to run the family. Guided mode is the default: you review concrete modeling proposals. One-shot produces a draft with review markers; successful query checks do not confirm inferred business rules. Text-first One-shot depends especially heavily on the detail in your description.

## What you give it

| Input | What to provide |
| --- | --- |
| Database schema or live connection | DDL files and dialect, or read-only connection access and the schema/table scope. CSV samples are also accepted, with lower confidence because declared keys and constraints are absent. |
| Optional workload | SQL statements/history exports, one question per line, or JSON/CSV question-and-SQL pairs. Keep each pair together. Prefer explicit, stable item IDs unique across all workload files. |
| Optional domain notes | Glossaries, business rules, requirements and explanations of identifiers, row grain and distinct source populations. With schema plus notes, the schema route remains the starting point. |
| Existing project, for resume | ORM YAML, generated Python, bindings, emitter, workload/digests, verification and saved rewrites, state, reports and any feedback. Preserve their paths. |

Use your real data first. A read-only sample of your real rows can make probes and checks faster; tell the agent whether to use a sample or the full source and record the scope. Sampling affects the strength of the evidence, especially overlap and uniqueness. DDL alone supplies structure, not executed answer checks. The model must be bound to reachable source data before SQL/PyRel result comparison is possible.

SQL without a schema is insufficient for model recovery: provide DDL or a connection. With no schema, a domain description and questions can drive the text route. Questions prompt examples and vocabulary; their repetition does not establish a business fact.

A starting prompt:

```text
Run rai-orm in Guided mode on schema.sql and workload.pairs.json.
Use domain-notes.md for business vocabulary and rules. Use a read-only
sample of my real data for speed. Keep the holdout sealed from modeling.
Write the model and resumable artifacts in this project directory.
```

## End-to-end flow

The order matters. For a new schema-and-workload project, use:

1. **`rai-orm` entry point.** Check for existing YAML/state before intake. Choose or inherit Guided/One-shot and invocation budgets. The defaults are five verify repair attempts, two refactor acceptance attempts and patience of two attempts without repair-pass improvement; `until_pass` defaults to false.
2. **Choose `rai-orm-from-schema` or `rai-orm-from-text`.** Schema plus domain notes uses schema recovery; description without schema uses domain dialogue. This selects the modeling route; construction follows the workload preparation below.
3. **`rai-orm-from-workload` digest, when a workload exists.** Save the repair/holdout assignments before exposing evidence to modeling. For a new workload of at least 30 items, sort IDs and hold out every fifth item (20%); smaller workloads have no holdout. Extract only repair evidence for modeling. Keep an aggregate digest for inventory/reporting and a separate holdout digest for measurement. The tool extracts SQL structure; the agent supplies question terms and pair alignments. Evidence proposes joins, grain checks, vocabulary and derived facts; unused tables are never pruned just because the workload ignores them.
4. **Build through the selected modeling skill.** Review identifiers, facts, constraints and provenance; emit `model.orm.yaml`, `model.verbalization.txt` and the PyRel model. Schema recovery commits through Step 9f and translates at Step 10; text modeling commits through Step 7f and translates at Step 8. Register state once paths, inputs and emission method are known. The initial PyRel translation is unbound: add source-data bindings using `rai-pyrel-coding` before execution verification, and register the binding files.
5. **Connectivity.** Check entity paths and workload-required joins using the repair digest. Review data-tested link proposals, commit supported links through the modeling skill, regenerate and recheck. Preserve source bindings. Justify any remaining islands in the notes; a justification cannot clear a workload-required gap.
6. **`rai-orm-refactor:assess`.** Measure the current model and list suspects without changing it or consuming rounds. Current metrics carrying the plan's model revision allow this assessment to be skipped.
7. **`rai-orm-verify`.** Rewrite unresolved workload items, name the oracle, classify failures, repair general defects through the owning modeling skill and regenerate. Run saved passing rewrites unchanged as regression checks. Recheck connectivity each round. Holdout checks measure generalization and never select repairs.
8. **`rai-orm-refactor:accept`.** Review supported compaction proposals and their paths through existing elements. Commit candidate changes through the modeling skill, regenerate and hand them back to verification. Accept only with every unchanged baseline-passing ID preserved, unchanged oracle/weak accounting/exclusions and no total or per-split pass loss. Otherwise restore the complete snapshot. This uses the separate refactor allowance.
9. **Report.** Save `state.py plan` output, pass it to `report.py`, show `orm-report.md` and record the report paths/stop reason in state. Report the oracle, this invocation's rounds, cumulative rounds and residual issues. A budget stop with blockers is incomplete.

After model construction, the saved plan's exact order is **connectivity → `rai-orm-refactor:assess` → `rai-orm-verify` → `rai-orm-refactor:accept` → report**. Candidate changes return through modeling, connectivity and verification as needed. Without a workload, skip digest extraction and verification; refactor can measure/propose but cannot accept compaction without a usable verification baseline.

## Files and what each is for

Files appear as the corresponding steps run; a route without a workload does not have verification artifacts. Paths can be registered explicitly instead of using the defaults.

| File | Purpose |
| --- | --- |
| `model.orm.yaml` | Canonical model: concepts, fact types, identifiers, constraints, source bindings and proposal provenance/status. Make conceptual changes here through the modeling skill. |
| `model.verbalization.txt` | Plain-English review of facts and constraints for domain experts. |
| `model.py` or the recorded existing Python path | Generated PyRel model. Preserve/recheck data bindings on regeneration; do not create a second model file on resume. |
| Project emitter, if one exists | The recorded command/dependencies that regenerate the Python from YAML. It is discovered in the project, not automatically created by the family. Skill-built models can instead register `manual:step-10` and use the manual checklist. |
| `workload.digest.yaml`, `repair.digest.yaml`, `holdout.digest.yaml` | Count-only structural evidence, item contributions and inventory; repair evidence drives modeling/connectivity, holdout evidence is sealed measurement. |
| `model.verification.json`, `verification/<item-id>.py` | Per-item statuses, oracle, split assignments, round history and accepted rewrites. Saved passes become regression checks and query examples. |
| `connectivity.json`, `connectivity.proposals.yaml` | Graph components, isolated concepts, required gaps, tested overlap counts and proposed links. |
| `compaction.before.json`, `compaction.after.json` | Before/after counts, support scan coverage and ranked compaction hints. Current assessment metrics record `model_revision`. |
| `refactor-proposals.yaml`, `refactor-paths.md` | Proposal dispositions/provenance and existing-element path scaffolds. Scaffolds are reasoning aids, not executed equivalence proofs. |
| `orm-state.json` | Manifest of registered paths/hashes, mode, budgets, emitter check, finished steps, revisions, frozen passes and processed feedback. Its format version is 1. |
| `.orm-workloads/`, `.orm-facts/` | Immutable private workload snapshots and fact-fingerprint snapshots needed for safe deltas/regeneration tracking. Workload snapshots retain original source content; preserve them locally. |
| `orm-plan.json` | Saved read-only resume plan for reporting: ordered next steps, blockers and allowances. |
| `orm-report.md`, `orm-report.json` | Customer-readable statistics/issues and the same information in machine-readable form. They supplement verification history. |
| `feedback.yaml` | Structured user proposals: missing links, wrong grain, merge/split/rename, failing item IDs, compact requests or notes. |
| `feedback.md`, `feedback.processed.yaml` | Optional free-text feedback and the agent's reviewed structured conversion. The tool does not interpret prose itself. |
| `ontology-notes.md` | Reasons for keeping concepts, justified business islands, dropped-column decisions, pending evidence and verification limits. |

Digests and summary reports omit question text, SQL literals and result rows. This does not make the whole project content-free: original workloads, snapshots, generated code and domain artifacts may contain source content. See the diagnostic limitation below before sharing state.

## Hot start and resume

Run tools from the project directory with its Python environment. In the commands below, `SKILLS` is the absolute path to the installed repository's `skills` directory. Keep all registered project artifacts inside the manifest's directory; paths resolve relative to that directory. Use the existing generated model path.

**Plan first.** `plan` writes nothing and also works with YAML but no manifest as bootstrap discovery. Supply named paths when they differ from defaults:

```sh
SKILLS=/path/to/rai-agent-skills/skills
python "$SKILLS/rai-orm/tools/state.py" plan \
  --state orm-state.json --model-yaml model.orm.yaml --model-py model.py \
  --feedback feedback.yaml
```

Omit `--feedback` if there is no feedback file. Inspect `blockers`, `can_resume`, `steps` and `baseline_model_revision`; a zero exit status from planning does not mean candidates may be applied.

For structured feedback, use the model's exact concept names and existing workload IDs. For example, a missing-link request in `feedback.yaml` has this shape:

```yaml
version: 1
items:
  - id: link_review
    kind: missing_link
    from: Order
    to: Customer
```

Replace the concept names with those in your model. This requests investigation; it does not assert a relationship. Free-text `feedback.md` is read by the agent and converted into reviewed `feedback.processed.yaml`. Guided reviews the structured batch before application; One-shot retains proposal/review markers and automatically applies only supported required-gap connectivity proposals. Mark feedback processed only after review and a recorded disposition, keeping pending proposals visible.

**Initialize once.** For existing YAML without state, preserve all artifacts, discover the actual emitter and register every input it reads. This example assumes the named artifacts and binding file already exist:

```sh
python "$SKILLS/rai-orm/tools/state.py" init \
  --input schema.sql --workload workload.pairs.json --mode guided \
  --model-yaml model.orm.yaml --model-py model.py --binding bindings.py \
  --digest workload.digest.yaml --repair-digest repair.digest.yaml \
  --holdout-digest holdout.digest.yaml --verification model.verification.json \
  --emitter 'python emit_model.py --model model.orm.yaml --out model.py' \
  --rounds-per-invocation 5 --refactor-rounds 2 --patience 2
```

Substitute the project's actual emitter; omit unused artifact flags. Register additional emitter code with repeated `--emitter-file` and configuration/evidence inputs with repeated `--binding`. Registration checks a real emitter in a temporary sandbox copy: unchanged Python must reproduce byte-for-byte and YAML/digests must remain unchanged. Resolve `EMITTER_UNVERIFIED` or `EMITTER_NOT_IDEMPOTENT` before application. For a skill-built model without a script, use `--emitter manual:step-10`; this is a recorded manual translation procedure, not a runnable command. Never overwrite state with `init`.

**Update after accepted work.** The agent records finished steps with `update --skill ...`. Begin a fresh invocation once, preserving history:

```sh
python "$SKILLS/rai-orm/tools/state.py" update \
  --skill rai-orm --start-invocation
```

Defaults/inherited settings apply unless changed explicitly at invocation start. Verify attempts and refactor accept/rollback attempts spend their own allowances; assessment and baseline checks cost no rounds. `--until-pass` ignores the finite verify allowance, but patience still stops the run and unreviewed questions remain unverified.

**Recheck the baseline and freeze the split.** Preserve every surviving item's repair/holdout assignment, oracle, accepted rewrite and round history. If model/bindings changed, or legacy verification has no exact revision match, re-run saved passes with the original oracle before accepting candidates. Record the successfully checked revision in verification. The resumed baseline is the existing global round N (N+0); next repairs start at N+1. Snapshot YAML, generated files, verbalization, bindings, verification, digests and rewrites together for rollback.

**Respect the regeneration gate.** Changes to applied facts must be present in the generated Python as whole IDs/readings or the emitter's property declarations. Metadata-only edits may leave Python unchanged; removal/rejection of emitted facts must change its hash. `EMITTER_INCOMPLETE` names missing facts. Use the actual emitter's metadata schema; the hot-start reference describes `pyrel: {owner, property, type}` for emitters using that shape. With `manual:step-10`, validate YAML, refresh verbalization, translate the whole model to the recorded Python path, preserve bindings/review markers, check declarations and re-run saved passes before the modeling/verification updates.

**Handle regressions explicitly.** Ordinary verify repairs can accept a round with lost passes only when non-weak fixes exceed regressions. Record lost items as `fail` with `regressed_at_round`, fixes with `passed_at_round` and matching round counts, then use:

```sh
python "$SKILLS/rai-orm/tools/state.py" update \
  --skill rai-orm-verify --accept-regressions
```

Without that flag, a lost baseline pass blocks update; the flag does nothing when no passes were lost. Equal or greater regressions require rollback. Accepted losses remain `REGRESSED_ITEM` blockers to restore first. The exception never applies to refactor: every unchanged baseline pass must survive. Verified rename/removal/merge migrations use separate candidate rewrite files and explicit `--accept-pyrel-paths` acknowledgment after equivalence checks.

**Review workload changes and missing artifacts.** Extract only new/changed repair items when preserved snapshots/contributions support safe subtraction; keep surviving split assignments. Missing old evidence requires a full digest rebuild and recheck, accepted explicitly with `--accept-workload-delta --full-rebuild`. Changed specifications need a new check and current `spec_hash` before their old passes count again. Restore a missing required artifact. If you deliberately retire a registered artifact after reviewing the consequence, name its manifest key and reason:

```sh
python "$SKILLS/rai-orm/tools/state.py" update \
  --skill rai-orm --retire-artifact digest \
  --retire-reason 'Reviewed replacement evidence and retired the aggregate digest'
```

Retirement records a decision; it does not supply missing verification, erase regressions or bypass another blocker. Original schema/document changes also need explicit reconciliation, not blind resume.

After an interruption or budget stop, plan again, resolve blockers, start the fresh invocation once, establish N+0 and follow the ordered steps. Skip unchanged intake, construction and digest extraction. Read [hot-start.md](references/hot-start.md) for the full acceptance and delta protocol.

## Local tools

Use the project Python environment with PyYAML, DuckDB, NetworkX and SQLGlot available. These tools read metadata and write/check artifacts; they do not replace the agent's modeling decisions or execute the whole family. The examples use existing project files and the `SKILLS` path above.

**`connectivity.py`** checks entity paths and suggests links; its `--db` option opens a DuckDB source read-only. Omit it if unavailable. An optional live connection used by schema recovery is not itself a `--db` connection-string option here. Exit 2 with `--fail-on-required-gap` means a required gap remains; exit 1 means the check failed.

```sh
python "$SKILLS/rai-orm/tools/connectivity.py" --model model.orm.yaml \
  --db source.duckdb --digest repair.digest.yaml \
  --out connectivity.json --proposals connectivity.proposals.yaml \
  --fail-on-required-gap
```

**`compaction_metrics.py`** measures counts and statically scans listed rewrites. For assessment, substitute the exact `baseline_model_revision` printed by the current plan; `compaction.after.json` belongs beside the model for reporting.

```sh
python "$SKILLS/rai-orm-refactor/tools/compaction_metrics.py" \
  --model model.orm.yaml --verification model.verification.json \
  --digest workload.digest.yaml --model-revision '<baseline_model_revision>' \
  --out compaction.after.json
```

**`workload_digest.py`** extracts SQL structure using the saved split. Its CLI does not extract business vocabulary from prose; the agent adds terms and alignments.

```sh
python "$SKILLS/rai-orm-from-workload/tools/workload_digest.py" \
  --input workload.pairs.json --dialect postgres --schema schema.sql \
  --split repair --verification model.verification.json \
  --out repair.digest.yaml --no-timestamp
```

Use `--split holdout` separately for sealed measurement; omit split selection for the aggregate digest. `--ids FILE` selects listed item IDs, intersecting any split selection.

**`state.py`** prints ordered continuation work without applying feedback. Its `init` and `update` examples are in the resume section.

```sh
python "$SKILLS/rai-orm/tools/state.py" plan --state orm-state.json > orm-plan.json
```

**`report.py`** combines counts and fixed next actions. Refresh plan, connectivity and metrics first. Inputs other than `--model` are optional; absent verification means unknown coverage.

```sh
python "$SKILLS/rai-orm/tools/report.py" --model model.orm.yaml \
  --verification model.verification.json --connectivity connectivity.json \
  --digest workload.digest.yaml --plan orm-plan.json --out-dir .
```

## How to read the report

Start with the leading budget line, status and blocker issues. `BUDGET_EXHAUSTED` gives residual failures/unverified items and the continuation action. `REFACTOR_BUDGET_EXHAUSTED` means suspects remain after its separate allowance; coverage can be verified while refactor remains incomplete (`verified-refactor-incomplete`). Missing metrics mean refactor status is unknown.

Read concept counts separately from **relationships between entity concepts**, scalar properties and unary flags. A smaller concept count is useful only if identifiers, domain meaning and workload answers survive. Table/column coverage depends on recorded source bindings and inventory; missing inventory is unknown coverage.

Read **dev pass counts** as the report's repair-set passes, alongside holdout passes for each round. Compare counts using the same oracle and weak-pass accounting. `execution-match` compares source SQL and bound PyRel results; `structural` checks compilation/reachability; `user-review` covers reviewed verbalized rewrites. Empty-equals-empty is a weak match, not evidence of improvement. Unreviewed questions are `unverified`. Pass rates exclude `inexpressible` and `oracle-error`, so inspect those counts as well as the percentage.

Read connectivity in three parts:

- **Components:** groups connected by entity facts, subtype links or objectification paths. Shared primitive values alone do not connect entities. `connected` describes graph structure; proposed facts can supply paths without their meaning being confirmed.
- **Isolated concepts:** concepts with no path to another entity. Review missing bindings and link evidence; keep legitimate independent concepts and justify their business separation in `ontology-notes.md`. Low workload support is not a deletion rule.
- **Required gaps:** workload joins with no model path, including unbound source tables. These remain `missing-element` failures until the path exists. An island explanation or an exploratory overlap match cannot clear a required gap.

`COMPARISON_CAP_REACHED` means eligible links remain untested at the default 5,000-comparison cap. Inspect `required_gaps_untested` and `isolated_concepts_untested`; focus probes or raise the cap only when that priority work remains. Static single-item/duplicate/flag hints need domain review, especially with partial scan coverage. `all-pass` covers verified supported items; exclusions and other issues still matter.

## Known limits

The v2 family still has the following customer-relevant limits. The unresolved implementation items come from the [2026-10-05 follow-up log](/Users/nikolaosvasiloglou/github-repos/Terra/.planning/todos/2026-10-05-orm-skills-v2-followups.md); they are documented here, not fixed by this guide.

- **Keep explicit workload IDs across files.** The digest namespaces generated IDs for multiple files, but state still generates positional IDs and rejects the digest's colon form. Multiple implicit-ID files can collide. Stable explicit IDs avoid that mismatch and shifts after insertion.
- **Preserve old workload snapshots and shared count metadata.** Contribution fingerprints do not fully cover referenced `literal_cohorts`. If the old workload snapshot is gone and shared cohort evidence changed or disappeared, planning may miss the need for a full rebuild. Rebuild/recheck affected evidence instead of trusting subtraction from incomplete metadata.
- **Check emitter status in the plan even after a successful update.** Failed/unverified or non-idempotent emitter registrations are not consistently enforced by verify/refactor updates. Their updates may succeed while `plan` remains blocked. Resolve the failed check before using candidates.
- **Inspect emitter diagnostics locally before sharing state.** Raw emitter stderr can be persisted in `cause`, including traceback source content. Summary reports omit data values, but emitter failure state is not guaranteed to do so.
- **Follow the actual emitter schema and current hot-start gate.** The schema skill's older Step 10 wording requires a changed Python hash for every fact change and lists different declaration metadata. Current hot-start rules allow metadata-only changes without a new Python hash and document `{owner, property, type}` for emitters reading those fields. Inspect your emitter rather than copying stale metadata blindly.
- **Emitter checks have environment limits.** The implemented sandbox check uses macOS `sandbox-exec`; an unavailable sandbox blocks real-emitter validation. Its isolation still has open IPC scope and PATH limitations. Use a trusted project emitter and resolve runtime/dependency failures; this check is not a general untrusted-code sandbox.
- **Usage hints and path checks have limits.** Compaction and reporting heuristics are not fully aligned, and manifest-path checking is not uniform across commands. Keep files within the project, run `plan` before dependent work and inspect actual saved rewrites before removing a concept. Static scanning can miss indirect/dynamic uses or count unrelated matching identifiers.

The family also does not import a Python-only model into ORM YAML, recover a model from SQL alone, or automatically bind generated PyRel to data. Some SQL constructs cannot be expressed in the installed PyRel version; record them as `inexpressible` rather than reshaping the domain to imitate them. Textual constraints are stored without FORML interpretation; deontic (“should”) rules remain comments. The modeling guides also exclude diagram rendering, composite value records, polymorphic/cross-database FK recovery and multi-model translation.

Validate bundled examples before using them with current helpers. The schema skill's `examples/movie_catalog.orm.yaml` references undeclared `integer` and `string` value types, so `compaction_metrics.py` rejects that file as-is. Use validated project YAML for the metrics step.

## Worked example: a warehouse, counts only

Take a 90-table warehouse with a workload of 109 questions. Run `rai-orm`, prepare repair evidence, recover the schema model, bind real data, check connectivity, assess compaction, verify, evaluate supported refactors and write the report.

| Measure | After the run |
| --- | ---: |
| Source tables | 90 |
| Entity concepts | 76 |
| Relationships between concepts | 92 |
| Workload questions expressible | 94 of 109 |
| Questions outside that expressible count | 15 |

These are the example's supplied counts, not a reproduced verification run. Expressibility alone does not establish executed result equivalence. Read the actual oracle, repair/holdout passes, weak matches and status of the remaining 15 questions before treating the model as ready. Keep any blockers and pending proposals visible, then resume from the saved state when more work is needed.
