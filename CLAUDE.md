# π

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → plan → review → iterate workflows.

## Stack

- Python 3.13+ with uv, hatchling
- claude-agent-sdk, dspy, click, rich
- pytest + pytest-asyncio, ruff

## Commands

- Run: `π "objective"`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov`

## Environment

- `CLIPROXY_API_BASE` — DSPy LM endpoint (default: localhost:8317)
- `CLIPROXY_API_KEY` — API key (required)

## Architecture

**Workflow**: 4-stage pipeline — Research → Plan → Review → Iterate

**Output paths**: `thoughts/shared/research/*.md`, `thoughts/shared/plans/*.md`

**Modules:**

- `cli.py` — Entry point, logging setup
- `config.py` — Provider/model/stage config, available tools
- `workflow/` — DSPy ReAct agents (`module.py`) + sync→async bridge (`bridge.py`)
- `support/` — Directory management, permissions, HITL providers
- `hooks/` — PreToolUse (bash safety), PostToolUse (ruff/eslint/cargo/go)

## Conventions

- **Type hints**: `str | None`, `dict[str, T]`
- **Docstrings**: Google-style
- **Functions**: `*,` for keyword-only args
- **Async**: Nested `async def` with `run_until_complete()` wrapper
- **Logging**: `logger = logging.getLogger(__name__)`
- **Tests**: Class-based `TestFeature`, `@pytest.mark.asyncio`

## Logs

`.π/logs/` (7-day retention), `~/.claude/hook-logs/` (30-day retention)
