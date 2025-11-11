# Workflow Agent Delegation via Bash Tool Implementation Plan

## Overview

Refactor the workflow orchestration system to execute each stage (research, plan, review, iterate, implement, commit, validate) as external Python scripts invoked via subprocess. This change moves from in-process async agent calls to external process delegation, enabling better isolation, debugging, and failure recovery.

## Current State Analysis

### Existing Implementation

**Current architecture** (`π/workflow.py:35-176`):
- `run_workflow()` executes 4 stages sequentially using in-process `run_agent()` calls
- Active stages: research, plan, review, iterate
- Commented-out stages: implement, commit, validate
- Each stage uses `ClaudeAgentOptions` with hooks for Bash/Edit/Write validation
- Results passed directly between stages via Python variables
- Statistics tracked via `AgentStats` class

**Stage execution pattern** (`π/workflow.py:62-73`):
```python
research_codebase_result, research_stats = await run_agent(
    options=_get_options(cwd=cwd, model=research_model),
    log_file=workflow_log_dir / "research.log",
    prompt=f"{research_prompt}",
    verbose=False,
)
```

**Existing subprocess patterns** (`π/hooks.py:93-210`):
- Uses `subprocess.run()` for external tool invocation (ruff, eslint, cargo, go vet)
- Consistent error handling: check `returncode`, capture `stdout`/`stderr`
- Working directory control via `cwd` parameter

### Key Discoveries:
- Workflow uses `load_prompt()` to dynamically import prompts from `π/prompts/` (`π/utils.py:8-47`)
- Each prompt defines template variables and optional model override
- Results located via `find_file_starting_with()` utility (`π/utils.py:74-112`)
- No existing test infrastructure - tests need to be created from scratch
- 7 total stages to implement: research, plan, review, iterate, implement, commit, validate

## Desired End State

### Target Architecture

**Refactored workflow** - External process delegation:
```
run_workflow()
  ├─> subprocess.run(["python", "π/stages/research.py", ...])
  ├─> subprocess.run(["python", "π/stages/plan.py", ...])
  ├─> subprocess.run(["python", "π/stages/review.py", ...])
  ├─> subprocess.run(["python", "π/stages/iterate.py", ...])
  ├─> subprocess.run(["python", "π/stages/implement.py", ...])
  ├─> subprocess.run(["python", "π/stages/commit.py", ...])
  └─> subprocess.run(["python", "π/stages/validate.py", ...])
```

**Data contract** - JSON communication protocol:
```json
{
  "status": "success|error",
  "result": "last message from agent",
  "document": "path/to/generated/document.md",
  "stats": {
    "total_tools": 42,
    "errors": 0,
    "tool_counts": {"Read": 15, "Grep": 10, "Task": 8}
  },
  "error": "error message if status=error"
}
```

### Verification Criteria:
- All 7 workflow stages execute as external processes
- JSON protocol enables structured data passing between stages
- Retry logic handles transient failures
- Integration test validates full workflow end-to-end
- `make test` runs all tests successfully

## What We're NOT Doing

- Not modifying the prompt files in `π/prompts/` (they stay as-is)
- Not changing hooks.py behavior or tool validation logic
- Not adding parallel execution (stages remain sequential)
- Not implementing rollback/compensation logic beyond retry
- Not adding stage result caching or resumption from arbitrary points
- Not creating a UI or dashboard for workflow monitoring

## Implementation Approach

**Strategy**: Incremental refactoring with backward compatibility during development. Each phase builds on the previous, maintaining a working system throughout. Testing infrastructure established early to validate changes.

**Key design decisions**:
1. **JSON for inter-stage communication**: Robust, structured, easily debuggable
2. **CLI arguments for context**: workflow_id, user_query, paths passed as argv
3. **Retry once with logging**: Simple error recovery without complexity
4. **Sequential execution**: Simpler reasoning, matches current behavior
5. **Same hooks configuration**: Preserve existing validation logic

## Phase 1: Core Infrastructure

### Overview
Create the foundational components for external stage execution: directory structure, base classes, utilities, and error handling.

### Changes Required:

#### 1. Directory Structure
**Action**: Create new directories

```bash
mkdir -p π/stages
touch π/stages/__init__.py
```

#### 2. Base Stage Runner Class
**File**: `π/stages/__init__.py`
**Changes**: Create base class for all stage scripts

```python
"""Stage execution infrastructure for external workflow processes."""

import json
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class StageResult:
    """Structured result from a stage execution."""

    status: str  # "success" or "error"
    result: str  # Last message from agent
    document: str | None  # Path to generated document (if applicable)
    stats: dict[str, Any]  # Tool usage statistics
    error: str | None = None  # Error message if status="error"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageResult":
        """Deserialize from dictionary."""
        return cls(**data)


class StageRunner(ABC):
    """Base class for all workflow stage scripts."""

    def __init__(self, args: list[str]):
        """Initialize with command-line arguments."""
        self.args = args
        self.workflow_id: str = ""
        self.user_query: str = ""
        self.log_dir: Path = Path()
        self.thoughts_dir: Path = Path()
        self.previous_result: str = ""

    @abstractmethod
    def parse_args(self) -> None:
        """Parse command-line arguments specific to this stage."""
        pass

    @abstractmethod
    async def run_stage(self) -> StageResult:
        """Execute the stage logic and return structured result."""
        pass

    def output_result(self, result: StageResult) -> None:
        """Output result as JSON to stdout."""
        print(result.to_json())

    def output_stats(self, stats_summary: str) -> None:
        """Output stats to stderr for progress reporting."""
        print(stats_summary, file=sys.stderr)

    async def execute(self) -> int:
        """Main execution flow. Returns exit code."""
        try:
            self.parse_args()
            result = await self.run_stage()
            self.output_result(result)
            return 0 if result.status == "success" else 1
        except Exception as e:
            error_result = StageResult(
                status="error",
                result="",
                document=None,
                stats={},
                error=str(e)
            )
            self.output_result(error_result)
            return 1
```

#### 3. Utilities for Stage Execution
**File**: `π/utils.py`
**Changes**: Add functions to run stages and parse results

```python
def run_stage(
    stage_name: str,
    args: list[str],
    cwd: Path,
    retry: bool = True
) -> tuple[int, StageResult | None]:
    """Run a workflow stage script and parse its JSON output.

    Args:
        stage_name: Name of the stage (e.g., "research")
        args: Command-line arguments to pass to the stage
        cwd: Working directory
        retry: Whether to retry once on failure

    Returns:
        Tuple of (exit_code, StageResult or None)
    """
    import subprocess
    import sys
    import json
    from π.stages import StageResult

    command = [sys.executable, f"π/stages/{stage_name}.py"] + args

    # First attempt
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True
    )

    # Retry once if failed and retry enabled
    if result.returncode != 0 and retry:
        print(f"⚠️  Stage {stage_name} failed, retrying once...")
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True
        )

    # Log stderr (stats and progress info)
    if result.stderr:
        print(result.stderr.strip())

    # Parse JSON output
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            stage_result = StageResult.from_dict(data)
            return (0, stage_result)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse stage output: {e}")
            return (1, None)
    else:
        # Try to parse error result
        try:
            data = json.loads(result.stdout)
            stage_result = StageResult.from_dict(data)
            return (result.returncode, stage_result)
        except:
            return (result.returncode, None)
```

### Success Criteria:

#### Automated Verification:
- [ ] Directory `π/stages/` exists with `__init__.py`
- [ ] `StageRunner` class imports successfully: `python -c "from π.stages import StageRunner, StageResult"`
- [ ] `run_stage()` function imports successfully: `python -c "from π.utils import run_stage"`
- [ ] No linting errors: `uv run ruff check .`
- [ ] Type checking passes (if using mypy): `uv run mypy π/`

#### Manual Verification:
- [ ] Review `StageRunner` base class design for completeness
- [ ] Verify error handling covers edge cases
- [ ] Confirm JSON schema matches expected contract

---

## Phase 2: Implement Individual Stage Scripts

### Overview
Create 7 stage scripts that wrap existing `run_agent()` functionality with JSON I/O protocol.

### Changes Required:

#### 1. Research Stage Script
**File**: `π/stages/research.py`
**Changes**: Create standalone script for research stage

```python
#!/usr/bin/env python3
"""Research codebase stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import find_file_starting_with, load_prompt


class ResearchStage(StageRunner):
    """Research codebase stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir thoughts_dir"""
        if len(self.args) < 5:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <thoughts_dir>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.thoughts_dir = Path(self.args[4])

    async def run_stage(self) -> StageResult:
        """Execute research stage."""
        # Load prompt template
        prompt_template, model = load_prompt("research_codebase")
        prompt = prompt_template.format(
            workflow_id=self.workflow_id,
            user_query=self.user_query,
        )

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "research.log",
            prompt=prompt,
            verbose=False
        )

        # Find generated document
        try:
            document = find_file_starting_with(
                base_dir=self.thoughts_dir,
                start_text="research"
            )
            document_path = str(document)
        except FileNotFoundError:
            document_path = None

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=document_path,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ResearchStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 2. Plan Stage Script
**File**: `π/stages/plan.py`
**Changes**: Create standalone script for plan creation stage

```python
#!/usr/bin/env python3
"""Create plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import find_file_starting_with, load_prompt


class PlanStage(StageRunner):
    """Create implementation plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir thoughts_dir research_doc previous_result"""
        if len(self.args) < 7:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <thoughts_dir> <research_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.thoughts_dir = Path(self.args[4])
        self.research_document = self.args[5]
        self.previous_result = self.args[6]

    async def run_stage(self) -> StageResult:
        """Execute plan creation stage."""
        # Load prompt template
        prompt_template, model = load_prompt("create_plan")
        prompt = prompt_template.format(
            research_document=self.research_document,
            workflow_id=self.workflow_id,
            user_query=self.user_query,
        )

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent with previous stage result as context
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "plan.log",
            prompt=f"{prompt}\n\n{self.previous_result}",
            verbose=False
        )

        # Find generated document
        try:
            document = find_file_starting_with(
                base_dir=self.thoughts_dir,
                start_text="plan"
            )
            document_path = str(document)
        except FileNotFoundError:
            document_path = None

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=document_path,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = PlanStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 3. Review Stage Script
**File**: `π/stages/review.py`
**Changes**: Create standalone script for plan review stage

```python
#!/usr/bin/env python3
"""Review plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class ReviewStage(StageRunner):
    """Review plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir research_doc plan_doc previous_result"""
        if len(self.args) < 7:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <research_doc> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.research_document = self.args[4]
        self.plan_document = self.args[5]
        self.previous_result = self.args[6]

    async def run_stage(self) -> StageResult:
        """Execute review stage."""
        # Load prompt template
        prompt_template, model = load_prompt("review_plan")
        prompt = prompt_template.format(
            research_document=self.research_document,
            plan_document=self.plan_document,
            workflow_id=self.workflow_id,
            user_query=self.user_query,
        )

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "review.log",
            prompt=f"{prompt}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result (review doesn't create a new document)
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ReviewStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 4. Iterate Stage Script
**File**: `π/stages/iterate.py`
**Changes**: Create standalone script for plan iteration stage

```python
#!/usr/bin/env python3
"""Iterate plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class IterateStage(StageRunner):
    """Iterate on plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id user_query log_dir research_doc plan_doc previous_result"""
        if len(self.args) < 7:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <user_query> <log_dir> <research_doc> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.user_query = self.args[2]
        self.log_dir = Path(self.args[3])
        self.research_document = self.args[4]
        self.plan_document = self.args[5]
        self.previous_result = self.args[6]

    async def run_stage(self) -> StageResult:
        """Execute iteration stage."""
        # Load prompt template
        prompt_template, model = load_prompt("iterate_plan")
        prompt = prompt_template.format(
            research_document=self.research_document,
            plan_document=self.plan_document,
            workflow_id=self.workflow_id,
            user_query=self.user_query,
        )

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "iterate.log",
            prompt=f"{prompt}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = IterateStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 5. Implement Stage Script
**File**: `π/stages/implement.py`
**Changes**: Create standalone script for implementation stage

```python
#!/usr/bin/env python3
"""Implement plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class ImplementStage(StageRunner):
    """Implement plan stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id log_dir plan_doc previous_result"""
        if len(self.args) < 5:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <log_dir> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.log_dir = Path(self.args[2])
        self.plan_document = self.args[3]
        self.previous_result = self.args[4]

    async def run_stage(self) -> StageResult:
        """Execute implementation stage."""
        # Load prompt template
        prompt_template, model = load_prompt("implement_plan")

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent - implement_plan prompt expects plan path
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "implement.log",
            prompt=f"{prompt_template}\n\nPlan: {self.plan_document}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ImplementStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 6. Commit Stage Script
**File**: `π/stages/commit.py`
**Changes**: Create standalone script for commit stage

```python
#!/usr/bin/env python3
"""Commit changes stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class CommitStage(StageRunner):
    """Commit changes stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id log_dir previous_result"""
        if len(self.args) < 4:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <log_dir> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.log_dir = Path(self.args[2])
        self.previous_result = self.args[3]

    async def run_stage(self) -> StageResult:
        """Execute commit stage."""
        # Load prompt template
        prompt_template, model = load_prompt("commit")

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "commit.log",
            prompt=f"{prompt_template}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = CommitStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

#### 7. Validate Stage Script
**File**: `π/stages/validate.py`
**Changes**: Create standalone script for validation stage

```python
#!/usr/bin/env python3
"""Validate plan stage - external process wrapper."""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions
from π.agent import run_agent
from π.stages import StageResult, StageRunner
from π.utils import load_prompt


class ValidateStage(StageRunner):
    """Validate implementation stage."""

    def parse_args(self) -> None:
        """Parse: workflow_id log_dir plan_doc previous_result"""
        if len(self.args) < 5:
            raise ValueError(
                f"Usage: {self.args[0]} <workflow_id> <log_dir> <plan_doc> <previous_result>"
            )
        self.workflow_id = self.args[1]
        self.log_dir = Path(self.args[2])
        self.plan_document = self.args[3]
        self.previous_result = self.args[4]

    async def run_stage(self) -> StageResult:
        """Execute validation stage."""
        # Load prompt template
        prompt_template, model = load_prompt("validate_plan")

        # Configure options
        options = ClaudeAgentOptions(
            permission_mode="acceptEdits",
            setting_sources=["project"],
            model=model,
            cwd=Path.cwd()
        )

        # Run agent
        result, stats = await run_agent(
            options=options,
            log_file=self.log_dir / "validate.log",
            prompt=f"{prompt_template}\n\nPlan: {self.plan_document}\n\n{self.previous_result}",
            verbose=False
        )

        # Output stats to stderr
        self.output_stats(f"📊 {stats.get_summary()}")

        # Return structured result
        return StageResult(
            status="success",
            result=result,
            document=None,
            stats={
                "total_tools": stats.total_tools,
                "errors": stats.errors,
                "tool_counts": stats.tool_counts
            }
        )


async def main() -> int:
    """Entry point."""
    stage = ValidateStage(sys.argv)
    return await stage.execute()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

### Success Criteria:

#### Automated Verification:
- [ ] All 7 stage scripts exist and are executable: `ls -l π/stages/*.py`
- [ ] Each script imports successfully: `python -c "import π.stages.research"`
- [ ] No linting errors: `uv run ruff check π/stages/`
- [ ] Type checking passes: `uv run mypy π/stages/`
- [ ] Each script can be invoked with --help without error

#### Manual Verification:
- [ ] Review each stage script for correct argument parsing
- [ ] Verify JSON output structure matches StageResult schema
- [ ] Confirm error handling propagates to JSON output
- [ ] Check that all prompt template variables are correctly passed

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 3: Refactor workflow.py

### Overview
Replace in-process agent calls with subprocess invocations, implementing sequential execution with retry logic and JSON parsing.

### Changes Required:

#### 1. Update Imports
**File**: `π/workflow.py`
**Changes**: Add subprocess utilities import

```python
# Add to imports section
from π.utils import run_stage
```

#### 2. Refactor Stage Execution Pattern
**File**: `π/workflow.py`
**Changes**: Replace existing run_agent calls with run_stage calls

**Before** (lines 56-73):
```python
# 1. Research codebase
print("\n🔍 Stage 1/4: Researching codebase...")
research_prompt_template, research_model = load_prompt("research_codebase")
research_prompt = research_prompt_template.format(
    workflow_id=workflow_id,
    user_query=user_query,
)
research_codebase_result, research_stats = await run_agent(
    options=_get_options(cwd=cwd, model=research_model),
    log_file=workflow_log_dir / "research.log",
    prompt=f"{research_prompt}",
    verbose=False,
)
research_document = find_file_starting_with(
    base_dir=workflow_thoughts_dir,
    start_text="research",
)
print(f"✓ Research completed → {research_document.name}")
print(f"  📊 {research_stats.get_summary()}")
```

**After**:
```python
# 1. Research codebase
print("\n🔍 Stage 1/7: Researching codebase...")
exit_code, research_result = run_stage(
    stage_name="research",
    args=[
        workflow_id,
        user_query,
        str(workflow_log_dir),
        str(workflow_thoughts_dir)
    ],
    cwd=cwd,
    retry=True
)

if exit_code != 0 or not research_result:
    print(f"❌ Research stage failed")
    return None

research_document = Path(research_result.document) if research_result.document else None
print(f"✓ Research completed → {research_document.name if research_document else 'N/A'}")
```

#### 3. Update All Stage Invocations
**File**: `π/workflow.py`
**Changes**: Apply same pattern to all stages

```python
async def run_workflow(*, prompt: str, cwd: Path) -> None | str:
    # Generate unique workflow ID
    workflow_id = generate_workflow_id()

    # Create workflow-specific thoughts & log directories
    thoughts_base = cwd / Path("thoughts")
    logs_base = cwd / Path(".logs")

    workflow_thoughts_dir = create_workflow_dir(thoughts_base, workflow_id)
    workflow_log_dir = create_workflow_dir(logs_base, workflow_id)

    print("=" * 80)
    print(f"Workflow ID: {workflow_id}")
    print(f"Thoughts: {workflow_thoughts_dir}")
    print(f"Logs: {workflow_log_dir}")
    print("=" * 80)

    user_query = prompt.strip()

    # 1. Research codebase
    print("\n🔍 Stage 1/7: Researching codebase...")
    exit_code, research_result = run_stage(
        stage_name="research",
        args=[workflow_id, user_query, str(workflow_log_dir), str(workflow_thoughts_dir)],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not research_result:
        print(f"❌ Research stage failed")
        return None
    research_document = research_result.document
    print(f"✓ Research completed → {Path(research_document).name if research_document else 'N/A'}")

    # 2. Create plan
    print("\n📝 Stage 2/7: Creating implementation plan...")
    exit_code, plan_result = run_stage(
        stage_name="plan",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            str(workflow_thoughts_dir),
            research_document or "",
            research_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not plan_result:
        print(f"❌ Plan stage failed")
        return None
    plan_document = plan_result.document
    print(f"✓ Plan created → {Path(plan_document).name if plan_document else 'N/A'}")

    # 3. Review plan
    print("\n🔎 Stage 3/7: Reviewing plan...")
    exit_code, review_result = run_stage(
        stage_name="review",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            research_document or "",
            plan_document or "",
            plan_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not review_result:
        print(f"❌ Review stage failed")
        return None
    print("✓ Plan reviewed")

    # 4. Iterate plan
    print("\n🔄 Stage 4/7: Iterating on plan...")
    exit_code, iterate_result = run_stage(
        stage_name="iterate",
        args=[
            workflow_id,
            user_query,
            str(workflow_log_dir),
            research_document or "",
            plan_document or "",
            review_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not iterate_result:
        print(f"❌ Iterate stage failed")
        return None
    print("✓ Plan iteration completed")

    # 5. Implement plan
    print("\n⚙️  Stage 5/7: Implementing plan...")
    exit_code, implement_result = run_stage(
        stage_name="implement",
        args=[
            workflow_id,
            str(workflow_log_dir),
            plan_document or "",
            iterate_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not implement_result:
        print(f"❌ Implementation stage failed")
        return None
    print("✓ Implementation completed")

    # 6. Commit changes
    print("\n💾 Stage 6/7: Committing changes...")
    exit_code, commit_result = run_stage(
        stage_name="commit",
        args=[
            workflow_id,
            str(workflow_log_dir),
            implement_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not commit_result:
        print(f"❌ Commit stage failed")
        return None
    print("✓ Changes committed")

    # 7. Validate plan
    print("\n✅ Stage 7/7: Validating implementation...")
    exit_code, validate_result = run_stage(
        stage_name="validate",
        args=[
            workflow_id,
            str(workflow_log_dir),
            plan_document or "",
            commit_result.result
        ],
        cwd=cwd,
        retry=True
    )
    if exit_code != 0 or not validate_result:
        print(f"❌ Validation stage failed")
        return None
    print("✓ Validation completed")

    # Calculate total stats from all stages
    total_tools = sum([
        research_result.stats.get("total_tools", 0),
        plan_result.stats.get("total_tools", 0),
        review_result.stats.get("total_tools", 0),
        iterate_result.stats.get("total_tools", 0),
        implement_result.stats.get("total_tools", 0),
        commit_result.stats.get("total_tools", 0),
        validate_result.stats.get("total_tools", 0),
    ])
    total_errors = sum([
        research_result.stats.get("errors", 0),
        plan_result.stats.get("errors", 0),
        review_result.stats.get("errors", 0),
        iterate_result.stats.get("errors", 0),
        implement_result.stats.get("errors", 0),
        commit_result.stats.get("errors", 0),
        validate_result.stats.get("errors", 0),
    ])

    print("\n" + "=" * 80)
    print("✅ Workflow completed successfully!")
    print(f"Final plan: {plan_document}")
    print(f"Full logs: {workflow_log_dir}")
    print(f"Total: {total_tools} tools executed, {total_errors} errors")
    print("=" * 80)

    return validate_result.result
```

#### 4. Remove Commented Code
**File**: `π/workflow.py`
**Changes**: Delete lines 153-176 (old commented-out stage implementations)

#### 5. Remove Old Agent Import
**File**: `π/workflow.py`
**Changes**: Update imports to remove `run_agent`

**Before**:
```python
from π.agent import run_agent
```

**After**:
```python
# run_agent no longer needed - stages are external processes
```

#### 6. Remove _get_options Function
**File**: `π/workflow.py`
**Changes**: Delete `_get_options()` function (lines 18-32) as it's now handled in stage scripts

### Success Criteria:

#### Automated Verification:
- [ ] workflow.py imports successfully: `python -c "from π.workflow import run_workflow"`
- [ ] No linting errors: `uv run ruff check π/workflow.py`
- [ ] Type checking passes: `uv run mypy π/workflow.py`
- [ ] No references to old run_agent pattern: `grep -n "run_agent" π/workflow.py` returns empty

#### Manual Verification:
- [ ] Review error handling for each stage invocation
- [ ] Verify retry logic is correctly implemented
- [ ] Confirm all stage arguments are properly passed
- [ ] Check that document paths flow correctly between stages

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 4: Testing Infrastructure

### Overview
Set up pytest framework and create integration test for full workflow execution.

### Changes Required:

#### 1. Add Test Dependencies
**File**: `pyproject.toml`
**Changes**: Add pytest to dev dependencies

```toml
[dependency-groups]
dev = [
    "ruff>=0.14.1",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

#### 2. Create Test Directory Structure
**Action**: Create test directories

```bash
mkdir -p tests/integration
touch tests/__init__.py
touch tests/integration/__init__.py
```

#### 3. Create Workflow Integration Test
**File**: `tests/integration/test_workflow.py`
**Changes**: Create comprehensive workflow test

```python
"""Integration tests for workflow execution."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from π.workflow import run_workflow


@pytest.fixture
def mock_cwd(tmp_path):
    """Create temporary working directory with required structure."""
    (tmp_path / "thoughts").mkdir()
    (tmp_path / ".logs").mkdir()
    return tmp_path


@pytest.fixture
def sample_prompt():
    """Sample workflow prompt."""
    return "Research the authentication system and create an implementation plan"


@pytest.mark.asyncio
async def test_workflow_basic_execution(mock_cwd, sample_prompt):
    """Test basic workflow execution through all stages."""

    # Mock run_stage to return successful results
    from π.stages import StageResult

    def mock_run_stage(stage_name, args, cwd, retry=True):
        """Mock stage execution."""
        result = StageResult(
            status="success",
            result=f"Mock result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name in ["research", "plan"] else None,
            stats={"total_tools": 10, "errors": 0, "tool_counts": {"Read": 5}}
        )
        # Create mock document files
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        result = await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify workflow completed
        assert result is not None
        assert "validate" in result.lower() or "Mock result" in result


@pytest.mark.asyncio
async def test_workflow_handles_stage_failure(mock_cwd, sample_prompt):
    """Test workflow stops on stage failure."""

    def mock_run_stage_with_failure(stage_name, args, cwd, retry=True):
        """Mock stage that fails on plan stage."""
        from π.stages import StageResult

        if stage_name == "plan":
            # Simulate failure
            return (1, None)

        result = StageResult(
            status="success",
            result=f"Mock result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name == "research" else None,
            stats={"total_tools": 10, "errors": 0, "tool_counts": {"Read": 5}}
        )
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage_with_failure):
        result = await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify workflow stopped
        assert result is None


@pytest.mark.asyncio
async def test_workflow_creates_directories(mock_cwd, sample_prompt):
    """Test workflow creates thoughts and log directories."""

    from π.stages import StageResult

    def mock_run_stage(stage_name, args, cwd, retry=True):
        result = StageResult(
            status="success",
            result="Mock result",
            document=None,
            stats={"total_tools": 1, "errors": 0, "tool_counts": {}}
        )
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify directories exist
        assert (mock_cwd / "thoughts").exists()
        assert (mock_cwd / ".logs").exists()

        # Verify workflow-specific directories were created
        thoughts_dirs = list((mock_cwd / "thoughts").iterdir())
        log_dirs = list((mock_cwd / ".logs").iterdir())

        assert len(thoughts_dirs) > 0
        assert len(log_dirs) > 0


@pytest.mark.asyncio
async def test_workflow_passes_data_between_stages(mock_cwd, sample_prompt):
    """Test data flows correctly between stages."""

    from π.stages import StageResult

    stage_calls = []

    def mock_run_stage(stage_name, args, cwd, retry=True):
        """Track stage calls and arguments."""
        stage_calls.append({
            "stage": stage_name,
            "args": args
        })

        result = StageResult(
            status="success",
            result=f"Result from {stage_name}",
            document=str(mock_cwd / "thoughts" / f"{stage_name}.md") if stage_name in ["research", "plan"] else None,
            stats={"total_tools": 1, "errors": 0, "tool_counts": {}}
        )
        if result.document:
            Path(result.document).touch()
        return (0, result)

    with patch("π.workflow.run_stage", side_effect=mock_run_stage):
        await run_workflow(prompt=sample_prompt, cwd=mock_cwd)

        # Verify stages were called in order
        expected_stages = ["research", "plan", "review", "iterate", "implement", "commit", "validate"]
        actual_stages = [call["stage"] for call in stage_calls]
        assert actual_stages == expected_stages

        # Verify plan stage received research result
        plan_call = stage_calls[1]  # Second call is plan
        assert "Result from research" in plan_call["args"][-1]
```

#### 4. Update Makefile
**File**: `Makefile`
**Changes**: Add test target

```makefile
test:
	@echo "Running tests with pytest..."
	uv run pytest tests/ -v

check:
	@echo "Linting code with ruff..."
	uv run ruff check .
	@echo "Running tests..."
	uv run pytest tests/ -v
```

#### 5. Create pytest Configuration
**File**: `pytest.ini`
**Changes**: Configure pytest

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

### Success Criteria:

#### Automated Verification:
- [ ] pytest installed: `uv run pytest --version`
- [ ] Tests discovered: `uv run pytest --collect-only`
- [ ] All tests pass: `make test`
- [ ] Linting passes: `uv run ruff check tests/`
- [ ] Coverage acceptable: `uv run pytest --cov=π tests/`

#### Manual Verification:
- [ ] Review test coverage for comprehensiveness
- [ ] Verify mock objects accurately simulate stage behavior
- [ ] Confirm tests cover error paths
- [ ] Check that tests can run in isolation

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation from the human that the manual testing was successful before proceeding to the next phase.

---

## Phase 5: Documentation & Cleanup

### Overview
Update documentation, remove dead code, and add architectural explanations.

### Changes Required:

#### 1. Update README
**File**: `README.md`
**Changes**: Document new architecture

Add new section after line 56:

```markdown
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
```

#### 2. Add Architecture Diagram Comment
**File**: `π/workflow.py`
**Changes**: Add module docstring with ASCII diagram

```python
"""Workflow orchestration via external stage processes.

Architecture:

    run_workflow()
         |
         ├─> [research.py] ──> research.md
         |        ↓
         ├─> [plan.py] ────> plan.md
         |        ↓
         ├─> [review.py]
         |        ↓
         ├─> [iterate.py]
         |        ↓
         ├─> [implement.py]
         |        ↓
         ├─> [commit.py]
         |        ↓
         └─> [validate.py]

Each stage:
  - Runs as external Python subprocess
  - Receives context via CLI arguments
  - Outputs JSON to stdout
  - Logs progress to stderr
  - Returns StageResult with status/stats

Data flow:
  - Sequential execution (no parallelism)
  - Previous stage result passed to next
  - Document paths tracked across stages
  - Retry once on failure
"""
```

#### 3. Remove Unused Imports
**File**: `π/workflow.py`
**Changes**: Clean up imports

Remove:
```python
from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import HookMatcher
from π.hooks import check_bash_command, check_file_format
```

These are now only used within stage scripts.

#### 4. Update Installation Instructions
**File**: `README.md`
**Changes**: Update development setup (line 45-50)

```markdown
## Development

Install dependencies:
```bash
make install
```

Run linting and tests:
```bash
make check
```

Run tests only:
```bash
make test
```
```

#### 5. Add Stage Development Guide
**File**: `π/stages/README.md`
**Changes**: Create new file

```markdown
# Workflow Stages

Each stage in the workflow system runs as an independent Python script.

## Structure

All stages follow this pattern:

1. Inherit from `StageRunner` base class
2. Implement `parse_args()` to handle CLI arguments
3. Implement `run_stage()` to execute logic
4. Return `StageResult` with structured output
5. Use `asyncio.run(main())` as entry point

## Data Contract

### Input (CLI Arguments)
Common arguments across stages:
- `workflow_id`: Unique identifier for this workflow run
- `user_query`: The user's original request
- `log_dir`: Directory for log files
- `thoughts_dir`: Directory for generated documents
- `previous_result`: Result from previous stage

### Output (JSON on stdout)
```json
{
  "status": "success",
  "result": "Final message from agent",
  "document": "/path/to/document.md",
  "stats": {
    "total_tools": 42,
    "errors": 0,
    "tool_counts": {"Read": 15, "Grep": 10}
  }
}
```

## Adding a New Stage

1. Create `π/stages/new_stage.py`
2. Subclass `StageRunner`
3. Implement required methods
4. Add corresponding prompt file in `π/prompts/`
5. Update `π/workflow.py` to invoke the stage
6. Add test in `tests/integration/`

## Testing Stages Independently

Each stage can be tested standalone:

```bash
python π/stages/research.py \
  <workflow-id> \
  "user query" \
  /path/to/logs \
  /path/to/thoughts
```

The stage will output JSON result to stdout and progress to stderr.
```

### Success Criteria:

#### Automated Verification:
- [ ] README renders correctly on GitHub
- [ ] No broken links in documentation: `make check-links` (if available)
- [ ] No linting errors: `uv run ruff check .`
- [ ] All tests still pass: `make test`

#### Manual Verification:
- [ ] README accurately describes new architecture
- [ ] ASCII diagram is clear and helpful
- [ ] Stage development guide is complete
- [ ] Installation instructions work for new developers
- [ ] No references to old implementation remain

---

## Testing Strategy

### Integration Tests (Phase 4)
- **Full workflow execution**: Test all 7 stages in sequence
- **Failure handling**: Verify workflow stops on stage failure
- **Data passing**: Confirm results flow between stages
- **Directory creation**: Check logs and thoughts directories
- **Retry logic**: Verify stages retry once on failure

### Manual Testing Steps
1. Run full workflow with sample prompt: `π "Add user authentication"`
2. Verify all 7 stages execute successfully
3. Check generated files in thoughts/ and .logs/ directories
4. Inspect JSON output from individual stages
5. Test stage failure by introducing error (e.g., bad prompt file)
6. Verify retry logic by simulating transient failure
7. Run `make check` to ensure linting passes
8. Run `make test` to ensure integration tests pass

## Performance Considerations

**Process Overhead**:
- Each stage spawns new Python interpreter (~100-200ms overhead)
- 7 stages = ~700-1400ms total overhead
- Negligible compared to agent execution time (typically minutes)

**Memory Usage**:
- Each stage runs in isolated process
- No memory accumulation across stages
- Peak memory per stage ~200-500MB (agent SDK overhead)

**Disk I/O**:
- Increased file operations for JSON serialization
- Log files now written per-stage
- Minimal impact (<1% overhead)

## Migration Notes

**Breaking Changes**:
- `run_workflow()` signature unchanged - no external API impact
- Internal implementation completely refactored
- No data migration needed (thoughts/ structure unchanged)

**Backward Compatibility**:
- CLI interface remains identical
- Prompt files unchanged
- Output format unchanged
- Log structure unchanged

**Deployment**:
- No special migration steps required
- Install new dependencies: `make install`
- Run tests to verify: `make test`
- Deploy as normal

## References

- Original workflow: `π/workflow.py:35-176` (before refactoring)
- Subprocess pattern: `π/hooks.py:93-210`
- Prompt loading: `π/utils.py:8-47`
- Agent execution: `π/agent.py:139-161`
