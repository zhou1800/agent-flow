"""Skill builder pipeline."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.store import MemoryStore
from skills.spec import SkillSpec
from tools.pytest_tool import PytestTool


class SkillBuilder:
    def __init__(self, repo_root: Path, memory_store: MemoryStore) -> None:
        self.repo_root = repo_root
        self.generated_dir = repo_root / "skills_generated"
        self.manifest_path = self.generated_dir / "manifest.json"
        self.memory_store = memory_store
        self.generated_dir.mkdir(parents=True, exist_ok=True)

    def build_skill(self, spec: SkillSpec, justification: str) -> bool:
        module_name = f"skills_generated.{spec.name.lower()}"
        module_path = self.generated_dir / f"{spec.name.lower()}.py"
        spec.module = module_name
        module_path.write_text(_module_template(spec))
        test_path = self.repo_root / "tests" / "skills_generated"
        test_path.mkdir(parents=True, exist_ok=True)
        test_file = test_path / f"test_{spec.name.lower()}.py"
        test_file.write_text(_test_template(spec))

        pytest_tool = PytestTool(self.repo_root)
        result = pytest_tool.run([str(test_file)])
        if not result.ok:
            module_path.unlink(missing_ok=True)
            test_file.unlink(missing_ok=True)
            return False

        manifest = {"skills": []}
        if self.manifest_path.exists():
            manifest = json.loads(self.manifest_path.read_text())
        manifest["skills"].append({"module": module_name, "spec": _spec_to_dict(spec)})
        self.manifest_path.write_text(json.dumps(manifest, indent=2))
        self._write_lesson(spec, justification)
        return True

    def _write_lesson(self, spec: SkillSpec, justification: str) -> None:
        lesson_id = str(uuid.uuid4())
        metadata = {
            "id": lesson_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tags": ["skill", spec.name],
            "component": "skills",
        }
        body = (
            f"Created skill {spec.name}.\n"
            f"Purpose: {spec.purpose}\n"
            f"Contract: {spec.contract}\n"
            f"Justification: {justification}\n"
        )
        self.memory_store.write_lesson(metadata, body)


def _module_template(spec: SkillSpec) -> str:
    return (
        "from skills.spec import SkillSpec\n\n"
        f"SKILL_SPEC = SkillSpec(name=\"{spec.name}\", purpose=\"{spec.purpose}\", "
        f"contract=\"{spec.contract}\", required_tools={spec.required_tools}, retrieval_prefs={spec.retrieval_prefs}, module=\"{spec.module}\")\n\n"
        "def execute(context):\n"
        "    return {\"status\": \"PARTIAL\", \"summary\": \"not implemented\"}\n"
    )


def _test_template(spec: SkillSpec) -> str:
    return (
        "from skills_generated.{name} import SKILL_SPEC\n\n"
        "def test_skill_spec():\n"
        "    assert SKILL_SPEC.name == \"{spec_name}\"\n"
    ).format(name=spec.name.lower(), spec_name=spec.name)


def _spec_to_dict(spec: SkillSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "purpose": spec.purpose,
        "contract": spec.contract,
        "required_tools": spec.required_tools,
        "retrieval_prefs": spec.retrieval_prefs,
        "module": spec.module,
    }
