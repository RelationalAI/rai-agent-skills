"""End-to-end skill eval orchestrator.

For each eval in a skill's evals.json:
  1. Run the agent headless via `claude --print` (runner.py)
  2. Judge each expectation via a separate `claude --print` call (judge.py)
  3. Save per-eval transcript + judgments
  4. Diff against baselines/<skill>.json (diff.py)
  5. Print summary; exit non-zero if regressions

Usage:
    python evals/run.py --skill rai-predictive-modeling
    python evals/run.py --all
    python evals/run.py --all --update-baseline      # promote current results
    python evals/run.py --skill rai-predictive-training --eval-id 3
    python evals/run.py --all --cwd /data/haythem/PyRel
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from runner import DEFAULT_CWD, run_eval  # noqa: E402
from judge import judge  # noqa: E402
from diff import compare, load_baseline, write_baseline, to_passmap  # noqa: E402

REPO = ROOT.parent
SKILLS_DIR = REPO / "skills"
BASELINES_DIR = ROOT / "baselines"
RESULTS_DIR = ROOT / "results"

PREDICTIVE_SKILLS = ["rai-predictive-training"]


def load_skill_evals(skill_name: str) -> dict:
    path = SKILLS_DIR / skill_name / "evals" / "evals.json"
    if not path.exists():
        raise FileNotFoundError(f"No evals.json for skill {skill_name}: {path}")
    with open(path) as f:
        return json.load(f)


def run_one_eval(
    skill_name: str,
    eval_obj: dict,
    out_dir: Path,
    cwd: Path,
    run_timeout: int,
    judge_timeout: int,
    verbose: bool = False,
) -> dict:
    eid = eval_obj["id"]
    if verbose:
        print(f"\n--- [{skill_name}] eval {eid}: running agent (timeout={run_timeout}s) ---", flush=True)
    else:
        print(f"  [{skill_name}] eval {eid} ... ", end="", flush=True)

    run = run_eval(
        skill_name=skill_name,
        eval_prompt=eval_obj["prompt"],
        cwd=cwd,
        timeout=run_timeout,
        stream_to_stdout=verbose,
    )

    if verbose:
        print(f"\n--- [{skill_name}] eval {eid}: agent done (exit={run.exit_code}, timeout={run.timed_out}) ---", flush=True)

    transcript_path = out_dir / f"eval_{eid}_transcript.txt"
    transcript_path.write_text(run.transcript)

    if run.timed_out or run.exit_code != 0:
        print(f"runner failed (exit={run.exit_code}, timeout={run.timed_out})")
        # Still save a result row so diff sees it as failing.
        exp_results = [
            {
                "expectation": e,
                "passed": False,
                "justification": f"Runner failed: exit={run.exit_code}, timeout={run.timed_out}",
                "raw": "",
            }
            for e in eval_obj["expectations"]
        ]
        result = {
            "id": eid,
            "all_passed": False,
            "expectations": exp_results,
            "run_meta": run.to_dict(),
        }
        (out_dir / f"eval_{eid}.json").write_text(json.dumps(result, indent=2))
        return result

    exp_results: list[dict] = []
    total = len(eval_obj["expectations"])
    for i, exp in enumerate(eval_obj["expectations"], 1):
        if verbose:
            print(f"  judging {i}/{total}: {exp[:90]}", flush=True)
        j = judge(run.transcript, exp, timeout=judge_timeout)
        if verbose:
            mark = "PASS" if j.passed else "FAIL"
            print(f"    {mark} -- {j.justification[:160]}", flush=True)
        exp_results.append({
            "expectation": exp,
            "passed": j.passed,
            "justification": j.justification,
            "raw": j.raw,
        })

    passed = sum(1 for e in exp_results if e["passed"])
    if verbose:
        print(f"  [{skill_name}] eval {eid}: {passed}/{total} passed", flush=True)
    else:
        print(f"{passed}/{total} passed")

    result = {
        "id": eid,
        "all_passed": passed == total,
        "expectations": exp_results,
        "run_meta": {
            "exit_code": run.exit_code,
            "timed_out": run.timed_out,
            "cmd": run.cmd,
        },
    }
    (out_dir / f"eval_{eid}.json").write_text(json.dumps(result, indent=2))
    return result


def run_skill(
    skill_name: str,
    out_root: Path,
    cwd: Path,
    eval_ids: list[int] | None,
    run_timeout: int,
    judge_timeout: int,
    verbose: bool = False,
) -> dict:
    print(f"\n=== {skill_name} ===")
    skill_evals = load_skill_evals(skill_name)
    out_dir = out_root / skill_name
    out_dir.mkdir(parents=True, exist_ok=True)

    selected = skill_evals["evals"]
    if eval_ids:
        selected = [e for e in selected if e["id"] in eval_ids]

    results_by_id: dict[str, list[dict]] = {}
    for eval_obj in selected:
        res = run_one_eval(
            skill_name=skill_name,
            eval_obj=eval_obj,
            out_dir=out_dir,
            cwd=cwd,
            run_timeout=run_timeout,
            judge_timeout=judge_timeout,
            verbose=verbose,
        )
        results_by_id[str(res["id"])] = res["expectations"]

    baseline_path = BASELINES_DIR / f"{skill_name}.json"
    baseline = load_baseline(baseline_path)
    diff = compare(results_by_id, baseline)

    skill_summary = {
        "skill_name": skill_name,
        "results": results_by_id,
        "diff": diff,
    }
    (out_dir / "skill_summary.json").write_text(json.dumps(skill_summary, indent=2))
    return skill_summary


def print_summary(summary: list[dict]) -> bool:
    """Print aggregate; return True if any regressions were found."""
    print("\n=== Summary ===")
    has_regression = False
    for s in summary:
        results = s["results"]
        total = sum(len(v) for v in results.values())
        passed = sum(1 for v in results.values() for e in v if e["passed"])
        diff = s["diff"]
        regs = len(diff.get("regressions", []))
        imps = len(diff.get("improvements", []))
        added = len(diff.get("added", []))
        removed = len(diff.get("removed", []))
        flag = " (first run, no baseline)" if diff.get("first_run") else ""

        print(
            f"  {s['skill_name']}: {passed}/{total} passed | "
            f"regressions: {regs} | improvements: {imps} | "
            f"added: {added} | removed: {removed}{flag}"
        )

        if regs > 0:
            has_regression = True
            for r in diff["regressions"]:
                short = r["expectation"][:90]
                print(f"    REGRESSION eval={r['eval_id']}: {short}")

    return has_regression


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--skill",
        action="append",
        help="Skill name (repeatable). Defaults to predictive skills.",
    )
    p.add_argument("--all", action="store_true", help="Run all predictive skills.")
    p.add_argument(
        "--eval-id",
        type=int,
        action="append",
        help="Restrict to specific eval id(s).",
    )
    p.add_argument(
        "--cwd",
        default=str(DEFAULT_CWD),
        help="Working directory for the agent subprocess (default: %(default)s).",
    )
    p.add_argument(
        "--out",
        default=None,
        help="Output directory for this run (default: evals/results/<timestamp>).",
    )
    p.add_argument(
        "--run-timeout",
        type=int,
        default=1200,
        help="Per-eval agent timeout in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--judge-timeout",
        type=int,
        default=180,
        help="Per-expectation judge timeout in seconds (default: %(default)s).",
    )
    p.add_argument(
        "--update-baseline",
        action="store_true",
        help="After the run, write current pass/fail map to baselines/<skill>.json.",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Stream agent stdout in real time and print per-expectation judge progress.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.all:
        skills = PREDICTIVE_SKILLS
    elif args.skill:
        skills = args.skill
    else:
        skills = PREDICTIVE_SKILLS  # default

    run_id = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_root = Path(args.out) if args.out else (RESULTS_DIR / run_id)
    out_root.mkdir(parents=True, exist_ok=True)
    print(f"Run id: {run_id}")
    print(f"Results -> {out_root}")
    print(f"Working dir for agent: {args.cwd}")

    cwd = Path(args.cwd)
    summary: list[dict] = []
    for skill_name in skills:
        s = run_skill(
            skill_name=skill_name,
            out_root=out_root,
            cwd=cwd,
            eval_ids=args.eval_id,
            run_timeout=args.run_timeout,
            judge_timeout=args.judge_timeout,
            verbose=args.verbose,
        )
        summary.append(s)

    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))

    has_regression = print_summary(summary)

    if args.update_baseline:
        for s in summary:
            baseline_path = BASELINES_DIR / f"{s['skill_name']}.json"
            write_baseline(baseline_path, s["results"])
            print(f"Baseline updated: {baseline_path}")

    return 1 if has_regression else 0


if __name__ == "__main__":
    sys.exit(main())
