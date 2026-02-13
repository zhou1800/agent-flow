"""Artifact store for workflow steps."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from memory.store import MemoryStore


class ArtifactStore:
    def __init__(self, base_dir: Path, memory_store: MemoryStore | None = None) -> None:
        self.base_dir = base_dir
        self.memory_store = memory_store

    def write_step(self, task_id: str, step_id: str, artifacts: list[dict[str, Any]], outputs: dict[str, Any] | None = None) -> str:
        step_dir = self.base_dir / step_id
        step_dir.mkdir(parents=True, exist_ok=True)
        outputs_path = step_dir / "outputs.json"
        outputs_path.write_text(json.dumps(outputs or {}, indent=2))
        artifacts_path = step_dir / "artifacts.json"
        artifacts_path.write_text(json.dumps(artifacts, indent=2))
        digest = self._hash_files([outputs_path, artifacts_path])
        if self.memory_store:
            artifact_id = f"{task_id}-{step_id}-{digest[:8]}"
            self.memory_store.index_artifact(artifact_id, step_id, task_id, step_dir, digest, {"count": len(artifacts)})
        return digest

    def _hash_files(self, paths: list[Path]) -> str:
        hasher = hashlib.sha256()
        for path in paths:
            hasher.update(path.read_bytes())
        return hasher.hexdigest()
