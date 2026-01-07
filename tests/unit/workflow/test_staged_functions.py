"""Tests for staged workflow functions (stage_research, stage_design, stage_execute)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import dspy
import pytest

from π.workflow.staged import stage_design, stage_execute, stage_research
from π.workflow.types import PlanDocPath, ResearchDocPath


def _create_research_doc(tmp_path: Path) -> str:
    """Helper to create a valid research document."""
    research_dir = tmp_path / "thoughts" / "shared" / "research"
    research_dir.mkdir(parents=True)
    doc = research_dir / "2026-01-05-test-research.md"
    doc.write_text("# Research\n\nResearch content.")
    return str(doc)


def _create_plan_doc(tmp_path: Path) -> str:
    """Helper to create a valid plan document."""
    plan_dir = tmp_path / "thoughts" / "shared" / "plans"
    plan_dir.mkdir(parents=True)
    doc = plan_dir / "2026-01-05-test-plan.md"
    doc.write_text("# Plan\n\nPlan content.")
    return str(doc)


class TestStageResearch:
    """Tests for stage_research() function."""

    @pytest.fixture
    def mock_context(self):
        """Mock ExecutionContext."""
        with patch("π.workflow.staged.get_ctx") as mock_get:
            ctx = MagicMock()
            ctx.extracted_paths = {}
            mock_get.return_value = ctx
            yield ctx

    @pytest.fixture
    def mock_react(self):
        """Mock dspy.ReAct agent."""
        with patch("π.workflow.staged.dspy.ReAct") as mock_class:
            mock_agent = MagicMock()
            mock_class.return_value = mock_agent
            yield mock_agent

    def test_invokes_react_agent_with_objective(
        self, tmp_path, mock_context, mock_react
    ):
        """Should call ReAct agent with research objective."""
        research_doc = _create_research_doc(tmp_path)

        # Configure mock agent response
        mock_react.return_value = dspy.Prediction(
            research_summary="Found existing patterns",
            research_doc_path=research_doc,
            needs_implementation=True,
        )

        mock_lm = MagicMock()
        result = stage_research(objective="add logging", lm=mock_lm)

        # Verify agent was called with objective
        mock_react.assert_called_once_with(objective="add logging")
        assert result.summary == "Found existing patterns"

    def test_returns_early_when_no_implementation_needed(
        self, tmp_path, mock_context, mock_react
    ):
        """Should set needs_implementation=False when research indicates complete."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summary="Feature already exists",
            research_doc_path=research_doc,
            needs_implementation=False,
        )

        result = stage_research(objective="add logging", lm=MagicMock())

        assert result.needs_implementation is False
        assert result.reason == "Agent determined no implementation needed"

    def test_extracts_research_doc_path(self, tmp_path, mock_context, mock_react):
        """Should parse and validate doc path from agent output."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summary="Research complete",
            research_doc_path=research_doc,
            needs_implementation=True,
        )

        result = stage_research(objective="test", lm=MagicMock())

        assert isinstance(result.research_doc, ResearchDocPath)
        assert "research" in result.research_doc.path

    def test_sets_context_stage_and_objective(self, tmp_path, mock_context, mock_react):
        """Should set current_stage and objective in ExecutionContext."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summary="Done",
            research_doc_path=research_doc,
            needs_implementation=True,
        )

        stage_research(objective="implement feature", lm=MagicMock())

        assert mock_context.current_stage == "research"
        assert mock_context.objective == "implement feature"

    def test_raises_on_invalid_doc_path(self, mock_context, mock_react):
        """Should raise ValueError when agent returns invalid path."""
        mock_react.return_value = dspy.Prediction(
            research_summary="Done",
            research_doc_path="/invalid/path.md",
            needs_implementation=True,
        )

        with pytest.raises(ValueError, match="must be in"):
            stage_research(objective="test", lm=MagicMock())


class TestStageDesign:
    """Tests for stage_design() function."""

    @pytest.fixture
    def mock_context(self):
        """Mock ExecutionContext."""
        with patch("π.workflow.staged.get_ctx") as mock_get:
            ctx = MagicMock()
            ctx.extracted_paths = {}
            mock_get.return_value = ctx
            yield ctx

    @pytest.fixture
    def mock_react(self):
        """Mock dspy.ReAct agent."""
        with patch("π.workflow.staged.dspy.ReAct") as mock_class:
            mock_agent = MagicMock()
            mock_class.return_value = mock_agent
            yield mock_agent

    def test_requires_research_doc_path(self, tmp_path, mock_context, mock_react):
        """Should accept validated ResearchDocPath input."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path=plan_doc,
        )

        research_path = ResearchDocPath(path=research_doc)
        result = stage_design(
            research_doc=research_path,
            objective="add feature",
            lm=MagicMock(),
        )

        assert result.summary == "Plan created"
        # Verify research path was stored in context
        assert mock_context.extracted_paths["research"] == research_doc

    def test_extracts_plan_doc_path(self, tmp_path, mock_context, mock_react):
        """Should parse and validate plan path from agent output."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Design complete",
            plan_doc_path=plan_doc,
        )

        research_path = ResearchDocPath(path=research_doc)
        result = stage_design(
            research_doc=research_path,
            objective="test",
            lm=MagicMock(),
        )

        assert isinstance(result.plan_doc, PlanDocPath)
        assert "plans" in result.plan_doc.path

    def test_sets_context_stage(self, tmp_path, mock_context, mock_react):
        """Should set current_stage to 'design' in ExecutionContext."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Done",
            plan_doc_path=plan_doc,
        )

        research_path = ResearchDocPath(path=research_doc)
        stage_design(
            research_doc=research_path,
            objective="implement",
            lm=MagicMock(),
        )

        assert mock_context.current_stage == "design"

    def test_raises_on_invalid_plan_path(self, tmp_path, mock_context, mock_react):
        """Should raise ValueError when agent returns invalid plan path."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Done",
            plan_doc_path="/invalid/plan.md",
        )

        research_path = ResearchDocPath(path=research_doc)
        with pytest.raises(ValueError, match="must be in"):
            stage_design(
                research_doc=research_path,
                objective="test",
                lm=MagicMock(),
            )


class TestStageExecute:
    """Tests for stage_execute() function."""

    @pytest.fixture
    def mock_context(self):
        """Mock ExecutionContext."""
        with patch("π.workflow.staged.get_ctx") as mock_get:
            ctx = MagicMock()
            ctx.extracted_paths = {}
            mock_get.return_value = ctx
            yield ctx

    @pytest.fixture
    def mock_react(self):
        """Mock dspy.ReAct agent."""
        with patch("π.workflow.staged.dspy.ReAct") as mock_class:
            mock_agent = MagicMock()
            mock_class.return_value = mock_agent
            yield mock_agent

    def test_parses_files_changed(self, tmp_path, mock_context, mock_react):
        """Should parse comma-separated file list from agent output."""
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="src/main.py, src/utils.py, tests/test_main.py",
            commit_hash="abc1234",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="implement feature",
            lm=MagicMock(),
        )

        expected = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        assert result.files_changed == expected

    def test_handles_none_commit_hash(self, tmp_path, mock_context, mock_react):
        """Should convert 'none' string to None for commit_hash."""
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            status="partial",
            files_changed="file.py",
            commit_hash="none",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.commit_hash is None
        assert result.status == "partial"

    def test_preserves_actual_commit_hash(self, tmp_path, mock_context, mock_react):
        """Should preserve actual commit hash when not 'none'."""
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="file.py",
            commit_hash="def5678",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.commit_hash == "def5678"

    def test_handles_empty_files_changed(self, tmp_path, mock_context, mock_react):
        """Should handle empty files_changed string."""
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            status="failed",
            files_changed="",
            commit_hash="none",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.files_changed == []

    def test_sets_context_stage(self, tmp_path, mock_context, mock_react):
        """Should set current_stage to 'execute' in ExecutionContext."""
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="file.py",
            commit_hash="abc1234",
        )

        plan_path = PlanDocPath(path=plan_doc)
        stage_execute(
            plan_doc=plan_path,
            objective="implement",
            lm=MagicMock(),
        )

        assert mock_context.current_stage == "execute"
        assert mock_context.extracted_paths["plan"] == plan_doc
