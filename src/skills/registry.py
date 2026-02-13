"""Skill registry for built-in and generated skills."""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skills.spec import SkillSpec


@dataclass
class SkillEntry:
    spec: SkillSpec
    module: Any


class SkillRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.generated_dir = root / "skills_generated"
        self.manifest_path = self.generated_dir / "manifest.json"
        self._skills: dict[str, SkillEntry] = {}

    def load(self) -> None:
        self._skills.clear()
        self._load_builtin()
        self._load_generated()

    def _load_builtin(self) -> None:
        try:
            module = importlib.import_module("skills_builtin")
        except ModuleNotFoundError:
            return
        specs = getattr(module, "SKILLS", [])
        for spec in specs:
            self._skills[spec.name] = SkillEntry(spec=spec, module=module)

    def _load_generated(self) -> None:
        if not self.manifest_path.exists():
            return
        data = json.loads(self.manifest_path.read_text())
        for entry in data.get("skills", []):
            module_name = entry["module"]
            spec_data = entry["spec"]
            module = importlib.import_module(module_name)
            spec = SkillSpec(**spec_data)
            self._skills[spec.name] = SkillEntry(spec=spec, module=module)

    def reload(self) -> None:
        for entry in self._skills.values():
            importlib.reload(entry.module)
        self.load()

    def list_skills(self) -> list[SkillSpec]:
        return [entry.spec for entry in self._skills.values()]

    def get(self, name: str) -> SkillEntry | None:
        return self._skills.get(name)
