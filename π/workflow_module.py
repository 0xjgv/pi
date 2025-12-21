"""DSPy Workflow Module for π.

Provides PiWorkflow, a structured dspy.Module that enforces
sequential stage execution with per-stage model selection.
"""

from functools import lru_cache
from os import getenv

import dspy

from π.config import Provider, get_model
from π.hitl import ConsoleInputProvider, HumanInputProvider, create_ask_human_tool
from π.stage_config import DEFAULT_STAGE_CONFIGS, Stage, StageConfig
from π.workflow import clarify_goal, create_plan, implement_plan, research_codebase

# -----------------------------------------------------------------------------
# Stage Signatures
# -----------------------------------------------------------------------------


class ClarifySignature(dspy.Signature):
    """Clarify the user's objective through interactive questioning."""

    objective: str = dspy.InputField(desc="The user's original objective or task")
    clarified_objective: str = dspy.OutputField(
        desc="The refined, unambiguous objective after clarification"
    )


class ResearchSignature(dspy.Signature):
    """Research the codebase to understand patterns and architecture."""

    objective: str = dspy.InputField(desc="The clarified objective to research")
    research_summary: str = dspy.OutputField(
        desc="Summary of research findings about the codebase"
    )
    research_doc_path: str = dspy.OutputField(
        desc="Path to the detailed research document"
    )


class PlanSignature(dspy.Signature):
    """Create an implementation plan based on research findings."""

    objective: str = dspy.InputField(desc="The clarified objective to plan for")
    research_doc_path: str = dspy.InputField(desc="Path to the research document")
    plan_summary: str = dspy.OutputField(desc="Summary of the implementation plan")
    plan_doc_path: str = dspy.OutputField(desc="Path to the detailed plan document")


class ImplementSignature(dspy.Signature):
    """Implement the plan by making code changes."""

    objective: str = dspy.InputField(desc="The clarified objective to implement")
    plan_doc_path: str = dspy.InputField(desc="Path to the plan document")
    implementation_summary: str = dspy.OutputField(
        desc="Summary of the implementation changes made"
    )


# -----------------------------------------------------------------------------
# LM Factory
# -----------------------------------------------------------------------------


@lru_cache(maxsize=6)
def get_lm(provider: Provider, tier: str) -> dspy.LM:
    """Get cached LM instance for provider/tier combination.

    Args:
        provider: AI provider (claude, antigravity, openai)
        tier: Model tier (low, med, high)

    Returns:
        Configured dspy.LM instance
    """
    model = get_model(provider=provider, tier=tier)
    return dspy.LM(
        api_base=getenv("CLIPROXY_API_BASE", "http://localhost:8317"),
        api_key=getenv("CLIPROXY_API_KEY"),
        model=model,
    )


# -----------------------------------------------------------------------------
# Workflow Module
# -----------------------------------------------------------------------------


class RPIWorkflow(dspy.Module):
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
        human_input_provider: HumanInputProvider | None = None,
        stage_configs: dict[Stage, StageConfig] | None = None,
        provider: Provider = Provider.Claude,
    ):
        """Initialize workflow with configuration.

        Args:
            provider: AI provider (default: Claude)
            stage_configs: Custom per-stage configs (merged with defaults)
            human_input_provider: HITL provider (default: ConsoleInputProvider)
        """
        super().__init__()
        self.configs = {**DEFAULT_STAGE_CONFIGS, **(stage_configs or {})}
        self.human_input = human_input_provider or ConsoleInputProvider()
        self.provider = provider

        # Build per-stage ReAct agents
        self._clarify_agent = self._build_clarify_agent()
        self._research_agent = self._build_research_agent()
        self._plan_agent = self._build_plan_agent()
        self._implement_agent = self._build_implement_agent()

    def _build_clarify_agent(self) -> dspy.ReAct:
        """Build clarify stage agent with HITL tool."""
        return dspy.ReAct(
            signature=ClarifySignature,
            tools=[clarify_goal, create_ask_human_tool(self.human_input)],
            max_iters=self.configs[Stage.CLARIFY].max_iters,
        )

    def _build_research_agent(self) -> dspy.ReAct:
        """Build research stage agent."""
        return dspy.ReAct(
            signature=ResearchSignature,
            tools=[research_codebase],
            max_iters=self.configs[Stage.RESEARCH].max_iters,
        )

    def _build_plan_agent(self) -> dspy.ReAct:
        """Build plan stage agent."""
        return dspy.ReAct(
            signature=PlanSignature,
            tools=[create_plan],
            max_iters=self.configs[Stage.PLAN].max_iters,
        )

    def _build_implement_agent(self) -> dspy.ReAct:
        """Build implement stage agent."""
        return dspy.ReAct(
            signature=ImplementSignature,
            tools=[implement_plan],
            max_iters=self.configs[Stage.IMPLEMENT].max_iters,
        )

    def _run_stage(
        self, *, stage: Stage, agent: dspy.ReAct, **kwargs
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
            agent=self._clarify_agent,
            objective=objective,
            stage=Stage.CLARIFY,
        )
        working_objective = clarified.get("clarified_objective") or objective

        # Stage 2: Research (deep codebase exploration)
        researched = self._run_stage(
            objective=working_objective,
            agent=self._research_agent,
            stage=Stage.RESEARCH,
        )

        # Stage 3: Plan (architectural reasoning)
        planned = self._run_stage(
            research_doc_path=researched.research_doc_path,
            objective=working_objective,
            agent=self._plan_agent,
            stage=Stage.PLAN,
        )

        # Stage 4: Implement (code generation)
        implemented = self._run_stage(
            plan_doc_path=planned.plan_doc_path,
            objective=working_objective,
            agent=self._implement_agent,
            stage=Stage.IMPLEMENT,
        )

        return dspy.Prediction(
            implementation_summary=implemented.implementation_summary,
            clarified_objective=clarified.clarified_objective,
            research_doc_path=researched.research_doc_path,
            plan_doc_path=planned.plan_doc_path,
            objective=working_objective,
        )
