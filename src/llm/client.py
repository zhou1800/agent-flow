"""LLM client abstractions and mock adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMClient(Protocol):
    def send(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        ...


class StubLLMClient:
    def send(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError("Stub client not configured")


@dataclass
class MockLLMClient:
    script: list[dict[str, Any]]

    def send(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.script:
            return self.script.pop(0)
        return {
            "status": "PARTIAL",
            "summary": "mock response",
            "artifacts": [],
            "metrics": {"token_estimate": 0},
            "next_actions": [],
            "failure_signature": "mock-empty",
        }


class PlaceholderLLMClient:
    """Placeholder for plugging in a real client. Override send()."""

    def send(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
             response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError("Integrate your LLM client here.")
