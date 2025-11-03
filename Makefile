.PHONY: help install format check clean codespace
SHELL := /bin/bash

help:
	@echo "Available targets:"
	@echo "  make install   - Install deps with uv"
	@echo "  make format    - Format code with ruff"
	@echo "  make check     - Run lint and test (without formatting)"
	@echo "  make clean     - Remove cache and generated files"

install:
	@echo "Installing deps..."
	uv sync

format:
	@echo "Formatting code with ruff..."
	uv run ruff format .

check:
	@echo "Linting code with ruff..."
	uv run ruff check .

fix:
	@echo "Fixing lint errors with ruff..."
	uv run ruff check --fix .

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

codespace:
	@echo "Setting up codespace..."
	npm install -g @anthropic-ai/claude-code
	python -m pip install --upgrade pip
	pip install uv
	uv sync

	echo "alias cldd='claude --dangerously-skip-permissions'" >> ~/.bashrc
	source .venv/bin/activate
	source ~/.bashrc