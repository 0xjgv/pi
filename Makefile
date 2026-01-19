# Silent helper (set VERBOSE=1 for full output)
SILENT_HELPER := source .claude/hack/run_silent.sh

.PHONY: help
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

##@ Setup

.PHONY: install
install: ## Install dependencies with uv
	@$(SILENT_HELPER) && \
		print_main_header "Installing Dependencies" && \
		run_silent "Sync dependencies" "uv sync"

##@ Code Quality

.PHONY: fix
fix: ## Fix lint errors with ruff
	@$(SILENT_HELPER) && run_silent "Fix lint errors" "uv run ruff check --fix ."

.PHONY: format
format: ## Format code with ruff
	@$(SILENT_HELPER) && run_silent "Format code" "uv run ruff format ."

.PHONY: lint
lint: ## Lint code with ruff
	@$(SILENT_HELPER) && run_silent "Lint check" "uv run ruff check ."

.PHONY: deadcode
deadcode: ## Scan for dead code with vulture
	@uv run vulture

.PHONY: quality-check
quality-check: ## Run quality checks (fix, format, lint)
	@$(SILENT_HELPER) && print_main_header "Running Quality Checks"
	@$(MAKE) fix
	@$(MAKE) format
	@$(MAKE) lint

##@ Maintenance

.PHONY: clean
clean: ## Remove cache and generated files
	@$(SILENT_HELPER) && \
		print_main_header "Cleaning Up" && \
		run_silent "Remove cache" "rm -rf .pytest_cache .mypy_cache .ruff_cache */__pycache__ */*/__pycache__ *.egg-info" && \
		run_silent "Ruff clean" "uv run ruff clean"

##@ Testing

.PHONY: test
test: ## Run tests with pytest
	@$(SILENT_HELPER) && print_main_header "Running Tests" && \
		run_silent "Running tests" "uv run pytest -x -v tests/"

.PHONY: test-cov
test-cov: ## Run tests with coverage (fails if <80%)
	@$(SILENT_HELPER) && run_silent "Running tests with coverage" "uv run pytest tests/ -v --cov=π --cov-report=term-missing --cov-fail-under=80"

.PHONY: test-no-api
test-no-api: ## Run tests without API access
	@$(SILENT_HELPER) && print_main_header "Running Tests (No API)" && \
		CLIPROXY_API_BASE="" CLIPROXY_API_KEY="" run_silent "Running tests" "uv run pytest -x -v tests/"

.PHONY: test-markers
test-markers: ## Run only tests marked as no_api
	@$(SILENT_HELPER) && run_silent "Running no_api marked tests" "uv run pytest -m no_api tests/ -v"

##@ Mutation Testing

.PHONY: mutate
mutate: ## Run mutation testing (uses pyproject.toml config)
	@echo "Running mutation testing (this may take several minutes)..."
	@uv run mutmut run
	@uv run mutmut results

.PHONY: mutate-browse
mutate-browse: ## Browse mutation testing results interactively
	@uv run mutmut browse

.PHONY: mutate-clean
mutate-clean: ## Clear mutation testing cache
	@rm -rf mutants/
	@echo "Mutation cache cleared"

##@ Development

.PHONY: check
check: quality-check test ## Run all checks

.PHONY: codespace
codespace: ## Set up codespace environment
	@$(SILENT_HELPER) && \
		print_main_header "Setting Up Codespace" && \
		run_silent "Install claude-code" "npm install -g @anthropic-ai/claude-code" && \
		run_silent "Upgrade pip" "python -m pip install --upgrade pip" && \
		run_silent "Install uv" "pip install uv" && \
		run_silent "Sync deps" "uv sync" && \
		run_silent "Add alias" "echo \"alias cldd='claude --dangerously-skip-permissions'\" >> ~/.bashrc" && \
		run_silent "Activate venv" "source .venv/bin/activate && source ~/.bashrc"

##@ Distribution

.PHONY: link
link: install ## Install and add π to PATH via symlink
	@mkdir -p ~/.local/bin
	@ln -sf "$(CURDIR)/.venv/bin/π" ~/.local/bin/π
	@echo "✓ Linked π to ~/.local/bin/π"
	@echo "  Ensure ~/.local/bin is in your PATH:"
	@echo "  export PATH=\"\$$HOME/.local/bin:\$$PATH\""

.PHONY: unlink
unlink: ## Remove π symlink
	@rm -f ~/.local/bin/π
	@echo "✓ Removed π from ~/.local/bin"
