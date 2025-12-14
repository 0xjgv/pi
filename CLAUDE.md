# π

CLI tool orchestrating Claude agents for automated research → plan → implement workflows.

## Stack

- Python 3.13+ with uv
- claude-agent-sdk (>=0.1.13)
- pydantic for structured outputs
- ruff for linting/formatting

## Structure

```shell
π/                    # Main package
├── agent.py          # Agent configuration factory
├── agent_comm.py     # Workflow orchestration, supervisor/SWE loops
├── agents.py         # Agent definitions
├── hooks.py          # PreToolUse/PostToolUse validation hooks
├── idea_workflow.py  # Idea-based workflow implementation
├── schemas.py        # Pydantic models
├── types.py          # Type definitions
└── utils.py          # Helpers, logging
.claude/
├── agents/           # Sub-agent definitions (codebase-analyzer, etc.)
└── commands/         # Slash commands (1_research → 4_commit)
thoughts/shared/      # Generated research and plan artifacts
```

## Commands

- Format: `make format`
- Lint: `make check`
- Run: `π "your prompt"` or `uv run π "your prompt"`

## Key Patterns

- **Dual structured output**: SDK native first, JSON text parsing fallback
- **Hook validation**: PostToolUse runs language-specific linters, PreToolUse blocks dangerous bash
- **Workflow stages**: research → plan → implement with supervisor question loops
- **Documentation-first**: Research agents describe "what is", never critique

## References

- [README.md](README.md)
- [IDEA.md](IDEA.md)
