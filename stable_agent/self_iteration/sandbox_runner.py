"""Sandbox runner for PR-only self-iteration."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SandboxResult:
    ok: bool
    command: list[str]
    returncode: int
    stdout_tail: str
    stderr_tail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SandboxRunner:
    def run(self, command: list[str], *, timeout: int = 60) -> SandboxResult:
        forbidden = {"git push", "git merge", "vercel deploy", "deploy"}
        joined = " ".join(command)
        if any(item in joined for item in forbidden):
            return SandboxResult(False, command, 2, "", "forbidden self-iteration command")
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return SandboxResult(proc.returncode == 0, command, proc.returncode, proc.stdout[-1000:], proc.stderr[-1000:])
