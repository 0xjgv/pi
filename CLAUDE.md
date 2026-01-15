# π

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → design → execute workflows.

## Stack (pyproject.toml)

- Python 3.13+ with uv, hatchling
- claude-agent-sdk, dspy, rich
- pytest + pytest-asyncio, ruff

## Commands

- Run: `π "objective"`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov` — aim for 80% coverage
- Mutate: `make mutate` (all paths) or `make mutate-browse` (interactive)
- Link: `make link` — symlink π to ~/.local/bin

## Environment

- `PI_LM_DEBUG` — Enable verbose LM logging: raw prompts, completions, tokens (default: off)

## Architecture

**Workflow**: 3-stage pipeline — Research → Design → Execute (with early exit)

**Output paths**: `thoughts/shared/research/*.md`, `thoughts/shared/plans/*.md`

**Modules:**

- `core/` — Leaf layer: enums, models, errors (no internal deps)
- `cli/` — Entry point, logging setup
- `config.py` — Stage/tool config, re-exports from core
- `workflow/` — DSPy ReAct agents, sync→async bridge
- `support/` — Directory management, permissions, AITL (autonomous question answering)
- `hooks/` — PreToolUse (bash safety), PostToolUse (linting)
- `doc_sync/` — Documentation synchronization utility

**AITL**: Agent-in-the-loop — workflow agents ask questions answered autonomously by a codebase-aware agent (Read/Glob/Grep tools). No human intervention required.

## Conventions

- **Type hints**: `str | None`, `dict[str, T]` (see `tool.ruff` in pyproject.toml)
- **Docstrings**: Google-style
- **Functions**: `*,` for keyword-only args
- **Async**: Nested `async def` with `get_event_loop().run_until_complete()` wrapper
- **Logging**: `logger = logging.getLogger(__name__)`
- **Tests**: Class-based `TestFeature`, `@pytest.mark.asyncio`

## Logs

`.π/logs/` (7-day retention), `~/.claude/hook-logs/` (30-day retention)
