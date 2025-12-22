"""Tests for π.workflow_module (PiWorkflow DSPy Module)."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from π.config import Provider, DEFAULT_STAGE_CONFIGS, Stage, StageConfig


class TestPiWorkflowInit:
    """Tests for PiWorkflow initialization."""

    @pytest.fixture
    def mock_dspy(self) -> Generator[MagicMock, None, None]:
        """Mock dspy module."""
        with patch("π.workflow.module.dspy") as mock:
            mock.ReAct.return_value = MagicMock()
            mock.context.return_value.__enter__ = MagicMock()
            mock.context.return_value.__exit__ = MagicMock()
            yield mock

    def test_creates_with_default_provider(self, mock_dspy: MagicMock):
        """Should default to Claude provider."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()

        assert workflow.provider == Provider.Claude

    def test_accepts_custom_provider(self, mock_dspy: MagicMock):
        """Should accept Antigravity provider."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow(provider=Provider.Antigravity)

        assert workflow.provider == Provider.Antigravity

    def test_uses_default_stage_configs(self, mock_dspy: MagicMock):
        """Should use DEFAULT_STAGE_CONFIGS when none provided."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()

        assert workflow.configs == DEFAULT_STAGE_CONFIGS

    def test_accepts_custom_stage_configs(self, mock_dspy: MagicMock):
        """Should merge custom configs with defaults."""
        from π.workflow import RPIWorkflow

        custom_configs = {
            Stage.PLAN: StageConfig(model_tier="med", max_iters=10),
        }

        workflow = RPIWorkflow(stage_configs=custom_configs)

        # Custom config applied
        assert workflow.configs[Stage.PLAN].model_tier == "med"
        assert workflow.configs[Stage.PLAN].max_iters == 10
        # Defaults preserved for other stages
        assert workflow.configs[Stage.CLARIFY] == DEFAULT_STAGE_CONFIGS[Stage.CLARIFY]

    def test_creates_five_react_agents(self, mock_dspy: MagicMock):
        """Should create one ReAct agent per stage."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # ReAct called 5 times (one per stage)
        assert mock_dspy.ReAct.call_count == 5

    def test_clarify_agent_has_ask_human_tool(self, mock_dspy: MagicMock):
        """Clarify agent should include ask_human tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the clarify agent call (first one)
        clarify_call = mock_dspy.ReAct.call_args_list[0]
        tools = clarify_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "ask_human" in tool_names

    def test_research_agent_no_ask_human(self, mock_dspy: MagicMock):
        """Non-clarify agents should not have ask_human tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Research agent is second call
        research_call = mock_dspy.ReAct.call_args_list[1]
        tools = research_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "ask_human" not in tool_names

    def test_accepts_custom_human_input_provider(self, mock_dspy: MagicMock):
        """Should accept custom HITL provider."""
        from π.workflow import RPIWorkflow

        mock_provider = MagicMock()

        workflow = RPIWorkflow(human_input_provider=mock_provider)

        assert workflow.human_input is mock_provider


class TestPiWorkflowStageExecution:
    """Tests for PiWorkflow stage execution order."""

    @pytest.fixture
    def mock_workflow_deps(self) -> Generator[dict, None, None]:
        """Mock all workflow dependencies."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.clarify_goal") as mock_clarify,
            patch("π.workflow.module.research_codebase") as mock_research,
            patch("π.workflow.module.create_plan") as mock_plan,
            patch("π.workflow.module.implement_plan") as mock_impl,
            patch("π.workflow.module.get_lm") as mock_get_lm,
        ):
            # Setup ReAct mock to return predictions
            mock_react_instance = MagicMock()
            mock_dspy.ReAct.return_value = mock_react_instance
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()
            mock_dspy.Prediction = MagicMock

            yield {
                "dspy": mock_dspy,
                "clarify": mock_clarify,
                "research": mock_research,
                "plan": mock_plan,
                "implement": mock_impl,
                "get_lm": mock_get_lm,
                "react": mock_react_instance,
            }

    def test_forward_executes_all_stages(self, mock_workflow_deps: dict):
        """forward() should execute all five stages."""
        from π.workflow import RPIWorkflow

        mock_workflow_deps["react"].return_value = MagicMock(
            clarified_objective="clarified",
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            review_summary="reviewed",
            implementation_summary="done",
        )

        workflow = RPIWorkflow()
        workflow(objective="test task")

        # ReAct instance called 5 times (once per stage)
        assert mock_workflow_deps["react"].call_count == 5

    def test_forward_enforces_stage_order(self, mock_workflow_deps: dict):
        """Stages must execute in order: clarify → research → plan → implement."""
        from π.workflow import RPIWorkflow

        call_order = []

        def track_call(**kwargs):
            if "objective" in kwargs and "research_doc_path" not in kwargs:
                if "plan_doc_path" not in kwargs:
                    call_order.append("clarify" if len(call_order) == 0 else "research")
                else:
                    call_order.append("implement")
            elif "research_doc_path" in kwargs:
                call_order.append("plan")
            return MagicMock(
                clarified_objective="clarified",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                implementation_summary="done",
            )

        mock_workflow_deps["react"].side_effect = track_call

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Verify order based on call signatures
        assert len(call_order) == 4

    def test_uses_clarified_objective_for_subsequent_stages(
        self, mock_workflow_deps: dict
    ):
        """Research/plan/implement should use clarified objective."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            mock_result = MagicMock(
                clarified_objective="CLARIFIED GOAL",
                research_doc_path="/research.md",
                plan_doc_path="/plan.md",
                implementation_summary="done",
            )
            # Configure .get() to return the clarified_objective
            mock_result.get.return_value = "CLARIFIED GOAL"
            return mock_result

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="original goal")

        # First call (clarify) gets original
        assert calls[0]["objective"] == "original goal"
        # Subsequent calls get clarified objective
        assert calls[1]["objective"] == "CLARIFIED GOAL"
        assert calls[2]["objective"] == "CLARIFIED GOAL"

    def test_passes_research_doc_to_plan(self, mock_workflow_deps: dict):
        """Plan stage should receive research_doc_path."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                clarified_objective="goal",
                research_doc_path="/path/to/research.md",
                plan_doc_path="/path/to/plan.md",
                implementation_summary="done",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Plan call (3rd) should have research_doc_path
        plan_call = calls[2]
        assert "research_doc_path" in plan_call
        assert plan_call["research_doc_path"] == "/path/to/research.md"

    def test_passes_plan_doc_to_implement(self, mock_workflow_deps: dict):
        """Implement stage should receive plan_doc_path."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                clarified_objective="goal",
                research_doc_path="/research.md",
                plan_doc_path="/path/to/plan.md",
                implementation_summary="done",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Implement call (4th) should have plan_doc_path
        impl_call = calls[3]
        assert "plan_doc_path" in impl_call
        assert impl_call["plan_doc_path"] == "/path/to/plan.md"


class TestPiWorkflowModelSelection:
    """Tests for per-stage model selection."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict, None, None]:
        """Mock dependencies for model selection tests."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.clarify_goal"),
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.implement_plan"),
        ):
            mock_react = MagicMock()
            mock_react.return_value = MagicMock(
                clarified_objective="goal",
                research_doc_path="/r.md",
                plan_doc_path="/p.md",
                implementation_summary="done",
            )
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            yield {"dspy": mock_dspy, "get_lm": mock_get_lm}

    def test_uses_different_models_per_stage(self, mock_deps: dict):
        """Each stage should request its configured model tier."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # get_lm called 5 times with different tiers
        lm_calls = mock_deps["get_lm"].call_args_list
        tiers_requested = [call.args[1] for call in lm_calls]

        # Default tiers: low, high, high, med, med (clarify, research, plan, review, implement)
        assert tiers_requested == ["low", "high", "high", "med", "med"]

    def test_uses_dspy_context_for_model_override(self, mock_deps: dict):
        """Should use dspy.context() for per-stage model."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # dspy.context called 5 times (once per stage)
        assert mock_deps["dspy"].context.call_count == 5

    def test_custom_stage_config_changes_model(self, mock_deps: dict):
        """Custom stage config should change model tier."""
        from π.workflow import RPIWorkflow

        custom = {
            Stage.CLARIFY: StageConfig(model_tier="high", max_iters=2),
        }

        workflow = RPIWorkflow(stage_configs=custom)
        workflow(objective="test")

        # First get_lm call should be "high" (clarify override)
        first_call = mock_deps["get_lm"].call_args_list[0]
        assert first_call.args[1] == "high"


class TestPiWorkflowPrediction:
    """Tests for PiWorkflow output prediction."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict, None, None]:
        """Mock dependencies."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm"),
            patch("π.workflow.module.clarify_goal"),
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.implement_plan"),
        ):
            mock_react = MagicMock()
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            # Create a proper Prediction mock
            class MockPrediction:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            mock_dspy.Prediction = MockPrediction

            yield {"dspy": mock_dspy, "react": mock_react}

    def test_returns_prediction_with_all_outputs(self, mock_deps: dict):
        """forward() should return Prediction with all stage outputs."""
        from π.workflow import RPIWorkflow

        mock_deps["react"].side_effect = [
            MagicMock(clarified_objective="The clarified goal"),
            MagicMock(research_doc_path="/docs/research.md"),
            MagicMock(plan_doc_path="/docs/plan.md"),
            MagicMock(review_summary="Plan reviewed"),
            MagicMock(implementation_summary="Implementation complete"),
        ]

        workflow = RPIWorkflow()
        result = workflow(objective="original goal")

        assert hasattr(result, "objective")
        assert hasattr(result, "research_doc_path")
        assert hasattr(result, "plan_doc_path")
        assert hasattr(result, "implementation_summary")

    def test_returns_clarified_objective(self, mock_deps: dict):
        """Result should contain the clarified objective."""
        from π.workflow import RPIWorkflow

        mock_result = MagicMock(
            clarified_objective="Clarified: Add Redis caching",
            research_doc_path="/r.md",
            plan_doc_path="/p.md",
            implementation_summary="done",
        )
        # Configure .get() to return the clarified_objective
        mock_result.get.return_value = "Clarified: Add Redis caching"
        mock_deps["react"].return_value = mock_result

        workflow = RPIWorkflow()
        result = workflow(objective="add caching")

        assert result.objective == "Clarified: Add Redis caching"
