# π

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → plan → review → implement workflows.

## Stack

- Python 3.13+ with uv, hatchling build
- claude-agent-sdk, dspy, click, rich
- pytest + pytest-asyncio for testing
- ruff for lint/format

## Commands

- Run: `π "prompt"` or `π "prompt" -t high -m workflow`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov`

## CLI Options

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `-t/--thinking` | low/med/high | low | Model tier (haiku/sonnet/opus) |
| `-p/--provider` | claude/antigravity/openai | claude | LM provider |
| `-m/--mode` | auto/simple/workflow | auto | Execution mode |
| `-v/--version` | — | — | Show version |

## Environment

- `CLIPROXY_API_BASE` — DSPy LM endpoint (default: localhost:8317)
- `CLIPROXY_API_KEY` — API key (required)

## Architecture

**Two modes:**

- **Simple**: Single ReAct agent with 3 tools (research, clarify, plan)
- **Workflow**: 5-stage pipeline with per-stage model tiers:
  - Clarify (low) → Research (high) → Plan (high) → Review (med) → Implement (med)

**Module structure:**

- `cli.py` — Entry point, mode routing
- `workflow/` — Core workflow execution
  - `bridge.py` — Tool functions bridging sync→async to Claude SDK
  - `module.py` — DSPy module with 5 ReAct agents
  - `router.py` — Auto-classifies objective to simple/workflow
  - `session.py` — Tracks session IDs across tool calls
- `config/` — Provider/model/stage configuration + agent options
- `optimization/` — GEPA metrics and training utilities
- `support/` — Infrastructure (directories, permissions, HITL)
- `hooks/` — PreToolUse (bash safety), PostToolUse (linters)

## Conventions

- **Type hints**: Modern syntax (`str | None`, `dict[str, T]`)
- **Docstrings**: Google-style with Args/Returns/Raises
- **Functions**: Use `*,` for keyword-only args
- **Async**: Nested `async def` with sync wrapper via `run_until_complete()`
- **Logging**: Module-level `logger = logging.getLogger(__name__)`
- **Tests**: Class-based (`TestFeature`), `@pytest.mark.asyncio` for async

## Logs

Debug logs auto-saved to `.π/logs/` (7-day retention, gitignored).
