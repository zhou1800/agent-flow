from __future__ import annotations

from dataclasses import dataclass, field

from agents.worker import Worker
from flow_types import WorkerStatus
from llm.client import MockLLMClient
from tools.base import ToolResult


@dataclass
class DummyTool:
    calls: list[str] = field(default_factory=list)

    def echo(self, text: str) -> ToolResult:
        self.calls.append(text)
        return ToolResult(ok=True, summary="echo", data={"text": text}, elapsed_ms=0.1)


def test_worker_executes_tool_calls_and_counts() -> None:
    dummy = DummyTool()
    llm = MockLLMClient(
        script=[
            {"tool_calls": [{"tool": "dummy", "action": "echo", "args": {"text": "hi"}}]},
            {"status": "SUCCESS", "summary": "done", "artifacts": [], "metrics": {}, "next_actions": [], "failure_signature": ""},
        ]
    )
    worker = Worker("Implementer", llm, tools={"dummy": dummy})
    output = worker.run("goal", "step", inputs={}, memory=[])
    assert output.status == WorkerStatus.SUCCESS
    assert dummy.calls == ["hi"]
    assert output.metrics["model_calls"] == 2
    assert output.metrics["tool_calls"] == 1
    assert output.metrics["iteration_count"] == 2
