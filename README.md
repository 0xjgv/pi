# π

`π` (pi) v0.1.0 is a sophisticated Python CLI that provides intelligent codebase automation through a multi-stage workflow system. Built on the Claude Agent SDK, it enables complex development tasks through structured research, planning, validation, review, and iteration stages with built-in safety and code quality enforcement.

## Highlights

- **5-Stage Workflow System**: Research → Create Plan → Validate Plan → Review Plan → Iterate Plan
- **Intelligent Sub-agent Orchestration**: Spawns specialized agents for different tasks
- **Built-in Safety Hooks**: Prevents destructive commands and enforces code quality
- **Multi-language Support**: Python (ruff), TypeScript/JavaScript (ESLint), Rust (cargo check), Go (go vet)
- **Comprehensive Logging**: Workflow tracking with detailed logs and thoughts documentation
- **Streaming Responses**: Real-time output with statistics tracking
- **Zero Configuration**: Works out of the box with Anthropic credentials

## Architecture

### Core Components

- **CLI Interface** (`π/cli.py`): Entry point with async command handling
- **Workflow System** (`π/workflow.py`): 4-stage orchestration pipeline
- **Agent Management** (`π/agent.py`): Claude agent lifecycle and statistics
- **Safety Hooks** (`π/hooks.py`): Pre/post tool execution validation
- **Prompt System** (`π/prompts/`): Modular prompt templates
- **Utilities** (`π/utils.py`): Workflow management and logging

### Workflow Stages

1. **Research**: Comprehensive codebase analysis with parallel sub-agents
2. **Create Plan**: Implementation planning based on research findings
3. **Validate Plan**: Technical validation and feasibility assessment
4. **Review Plan**: Validation and quality assessment of the plan
5. **Iterate Plan**: Refinement and improvement of the plan

## Prerequisites

- Python 3.13+
- Anthropic API key in your environment
- [uv](https://github.com/astral-sh/uv) (recommended) for dependency management
- Git (for workflow tracking)

## Installation

### Quick Install (with uv)

```bash
git clone https://github.com/0xjgv/pi
mv pi π
cd π
uv sync
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### Manual Install (without uv)

```bash
git clone https://github.com/0xjgv/pi
mv pi π
cd π
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

## Usage

### Basic Usage

```bash
π "Add user authentication to the app"
π "Refactor the payment processing module"
π "Create tests for the API endpoints"
```

### With uv (recommended)

```bash
uv run π "Implement dark mode toggle"
```

### What Happens During Execution

1. **Workflow Initialization**: Generates unique workflow ID and directories
2. **Research Stage**: Analyzes codebase structure and relevant components
3. **Planning Stage**: Creates detailed implementation plan
4. **Validation Stage**: Technical validation and feasibility assessment
5. **Review Stage**: Validates plan completeness and correctness
6. **Iteration Stage**: Refines plan based on review feedback
7. **Results**: Outputs final plan with statistics and file references

## Safety Features

### Command Protection
- Blocks destructive bash commands (`rm`, `rm -rf` patterns)
- Pre-execution validation for shell commands
- Configurable safety patterns

### Code Quality Enforcement
- Automatic linting on file modifications:
  - **Python**: ruff format and check
  - **TypeScript/JavaScript**: ESLint
  - **Rust**: cargo check
  - **Go**: go vet
- Blocks operations that fail quality checks
- Language-specific project detection

### Permission Management
- `permission_mode="acceptEdits"` for rapid iteration
- Configurable hook system for custom validation
- Detailed logging of all operations

## Configuration

### Environment Variables
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Workflow Customization
- Prompt templates in `π/prompts/` can be customized
- Hook patterns in `π/hooks.py` can be modified
- Workflow stages can be enabled/disabled in `π/workflow.py`

### Model Configuration
Each workflow stage can use different Claude models:
- Research stage: `opus` (default)
- Planning stage: configurable per prompt
- Review/Iteration stages: configurable per prompt

## Development

### Development Workflow

```bash
# Install dependencies
make install

# Format code
make format

# Run linting and checks
make check

# Auto-fix linting issues
make fix

# Clean build artifacts and caches
make clean

# Setup development environment (GitHub Codespaces)
make codespace
```

### Project Structure
```
π/
├── cli.py              # CLI entry point
├── workflow.py         # 4-stage workflow orchestration
├── agent.py           # Agent management and statistics
├── agent_comm.py      # Agent communication utilities
├── hooks.py           # Safety and quality hooks
├── utils.py           # Core utilities and helpers
└── prompts/           # Modular prompt templates
    ├── research_codebase.py
    ├── create_plan.py
    ├── review_plan.py
    ├── iterate_plan.py
    └── ...
```

### Adding Custom Prompts

1. Create new prompt module in `π/prompts/`
2. Export `prompt` (template string) and optional `model`
3. Use template variables: `{workflow_id}`, `{user_query}`, etc.
4. Import and use in workflow via `load_prompt()`

### Extending Hooks

Modify `π/hooks.py` to add:
- New command patterns to block
- Additional language linters
- Custom validation logic
- Project-specific safety rules

## Workflow Artifacts

### Directory Structure
```
project/
├── thoughts/           # Research documentation
│   └── {workflow_id}/
│       └── research-*.md
└── .logs/             # Execution logs
    └── {workflow_id}/
        ├── research.log
        ├── plan.log
        ├── review.log
        └── iterate.log
```

### Research Documents
Comprehensive markdown documents with:
- YAML frontmatter with metadata
- Codebase analysis and documentation
- File references with line numbers
- Architecture documentation
- Historical context

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure Anthropic API key is set
2. **Module Not Found**: Check Python 3.13+ requirement
3. **Hook Failures**: Verify language tools are installed
4. **Workflow Stuck**: Check logs in `.logs/{workflow_id}/`

### Debug Mode
Enable verbose logging by modifying workflow.py:
```python
result = await run_agent(
    verbose=True,  # Show detailed agent messages
    # ... other parameters
)
```

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]

### Development Guidelines
- Follow Python 3.13+ syntax and features
- Use ruff for code formatting and linting
- Add tests for new functionality
- Update documentation for API changes
- Ensure hooks cover new safety concerns
