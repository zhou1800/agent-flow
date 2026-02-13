"""PytestTool runs pytest and parses results."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from .base import ToolResult


class PytestTool:
    name = "pytest"

    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, args: list[str]) -> ToolResult:
        start = time.perf_counter()
        cmd = [sys.executable, "-m", "pytest", *args]
        try:
            result = subprocess.run(cmd, cwd=_safe_cwd(self.root), capture_output=True, text=True, check=False)
            output = result.stdout + "\n" + result.stderr
            passed, failed = _parse_counts(output)
            failing_tests = _parse_failures(output)
            return ToolResult(
                ok=result.returncode == 0,
                summary="pytest run",
                data={
                    "returncode": result.returncode,
                    "passed": passed,
                    "failed": failed,
                    "failing_tests": failing_tests,
                    "output": output,
                },
                elapsed_ms=_elapsed_ms(start),
                error=None if result.returncode == 0 else "pytest failed",
            )
        except Exception as exc:
            return ToolResult(ok=False, summary="pytest error", data={}, elapsed_ms=_elapsed_ms(start), error=str(exc))


def _safe_cwd(root: Path) -> Path:
    """Avoid stdlib shadowing when running from directories containing stdlib-like module names."""
    if (root / "types.py").exists():
        return root.parent
    return root


def _parse_counts(output: str) -> tuple[int | None, int | None]:
    match = re.search(r"(\d+)\s+passed", output)
    passed = int(match.group(1)) if match else None
    match = re.search(r"(\d+)\s+failed", output)
    failed = int(match.group(1)) if match else None
    return passed, failed


def _parse_failures(output: str) -> list[str]:
    failures = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            failures.append(line.split("FAILED ", 1)[1].strip())
    return failures


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
