"""GrepTool uses ripgrep if available."""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

from .base import ToolResult


class GrepTool:
    name = "grep"

    def __init__(self, root: Path) -> None:
        self.root = root

    def search(self, pattern: str, path: str | None = None) -> ToolResult:
        start = time.perf_counter()
        target = self.root if path is None else (self.root / path)
        if shutil.which("rg"):
            result = subprocess.run(["rg", pattern, str(target)], capture_output=True, text=True, check=False)
            return ToolResult(
                ok=result.returncode in (0, 1),
                summary="rg search",
                data={"output": result.stdout},
                elapsed_ms=_elapsed_ms(start),
                error=None if result.returncode in (0, 1) else "rg error",
            )
        try:
            matches = []
            regex = re.compile(pattern)
            for file_path in target.rglob("*"):
                if file_path.is_file():
                    content = file_path.read_text(errors="ignore")
                    for line_no, line in enumerate(content.splitlines(), start=1):
                        if regex.search(line):
                            matches.append(f"{file_path}:{line_no}:{line}")
            return ToolResult(ok=True, summary="fallback grep", data={"output": "\n".join(matches)}, elapsed_ms=_elapsed_ms(start))
        except Exception as exc:
            return ToolResult(ok=False, summary="grep error", data={}, elapsed_ms=_elapsed_ms(start), error=str(exc))


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
