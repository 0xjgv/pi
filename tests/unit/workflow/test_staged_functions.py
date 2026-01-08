"""Tests for staged workflow functions (stage_research, stage_design, stage_execute)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import dspy
import pytest

from π.workflow.staged import stage_design, stage_execute, stage_research
from π.workflow.types import PlanDocPath, ResearchDocPath, ResearchResult


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
        """Mock ExecutionContext with extracted_paths and extracted_results."""
        with patch("π.workflow.staged.get_ctx") as mock_get:
            ctx = MagicMock()
            ctx.extracted_paths = {}
            ctx.extracted_results = {}
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
            research_summaries=["Found existing patterns"],
            research_doc_paths=[research_doc],
            needs_implementation=True,
        )

        mock_lm = MagicMock()
        result = stage_research(objective="add logging", lm=mock_lm)

        # Verify agent was called with objective
        mock_react.assert_called_once_with(objective="add logging")
        # Summary is in the summaries list
        assert "Found existing patterns" in result.summaries

    def test_returns_early_when_no_implementation_needed(
        self, tmp_path, mock_context, mock_react
    ):
        """Should set needs_implementation=False when research indicates complete."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summaries=["Feature already exists"],
            research_doc_paths=[research_doc],
            needs_implementation=False,
        )

        result = stage_research(objective="add logging", lm=MagicMock())

        assert result.needs_implementation is False
        assert result.reason == "Agent determined no implementation needed"

    def test_extracts_research_doc_paths(self, tmp_path, mock_context, mock_react):
        """Should parse and validate doc paths from agent output."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summaries=["Research complete"],
            research_doc_paths=[research_doc],
            needs_implementation=True,
        )

        result = stage_research(objective="test", lm=MagicMock())

        assert len(result.research_docs) >= 1
        assert isinstance(result.research_docs[0], ResearchDocPath)
        assert "research" in result.research_docs[0].path

    def test_sets_context_stage_and_objective(self, tmp_path, mock_context, mock_react):
        """Should set current_stage and objective in ExecutionContext."""
        research_doc = _create_research_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            research_summaries=["Done"],
            research_doc_paths=[research_doc],
            needs_implementation=True,
        )

        stage_research(objective="implement feature", lm=MagicMock())

        assert mock_context.current_stage == "research"
        assert mock_context.objective == "implement feature"

    def test_raises_on_invalid_doc_path(self, mock_context, mock_react):
        """Should raise ValueError when agent returns invalid path."""
        mock_react.return_value = dspy.Prediction(
            research_summaries=["Done"],
            research_doc_paths=["/invalid/path.md"],
            needs_implementation=True,
        )

        with pytest.raises(ValueError, match="must be in"):
            stage_research(objective="test", lm=MagicMock())

    def test_aggregates_multiple_research_docs(
        self, tmp_path, mock_context, mock_react
    ):
        """Should aggregate research docs from context extracted_paths."""
        research_doc = _create_research_doc(tmp_path)

        # Create a second research doc
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        doc2 = research_dir / "2026-01-06-second-research.md"
        doc2.write_text("# Second Research\n\nMore content.")
        research_doc2 = str(doc2)

        # Pre-populate context with an additional research doc (simulating tool call)
        mock_context.extracted_paths = {"research": {research_doc2}}
        mock_context.extracted_results = {research_doc2: "Second research findings"}

        mock_react.return_value = dspy.Prediction(
            research_summaries=["Primary research findings"],
            research_doc_paths=[research_doc],
            needs_implementation=True,
        )

        result = stage_research(objective="test", lm=MagicMock())

        # Should have both docs
        assert len(result.research_docs) == 2
        paths = [doc.path for doc in result.research_docs]
        assert research_doc in paths
        assert research_doc2 in paths
        # Should have both summaries
        assert len(result.summaries) == 2


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

    def test_accepts_research_result(self, tmp_path, mock_context, mock_react):
        """Should accept full ResearchResult input with multi-doc support."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path=plan_doc,
        )

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Research findings about the codebase"],
            needs_implementation=True,
        )
        result = stage_design(
            research=research,
            objective="add feature",
            lm=MagicMock(),
        )

        assert result.summary == "Plan created"
        # Verify research path was stored in context for validation
        assert research_doc in mock_context.extracted_paths["research"]

    def test_extracts_plan_doc_path(self, tmp_path, mock_context, mock_react):
        """Should parse and validate plan path from agent output."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Design complete",
            plan_doc_path=plan_doc,
        )

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Research complete"],
            needs_implementation=True,
        )
        result = stage_design(
            research=research,
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

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Done"],
            needs_implementation=True,
        )
        stage_design(
            research=research,
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

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Research done"],
            needs_implementation=True,
        )
        with pytest.raises(ValueError, match="must be in"):
            stage_design(
                research=research,
                objective="test",
                lm=MagicMock(),
            )

    def test_agent_receives_exactly_declared_fields(
        self, tmp_path, mock_context, mock_react
    ):
        """Verify agent is called with exactly the fields in DesignSignature."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path=plan_doc,
        )

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Research summary text"],
            needs_implementation=True,
        )
        stage_design(
            research=research,
            objective="add feature",
            lm=MagicMock(),
        )

        # Verify agent was called with exactly the declared signature fields
        mock_react.assert_called_once()
        call_kwargs = mock_react.call_args[1]

        # Should have exactly these fields (matching DesignSignature inputs)
        expected_fields = {"objective", "research_doc_paths", "research_summary"}
        assert set(call_kwargs.keys()) == expected_fields
        assert call_kwargs["research_summary"] == "Research summary text"
        assert research_doc in call_kwargs["research_doc_paths"]

    def test_builds_combined_summary_from_multiple_docs(
        self, tmp_path, mock_context, mock_react
    ):
        """Should build combined summary when multiple research docs exist."""
        research_doc1 = _create_research_doc(tmp_path)

        # Create second research doc
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        doc2 = research_dir / "2026-01-06-second.md"
        doc2.write_text("# Second\n\nContent.")
        research_doc2 = str(doc2)

        plan_doc = _create_plan_doc(tmp_path)

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path=plan_doc,
        )

        research = ResearchResult(
            research_docs=[
                ResearchDocPath(path=research_doc1),
                ResearchDocPath(path=research_doc2),
            ],
            summaries=["First finding", "Second finding"],
            needs_implementation=True,
        )
        stage_design(
            research=research,
            objective="add feature",
            lm=MagicMock(),
        )

        call_kwargs = mock_react.call_args[1]

        # Both paths should be in the comma-separated string
        assert research_doc1 in call_kwargs["research_doc_paths"]
        assert research_doc2 in call_kwargs["research_doc_paths"]
        # Combined summary should include both findings
        assert "First finding" in call_kwargs["research_summary"]
        assert "Second finding" in call_kwargs["research_summary"]


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
        assert plan_doc in mock_context.extracted_paths["plan"]


class TestBuildResearchSummary:
    """Tests for _build_research_summary() function."""

    def test_empty_summaries_returns_placeholder(self):
        """Should return placeholder text when no summaries."""
        from π.workflow.staged import _build_research_summary

        result = _build_research_summary([])
        assert result == "(No research findings)"

    def test_single_summary_returns_as_is(self):
        """Should return single summary without formatting."""
        from π.workflow.staged import _build_research_summary

        result = _build_research_summary(["Authentication uses JWT"])
        assert result == "Authentication uses JWT"

    def test_multiple_summaries_formatted_with_headers(self):
        """Should format multiple summaries with headers and separators."""
        from π.workflow.staged import _build_research_summary

        summaries = ["First finding", "Second finding"]
        result = _build_research_summary(summaries)

        assert "### Research 1" in result
        assert "First finding" in result
        assert "### Research 2" in result
        assert "Second finding" in result
        assert "---" in result  # Separator between findings
