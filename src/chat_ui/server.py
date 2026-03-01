"""Local web chat UI for Tokimon."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from artifacts import ArtifactStore
from agents.worker import Worker
from llm.client import build_llm_client
from observability.reports import build_run_metrics_payload
from observability.reports import normalize_step_metrics
from observability.reports import write_metrics_and_dashboard
from runs import create_run_context
from tools.file_tool import FileTool
from tools.grep_tool import GrepTool
from tools.patch_tool import PatchTool
from tools.pytest_tool import PytestTool
from tools.web_tool import WebTool


_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Tokimon Chat</title>
    <style>
      :root { color-scheme: light dark; }
      body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      header { padding: 12px 16px; border-bottom: 1px solid #4443; font-weight: 600; }
      #wrap { display: grid; grid-template-rows: 1fr auto; height: calc(100vh - 49px); }
      #log { padding: 16px; overflow: auto; }
      .msg { margin: 0 0 12px 0; white-space: pre-wrap; }
      .user { font-weight: 600; }
      .assistant { opacity: 0.95; }
      form { display: grid; grid-template-columns: 1fr auto; gap: 10px; padding: 12px 16px; border-top: 1px solid #4443; }
      textarea { width: 100%; resize: vertical; min-height: 44px; padding: 10px; font: inherit; }
      button { padding: 10px 14px; font: inherit; }
      .meta { opacity: 0.7; font-size: 12px; margin-top: 4px; }
      .error { color: #b00020; }
      details.structured { margin-top: 8px; }
      details.structured > summary { cursor: pointer; opacity: 0.85; }
      pre { margin: 8px 0 0 0; padding: 10px; border: 1px solid #4443; border-radius: 6px; overflow: auto; }
      .ui-block { margin-top: 8px; padding: 10px; border: 1px solid #4443; border-radius: 6px; }
      .ui-block-title { font-size: 12px; opacity: 0.75; margin-bottom: 6px; }
      .ui-block pre { margin-top: 6px; }
    </style>
  </head>
  <body>
    <header>Tokimon Chat UI</header>
    <div id="wrap">
      <div id="log"></div>
      <form id="form">
        <textarea id="input" placeholder="Type a message…"></textarea>
        <button id="send" type="submit">Send</button>
      </form>
    </div>
    <script>
      const log = document.getElementById('log');
      const form = document.getElementById('form');
      const input = document.getElementById('input');
      const sendBtn = document.getElementById('send');
      const history = [];

      function append(role, content, meta) {
        const p = document.createElement('div');
        p.className = 'msg ' + role;
        const label = role === 'user' ? 'You' : 'Tokimon';
        const line = document.createElement('div');
        line.textContent = label + ': ' + content;
        p.appendChild(line);
        if (meta) {
          const m = document.createElement('div');
          m.className = 'meta';
          m.textContent = meta;
          p.appendChild(m);
        }
        log.appendChild(p);
        log.scrollTop = log.scrollHeight;
        return p;
      }

      function renderStructured(container, data) {
        if (!container || !data) return;
        const result = data.step_result || data;
        const details = document.createElement('details');
        details.className = 'structured';
        const s = document.createElement('summary');
        s.textContent = 'Structured result';
        details.appendChild(s);
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(result, null, 2);
        details.appendChild(pre);
        container.appendChild(details);

        const blocks = (result && Array.isArray(result.ui_blocks)) ? result.ui_blocks : [];
        if (!blocks.length) return;
        for (let i = 0; i < blocks.length; i++) {
          const block = blocks[i];
          const blockEl = document.createElement('div');
          blockEl.className = 'ui-block';
          const titleEl = document.createElement('div');
          titleEl.className = 'ui-block-title';
          const title = (block && block.title) ? String(block.title) : '';
          const type = (block && block.type) ? String(block.type) : 'unknown';
          titleEl.textContent = title || ('UI Block ' + (i + 1) + ' (' + type + ')');
          blockEl.appendChild(titleEl);

          const contentEl = document.createElement('pre');
          if (type === 'text') {
            contentEl.textContent = (block && block.text) ? String(block.text) : '';
          } else if (type === 'json') {
            contentEl.textContent = JSON.stringify(block ? block.data : null, null, 2);
          } else {
            contentEl.textContent = JSON.stringify(block, null, 2);
          }
          blockEl.appendChild(contentEl);
          container.appendChild(blockEl);
        }
      }

      async function sendMessage(message) {
        append('user', message);
        history.push({role: 'user', content: message});
        sendBtn.disabled = true;
        try {
          const res = await fetch('/api/send', {
            method: 'POST',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify({message, history})
          });
          const data = await res.json();
          const reply = data.reply || data.summary || '';
          const meta = data.status ? ('status=' + data.status) : '';
          const node = append('assistant', reply || '(no reply)', meta);
          renderStructured(node, data);
          history.push({role: 'assistant', content: reply || ''});
        } catch (err) {
          const msg = (err && err.message) ? err.message : String(err);
          append('assistant', 'Error: ' + msg, 'request failed');
          const last = log.lastChild;
          if (last) last.classList.add('error');
        } finally {
          sendBtn.disabled = false;
        }
      }

      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = (input.value || '').trim();
        if (!message) return;
        input.value = '';
        sendMessage(message);
      });
    </script>
  </body>
</html>
"""


@dataclass(frozen=True)
class ChatUIConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    llm_provider: str = "mock"
    workspace_dir: Path = field(default_factory=Path.cwd)


class _ChatHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], config: ChatUIConfig) -> None:
        super().__init__(server_address, _ChatUIHandler)
        self.config = config
        self.workspace_dir = config.workspace_dir.resolve()
        self.llm_client = build_llm_client(config.llm_provider, workspace_dir=self.workspace_dir)
        self.tools = {
            "file": FileTool(self.workspace_dir),
            "grep": GrepTool(self.workspace_dir),
            "patch": PatchTool(self.workspace_dir),
            "pytest": PytestTool(self.workspace_dir),
            "web": WebTool(),
        }
        runs_root = self.workspace_dir / "runs" / "chat-ui"
        self.run_context = create_run_context(runs_root)
        self.run_context.write_manifest({"runner": "chat-ui", "workspace_dir": str(self.workspace_dir)})
        self.artifact_store = ArtifactStore(self.run_context.artifacts_dir)
        self._step_lock = threading.Lock()
        self._step_index = 0
        self._run_start = time.perf_counter()
        self._step_metrics: dict[str, dict[str, Any]] = {}

    def handle_send(self, message: str, history: list[dict[str, Any]] | None) -> dict[str, Any]:
        history = history or []
        memory = _history_to_memory(history)
        worker = Worker("Chat", self.llm_client, self.tools)
        with self._step_lock:
            self._step_index += 1
            step_id = f"chat-{self._step_index:04d}"
        output = worker.run(goal=message, step_id=step_id, inputs={"message": message, "history": history}, memory=memory)
        raw_ui_blocks = output.data.get("ui_blocks") if isinstance(output.data, dict) else None
        ui_blocks: list[dict[str, Any]] = []
        if isinstance(raw_ui_blocks, list):
            ui_blocks = [block for block in raw_ui_blocks if isinstance(block, dict)]
        step_result: dict[str, Any] = {
            "status": output.status.value,
            "summary": output.summary,
            "artifacts": output.artifacts,
            "metrics": output.metrics,
            "next_actions": output.next_actions,
            "failure_signature": str(output.failure_signature or ""),
            "ui_blocks": ui_blocks,
        }
        self.artifact_store.write_step(
            task_id=self.run_context.run_id,
            step_id=step_id,
            artifacts=output.artifacts,
            outputs={"summary": output.summary},
            step_result=step_result,
        )
        step_metrics = normalize_step_metrics(
            step_id=step_id,
            attempt_id=1,
            status=output.status.value,
            artifacts=output.artifacts,
            raw_metrics=output.metrics,
            failure_signature=output.failure_signature,
        )
        with self._step_lock:
            self._step_metrics[step_id] = step_metrics
            wall_time_s = time.perf_counter() - self._run_start
            steps = [self._step_metrics[key] for key in sorted(self._step_metrics)]
            run_metrics_payload = build_run_metrics_payload(
                run_id=self.run_context.run_id,
                runner="chat-ui",
                wall_time_s=wall_time_s,
                steps=steps,
                tests_passed=None,
                tests_failed=None,
            )
            write_metrics_and_dashboard(self.run_context.reports_dir, run_metrics_payload)
        return {
            "status": output.status.value,
            "reply": output.summary,
            "summary": output.summary,
            "artifacts": output.artifacts,
            "metrics": output.metrics,
            "next_actions": output.next_actions,
            "failure_signature": output.failure_signature,
            "ui_blocks": ui_blocks,
            "run_id": self.run_context.run_id,
            "step_id": step_id,
            "step_result": step_result,
        }


class ChatUIServer:
    def __init__(self, config: ChatUIConfig) -> None:
        self._server = _ChatHTTPServer((config.host, int(config.port)), config)
        self._thread = threading.Thread(target=self._server.serve_forever, name="tokimon-chat-ui", daemon=True)

    @property
    def host(self) -> str:
        return str(self._server.server_address[0])

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def run_chat_ui(config: ChatUIConfig) -> None:
    server = ChatUIServer(config)
    server.start()
    print(f"Tokimon Chat UI: {server.url}")
    try:
        server._thread.join()
    except KeyboardInterrupt:
        server.stop()


class _ChatUIHandler(BaseHTTPRequestHandler):
    server: _ChatHTTPServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(_INDEX_HTML)
            return
        if parsed.path == "/healthz":
            self._send_json({"ok": True})
            return
        self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/send":
            self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            self._send_json({"ok": False, "error": "message must be a non-empty string"}, status=HTTPStatus.BAD_REQUEST)
            return
        history = payload.get("history")
        if history is not None and not isinstance(history, list):
            self._send_json({"ok": False, "error": "history must be a list"}, status=HTTPStatus.BAD_REQUEST)
            return
        response = self.server.handle_send(message.strip(), history)
        self._send_json({"ok": True, **response})

    def _read_json(self) -> dict[str, Any]:
        length = self.headers.get("content-length")
        if not length:
            raise ValueError("missing content-length")
        try:
            n = int(length)
        except ValueError as exc:
            raise ValueError("invalid content-length") from exc
        raw = self.rfile.read(max(0, n))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise ValueError("invalid json body") from exc
        if not isinstance(payload, dict):
            raise ValueError("json body must be an object")
        return payload

    def _send_html(self, html: str) -> None:
        data = (html or "").encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], *, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(int(status))
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _history_to_memory(history: list[dict[str, Any]], *, limit: int = 16, max_chars: int = 10_000) -> list[str]:
    trimmed = history[-limit:] if limit > 0 else []
    lines: list[str] = []
    total = 0
    for msg in trimmed:
        role = str(msg.get("role") or "").strip()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        line = f"{role}: {content}" if role else content
        total += len(line)
        if total > max_chars:
            lines.append("...(history truncated)")
            break
        lines.append(line)
    return lines
