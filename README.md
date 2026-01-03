# π

CLI tool orchestrating Claude agents via DSPy ReAct for autonomous research → plan → review → iterate workflows.

## Highlights

- **DSPy ReAct orchestration** — automatic tool selection and multi-step reasoning
- **Full Claude Agent SDK tooling** — files, shell commands, web search, task management
- **Four-stage pipeline** — research → plan → review → iterate with per-stage models
- **Human-in-the-loop** — `ask_human` tool for clarification during workflows
- **Safety hooks** — blocks dangerous commands, runs linters on file changes
- **Sub-agent system** — parallel specialized agents for codebase exploration

## Workflow

```
User Objective
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 1: Research (/1_research_codebase)        │
│ • Spawns codebase-locator, analyzer agents      │
│ • May ask for clarification via ask_human       │
│ • Outputs: thoughts/shared/research/*.md        │
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 2: Plan (/2_create_plan)                  │
│ • Creates implementation plan based on research │
│ • May ask for clarification via ask_human       │
│ • Outputs: thoughts/shared/plans/*.md           │
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 3: Review (/3_review_plan)                │
│ • Reviews plan for completeness and accuracy    │
│ • Identifies gaps, inconsistencies, improvements│
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 4: Iterate (/4_iterate_plan)              │
│ • Incorporates review feedback into plan        │
│ • Outputs: Updated plan document                │
└─────────────────────────────────────────────────┘
```

Each stage uses a dedicated DSPy ReAct agent with configurable model tier.

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Claude Code installed ([claude.ai/code](https://claude.ai/code))

## Install

```bash
git clone https://github.com/0xjgv/pi π
cd π
make link                      # Installs deps + links π to ~/.local/bin
```

Ensure `~/.local/bin` is in your PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

<details>
<summary>Alternative: Activate venv manually</summary>

```bash
git clone https://github.com/0xjgv/pi π
cd π
uv sync                        # or: make install
source .venv/bin/activate      # Now π is available
```

</details>

<details>
<summary>Uninstall</summary>

```bash
make unlink                    # Removes symlink from ~/.local/bin
```

</details>

## Run

```bash
π "Summarize the project files"
π "Create a plan for user authentication"

# Or pipe from stdin
echo "Analyze the test coverage" | π
```

## CLI Options

| Flag | Description |
|------|-------------|
| `-v, --version` | Show version |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLIPROXY_API_BASE` | `http://localhost:8317` | DSPy LM endpoint |
| `CLIPROXY_API_KEY` | — | API authentication key |

## Project Structure

```
π/                              # Main package
├── cli.py                      # CLI entry point
├── config.py                   # Provider/model/stage configuration
├── errors.py                   # Package-wide exceptions
├── utils.py                    # Core utilities
├── workflow/                   # Core workflow execution
│   ├── bridge.py               # Sync-async bridge
│   └── module.py               # DSPy workflow module
├── support/                    # Supporting infrastructure
│   ├── directory.py            # Log management
│   ├── permissions.py          # Tool permissions
│   └── hitl.py                 # Human-in-the-loop
└── hooks/                      # Pre/PostToolUse validation
    ├── safety.py               # Dangerous command blocking
    ├── checkers.py             # Language-specific linters
    └── registry.py             # Checker registration

.claude/
├── agents/                     # Sub-agent definitions
└── commands/                   # Slash commands (stages 1-4)
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
