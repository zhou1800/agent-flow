from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from tools.grep_tool import GrepTool


def test_grep_tool_fallback_search_finds_matches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    file_path = tmp_path / "hay.txt"
    file_path.write_text("hay\nneedle here\n")

    result = GrepTool(tmp_path).search("needle")
    assert result.ok is True
    assert str(file_path) in result.data["output"]
    assert ":2:needle here" in result.data["output"]


def test_grep_tool_uses_rg_when_available(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rg" if name == "rg" else None)

    def fake_run(cmd, capture_output, text, check):
        assert cmd[0] == "rg"
        return SimpleNamespace(returncode=0, stdout="match\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GrepTool(tmp_path).search("pattern")
    assert result.ok is True
    assert result.data["output"] == "match\n"


def test_grep_tool_rg_no_matches_is_ok(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rg" if name == "rg" else None)

    def fake_run(cmd, capture_output, text, check):
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = GrepTool(tmp_path).search("pattern")
    assert result.ok is True
