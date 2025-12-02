# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync              # Install dependencies
make format          # Format with ruff
make check           # Lint with ruff
make fix             # Auto-fix lint errors
make clean           # Remove caches

π "<prompt>"         # Run CLI with a prompt
```

## Architecture

π is a Python CLI wrapper around the Claude Agent SDK for multi-agent workflows.

### Core Components

- **`cli.py`** - Entry point (`π` command), runs the workflow
- **`workflow.py`** - Orchestrates staged workflow: research → plan → review → iterate
- **`agent.py`** - Single-agent runner with message handling and stats tracking
- **`agent_comm.py`** - Multi-agent communication via async queues (`AgentQueue`, `QueueMessage`)
- **`hooks.py`** - Pre/post tool hooks for bash command blocking and language-specific linting
- **`utils.py`** - Workflow ID generation, logging, CSV escaping

### Multi-Agent Queue System

Agents communicate through `asyncio.Queue`-based message passing:

```markdown
AgentQueue("software_engineer") ←→ AgentQueue("tech_lead")
     ↑                                    ↓
     └────── QueueMessage (from, text) ───┘
```

Each agent has an inbox and outbox(es). Messages flow bidirectionally until terminated with `None`.

### Hooks

- **PreToolUse**: `check_bash_command` blocks `rm` patterns
- **PostToolUse**: `check_file_format` runs ruff/eslint/cargo/go vet on edits

## Guidelines

Follow the Zen of Python. Explicit over implicit. Simple over complex. Readability counts.
