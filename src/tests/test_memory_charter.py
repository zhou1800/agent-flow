from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from memory.store import MemoryStore


_REQUIRED_CHARTER_FIELDS = (
    "failure_signature",
    "root_cause_hypothesis",
    "strategy_change",
    "evidence_of_novelty",
    "retrieval_tags",
)


def _charter_metadata(lesson_id: str, lesson_type: str) -> dict[str, Any]:
    return {
        "id": lesson_id,
        "lesson_type": lesson_type,
        "failure_signature": "fs1",
        "root_cause_hypothesis": "hypothesis",
        "strategy_change": "change",
        "evidence_of_novelty": "novelty",
        "retrieval_tags": ["memory"],
        "component": "tests",
        "tags": [lesson_type],
    }


@pytest.mark.parametrize("lesson_type", ["failure", "retry"])
def test_write_lesson_requires_charter_fields(tmp_path: Path, lesson_type: str) -> None:
    store = MemoryStore(tmp_path)

    store.write_lesson(_charter_metadata("ok-" + lesson_type, lesson_type), "ok")

    for field in _REQUIRED_CHARTER_FIELDS:
        metadata = _charter_metadata("missing-" + lesson_type + "-" + field, lesson_type)
        metadata.pop(field)
        with pytest.raises(ValueError, match=r"(?i)lesson"):
            store.write_lesson(metadata, "body")


def test_write_lesson_denies_secret_metadata(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    metadata = _charter_metadata("secret-metadata", "failure")
    metadata["api_key"] = "supersecret"
    with pytest.raises(ValueError, match=r"(?i)secret"):
        store.write_lesson(metadata, "body")


def test_write_lesson_redacts_bearer_tokens(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path)
    lesson = store.write_lesson(_charter_metadata("redact-body", "failure"), "Authorization: Bearer supersecret")
    raw = lesson.path.read_text()
    assert "supersecret" not in raw

    loaded = store.load_lesson("redact-body")
    assert "supersecret" not in loaded.body
    assert "<REDACTED>" in loaded.body
