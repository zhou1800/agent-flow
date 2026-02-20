"""PatchTool applies unified diffs with validation."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from .base import ToolResult, elapsed_ms


class PatchTool:
    name = "patch"

    def __init__(self, root: Path) -> None:
        self.root = root

    def apply(self, patch_text: str) -> ToolResult:
        start = time.perf_counter()
        if not shutil.which("git"):
            return ToolResult(ok=False, summary="git not available", data={}, elapsed_ms=elapsed_ms(start), error="git is required")
        try:
            check = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=patch_text.encode(),
                cwd=self.root,
                capture_output=True,
                check=False,
            )
            if check.returncode != 0:
                return ToolResult(
                    ok=False,
                    summary="patch validation failed",
                    data={"stdout": check.stdout.decode(), "stderr": check.stderr.decode()},
                    elapsed_ms=elapsed_ms(start),
                    error="patch check failed",
                )
            apply = subprocess.run(
                ["git", "apply", "-"],
                input=patch_text.encode(),
                cwd=self.root,
                capture_output=True,
                check=False,
            )
            if apply.returncode != 0:
                return ToolResult(
                    ok=False,
                    summary="patch apply failed",
                    data={"stdout": apply.stdout.decode(), "stderr": apply.stderr.decode()},
                    elapsed_ms=elapsed_ms(start),
                    error="patch apply failed",
                )
            return ToolResult(ok=True, summary="patch applied", data={}, elapsed_ms=elapsed_ms(start))
        except Exception as exc:
            return ToolResult(ok=False, summary="patch error", data={}, elapsed_ms=elapsed_ms(start), error=str(exc))
