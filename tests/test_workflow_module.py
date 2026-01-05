"""Tests for π.workflow_module (PiWorkflow DSPy Module)."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


class TestPiWorkflowInit:
    """Tests for PiWorkflow initialization."""

    @pytest.fixture
    def mock_dspy(self) -> Generator[MagicMock]:
        """Mock dspy module."""
        with patch("π.workflow.module.dspy") as mock:
            mock.ReAct.return_value = MagicMock()
            mock.context.return_value.__enter__ = MagicMock()
            mock.context.return_value.__exit__ = MagicMock()
            yield mock

    def test_creates_six_react_agents(self, mock_dspy: MagicMock):
        """Should create one ReAct agent per stage (6 total)."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # ReAct called 6 times (research, plan, review, iterate, implement, commit)
        assert mock_dspy.ReAct.call_count == 6

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

    def test_implement_agent_has_implement_plan_tool(self, mock_dspy: MagicMock):
        """Implement agent should include implement_plan tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the implement agent call (fifth one)
        implement_call = mock_dspy.ReAct.call_args_list[4]
        tools = implement_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "implement_plan" in tool_names

    def test_commit_agent_has_commit_changes_tool(self, mock_dspy: MagicMock):
        """Commit agent should include commit_changes tool."""
        from π.workflow import RPIWorkflow

        RPIWorkflow()

        # Find the commit agent call (sixth one)
        commit_call = mock_dspy.ReAct.call_args_list[5]
        tools = commit_call.kwargs.get("tools", [])

        tool_names = [t.__name__ for t in tools]
        assert "commit_changes" in tool_names


class TestPiWorkflowStageExecution:
    """Tests for PiWorkflow stage execution order."""

    @pytest.fixture
    def mock_workflow_deps(self) -> Generator[dict]:
        """Mock all workflow dependencies."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.research_codebase") as mock_research,
            patch("π.workflow.module.create_plan") as mock_plan,
            patch("π.workflow.module.review_plan") as mock_review,
            patch("π.workflow.module.iterate_plan") as mock_iterate,
            patch("π.workflow.module.implement_plan") as mock_implement,
            patch("π.workflow.module.commit_changes") as mock_commit,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
        ):
            # Setup ReAct mock to return predictions
            mock_react_instance = MagicMock()
            mock_dspy.ReAct.return_value = mock_react_instance
            mock_dspy.context.return_value.__enter__ = MagicMock()
            # Must return False to not suppress exceptions
            mock_dspy.context.return_value.__exit__ = MagicMock(return_value=False)
            mock_dspy.Prediction = MagicMock

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
                "implement": mock_implement,
                "commit": mock_commit,
                "get_lm": mock_get_lm,
                "get_extracted_path": mock_get_extracted_path,
                "react": mock_react_instance,
            }

    def test_forward_executes_all_stages(self, mock_workflow_deps: dict):
        """forward() should execute all six stages."""
        from π.workflow import RPIWorkflow

        # Each stage needs trajectory with proper tool_name for validation
        def make_result(**kwargs):
            result = MagicMock(**kwargs)
            # Empty trajectory (no validation needed for stages 1-3)
            result.trajectory = {}
            return result

        mock_workflow_deps["react"].side_effect = [
            make_result(research_doc_path="/path/research.md"),
            make_result(plan_doc_path="/path/plan.md"),
            make_result(plan_review_feedback="reviewed"),
            make_result(
                iteration_summary="iterated",
                changes_made="changes",
                trajectory={"tool_name_0": "iterate_plan"},
            ),
            make_result(
                implementation_status="success",
                files_changed="file1.py",
                trajectory={"tool_name_0": "implement_plan"},
            ),
            make_result(
                commit_result="abc123",
                trajectory={"tool_name_0": "commit_changes"},
            ),
        ]

        workflow = RPIWorkflow()
        workflow(objective="test task")

        # ReAct instance called 6 times (once per stage)
        assert mock_workflow_deps["react"].call_count == 6

    def test_passes_research_doc_to_plan(self, mock_workflow_deps: dict):
        """Plan stage should receive research_doc_path from context."""
        from π.workflow import RPIWorkflow

        calls = []
        stage_idx = [0]

        def capture_calls(**kwargs):
            calls.append(kwargs)
            idx = stage_idx[0]
            stage_idx[0] += 1
            result = MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="ok",
                iteration_summary="updated",
                changes_made="changes",
                implementation_status="success",
                files_changed="file1.py",
                commit_result="abc123",
            )
            # Add trajectory for stages that need validation
            if idx == 3:
                result.trajectory = {"tool_name_0": "iterate_plan"}
            elif idx == 4:
                result.trajectory = {"tool_name_0": "implement_plan"}
            elif idx == 5:
                result.trajectory = {"tool_name_0": "commit_changes"}
            else:
                result.trajectory = {}
            return result

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
        stage_idx = [0]

        def capture_calls(**kwargs):
            calls.append(kwargs)
            idx = stage_idx[0]
            stage_idx[0] += 1
            result = MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="ok",
                iteration_summary="updated",
                changes_made="changes",
                implementation_status="success",
                files_changed="file1.py",
                commit_result="abc123",
            )
            if idx == 3:
                result.trajectory = {"tool_name_0": "iterate_plan"}
            elif idx == 4:
                result.trajectory = {"tool_name_0": "implement_plan"}
            elif idx == 5:
                result.trajectory = {"tool_name_0": "commit_changes"}
            else:
                result.trajectory = {}
            return result

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
        stage_idx = [0]

        def capture_calls(**kwargs):
            calls.append(kwargs)
            idx = stage_idx[0]
            stage_idx[0] += 1
            result = MagicMock(
                research_doc_path="/path/research.md",
                plan_doc_path="/path/plan.md",
                plan_review_feedback="Found 2 issues: missing error handling",
                iteration_summary="Updated plan to address review feedback",
                changes_made="changes",
                implementation_status="success",
                files_changed="file1.py",
                commit_result="abc123",
            )
            if idx == 3:
                result.trajectory = {"tool_name_0": "iterate_plan"}
            elif idx == 4:
                result.trajectory = {"tool_name_0": "implement_plan"}
            elif idx == 5:
                result.trajectory = {"tool_name_0": "commit_changes"}
            else:
                result.trajectory = {}
            return result

        mock_workflow_deps["react"].side_effect = capture_calls

        workflow = RPIWorkflow()
        workflow(objective="test")

        # Iterate call (4th) should have plan_review_feedback from review
        iterate_call = calls[3]
        assert "plan_review_feedback" in iterate_call
        assert iterate_call["plan_review_feedback"] == (
            "Found 2 issues: missing error handling"
        )


class TestPiWorkflowModelSelection:
    """Tests for per-stage model selection."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict]:
        """Mock dependencies for model selection tests."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm") as mock_get_lm,
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.iterate_plan"),
            patch("π.workflow.module.implement_plan"),
            patch("π.workflow.module.commit_changes"),
        ):
            stage_idx = [0]

            def make_result(**_kwargs):
                idx = stage_idx[0]
                stage_idx[0] += 1
                result = MagicMock(
                    research_doc_path="/r.md",
                    plan_doc_path="/p.md",
                    plan_review_feedback="ok",
                    iteration_summary="updated",
                    changes_made="changes",
                    implementation_status="success",
                    files_changed="file1.py",
                    commit_result="abc123",
                )
                if idx == 3:
                    result.trajectory = {"tool_name_0": "iterate_plan"}
                elif idx == 4:
                    result.trajectory = {"tool_name_0": "implement_plan"}
                elif idx == 5:
                    result.trajectory = {"tool_name_0": "commit_changes"}
                else:
                    result.trajectory = {}
                return result

            mock_react = MagicMock(side_effect=make_result)
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock(return_value=False)

            # Mock get_extracted_path to return valid paths
            mock_get_extracted_path.side_effect = lambda doc_type: {
                "research": "/r.md",
                "plan": "/p.md",
            }.get(doc_type)

            yield {"dspy": mock_dspy, "get_lm": mock_get_lm}

    def test_uses_high_tier_for_main_stages(self, mock_deps: dict):
        """First 5 stages use high tier, commit uses low tier."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # get_lm called twice: once for stages 1-5 (high), once for commit (low)
        assert mock_deps["get_lm"].call_count == 2
        calls = mock_deps["get_lm"].call_args_list
        assert calls[0].args[1] == "high"  # First call for stages 1-5
        assert calls[1].args[1] == "low"  # Second call for commit stage

    def test_uses_dspy_context_for_model_override(self, mock_deps: dict):
        """Should use two dspy.context() calls - one for main stages, one for commit."""
        from π.workflow import RPIWorkflow

        workflow = RPIWorkflow()
        workflow(objective="test")

        # dspy.context called twice (stages 1-5 with HIGH, stage 6 with LOW)
        assert mock_deps["dspy"].context.call_count == 2


class TestPiWorkflowPrediction:
    """Tests for PiWorkflow output prediction."""

    @pytest.fixture
    def mock_deps(self) -> Generator[dict]:
        """Mock dependencies."""
        with (
            patch("π.workflow.module.dspy") as mock_dspy,
            patch("π.workflow.module.get_lm"),
            patch("π.workflow.module.get_extracted_path") as mock_get_extracted_path,
            patch("π.workflow.module.research_codebase"),
            patch("π.workflow.module.create_plan"),
            patch("π.workflow.module.review_plan"),
            patch("π.workflow.module.iterate_plan"),
            patch("π.workflow.module.implement_plan"),
            patch("π.workflow.module.commit_changes"),
        ):
            mock_react = MagicMock()
            mock_dspy.ReAct.return_value = mock_react
            mock_dspy.context.return_value.__enter__ = MagicMock()
            mock_dspy.context.return_value.__exit__ = MagicMock(return_value=False)

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

        # Create mocks with trajectory for validation
        def make_mock(trajectory=None, **kwargs):
            m = MagicMock(**kwargs)
            m.trajectory = trajectory or {}
            return m

        mock_deps["react"].side_effect = [
            make_mock(research_doc_path="/docs/research.md"),
            make_mock(plan_doc_path="/docs/plan.md"),
            make_mock(plan_review_feedback="Plan reviewed"),
            make_mock(
                iteration_summary="Plan updated",
                changes_made="changes",
                trajectory={"tool_name_0": "iterate_plan"},
            ),
            make_mock(
                implementation_status="success",
                files_changed="file1.py",
                trajectory={"tool_name_0": "implement_plan"},
            ),
            make_mock(
                commit_result="abc123",
                trajectory={"tool_name_0": "commit_changes"},
            ),
        ]

        workflow = RPIWorkflow()
        result = workflow(objective="original goal")

        assert hasattr(result, "research_doc_path")
        assert hasattr(result, "plan_doc_path")
        assert hasattr(result, "iteration_summary")
        assert hasattr(result, "implementation_status")
        assert hasattr(result, "files_changed")
        assert hasattr(result, "commit_result")
