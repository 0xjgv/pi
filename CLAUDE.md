# π

CLI tool orchestrating Claude agents via DSPy ReAct for research → plan → implement workflows.

## Stack

- Python 3.13+ with uv
- claude-agent-sdk, dspy, click, rich
- ruff for linting/formatting

## Structure

```markdown
π/                    # Main package
├── cli.py            # CLI entry + DSPy ReAct orchestration
├── agent.py          # Agent configuration factory
├── session.py        # Workflow state management
├── hooks/            # Pre/PostToolUse validation
└── utils.py          # Helpers, logging
.claude/
├── agents/           # Sub-agent definitions
└── commands/         # Slash commands (1-4)
```

## Commands

- Run: `π "prompt"` or `π "prompt" -t high -v`
- Quality: `make check` (fix, format, lint, test) — see [Makefile](Makefile)

## CLI Options

- `-t/--thinking`: Model tier (low=haiku, med=sonnet, high=opus)
- `-v/--verbose`: Debug logging

## Environment

- `CLIPROXY_API_BASE` — DSPy LM endpoint (default: localhost:8317)
- `CLIPROXY_API_KEY` — API key for DSPy

## Key Patterns

- **DSPy ReAct**: Automatic tool selection via `research_codebase`, `create_plan`, `implement_plan`
- **Session resumption**: WorkflowSession tracks session IDs across tool calls
- **Hook validation**: Safety checks on bash, linters on file writes

## References

- [README.md](README.md)
