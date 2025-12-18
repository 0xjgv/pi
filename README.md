# π

Research, Plan, & Implement, CLI tool.

## Highlights

- Full access to the Claude Agent SDK tooling (files, shell commands, reasoning)
- Automatic acceptance of file edits for faster iteration
- Zero config beyond your Anthropic credentials

## Workflow

*software engineer (swe) agent*
*tech lead (tl) agent*

- start: user provides a task description or question (the objective of the workflow)
- *swe* agent runs the `/1_research_codebase` command with the objective of the workflow
-- alt *swe* agent has questions (loop until *swe* agent has no questions)
    -- *tl* agent answers them
- *swe* agent runs the `/2_create_plan` command with path to the research document
-- alt *swe* agent has questions (loop until *swe* agent has no questions)
    -- *tl* agent answers them
- *swe* agent runs the `/3_implement_plan` command with path to the plan document
-- alt *swe* agent has questions (loop until *swe* agent has no questions)
    -- *tl* agent answers them
- done

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Claude Code installed (claude.ai/code)

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
- `make check` – lint plus tests
- `make clean` – drop build artifacts and caches

## License

<!-- TODO: Add your license here -->

## Contributing

<!-- TODO: Add contributing guidelines here -->
