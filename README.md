# Agent-Flow

Doc-led hierarchical manager/worker agent system with workflow orchestration, novelty-gated retries, offline benchmarks, and a self-improvement mode.

The CLI entrypoint is `agent-flow` (alias: `super-agent`).

## Install
Run from the repository root:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e src[dev]
```

## Use the CLI
Show commands:
```bash
source .venv/bin/activate && agent-flow --help
```

Run the benchmark suite (baseline vs hierarchical) and write a report under `src/runs/`:
```bash
source .venv/bin/activate && agent-flow run-suite
```

Run a single benchmark task:
```bash
source .venv/bin/activate && agent-flow run-task --task-id stats-summary
source .venv/bin/activate && agent-flow run-task --task-id lru-cache --runner baseline
```
Task ids live in `src/benchmarks/tasks/*/task.json`.

Inspect or resume a run:
```bash
source .venv/bin/activate && agent-flow inspect-run --run-path src/runs/run-<id>
source .venv/bin/activate && agent-flow resume-run --run-path src/runs/run-<id>
```

List skills (built-in + generated):
```bash
source .venv/bin/activate && agent-flow list-skills
```

Self-improve (experimental; uses the current working directory as the "master" workspace):
```bash
source .venv/bin/activate && agent-flow self-improve --goal "Improve agent-flow based on docs and failing tests."
```

Note: the CLI currently uses `MockLLMClient` (no real model calls). To plug in a real model, implement an `LLMClient` and wire it into `src/cli.py`.

## Development
Run tests:
```bash
source .venv/bin/activate && pytest --maxfail=1 -c src/pyproject.toml src/tests
```

## Docs
- Architecture/specs: `docs/c4/`
- Requirements: `docs/c4/level-3-component/agent-flow/requirements.md`
- Test plan: `docs/c4/level-3-component/agent-flow/test-plan.md`
- AI agent workflow rules: `AGENTS.md` and `docs/helix.md`
