from pathlib import Path

from memory.store import MemoryStore


def test_staged_retrieval(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    store.write_lesson({"id": "l1", "tags": ["alpha"], "component": "core"}, "alpha lesson")
    store.write_lesson({"id": "l2", "tags": ["beta"], "component": "core"}, "beta lesson")

    stage1 = store.retrieve("alpha", stage=1, limit=5)
    assert any(lesson.metadata["id"] == "l1" for lesson in stage1)

    stage2 = store.retrieve("alpha", stage=2, limit=5, tags=["beta"], component="core")
    assert len(stage2) >= len(stage1)
