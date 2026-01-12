"""Tests for StagedWorkflow orchestrator."""

from unittest.mock import MagicMock, patch

from π.workflow.orchestrator import StagedWorkflow
from π.workflow.types import ResearchDocPath, ResearchResult


class TestStagedWorkflowEarlyExit:
    """Tests for early-exit behavior."""

    @patch("π.workflow.orchestrator.stage_research")
    def test_early_exit_when_already_complete(
        self, mock_research: MagicMock, tmp_path
    ) -> None:
        """Should exit after research if needs_implementation=False."""
        # Setup: create valid research doc
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        mock_research.return_value = ResearchResult(
            research_docs=[ResearchDocPath(path=str(doc))],
            summaries=["Feature already exists"],
            needs_implementation=False,
            reason="Already implemented",
        )

        workflow = StagedWorkflow(lm=MagicMock())
        result = workflow.forward("add logging")

        assert result.status == "already_complete"
        assert result.reason == "Already implemented"
        assert hasattr(result, "research_doc_paths")
        # Should NOT have plan_doc_path since we exited early
        assert not hasattr(result, "plan_doc_path") or result.plan_doc_path is None

    @patch("π.workflow.orchestrator.stage_execute")
    @patch("π.workflow.orchestrator.stage_design")
    @patch("π.workflow.orchestrator.stage_research")
    def test_full_workflow_when_implementation_needed(
        self,
        mock_research: MagicMock,
        mock_design: MagicMock,
        mock_execute: MagicMock,
        tmp_path,
    ) -> None:
        """Should execute all stages if needs_implementation=True."""
        from π.workflow.types import DesignResult, ExecuteResult, PlanDocPath

        # Setup: create valid docs
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        research_doc = research_dir / "2026-01-05-test.md"
        research_doc.write_text("# Research")

        plans_dir = tmp_path / "thoughts/shared/plans"
        plans_dir.mkdir(parents=True)
        plan_doc = plans_dir / "2026-01-05-test.md"
        plan_doc.write_text("# Plan")

        mock_research.return_value = ResearchResult(
            research_docs=[ResearchDocPath(path=str(research_doc))],
            summaries=["New feature needed"],
            needs_implementation=True,
        )
        mock_design.return_value = DesignResult(
            plan_doc=PlanDocPath(path=str(plan_doc)),
            summary="Plan created",
        )
        mock_execute.return_value = ExecuteResult(
            status="success",
            files_changed=["test.py"],
            commit_hash="abc1234",
        )

        workflow = StagedWorkflow(lm=MagicMock())
        result = workflow.forward("add new feature")

        assert result.status == "success"
        assert result.commit_hash == "abc1234"
        mock_research.assert_called_once()
        mock_design.assert_called_once()
        mock_execute.assert_called_once()

    @patch("π.workflow.orchestrator.stage_research")
    def test_returns_failed_on_research_error(self, mock_research: MagicMock) -> None:
        """Should return failed status when research raises ValueError."""
        mock_research.side_effect = ValueError("Research failed")

        workflow = StagedWorkflow(lm=MagicMock())
        result = workflow.forward("test objective")

        assert result.status == "failed"
        assert "Research failed" in result.reason

    @patch("π.workflow.orchestrator.stage_design")
    @patch("π.workflow.orchestrator.stage_research")
    def test_returns_failed_on_design_error(
        self, mock_research: MagicMock, mock_design: MagicMock, tmp_path
    ) -> None:
        """Should return failed status when design raises ValueError."""
        # Setup: create valid research doc
        research_dir = tmp_path / "thoughts/shared/research"
        research_dir.mkdir(parents=True)
        doc = research_dir / "2026-01-05-test.md"
        doc.write_text("# Test")

        mock_research.return_value = ResearchResult(
            research_docs=[ResearchDocPath(path=str(doc))],
            summaries=["New feature needed"],
            needs_implementation=True,
        )
        mock_design.side_effect = ValueError("Design failed")

        workflow = StagedWorkflow(lm=MagicMock())
        result = workflow.forward("test objective")

        assert result.status == "failed"
        assert "Design failed" in result.reason
        assert hasattr(result, "research_doc_paths")
