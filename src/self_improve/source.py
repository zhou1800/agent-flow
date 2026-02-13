"""Helpers for reading optional self-improvement inputs (URL, file, or inline text)."""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputPayload:
    kind: str  # "none" | "url" | "file" | "text"
    ref: str | None
    content: str


def read_optional_input(ref: str | None, max_bytes: int = 512_000) -> InputPayload:
    if not ref:
        return InputPayload(kind="none", ref=None, content="")

    ref = ref.strip()
    if ref.startswith(("http://", "https://")):
        return _read_url(ref, max_bytes=max_bytes)

    path = Path(ref)
    if path.exists() and path.is_file():
        content = path.read_text(errors="replace")
        if len(content.encode()) > max_bytes:
            content = content.encode()[:max_bytes].decode(errors="replace")
        return InputPayload(kind="file", ref=str(path), content=content)

    return InputPayload(kind="text", ref=None, content=ref)


def _read_url(url: str, max_bytes: int) -> InputPayload:
    req = urllib.request.Request(url, headers={"User-Agent": "agent-flow-self-improve"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        data = data[:max_bytes]
    content = data.decode(errors="replace")
    return InputPayload(kind="url", ref=url, content=content)
