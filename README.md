# π

[![Build](https://github.com/0xjgv/pi/actions/workflows/test.yml/badge.svg)](https://github.com/0xjgv/pi/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/0xjgv/pi/branch/main/graph/badge.svg)](https://codecov.io/gh/0xjgv/pi)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

CLI orchestrating Claude agents via DSPy ReAct for autonomous research → design → execute workflows.

## Highlights

- **DSPy ReAct orchestration** — automatic tool selection and multi-step reasoning
- **Full Claude Agent SDK tooling** — files, shell commands, web search, task management
- **Three-stage pipeline** — Research → Design → Execute with early exit capability
- **Agent-in-the-loop (AITL)** — autonomous question answering via codebase-aware agent
- **Safety hooks** — blocks dangerous commands, runs linters on file changes
- **Sub-agent system** — parallel specialized agents for codebase exploration

## Workflow

```markdown
User Objective
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 1: Research                               │
│ • Spawns codebase-locator, analyzer agents      │
│ • Autonomous question answering via AITL        │
│ • Early exit if no implementation needed        │
│ • Output: thoughts/shared/research/*.md         │
└─────────────────────────────────────────────────┘
     ↓ (if implementation needed)
┌─────────────────────────────────────────────────┐
│ Stage 2: Design                                 │
│ • Creates implementation plan from research     │
│ • Reviews and iterates on plan                  │
│ • Output: thoughts/shared/plans/*.md            │
└─────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────┐
│ Stage 3: Execute                                │
│ • Implements plan with full SDK tooling         │
│ • Commits changes automatically                 │
│ • Output: Modified files, git commit            │
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
| `CLIPROXY_API_KEY` | — | API authentication key (required) |

## Project Structure

```markdown
π/                              # Main package
├── cli/
│   └── main.py                 # CLI entry point
├── config.py                   # Agent options, available tools
├── console.py                  # Rich console singleton
├── state.py                    # Spinner state management
├── utils.py                    # Utilities (logging, speech, sleep prevention)
├── core/                       # Leaf layer (no internal deps)
│   ├── enums.py                # Provider, Stage, Tier
│   ├── errors.py               # Package exceptions
│   └── models.py               # LM factory, tier mappings
├── workflow/                   # Core workflow execution
│   ├── orchestrator.py         # StagedWorkflow (3-stage pipeline)
│   ├── staged.py               # Stage functions (research, design, execute)
│   ├── module.py               # DSPy signatures
│   ├── tools.py                # Workflow tools (research, plan, implement)
│   ├── bridge.py               # Sync-async bridge to Claude SDK
│   ├── context.py              # Execution context (session, paths)
│   ├── callbacks.py            # ReAct logging callback
│   └── types.py                # Type validation (doc paths, results)
├── support/                    # Supporting infrastructure
│   ├── aitl.py                 # Agent-in-the-loop question answering
│   ├── directory.py            # Log/document management
│   └── permissions.py          # Tool permissions callback
├── hooks/                      # Pre/PostToolUse validation
│   ├── safety.py               # Dangerous command blocking
│   ├── linting.py              # Post-write linting hook
│   ├── checkers.py             # Language-specific linters
│   ├── registry.py             # Checker registration
│   └── utils.py                # Hook utilities
└── doc_sync/                   # Documentation synchronization
    └── core.py                 # CLAUDE.md sync utility

.claude/
├── agents/                     # Sub-agent definitions
└── commands/                   # Slash commands (stages 1-6)
```

## Sub-Agents

Specialized agents spawned in parallel for codebase exploration:

| Agent | Purpose |
|-------|---------|
| `codebase-locator` | Finds WHERE code lives (file paths) |
| `codebase-analyzer` | Analyzes HOW code works (implementation details) |
| `codebase-pattern-finder` | Finds similar patterns and usage examples |
| `codebase-simplifier` | Simplifies and refines code for clarity |
| `thoughts-analyzer` | Extracts insights from research documents |
| `thoughts-locator` | Discovers relevant documents in thoughts/ |
| `web-search-researcher` | External web research |

## Slash Commands

| Command | Purpose |
|---------|---------|
| `/1_research_codebase` | Research codebase patterns and architecture |
| `/2_create_plan` | Create implementation plan from research |
| `/3_review_plan` | Review plan for completeness |
| `/4_implement_plan` | Execute implementation from plan |
| `/5_commit` | Create git commit with changes |
| `/write-claude-md` | Create or update CLAUDE.md |

## Safety & Quality Hooks

**Pre-execution safety** — Blocks dangerous bash commands:

- Destructive operations (`rm -rf /`, `rm -rf ~`)
- Pipe-to-shell attacks (`curl ... | bash`)
- Disk operations (`dd`, `mkfs`, `fdisk`)
- Fork bombs and system file corruption

**Post-write linting** — Automatic checks after file modifications:

| Language | Checker |
|----------|---------|
| Python | `ruff check --fix` |
| TypeScript/JavaScript | `eslint` |
| Rust | `cargo check` |
| Go | `golangci-lint` / `go vet` |

## Configuration

- `permission_mode="acceptEdits"` — auto-applies file changes
- `stream=True` — prints tokens as they arrive
- Working directory is wherever you launch the CLI
- Logs stored in `.π/logs/` (7-day retention)
- Research/plan documents archived after 5 days

## Development

```bash
make install        # Install dependencies with uv
make check          # Run all checks (fix, format, lint, test)
make test           # Run tests with pytest
make test-cov       # Tests with coverage report (fails if <80%)
make quality-check  # Fix + format + lint only
make mutate         # Run mutation testing
make clean          # Remove caches and build artifacts
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
