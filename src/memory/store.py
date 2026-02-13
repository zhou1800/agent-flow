"""Memory store for Lessons and artifact index."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Lesson:
    metadata: dict[str, Any]
    body: str
    path: Path


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.lessons_dir = root / "lessons"
        self.artifacts_dir = root / "artifacts"
        self.index_path = root / "index.sqlite"
        self.lessons_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, metadata TEXT, body TEXT, tags TEXT, component TEXT, failure_signature TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, step_id TEXT, task_id TEXT, path TEXT, hash TEXT, metadata TEXT)"
            )
            try:
                conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(id, body, tags, component, failure_signature)"
                )
            except sqlite3.OperationalError:
                # FTS5 not available; fallback to table-only search.
                pass
            conn.commit()
        finally:
            conn.close()

    def write_lesson(self, metadata: dict[str, Any], body: str) -> Lesson:
        lesson_id = metadata.get("id") or metadata.get("lesson_id")
        if not lesson_id:
            raise ValueError("Lesson metadata must include an 'id'")
        path = self.lessons_dir / f"lesson-{lesson_id}.md"
        header = json.dumps(metadata, sort_keys=True)
        content = f"{header}\n---\n{body}\n"
        path.write_text(content)
        self._index_lesson(lesson_id, metadata, body)
        return Lesson(metadata=metadata, body=body, path=path)

    def _index_lesson(self, lesson_id: str, metadata: dict[str, Any], body: str) -> None:
        tags = ",".join(metadata.get("tags", [])) if isinstance(metadata.get("tags"), list) else str(metadata.get("tags", ""))
        component = metadata.get("component", "")
        failure_signature = metadata.get("failure_signature", "")
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute(
                "REPLACE INTO lessons (id, metadata, body, tags, component, failure_signature) VALUES (?, ?, ?, ?, ?, ?)",
                (lesson_id, json.dumps(metadata), body, tags, component, failure_signature),
            )
            try:
                conn.execute(
                    "REPLACE INTO lessons_fts (id, body, tags, component, failure_signature) VALUES (?, ?, ?, ?, ?)",
                    (lesson_id, body, tags, component, failure_signature),
                )
            except sqlite3.OperationalError:
                pass
            conn.commit()
        finally:
            conn.close()

    def load_lesson(self, lesson_id: str) -> Lesson:
        path = self.lessons_dir / f"lesson-{lesson_id}.md"
        content = path.read_text()
        header, body = content.split("---", 1)
        metadata = json.loads(header.strip())
        return Lesson(metadata=metadata, body=body.strip(), path=path)

    def index_artifact(self, artifact_id: str, step_id: str, task_id: str, path: Path, digest: str, metadata: dict[str, Any]) -> None:
        conn = sqlite3.connect(self.index_path)
        try:
            conn.execute(
                "REPLACE INTO artifacts (id, step_id, task_id, path, hash, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (artifact_id, step_id, task_id, str(path), digest, json.dumps(metadata)),
            )
            conn.commit()
        finally:
            conn.close()

    def list_artifacts(self, task_id: str | None = None, step_id: str | None = None) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self.index_path)
        try:
            clauses = []
            params: list[Any] = []
            if task_id:
                clauses.append("task_id = ?")
                params.append(task_id)
            if step_id:
                clauses.append("step_id = ?")
                params.append(step_id)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            cursor = conn.execute(f"SELECT id, step_id, task_id, path, hash, metadata FROM artifacts {where}", params)
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row[0],
                        "step_id": row[1],
                        "task_id": row[2],
                        "path": row[3],
                        "hash": row[4],
                        "metadata": json.loads(row[5]) if row[5] else {},
                    }
                )
            return results
        finally:
            conn.close()

    def retrieve(self, query: str, stage: int, limit: int = 5, tags: list[str] | None = None,
                 failure_signature: str | None = None, component: str | None = None) -> list[Lesson]:
        tags = tags or []
        conn = sqlite3.connect(self.index_path)
        try:
            rows = []
            if stage == 1:
                rows = _search(conn, query, tags=tags, component=component, failure_signature=failure_signature, limit=limit)
            elif stage == 2:
                rows = _search(conn, query, tags=tags, component=component, failure_signature=failure_signature, limit=limit)
                if len(rows) < limit and tags:
                    rows += _search(conn, " ".join(tags), tags=tags, component=component, failure_signature=failure_signature, limit=limit - len(rows))
            else:
                rows = _search(conn, query, tags=tags, component=component, failure_signature=failure_signature, limit=limit)
                if len(rows) < limit and failure_signature:
                    rows += _search(conn, failure_signature, tags=tags, component=component, failure_signature=failure_signature, limit=limit - len(rows))
            lessons = []
            seen = set()
            for row in rows:
                lesson_id = row[0]
                if lesson_id in seen:
                    continue
                seen.add(lesson_id)
                lessons.append(self.load_lesson(lesson_id))
            return lessons
        finally:
            conn.close()


def _search(conn: sqlite3.Connection, query: str, tags: list[str], component: str | None,
            failure_signature: str | None, limit: int) -> list[tuple]:
    params: list[Any] = []
    clauses: list[str] = []
    if component:
        clauses.append("component = ?")
        params.append(component)
    if failure_signature:
        clauses.append("failure_signature = ?")
        params.append(failure_signature)
    if tags:
        clauses.append("tags LIKE ?")
        params.append("%" + "%".join(tags) + "%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    try:
        cursor = conn.execute(
            f"SELECT id FROM lessons_fts WHERE lessons_fts MATCH ? {where} LIMIT ?",
            [query, *params, limit],
        )
        return cursor.fetchall()
    except sqlite3.OperationalError:
        cursor = conn.execute(
            f"SELECT id FROM lessons {where} LIMIT ?",
            [*params, limit],
        )
        return cursor.fetchall()
