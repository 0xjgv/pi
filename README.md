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
- `make check` – lint plus tests
- `make clean` – drop build artifacts and caches

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]
