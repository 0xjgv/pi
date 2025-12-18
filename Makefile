# Silent helper (set VERBOSE=1 for full output)
SILENT_HELPER := source ~/.claude/hack/run_silent.sh

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

##@ Development

.PHONY: check
check: quality-check ## Run all checks

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
