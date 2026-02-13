import shutil
import uuid
from pathlib import Path

from memory.store import MemoryStore
from skills.builder import SkillBuilder
from skills.registry import SkillRegistry
from skills.spec import SkillSpec


def test_skill_builder_and_registry(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    memory_store = MemoryStore(tmp_path / "memory")
    builder = SkillBuilder(repo_root, memory_store)
    name = f"TempSkill{uuid.uuid4().hex[:6]}"
    spec = SkillSpec(
        name=name,
        purpose="Temporary skill for testing.",
        contract="Return a placeholder.",
        required_tools=["file"],
        retrieval_prefs={"stage1": "tight"},
    )
    manifest_path = repo_root / "skills_generated" / "manifest.json"
    original_manifest = manifest_path.read_text() if manifest_path.exists() else None

    try:
        ok = builder.build_skill(spec, "test justification")
        assert ok is True
        registry = SkillRegistry(repo_root)
        registry.load()
        assert registry.get(name) is not None
    finally:
        module_path = repo_root / "skills_generated" / f"{name.lower()}.py"
        test_path = repo_root / "tests" / "skills_generated" / f"test_{name.lower()}.py"
        skills_tests_dir = repo_root / "tests" / "skills_generated"
        if module_path.exists():
            module_path.unlink()
        if test_path.exists():
            test_path.unlink()
        cache_dir = skills_tests_dir / "__pycache__"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        if skills_tests_dir.exists() and not any(skills_tests_dir.iterdir()):
            skills_tests_dir.rmdir()
        if original_manifest is not None:
            manifest_path.write_text(original_manifest)
        elif manifest_path.exists():
            manifest_path.unlink()
