# π

`π` is a tiny Python CLI that lets you talk to Claude from your terminal without fuss. It wraps the official Claude Agent SDK, keeps the current working directory in context, and streams replies as they arrive.

## Highlights

- One-shot prompts with streamed, async responses
- Automatic acceptance of file edits for faster iteration
- Full access to the Claude Agent SDK tooling (files, shell commands, reasoning)
- Zero config beyond your Anthropic credentials

## Prerequisites

- Python 3.13+
- Anthropic API key in your environment
- [uv](https://github.com/astral-sh/uv) (optional) if you prefer ultra-fast dependency management

## Install

```bash
git clone https://github.com/0xjgv/pi
mv pi π
cd π
uv sync         # or: make install
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

Prefer manual setup without uv?

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

## Run

```bash
π "Summarize the project files" # or: uv run π "Summarize the project files"
```

Claude receives the prompt, works within the current directory, and streams output back to the terminal.

## Configuration

- `permission_mode="acceptEdits"` — auto-applies file changes suggested by Claude
- `stream=True` — prints tokens as they arrive
- Working directory is whatever path you launch the CLI from

## Development

Common tasks are bundled into the `Makefile`:

- `make install` – install pyproject deps
- `make format` – format with Ruff
- `make test` – run tests with pytest
- `make check` – lint plus tests
- `make clean` – drop build artifacts and caches

## Architecture

### Workflow System

The π CLI uses a multi-stage workflow system where each stage runs as an external Python process:

1. **Research** - Analyzes the codebase to understand context
2. **Plan** - Creates detailed implementation plans
3. **Review** - Validates plans for completeness
4. **Iterate** - Refines plans based on feedback
5. **Implement** - Executes the plan
6. **Commit** - Creates git commits
7. **Validate** - Verifies implementation success

#### Stage Communication

Stages communicate via JSON protocol:
- **Input**: CLI arguments (workflow_id, user_query, paths, previous results)
- **Output**: JSON on stdout with status, result, document path, and stats
- **Logging**: Progress info on stderr

#### Benefits

- **Isolation**: Each stage runs in a clean process
- **Debugging**: Stages can be tested independently
- **Recovery**: Failed stages can be retried
- **Clarity**: Clear data contracts between stages

See `π/stages/` for stage implementations.

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]
