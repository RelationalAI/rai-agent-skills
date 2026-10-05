# Integration notes for the supervising task

This task adds only `skills/rai-orm-refactor/**`. The following are proposed additions to other files, not edits performed by this task. Cross-skill references below use skill names; the supervisor owns routing, manifest registration and workflow-chain edits.

## Router: `rai-orm`

Add this row to the ORM skills table:

```markdown
| `rai-orm-refactor` | Compact an existing ORM ontology with existing-element path scaffolds, retaining verified workload coverage | after verification, when compaction is requested or ontology drift is observed |
```

Add this routing row before the generic existing-PyRel row:

```markdown
| Existing ORM YAML with query-shaped concepts, flag explosions, table mirrors or duplicated families | `rai-orm-refactor` → modeling skill final commit/regeneration → `rai-orm-verify` acceptance check |
```

Add to the hand-off table:

```markdown
| `rai-orm-verify` | `rai-orm-refactor` | Existing YAML/PyRel/binding, digest and workload artifacts, current verification report and saved rewrites, inherited mode and remaining verification budget |
| `rai-orm-refactor` | the original modeling skill | A batch of proposals with `provenance.origin: refactor`, affected ids, existing-element path scaffolds and rollback snapshot; commit through SRP Step 9f or CSDP Step 7f, validate and regenerate |
| the modeling skill | `rai-orm-verify` | Candidate YAML/PyRel/binding plus the same workload, split and oracle; accept only without a verified pass-count drop, otherwise restore the snapshot |
```

Add to the route-close instruction:

```markdown
When compaction ran, report before/after concept and flag counts, support coverage, accepted/kept/rolled-back proposals and verified pass counts; state budget exhaustion prominently with residual classes and remaining suspects.
```

## Workflow-chain documentation

Proposed line for `CLAUDE.md` and the equivalent workflow description in `README.md`:

```markdown
- **ORM compaction (optional, after verification):** rai-orm-refactor → original modeling skill final commit/validation/regeneration → rai-orm-verify; accept only if verified workload pass counts do not drop.
```

## Modeling representation and final-step instructions

Add to the provenance documentation owned by `rai-orm-from-schema`:

```markdown
Object types and fact types created or changed by rai-orm-refactor carry provenance.origin: refactor and provenance.refactor: {proposal_id: <id>, previous_origin: <origin>, yaml_ids: [<id>], item_ids: [<id>], support: <count>}; preserve binding and original evidence fields. Deletion proposals retain provenance in refactor-proposals.yaml. Constraint source remains in the existing vocabulary; new workload-backed constraints use source: workload and its required provenance fields, not source: refactor. Verification does not confirm a proposed domain rule.
```

Add `refactor` to any enumerated allowed object/fact `provenance.origin` vocabulary if a validator enforces it. Add `provenance.tables: [<table-name>]` as an optional explicit binding list for merged concepts if that list is not already supported; keep singular `provenance.table` compatibility. The metrics tool supports both forms and does not guess undeclared bindings.

Proposed line for the final steps of both modeling skills:

```markdown
Accept refactor batches through the same review, YAML validation and regeneration path as workload repairs; retain One-shot proposals and REVIEW PROPOSAL comments, regenerate the verbalization and model.py, and preserve/recheck source bindings before handing back to rai-orm-verify.
```

## Verification hand-back

Add to `rai-orm-verify`:

```markdown
For a rai-orm-refactor candidate, re-run all items against the baseline workload, split and oracle, including prior passes and the sealed holdout; report pass counts, regressions, fixes, weak passes and exclusions. Accept only when verified total and per-split pass counts do not drop and regressions do not exceed fixes; otherwise restore the consistent model/binding/report/rewrite snapshot. Share the existing round budget across the compaction hand-back; do not reset it for each batch. Prominently report budget exhaustion and residual failures when stopped_because is budget.
```

## Packaging

Register `rai-orm-refactor` beside the other ORM skills in the plugin manifest using that manifest's existing entry shape. Any publication version bump belongs to the supervising task. No manifest or version file was changed here.
