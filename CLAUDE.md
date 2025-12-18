# π

CLI tool orchestrating Claude agents for automated research → plan → implement workflows.

## Stack

- Python 3.13+ with uv
- claude-agent-sdk (>=0.1.18)
- dspy (>=3.0.4) for ReAct agent orchestration
- ruff for linting/fixing/formatting
- rich for pretty console output

## Structure

```shell
π/                    # Main package
├── agent.py          # Agent configuration factory
├── cli.py            # CLI entry point + DSPy ReAct orchestration
├── hooks.py          # PreToolUse/PostToolUse validation hooks
└── utils.py          # Helpers, logging
.claude/
├── agents/           # Sub-agent definitions (codebase-analyzer, etc.)
└── commands/         # Slash commands (1_research → 4_commit)
thoughts/shared/      # Generated research and plan artifacts
```

## Development Commands

- Run: `π "your prompt"` or `uv run π "your prompt"`
- Format: `make format`
- Lint: `make lint`
- Test: `make test`
- Test with coverage: `make test-cov`
- Check: `make check` (fix, format, lint, test)

## Key Patterns

- **DSPy ReAct orchestration**: Automatic tool selection via DSPy's ReAct agent
- **Hook validation**: PostToolUse runs language-specific linters, PreToolUse blocks dangerous bash
- **Workflow stages**: research → plan → implement with slash command delegation
- **Documentation-first**: Research agents describe "what is", never critique

## References

- [README.md](README.md)
- [IDEA.md](IDEA.md)
