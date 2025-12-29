"""Tests for π.workflow_module (PiWorkflow DSPy Module)."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from π.config import Provider


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

    def test_creates_three_react_agents(self, mock_dspy: MagicMock):
        """Should create one ReAct agent per active stage (3 total)."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # ReAct called 3 times (research, plan, review_plan)
        assert mock_dspy.ReAct.call_count == 3

    def test_research_agent_has_research_tool(self, mock_dspy: MagicMock):
        """Research agent should include research_codebase tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the research agent call (first one)
        research_call = mock_dspy.ReAct.call_args_list[0]
        tools = research_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "research_codebase" in tool_names

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
            patch("π.workflow.module.research_codebase") as mock_research,
            patch("π.workflow.module.create_plan") as mock_plan,
            patch("π.workflow.module.review_plan") as mock_review,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.Path") as mock_path,
        ):
            # Setup ReAct mock to return predictions
            mock_react_instance = MagicMock()
            mock_dspy.ReAct.return_value = mock_react_instance
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()
            mock_dspy.Prediction = MagicMock

            # Mock Path to always report files exist
            mock_path.return_value.exists.return_value = True

            yield {
                "dspy": mock_dspy,
                "research": mock_research,
                "plan": mock_plan,
                "review": mock_review,
                "get_lm": mock_get_lm,
                "react": mock_react_instance,
            }

    def test_forward_executes_all_stages(self, mock_workflow_deps: dict):
        """forward() should execute all three stages."""
        from π.workflow import RPIWorkflow

        mock_workflow_deps["react"].return_value = MagicMock(
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            review_summary="reviewed",
        )

        workflow = RPIWorkflow()
        workflow(objective="test task")

        # ReAct instance called 3 times (once per stage)
        assert mock_workflow_deps["react"].call_count == 3

    def test_passes_research_doc_to_plan(self, mock_workflow_deps: dict):
        """Plan stage should receive research_doc_path."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                research_doc_path="/path/to/research.md",
                plan_doc_path="/path/to/plan.md",
                review_summary="ok",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Plan call (2nd) should have research_doc_path
        plan_call = calls[1]
        assert "research_doc_path" in plan_call
        assert plan_call["research_doc_path"] == "/path/to/research.md"

    def test_passes_plan_doc_to_review(self, mock_workflow_deps: dict):
        """Review stage should receive plan_doc_path."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                research_doc_path="/research.md",
                plan_doc_path="/path/to/plan.md",
                review_summary="ok",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Review call (3rd) should have plan_doc_path
        review_call = calls[2]
        assert "plan_doc_path" in review_call
        assert review_call["plan_doc_path"] == "/path/to/plan.md"


class TestPiWorkflowModelSelection:
    """Tests for per-stage model selection."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict, None, None]:
        """Mock dependencies for model selection tests."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.Path") as mock_path,
        ):
            mock_react = MagicMock()
            mock_react.return_value = MagicMock(
                research_doc_path="/r.md",
                plan_doc_path="/p.md",
                review_summary="ok",
            )
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            # Mock Path to always report files exist
            mock_path.return_value.exists.return_value = True

            yield {"dspy": mock_dspy, "get_lm": mock_get_lm}

    def test_uses_high_tier_for_all_stages(self, mock_deps: dict):
        """All stages use high tier model (single LM call)."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # get_lm called once with high tier (shared across all stages)
        mock_deps["get_lm"].assert_called_once()
        call_args = mock_deps["get_lm"].call_args
        assert call_args.args[1] == "high"

    def test_uses_dspy_context_for_model_override(self, mock_deps: dict):
        """Should use single dspy.context() for all stages."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # dspy.context called once (wraps all stages)
        assert mock_deps["dspy"].context.call_count == 1


class TestPiWorkflowPrediction:
    """Tests for PiWorkflow output prediction."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict, None, None]:
        """Mock dependencies."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm"),
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.Path") as mock_path,
        ):
            mock_react = MagicMock()
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            # Mock Path to always report files exist
            mock_path.return_value.exists.return_value = True

            # Create a proper Prediction mock
            class MockPrediction:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            mock_dspy.Prediction = MockPrediction

            yield {"dspy": mock_dspy, "react": mock_react}

    def test_returns_prediction_with_all_outputs(self, mock_deps: dict):
        """forward() should return Prediction with stage outputs."""
        from π.workflow import RPIWorkflow

        mock_deps["react"].side_effect = [
            MagicMock(research_doc_path="/docs/research.md"),
            MagicMock(plan_doc_path="/docs/plan.md"),
            MagicMock(review_summary="Plan reviewed"),
        ]

        workflow = RPIWorkflow()
        result = workflow(objective="original goal")

        assert hasattr(result, "research_doc_path")
        assert hasattr(result, "plan_doc_path")
