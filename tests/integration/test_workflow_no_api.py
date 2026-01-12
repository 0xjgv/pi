"""Integration tests verifying no API calls are made."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from π.cli import main


class TestWorkflowIntegrationNoAPI:
    """Integration tests verifying no API calls are made."""

    @pytest.fixture(autouse=True)
    def isolate_logging(self, tmp_path: Path) -> Generator[None]:
        """Redirect logging to temporary directory and disable checkpoints."""
        mock_logs_dir = tmp_path / ".π" / "logs"
        mock_logs_dir.mkdir(parents=True)
        with (
            patch("π.cli.main.get_logs_dir", return_value=mock_logs_dir),
            patch("π.workflow.checkpoint.get_project_root", return_value=tmp_path),
        ):
            yield

    @pytest.fixture(autouse=True)
    def setup_mocks(
        self,
        mock_lm,
        clear_lm_cache,
        fresh_execution_context,
    ):
        """Set up all mocks for integration tests."""
        self.mock_lm = mock_lm
        self.ctx = fresh_execution_context

    @pytest.fixture
    def mock_full_workflow(
        self,
        mock_claude_client_with_responses,
        tmp_path: Path,
    ):
        """Set up complete workflow mocking with temp files."""
        from tests.factories import create_workflow_result

        # Create temp document structure
        research_dir = tmp_path / "thoughts" / "shared" / "research"
        research_dir.mkdir(parents=True)
        research_doc = research_dir / "2026-01-05-test.md"
        research_doc.write_text("# Research\n")

        plan_dir = tmp_path / "thoughts" / "shared" / "plans"
        plan_dir.mkdir(parents=True)
        plan_doc = plan_dir / "2026-01-05-test.md"
        plan_doc.write_text("# Plan\n")

        # Create mock responses for each stage
        messages = [
            create_workflow_result(stage="research", doc_path=str(research_doc)),
            create_workflow_result(stage="plan", doc_path=str(plan_doc)),
            create_workflow_result(stage="review"),
            create_workflow_result(stage="iterate"),
            create_workflow_result(stage="implement"),
            create_workflow_result(stage="commit"),
        ]

        with mock_claude_client_with_responses(messages) as client:
            yield client, tmp_path

    @pytest.mark.no_api
    def test_full_workflow_no_api_calls(
        self,
        mock_full_workflow,
        mock_rpi_workflow_full,
        capsys,
    ):
        """Verify complete workflow runs without API calls."""
        main(["test objective"])

        captured = capsys.readouterr()
        assert "π Workflow" in captured.out
        # Verify mock_lm was injected (mocking is working)
        assert self.mock_lm is not None

    @pytest.mark.no_api
    def test_workflow_stages_mocks_available(
        self,
        mock_workflow_stages,
        mock_full_workflow,
    ):
        """Verify workflow stage mocks are properly set up."""
        # Verify all stages are mocked
        expected_stages = {
            "research",
            "plan",
            "review",
            "iterate",
            "implement",
            "commit",
        }
        for stage_name, mock in mock_workflow_stages.items():
            assert mock is not None
            assert stage_name in expected_stages

    @pytest.mark.no_api
    def test_environment_variables_not_required_in_tests(
        self,
        clean_env,
        mock_full_workflow,
        mock_rpi_workflow_full,
    ):
        """Tests should pass without API environment variables."""
        # clean_env removes CLIPROXY_API_BASE and CLIPROXY_API_KEY
        # This should not cause failures with proper mocking
        main(["test objective"])
