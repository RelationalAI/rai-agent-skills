"""LLM-as-judge for skill evals.

One `claude --print` call per (transcript, expectation) pair. The judge
prompt forces a single-line JSON response: {"passed": bool, "justification": str}.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT = 180
DEFAULT_CLAUDE_BIN = "claude"

JUDGE_PROMPT = """\
You are evaluating whether an AI agent's response satisfies a specific expectation.
Respond with only a single JSON object on one line. No markdown. No prose.

EXPECTATION:
{expectation}

AGENT_RESPONSE:
<<<BEGIN>>>
{transcript}
<<<END>>>

Output schema (single line, no code fence):
{{"passed": true|false, "justification": "<1-2 sentences citing specific evidence from AGENT_RESPONSE>"}}
"""


@dataclass
class JudgeResult:
    passed: bool
    justification: str
    raw: str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "justification": self.justification,
            "raw": self.raw,
        }


def _extract_json(s: str) -> dict | None:
    s = s.strip()
    # Strip code fences if present.
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # Find the first {...} block.
    match = re.search(r"\{.*\}", s, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def judge(
    transcript: str,
    expectation: str,
    timeout: int = DEFAULT_TIMEOUT,
    claude_bin: str = DEFAULT_CLAUDE_BIN,
    cwd: Path | None = None,
) -> JudgeResult:
    prompt = JUDGE_PROMPT.format(expectation=expectation, transcript=transcript)
    cmd = [claude_bin, "--print", prompt]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JudgeResult(
            passed=False,
            justification="Judge call timed out.",
            raw="",
        )

    raw = proc.stdout.strip()
    parsed = _extract_json(raw)
    if parsed is None:
        return JudgeResult(
            passed=False,
            justification=f"Could not parse JSON from judge: {raw[:300]!r}",
            raw=raw,
        )

    return JudgeResult(
        passed=bool(parsed.get("passed", False)),
        justification=str(parsed.get("justification", "")),
        raw=raw,
    )
