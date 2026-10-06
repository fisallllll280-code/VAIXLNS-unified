"""Isolated subprocess bridge for pluggable math/physics/engineering solvers.

Workers receive one JSON object on stdin and emit one JSON object on stdout.
Shell execution is disabled; each invocation is bounded by a timeout.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import subprocess
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SolverResult:
    ok: bool
    output: Mapping[str, Any] | None
    error: str | None
    return_code: int


class SolverBridge:
    def __init__(self, command: Sequence[str], *, timeout_seconds: float = 10.0) -> None:
        if not command:
            raise ValueError("SOLVER_COMMAND_REQUIRED")
        if any(not str(item).strip() for item in command):
            raise ValueError("SOLVER_COMMAND_INVALID")
        self.command = tuple(command)
        self.timeout_seconds = timeout_seconds

    def run(self, payload: Mapping[str, Any]) -> SolverResult:
        try:
            completed = subprocess.run(
                list(self.command),
                input=(json.dumps(dict(payload), ensure_ascii=False) + "\n").encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
                env={**os.environ, "VAIXLNS_SOLVER_MODE": "isolated"},
            )
        except subprocess.TimeoutExpired:
            return SolverResult(False, None, "SOLVER_TIMEOUT", -1)
        except OSError as exc:
            return SolverResult(False, None, f"SOLVER_START_ERROR:{exc}", -1)

        if completed.returncode != 0:
            return SolverResult(
                False,
                None,
                f"SOLVER_EXIT:{completed.returncode}:{completed.stderr.decode('utf-8', errors='replace').strip()}",
                completed.returncode,
            )
        try:
            output = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return SolverResult(False, None, f"SOLVER_OUTPUT_INVALID:{exc}", completed.returncode)
        if not isinstance(output, dict):
            return SolverResult(False, None, "SOLVER_OUTPUT_OBJECT_REQUIRED", completed.returncode)
        return SolverResult(True, output, None, completed.returncode)
