# π

CLI tool orchestrating Claude agents via DSPy ReAct for autonomous research → plan → implement workflows.

## Highlights

- **DSPy ReAct orchestration** — automatic tool selection and multi-step reasoning
- **Full Claude Agent SDK tooling** — files, shell commands, web search, task management
- **Three-phase workflow** — structured research → planning → implementation
- **Safety hooks** — blocks dangerous commands, runs linters on file changes
- **Sub-agent system** — parallel specialized agents for codebase exploration

## Workflow

```
User Objective
     ↓
┌─────────────────────────────────────────────────┐
│ Phase 1: Research (/1_research_codebase)        │
│ • Spawns codebase-locator, analyzer agents      │
│ • Outputs: thoughts/shared/research/*.md        │
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Phase 2: Plan (/2_create_plan)                  │
│ • Creates implementation plan with phases       │
│ • Outputs: thoughts/shared/plans/*.md           │
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Phase 3: Implement (/3_implement_plan)          │
│ • Executes plan with safety hooks               │
│ • Pauses for manual verification per phase      │
└─────────────────────────────────────────────────┘
```

The DSPy ReAct agent automatically selects between `research_codebase`, `create_plan`, and `implement_plan` tools based on the objective.

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Claude Code installed ([claude.ai/code](https://claude.ai/code))

## Install

```bash
git clone https://github.com/0xjgv/pi
mv pi π
cd π
uv sync                        # or: make install
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

<details>
<summary>Manual setup without uv</summary>

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
```

</details>

## Run

```bash
π "Summarize the project files"
π "Implement user authentication" -t high      # Use Opus for complex tasks
π "Fix the typo in utils.py" -t low -v         # Use Haiku with debug output
```

## CLI Options

| Flag | Description |
|------|-------------|
| `-t, --thinking` | Model tier: `low` (haiku), `med` (sonnet), `high` (opus) |
| `-v, --verbose` | Enable debug logging |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLIPROXY_API_BASE` | `http://localhost:8317` | DSPy LM endpoint |
| `CLIPROXY_API_KEY` | — | API authentication key |

## Project Structure

```
π/                    # Main package
├── cli.py            # CLI entry + DSPy ReAct orchestration
├── agent.py          # Agent configuration factory
├── session.py        # Workflow state management
├── hooks/            # Pre/PostToolUse validation
│   ├── safety.py     # Dangerous command blocking
│   ├── checkers.py   # Language-specific linters
│   └── registry.py   # Checker registration
└── utils.py          # Logging helpers

.claude/
├── agents/           # Sub-agent definitions
└── commands/         # Slash commands (phases 1-4)
```

## Sub-Agents

Specialized agents spawned in parallel for codebase exploration:

| Agent | Purpose |
|-------|---------|
| `codebase-locator` | Finds WHERE code lives (file paths) |
| `codebase-analyzer` | Analyzes HOW code works (implementation details) |
| `codebase-pattern-finder` | Finds similar patterns and usage examples |
| `thoughts-analyzer` | Extracts insights from research documents |
| `web-search-researcher` | External web research |

## Safety & Quality Hooks

**Pre-execution safety** — Blocks dangerous bash commands:
- Destructive operations (`rm -rf /`, `rm -rf ~`)
- Pipe-to-shell attacks (`curl ... | bash`)
- Disk operations (`dd`, `mkfs`, `fdisk`)
- Fork bombs and system file corruption

**Post-write linting** — Automatic checks after file modifications:

| Language | Checker |
|----------|---------|
| Python | `ruff check` |
| TypeScript/JavaScript | `eslint` |
| Rust | `cargo check` |
| Go | `golangci-lint` / `go vet` |

## Configuration

- `permission_mode="acceptEdits"` — auto-applies file changes
- `stream=True` — prints tokens as they arrive
- Working directory is wherever you launch the CLI

## Development

```bash
make install        # Install dependencies with uv
make check          # Run all checks (fix, format, lint, test)
make test           # Run tests with pytest
make test-cov       # Tests with coverage report
make quality-check  # Fix + format + lint only
make clean          # Remove caches and build artifacts
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
