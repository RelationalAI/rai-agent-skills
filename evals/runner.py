"""Subprocess wrapper around `claude --print` for skill evals.

One subprocess per eval. Captures stdout (the agent transcript), stderr,
exit code, and timeout state. The runner does NOT judge; it only collects.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CWD = Path.cwd()
DEFAULT_TIMEOUT = 600  # seconds per agent run
DEFAULT_CLAUDE_BIN = "claude"


@dataclass
class RunResult:
    transcript: str
    stderr: str
    exit_code: int
    timed_out: bool
    cmd: str

    def to_dict(self) -> dict:
        return {
            "transcript": self.transcript,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "cmd": self.cmd,
        }


def build_prompt(skill_name: str, eval_prompt: str) -> str:
    return (
        f"You must use the {skill_name} skill to answer the following request. "
        f"Reply with the requested artifact only — no preamble, no questions back, "
        f"no follow-up offers.\n\n"
        f"REQUEST:\n{eval_prompt}"
    )


def run_eval(
    skill_name: str,
    eval_prompt: str,
    cwd: Path = DEFAULT_CWD,
    timeout: int = DEFAULT_TIMEOUT,
    claude_bin: str = DEFAULT_CLAUDE_BIN,
    skip_permissions: bool = True,
    stream_to_stdout: bool = False,
) -> RunResult:
    prompt = build_prompt(skill_name, eval_prompt)
    cmd = [claude_bin, "--print"]
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd.append(prompt)

    cmd_str = " ".join(shlex.quote(c) for c in cmd[:-1]) + " <prompt>"

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    transcript_chunks: list[str] = []
    deadline = time.monotonic() + timeout
    timed_out = False

    assert proc.stdout is not None
    for line in proc.stdout:
        transcript_chunks.append(line)
        if stream_to_stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
        if time.monotonic() > deadline:
            timed_out = True
            proc.kill()
            break

    try:
        proc.wait(timeout=max(0.1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()

    stderr = proc.stderr.read() if proc.stderr else ""
    transcript = "".join(transcript_chunks)
    if timed_out:
        stderr += "\n[TIMEOUT]"

    return RunResult(
        transcript=transcript,
        stderr=stderr,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
        cmd=cmd_str,
    )
