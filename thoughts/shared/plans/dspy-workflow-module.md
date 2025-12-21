# DSPy Workflow Module Implementation Plan

## Overview

Replace current single ReAct agent with a structured `PiWorkflow` module that:
1. Enforces sequential stage execution (clarify → research → plan → implement)
2. Uses per-stage ReAct agents for tool feedback handling
3. Supports per-stage model selection (Haiku/Sonnet/Opus or Antigravity models)
4. Integrates human-in-the-loop (HITL) for the clarify stage

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PiWorkflow(dspy.Module)                                                │
│                                                                         │
│  forward(objective) enforces: clarify → research → plan → implement    │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ ClarifyAgent     │  │ ResearchAgent    │  │ PlanAgent        │ ...  │
│  │ (ReAct + Haiku)  │  │ (ReAct + Opus)   │  │ (ReAct + Opus)   │      │
│  │                  │  │                  │  │                  │      │
│  │ tools:           │  │ tools:           │  │ tools:           │      │
│  │ - clarify_tool   │  │ - research_tool  │  │ - plan_tool      │      │
│  │ - ask_human      │  │                  │  │                  │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
π/
├── workflow_module.py   # NEW: PiWorkflow dspy.Module
├── hitl.py              # NEW: Human-in-the-loop providers
├── stage_config.py      # NEW: Stage enum and configurations
├── workflow.py          # KEEP: Existing tool functions (clarify_goal, etc.)
├── cli.py               # UPDATE: Use PiWorkflow, add per-stage model flags
└── config.py            # UPDATE: Add LM factory helper
```

## Implementation Phases

### Phase 1: Foundation (Days 1-2)

#### 1.1 Create `π/stage_config.py`

```python
from dataclasses import dataclass
from enum import StrEnum


class Stage(StrEnum):
    CLARIFY = "clarify"
    RESEARCH = "research"
    PLAN = "plan"
    IMPLEMENT = "implement"


@dataclass(frozen=True)
class StageConfig:
    """Immutable configuration for a workflow stage."""
    model_tier: str  # "low", "med", "high"
    max_iters: int
    description: str = ""


DEFAULT_STAGE_CONFIGS: dict[Stage, StageConfig] = {
    Stage.CLARIFY: StageConfig(
        model_tier="low",
        max_iters=5,
        description="Fast model for human interaction loops",
    ),
    Stage.RESEARCH: StageConfig(
        model_tier="high",
        max_iters=3,
        description="Powerful model for deep codebase exploration",
    ),
    Stage.PLAN: StageConfig(
        model_tier="high",
        max_iters=3,
        description="Powerful model for architectural reasoning",
    ),
    Stage.IMPLEMENT: StageConfig(
        model_tier="med",
        max_iters=5,
        description="Balanced model for code generation",
    ),
}
```

#### 1.2 Create `π/hitl.py`

```python
from typing import Protocol
from rich.console import Console
from rich.prompt import Prompt


class HumanInputProvider(Protocol):
    def ask(self, question: str) -> str: ...


class ConsoleInputProvider:
    """Console-based human input for CLI."""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def ask(self, question: str) -> str:
        self.console.print(f"\n[bold yellow]Clarification needed:[/bold yellow]")
        self.console.print(f"  {question}\n")
        return Prompt.ask("[bold green]Your answer[/bold green]")


def create_ask_human_tool(provider: HumanInputProvider):
    """Create DSPy-compatible ask_human tool."""
    def ask_human(question: str) -> str:
        """Ask human for clarification. Use when objective is ambiguous."""
        return provider.ask(question)
    return ask_human
```

#### 1.3 Update `π/config.py`

Add LM factory with caching:

```python
from functools import lru_cache

@lru_cache(maxsize=3)
def get_lm(provider: Provider, tier: str) -> dspy.LM:
    """Get cached LM instance for provider/tier."""
    model = get_model(provider=provider, tier=tier)
    return dspy.LM(
        api_base=getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
        api_key=getenv("CLIPROXY_API_KEY"),
        model=model,
    )
```

### Phase 2: Core Module (Days 3-5)

#### 2.1 Create `π/workflow_module.py`

```python
from os import getenv
from pathlib import Path
from typing import Callable

import dspy

from π.config import Provider, get_lm
from π.hitl import ConsoleInputProvider, create_ask_human_tool
from π.stage_config import DEFAULT_STAGE_CONFIGS, Stage, StageConfig
from π.workflow import clarify_goal, create_plan, implement_plan, research_codebase


class PiWorkflow(dspy.Module):
    """
    Workflow module with per-stage ReAct agents.

    Enforces: clarify → research → plan → implement
    Each stage uses configurable model tier.
    """

    def __init__(
        self,
        *,
        provider: Provider = Provider.Claude,
        stage_configs: dict[Stage, StageConfig] | None = None,
        human_input_provider: "HumanInputProvider | None" = None,
    ):
        super().__init__()
        self.provider = provider
        self.configs = {**DEFAULT_STAGE_CONFIGS, **(stage_configs or {})}
        self.human_input = human_input_provider or ConsoleInputProvider()

        # Build per-stage agents
        self._clarify_agent = self._build_clarify_agent()
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._implement_agent = self._build_implement_agent()

    def _build_clarify_agent(self) -> dspy.ReAct:
        return dspy.ReAct(
            signature="objective -> clarified_objective",
            tools=[
                self._wrap_clarify_tool(),
                create_ask_human_tool(self.human_input),
            ],
            max_iters=self.configs[Stage.CLARIFY].max_iters,
        )

    def _build_research_agent(self) -> dspy.ReAct:
        return dspy.ReAct(
            signature="objective -> research_summary, research_doc_path",
            tools=[self._wrap_research_tool()],
            max_iters=self.configs[Stage.RESEARCH].max_iters,
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        return dspy.ReAct(
            signature="objective, research_doc_path -> plan_summary, plan_doc_path",
            tools=[self._wrap_plan_tool()],
            max_iters=self.configs[Stage.PLAN].max_iters,
        )

    def _build_implement_agent(self) -> dspy.ReAct:
        return dspy.ReAct(
            signature="objective, plan_doc_path -> implementation_summary",
            tools=[self._wrap_implement_tool()],
            max_iters=self.configs[Stage.IMPLEMENT].max_iters,
        )

    def _run_stage(self, stage: Stage, agent: dspy.ReAct, **kwargs) -> dspy.Prediction:
        """Run agent with stage-specific model via dspy.context()."""
        lm = get_lm(self.provider, self.configs[stage].model_tier)
        with dspy.context(lm=lm):
            return agent(**kwargs)

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute workflow with enforced stage order."""

        # Stage 1: Clarify
        clarified = self._run_stage(
            Stage.CLARIFY,
            self._clarify_agent,
            objective=objective,
        )
        working_objective = clarified.clarified_objective or objective

        # Stage 2: Research
        researched = self._run_stage(
            Stage.RESEARCH,
            self._research_agent,
            objective=working_objective,
        )

        # Stage 3: Plan
        planned = self._run_stage(
            Stage.PLAN,
            self._plan_agent,
            objective=working_objective,
            research_doc_path=researched.research_doc_path,
        )

        # Stage 4: Implement
        implemented = self._run_stage(
            Stage.IMPLEMENT,
            self._implement_agent,
            objective=working_objective,
            plan_doc_path=planned.plan_doc_path,
        )

        return dspy.Prediction(
            objective=working_objective,
            research_doc_path=researched.research_doc_path,
            plan_doc_path=planned.plan_doc_path,
            implementation_summary=implemented.implementation_summary,
        )

    # --- Tool wrappers ---

    def _wrap_clarify_tool(self) -> Callable:
        def clarify_tool(query: str) -> str:
            """Run clarification via Claude SDK. Returns clarified goal."""
            return clarify_goal(query=query)
        return clarify_tool

    def _wrap_research_tool(self) -> Callable:
        def research_tool(query: str) -> str:
            """Research codebase via Claude SDK. Returns research doc path."""
            return research_codebase(query=query)
        return research_tool

    def _wrap_plan_tool(self) -> Callable:
        def plan_tool(research_doc_path: str, query: str) -> str:
            """Create plan via Claude SDK. Returns plan doc path."""
            return create_plan(
                research_document_path=Path(research_doc_path),
                query=query,
            )
        return plan_tool

    def _wrap_implement_tool(self) -> Callable:
        def implement_tool(plan_doc_path: str, query: str) -> str:
            """Implement plan via Claude SDK."""
            return implement_plan(
                plan_document_path=Path(plan_doc_path),
                query=query,
            )
        return implement_tool
```

### Phase 3: CLI Integration (Days 6-7)

#### 3.1 Update `π/cli.py`

```python
import click
from rich.console import Console

from π.config import Provider, configure_dspy
from π.stage_config import Stage, StageConfig
from π.workflow_module import PiWorkflow

console = Console()


@click.command()
@click.argument("prompt")
@click.option("-p", "--provider", default="claude", help="AI provider")
@click.option("-t", "--thinking", default="med", help="Default model tier")
@click.option("--clarify-tier", default=None, help="Model tier for clarify stage")
@click.option("--research-tier", default=None, help="Model tier for research stage")
@click.option("--plan-tier", default=None, help="Model tier for plan stage")
@click.option("--implement-tier", default=None, help="Model tier for implement stage")
@click.option("-v", "--verbose", is_flag=True, help="Debug logging")
def main(
    prompt: str,
    provider: str,
    thinking: str,
    clarify_tier: str | None,
    research_tier: str | None,
    plan_tier: str | None,
    implement_tier: str | None,
    verbose: bool,
):
    """Run π workflow."""

    # Build stage configs (use per-stage overrides or default tier)
    stage_configs = {}
    if clarify_tier:
        stage_configs[Stage.CLARIFY] = StageConfig(model_tier=clarify_tier, max_iters=5)
    if research_tier:
        stage_configs[Stage.RESEARCH] = StageConfig(model_tier=research_tier, max_iters=3)
    if plan_tier:
        stage_configs[Stage.PLAN] = StageConfig(model_tier=plan_tier, max_iters=3)
    if implement_tier:
        stage_configs[Stage.IMPLEMENT] = StageConfig(model_tier=implement_tier, max_iters=5)

    # Create and run workflow
    workflow = PiWorkflow(
        provider=Provider(provider),
        stage_configs=stage_configs if stage_configs else None,
    )

    result = workflow(objective=prompt)

    console.print("\n[bold green]Workflow complete![/bold green]")
    console.print(f"[dim]Research:[/dim] {result.research_doc_path}")
    console.print(f"[dim]Plan:[/dim] {result.plan_doc_path}")
    console.print(f"\n{result.implementation_summary}")
```

### Phase 4: Testing (Days 8-9)

#### 4.1 Unit Tests

```python
# tests/test_workflow_module.py

import pytest
from unittest.mock import MagicMock, patch
import dspy

from π.workflow_module import PiWorkflow
from π.stage_config import Stage, StageConfig


class TestPiWorkflow:

    def test_enforces_stage_order(self):
        """Stages execute in order: clarify → research → plan → implement."""
        call_order = []

        with patch.object(PiWorkflow, '_run_stage') as mock_run:
            def track_stage(stage, agent, **kwargs):
                call_order.append(stage)
                return dspy.Prediction(
                    clarified_objective="test",
                    research_doc_path="/path/research.md",
                    plan_doc_path="/path/plan.md",
                    implementation_summary="done",
                )
            mock_run.side_effect = track_stage

            workflow = PiWorkflow()
            workflow(objective="test")

            assert call_order == [
                Stage.CLARIFY,
                Stage.RESEARCH,
                Stage.PLAN,
                Stage.IMPLEMENT,
            ]

    def test_per_stage_model_selection(self):
        """Each stage uses configured model tier."""
        stage_configs = {
            Stage.CLARIFY: StageConfig(model_tier="low", max_iters=2),
            Stage.PLAN: StageConfig(model_tier="high", max_iters=5),
        }

        workflow = PiWorkflow(stage_configs=stage_configs)

        assert workflow.configs[Stage.CLARIFY].model_tier == "low"
        assert workflow.configs[Stage.PLAN].model_tier == "high"
        # Defaults preserved
        assert workflow.configs[Stage.RESEARCH].model_tier == "high"

    def test_hitl_tool_available_in_clarify(self):
        """Clarify agent has ask_human tool."""
        workflow = PiWorkflow()

        tool_names = [t.__name__ for t in workflow._clarify_agent.tools]
        assert "ask_human" in tool_names
        assert "clarify_tool" in tool_names

    def test_research_agent_no_hitl(self):
        """Non-clarify agents don't have HITL."""
        workflow = PiWorkflow()

        research_tools = [t.__name__ for t in workflow._research_agent.tools]
        assert "ask_human" not in research_tools
```

#### 4.2 Integration Tests

```python
# tests/test_workflow_integration.py

@pytest.mark.integration
def test_full_workflow_with_mock_claude():
    """End-to-end workflow with mocked Claude SDK."""
    ...
```

### Phase 5: Documentation & Polish (Day 10)

- Update README.md with new CLI flags
- Add docstrings to all public methods
- Update CLAUDE.md with new architecture overview

## Rollback Plan

Keep `π/workflow.py` unchanged. New module is additive:
- If issues, revert `cli.py` to use old `dspy.ReAct` directly
- Old workflow functions remain compatible

## Success Criteria

1. [ ] `π "prompt"` executes all 4 stages in order
2. [ ] Per-stage model selection works (`--plan-tier=high`)
3. [ ] HITL pauses for human input during clarify
4. [ ] Stage skipping is impossible (enforced by Module)
5. [ ] Existing tests pass
6. [ ] New unit tests for PiWorkflow pass

## Open Questions

1. **Skip clarify flag?** Add `--skip-clarify` for simple tasks?
2. **Retry semantics**: If research fails, does ReAct retry automatically?
3. **State persistence**: Save workflow state for resume after crash?
4. **Web HITL**: Queue-based provider for future web UI?

## Dependencies

- dspy >= 2.6 (for `dspy.context()` support)
- No new external dependencies

## Estimated Effort

| Phase | Days | Risk |
|-------|------|------|
| Foundation | 2 | Low |
| Core Module | 3 | Medium |
| CLI Integration | 2 | Low |
| Testing | 2 | Low |
| Documentation | 1 | Low |
| **Total** | **10** | - |
