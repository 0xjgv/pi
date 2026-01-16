"""Tests for staged workflow functions (stage_research, stage_design, stage_execute)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import dspy
import pytest

from π.workflow.context import Command
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

        # Set up context with tracked paths and summaries (simulating tool calls)
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Found existing patterns"}

        # Configure mock agent response (LM output is now ignored for paths/summaries)
        mock_react.return_value = dspy.Prediction(
            research_summaries=["LM summary (ignored)"],
            research_doc_paths=["invalid/path.md"],  # Ignored
            needs_implementation=True,
            task_status="complete",
        )

        mock_lm = MagicMock()
        result = stage_research(objective="add logging", lm=mock_lm)

        # Verify agent was called with objective
        mock_react.assert_called_once_with(objective="add logging")
        # Summary comes from tracked context, not LM output
        assert "Found existing patterns" in result.summaries

    def test_returns_early_when_no_implementation_needed(
        self, tmp_path, mock_context, mock_react
    ):
        """Should set needs_implementation=False when research indicates complete."""
        research_doc = _create_research_doc(tmp_path)

        # Set up context with tracked paths
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Feature already exists"}

        mock_react.return_value = dspy.Prediction(
            research_summaries=["LM summary (ignored)"],
            research_doc_paths=["ignored"],
            needs_implementation=False,
            task_status="complete",
        )

        result = stage_research(objective="add logging", lm=MagicMock())

        assert result.needs_implementation is False
        assert result.reason == "Agent determined no implementation needed"

    def test_extracts_research_doc_paths(self, tmp_path, mock_context, mock_react):
        """Should use tracked doc paths from context, not LM output."""
        research_doc = _create_research_doc(tmp_path)

        # Set up context with tracked paths
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Research complete"}

        mock_react.return_value = dspy.Prediction(
            research_summaries=["LM summary (ignored)"],
            research_doc_paths=["ignored"],
            needs_implementation=True,
            task_status="complete",
        )

        result = stage_research(objective="test", lm=MagicMock())

        assert len(result.research_docs) == 1
        assert isinstance(result.research_docs[0], ResearchDocPath)
        assert "research" in result.research_docs[0].path

    def test_sets_context_stage_and_objective(self, tmp_path, mock_context, mock_react):
        """Should set current_stage and objective in ExecutionContext."""
        research_doc = _create_research_doc(tmp_path)

        # Set up context with tracked paths
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Done"}

        mock_react.return_value = dspy.Prediction(
            research_summaries=["ignored"],
            research_doc_paths=["ignored"],
            needs_implementation=True,
            task_status="complete",
        )

        stage_research(objective="implement feature", lm=MagicMock())

        assert mock_context.current_stage == "research"
        assert mock_context.objective == "implement feature"

    def test_ignores_invalid_lm_doc_paths(self, tmp_path, mock_context, mock_react):
        """Should ignore invalid paths from LM output and use only tracked paths."""
        research_doc = _create_research_doc(tmp_path)

        # Set up context with valid tracked path
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Valid research"}

        # LM returns invalid path - should be ignored
        mock_react.return_value = dspy.Prediction(
            research_summaries=["LM summary"],
            research_doc_paths=["/invalid/path.md"],
            needs_implementation=True,
            task_status="complete",
        )

        # Should NOT raise - LM paths are ignored
        result = stage_research(objective="test", lm=MagicMock())
        assert len(result.research_docs) == 1
        assert result.research_docs[0].path == research_doc

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

        # Pre-populate context with both research docs (simulating tool calls)
        mock_context.extracted_paths = {
            Command.RESEARCH_CODEBASE: {research_doc, research_doc2}
        }
        mock_context.extracted_results = {
            research_doc: "Primary research findings",
            research_doc2: "Second research findings",
        }

        mock_react.return_value = dspy.Prediction(
            research_summaries=["LM summary (ignored)"],
            research_doc_paths=["ignored"],
            needs_implementation=True,
            task_status="complete",
        )

        result = stage_research(objective="test", lm=MagicMock())

        # Should have both docs from context
        assert len(result.research_docs) == 2
        paths = [doc.path for doc in result.research_docs]
        assert research_doc in paths
        assert research_doc2 in paths
        # Should have both summaries from context
        assert len(result.summaries) == 2

    def test_handles_needs_clarification_status(
        self, tmp_path, mock_context, mock_react
    ):
        """Should set reason when agent signals needs_clarification."""
        research_doc = _create_research_doc(tmp_path)

        # Set up context with tracked paths
        mock_context.extracted_paths = {Command.RESEARCH_CODEBASE: {research_doc}}
        mock_context.extracted_results = {research_doc: "Partial findings"}

        mock_react.return_value = dspy.Prediction(
            research_summaries=["ignored"],
            research_doc_paths=["ignored"],
            needs_implementation=True,
            task_status="needs_clarification",
        )

        result = stage_research(objective="test", lm=MagicMock())

        assert result.needs_implementation is True
        assert result.reason == "Agent requires user clarification"


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

        # Set up context with tracked plan path (simulating tool call)
        mock_context.extracted_paths = {Command.CREATE_PLAN: {plan_doc}}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path="ignored",  # LM output ignored
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
        assert research_doc in mock_context.extracted_paths[Command.RESEARCH_CODEBASE]

    def test_extracts_plan_doc_path(self, tmp_path, mock_context, mock_react):
        """Should use tracked plan path from context, not LM output."""
        research_doc = _create_research_doc(tmp_path)
        plan_doc = _create_plan_doc(tmp_path)

        # Set up context with tracked plan path
        mock_context.extracted_paths = {Command.CREATE_PLAN: {plan_doc}}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Design complete",
            plan_doc_path="ignored",  # LM output ignored
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

        # Set up context with tracked plan path
        mock_context.extracted_paths = {Command.CREATE_PLAN: {plan_doc}}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Done",
            plan_doc_path="ignored",
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

    def test_raises_when_no_plan_created(self, tmp_path, mock_context, mock_react):
        """Should raise ValueError when no plan is tracked in context."""
        research_doc = _create_research_doc(tmp_path)

        # No plan in context
        mock_context.extracted_paths = {}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Done",
            plan_doc_path="/invalid/plan.md",  # Ignored
        )

        research = ResearchResult(
            research_docs=[ResearchDocPath(path=research_doc)],
            summaries=["Research done"],
            needs_implementation=True,
        )
        with pytest.raises(ValueError, match="did not produce a plan"):
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

        # Set up context with tracked plan path
        mock_context.extracted_paths = {Command.CREATE_PLAN: {plan_doc}}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path="ignored",
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
        expected_fields = {"objective", "research_doc_paths", "research_summaries"}
        assert set(call_kwargs.keys()) == expected_fields
        assert call_kwargs["research_summaries"] == ["Research summary text"]
        assert research_doc in call_kwargs["research_doc_paths"]

    def test_passes_multiple_research_docs_as_lists(
        self, tmp_path, mock_context, mock_react
    ):
        """Should pass research paths and summaries as lists."""
        research_doc1 = _create_research_doc(tmp_path)

        # Create second research doc
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        doc2 = research_dir / "2026-01-06-second.md"
        doc2.write_text("# Second\n\nContent.")
        research_doc2 = str(doc2)

        plan_doc = _create_plan_doc(tmp_path)

        # Set up context with tracked plan path
        mock_context.extracted_paths = {Command.CREATE_PLAN: {plan_doc}}

        mock_react.return_value = dspy.Prediction(
            plan_summary="Plan created",
            plan_doc_path="ignored",
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

        # Both paths should be in the list
        assert research_doc1 in call_kwargs["research_doc_paths"]
        assert research_doc2 in call_kwargs["research_doc_paths"]
        # Summaries should be passed as list
        assert call_kwargs["research_summaries"] == ["First finding", "Second finding"]


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

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess.run for git commands."""
        with patch("π.workflow.staged.subprocess.run") as mock_run:
            yield mock_run

    def test_gets_files_changed_from_git(
        self, tmp_path, mock_context, mock_react, mock_subprocess
    ):
        """Should get files_changed from git diff, not LM output."""
        plan_doc = _create_plan_doc(tmp_path)

        # Mock git diff --name-only output
        mock_subprocess.side_effect = [
            MagicMock(
                returncode=0,
                stdout="src/main.py\nsrc/utils.py\ntests/test_main.py\n",
            ),
            MagicMock(returncode=0, stdout="abc1234"),  # git rev-parse
        ]

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="ignored",  # LM output ignored
            commit_hash="ignored",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="implement feature",
            lm=MagicMock(),
        )

        expected = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        assert result.files_changed == expected

    def test_gets_commit_hash_from_git(
        self, tmp_path, mock_context, mock_react, mock_subprocess
    ):
        """Should get commit_hash from git rev-parse, not LM output."""
        plan_doc = _create_plan_doc(tmp_path)

        # Mock git commands
        mock_subprocess.side_effect = [
            MagicMock(returncode=0, stdout="file.py\n"),  # git diff
            MagicMock(returncode=0, stdout="def5678"),  # git rev-parse
        ]

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="ignored",
            commit_hash="ignored",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.commit_hash == "def5678"

    def test_handles_git_failure(
        self, tmp_path, mock_context, mock_react, mock_subprocess
    ):
        """Should handle git command failures gracefully."""
        plan_doc = _create_plan_doc(tmp_path)

        # Mock git commands failing
        mock_subprocess.side_effect = [
            MagicMock(returncode=1, stdout=""),  # git diff failed
            MagicMock(returncode=1, stdout=""),  # git rev-parse failed
        ]

        mock_react.return_value = dspy.Prediction(
            status="partial",
            files_changed="ignored",
            commit_hash="ignored",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.files_changed == []
        assert result.commit_hash is None
        assert result.status == "partial"

    def test_handles_empty_git_diff(
        self, tmp_path, mock_context, mock_react, mock_subprocess
    ):
        """Should handle empty git diff output."""
        plan_doc = _create_plan_doc(tmp_path)

        # Mock empty git diff output
        mock_subprocess.side_effect = [
            MagicMock(returncode=0, stdout=""),  # No changes
            MagicMock(returncode=0, stdout="abc1234"),
        ]

        mock_react.return_value = dspy.Prediction(
            status="failed",
            files_changed="ignored",
            commit_hash="ignored",
        )

        plan_path = PlanDocPath(path=plan_doc)
        result = stage_execute(
            plan_doc=plan_path,
            objective="test",
            lm=MagicMock(),
        )

        assert result.files_changed == []

    def test_sets_context_stage(
        self, tmp_path, mock_context, mock_react, mock_subprocess
    ):
        """Should set current_stage to 'execute' in ExecutionContext."""
        plan_doc = _create_plan_doc(tmp_path)

        # Mock git commands
        mock_subprocess.side_effect = [
            MagicMock(returncode=0, stdout="file.py\n"),
            MagicMock(returncode=0, stdout="abc1234"),
        ]

        mock_react.return_value = dspy.Prediction(
            status="success",
            files_changed="ignored",
            commit_hash="ignored",
        )

        plan_path = PlanDocPath(path=plan_doc)
        stage_execute(
            plan_doc=plan_path,
            objective="implement",
            lm=MagicMock(),
        )

        assert mock_context.current_stage == "execute"
        assert plan_doc in mock_context.extracted_paths[Command.IMPLEMENT_PLAN]
