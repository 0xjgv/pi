# π

CLI tool orchestrating Claude agents for automated research → plan → implement workflows.

## Stack

- Python 3.13+ with uv
- claude-agent-sdk (>=0.1.7)
- pydantic for structured outputs
- ruff for linting/formatting

## Structure

```shell
π/                    # Main package
├── agent.py          # Agent configuration factory (ClaudeAgentOptions)
├── agent_comm.py     # Workflow orchestration, supervisor/SWE agent loops
├── hooks.py          # PreToolUse/PostToolUse validation hooks
├── schemas.py        # Pydantic models (StageOutput, SupervisorDecision)
└── utils.py          # Workflow ID generation, CSV logging, helpers
.claude/
├── agents/           # Sub-agent definitions (codebase-analyzer, etc.)
└── commands/         # Slash commands (1_research, 2_plan, 3_implement)
thoughts/shared/      # Generated research/ and plans/ artifacts
```

## Commands

- Format: `make format`
- Lint: `make check`
- Run: `π "your prompt"` or `uv run π "your prompt"`

## Key Patterns

- **Dual structured output**: SDK native first, JSON text parsing fallback (`agent_comm.py:112-155`)
- **Hook validation**: PostToolUse runs language-specific linters, PreToolUse blocks dangerous bash commands
- **Workflow stages**: research → plan → implement, each with question loops to supervisor agent
- **Documentation-first agents**: Research agents describe "what is", never critique or suggest

## References

- README.md (project README)
- IDEA.md (project IDEA)

## Claude Agent SDK Documentation

- <https://platform.claude.com/docs/en/agent-sdk/structured-outputs>
- <https://platform.claude.com/docs/en/agent-sdk/slash-commands>
- <https://platform.claude.com/docs/en/agent-sdk/todo-tracking>
- <https://platform.claude.com/docs/en/agent-sdk/custom-tools>
