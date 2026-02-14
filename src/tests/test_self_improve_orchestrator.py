from __future__ import annotations

from pathlib import Path

from llm.client import MockLLMClient
from self_improve.orchestrator import SelfImproveOrchestrator, SelfImproveSettings
from self_improve.workspace import clone_master, compute_changes


def test_self_improve_runs_sessions_and_merges_winner(tmp_path: Path) -> None:
    master = tmp_path / "master"
    (master / "proj").mkdir(parents=True, exist_ok=True)
    (master / "proj" / "__init__.py").write_text("")
    (master / "proj" / "app.py").write_text("def add(a, b):\n    return a - b\n")
    (master / "proj" / "tests").mkdir(parents=True, exist_ok=True)
    (master / "proj" / "tests" / "test_app.py").write_text(
        "from proj.app import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )

    def llm_factory(session_id: str) -> MockLLMClient:
        plan = {
            "status": "SUCCESS",
            "summary": "planned",
            "workflow": {"steps": [{"id": "fix", "worker": "Implementer"}]},
        }
        if session_id.endswith("-1"):
            return MockLLMClient(
                script=[
                    plan,
                    {"tool_calls": [{"tool": "file", "action": "write", "args": {"path": "proj/app.py", "content": "def add(a, b):\n    return a + b\n"}}]},
                    {"status": "SUCCESS", "summary": "fixed"},
                ]
            )
        return MockLLMClient(
            script=[
                plan,
                {"status": "SUCCESS", "summary": "no-op"},
            ]
        )

    settings = SelfImproveSettings(
        sessions_per_batch=2,
        batches=1,
        max_workers=2,
        include_paths=["proj"],
        pytest_args=["proj/tests"],
        merge_on_success=True,
    )
    orchestrator = SelfImproveOrchestrator(master, llm_factory=llm_factory, settings=settings)
    report = orchestrator.run("Fix proj.add", input_ref=None)

    assert report.batches[0].winner_session_id is not None
    assert report.batches[0].merged is True
    assert report.batches[0].master_evaluation is not None
    assert report.batches[0].master_evaluation.ok is True
    assert "return a + b" in (master / "proj" / "app.py").read_text()


def test_compute_changes_detects_added_files_when_workspace_path_contains_runs(tmp_path: Path) -> None:
    master = tmp_path / "master"
    (master / "proj").mkdir(parents=True, exist_ok=True)
    (master / "proj" / "app.py").write_text("print('hello')\n")

    workspace_root = tmp_path / "runs" / "session-workspace"
    clone_master(master, workspace_root, include_paths=["proj"])
    (workspace_root / "proj" / "new_file.txt").write_text("new\n")

    changes = compute_changes(master, workspace_root, include_paths=["proj"])
    assert any(
        change.kind == "add" and change.relpath == str(Path("proj") / "new_file.txt")
        for change in changes
    )
