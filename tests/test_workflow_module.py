"""Tests for π.workflow_module (PiWorkflow DSPy Module)."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


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

    def test_creates_four_react_agents(self, mock_dspy: MagicMock):
        """Should create one ReAct agent per active stage (4 total)."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # ReAct called 4 times (research, plan, review_plan, iterate_plan)
        assert mock_dspy.ReAct.call_count == 4

    def test_research_agent_has_research_tool(self, mock_dspy: MagicMock):
        """Research agent should include research_codebase tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the research agent call (first one)
        research_call = mock_dspy.ReAct.call_args_list[0]
        tools = research_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "research_codebase" in tool_names

    def test_iterate_agent_has_iterate_tool(self, mock_dspy: MagicMock):
        """Iterate agent should include iterate_plan tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the iterate agent call (fourth one)
        iterate_call = mock_dspy.ReAct.call_args_list[3]
        tools = iterate_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "iterate_plan" in tool_names

    def test_research_agent_has_ask_user_question_tool(self, mock_dspy: MagicMock):
        """Research agent should include ask_user_question tool for clarification."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the research agent call (first one)
        research_call = mock_dspy.ReAct.call_args_list[0]
        tools = research_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "ask_user_question" in tool_names

    def test_plan_agent_has_ask_user_question_tool(self, mock_dspy: MagicMock):
        """Plan agent should include ask_user_question tool for clarification."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the plan agent call (second one)
        plan_call = mock_dspy.ReAct.call_args_list[1]
        tools = plan_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "ask_user_question" in tool_names


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
            patch("π.workflow.module.iterate_plan") as mock_iterate,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
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

            # Mock get_extracted_path to return valid paths
            mock_get_extracted_path.side_effect = lambda doc_type: {
                "research": "/path/research.md",
                "plan": "/path/plan.md",
            }.get(doc_type)

            yield {
                "dspy": mock_dspy,
                "research": mock_research,
                "plan": mock_plan,
                "review": mock_review,
                "iterate": mock_iterate,
                "get_lm": mock_get_lm,
                "get_extracted_path": mock_get_extracted_path,
                "react": mock_react_instance,
            }

    def test_forward_executes_all_stages(self, mock_workflow_deps: dict):
        """forward() should execute all four stages."""
        from π.workflow import RPIWorkflow

        mock_workflow_deps["react"].return_value = MagicMock(
            research_doc_path="/path/research.md",
            plan_doc_path="/path/plan.md",
            plan_review_feedback="reviewed",
            iteration_summary="iterated",
        )

        workflow = RPIWorkflow()
        workflow(objective="test task")

        # ReAct instance called 4 times (once per stage)
        assert mock_workflow_deps["react"].call_count == 4

    def test_passes_research_doc_to_plan(self, mock_workflow_deps: dict):
        """Plan stage should receive research_doc_path from context."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="ok",
                iteration_summary="updated",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Plan call (2nd) should have research_doc_path from get_extracted_path
        plan_call = calls[1]
        assert "research_doc_path" in plan_call
        assert plan_call["research_doc_path"] == "/path/research.md"

    def test_passes_plan_doc_to_review(self, mock_workflow_deps: dict):
        """Review stage should receive plan_doc_path from context."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="ok",
                iteration_summary="updated",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Review call (3rd) should have plan_doc_path from get_extracted_path
        review_call = calls[2]
        assert "plan_doc_path" in review_call
        assert review_call["plan_doc_path"] == "/path/plan.md"

    def test_passes_review_feedback_to_iterate(self, mock_workflow_deps: dict):
        """Iterate stage should receive plan_review_feedback from review."""
        from π.workflow import RPIWorkflow

        calls = []

        def capture_calls(**kwargs):
            calls.append(kwargs)
            return MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="Found 2 issues: missing error handling, unclear scope",
                iteration_summary="Updated plan to address review feedback",
            )

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Iterate call (4th) should have plan_review_feedback from review
        iterate_call = calls[3]
        assert "plan_review_feedback" in iterate_call
        assert (
            iterate_call["plan_review_feedback"]
            == "Found 2 issues: missing error handling, unclear scope"
        )


class TestPiWorkflowModelSelection:
    """Tests for per-stage model selection."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict, None, None]:
        """Mock dependencies for model selection tests."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.iterate_plan"),
            patch("π.workflow.module.Path") as mock_path,
        ):
            mock_react = MagicMock()
            mock_react.return_value = MagicMock(
                research_doc_path="/r.md",
                plan_doc_path="/p.md",
                plan_review_feedback="ok",
                iteration_summary="updated",
            )
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            # Mock Path to always report files exist
            mock_path.return_value.exists.return_value = True

            # Mock get_extracted_path to return valid paths
            mock_get_extracted_path.side_effect = lambda doc_type: {
                "research": "/r.md",
                "plan": "/p.md",
            }.get(doc_type)

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
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.iterate_plan"),
            patch("π.workflow.module.Path") as mock_path,
        ):
            mock_react = MagicMock()
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock()

            # Mock Path to always report files exist
            mock_path.return_value.exists.return_value = True

            # Mock get_extracted_path to return valid paths
            mock_get_extracted_path.side_effect = lambda doc_type: {
                "research": "/docs/research.md",
                "plan": "/docs/plan.md",
            }.get(doc_type)

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
            MagicMock(plan_review_feedback="Plan reviewed"),
            MagicMock(iteration_summary="Plan updated"),
        ]

        workflow = RPIWorkflow()
        result = workflow(objective="original goal")

        assert hasattr(result, "research_doc_path")
        assert hasattr(result, "plan_doc_path")
        assert hasattr(result, "iteration_summary")
