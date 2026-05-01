# Skill Evals

Evaluation of skills under `skills/<name>/`. For each eval, the runner spawns a headless `claude --print` agent, captures its transcript, then asks a separate LLM-as-judge call to score each expectation pass/fail.

## Running

```bash
# Single skill
python evals/run.py --skill rai-predictive-training

# Single eval id (faster iteration)
python evals/run.py --skill rai-predictive-training --eval-id 1

# Multiple skills in one run
python evals/run.py --skill rai-ontology-design --skill rai-predictive-modeling

# Run from a different working directory (where `raiconfig.yaml` lives, etc.)
python evals/run.py --skill <name> --cwd /path/to/project

# Freeze current pass/fail map as the baseline
python evals/run.py --skill <name> --update-baseline

# Verbose: per-expectation judge progress and banners around each eval
python evals/run.py --skill <name> --eval-id 1 -v
```

`run.py` exits non-zero if any expectation regressed against the stored baseline (passing in baseline, now failing).

**About `-v`.** It prints banners between phases (`running agent...`, `agent done`, `judging i/N: ...`, `PASS/FAIL -- <justification>`) so you can see judge-by-judge progress live. It does **not** stream the agent's stdout in real time — `claude --print` with text output buffers the entire reply and emits it at the end of the run, so the agent phase is silent regardless of `-v`. Use `-v` mainly to watch the judge phase or to confirm the runner is alive between evals.

## Adding evals

Edit `skills/<skill>/evals/evals.json`:

```json
{
  "id": 1,
  "prompt": "<user prompt>",
  "expected_output": "<plain-language description of the right answer>",
  "expectations": [
    "<one atomic, judgeable claim>",
    "<another>"
  ]
}
```

- **Each `expectation` is judged in isolation** — keep them atomic. Vague or compound claims produce inconsistent verdicts.
- **`expected_output` is documentation only**; the judge never sees it. It's a note for whoever maintains the eval.
- **Anchor on artifacts**, not process: specific code patterns, argument names, design choices — not "explained well."

After adding, run once, spot-check verdicts in `results/<timestamp>/<skill>/eval_<id>.json`, then re-run with `--update-baseline` to freeze the reference.

## Layout

```
evals/
  run.py              # CLI orchestrator
  runner.py           # claude --print subprocess wrapper (one per eval)
  judge.py            # LLM-as-judge (one call per expectation)
  diff.py             # baseline comparison
  baselines/<skill>.json
  results/<YYYYMMDD_HHMMSS>/<skill>/
    eval_<id>_transcript.txt    # raw agent transcript
    eval_<id>.json              # per-eval result + per-expectation judgments
    skill_summary.json          # aggregate + diff vs baseline
```

Eval prompts live next to each skill: `skills/<skill>/evals/evals.json`.

## Prerequisites

- `claude` CLI authenticated (`claude --version` works).
- The skill must resolve from the agent's `--cwd` (default: `Path.cwd()`).
- Evals that touch Snowflake need a working `raiconfig.yaml` and the `relationalai` SDK in that cwd.

## Permissions

The runner passes `--dangerously-skip-permissions` so the agent can read files, run Bash, and introspect Snowflake without per-call approval. Same blast radius as an unsupervised agent — review prompts and `cwd` before running.
