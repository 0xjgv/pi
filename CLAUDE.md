# π

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → plan → review → iterate workflows.

## Stack (pyproject.toml)

- Python 3.13+ with uv, hatchling
- claude-agent-sdk, dspy, click, rich
- pytest + pytest-asyncio, ruff

## Commands

- Run: `π "objective"`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov` — aim for 80% coverage

## Environment

- `CLIPROXY_API_BASE` — DSPy LM endpoint (default: localhost:8317)
- `CLIPROXY_API_KEY` — API key (required)

## Architecture

**Workflow**: 4-stage pipeline — Research → Plan → Review → Iterate

**Output paths**: `thoughts/shared/research/*.md`, `thoughts/shared/plans/*.md`

**Modules:**

- `core/` — Leaf layer: enums, models, errors (no internal deps)
- `cli/` — Entry point, logging, CLI utilities
- `config.py` — Stage/tool config, re-exports from core
- `workflow/` — DSPy ReAct agents + sync→async bridge
- `support/` — Directory management, permissions, HITL
- `hooks/` — PreToolUse (bash safety), PostToolUse (linting)

## Conventions

- **Type hints**: `str | None`, `dict[str, T]` (Read the `tool.ruff` section of the `pyproject.toml` file for more details)
- **Docstrings**: Google-style
- **Functions**: `*,` for keyword-only args
- **Async**: Nested `async def` with `run_until_complete()` wrapper
- **Logging**: `logger = logging.getLogger(__name__)`
- **Tests**: Class-based `TestFeature`, `@pytest.mark.asyncio`

## Logs

`.π/logs/` (7-day retention), `~/.claude/hook-logs/` (30-day retention)
