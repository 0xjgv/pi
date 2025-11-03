.PHONY: install format lint test clean check all help codespace
SHELL := /bin/bash

# Default target
all: format lint test

help:
	@echo "Available targets:"
	@echo "  make install   - Install deps with uv"
	@echo "  make format    - Format code with ruff"
	@echo "  make lint      - Lint code with ruff"
	@echo "  make test      - Run tests with pytest"
	@echo "  make check     - Run lint and test (without formatting)"
	@echo "  make clean     - Remove cache and generated files"
	@echo "  make all       - Run format, lint, and test"

install:
	@echo "Installing deps..."
	uv sync

format:
	@echo "Formatting code with ruff..."
	uv run ruff format .

lint:
	@echo "Linting code with ruff..."
	uv run ruff check .

fix:
	@echo "Fixing lint errors with ruff..."
	uv run ruff check --fix .

test:
	@echo "Running tests with pytest..."
	uv run pytest tests/ -v

check: lint test

clean:
	@echo "Cleaning up cache and generated files..."
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@uv run ruff clean
	@echo "Clean complete!"

activate:
	@echo "Activating virtual environment..."
	source .venv/bin/activate

codespace:
	@echo "Setting up codespace..."
	npm install -g @anthropic-ai/claude-code
	python -m pip install --upgrade pip
	pip install uv
	uv sync

	echo "alias cldd='claude --dangerously-skip-permissions'" >> ~/.bashrc
	source .venv/bin/activate
	source ~/.bashrc