"""Opt-in approval gate for high-risk tool calls."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Literal


ToolApprovalMode = Literal["off", "block", "deny"]


def tool_approval_mode_from_env(env: dict[str, str] | None = None) -> ToolApprovalMode:
    if env is None:
        env = os.environ  # pragma: no cover
    raw = str(env.get("TOKIMON_TOOL_APPROVAL_MODE", "off") or "off").strip().lower()
    if raw not in {"off", "block", "deny"}:
        raw = "off"
    return raw  # type: ignore[return-value]


def approval_id_for(tool: str, action: str, args_hash: str) -> str:
    payload = json.dumps(
        {"tool": str(tool or ""), "action": str(action or ""), "args_hash": str(args_hash or "")},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_approval_request(
    *,
    tool: str,
    action: str,
    args_hash: str,
    args_preview: dict[str, Any],
    reason: str,
    max_reason_chars: int = 200,
) -> dict[str, Any]:
    bounded_reason = str(reason or "").strip()
    if len(bounded_reason) > max_reason_chars:
        bounded_reason = bounded_reason[:max_reason_chars] + "...(truncated)"
    return {
        "approval_id": approval_id_for(tool, action, args_hash),
        "tool": str(tool or ""),
        "action": str(action or ""),
        "args_hash": str(args_hash or ""),
        "args_preview": args_preview,
        "reason": bounded_reason,
    }

