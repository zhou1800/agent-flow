"""CLI entrypoint for Tokimon."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import replace
from pathlib import Path

from chat_ui.server import ChatUIConfig, run_chat_ui
from benchmarks.harness import EvaluationHarness
from llm.client import (
    ClaudeCLIClient,
    ClaudeCLISettings,
    CodexCLIClient,
    CodexCLISettings,
    LLMClient,
    MockLLMClient,
    build_llm_client,
)
from memory.store import MemoryStore
from runners.baseline import BaselineRunner
from runners.hierarchical import HierarchicalRunner
from self_improve.orchestrator import SelfImproveOrchestrator, SelfImproveSettings
from self_improve.provider_mix import mixed_provider_for_session, validate_mixed_sessions_per_batch
from skills.builder import SkillBuilder
from skills.registry import SkillRegistry
from skills.spec import SkillSpec


def build_parser(*, exit_on_error: bool = True) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tokimon", exit_on_error=exit_on_error)
    subparsers = parser.add_subparsers(dest="command")

    auto = subparsers.add_parser("auto")
    auto.add_argument("prompt")

    run_task = subparsers.add_parser("run-task")
    run_task.add_argument("--task-id", required=True)
    run_task.add_argument("--runner", choices=["baseline", "hierarchical"], default="hierarchical", help=argparse.SUPPRESS)

    subparsers.add_parser("run-suite")

    resume = subparsers.add_parser("resume-run")
    resume.add_argument("--run-path", required=True)

    inspect_run = subparsers.add_parser("inspect-run")
    inspect_run.add_argument("--run-path", required=True)

    subparsers.add_parser("list-skills")

    build_skill = subparsers.add_parser("build-skill")
    build_skill.add_argument("--name", required=True)
    build_skill.add_argument("--purpose", required=True)
    build_skill.add_argument("--contract", required=True)
    build_skill.add_argument("--tools", default="")
    build_skill.add_argument("--justification", required=True)

    self_improve = subparsers.add_parser("self-improve")
    self_improve.add_argument("--goal", default="Improve tokimon based on docs and failing tests.")
    self_improve.add_argument("--input", default=None)
    self_improve.add_argument("--sessions", type=int, default=5, help=argparse.SUPPRESS)
    self_improve.add_argument("--batches", type=int, default=1, help=argparse.SUPPRESS)
    self_improve.add_argument("--workers", type=int, default=4, help=argparse.SUPPRESS)
    self_improve.add_argument("--no-merge", action="store_true", help=argparse.SUPPRESS)
    self_improve.add_argument(
        "--llm",
        choices=["mock", "codex", "claude", "mixed"],
        default=os.environ.get("TOKIMON_LLM", "mixed"),
        help=argparse.SUPPRESS,
    )

    chat_ui = subparsers.add_parser("chat-ui")
    chat_ui.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    chat_ui.add_argument("--port", type=int, default=8765)
    chat_ui.add_argument(
        "--llm",
        choices=["mock", "codex", "claude"],
        default=os.environ.get("TOKIMON_LLM", "mock"),
        help=argparse.SUPPRESS,
    )
    chat_ui.add_argument("--workspace", default=None, help=argparse.SUPPRESS)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "auto":
        routed_argv = _auto_decide_argv(str(args.prompt))
        if not routed_argv:
            parser.print_help()
            return 0
        return main(routed_argv)

    repo_root = Path(__file__).resolve().parent
    workspace_root = repo_root.parent
    runs_root = workspace_root / "runs"
    llm_client = MockLLMClient(script=[])

    if args.command == "run-task":
        task_dir = _find_task_dir(repo_root, args.task_id)
        if task_dir is None:
            raise SystemExit(f"Unknown task: {args.task_id}")
        spec_path = task_dir / "task.json"
        spec = json.loads(spec_path.read_text())
        workspace = runs_root / "workspaces" / args.task_id / args.runner
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(task_dir / "starter", workspace)
        tests_dst = workspace / "tests"
        shutil.copytree(task_dir / "tests", tests_dst)
        test_args = [str(tests_dst)]
        if args.runner == "baseline":
            runner = BaselineRunner(workspace, llm_client, base_dir=runs_root)
            runner.run(spec.get("description", ""), task_id=args.task_id, test_args=test_args)
        else:
            runner = HierarchicalRunner(workspace, llm_client, base_dir=runs_root)
            runner.run(spec.get("description", ""), task_steps=None, task_id=args.task_id, test_args=test_args)
        return 0

    if args.command == "run-suite":
        harness = EvaluationHarness(repo_root, runs_dir=runs_root)
        harness.run_suite()
        return 0

    if args.command == "resume-run":
        run_path = Path(args.run_path)
        workflow_state = run_path / "workflow_state.json"
        if not workflow_state.exists():
            raise SystemExit("workflow_state.json not found")
        runner = HierarchicalRunner(repo_root, llm_client, base_dir=runs_root)
        runner.resume(run_path)
        return 0

    if args.command == "inspect-run":
        run_path = Path(args.run_path)
        run_manifest = run_path / "run.json"
        workflow_state = run_path / "workflow_state.json"
        if run_manifest.exists():
            print(run_manifest.read_text())
        if workflow_state.exists():
            print(workflow_state.read_text())
        return 0

    if args.command == "list-skills":
        registry = SkillRegistry(repo_root)
        registry.load()
        for spec in registry.list_skills():
            print(f"{spec.name}: {spec.purpose}")
        return 0

    if args.command == "build-skill":
        tools = [t.strip() for t in args.tools.split(",") if t.strip()]
        spec = SkillSpec(
            name=args.name,
            purpose=args.purpose,
            contract=args.contract,
            required_tools=tools,
            retrieval_prefs={"stage1": "tight", "stage2": "broaden", "stage3": "targeted"},
        )
        builder = SkillBuilder(repo_root, MemoryStore(repo_root / "memory"))
        ok = builder.build_skill(spec, args.justification)
        return 0 if ok else 1

    if args.command == "self-improve":
        master_root = Path.cwd().resolve()
        settings = SelfImproveSettings(
            sessions_per_batch=args.sessions,
            batches=args.batches,
            max_workers=args.workers,
            merge_on_success=not args.no_merge,
        )
        llm_provider = str(args.llm or "mock").strip().lower()
        if llm_provider == "mixed":
            validate_mixed_sessions_per_batch(int(args.sessions))

        def llm_factory(_session_id: str, workspace_dir: Path):
            session_provider = llm_provider
            if llm_provider == "mixed":
                session_provider = mixed_provider_for_session(_session_id)

            if session_provider in {"codex", "codex-cli"}:
                codex_settings = CodexCLISettings.from_env()
                if "TOKIMON_CODEX_SANDBOX" not in os.environ:
                    codex_settings = replace(codex_settings, sandbox="workspace-write")
                if "TOKIMON_CODEX_APPROVAL" not in os.environ:
                    codex_settings = replace(codex_settings, ask_for_approval="never")
                if "TOKIMON_CODEX_SEARCH" not in os.environ:
                    codex_settings = replace(codex_settings, search=True)
                if "TOKIMON_CODEX_TIMEOUT_S" not in os.environ:
                    codex_settings = replace(codex_settings, timeout_s=240)
                return CodexCLIClient(workspace_dir, settings=codex_settings)

            if session_provider in {"claude", "claude-cli"}:
                claude_settings = ClaudeCLISettings.from_env()
                if "TOKIMON_CLAUDE_TIMEOUT_S" not in os.environ:
                    claude_settings = replace(claude_settings, timeout_s=240)
                return ClaudeCLIClient(workspace_dir, settings=claude_settings)

            return build_llm_client(session_provider, workspace_dir=workspace_dir)

        orchestrator = SelfImproveOrchestrator(master_root, llm_factory=llm_factory, settings=settings)
        try:
            report = orchestrator.run(args.goal, input_ref=args.input)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps({"run_root": report.run_root}, indent=2))
        return 0

    if args.command == "chat-ui":
        workspace_dir = Path(args.workspace).resolve() if args.workspace else Path.cwd().resolve()
        config = ChatUIConfig(
            host=str(args.host),
            port=int(args.port),
            llm_provider=str(args.llm),
            workspace_dir=workspace_dir,
        )
        run_chat_ui(config)
        return 0

    return 1


def _find_task_dir(repo_root: Path, task_id: str) -> Path | None:
    tasks_dir = repo_root / "benchmarks" / "tasks"
    if not tasks_dir.exists():
        return None
    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        spec_path = task_dir / "task.json"
        if not spec_path.exists():
            continue
        spec = json.loads(spec_path.read_text())
        if spec.get("id") == task_id:
            return task_dir
    return None


_AUTO_ALLOWED_COMMANDS: frozenset[str] = frozenset({"run-suite", "list-skills", "run-task", "self-improve"})


def _auto_decide_argv(prompt: str, *, llm_client: LLMClient | None = None) -> list[str]:
    """Convert a free-form prompt into a concrete CLI argv list.

    Primary behavior: use an AI router to select an argv list.
    Fallback: deterministic heuristic routing when the router fails.
    """

    normalized = prompt.strip()
    if not normalized:
        return []

    routed = _auto_route_with_llm(normalized, llm_client=llm_client)
    if routed:
        return routed

    return _auto_route_heuristic(normalized)


def _auto_route_with_llm(prompt: str, *, llm_client: LLMClient | None) -> list[str] | None:
    normalized = prompt.strip()
    if not normalized:
        return None

    client = llm_client or _build_auto_router_client(Path.cwd().resolve())
    messages = [
        {
            "role": "system",
            "content": "\n".join(
                [
                    "You are Tokimon's CLI router.",
                    "Given a user prompt, choose exactly one Tokimon subcommand to run.",
                    "",
                    "Allowed commands (argv[0]): run-suite, list-skills, run-task, self-improve.",
                    "Return JSON with: {\"status\":\"SUCCESS\",\"argv\":[...]} and nothing else.",
                    "Rules:",
                    "- argv excludes the leading 'tokimon'.",
                    "- Use minimal argv; prefer self-improve for learning/improving prompts.",
                    "- run-task MUST include: --task-id <id>.",
                    "- Do NOT return 'auto' and do NOT include -h/--help.",
                    "- Do NOT request tool calls.",
                    "",
                    "Examples:",
                    "Prompt: run suite -> {\"status\":\"SUCCESS\",\"argv\":[\"run-suite\"]}",
                    "Prompt: list skills -> {\"status\":\"SUCCESS\",\"argv\":[\"list-skills\"]}",
                    "Prompt: run task demo-1 -> {\"status\":\"SUCCESS\",\"argv\":[\"run-task\",\"--task-id\",\"demo-1\"]}",
                    "Prompt: please learn X -> {\"status\":\"SUCCESS\",\"argv\":[\"self-improve\",\"--goal\",\"please learn X\"]}",
                ]
            ),
        },
        {"role": "user", "content": normalized},
    ]

    try:
        response = client.send(messages, tools=None)
    except Exception:
        return None
    argv = _extract_routed_argv(response)
    if argv is None:
        return None
    if not _validate_routed_argv(argv):
        return None
    return argv


def _extract_routed_argv(response: object) -> list[str] | None:
    if not isinstance(response, dict):
        return None
    raw = response.get("argv")
    if raw is None:
        return None
    if isinstance(raw, str):
        candidate: list[object] = [raw]
    elif isinstance(raw, list):
        candidate = raw
    else:
        return None

    argv: list[str] = []
    for item in candidate:
        if not isinstance(item, str):
            return None
        stripped = item.strip()
        if not stripped:
            continue
        argv.append(stripped)
    if not argv:
        return None
    return argv


def _validate_routed_argv(argv: list[str]) -> bool:
    if argv[0] not in _AUTO_ALLOWED_COMMANDS:
        return False
    if any(arg in {"-h", "--help"} for arg in argv):
        return False

    parser = build_parser(exit_on_error=False)
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, ValueError):
        return False
    except SystemExit:
        return False
    if getattr(parsed, "command", None) != argv[0]:
        return False
    return True


def _auto_router_provider() -> str:
    provider = (os.environ.get("TOKIMON_LLM") or "").strip().lower()
    if provider in {"codex", "codex-cli"}:
        return "codex"
    if provider in {"claude", "claude-cli"}:
        return "claude"
    if provider in {"mock"}:
        return "mock"
    if provider in {"mixed"}:
        return "codex"
    return "codex"


def _build_auto_router_client(workspace_dir: Path) -> LLMClient:
    provider = _auto_router_provider()
    if provider == "codex":
        codex_settings = replace(
            CodexCLISettings.from_env(),
            sandbox="read-only",
            ask_for_approval="never",
            search=False,
            timeout_s=60,
        )
        return CodexCLIClient(workspace_dir, settings=codex_settings)
    if provider == "claude":
        claude_settings = replace(ClaudeCLISettings.from_env(), timeout_s=60)
        return ClaudeCLIClient(workspace_dir, settings=claude_settings)
    if provider == "mock":
        return MockLLMClient(script=[])
    try:
        return build_llm_client(provider, workspace_dir=workspace_dir)
    except Exception:
        return MockLLMClient(script=[])


def _auto_route_heuristic(prompt: str) -> list[str]:
    normalized = prompt.strip()
    if not normalized:
        return []

    lower = normalized.lower()

    if lower in {"run-suite", "suite"} or "run suite" in lower:
        return ["run-suite"]

    if lower in {"list-skills", "skills"} or "list skills" in lower:
        return ["list-skills"]

    task_match = re.search(
        r"(?:^|\b)(?:run\s+task\s+|task\s*[:=]\s*|task-id\s*[:=]\s*)([A-Za-z0-9_.-]+)(?:\b|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if task_match:
        return ["run-task", "--task-id", task_match.group(1)]

    return ["self-improve", "--goal", normalized]


if __name__ == "__main__":
    raise SystemExit(main())
