# Statistics and issues report

Load when closing an ORM route or verification loop, especially after plateau or budget exhaustion.

```sh
python skills/rai-orm/tools/report.py --model model.orm.yaml \
  --verification model.verification.json --connectivity connectivity.json \
  --digest workload.digest.yaml --plan orm-plan.json --out-dir .
```

All inputs except `--model` are optional. `--plan PATH` reads the JSON printed by `state.py plan` and loads `compaction.after.json` beside the model for remaining suspects; refresh these artifacts before reporting. The plan supplies `budget.refactor_rounds` and `rounds_used_by_skill_this_invocation["rai-orm-refactor"]`. Missing compaction metrics are unknown, not proof that refactor finished. Missing connectivity is computed structurally from the model; data probes are not run by this tool. Missing verification means pass counts and rates are unknown, not zero failures or completion. With a digest, its entire workload is unverified until verification evidence exists.

## Output contract

`orm-report.json` contains `version: 1`, `status`, `statistics`, and `issues`. `orm-report.md` renders the same statistics and actions. Both files contain only counts, ids, model/schema names, status/class names and fixed action text. Free-text defect descriptions, SQL, questions, result values and literals in saved PyRel files are never copied.

Statistics include entity/value object types and `statistics.fact_types` split into `entity_relationships` (binary facts with two entity roles), `scalar_properties` (binary facts whose second role is a value type), `flags` (unary facts), and `n_ary` (other arities). Self relationships count as entity relationships. The markdown headline reads, for example, "76 concepts, 72 relationships between concepts, 1,945 scalar properties, 107 flags"; value types and n-ary facts are shown separately. Legacy arity totals are retained only for compatibility as `statistics.fact_types_total_unary`, `fact_types_total_binary`, and `fact_types_total_n_ary`.

Statistics also include inline and top-level constraints by source, status and their combination; relationships per concept; components and isolated concepts; covered tables and bound/dropped column counts. Coverage uses `source_bindings`, legacy provenance pointers and both column tuples of applied data-link facts. `source.scope.tables` supplies the explicit table inventory; `source.columns` supplies the optional column inventory. Wildcard scope is unknown, not proof of complete coverage. Missing column inventory yields `columns_unaccounted: null`. A bound column takes precedence over a dropped pointer for the same table/column.

With verification, statistics include `rounds_run_total`, `rounds_run_this_invocation` and a count-only `invocations` list; the Markdown states cumulative rounds separately from the budget of this invocation. Legacy reports use the last global round as the total (baseline 0 excluded) and say the invocation count is unknown. With verification, statistics also include per-round repair/holdout passes, repair group counts, regressions, residual failures by class, rates, and counts for `pass`, `fail`, `unverified`, `inexpressible`, `oracle-error`. Each repair entry counts as one group. Per-round connectivity is retained when recorded in the verification file. Use the maximum of digest, verification and recorded item counts. Missing records and unknown statuses count as unverified; `UNKNOWN_ITEM_STATUS` raises an issue. `WORKLOAD_COUNT_MISMATCH` blocks all-pass when counts differ. Pass rates use the verification summary, or recorded item statuses by split when summary rates are absent.

Each issue has a fixed `id`, `severity` (`blocker`, `warning`, `info`), `count`, and `next_action`; some add numeric evidence or concept ids. Blockers sort first, with budget exhaustion ahead of every other issue.

| Id | Trigger | Next action |
|---|---|---|
| `BUDGET_EXHAUSTED` | `stopped_because: budget` and residual failures or unverified items remain | Resume `rai-orm` at Step 0 with `orm-state.json` and `model.verification.json`; run `state.py plan` for a fresh invocation budget |
| `REFACTOR_BUDGET_EXHAUSTED` | Refactor rounds used reach `budget.refactor_rounds` (default 2), and compaction metrics still list suspects | Resume with a fresh refactor allowance; blocker count is the number of remaining suspect entries |
| `PLATEAU` | Explicit plateau stop; legacy reports without invocation boundaries also infer two non-improving rounds with residual failures | Review residual groups at Step 4 before another repair |
| `UNVERIFIED_ITEMS` | Explicit unverified items or workload items with no record | Continue oracle checks or user review; report their share of the workload |
| `HOLDOUT_GAP` | Repair pass rate exceeds holdout pass rate by more than 0.15 | Review whether repairs are fitted; keep holdout failures out of repair decisions |
| `ISLANDS` | More than one component | Review link proposals and justify remaining islands |
| `ISOLATED_CONCEPTS` | Concepts with no path to another concept | Review bindings and link evidence |
| `COMPARISON_CAP_REACHED` | Connectivity `summary.comparison_cap_reached: true` | The cap is reached; untested candidates are ranked after required-gap and isolated-concept pairs. Raise `--max-comparisons` only if required gaps or isolated concepts are still untested; show `required_gaps_untested` / `isolated_concepts_untested` counts when provided, otherwise say counts unavailable |
| `REQUIRED_JOIN_GAPS` | Any workload join without a path | `missing-element`; add a proposed link with overlap evidence |
| `ORACLE_ERRORS` | Excluded oracle errors > 0 | Repair the oracle and re-check |
| `INEXPRESSIBLE_ITEMS` | Excluded unsupported items > 0 | Document the supported workload boundary |
| `DROPPED_COLUMNS` | Explicit dropped bindings > 0 | Bind or justify each column |
| `REGRESSIONS` | Recorded regressions > 0 | Re-run saved passes and review rollback decisions |
| `SINGLE_ITEM_CONCEPTS` | A concept appears in exactly one saved workload PyRel file | Review for query-shaped modeling against schema and domain vocabulary |

The singleton check runs only when `items[].pyrel` lists saved files. Paths resolve relative to `model.verification.json`. It parses Python AST identifiers and attributes matching entity names, including imported aliases, and counts each concept once per workload item. It reads no unlisted files and emits no literals. Both reporting and compaction use `rai-orm/tools/orm_usage.py`; the refactor scanner module provides compatibility exports without modifying the import path. Missing/invalid files yield partial coverage: list single-item observations with `coverage: partial` and `lower_bound: true`; they do not prove exclusive use. Identifier matching is a heuristic; inspect the named concepts before changing the model.

## Budget-first presentation

When residual failures or unverified items remain at exhaustion of the budget of this invocation, the **first line** of `orm-report.md` is:

```text
BUDGET_EXHAUSTED: 4 residual failures. Continue: Resume rai-orm at Step 0 with orm-state.json and model.verification.json; run state.py plan for a fresh invocation budget.
```

The first line additionally gives `Unverified items: N.` when any remain, even if residual failures are zero. The budget issue counts residual failures and records unverified items separately. Show that line first in the user summary. JSON `status` is `budget-exhausted`, with a blocker issue and residual count. Neither file claims completion or all-pass in that state. Residual counts conservatively reconcile summary classes with recorded failed items, so an empty residual summary cannot hide failures.

When the refactor allowance is exhausted with remaining suspects, the first line starts `REFACTOR_BUDGET_EXHAUSTED: N remaining suspects.` (ahead of verify-budget exhaustion if both apply). Show verified workload coverage and incomplete refactor work on separate lines. An otherwise `all-pass` report becomes `verified-refactor-incomplete`; existing failure statuses remain failures. Refactor attempts consume their own allowance, separate from verify rounds.

Without budget failure, status is `residual-failures`, `required-gaps`, `unverified`, or `all-pass`, according to the evidence. `all-pass` refers only to verified supported items; exclusions, dropped columns and connectivity issues are still shown.

If the tool is unavailable, aggregate the same model counts and saved verification records manually, generate issues from the trigger table, and preserve the budget-first line and privacy rules.
