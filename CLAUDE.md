# π

CLI orchestrating Claude agents via SDK tools for autonomous research → design → execute workflows.

## Stack (pyproject.toml)

- Python 3.13+ with uv, hatchling
- claude-agent-sdk, pydantic, python-dotenv, rich
- pytest + pytest-asyncio, ruff, vulture, mutmut

## Commands

- Run: `π "objective"` or `π --verbose "objective"`
- Quality: `make check` (fix → format → lint → test)
- Test: `make test` or `make test-cov` — 80% coverage required
- No-API: `make test-no-api` or `make test-markers` (no_api, slow)
- Mutate: `make mutate` or `make mutate-browse`
- Setup: `make install`, `make link` / `make unlink`

## Environment

- `PI_LM_DEBUG` — Verbose LM logging (set by `--verbose` flag)

## Architecture

**Workflow**: 3-stage pipeline — Research → Design → Execute (with early exit)

**Output**: `thoughts/shared/research/*.md`, `thoughts/shared/plans/*.md`

**Model Tiers**: Tier.LOW → haiku, Tier.MED → sonnet, Tier.HIGH → opus

**Modules:**

- `core/` — Leaf layer: enums, models, errors, constants (no internal deps)
- `cli/` — Entry point, live display, logging setup
- `config.py` — Agent options, command mapping, logging configuration
- `bridge/` — Claude SDK async session integration
- `hooks/` — PreToolUse (bash safety), PostToolUse (linting)
- `tools.py` — MCP workflow tools
- `context.py` — Workflow context management
- `observer.py` — Event observers for stage agents
- `models.py`, `state.py` — Workflow models and state
- `doc_sync/` — Documentation synchronization utility
- Root: `console.py`, `utils.py` — shared utilities (project root detection, system helpers)

## Conventions

- **Type hints**: `str | None`, `dict[str, T]` (PEP 604, built-in generics)
- **Docstrings**: Google-style
- **Functions**: `*,` for keyword-only args
- **Async**: `async def` with `asyncio.run()` wrapper
- **Logging**: `logger = logging.getLogger(__name__)`
- **Tests**: Class-based `TestFeature`, `@pytest.mark.asyncio`

## Logs

`.π/logs/` (7-day retention), `~/.claude/hook-logs/` (30-day retention)
