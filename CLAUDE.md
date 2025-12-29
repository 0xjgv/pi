# π

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → plan → review → implement workflows.

## Stack

- Python 3.13+ with uv, hatchling build
- claude-agent-sdk, dspy, click, rich
- pytest + pytest-asyncio for testing
- ruff for lint/format

## Commands

- Run: `π "prompt"`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov`

## CLI Options

| Flag | Description |
|------|-------------|
| `-v/--version` | Show version |

## Environment

- `CLIPROXY_API_BASE` — DSPy LM endpoint (default: localhost:8317)
- `CLIPROXY_API_KEY` — API key (required)

## Architecture

**Workflow**: 5-stage pipeline — Clarify → Research → Plan → Review → Implement

**Module structure:**

- `cli.py` — Entry point
- `config.py` — Provider/model/stage configuration
- `workflow/` — Core workflow execution
  - `bridge.py` — Tool functions bridging sync→async to Claude SDK
  - `module.py` — DSPy module with 5 ReAct agents
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
