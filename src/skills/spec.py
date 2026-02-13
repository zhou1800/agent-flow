"""Skill specification structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillSpec:
    name: str
    purpose: str
    contract: str
    required_tools: list[str] = field(default_factory=list)
    retrieval_prefs: dict[str, Any] = field(default_factory=dict)
    module: str | None = None
