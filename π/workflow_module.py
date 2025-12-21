"""DSPy Workflow Module for π.

Provides PiWorkflow, a structured dspy.Module that enforces
sequential stage execution with per-stage model selection.
"""

from functools import lru_cache
from os import getenv
from pathlib import Path
from typing import TYPE_CHECKING

import dspy

from π.config import Provider
from π.hitl import ConsoleInputProvider, HumanInputProvider, create_ask_human_tool
from π.stage_config import DEFAULT_STAGE_CONFIGS, Stage, StageConfig
from π.workflow import clarify_goal, create_plan, implement_plan, research_codebase

if TYPE_CHECKING:
    from collections.abc import Callable


@lru_cache(maxsize=6)
def get_lm(provider: Provider, tier: str) -> dspy.LM:
    """Get cached LM instance for provider/tier combination.

    Args:
        provider: AI provider (claude, antigravity, openai)
        tier: Model tier (low, med, high)

    Returns:
        Configured dspy.LM instance
    """
    from π.config import get_model

    model = get_model(provider=provider, tier=tier)
    return dspy.LM(
        api_base=getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
        api_key=getenv("CLIPROXY_API_KEY"),
        model=model,
    )


class PiWorkflow(dspy.Module):
    """Workflow module with per-stage ReAct agents.

    Enforces sequential execution: clarify → research → plan → implement.
    Each stage uses a dedicated ReAct agent with configurable model tier.

    Attributes:
        provider: AI provider for model selection
        configs: Per-stage configuration (model tier, max iterations)
        human_input: Provider for human-in-the-loop interactions
    """

    def __init__(
        self,
        *,
        provider: Provider = Provider.Claude,
        stage_configs: dict[Stage, StageConfig] | None = None,
        human_input_provider: HumanInputProvider | None = None,
    ):
        """Initialize workflow with configuration.

        Args:
            provider: AI provider (default: Claude)
            stage_configs: Custom per-stage configs (merged with defaults)
            human_input_provider: HITL provider (default: ConsoleInputProvider)
        """
        super().__init__()
        self.provider = provider
        self.configs = {**DEFAULT_STAGE_CONFIGS, **(stage_configs or {})}
        self.human_input = human_input_provider or ConsoleInputProvider()

        # Build per-stage ReAct agents
        self._clarify_agent = self._build_clarify_agent()
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._implement_agent = self._build_implement_agent()

    def _build_clarify_agent(self) -> dspy.ReAct:
        """Build clarify stage agent with HITL tool."""
        return dspy.ReAct(
            signature="objective -> clarified_objective",
            tools=[
                self._wrap_clarify_tool(),
                create_ask_human_tool(self.human_input),
            ],
            max_iters=self.configs[Stage.CLARIFY].max_iters,
        )

    def _build_research_agent(self) -> dspy.ReAct:
        """Build research stage agent."""
        return dspy.ReAct(
            signature="objective -> research_summary, research_doc_path",
            tools=[self._wrap_research_tool()],
            max_iters=self.configs[Stage.RESEARCH].max_iters,
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        """Build plan stage agent."""
        return dspy.ReAct(
            signature="objective, research_doc_path -> plan_summary, plan_doc_path",
            tools=[self._wrap_plan_tool()],
            max_iters=self.configs[Stage.PLAN].max_iters,
        )

    def _build_implement_agent(self) -> dspy.ReAct:
        """Build implement stage agent."""
        return dspy.ReAct(
            signature="objective, plan_doc_path -> implementation_summary",
            tools=[self._wrap_implement_tool()],
            max_iters=self.configs[Stage.IMPLEMENT].max_iters,
        )

    def _run_stage(
        self, stage: Stage, agent: dspy.ReAct, **kwargs
    ) -> dspy.Prediction:
        """Run agent with stage-specific model via dspy.context().

        Args:
            stage: The workflow stage being executed
            agent: The ReAct agent for this stage
            **kwargs: Arguments to pass to the agent

        Returns:
            Agent's prediction output
        """
        lm = get_lm(self.provider, self.configs[stage].model_tier)
        with dspy.context(lm=lm):
            return agent(**kwargs)

    def forward(self, objective: str) -> dspy.Prediction:
        """Execute workflow with enforced stage order.

        Stages execute sequentially: clarify → research → plan → implement.
        Each stage's output feeds into the next stage.

        Args:
            objective: The user's original objective/task

        Returns:
            Prediction containing all stage outputs:
            - objective: The clarified objective
            - research_doc_path: Path to research document
            - plan_doc_path: Path to plan document
            - implementation_summary: Summary of implementation
        """
        # Stage 1: Clarify (uses HITL for human interaction)
        clarified = self._run_stage(
            Stage.CLARIFY,
            self._clarify_agent,
            objective=objective,
        )
        working_objective = getattr(clarified, "clarified_objective", None) or objective

        # Stage 2: Research (deep codebase exploration)
        researched = self._run_stage(
            Stage.RESEARCH,
            self._research_agent,
            objective=working_objective,
        )

        # Stage 3: Plan (architectural reasoning)
        planned = self._run_stage(
            Stage.PLAN,
            self._plan_agent,
            objective=working_objective,
            research_doc_path=researched.research_doc_path,
        )

        # Stage 4: Implement (code generation)
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

    # -------------------------------------------------------------------------
    # Tool Wrappers (delegate to existing workflow functions)
    # -------------------------------------------------------------------------

    def _wrap_clarify_tool(self) -> "Callable":
        """Wrap clarify_goal as a DSPy tool."""

        def clarify_tool(query: str) -> str:
            """Run clarification via Claude SDK.

            Use this to clarify the user's objective by engaging
            with the clarification workflow.

            Args:
                query: The objective or question to clarify

            Returns:
                Clarification result with session info
            """
            return clarify_goal(query=query)

        return clarify_tool

    def _wrap_research_tool(self) -> "Callable":
        """Wrap research_codebase as a DSPy tool."""

        def research_tool(query: str) -> str:
            """Research codebase via Claude SDK.

            Explores the codebase to understand existing patterns,
            architecture, and relevant code for the objective.

            Args:
                query: What to research in the codebase

            Returns:
                Research summary with document path
            """
            return research_codebase(query=query)

        return research_tool

    def _wrap_plan_tool(self) -> "Callable":
        """Wrap create_plan as a DSPy tool."""

        def plan_tool(research_doc_path: str, query: str) -> str:
            """Create implementation plan via Claude SDK.

            Uses research findings to create a detailed
            implementation plan.

            Args:
                research_doc_path: Path to research document
                query: Planning objective

            Returns:
                Plan summary with document path
            """
            return create_plan(
                research_document_path=Path(research_doc_path),
                query=query,
            )

        return plan_tool

    def _wrap_implement_tool(self) -> "Callable":
        """Wrap implement_plan as a DSPy tool."""

        def implement_tool(plan_doc_path: str, query: str) -> str:
            """Implement plan via Claude SDK.

            Executes the implementation plan, making code changes
            as specified.

            Args:
                plan_doc_path: Path to plan document
                query: Implementation objective

            Returns:
                Implementation summary
            """
            return implement_plan(
                plan_document_path=Path(plan_doc_path),
                query=query,
            )

        return implement_tool
